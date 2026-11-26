import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_registered_investigation_tool():
    async def check():
        async with stdio_client(
            StdioServerParameters(command="uv", args=["run", "beakdown-mcp"])
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                assert {t.name for t in result.tools} == {
                    "create_handoff_session",
                    "create_investigation_session",
                    "refresh_build_evidence",
                    "get_session_result",
                }
                tool = next(
                    t for t in result.tools if t.name == "create_investigation_session"
                )
                assert {"title", "target", "screens"}.issubset(
                    tool.inputSchema["required"]
                )

    asyncio.run(check())
