"""
MCP Client - JSON-RPC 2.0 over stdio implementation

This module implements a client for the Model Context Protocol (MCP) using
stdio transport. It handles:
- Process lifecycle management
- JSON-RPC 2.0 communication
- Tool discovery and invocation
- Error handling and timeouts

Protocol Reference:
- Request: {"jsonrpc": "2.0", "id": <int>, "method": <string>, "params": <object>}
- Response: {"jsonrpc": "2.0", "id": <int>, "result": <any>}
- Error: {"jsonrpc": "2.0", "id": <int>, "error": {"code": <int>, "message": <string>}}
"""

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from agentos.core.mcp.config import MCPServerConfig

logger = logging.getLogger(__name__)


class MCPClientError(Exception):
    """Base exception for MCP client errors"""
    pass


class MCPConnectionError(MCPClientError):
    """Raised when connection fails"""
    pass


class MCPTimeoutError(MCPClientError):
    """Raised when operation times out"""
    pass


class MCPProtocolError(MCPClientError):
    """Raised when protocol violation occurs"""
    pass


class MCPClient:
    """
    MCP stdio client implementation

    Manages a subprocess running an MCP server and communicates via stdio
    using JSON-RPC 2.0 protocol.

    Example:
        config = MCPServerConfig(
            id="test-server",
            command=["node", "server.js"]
        )
        client = MCPClient(config)
        await client.connect()
        tools = await client.list_tools()
        result = await client.call_tool("tool_name", {"arg": "value"})
        await client.disconnect()
    """

    def __init__(self, server_config: MCPServerConfig):
        """
        Initialize MCP client

        Args:
            server_config: MCP server configuration
        """
        self.config = server_config
        self.process: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self._connected = False

    async def connect(self) -> bool:
        """
        Connect to MCP server

        Starts the server process and initializes communication.

        Returns:
            True if connection successful

        Raises:
            MCPConnectionError: If connection fails
        """
        if self._connected:
            logger.warning(f"MCP client already connected: {self.config.id}")
            return True

        try:
            logger.info(f"Connecting to MCP server: {self.config.id}")
            logger.debug(f"Command: {' '.join(self.config.command)}")

            # Prepare environment
            env = {**self.config.env}
            # Inherit parent environment
            import os
            env = {**os.environ, **env}

            # Start subprocess
            self.process = await asyncio.create_subprocess_exec(
                *self.config.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )

            # Start reader task
            self._reader_task = asyncio.create_task(self._read_loop())

            # Send initialize request (MCP handshake)
            try:
                result = await self._send_request(
                    "initialize",
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "agentos",
                            "version": "0.3.1"
                        }
                    },
                    timeout_ms=5000
                )
                logger.info(f"MCP server initialized: {self.config.id}")
                logger.debug(f"Server info: {result.get('serverInfo', {})}")

                # Send initialized notification
                await self._send_notification("notifications/initialized")

            except Exception as e:
                logger.error(f"Failed to initialize MCP server: {e}")
                await self.disconnect()
                raise MCPConnectionError(f"Failed to initialize: {e}") from e

            self._connected = True
            logger.info(f"Successfully connected to MCP server: {self.config.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to MCP server {self.config.id}: {e}", exc_info=True)
            await self.disconnect()
            raise MCPConnectionError(f"Connection failed: {e}") from e

    async def disconnect(self):
        """
        Disconnect from MCP server

        Gracefully shuts down the connection and terminates the process.
        """
        if not self._connected:
            return

        logger.info(f"Disconnecting from MCP server: {self.config.id}")

        try:
            # Cancel reader task
            if self._reader_task and not self._reader_task.done():
                self._reader_task.cancel()
                try:
                    await self._reader_task
                except asyncio.CancelledError:
                    pass

            # Terminate process
            if self.process and self.process.returncode is None:
                self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Process did not terminate gracefully, killing: {self.config.id}")
                    self.process.kill()
                    await self.process.wait()

            # Cancel pending requests
            for future in self._pending_requests.values():
                if not future.done():
                    future.cancel()
            self._pending_requests.clear()

            self._connected = False
            logger.info(f"Disconnected from MCP server: {self.config.id}")

        except Exception as e:
            logger.error(f"Error during disconnect: {e}", exc_info=True)

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all available tools from MCP server

        Returns:
            List of tool schemas

        Raises:
            MCPClientError: If request fails
        """
        if not self._connected:
            raise MCPConnectionError("Not connected to MCP server")

        try:
            logger.debug(f"Listing tools from MCP server: {self.config.id}")
            result = await self._send_request(
                "tools/list",
                {},
                timeout_ms=self.config.timeout_ms
            )

            tools = result.get("tools", [])
            logger.info(f"Found {len(tools)} tools from MCP server: {self.config.id}")
            return tools

        except Exception as e:
            logger.error(f"Failed to list tools: {e}", exc_info=True)
            raise MCPClientError(f"Failed to list tools: {e}") from e

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call a tool on the MCP server

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool execution result

        Raises:
            MCPClientError: If call fails
        """
        if not self._connected:
            raise MCPConnectionError("Not connected to MCP server")

        try:
            logger.debug(f"Calling MCP tool: {tool_name} with args: {arguments}")
            result = await self._send_request(
                "tools/call",
                {
                    "name": tool_name,
                    "arguments": arguments
                },
                timeout_ms=self.config.timeout_ms
            )

            logger.info(f"MCP tool call successful: {tool_name}")
            return result

        except Exception as e:
            logger.error(f"Failed to call tool {tool_name}: {e}", exc_info=True)
            raise MCPClientError(f"Failed to call tool: {e}") from e

    def is_alive(self) -> bool:
        """
        Check if connection is alive

        Returns:
            True if connected and process is running
        """
        if not self._connected:
            return False

        if not self.process or self.process.returncode is not None:
            return False

        return True

    async def _send_request(
        self,
        method: str,
        params: Dict[str, Any],
        timeout_ms: int = 30000
    ) -> Dict[str, Any]:
        """
        Send JSON-RPC request and wait for response

        Args:
            method: JSON-RPC method name
            params: Method parameters
            timeout_ms: Timeout in milliseconds

        Returns:
            Response result

        Raises:
            MCPTimeoutError: If request times out
            MCPProtocolError: If protocol error occurs
        """
        if not self.process or not self.process.stdin:
            raise MCPConnectionError("Process not connected")

        # Generate request ID
        self._request_id += 1
        request_id = self._request_id

        # Create request
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }

        # Create future for response
        future: asyncio.Future = asyncio.Future()
        self._pending_requests[request_id] = future

        try:
            # Send request
            request_json = json.dumps(request) + "\n"
            self.process.stdin.write(request_json.encode("utf-8"))
            await self.process.stdin.drain()

            logger.debug(f"Sent request: {method} (id={request_id})")

            # Wait for response with timeout
            timeout_seconds = timeout_ms / 1000.0
            result = await asyncio.wait_for(future, timeout=timeout_seconds)

            return result

        except asyncio.TimeoutError:
            logger.error(f"Request timed out: {method} (id={request_id})")
            raise MCPTimeoutError(f"Request timed out after {timeout_ms}ms: {method}")

        finally:
            # Clean up pending request
            self._pending_requests.pop(request_id, None)

    async def _send_notification(self, method: str, params: Optional[Dict[str, Any]] = None):
        """
        Send JSON-RPC notification (no response expected)

        Args:
            method: JSON-RPC method name
            params: Method parameters
        """
        if not self.process or not self.process.stdin:
            raise MCPConnectionError("Process not connected")

        notification = {
            "jsonrpc": "2.0",
            "method": method
        }
        if params:
            notification["params"] = params

        notification_json = json.dumps(notification) + "\n"
        self.process.stdin.write(notification_json.encode("utf-8"))
        await self.process.stdin.drain()

        logger.debug(f"Sent notification: {method}")

    async def _read_loop(self):
        """
        Read loop for processing responses from server

        Runs in background task, reading lines from stdout and dispatching
        to pending request futures.
        """
        if not self.process or not self.process.stdout:
            logger.error("Cannot start read loop: process not initialized")
            return

        try:
            logger.debug(f"Starting read loop for MCP server: {self.config.id}")

            while True:
                # Read line from stdout
                line = await self.process.stdout.readline()
                if not line:
                    logger.warning(f"MCP server stdout closed: {self.config.id}")
                    break

                # Parse JSON response
                try:
                    line_str = line.decode("utf-8").strip()
                    if not line_str:
                        continue

                    response = json.loads(line_str)
                    logger.debug(f"Received response: {response.get('id', 'notification')}")

                    # Handle response
                    self._handle_response(response)

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    logger.debug(f"Invalid JSON: {line_str}")
                    continue

        except asyncio.CancelledError:
            logger.debug(f"Read loop cancelled for MCP server: {self.config.id}")
            raise

        except Exception as e:
            logger.error(f"Error in read loop: {e}", exc_info=True)

        finally:
            logger.debug(f"Read loop ended for MCP server: {self.config.id}")

    def _handle_response(self, response: Dict[str, Any]):
        """
        Handle JSON-RPC response

        Args:
            response: Parsed JSON-RPC response
        """
        # Check if this is a notification (no id)
        if "id" not in response:
            logger.debug(f"Received notification: {response.get('method', 'unknown')}")
            return

        request_id = response["id"]

        # Find pending request
        future = self._pending_requests.get(request_id)
        if not future:
            logger.warning(f"Received response for unknown request: {request_id}")
            return

        # Handle error response
        if "error" in response:
            error = response["error"]
            error_msg = f"MCP error {error.get('code')}: {error.get('message')}"
            logger.error(f"Request {request_id} failed: {error_msg}")
            future.set_exception(MCPProtocolError(error_msg))
            return

        # Handle success response
        if "result" in response:
            result = response["result"]
            future.set_result(result)
            return

        # Invalid response
        logger.error(f"Invalid response format: {response}")
        future.set_exception(MCPProtocolError("Invalid response format"))
