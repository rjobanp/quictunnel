import asyncio
import datetime
import json
from typing import Any, Callable, Optional

import structlog
from starlette.requests import Request
from starlette.responses import Response
from starlette.websockets import WebSocket

logger = structlog.get_logger()


class Session:
    def __init__(
        self,
        register_tunnel_host: Callable[[str, Any], None],
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        self.register_tunnel_host = register_tunnel_host
        self.reader = reader
        self.writer = writer
        self.started = datetime.datetime.now()
        self.closed = False
        self.host: Optional[str] = None

        self._serve_future = asyncio.ensure_future(self.serve())

    async def serve(self):
        """
        Handle the quic stream behind this session
        """
        while True:
            data = await self.reader.readline()
            if self.closed:
                return
            if not data:
                await self.close()

            # handle stream data here
            try:
                await self.handle_data(data)
            except BaseException:
                logger.exception("Error handling data, closing session")
                await self.close()

    async def close(self) -> None:
        if self.closed:
            # already closed
            return
        self.closed = True
        self.reader.feed_eof()
        if self.writer.can_write_eof():
            self.writer.write_eof()
        self.writer.close()

    async def handle_data(self, data: bytes) -> None:
        # TODO: Clean this up and implement more robust message handling
        # Also consider using protobuf or msgpack over JSON
        try:
            message = json.loads(data)
            logger.debug("Got message", message=message)
        except ValueError:
            logger.exception("Unable to decode json from stream data")

        if message.get("type") == "host_request":
            # TODO: validate auth
            # Register ourselves as the session for handling the requested
            # host
            self.host = message["host"]
            await self.register_tunnel_host(self.host, self)

    async def proxy_request(self, request: Request) -> Response:
        return Response()

    async def proxy_websocket(self, websocket: WebSocket) -> None:
        pass
