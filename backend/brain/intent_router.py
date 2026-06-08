import re
import logging

logger = logging.getLogger("jarvis.brain.intent")

INTENTS = [
    ("greeting", [
        r"\bciao\b", r"\bhey\b", r"\bsalve\b", r"\bhello\b", r"\bhi\b",
        r"\bbuongiorno\b", r"\bbuonasera\b", r"\bgood morning\b",
    ]),

    # ── Step 4: Git ────────────────────────────────────────────────────────────
    ("git", [
        r"\b(commit|committa|fai il commit)\b",
        r"\b(git status|stato git|modifiche git)\b",
        r"\b(git log|ultimi commit|storia del repo|log git)\b",
        r"\b(git push|fai il push|push sul remote)\b",
        r"\b(git pull|aggiorna dal remote|pull)\b",
        r"\b(crea branch|nuovo branch|checkout branch)\b",
        r"\b(git stash|salva temporaneamente)\b",
        r"\b(git diff|differenze git|cosa ho cambiato)\b",
    ]),

    # ── Step 5: Terminale sicuro ───────────────────────────────────────────────
    ("terminal", [
        r"\b(esegui|lancia|eseguire|run|execute|fai girare)\s+\w",
        r"\b(versione di python|versione di pip)\b",
        r"\b(processi attivi|lista processi|ps aux|tasklist)\b",
        r"\b(uso del disco|spazio su disco)\b",
        r"\b(uso della ram|quanta ram|memoria libera)\b",
        r"\b(indirizzo ip|ipconfig|ifconfig)\b",
        r"\b(container docker|docker ps|immagini docker)\b",
        r"\b(variabili d.ambiente|env)\b",
        r"\b(uptime|da quanto[  ]è acceso)\b",
        r"\binstalla (la )?dip[en]+denza\b",
        r"\bpip install\b",
    ]),

    # ── Step 6: Focus / Productivity ──────────────────────────────────────────
    ("productivity", [
        r"\b(attiva|inizia|avvia|start)\s+(la\s+)?modalità\s+focus\b",
        r"\b(inizia|avvia|start|fai)\s+(un\s+)?pomodoro\b",
        r"\bpomodoro\s+(da\s+)?\d+\b",
        r"\b(pausa|metti in pausa)\s+(il\s+)?(focus|pomodoro)\b",
        r"\b(riprendi|continua)\s+(il\s+)?(focus|pomodoro)\b",
        r"\b(disattiva|ferma|stop|termina)\s+(la\s+)?(modalità\s+)?focus\b",
        r"\bquanto\s+(manca|resta|rimane)\b",
        r"\b(stato|status)\s+(del\s+)?(focus|pomodoro)\b",
        r"\b(aggiungi|rimuovi).+(blacklist\s+focus)\b",
        r"\btimer\b", r"\bpromemoria\b", r"\bricorda\b",
    ]),

    # ── Step 7: RPA / UI Automation ───────────────────────────────────────────
    # Nota: "apri" + app ha priorità su system_control
    ("rpa", [
        r"\b(screenshot|schermata|cattura\s+(lo\s+)?schermo)\b",
        r"\b(analizza|cosa c.è|descrivi)\s+(lo\s+)?schermo\b",
        r"\bcosa\s+(vedi|c.è)\s+(sullo|nello)\s+schermo\b",
        r"\bclicca\s+(su|il|la|lo)\b",
        r"\bdoppio\s+click\b",
        r"\bclick\s+destro\b",
        r"\b(scrivi|digita|inserisci)\s+.+nel\b",
        r"\bpremi\s+(ctrl|alt|shift|win|f\d+)\b",
        r"\b(ctrl|alt|shift)\s*\+\s*\w",
        r"\b(apri|avvia|lancia)\s+(chrome|firefox|edge|vscode|vs code|notepad|terminale|discord|spotify)\b",
        r"\b(apri|apri il file)\s+.+\.(py|js|ts|txt|md|json|pdf|docx|xlsx)\b",
        r"\b(scorri|scrolla)\s*(in\s+)?(su|giù|alto|basso)\b",
        r"\btrascina\s+da\b",
        r"\bdrag\b",
        r"\brisoluzione\s+(dello\s+)?schermo\b",
    ]),

    ("system_control", [
        r"\b(volume|spegn[i]|riavvia|blocca\s+lo\s+schermo|wifi|bluetooth)\b",
        r"\b(shutdown|restart|lock screen)\b",
    ]),
    ("media_player", [
        r"\b(musica|canzone|play|pausa|stop|skippa|riproduci|spotify)\b",
        r"\b(music|song|play|pause|stop|skip)\b",
    ]),
    ("vision", [
        r"\b(guarda con la webcam|usa la camera|riconosce con yolo)\b",
    ]),
    ("web_search", [
        r"\bcerca\b", r"\bsearch\b", r"\btrova online\b",
        r"\b(chi|che cos|dove|quando|come|perché)\s",
        r"\b(who|what|where|when|why|how)\s",
    ]),
]


class IntentRouter:
    def route(self, text: str) -> str:
        text_lower = text.lower()
        for intent, patterns in INTENTS:
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    logger.debug(f"Routing '{text[:60]}' → {intent}")
                    return intent
        logger.debug(f"Routing '{text[:60]}' → chat")
        return "chat"
