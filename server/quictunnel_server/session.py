import datetime

import asyncio

from starlette.requests import Request
from starlette.responses import Response
from starlette.websockets import WebSocket

from typing import Callable, Any


class Session:
    def __init__(
        self,
        register_tunnel_host: Callable[[str, Any]],
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        self.register_tunnel_host = register_tunnel_host
        self.reader = reader
        self.writer = writer
        self.started = datetime.datetime.now()
        self.closed = False

        self._serve_future = asyncio.ensure_future(self.serve())

    async def serve(self):
        """
        Handle the quic stream behind this session
        """
        async for data in self.reader:
            # handle stream data here

            # TODO: Wait for the client to provide a message containing
            # a tunnel host name, validate the tunnel host and the
            # auth data, then call self.register_tunnel_host to register
            # ourselves on the global session manager
            pass
        else:
            # stream closed if reader is closed
            await self.close()

    async def close(self) -> None:
        if self.closed:
            # already closed
            return
        self.closed = True

    async def proxy_request(self, request: Request) -> Response:
        return Response()

    async def proxy_websocket(self, websocket: WebSocket) -> None:
        pass
