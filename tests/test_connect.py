import pytest

from db.connect import is_local, with_tls

REMOTE = "postgresql://vl_reader.ref:pw@aws-0-eu-central-1.pooler.supabase.com:5432/postgres"


def test_remote_connections_require_tls():
    secured = with_tls(REMOTE)
    assert "sslmode=require" in secured
    assert "aws-0-eu-central-1.pooler.supabase.com" in secured


def test_an_explicit_sslmode_is_kept():
    url = REMOTE + "?sslmode=verify-full"
    assert with_tls(url) == url


def test_pgsslmode_from_the_environment_is_kept(monkeypatch):
    monkeypatch.setenv("PGSSLMODE", "verify-full")
    assert with_tls(REMOTE) == REMOTE


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://postgres:test@localhost:54329/postgres",
        "postgresql://postgres:test@127.0.0.1/postgres",
        "postgresql://postgres:test@[::1]:5432/postgres",
        "dbname=postgres",
    ],
)
def test_local_databases_are_left_alone(url, monkeypatch):
    monkeypatch.delenv("PGSSLMODE", raising=False)
    monkeypatch.delenv("PGHOST", raising=False)
    assert is_local(url)
    assert with_tls(url) == url


def test_remote_is_not_local():
    assert not is_local(REMOTE)
