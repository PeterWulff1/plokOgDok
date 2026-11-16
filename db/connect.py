"""Connection strings: every database that isn't on this machine must be reached over TLS.

psycopg's default (`sslmode=prefer`) falls back to an unencrypted connection when the server
or someone in between says TLS isn't available. `require` refuses instead. A URL that sets
`sslmode` itself (for example `verify-full`) is left alone.
"""

import os

from psycopg.conninfo import conninfo_to_dict, make_conninfo

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def is_local(url: str) -> bool:
    """True when the connection string points at this machine (or a Unix socket)."""
    host = conninfo_to_dict(url).get("host") or ""
    return not host or host.startswith("/") or host in LOCAL_HOSTS


def with_tls(url: str) -> str:
    """The connection string with `sslmode=require`, unless it is local or already sets one."""
    if is_local(url) or "sslmode" in conninfo_to_dict(url) or os.environ.get("PGSSLMODE"):
        return url
    return make_conninfo(url, sslmode="require")
