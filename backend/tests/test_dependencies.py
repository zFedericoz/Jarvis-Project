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