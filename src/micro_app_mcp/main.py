"""MCP Server 入口"""

import argparse
import sys

from micro_app_mcp.app.server import mcp


def main():
    """主函数入口"""
    parser = argparse.ArgumentParser(description="Micro-App MCP Server")
    parser.add_argument(
        "--transport",
        type=str,
        default="stdio",
        choices=["stdio", "http", "sse", "streamable-http"],
        help="传输协议类型 (stdio/http/sse/streamable-http)",
    )
    parser.add_argument("--host", type=str, default="0.0.0.0", help="绑定的主机地址")
    parser.add_argument("--port", type=int, default=8080, help="绑定的端口号")

    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport=args.transport)
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
