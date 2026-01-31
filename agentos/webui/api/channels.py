"""Channels API - Webhook endpoints for external communication channels.

This module provides webhook endpoints for CommunicationOS channel adapters.
Each channel adapter registers webhook routes for receiving inbound messages.

Supported Channels:
    - WhatsApp (Twilio): /api/channels/whatsapp_twilio/webhook
    - Telegram: /api/channels/telegram/webhook
    - Slack: /api/channels/slack/webhook

Architecture:
    1. Webhook receives POST request from external platform
    2. Verify signature to ensure authenticity
    3. Parse webhook data to InboundMessage
    4. Process through MessageBus (deduplication, rate limiting, audit)
    5. Check for commands (/session, /help) and handle directly
    6. Forward non-commands to AgentOS chat pipeline
    7. Return 200 OK to acknowledge receipt

Security:
    - Signature verification is REQUIRED for all channels
    - Rate limiting applied via MessageBus middleware
    - Command processing happens before chat forwarding
    - Chat-only mode by default (no execution)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, HTTPException, Form, Header, BackgroundTasks
from fastapi.responses import Response, JSONResponse

from agentos.communicationos.channels import (
    WhatsAppTwilioAdapter,
    TelegramAdapter,
    SlackAdapter,
)
from agentos.communicationos.channels.discord import DiscordAdapter
from agentos.communicationos.channels.sms import SmsAdapter
from agentos.communicationos.commands import CommandProcessor
from agentos.communicationos.message_bus import MessageBus, ProcessingStatus
from agentos.communicationos.registry import ChannelRegistry, ChannelConfigStore
from agentos.communicationos.dedupe import DedupeStore, DedupeMiddleware
from agentos.communicationos.rate_limit import RateLimitStore, RateLimitMiddleware
from agentos.communicationos.audit import AuditStore, AuditMiddleware

logger = logging.getLogger(__name__)

router = APIRouter()

# Global MessageBus instance (initialized on startup)
_message_bus: MessageBus = None
_command_processor: CommandProcessor = None
_channel_registry: ChannelRegistry = None


def initialize_communicationos():
    """Initialize CommunicationOS infrastructure.

    This should be called during application startup to set up the MessageBus,
    middleware, and channel registry.
    """
    global _message_bus, _command_processor, _channel_registry

    if _message_bus is not None:
        logger.info("CommunicationOS already initialized")
        return

    logger.info("Initializing CommunicationOS...")

    # Initialize MessageBus
    _message_bus = MessageBus()

    # Add middleware in order: dedupe -> rate limit -> audit
    dedupe_store = DedupeStore()
    _message_bus.add_middleware(DedupeMiddleware(dedupe_store))

    rate_limit_store = RateLimitStore()
    _message_bus.add_middleware(RateLimitMiddleware(rate_limit_store))

    audit_store = AuditStore()
    _message_bus.add_middleware(AuditMiddleware(audit_store))

    # Initialize CommandProcessor
    _command_processor = CommandProcessor()

    # Initialize ChannelRegistry
    _channel_registry = ChannelRegistry()

    # Load enabled channels and register adapters
    _load_enabled_channels()

    logger.info("CommunicationOS initialized successfully")


def _load_enabled_channels():
    """Load and register all enabled channel adapters."""
    global _message_bus, _channel_registry

    # Get config store
    config_store = ChannelConfigStore()

    # Get all enabled channels
    enabled_channels = config_store.list_channels()

    for channel_status in enabled_channels:
        if not channel_status.get("enabled"):
            continue

        channel_id = channel_status["channel_id"]

        # Get full config
        config = config_store.get_config(channel_id)
        if not config:
            continue

        # Get manifest_id from config
        manifest_id = config.get("manifest_id")
        if not manifest_id:
            logger.warning(f"Channel {channel_id} missing manifest_id")
            continue

        # Load adapter based on manifest_id
        if manifest_id == "whatsapp_twilio":
            try:
                # Create adapter
                adapter = WhatsAppTwilioAdapter(
                    channel_id=channel_id,
                    account_sid=config["account_sid"],
                    auth_token=config["auth_token"],
                    phone_number=config["phone_number"],
                    messaging_service_sid=config.get("messaging_service_sid")
                )

                # Register with MessageBus
                _message_bus.register_adapter(channel_id, adapter)

                logger.info(f"Registered WhatsApp Twilio adapter: {channel_id}")
            except Exception as e:
                logger.exception(f"Failed to load channel {channel_id}: {e}")
        elif manifest_id == "telegram":
            try:
                # Create adapter
                adapter = TelegramAdapter(
                    channel_id=channel_id,
                    bot_token=config["bot_token"],
                    webhook_secret=config["webhook_secret"]
                )

                # Register with MessageBus
                _message_bus.register_adapter(channel_id, adapter)

                logger.info(f"Registered Telegram adapter: {channel_id}")
            except Exception as e:
                logger.exception(f"Failed to load channel {channel_id}: {e}")
        elif manifest_id == "slack":
            try:
                # Create adapter
                adapter = SlackAdapter(
                    channel_id=channel_id,
                    bot_token=config["bot_token"],
                    signing_secret=config["signing_secret"],
                    trigger_policy=config.get("trigger_policy", "mention_or_dm")
                )

                # Register with MessageBus
                _message_bus.register_adapter(channel_id, adapter)

                logger.info(f"Registered Slack adapter: {channel_id}")
            except Exception as e:
                logger.exception(f"Failed to load channel {channel_id}: {e}")
        elif manifest_id == "discord":
            try:
                # Create adapter
                adapter = DiscordAdapter(
                    channel_id=channel_id,
                    application_id=config["application_id"],
                    public_key=config["public_key"],
                    bot_token=config["bot_token"]
                )

                # Register with MessageBus
                _message_bus.register_adapter(channel_id, adapter)

                logger.info(f"Registered Discord adapter: {channel_id}")
            except Exception as e:
                logger.exception(f"Failed to load channel {channel_id}: {e}")
        elif manifest_id == "sms":
            try:
                # Import SMS provider
                from agentos.communicationos.providers.sms import TwilioSmsProvider
                from agentos.communicationos.audit import AuditStore

                # Create Twilio provider
                provider = TwilioSmsProvider(
                    account_sid=config["twilio_account_sid"],
                    auth_token=config["twilio_auth_token"],
                    from_number=config["twilio_from_number"]
                )

                # Create SMS adapter
                adapter = SmsAdapter(
                    channel_id=channel_id,
                    provider=provider,
                    audit_store=AuditStore(),
                    max_length=config.get("sms_max_len", 480),
                    webhook_auth_token=config.get("twilio_auth_token")  # For signature verification
                )

                # Register with MessageBus
                _message_bus.register_adapter(channel_id, adapter)

                logger.info(f"Registered SMS adapter: {channel_id}")
            except Exception as e:
                logger.exception(f"Failed to load SMS channel {channel_id}: {e}")
        else:
            logger.warning(f"Unsupported channel type: {manifest_id}")


async def _forward_to_chat(inbound_message):
    """Forward inbound message to AgentOS chat pipeline.

    This function integrates with the existing AgentOS chat service to process
    messages from external channels.

    Args:
        inbound_message: InboundMessage to forward

    Note:
        This is a placeholder implementation. The actual chat integration will
        depend on the AgentOS chat API structure.
    """
    from agentos.core.chat.service import ChatService
    from agentos.core.chat.models import ChatMessage

    try:
        # Get or create chat session based on channel session
        chat_service = ChatService()

        # Map CommunicationOS session to ChatSession
        # For now, we use the channel_id + user_key as a unique identifier
        session_id = f"{inbound_message.channel_id}_{inbound_message.user_key}"

        # TODO: Implement proper session mapping
        # This should use the SessionRouter to resolve the active session

        # Create chat message
        # Note: This is a simplified implementation
        # The actual implementation needs to handle session resolution properly

        logger.info(
            f"Forwarding message to chat: session_id={session_id}, "
            f"user={inbound_message.user_key}, text={inbound_message.text[:50]}..."
        )

        # Here we would call the chat service to process the message
        # For now, just log it as a placeholder
        logger.warning(
            "Chat forwarding not fully implemented yet. "
            "Message logged but not processed by chat pipeline."
        )

    except Exception as e:
        logger.exception(f"Failed to forward message to chat: {e}")


@router.post("/whatsapp_twilio/webhook")
async def whatsapp_twilio_webhook(
    request: Request,
    x_twilio_signature: str = Header(None, alias="X-Twilio-Signature")
):
    """Webhook endpoint for WhatsApp (Twilio).

    This endpoint receives webhook POST requests from Twilio when WhatsApp
    messages are sent to the configured number.

    Headers:
        X-Twilio-Signature: HMAC-SHA256 signature for verification

    Request Body:
        Form-encoded webhook data from Twilio

    Returns:
        200 OK if message processed successfully
        400 Bad Request if signature verification fails
        500 Internal Server Error if processing fails

    Security:
        - Signature verification is MANDATORY
        - Rate limiting applied via MessageBus
        - Commands processed separately from chat
    """
    # Initialize if not already done
    if _message_bus is None:
        initialize_communicationos()

    # Get form data
    form_data = await request.form()
    webhook_data = dict(form_data)

    # Get channel_id from URL or configuration
    # For now, we'll look up based on the "To" number
    to_number = webhook_data.get("To", "").replace("whatsapp:", "")

    # Find the adapter for this number
    # In a production setup, this would be a proper lookup
    # For now, we'll use a simple approach
    channel_id = None
    adapter = None

    for cid, adp in _message_bus._adapters.items():
        if hasattr(adp, 'phone_number') and adp.phone_number == to_number:
            channel_id = cid
            adapter = adp
            break

    if not adapter:
        logger.error(f"No adapter found for WhatsApp number: {to_number}")
        raise HTTPException(
            status_code=400,
            detail=f"No channel configured for number: {to_number}"
        )

    # Verify signature
    if not x_twilio_signature:
        logger.error("Missing X-Twilio-Signature header")
        raise HTTPException(
            status_code=400,
            detail="Missing X-Twilio-Signature header"
        )

    # Get full URL for signature verification
    url = str(request.url)

    # Verify signature
    is_valid = adapter.verify_webhook_signature(
        x_twilio_signature,
        url,
        webhook_data
    )

    if not is_valid:
        logger.error(f"Invalid Twilio signature for channel: {channel_id}")
        raise HTTPException(
            status_code=400,
            detail="Invalid webhook signature"
        )

    logger.info(f"Twilio signature verified for channel: {channel_id}")

    try:
        # Parse webhook data to InboundMessage
        inbound_message = adapter.parse_event(webhook_data)

        # Process through MessageBus
        context = await _message_bus.process_inbound(inbound_message)

        # Check processing status
        if context.status == ProcessingStatus.REJECT:
            logger.info(
                f"Message rejected by middleware: {context.error}"
            )
            # Still return 200 to Twilio to acknowledge receipt
            return Response(status_code=200)

        if context.status == ProcessingStatus.ERROR:
            logger.error(
                f"Error processing message: {context.error}"
            )
            # Return 500 so Twilio will retry
            raise HTTPException(
                status_code=500,
                detail="Failed to process message"
            )

        # Check if message is a command
        if inbound_message.text and _command_processor.is_command(inbound_message.text):
            logger.info(f"Processing command: {inbound_message.text}")

            # Process command
            response = _command_processor.process_command(
                inbound_message.text,
                inbound_message.channel_id,
                inbound_message.user_key,
                inbound_message.conversation_key
            )

            # Send response through MessageBus
            await _message_bus.send_outbound(response)

            logger.info(f"Command response sent to user: {inbound_message.user_key}")
        else:
            # Forward to chat pipeline
            logger.info("Forwarding non-command message to chat")
            await _forward_to_chat(inbound_message)

        # Return 200 OK to acknowledge receipt
        return Response(status_code=200)

    except ValueError as e:
        logger.exception(f"Invalid webhook data: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid webhook data: {str(e)}"
        )
    except Exception as e:
        logger.exception(f"Failed to process webhook: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None, alias="X-Telegram-Bot-Api-Secret-Token")
):
    """Webhook endpoint for Telegram Bot API.

    This endpoint receives webhook POST requests from Telegram when messages
    are sent to the configured bot.

    Headers:
        X-Telegram-Bot-Api-Secret-Token: Secret token for verification

    Request Body:
        JSON-encoded Telegram update data

    Returns:
        200 OK if message processed successfully (always return 200 to avoid retries)
        400 Bad Request if secret token verification fails

    Security:
        - Secret token verification is MANDATORY
        - Rate limiting applied via MessageBus
        - Bot loop protection (ignores messages from bots)
        - Commands processed separately from chat

    Important:
        Always return 200 OK to Telegram, even if internal processing fails.
        This prevents Telegram from retrying the same message repeatedly.
    """
    # Initialize if not already done
    if _message_bus is None:
        initialize_communicationos()

    # Get JSON body
    try:
        update_data = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse Telegram webhook JSON: {e}")
        # Return 200 to prevent retries
        return Response(status_code=200)

    # Extract message to find the channel
    # For Telegram, we need to determine which adapter to use based on bot
    # For now, we'll try all Telegram adapters until one validates
    channel_id = None
    adapter = None

    for cid, adp in _message_bus._adapters.items():
        if isinstance(adp, TelegramAdapter):
            # Verify secret token
            if adp.verify_secret(x_telegram_bot_api_secret_token):
                channel_id = cid
                adapter = adp
                break

    if not adapter:
        logger.error("No Telegram adapter found or secret token invalid")
        # Still return 200 to prevent retries
        return Response(status_code=200)

    logger.info(f"Telegram webhook verified for channel: {channel_id}")

    try:
        # Parse update to InboundMessage
        inbound_message = adapter.parse_update(update_data)

        # If message should be ignored (e.g., from bot), return success
        if inbound_message is None:
            logger.debug("Telegram update ignored (bot message or unsupported type)")
            return Response(status_code=200)

        # Process through MessageBus
        context = await _message_bus.process_inbound(inbound_message)

        # Check processing status
        if context.status == ProcessingStatus.REJECT:
            logger.info(
                f"Message rejected by middleware: {context.error}"
            )
            # Still return 200 to acknowledge receipt
            return Response(status_code=200)

        if context.status == ProcessingStatus.ERROR:
            logger.error(
                f"Error processing message: {context.error}"
            )
            # Return 200 to prevent retries (internal errors shouldn't cause retries)
            return Response(status_code=200)

        # Check if message is a command
        if inbound_message.text and _command_processor.is_command(inbound_message.text):
            logger.info(f"Processing command: {inbound_message.text}")

            # Process command
            response = _command_processor.process_command(
                inbound_message.text,
                inbound_message.channel_id,
                inbound_message.user_key,
                inbound_message.conversation_key
            )

            # Send response through MessageBus
            await _message_bus.send_outbound(response)

            logger.info(f"Command response sent to user: {inbound_message.user_key}")
        else:
            # Forward to chat pipeline
            logger.info("Forwarding non-command message to chat")
            await _forward_to_chat(inbound_message)

        # Return 200 OK to acknowledge receipt
        return Response(status_code=200)

    except ValueError as e:
        logger.exception(f"Invalid webhook data: {e}")
        # Return 200 to prevent retries
        return Response(status_code=200)
    except Exception as e:
        logger.exception(f"Failed to process webhook: {e}")
        # Return 200 to prevent retries
        return Response(status_code=200)


async def _process_slack_event_async(
    channel_id: str,
    adapter: SlackAdapter,
    event_data: Dict[str, Any]
):
    """Process Slack event asynchronously.

    This function is run as a background task to ensure the webhook
    responds within 3 seconds while still processing the event.

    Args:
        channel_id: Channel ID
        adapter: SlackAdapter instance
        event_data: Slack event data
    """
    try:
        # Parse event to InboundMessage
        inbound_message = adapter.parse_event(event_data)

        # If message should be ignored, return
        if inbound_message is None:
            logger.debug("Slack event ignored (bot message or filtered)")
            return

        # Process through MessageBus
        context = await _message_bus.process_inbound(inbound_message)

        # Check processing status
        if context.status == ProcessingStatus.REJECT:
            logger.info(
                f"Message rejected by middleware: {context.error}"
            )
            return

        if context.status == ProcessingStatus.ERROR:
            logger.error(
                f"Error processing message: {context.error}"
            )
            return

        # Check if message is a command
        if inbound_message.text and _command_processor.is_command(inbound_message.text):
            logger.info(f"Processing command: {inbound_message.text}")

            # Process command
            response = _command_processor.process_command(
                inbound_message.text,
                inbound_message.channel_id,
                inbound_message.user_key,
                inbound_message.conversation_key
            )

            # Send response through MessageBus
            await _message_bus.send_outbound(response)

            logger.info(f"Command response sent to user: {inbound_message.user_key}")
        else:
            # Forward to chat pipeline
            logger.info("Forwarding non-command message to chat")
            await _forward_to_chat(inbound_message)

    except Exception as e:
        logger.exception(f"Failed to process Slack event async: {e}")


@router.post("/slack/webhook")
async def slack_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_slack_request_timestamp: str = Header(None, alias="X-Slack-Request-Timestamp"),
    x_slack_signature: str = Header(None, alias="X-Slack-Signature"),
    x_slack_retry_num: Optional[str] = Header(None, alias="X-Slack-Retry-Num")
):
    """Webhook endpoint for Slack Events API.

    This endpoint receives webhook POST requests from Slack when events
    occur in your Slack workspace (messages, mentions, etc.).

    Headers:
        X-Slack-Request-Timestamp: Request timestamp for signature verification
        X-Slack-Signature: HMAC-SHA256 signature for verification
        X-Slack-Retry-Num: Present if this is a retry (for idempotency)

    Request Body:
        JSON-encoded Slack event data

    Returns:
        200 OK within 3 seconds (REQUIRED by Slack)
        For URL verification: JSON with challenge
        For events: 200 OK immediately, process async

    Security:
        - Signature verification is MANDATORY
        - Timestamp validation prevents replay attacks
        - Rate limiting applied via MessageBus
        - Bot loop protection (ignores bot messages)
        - Idempotency handling for retries

    Important:
        MUST respond within 3 seconds or Slack will retry.
        Use BackgroundTasks for async processing.

    Reference:
        https://api.slack.com/apis/connections/events-api
    """
    # Initialize if not already done
    if _message_bus is None:
        initialize_communicationos()

    # Get raw body for signature verification
    body = await request.body()
    body_str = body.decode('utf-8')

    # Parse JSON
    try:
        event_data = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse Slack webhook JSON: {e}")
        return Response(status_code=200)

    # Handle URL verification challenge
    # This must be handled immediately (not async)
    if event_data.get("type") == "url_verification":
        challenge = event_data.get("challenge")
        if challenge:
            logger.info("Handling Slack URL verification challenge")
            return JSONResponse({"challenge": challenge})
        else:
            logger.error("URL verification missing challenge")
            return Response(status_code=400)

    # Find matching Slack adapter based on signature verification
    # We need to verify signature to determine which adapter to use
    channel_id = None
    adapter = None

    for cid, adp in _message_bus._adapters.items():
        if isinstance(adp, SlackAdapter):
            # Verify signature
            if x_slack_signature and x_slack_request_timestamp:
                if adp.verify_signature(
                    x_slack_request_timestamp,
                    body_str,
                    x_slack_signature
                ):
                    channel_id = cid
                    adapter = adp
                    break

    if not adapter:
        logger.error("No Slack adapter found or signature verification failed")
        # Still return 200 to prevent retries
        return Response(status_code=200)

    logger.info(f"Slack webhook verified for channel: {channel_id}")

    # Check if this is a retry
    if x_slack_retry_num:
        retry_num = x_slack_retry_num
        logger.info(
            f"Slack retry detected: retry_num={retry_num}, "
            f"channel={channel_id}"
        )
        # Idempotency will be handled by the adapter's event tracking

    # CRITICAL: Return 200 OK immediately (within 3 seconds)
    # Process event asynchronously in background
    background_tasks.add_task(
        _process_slack_event_async,
        channel_id,
        adapter,
        event_data
    )

    # Return 200 OK immediately
    return Response(status_code=200)


@router.get("/status")
async def channels_status():
    """Get status of all registered channels.

    Returns:
        Dict with channel status information
    """
    if _message_bus is None:
        return {
            "initialized": False,
            "channels": []
        }

    return {
        "initialized": True,
        "channels": list(_message_bus._adapters.keys()),
        "middleware_count": len(_message_bus._middleware)
    }


@router.get("/manifests")
async def list_manifests():
    """List all available channel manifests.

    Returns:
        List of channel manifests with metadata
    """
    if _channel_registry is None:
        initialize_communicationos()

    manifests = _channel_registry.list_manifests()
    return {
        "ok": True,
        "data": {
            "manifests": [m.to_dict() for m in manifests]
        }
    }


@router.get("/manifests/{manifest_id}")
async def get_manifest(manifest_id: str):
    """Get full manifest for a specific channel.

    Args:
        manifest_id: Channel manifest identifier

    Returns:
        Full channel manifest including setup steps
    """
    if _channel_registry is None:
        initialize_communicationos()

    manifest = _channel_registry.get_manifest(manifest_id)
    if not manifest:
        raise HTTPException(
            status_code=404,
            detail=f"Manifest not found: {manifest_id}"
        )

    return {
        "ok": True,
        "data": manifest.to_dict()
    }


@router.post("/manifests/{manifest_id}/validate")
async def validate_config(manifest_id: str, request: Request):
    """Validate channel configuration against manifest.

    Args:
        manifest_id: Channel manifest identifier
        request: Request with config in body

    Returns:
        Validation result
    """
    if _channel_registry is None:
        initialize_communicationos()

    manifest = _channel_registry.get_manifest(manifest_id)
    if not manifest:
        raise HTTPException(
            status_code=404,
            detail=f"Manifest not found: {manifest_id}"
        )

    body = await request.json()
    config = body.get("config", {})

    is_valid, error_message = manifest.validate_config(config)

    return {
        "ok": is_valid,
        "data": {
            "valid": is_valid,
            "error": error_message
        }
    }


@router.post("/manifests/{manifest_id}/test")
async def test_channel(manifest_id: str, request: Request):
    """Test channel configuration.

    This endpoint attempts to verify the channel configuration by testing
    the webhook signature validation and basic connectivity.

    Args:
        manifest_id: Channel manifest identifier
        request: Request with config in body

    Returns:
        Test result with diagnostics
    """
    if _channel_registry is None:
        initialize_communicationos()

    manifest = _channel_registry.get_manifest(manifest_id)
    if not manifest:
        raise HTTPException(
            status_code=404,
            detail=f"Manifest not found: {manifest_id}"
        )

    body = await request.json()
    config = body.get("config", {})

    # Validate config first
    is_valid, error_message = manifest.validate_config(config)
    if not is_valid:
        return {
            "ok": False,
            "data": {
                "success": False,
                "error": f"Configuration validation failed: {error_message}",
                "diagnostics": {
                    "step": "validation",
                    "details": error_message
                }
            }
        }

    # For WhatsApp Twilio, test credentials
    if manifest_id == "whatsapp_twilio":
        try:
            # Try to create adapter to validate credentials
            from agentos.communicationos.channels import WhatsAppTwilioAdapter

            adapter = WhatsAppTwilioAdapter(
                channel_id="test_channel",
                account_sid=config.get("account_sid"),
                auth_token=config.get("auth_token"),
                phone_number=config.get("phone_number"),
                messaging_service_sid=config.get("messaging_service_sid")
            )

            # Test basic validation
            # Note: Full test would require calling Twilio API
            return {
                "ok": True,
                "data": {
                    "success": True,
                    "message": "Configuration appears valid. Webhook is ready to receive messages.",
                    "diagnostics": {
                        "step": "validation",
                        "details": "Credentials format validated successfully"
                    }
                }
            }
        except Exception as e:
            logger.exception(f"Channel test failed: {e}")
            return {
                "ok": False,
                "data": {
                    "success": False,
                    "error": f"Test failed: {str(e)}",
                    "diagnostics": {
                        "step": "adapter_creation",
                        "details": str(e),
                        "common_issues": [
                            "Invalid Account SID or Auth Token",
                            "Phone number format incorrect (should be +1234567890)",
                            "Network connectivity issues"
                        ]
                    }
                }
            }
    elif manifest_id == "telegram":
        try:
            # Try to create adapter and test webhook info
            from agentos.communicationos.channels.telegram import (
                TelegramAdapter,
                get_webhook_info,
            )

            adapter = TelegramAdapter(
                channel_id="test_channel",
                bot_token=config.get("bot_token"),
                webhook_secret=config.get("webhook_secret")
            )

            # Test by getting webhook info from Telegram
            success, webhook_info = get_webhook_info(config.get("bot_token"))

            if success:
                return {
                    "ok": True,
                    "data": {
                        "success": True,
                        "message": "Bot token is valid. Webhook is ready to receive messages.",
                        "diagnostics": {
                            "step": "api_test",
                            "details": f"Webhook URL: {webhook_info.get('url', 'Not set')}",
                            "webhook_info": webhook_info
                        }
                    }
                }
            else:
                return {
                    "ok": False,
                    "data": {
                        "success": False,
                        "error": "Failed to verify bot token",
                        "diagnostics": {
                            "step": "api_test",
                            "details": "Could not retrieve webhook info from Telegram",
                            "common_issues": [
                                "Invalid bot token",
                                "Network connectivity issues",
                                "Bot token revoked"
                            ]
                        }
                    }
                }
        except Exception as e:
            logger.exception(f"Telegram test failed: {e}")
            return {
                "ok": False,
                "data": {
                    "success": False,
                    "error": f"Test failed: {str(e)}",
                    "diagnostics": {
                        "step": "adapter_creation",
                        "details": str(e),
                        "common_issues": [
                            "Invalid bot token format",
                            "Missing webhook_secret",
                            "Network connectivity issues"
                        ]
                    }
                }
            }
    elif manifest_id == "slack":
        try:
            # Try to create adapter and test auth
            from agentos.communicationos.channels.slack import (
                SlackAdapter,
                auth_test,
            )

            adapter = SlackAdapter(
                channel_id="test_channel",
                bot_token=config.get("bot_token"),
                signing_secret=config.get("signing_secret"),
                trigger_policy=config.get("trigger_policy", "mention_or_dm")
            )

            # Test by calling auth.test API
            success, auth_info = auth_test(config.get("bot_token"))

            if success:
                return {
                    "ok": True,
                    "data": {
                        "success": True,
                        "message": "Bot token is valid. Webhook is ready to receive events.",
                        "diagnostics": {
                            "step": "api_test",
                            "details": f"Team: {auth_info.get('team')}, User: {auth_info.get('user')}",
                            "auth_info": auth_info
                        }
                    }
                }
            else:
                return {
                    "ok": False,
                    "data": {
                        "success": False,
                        "error": "Failed to verify bot token",
                        "diagnostics": {
                            "step": "api_test",
                            "details": "Could not authenticate with Slack API",
                            "common_issues": [
                                "Invalid bot token",
                                "Bot token revoked",
                                "Incorrect token format (should start with xoxb-)",
                                "Network connectivity issues"
                            ]
                        }
                    }
                }
        except Exception as e:
            logger.exception(f"Slack test failed: {e}")
            return {
                "ok": False,
                "data": {
                    "success": False,
                    "error": f"Test failed: {str(e)}",
                    "diagnostics": {
                        "step": "adapter_creation",
                        "details": str(e),
                        "common_issues": [
                            "Invalid bot token format",
                            "Missing signing_secret",
                            "Network connectivity issues"
                        ]
                    }
                }
            }
    elif manifest_id == "sms":
        # SMS channel test - send a test message if test_to_number is provided
        try:
            from agentos.communicationos.channels.sms import SmsAdapter
            from agentos.communicationos.providers.sms import TwilioSmsProvider

            # Create Twilio provider
            provider = TwilioSmsProvider(
                account_sid=config.get("twilio_account_sid"),
                auth_token=config.get("twilio_auth_token"),
                from_number=config.get("twilio_from_number")
            )

            # Validate provider configuration
            is_valid, error_msg = provider.validate_config()
            if not is_valid:
                return {
                    "ok": False,
                    "data": {
                        "success": False,
                        "error": f"Configuration validation failed: {error_msg}",
                        "diagnostics": {
                            "step": "validation",
                            "details": error_msg
                        }
                    }
                }

            # Test connection
            test_to_number = config.get("test_to_number")
            success, error_msg = provider.test_connection(test_to_number)

            if success:
                if test_to_number:
                    message = f"Test SMS sent successfully to {test_to_number}. Check the phone for the message."
                else:
                    message = "Twilio credentials validated successfully. Ready to send SMS."

                return {
                    "ok": True,
                    "data": {
                        "success": True,
                        "message": message,
                        "diagnostics": {
                            "step": "connection_test",
                            "details": "Twilio API connection successful",
                            "test_sms_sent": bool(test_to_number)
                        }
                    }
                }
            else:
                return {
                    "ok": False,
                    "data": {
                        "success": False,
                        "error": f"Connection test failed: {error_msg}",
                        "diagnostics": {
                            "step": "connection_test",
                            "details": error_msg,
                            "common_issues": [
                                "Invalid Account SID or Auth Token",
                                "From number not SMS-enabled in Twilio",
                                "Test number not verified (trial accounts)",
                                "Invalid phone number format (must be E.164)",
                                "Network connectivity issues"
                            ]
                        }
                    }
                }
        except Exception as e:
            logger.exception(f"SMS test failed: {e}")
            return {
                "ok": False,
                "data": {
                    "success": False,
                    "error": f"Test failed: {str(e)}",
                    "diagnostics": {
                        "step": "adapter_creation",
                        "details": str(e),
                        "common_issues": [
                            "Invalid configuration format",
                            "Missing required fields",
                            "Network connectivity issues"
                        ]
                    }
                }
            }
    else:
        # Generic test for other channels
        return {
            "ok": True,
            "data": {
                "success": True,
                "message": "Configuration validated successfully",
                "diagnostics": {
                    "step": "validation",
                    "details": "Channel configuration format is correct"
                }
            }
        }


async def _process_discord_interaction_async(
    channel_id: str,
    adapter: DiscordAdapter,
    interaction: Dict[str, Any]
):
    """Process Discord interaction asynchronously.

    This function is run as a background task to ensure the webhook
    responds within 3 seconds while still processing the interaction.

    Args:
        channel_id: Channel ID
        adapter: DiscordAdapter instance
        interaction: Discord interaction data
    """
    try:
        # Process through adapter's async handler
        await adapter.process_slash_command_async(
            interaction=interaction,
            message_bus=_message_bus
        )

    except Exception as e:
        logger.exception(f"Failed to process Discord interaction async: {e}")


@router.post("/discord/interactions")
async def discord_interactions(
    request: Request,
    background_tasks: BackgroundTasks,
    x_signature_ed25519: str = Header(None, alias="X-Signature-Ed25519"),
    x_signature_timestamp: str = Header(None, alias="X-Signature-Timestamp")
):
    """Webhook endpoint for Discord Interactions API.

    This endpoint receives webhook POST requests from Discord when slash
    commands are invoked in your Discord server.

    Headers:
        X-Signature-Ed25519: Ed25519 signature for verification
        X-Signature-Timestamp: Request timestamp for signature verification

    Request Body:
        JSON-encoded Discord interaction data

    Returns:
        For PING (type=1): JSON with type=1 (PONG)
        For slash commands (type=2): JSON with type=5 (DEFERRED) immediately,
                                     then process async in background

    Security:
        - Ed25519 signature verification is MANDATORY
        - Rate limiting applied via MessageBus
        - Idempotency handled by adapter

    Important:
        MUST respond within 3 seconds or Discord will timeout and mark interaction failed.
        Use BackgroundTasks for async processing after defer.

    Reference:
        https://discord.com/developers/docs/interactions/receiving-and-responding
    """
    # Initialize if not already done
    if _message_bus is None:
        initialize_communicationos()

    # Get raw body for signature verification
    body = await request.body()

    # Verify signature headers present
    if not x_signature_ed25519 or not x_signature_timestamp:
        logger.error("Discord webhook missing signature headers")
        return Response(status_code=401, content="Unauthorized: Missing signature headers")

    # Parse JSON
    try:
        interaction = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse Discord webhook JSON: {e}")
        return Response(status_code=400, content="Bad Request: Invalid JSON")

    # Find matching Discord adapter based on signature verification
    # We need to verify signature to determine which adapter to use
    channel_id = None
    adapter = None

    for cid, adp in _message_bus._adapters.items():
        if isinstance(adp, DiscordAdapter):
            # Verify signature
            if adp.verify_signature(
                signature=x_signature_ed25519,
                timestamp=x_signature_timestamp,
                body=body
            ):
                channel_id = cid
                adapter = adp
                break

    if not adapter:
        logger.error("No Discord adapter found or signature verification failed")
        return Response(status_code=401, content="Unauthorized: Invalid signature")

    logger.info(f"Discord webhook verified for channel: {channel_id}")

    # Get interaction type
    interaction_type = interaction.get("type")

    # Handle PING (type=1) - Must respond immediately
    if interaction_type == adapter.INTERACTION_TYPE_PING:
        response = adapter.handle_ping(interaction)
        logger.info(f"Handled Discord PING for channel: {channel_id}")
        return JSONResponse(response)

    # Handle APPLICATION_COMMAND (type=2) - Slash commands
    if interaction_type == adapter.INTERACTION_TYPE_APPLICATION_COMMAND:
        # CRITICAL: Return defer immediately (within 3 seconds)
        defer_response = adapter.handle_slash_command(interaction)

        # Process interaction asynchronously in background
        background_tasks.add_task(
            _process_discord_interaction_async,
            channel_id,
            adapter,
            interaction
        )

        # Return defer response immediately
        logger.info(
            f"Deferred Discord slash command: interaction_id={interaction.get('id')}, "
            f"channel={channel_id}"
        )
        return JSONResponse(defer_response)

    # Unknown interaction type - log and acknowledge
    logger.warning(
        f"Unknown Discord interaction type: {interaction_type}, "
        f"channel={channel_id}"
    )
    return Response(status_code=200)


@router.post("/sms/twilio/webhook/{path_token}")
async def sms_twilio_webhook(
    path_token: str,
    request: Request,
    background_tasks: BackgroundTasks,
    x_twilio_signature: Optional[str] = Header(None, alias="X-Twilio-Signature")
):
    """Webhook endpoint for Twilio SMS (inbound messages).

    This endpoint receives webhook POST requests from Twilio when SMS messages
    are received by the configured phone number.

    Security Layers:
        1. Path token in URL (prevents URL guessing)
        2. Twilio signature verification (HMAC-SHA1, mandatory)

    Flow:
        1. Verify path token matches configuration
        2. Verify Twilio signature (HMAC-SHA1 with Auth Token)
        3. Parse webhook data to InboundMessage
        4. Return 200 OK immediately (Twilio expects fast response)
        5. Process message asynchronously in background
        6. Generate reply via MessageBus if needed

    Args:
        path_token: Secret token from URL path (prevents unauthorized access)
        request: FastAPI request object
        background_tasks: FastAPI background tasks
        x_twilio_signature: Twilio signature header for verification

    Returns:
        200 OK: Message received and will be processed
        401 Unauthorized: Invalid path token or signature
        404 Not Found: Invalid path token

    Headers:
        X-Twilio-Signature: HMAC-SHA1 signature (required)

    Request Body (form-encoded):
        - MessageSid: Unique message ID
        - From: Sender phone number (E.164)
        - To: Recipient phone number (E.164)
        - Body: Message text content
        - NumMedia: Number of media attachments

    Security Note:
        Always return 200 OK after validation to acknowledge receipt.
        Processing happens asynchronously to avoid Twilio timeout.
    """
    # Initialize if not already done
    if _message_bus is None:
        initialize_communicationos()

    # Get form data from Twilio webhook
    try:
        form_data = await request.form()
        post_data = dict(form_data)
    except Exception as e:
        logger.error(f"Failed to parse Twilio SMS webhook form data: {e}")
        raise HTTPException(
            status_code=400,
            detail="Invalid form data"
        )

    # Log webhook receipt (without sensitive data)
    logger.info(
        f"Received SMS webhook: path_token={path_token[:8]}..., "
        f"MessageSid={post_data.get('MessageSid', 'unknown')}"
    )

    # Find SMS adapter by verifying path_token
    # Path token is stored in channel config and used for security
    from agentos.communicationos.registry import ChannelConfigStore
    config_store = ChannelConfigStore()

    channel_id = None
    adapter = None

    # Iterate through registered SMS adapters
    for cid, adp in _message_bus._adapters.items():
        # Check if it's an SMS adapter
        # (We need to import SmsAdapter to check instance)
        try:
            from agentos.communicationos.channels.sms import SmsAdapter
            if isinstance(adp, SmsAdapter):
                # Get channel config to verify path token
                config = config_store.get_config(cid)
                if config and config.get("webhook_path_token") == path_token:
                    channel_id = cid
                    adapter = adp
                    break
        except ImportError:
            logger.warning("SMS adapter not available")
            continue

    if not adapter:
        logger.warning(f"Invalid path token or no SMS adapter found: {path_token[:8]}...")
        raise HTTPException(
            status_code=404,
            detail="Not found"
        )

    logger.info(f"Path token verified for SMS channel: {channel_id}")

    # Verify Twilio signature (critical security check)
    if not x_twilio_signature:
        logger.error(f"Missing X-Twilio-Signature header for channel: {channel_id}")
        raise HTTPException(
            status_code=401,
            detail="Missing X-Twilio-Signature header"
        )

    # Get full URL for signature verification
    url = str(request.url)

    # Verify signature
    is_valid = adapter.verify_twilio_signature(
        url=url,
        post_data=post_data,
        signature=x_twilio_signature
    )

    if not is_valid:
        logger.error(f"Invalid Twilio signature for SMS channel: {channel_id}")
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature"
        )

    logger.info(f"Twilio signature verified for SMS channel: {channel_id}")

    # Parse webhook data to InboundMessage
    inbound_message = adapter.parse_inbound_webhook(post_data)

    if not inbound_message:
        # Duplicate or invalid message - silently ignore
        logger.debug(f"SMS webhook ignored (duplicate or invalid): {post_data.get('MessageSid')}")
        return Response(status_code=200)

    # Process asynchronously in background
    background_tasks.add_task(
        _process_sms_inbound_async,
        channel_id,
        adapter,
        inbound_message
    )

    # Return 200 OK immediately (Twilio needs fast response)
    logger.info(
        f"SMS webhook acknowledged: MessageSid={inbound_message.message_id}, "
        f"channel={channel_id}"
    )
    return Response(status_code=200)


async def _process_sms_inbound_async(
    channel_id: str,
    adapter,
    inbound_message: InboundMessage
):
    """Background task to process inbound SMS message.

    This runs asynchronously after returning 200 OK to Twilio.

    Flow:
        1. Process through MessageBus (deduplication, rate limiting)
        2. Check if message is a command (/help, /session, etc.)
        3. Generate reply via chat pipeline if not a command
        4. Send reply via adapter.handle_outbound()

    Args:
        channel_id: SMS channel identifier
        adapter: SmsAdapter instance
        inbound_message: Parsed InboundMessage
    """
    try:
        # Process through MessageBus
        context = await _message_bus.process_inbound(inbound_message)

        # Check processing status
        if context.status == ProcessingStatus.REJECT:
            logger.info(
                f"SMS message rejected by middleware: {context.error}"
            )
            return

        if context.status == ProcessingStatus.ERROR:
            logger.error(
                f"Error processing SMS message: {context.error}"
            )
            return

        # Check if message is a command
        if inbound_message.text and _command_processor.is_command(inbound_message.text):
            logger.info(f"Processing SMS command: {inbound_message.text}")

            # Process command
            response = _command_processor.process_command(
                inbound_message.text,
                inbound_message.channel_id,
                inbound_message.user_key,
                inbound_message.conversation_key
            )

            # Send response through adapter
            adapter.handle_outbound(response)

            logger.info(f"SMS command response sent to user: {inbound_message.user_key}")
        else:
            # Forward to chat pipeline
            logger.info("Forwarding SMS to chat pipeline")
            await _forward_to_chat(inbound_message)

    except Exception as e:
        logger.exception(f"Failed to process SMS inbound message: {e}")
        # Don't re-raise - we already returned 200 to Twilio
