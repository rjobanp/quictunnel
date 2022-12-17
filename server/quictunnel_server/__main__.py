import argparse
import asyncio

import uvicorn

from quictunnel_server.manager import SessionManager
from quictunnel_server.proxy_app import make_proxy_app


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proxy-port", type=int, default=8400)
    parser.add_argument("--proxy-host", type=str, default="127.0.0.1")
    args = parser.parse_args()

    session_context = SessionManager()

    # https://pgjones.gitlab.io/hypercorn/how_to_guides/configuring.html
    proxy_app_config = uvicorn.Config(
        app=make_proxy_app(session_context),
        host=args.proxy_host,
        port=args.proxy_port,
    )
    proxy_server = uvicorn.Server(proxy_app_config)

    await asyncio.gather(
        proxy_server.serve()
        #
    )


if __name__ == "__main__":
    # TODO: Switch to uvloop for faster runtime?
    asyncio.run(main())
