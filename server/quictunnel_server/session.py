import datetime

from starlette.requests import Request
from starlette.responses import Response
from starlette.websockets import WebSocket


class Session:
    def __init__(self, host: str) -> None:
        self.host = host
        self.started = datetime.datetime.now()
        self.closed = False

    async def close(self) -> None:
        self.closed = True

    async def proxy_request(self, request: Request) -> Response:
        return Response()

    async def proxy_websocket(self, websocket: WebSocket) -> None:
        pass
