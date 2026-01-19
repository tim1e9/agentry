"""
MCP Client for communicating with MCP server over HTTP transport.
"""
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client
from typing import Dict, List, Any
import asyncio
import logging


logger = logging.getLogger(__name__)


class MCPClient:
    """Client for MCP over HTTP protocol."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = None
        self.tools = []
        self.session_id = None
        
    async def _initialize_async(self):
        """Initialize the MCP session asynchronously."""
        async with streamable_http_client(self.base_url) as (read, write, get_session_id):
            async with ClientSession(read, write) as session:
                init_result = await session.initialize()
                logger.debug("MCP initialize result: %s", init_result)
                
                # List available tools
                tools_result = await session.list_tools()
                logger.debug("MCP tools result: %s", tools_result)
                logger.info("MCP tools discovered: %d", len(tools_result.tools))
                self.tools = tools_result.tools
                
                return session
    
    def initialize(self) -> Dict[str, Any]:
        """Initialize connection with MCP server (sync wrapper)."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._initialize_async())
            logger.info("MCP client initialized; cached tools=%d", len(self.tools))
            return {"status": "initialized", "tools": len(self.tools)}
        except Exception as e:
            logger.exception("Error initializing MCP client")
            return {}
        finally:
            loop.close()
    
    async def _list_tools_async(self, access_token: str = None) -> List[Dict[str, Any]]:
        """List tools asynchronously with optional authentication."""
        headers = {}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        async with create_mcp_http_client(headers=headers) as http_client:
            async with streamable_http_client(self.base_url, http_client=http_client) as (read, write, get_session_id):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_result = await session.list_tools()
                    return [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema
                        }
                        for tool in tools_result.tools
                    ]
    
    def list_tools(self, access_token: str = None) -> List[Dict[str, Any]]:
        """Get list of available tools from MCP server, optionally user-specific if access_token is provided."""
        if access_token:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(self._list_tools_async(access_token))
                return result
            except Exception as e:
                logger.exception("Error fetching user-specific tools")
                return []
            finally:
                loop.close()
        else:
            logger.debug("list_tools (cached) called; cached tools=%d", len(self.tools))
            return [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema
                }
                for tool in self.tools
            ]
    
    async def _call_tool_async(self, tool_name: str, arguments: Dict[str, Any], access_token: str = None) -> Dict[str, Any]:
        """Call a tool asynchronously, optionally forwarding an access token as Authorization header."""
        headers = {}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        async with create_mcp_http_client(headers=headers) as http_client:
            async with streamable_http_client(self.base_url, http_client=http_client) as (read, write, get_session_id):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    return {"content": [{"type": "text", "text": str(content.text)} for content in result.content]}

    def call_tool(self, tool_name: str, arguments: Dict[str, Any], access_token: str = None) -> Dict[str, Any]:
        """Call a tool on the MCP server (sync wrapper), optionally forwarding an access token."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._call_tool_async(tool_name, arguments, access_token))
            return result
        except Exception as e:
            logger.exception("Error calling tool %s", tool_name)
            return {"error": str(e)}
        finally:
            loop.close()

