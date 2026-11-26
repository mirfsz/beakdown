from mcp.server.fastmcp import FastMCP

from .tools import (
    create_handoff_session,
    create_investigation_session,
    get_session_result,
    refresh_build_evidence,
)

server = FastMCP("Beakdown")
server.tool()(create_handoff_session)
server.tool()(get_session_result)
server.tool()(create_investigation_session)
server.tool()(refresh_build_evidence)


def main():
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
