import asyncio
import json
import random

import pytest

from quictunnel_server.manager import SessionManager
from quictunnel_server.session import Session


@pytest.fixture
def session_manager() -> SessionManager:
    return SessionManager()


@pytest.fixture
def host() -> str:
    return "test_tunnel_" + str(random.randint(0, 1000))


class WriteTransportMock(asyncio.WriteTransport):
    def write_eof(self) -> None:
        return

    def can_write_eof(self) -> bool:
        return True

    def close(self) -> None:
        return


def get_test_session(manager: SessionManager) -> Session:
    """
    Returns a new Session instance
    """
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader(loop=loop)
    return Session(
        manager.register_session_host,
        reader,
        asyncio.StreamWriter(
            WriteTransportMock(),
            asyncio.BaseProtocol(),
            reader=reader,
            loop=loop,
        ),
    )


def send_host_client_request_to_session(host: str, session: Session) -> None:
    """
    Send a client request to the session containing the requested tunnel host
    """
    session.reader.feed_data(
        json.dumps({"type": "host_request", "host": host}).encode() + b"\n"
    )


async def test_host_lookup(session_manager: SessionManager, host: str):
    assert await session_manager.session_by_host(host) is None

    new_session = get_test_session(session_manager)
    send_host_client_request_to_session(host, new_session)
    await asyncio.sleep(0.1)
    assert new_session == await session_manager.session_by_host(host)
    # validate that casing does not matter
    assert new_session == await session_manager.session_by_host(host.capitalize())
    await new_session.close()


async def test_concurrent_host_add(session_manager: SessionManager, host: str):
    sessions = [get_test_session(session_manager) for _ in range(5)]
    # 5 sessions request the same host but only one of them should get it
    for session in sessions:
        send_host_client_request_to_session(host, session)

    await asyncio.sleep(0.1)
    assert len(session_manager._sessions.keys()) == 1
    winning_session = await session_manager.session_by_host(host)
    assert len([session for session in sessions if session == winning_session]) == 1
    asyncio.gather(*(session.close() for session in sessions))


async def test_session_remove(session_manager: SessionManager, host: str):
    new_session = get_test_session(session_manager)
    send_host_client_request_to_session(host, new_session)
    await session_manager.remove_session(new_session)
    assert new_session.closed


async def test_session_remove_non_mapped(session_manager: SessionManager, host: str):
    new_session = get_test_session(session_manager)
    await session_manager.remove_session(new_session)
    assert new_session.closed
