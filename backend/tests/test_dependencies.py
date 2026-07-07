import pytest
from api.dependencies import resolve_env

def test_resolve_env_no_var():
    assert resolve_env("hello") == "hello"

def test_resolve_env_with_default():
    result = resolve_env("${VAR:-default}")
    assert result == "default"

def test_resolve_env_with_env_var(monkeypatch):
    monkeypatch.setenv("MY_VAR", "custom")
    result = resolve_env("${MY_VAR:-default}")
    assert result == "custom"

def test_resolve_env_dict():
    result = resolve_env({"key": "${VAR:-val}"})
    assert result == {"key": "val"}

def test_resolve_env_list():
    result = resolve_env(["${VAR:-a}", "${VAR:-b}"])
    assert result == ["a", "b"]

def test_resolve_env_nested():
    result = resolve_env({"outer": {"inner": "${VAR:-deep}"}})
    assert result == {"outer": {"inner": "deep"}}

def test_resolve_env_number():
    assert resolve_env(42) == 42


def test_multi_tenant_isolation():
    """Due ChatManager con user_id diversi NON possono leggere le sessioni altrui.

    ChatManager usa ChatDBConnection singleton (data/chats.db), quindi entrambi
    condividono lo stesso database — testiamo l'isolamento a livello logico.
    """
    from chat.chat_manager import ChatManager

    # User A crea una sessione
    mgr_a = ChatManager(user_id="isolation_test_user_a")
    session = mgr_a.create_session()
    sid = session["id"]

    try:
        # User B NON può accedere alla sessione di A
        mgr_b = ChatManager(user_id="isolation_test_user_b")
        assert mgr_b.get_session(sid) is None
        assert mgr_b.list_sessions() == []
        assert mgr_b.get_messages(sid) == []
        assert mgr_b.rename_session(sid, "hacked") is False
        assert mgr_b.delete_session(sid) is False
        with pytest.raises(ValueError, match="not owned"):
            mgr_b.add_message(sid, "user", "malicious")

        # User A può ancora accedervi
        assert mgr_a.get_session(sid) is not None
        assert mgr_a.rename_session(sid, "new title") is True
        msg = mgr_a.add_message(sid, "user", "hello")
        assert msg is not None

        # User B NON può vedere i messaggi di A
        assert mgr_b.get_messages(sid) == []
        assert mgr_b.get_session(sid) is None

    finally:
        # Cleanup: elimina sessione di test
        mgr_a.delete_session(sid)