"""
Discord API client for bot interactions.

This module provides a client for interacting with Discord's API v10,
specifically for editing interaction responses via webhooks.

Key features:
- Edit original interaction responses
- Message truncation for long responses
- Error handling for rate limits, expired tokens, and auth failures
- Optional bot user validation

Reference: https://discord.com/developers/docs/interactions/receiving-and-responding
"""

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class DiscordClientError(Exception):
    """Base exception for Discord client errors."""
    pass


class DiscordRateLimitError(DiscordClientError):
    """Raised when rate limit is exceeded."""
    pass


class DiscordAuthError(DiscordClientError):
    """Raised when authentication fails."""
    pass


class DiscordInteractionExpiredError(DiscordClientError):
    """Raised when interaction token has expired (15 min limit)."""
    pass


class DiscordClient:
    """
    Discord API client for bot interactions.

    This client handles editing interaction responses using webhook tokens.
    It does NOT handle sending regular channel messages (which require channel_id).

    Attributes:
        application_id: Discord application ID
        bot_token: Discord bot token (used for some operations)
        max_message_length: Maximum message length before truncation (default: 2000)
    """

    # Discord's message length limit
    DEFAULT_MAX_MESSAGE_LENGTH = 2000

    # API base URL
    API_BASE_URL = "https://discord.com/api/v10"

    # Request timeout in seconds
    REQUEST_TIMEOUT = 10.0

    def __init__(
        self,
        application_id: str,
        bot_token: str,
        max_message_length: Optional[int] = None
    ):
        """
        Initialize Discord client.

        Args:
            application_id: Discord application ID
            bot_token: Discord bot token (without "Bot " prefix)
            max_message_length: Maximum message length before truncation
        """
        self.application_id = application_id
        self.bot_token = bot_token
        self.max_message_length = max_message_length or self.DEFAULT_MAX_MESSAGE_LENGTH

        # Validate inputs
        if not application_id:
            raise ValueError("application_id is required")
        if not bot_token:
            raise ValueError("bot_token is required")

    def _get_auth_header(self) -> str:
        """
        Get Authorization header value for bot token.

        Returns:
            Authorization header value in format "Bot {token}"
        """
        return f"Bot {self.bot_token}"

    def _truncate_content(self, content: str) -> tuple[str, bool]:
        """
        Truncate content if it exceeds max length.

        Args:
            content: Message content to truncate

        Returns:
            Tuple of (truncated_content, was_truncated)
        """
        if len(content) <= self.max_message_length:
            return content, False

        truncation_suffix = "...(truncated)"
        max_content_length = self.max_message_length - len(truncation_suffix)
        truncated = content[:max_content_length] + truncation_suffix

        logger.warning(
            "Message truncated",
            extra={
                "original_length": len(content),
                "truncated_length": len(truncated),
                "max_length": self.max_message_length
            }
        )

        return truncated, True

    async def edit_original_response(
        self,
        interaction_token: str,
        content: str
    ) -> None:
        """
        Edit the original interaction response.

        This uses Discord's webhook API to edit the initial response to a slash command.
        The interaction_token is valid for 15 minutes after the interaction is created.

        Args:
            interaction_token: The interaction token from the original interaction
            content: New message content

        Raises:
            DiscordInteractionExpiredError: If the interaction token has expired (15 min)
            DiscordAuthError: If bot_token is invalid
            DiscordRateLimitError: If rate limit is exceeded
            DiscordClientError: For other API errors

        Reference:
            https://discord.com/developers/docs/interactions/receiving-and-responding#edit-original-interaction-response
        """
        if not interaction_token:
            raise ValueError("interaction_token is required")

        # Truncate content if needed
        truncated_content, was_truncated = self._truncate_content(content)

        # Build API URL
        url = f"{self.API_BASE_URL}/webhooks/{self.application_id}/{interaction_token}/messages/@original"

        # Prepare request payload
        payload = {"content": truncated_content}

        # Note: Edit Original Response uses the interaction_token in the URL
        # and does NOT require the Bot token in headers
        headers = {
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT) as client:
            try:
                response = await client.patch(url, json=payload, headers=headers)

                # Handle specific error cases
                if response.status_code == 404:
                    raise DiscordInteractionExpiredError(
                        "Interaction token has expired (15 minute limit)"
                    )
                elif response.status_code == 401:
                    raise DiscordAuthError(
                        "Authentication failed - bot_token is invalid"
                    )
                elif response.status_code == 429:
                    # Parse rate limit information if available
                    retry_after = response.json().get("retry_after", "unknown")
                    raise DiscordRateLimitError(
                        f"Rate limit exceeded. Retry after: {retry_after}s"
                    )
                elif response.status_code >= 400:
                    error_data = response.text
                    try:
                        error_json = response.json()
                        error_data = error_json.get("message", error_data)
                    except Exception:
                        pass

                    raise DiscordClientError(
                        f"Discord API error ({response.status_code}): {error_data}"
                    )

                # Success
                response.raise_for_status()

                logger.info(
                    "Successfully edited interaction response",
                    extra={
                        "truncated": was_truncated,
                        "content_length": len(truncated_content)
                    }
                )

            except httpx.TimeoutException as e:
                raise DiscordClientError(f"Request timeout: {e}")
            except httpx.RequestError as e:
                raise DiscordClientError(f"Request failed: {e}")

    async def get_current_bot_user(self) -> Dict[str, Any]:
        """
        Get current bot user information.

        This is useful for validating the bot token and retrieving bot metadata.

        Returns:
            Dictionary containing bot user information:
            - id: Bot user ID
            - username: Bot username
            - discriminator: Bot discriminator
            - bot: Boolean indicating this is a bot account

        Raises:
            DiscordAuthError: If bot_token is invalid
            DiscordClientError: For other API errors

        Reference:
            https://discord.com/developers/docs/resources/user#get-current-user
        """
        url = f"{self.API_BASE_URL}/users/@me"

        headers = {
            "Authorization": self._get_auth_header()
        }

        async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT) as client:
            try:
                response = await client.get(url, headers=headers)

                if response.status_code == 401:
                    raise DiscordAuthError(
                        "Authentication failed - bot_token is invalid"
                    )
                elif response.status_code >= 400:
                    error_data = response.text
                    try:
                        error_json = response.json()
                        error_data = error_json.get("message", error_data)
                    except Exception:
                        pass

                    raise DiscordClientError(
                        f"Discord API error ({response.status_code}): {error_data}"
                    )

                response.raise_for_status()
                bot_user = response.json()

                logger.info(
                    "Retrieved bot user info",
                    extra={
                        "bot_id": bot_user.get("id"),
                        "username": bot_user.get("username")
                    }
                )

                return bot_user

            except httpx.TimeoutException as e:
                raise DiscordClientError(f"Request timeout: {e}")
            except httpx.RequestError as e:
                raise DiscordClientError(f"Request failed: {e}")


