import datetime
import traceback

import structlog
from starlette import status
from starlette.requests import HTTPConnection, Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocket

from quictunnel_server.manager import Session, SessionManager

logger = structlog.get_logger()


class RequestError(BaseException):
    def __init__(self, code=status.HTTP_500_INTERNAL_SERVER_ERROR, message=""):
        self.code = code
        self.message = message


def find_session(manager: SessionManager, connection: HTTPConnection) -> Session:
    """
    Find the corresponding tunnel session based on the host header set in the specified
    HTTP connection

    Raises a 400 error if no session is found
    """
    print(f"Handling connection from {connection.client.host}:{connection.client.port}")
    host_header = connection.headers["host"]

    # Setup logging to be 'context-local' which should persist through this request's
    # handling
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        host=host_header,
        client_host=connection.client.host,
        client_port=connection.client.port,
        start_time=datetime.datetime.utcnow().isoformat(),
    )

    # find host in session map
    session = manager.session_by_host(host_header)
    if not session:
        # if no host found, return error to client
        raise RequestError(
            code=status.HTTP_400_BAD_REQUEST,
            message="Session for specified host not found",
        )
    return session


async def http_handler(manager: SessionManager, request: Request):
    try:
        session = find_session(manager, request)
        return await session.proxy_request(request)
    except RequestError as err:
        logger.error(
            "Returning error response",
            code=err.code,
            content=err.message,
            client_addr=request.client,
            method=request.method,
            url=request.url,
            conn_type="http",
        )
        return Response(
            content=err.message,
            status_code=err.code,
            headers={"Content-Type": "text/plain"},
        )
    except BaseException:
        logger.error(
            "Returning unhandled error response",
            trace=traceback.format_exc(),
            client_addr=request.client,
            method=request.method,
            url=request.url,
            conn_type="http",
        )
        return Response(
            content="Server error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            headers={"Content-Type": "text/plain"},
        )


async def websocket_handler(manager: SessionManager, websocket: WebSocket) -> None:
    await websocket.accept()

    try:
        session = find_session(manager, websocket)
        await session.proxy_websocket(websocket)
        await websocket.close()
    except RequestError as err:
        logger.error(
            "Closing websocket due to error",
            code=err.code,
            content=err.message,
            client_addr=websocket.client,
            url=websocket.url,
            conn_type="websocket",
        )
        await websocket.close(code=err.code, reason=err.message)
    except BaseException:
        logger.error(
            "Closing websocket due to unhandled error",
            trace=traceback.format_exc(),
            client_addr=websocket.client,
            url=websocket.url,
            conn_type="websocket",
        )
        await websocket.close(code=status.HTTP_500_INTERNAL_SERVER_ERROR)


def make_proxy_app(manager: SessionManager) -> ASGIApp:
    """
    Return an ASGI app function to handle HTTP & Websocket requests
    and forward them to the corresponding tunnel session
    """

    async def proxy_app(scope: Scope, receive: Receive, send: Send):
        """
        ASGI interface using Starlette as a toolkit
        """
        # TODO: implement the lifespan handler
        if scope["type"] == "lifespan":
            return None

        if scope["type"] == "http":
            http_response = await http_handler(
                manager, Request(scope, receive=receive, send=send)
            )
            return await http_response(scope, receive, send)

        elif scope["type"] == "websocket":
            return await websocket_handler(
                manager, WebSocket(scope, receive=receive, send=send)
            )

        else:
            raise Exception(f"Unsupported protocol {scope['type']}")

    return proxy_app
