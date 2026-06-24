import logging
import json
from typing import Optional
from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from app.core.config import settings

logger = logging.getLogger(__name__)

class KaprukaMCPClient:
    def __init__(self):
        # THE FIX: We append /sse to the base URL to hit the dedicated stream endpoint

        
        self._session: Optional[ClientSession] = None
        self._exit_stack = AsyncExitStack()
        self.url = settings.kapruka_mcp_url
        logger.info(f"Connecting to Kapruka MCP SSE stream at {self.url}...")

    async def _ensure_session(self) -> ClientSession:
        """Maintains a persistent connection to the Kapruka server."""
        if self._session:
            return self._session

        logger.info(f"Connecting to Kapruka MCP SSE stream at {self.url}...")
        
        try:
            # The official SDK handles the GET stream, parses the unique POST endpoint, 
            # and automatically injects the Session ID into every request.
            streams = await self._exit_stack.enter_async_context(streamablehttp_client(self.url))
            session = await self._exit_stack.enter_async_context(ClientSession(streams[0], streams[1]))
            await session.initialize()
            
            self._session = session
            logger.info("MCP Session established successfully.")
            return self._session
            
        except Exception as e:
            logger.error(f"Failed to establish MCP session: {e}")
            await self._exit_stack.aclose()
            raise

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Executes a tool call and formats the response back into a clean dictionary."""
        session = await self._ensure_session()
        
        try:
            # The SDK executes the call and handles rate-limit retries natively
            result = await session.call_tool(tool_name, arguments)
            
            # The official SDK returns a CallToolResult object containing text blocks.
            # We parse the text block back into the raw dictionary your frontend expects.
            if result.content and len(result.content) > 0:
                text_response = result.content[0].text
                try:
                    return json.loads(text_response)
                except json.JSONDecodeError:
                    return {"result": text_response}
            return {}
            
        except Exception as e:
            logger.error(f"Error executing {tool_name}: {e}")
            # If the server drops the connection, wipe our state to force a fresh handshake next time
            self._session = None
            await self._exit_stack.aclose()
            raise Exception(f"MCP Tool Error ({tool_name}): {str(e)}") from e

async def close(self):
        """Gracefully shuts down the connection when the application exits."""
        if not self._session:
            return
            
        logger.info("Closing Kapruka MCP client connection...")
        self._session = None
        
        try:
            # Clear out the exit stack context managers
            await self._exit_stack.aclose()
        except (RuntimeError, Exception) as e:
            # Catches Python 3.14 task group/generator teardown artifacts safely
            logger.debug(f"Muted SDK cleanup exception during exit: {e}")

# Singleton pattern to ensure we don't open 50 separate connections to Kapruka
_client_instance: Optional[KaprukaMCPClient] = None

async def get_client() -> KaprukaMCPClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = KaprukaMCPClient()
    return _client_instance

async def close_client():
    global _client_instance
    if _client_instance is not None:
        await _client_instance.close()
        _client_instance = None