# Example usage
if __name__ == "__main__":
    import asyncio

    async def example_usage():
        """
        Example usage of DiscordClient.

        Note: This requires valid Discord credentials.
        """
        # Initialize client
        client = DiscordClient(
            application_id="YOUR_APPLICATION_ID",
            bot_token="YOUR_BOT_TOKEN"
        )

        # Example 1: Validate bot token by getting bot user info
        try:
            bot_user = await client.get_current_bot_user()
            print(f"Bot User: {bot_user['username']}#{bot_user['discriminator']}")
            print(f"Bot ID: {bot_user['id']}")
        except DiscordAuthError:
            print("Invalid bot token!")
            return

        # Example 2: Edit an interaction response
        # Note: interaction_token comes from the original Discord interaction
        interaction_token = "YOUR_INTERACTION_TOKEN"

        try:
            await client.edit_original_response(
                interaction_token=interaction_token,
                content="Hello from AgentOS! This is an updated response."
            )
            print("Successfully edited interaction response")
        except DiscordInteractionExpiredError:
            print("Interaction expired (>15 minutes old)")
        except DiscordRateLimitError as e:
            print(f"Rate limited: {e}")
        except DiscordClientError as e:
            print(f"Error: {e}")

        # Example 3: Handle long messages (automatic truncation)
        long_message = "A" * 3000  # Exceeds 2000 char limit
        try:
            await client.edit_original_response(
                interaction_token=interaction_token,
                content=long_message
            )
            print("Long message truncated and sent")
        except DiscordClientError as e:
            print(f"Error: {e}")

    # Run example
    # asyncio.run(example_usage())

    print("Discord client module loaded.")
    print("See example_usage() function for usage examples.")
