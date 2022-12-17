from asyncio import Lock
from typing import Optional

from structlog import get_logger

from quictunnel_server.session import Session

logger = get_logger()


def sanitize_host(host: str):
    return host.strip().lower()


class SessionManager:
    """
    Manage all tunnel sessions for this app

    Each session is keyed by its "host" which indicates the host-header
    that incoming requests will be matched against
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._session_lock = Lock()

    def session_by_host(self, host: str) -> Optional[Session]:
        """
        Retrieve a session by its designated host header lookup key
        """
        # TODO(roshan): Do we need to use the session_lock here?
        return self._sessions.get(sanitize_host(host))

    async def new_session(self, host: str) -> Session:
        """
        Create and return a new session for the given host if one does
        not already exist. Returns existing if found.
        """
        host = sanitize_host(host)
        async with self._session_lock:
            if host not in self._sessions:
                self._sessions[host] = Session(host=host)
            return self.session_by_host(host)

    async def remove_session(self, session: Session) -> None:
        """
        Clean up and remove a session from the map
        """
        async with self._session_lock:
            if session.host in self._sessions:
                popped_session = self._sessions.pop(session.host)
                if session is not popped_session:
                    logger.error(
                        "Asked to clean up session that doesn't match session"
                        " for same host in session map",
                        host=session.host,
                    )
            else:
                logger.warning(
                    "Asked to cleanup session for host not in session map",
                    host=session.host,
                )

        await session.close()
