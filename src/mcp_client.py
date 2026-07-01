import os
import sys
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MCPClient:
    """
    A context-managed client for communicating with the local MCP server over stdio.
    """
    def __init__(self, server_script="src.mcp_server"):
        self.server_script = server_script
        self.session = None
        self.stack = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    async def connect(self):
        self.stack = AsyncExitStack()
        
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", self.server_script],
            env=os.environ.copy()
        )
        
        stdio_transport = await self.stack.enter_async_context(stdio_client(server_params))
        stdio, write = stdio_transport
        self.session = await self.stack.enter_async_context(ClientSession(stdio, write))
        await self.session.initialize()

    async def disconnect(self):
        if self.stack:
            await self.stack.aclose()
            self.session = None

    async def call_tool(self, name: str, args: dict = None) -> str:
        if not self.session:
            raise RuntimeError("MCP Client is not connected. Call connect() first.")
        
        args = args or {}
        result = await self.session.call_tool(name, arguments=args)
        
        if result.content and len(result.content) > 0:
            return result.content[0].text
        return None
