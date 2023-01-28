from aioquic.asyncio import serve, QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, ConnectionTerminated, StreamDataReceived
from aioquic.tls import SessionTicket as TLSSessionTicket

import asyncio
import structlog
from typing import Optional, Dict

from quictunnel_server.manager import SessionManager
from quictunnel_server.session import Session

logger = structlog.get_logger()


class QuicTunnelProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_manager = Optional[SessionManager]
        self.tunnel_sessions = Dict[int, Session]

    def register_manager(self, session_manager: SessionManager):
        """
        Called after initialization with a reference to the
        global SessionManager
        """
        self.session_manager = session_manager

    async def register_tunnel_host(self, http_host: str, session: Session):
        """
        Callback to pass to a Session to allow it to register a new tunnel
        by http_host once it receives the initialization from the client
        """
        await self.session_manager.register_session_host(http_host, session)

    def quic_event_received(self, event: QuicEvent) -> None:
        # This logic is copied from the default QuicConnectionProtocol
        # with adjustments in the stream-handling logic to connect
        # streams to our tunnel sessions

        if isinstance(event, ConnectionTerminated):
            for reader in self._stream_readers.values():
                reader.feed_eof()

            for _, session in self.tunnel_sessions.items():
                future = asyncio.ensure_future(
                    self.session_manager.remove_session(session)
                )
                # TODO - need to keep a reference to this future somewhere since
                # otherwise it may be garbage collected before the cleanup finishes

        elif isinstance(event, StreamDataReceived):
            reader = self._stream_readers.get(event.stream_id, None)
            # New stream!
            if reader is None:
                # create the reader/writer objects for the stream
                reader, writer = self._create_stream(event.stream_id)

                # create a new session for managing this stream
                session = Session(self.register_tunnel_host, reader, writer)
                self.tunnel_sessions[event.stream_id] = session

            # pass any data to the reader of the relevant stream
            reader.feed_data(event.data)
            if event.end_stream:
                reader.feed_eof()


class TLSTicketStore:
    """
    Simple in-memory store for TLS session tickets.

    Session tickets are provided to clients to allow them to
    reconnect without going through a full TLS handshake

    TODO: implement a max-size for this store and move to
    an out-of-process store to enable horizontal scaling
    """

    def __init__(self) -> None:
        self.tickets: Dict[bytes, TLSSessionTicket] = {}

    def add(self, ticket: TLSSessionTicket) -> None:
        self.tickets[ticket.ticket] = ticket

    def pop(self, label: bytes) -> Optional[TLSSessionTicket]:
        return self.tickets.pop(label, None)


async def run_tunnel_app(host: str, port: int, session_manager: SessionManager):
    session_ticket_store = TLSTicketStore()

    configuration = QuicConfiguration(
        is_client=False,
        max_datagram_frame_size=65536,
    )

    def create_protocol(*args, **kwargs):
        new_protocol = QuicTunnelProtocol(*args, **kwargs)
        new_protocol.register_manager(session_manager)
        return new_protocol

    await serve(
        host,
        port,
        configuration=configuration,
        create_protocol=create_protocol,
        session_ticket_fetcher=session_ticket_store.pop,
        session_ticket_handler=session_ticket_store.add,
        # Don't provide a stream_handler since we are already overriding
        # the event handling in QuicTunnelProtocol. This stream_handler
        # argument assumes the use of the default QuicConnectionProtocol
        stream_handler=None,
        retry=True,
    )
