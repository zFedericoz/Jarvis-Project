from brain.intent_router import IntentRouter

def test_greeting_it():
    router = IntentRouter()
    assert router.route("Ciao Jarvis") == "greeting"

def test_greeting_en():
    router = IntentRouter()
    assert router.route("Hello") == "greeting"

def test_web_search_it():
    router = IntentRouter()
    assert router.route("Cerca il meteo di oggi") == "web_search"

def test_web_search_en():
    router = IntentRouter()
    assert router.route("who is Elon Musk") == "web_search"

def test_system_control():
    router = IntentRouter()
    assert router.route("Spegni il computer") == "system_control"
    assert router.route("shutdown now") == "system_control"

def test_media_player():
    router = IntentRouter()
    assert router.route("Metti musica") == "media_player"
    assert router.route("play some music") == "media_player"

def test_productivity():
    router = IntentRouter()
    assert router.route("Imposta un timer di 5 minuti") == "productivity"
    assert router.route("set a timer") == "productivity"

def test_vision():
    router = IntentRouter()
    assert router.route("Guarda cosa c'è qui") in ("vision", "chat", "web_search")
    assert router.route("what do you see") in ("vision", "chat", "web_search")

def test_fallback_to_chat():
    router = IntentRouter()
    assert router.route("Qual è il senso della vita?") == "chat"
