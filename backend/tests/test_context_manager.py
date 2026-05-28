from brain.context_manager import ContextManager

def test_add_turn():
    ctx = ContextManager(max_turns=5)
    ctx.add_turn("user", "hello")
    assert len(ctx.get_context()) == 1
    assert ctx.get_context()[0] == {"role": "user", "content": "hello"}

def test_context_max_turns():
    ctx = ContextManager(max_turns=2)
    ctx.add_turn("user", "msg1")
    ctx.add_turn("user", "msg2")
    ctx.add_turn("user", "msg3")
    assert len(ctx.get_context()) == 2
    assert ctx.get_context()[0]["content"] == "msg2"
    assert ctx.get_context()[1]["content"] == "msg3"

def test_clear():
    ctx = ContextManager()
    ctx.add_turn("user", "hello")
    ctx.clear()
    assert ctx.get_context() == []

def test_set_language():
    ctx = ContextManager()
    assert ctx.current_language == "it"
    ctx.set_language("en")
    assert ctx.current_language == "en"