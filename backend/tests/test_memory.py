from memory.ephemeral import EphemeralMemory

def test_ephemeral_set_get():
    mem = EphemeralMemory()
    mem.set("key1", "value1")
    assert mem.get("key1") == "value1"

def test_ephemeral_get_missing():
    mem = EphemeralMemory()
    assert mem.get("nonexistent") is None

def test_ephemeral_delete():
    mem = EphemeralMemory()
    mem.set("key1", "value1")
    mem.delete("key1")
    assert mem.get("key1") is None

def test_ephemeral_clear():
    mem = EphemeralMemory()
    mem.set("key1", "value1")
    mem.set("key2", "value2")
    mem.clear()
    assert mem.get("key1") is None
    assert mem.get("key2") is None