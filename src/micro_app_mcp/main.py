"""MCP Server 入口"""

from micro_app_mcp.app.server import mcp


def main():
    """主函数入口"""
    mcp.run()


if __name__ == "__main__":
    main()
