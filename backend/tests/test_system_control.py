import time
import pytest
from actions.system_control import SystemControl


@pytest.fixture
def action():
    return SystemControl({"system": {"host": "127.0.0.1", "port": 8765}})


@pytest.mark.asyncio
async def test_safe_command_passes_through(action):
    result = await action.execute("alza volume")
    assert "Volume alzato" in result


@pytest.mark.asyncio
async def test_destructive_triggers_confirm(action):
    result = await action.execute("shutdown")
    assert "Conferma" in result
    assert action._pending is not None
    assert action._pending["action"] == "shutdown"


@pytest.mark.asyncio
async def test_confirm_executes_destructive(action):
    await action.execute("shutdown")
    assert action._pending is not None
    result = await action.execute("sì")
    assert action._pending is None
    assert ("Procedo" in result or "non disponibile" in result)


@pytest.mark.asyncio
async def test_deny_cancels(action):
    await action.execute("riavvia")
    assert action._pending is not None
    result = await action.execute("no")
    assert "annullata" in result.lower()
    assert action._pending is None


@pytest.mark.asyncio
async def test_confirm_words_variants(action):
    for word in ["sì", "confermo", "procedi", "ok", "conferma", "yes"]:
        a = SystemControl({"system": {"host": "127.0.0.1", "port": 8765}})
        await a.execute("shutdown")
        r = await a.execute(word)
        assert a._pending is None, f"Parola '{word}' non riconosciuta come conferma: {r}"
        assert ("Procedo" in r or "non disponibile" in r), f"Parola '{word}' fallita: {r}"


@pytest.mark.asyncio
async def test_deny_words_variants(action):
    for word in ["no", "annulla", "cancel", "non"]:
        a = SystemControl({"system": {"host": "127.0.0.1", "port": 8765}})
        await a.execute("shutdown")
        r = await a.execute(word)
        assert "annullata" in r.lower(), f"Parola '{word}' non riconosciuta come rifiuto"


@pytest.mark.asyncio
async def test_timeout_expires_pending(action):
    await action.execute("shutdown")
    action._pending["timestamp"] = time.time() - 31
    result = await action.execute("sì")
    assert "annullata" not in result.lower()
    assert action._pending is None


@pytest.mark.asyncio
async def test_restart_also_triggers_confirm(action):
    result = await action.execute("riavvia")
    assert "Conferma" in result
    assert action._pending["action"] == "restart"
    r = await action.execute("conferma")
    assert action._pending is None
    assert ("Procedo" in r or "non disponibile" in r)


@pytest.mark.asyncio
async def test_negation_triggers_confirm_not_execution(action):
    result = await action.execute("non voglio spegnere il pc")
    assert action._pending is not None
    assert "Conferma" in result
    # Confermare che non esegue subito: deve chiedere conferma
    r2 = await action.execute("no")
    assert "annullata" in r2.lower()


# ── Regression: falsi positivi da substring matching ─────────────────────────

@pytest.mark.asyncio
async def test_denial_with_si_substring_not_confirmed():
    """'si' in 'sicuramente' NON deve essere riconosciuto come conferma."""
    a = SystemControl({"system": {"host": "127.0.0.1", "port": 8765}})
    await a.execute("shutdown")
    assert a._pending is not None
    r = await a.execute("sicuramente no, non spegnere")
    assert "annullata" in r.lower(), f"FALSO POSITIVO: 'si' dentro 'sicuramente' ha confermato! Risultato: {r}"
    assert a._pending is None


@pytest.mark.asyncio
async def test_denial_with_si_substring_variant():
    """Frasi con 'si'/'no' come substring di altre parole non devono causare falsi."""
    a = SystemControl({"system": {"host": "127.0.0.1", "port": 8765}})
    await a.execute("shutdown")
    assert a._pending is not None
    r = await a.execute("non saprei se è il caso")
    # 'non' matcha come parola intera → annullamento
    assert "annullata" in r.lower(), f"Frase di diniego non riconosciuta: {r}"
    assert a._pending is None


@pytest.mark.asyncio
async def test_deny_precedence_over_confirm():
    """Se frase contiene sia parole di conferma che di diniego, prevale il diniego."""
    a = SystemControl({"system": {"host": "127.0.0.1", "port": 8765}})
    await a.execute("shutdown")
    assert a._pending is not None
    r = await a.execute("sì ma non ora")
    # 'non' (deny) controllato prima di 'sì' (confirm) → annullamento
    assert "annullata" in r.lower(), f"Prevale la conferma! Risultato: {r}"
    assert a._pending is None
