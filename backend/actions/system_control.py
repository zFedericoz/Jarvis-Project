import re
import subprocess
import time
import psutil
import logging
from .base_action import BaseAction

logger = logging.getLogger("jarvis.actions.system")

_CONFIRM_TIMEOUT = 30

# Parole intere (con boundary \b) — evita falsi positivi da substring:
# "sicuramente" non matcha più "si" perché \bsi\b richiede spazi/bordi.
_CONFIRM_WORDS = {"sì", "si", "confermo", "conferma", "procedi", "ok", "yes", "y", "procede"}
_DENY_WORDS = {"no", "annulla", "cancel", "non", "ferma", "stop"}

# Anche i keyword distruttivi usano word boundary per evitare falsi match
_DESTRUCTIVE_KEYWORDS = {
    "shutdown": {"shutdown", "spegnimento", "spegnere", "spegni", "spengi", "spento"},
    "restart": {"restart", "riavvia", "riavvio", "reboot", "riavviare"},
}

# Pre-compila pattern per word boundary matching
_CONFIRM_PATTERNS = [re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE) for w in _CONFIRM_WORDS]
_DENY_PATTERNS = [re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE) for w in _DENY_WORDS]
# Pattern per i keyword distruttivi: un unico pattern per azione
_DESTRUCTIVE_PATTERNS = {
    action: re.compile(
        "|".join(rf"\b{re.escape(kw)}\b" for kw in kws),
        re.IGNORECASE,
    )
    for action, kws in _DESTRUCTIVE_KEYWORDS.items()
}


def _match_any(text: str, patterns: list[re.Pattern]) -> bool:
    """True se almeno un pattern matcha come parola intera in text."""
    return any(p.search(text) for p in patterns)


class SystemControl(BaseAction):
    def __init__(self, config: dict):
        super().__init__(config)
        self._pending: dict | None = None

    async def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower().strip()

        # ── Paso 1: controlla se c'è una conferma in sospeso ──────────
        if self._pending is not None:
            elapsed = time.time() - self._pending["timestamp"]
            if elapsed > _CONFIRM_TIMEOUT:
                logger.info("Conferma scaduta per %s", self._pending["action"])
                self._pending = None
            else:
                # Il diniego viene controllato PRIMA della conferma:
                # se una frase contiene sia parole di conferma che di diniego
                # (es. "sì, ma non ora"), prevale la cautela → annullamento.
                if _match_any(cmd, _DENY_PATTERNS):
                    action = self._pending["action"]
                    self._pending = None
                    return f"Operazione annullata, Signore. {action} non eseguito."

                if _match_any(cmd, _CONFIRM_PATTERNS):
                    stored = self._pending
                    self._pending = None
                    return self._execute_destructive(stored["action"])

                action = self._pending["action"]
                self._pending = None
                return (f"Richiesta precedente annullata. Eseguo il nuovo comando, Signore.\n"
                        + self._handle_safe(cmd))

        # ── Paso 2: nessuna conferma in sospeso, comando normale ──────
        for action, pattern in _DESTRUCTIVE_PATTERNS.items():
            if pattern.search(cmd):
                self._pending = {"action": action, "timestamp": time.time()}
                label = "spegnimento" if action == "shutdown" else "riavvio"
                return (f"Signore, ha richiesto il {label} del sistema. "
                        f"Questa operazione interromperà tutti i servizi in esecuzione. "
                        f"Conferma? Dica 'sì' o 'conferma' per procedere, "
                        f"'no' per annullare. Attendò istruzioni.")

        return self._handle_safe(cmd)

    def _handle_safe(self, cmd: str) -> str:
        """Esegue comandi non distruttivi (volume, lock, mute, stato)."""
        if "volume up" in cmd or "alza volume" in cmd:
            self._change_volume(5)
            return "Volume alzato, Signore."

        if "volume down" in cmd or "abbassa volume" in cmd:
            self._change_volume(-5)
            return "Volume abbassato, Signore."

        if "mute" in cmd or "silenzia" in cmd:
            self._change_volume(-100)
            return "Sistema silenziato, Signore."

        if "lock" in cmd or "blocca" in cmd:
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
            return "Workstation bloccata, Signore."

        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        return (f"Sistema stabile, Signore. CPU al {cpu}%, "
                f"RAM al {ram.percent}% ({ram.used // 1024**3}GB/{ram.total // 1024**3}GB usati).")

    def _execute_destructive(self, action: str) -> str:
        """Esegue l'azione distruttiva dopo conferma."""
        if action == "shutdown":
            try:
                subprocess.run(["shutdown", "/s", "/t", "10"], check=True)
                return "Procedo con lo spegnimento, Signore. 10 secondi al termine."
            except (FileNotFoundError, subprocess.CalledProcessError):
                return "Comando shutdown non disponibile su questo sistema, Signore."
        if action == "restart":
            try:
                subprocess.run(["shutdown", "/r", "/t", "10"], check=True)
                return "Procedo con il riavvio, Signore. 10 secondi al termine."
            except (FileNotFoundError, subprocess.CalledProcessError):
                return "Comando riavvio non disponibile su questo sistema, Signore."

    def _change_volume(self, delta: int):
        try:
            import pycaw.pycaw
            from pycaw.api.endpoint import AudioEndpoint
            subprocess.run(["nircmd", "changesysvolume", str(delta * 655)])
        except ImportError:
            try:
                script = f'''
$obj = New-Object -ComObject WScript.Shell
for ($i = 0; $i -lt [Math]::Abs({delta}); $i++) {{
    $obj.SendKeys([char]0xAF)
}}
'''
                subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, check=True)
            except (FileNotFoundError, subprocess.CalledProcessError):
                logger.warning("Volume change not available on this system")

    def can_handle(self, intent: str) -> bool:
        return intent == "system_control"