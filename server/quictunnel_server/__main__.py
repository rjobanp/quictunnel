import argparse
import asyncio

import uvicorn

from quictunnel_server.manager import SessionManager
from quictunnel_server.proxy_app import make_proxy_app
from quictunnel_server.tunnel_app import run_tunnel_app


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proxy-port", type=int, default=8400)
    parser.add_argument("--proxy-host", type=str, default="127.0.0.1")
    parser.add_argument("--tunnel-port", type=int, default=8401)
    parser.add_argument("--tunnel-host", type=str, default="127.0.0.1")
    args = parser.parse_args()

    session_manager = SessionManager()

    proxy_app_config = uvicorn.Config(
        app=make_proxy_app(session_manager),
        host=args.proxy_host,
        port=args.proxy_port,
    )
    proxy_server = uvicorn.Server(proxy_app_config)

    await asyncio.gather(
        proxy_server.serve(),
        run_tunnel_app(args.tunnel_host, args.tunnel_port, session_manager),
    )


if __name__ == "__main__":
    # TODO: Switch to uvloop for faster runtime?
    asyncio.run(main())
