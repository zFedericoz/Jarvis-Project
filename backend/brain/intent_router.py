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
        r"\b(git stash|stash|salva temporaneamente)\b",
        r"\b(git diff|differenze git|cosa ho cambiato)\b",
    ]),

    # ── Step 5: Terminale sicuro ───────────────────────────────────────────────
    ("terminal", [
        r"\b(esegui|lancia|eseguire|run|execute|fai girare)\s+\w",
        r"\b(versione di python|versione di pip|python --version)\b",
        r"\b(processi attivi|lista processi|ps aux|tasklist)\b",
        r"\b(uso del disco|spazio su disco|df -h)\b",
        r"\b(uso della ram|memoria (libera|disponibile)|quanta ram)\b",
        r"\b(ip (della macchina|locale)|indirizzo ip|ipconfig|ifconfig)\b",
        r"\b(container docker|docker ps|immagini docker)\b",
        r"\b(variabili d.ambiente|env|environment)\b",
        r"\b(uptime|da quanto[  ]è acceso)\b",
        r"\b(chi sono|utente corrente|whoami)\b",
        r"\b(file in questa cartella|cosa c.è qui|ls -la|dir)\b",
        r"\binstalla (la )?dip[en]+denza\b",
        r"\binstalla il pacchetto\b",
        r"\bpip install\b",
    ]),

    # ── Step 6: Focus / Productivity ──────────────────────────────────────────
    ("productivity", [
        # Focus mode
        r"\b(attiva|inizia|avvia|start)\s+(la\s+)?modalità\s+focus\b",
        r"\b(inizia|avvia|start|fai)\s+(un\s+)?pomodoro\b",
        r"\bpomodoro\s+(da\s+)?\d+\b",
        r"\b(pausa|metti in pausa)\s+(il\s+)?(focus|pomodoro)\b",
        r"\b(riprendi|continua)\s+(il\s+)?(focus|pomodoro)\b",
        r"\b(disattiva|ferma|stop|termina)\s+(la\s+)?(modalità\s+)?focus\b",
        r"\bquanto\s+(manca|resta|rimane)\b",
        r"\b(stato|status)\s+(del\s+)?(focus|pomodoro)\b",
        r"\b(aggiungi|rimuovi).+(blacklist\s+focus)\b",
        r"\b(lista|elenco)\s+(dei\s+)?siti\s+(bloccati|focus)\b",
        # Timer e promemoria
        r"\btimer\b", r"\bpromemoria\b", r"\bricorda\b", r"\ballarme\b",
        r"\bremind\b", r"\breminder\b", r"\balarm\b",
        r"\bconto alla rovescia\b",
    ]),

    ("system_control", [
        r"\b(volume|spegn[i]|riavvia|blocca|schermo|processo|task|wifi|bluetooth)\b",
        r"\b(shutdown|restart|lock|screen|process|wifi|bluetooth)\b",
    ]),
    ("media_player", [
        r"\b(musica|canzone|play|pausa|stop|skippa|riproduci|spotify)\b",
        r"\b(music|song|play|pause|stop|skip|spotify)\b",
    ]),
    ("vision", [
        r"\b(guarda|vedi|riconosce|cosa vedi)\b",
        r"\b(look|see|recognize|what do you see|camera)\b",
    ]),
    ("web_search", [
        r"\bcerca\b", r"\bsearch\b", r"\btrova\b", r"\bfind\b",
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
