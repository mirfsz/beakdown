from mcp.server.fastmcp import FastMCP
from .tools import create_handoff_session, get_session_result

server = FastMCP("Beakdown")
server.tool()(create_handoff_session)
server.tool()(get_session_result)


def main():
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
