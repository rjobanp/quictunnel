import asyncio
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


async def test_host_lookup(session_manager: SessionManager, host: str):
    assert session_manager.session_by_host("test") is None

    new_session = await session_manager.new_session(host)
    assert new_session == session_manager.session_by_host(host)
    # validate that casing does not matter
    assert new_session == session_manager.session_by_host(host.capitalize())


async def test_concurrent_host_add(session_manager: SessionManager, host: str):
    results = await asyncio.gather(
        *[session_manager.new_session(host) for _ in range(5)]
    )
    session = session_manager.session_by_host(host)
    assert len(session_manager._sessions.keys()) == 1
    assert all(result is session for result in results)


async def test_session_remove(session_manager: SessionManager, host: str):
    session = await session_manager.new_session(host)
    await session_manager.remove_session(session)
    assert session.closed


async def test_session_remove_non_mapped(session_manager: SessionManager, host: str):
    session = Session(host=host)
    await session_manager.remove_session(session)
    assert session.closed
