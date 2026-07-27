from mcp.server.fastmcp import Context, FastMCP

mcp = FastMCP("probe-server")


@mcp.tool()
def whoami(ctx: Context) -> str:
    cp = ctx.session.client_params
    if cp is None:
        return "client_params=None"
    return f"client_params={cp.clientInfo.name}/{cp.clientInfo.version}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
