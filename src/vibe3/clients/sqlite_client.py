"""SQLite client facade composed from focused repository mixins."""

from vibe3.clients.sqlite_base import SQLiteClientBase
from vibe3.clients.sqlite_context_cache_repo import SQLiteContextCacheRepo
from vibe3.clients.sqlite_event_repo import SQLiteEventRepo
from vibe3.clients.sqlite_flow_state_repo import SQLiteFlowStateRepo
from vibe3.clients.sqlite_session_repo import SQLiteSessionRepo


class SQLiteClient(
    SQLiteClientBase,
    SQLiteFlowStateRepo,
    SQLiteEventRepo,
    SQLiteContextCacheRepo,
    SQLiteSessionRepo,
):
    """Facade preserving the existing SQLiteClient API over focused repos."""

    pass
