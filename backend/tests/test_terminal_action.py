import pytest
from pathlib import Path
from actions.terminal_action import TerminalAction


@pytest.fixture
def action(tmp_path):
    config = {
        "terminal": {
            "enabled": True,
            "working_dir": str(tmp_path),
            "timeout": 5,
            "allowed_categories": ["info", "filesystem", "python"],
        }
    }
    return TerminalAction(config)


@pytest.mark.asyncio
async def test_python_c_blocked(action):
    """python -c con codice inline deve essere bloccato (blacklist + whitelist)."""
    blocked, reason = action._check_blacklist("python -c \"import os; os.system('echo pwned')\"")
    assert blocked, "python -c deve essere bloccato dalla blacklist"

    allowed, _ = action._check_whitelist("python -c \"import os; os.system('echo pwned')\"")
    assert not allowed, "python -c non deve passare la whitelist"


@pytest.mark.asyncio
async def test_python_version_allowed(action):
    """python --version deve essere eseguito."""
    result = await action.execute("python --version")
    assert "non ho capito" not in result.lower()
    assert "bloccato" not in result.lower()
    assert "Python" in result or "3." in result


@pytest.mark.asyncio
async def test_python_script_in_working_dir(action, tmp_path):
    """python script.py (nella working dir) deve essere eseguito."""
    script = tmp_path / "hello.py"
    script.write_text("print('Hello from test')")

    result = await action.execute(f"python {script.name}")
    assert "bloccato" not in result.lower()
    assert "Hello from test" in result


@pytest.mark.asyncio
async def test_python_absolute_path_blocked(action):
    """Path assoluto a .py fuori dalla working dir deve essere bloccato."""
    allowed, _ = action._check_whitelist("python /etc/passwd_stealer.py")
    assert not allowed, "Path assoluto .py deve essere bloccato dalla whitelist"


@pytest.mark.asyncio
async def test_python_m_http_server_blocked(action):
    """python -m http.server deve essere bloccato."""
    blocked, reason = action._check_blacklist("python -m http.server 8080")
    assert blocked, "python -m con modulo diverso da pytest deve essere bloccato dalla blacklist"

    allowed, _ = action._check_whitelist("python -m http.server 8080")
    assert not allowed, "python -m http.server non deve passare la whitelist"


@pytest.mark.asyncio
async def test_python_m_pytest_allowed(action, tmp_path):
    """python -m pytest deve essere eseguito (con path relativo senza ..)."""
    test_file = tmp_path / "test_sample.py"
    test_file.write_text("def test_pass(): assert True")

    result = await action.execute(f"python -m pytest {test_file.name} -q")
    assert "bloccato" not in result.lower()
    assert "passed" in result.lower() or "1 passed" in result


@pytest.mark.asyncio
async def test_python_script_with_dotdot_blocked(action):
    """python ../fuori.py (..) deve essere bloccato dalla whitelist."""
    allowed, _ = action._check_whitelist("python ../fuori.py")
    assert not allowed, "Path con .. deve essere bloccato"
