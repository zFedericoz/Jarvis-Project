"""
TerminalAction — terminale sicuro per J.A.R.V.I.S.

Architettura di sicurezza a TRE livelli:
  Livello 1 — Blacklist immediata (blocco prima dell'esecuzione)
              Comandi che possono danneggiare il sistema: rm -rf, format, del /s, ecc.

  Livello 2 — Whitelist per categoria
              Solo comandi appartenenti a categorie approvate vengono eseguiti.
              Nuove categorie si abilitano in settings.yaml (terminal.allowed_categories).

  Livello 3 — Timeout + output cap
              Ogni comando ha un timeout fisso (default 15s).
              L'output è troncato a MAX_OUTPUT_CHARS caratteri.

Comandi vocali supportati:
  "JARVIS, esegui ls -la"
  "JARVIS, che versione di Python ho?"          → python --version
  "JARVIS, quanta RAM sta usando node?"         → interpreta e mappa al comando giusto
  "JARVIS, mostrami i processi attivi"          → ps aux / tasklist
  "JARVIS, installa la dipendenza requests"     → pip install requests (se abilitato)
  "JARVIS, esegui lo script analisi.py"         → python analisi.py (nella working dir)

API REST:
  POST /api/terminal/run    { "command": "ls -la", "cwd": "/app" }
  GET  /api/terminal/history
  GET  /api/terminal/allowed

Configurazione in settings.yaml:
  terminal:
    enabled: true
    working_dir: "."
    timeout: 15
    allowed_categories:
      - info          # ps, top, df, du, free, uname, whoami, env, date
      - filesystem    # ls, dir, find, cat, head, tail, pwd, tree
      - python        # python, pip
      - git           # (delegato a GitAction, qui solo fallback)
      - network_info  # ping, curl (solo GET), nslookup, traceroute
      - docker_info   # docker ps, docker images, docker logs (sola lettura)
"""

import re
import asyncio
import logging
import subprocess
import shlex
from datetime import datetime
from pathlib import Path
from collections import deque

from .base_action import BaseAction

logger = logging.getLogger("jarvis.actions.terminal")

# ── Costanti di sicurezza ──────────────────────────────────────────────────────

MAX_OUTPUT_CHARS = 2000   # output massimo restituito all'utente
MAX_HISTORY = 50          # comandi nell'history

# ── Blacklist: blocco IMMEDIATO, indipendentemente dalla whitelist ─────────────
# Qualsiasi comando che matcha uno di questi pattern viene rifiutato.
_BLACKLIST_PATTERNS = [
    # Eliminazione dati
    r"\brm\s+(-[a-z]*f[a-z]*\s+)?/",     # rm -rf /...
    r"\brm\s+-[a-z]*r",                   # rm -r qualsiasi cosa
    r"\bdel\s+/[sqa]",                    # del /s /q /a (Windows)
    r"\brmdir\s+/[sq]",                   # rmdir /s
    r"\brd\s+/[sq]",                      # rd /s
    r"\bformat\b",                        # format c:
    r"\bmkfs\b",                          # mkfs (formattazione Linux)
    r"\bdd\s+.*of=/dev/",                 # dd su device
    r">\s*/dev/(sd|hd|nvme|vd)",          # redirect su block device

    # Escalation privilegi
    r"\bsudo\s+su\b",
    r"\bsudo\s+bash\b",
    r"\bsudo\s+sh\b",
    r"\bchmod\s+777\s+/",
    r"\bchown\s+.*\s+/",
    r"\bpasswd\b",

    # Rete pericolosa
    r"\bnc\s+.*-e\b",                     # netcat reverse shell
    r"\bbash\s+-i\s+>&",                  # reverse shell bash
    r"\bpython.*-c.*socket",              # reverse shell python
    r"\bcurl\s+.*\|\s*(ba)?sh",           # curl | bash
    r"\bwget\s+.*\|\s*(ba)?sh",           # wget | bash

    # Manipolazione sistema
    r"\bshutdown\b",
    r"\breboot\b",
    r"\binit\s+[06]\b",
    r"\bsystemctl\s+(stop|disable|mask)\s+",
    r"\bkillall\b",
    r"\bkill\s+-9\s+1\b",               # kill init

    # Registri e file di sistema Windows
    r"\breg\s+(delete|add|import)",
    r"\bregsvr32\b",
    r"\bnet\s+(user|localgroup)\b",
    r"\bsc\s+(delete|stop|config)\b",
    r"\bbcdedit\b",
    r"\bdiskpart\b",

    # Offuscamento / shell injection
    r"eval\s+\$\(",
    r"\$\(.*\)",                          # command substitution in contesti sospetti
    r"base64\s+-d.*\|\s*bash",
    r";\s*(rm|del|format)\b",             # concatenazione pericolosa
    r"\|\s*(rm|del|format)\b",
    r"&&\s*(rm|del|format)\b",
]

# ── Whitelist per categoria ────────────────────────────────────────────────────
# Ogni categoria è un dizionario {bin: [argomenti_consentiti_regex | None]}
# None = tutti gli argomenti sono ok per quel bin

_CATEGORIES: dict[str, dict[str, list | None]] = {
    "info": {
        "ps": None,
        "top": [r"^-b"],                   # solo batch mode
        "htop": None,
        "df": None,
        "du": [r"^-[sh]+\s"],
        "free": None,
        "uname": None,
        "whoami": None,
        "env": None,
        "date": None,
        "uptime": None,
        "tasklist": None,                  # Windows
        "wmic": [r"process\s+get"],        # Windows — solo lettura processi
        "systeminfo": None,                # Windows
    },
    "filesystem": {
        "ls": None,
        "dir": None,
        "find": [r"^\.?\s*-name", r"^/[a-z].*-name"],
        "cat": None,
        "type": None,                      # Windows
        "head": None,
        "tail": None,
        "pwd": None,
        "cd": None,
        "tree": None,
        "stat": None,
        "file": None,
        "wc": None,
    },
    "python": {
        "python": None,
        "python3": None,
        "pip": [r"^(install|list|show|freeze|check)\s"],
        "pip3": [r"^(install|list|show|freeze|check)\s"],
    },
    "network_info": {
        "ping": [r"^(-c\s+\d+\s+)?[\w\.\-]+$"],  # solo host senza opzioni rischiose
        "curl": [r"^-[sI]*\s+https?://"],          # solo GET/HEAD HTTP
        "wget": [r"^-q\s+--spider\s+https?://"],   # solo check
        "nslookup": None,
        "dig": None,
        "ipconfig": None,                           # Windows
        "ifconfig": None,
        "ip": [r"^(addr|route|link)\s"],
        "netstat": [r"^-[tlnup]+$"],
    },
    "docker_info": {
        "docker": [
            r"^ps(\s|$)",
            r"^images(\s|$)",
            r"^logs\s",
            r"^stats(\s|$)",
            r"^inspect\s",
            r"^version(\s|$)",
            r"^info(\s|$)",
        ],
        "docker-compose": [
            r"^ps(\s|$)",
            r"^logs(\s|$)",
            r"^config(\s|$)",
        ],
    },
    "git": {
        # Delegato a GitAction, ma accettiamo comandi git base come fallback
        "git": [
            r"^(status|log|diff|branch|remote|tag|stash list)",
        ],
    },
}

# ── Mapping lingua naturale → comando ─────────────────────────────────────────
_NL_TO_CMD = [
    (r"(versione|version) di python", "python --version"),
    (r"versione di pip", "pip --version"),
    (r"(processi|process) attiv", "ps aux" if __import__("platform").system() != "Windows" else "tasklist"),
    (r"(uso|utilizzo) (del )?disco", "df -h"),
    (r"(uso|utilizzo) (della )?ram|memoria libera", "free -h"),
    (r"quanta ram", "free -h"),
    (r"(ip|indirizzo) (della macchina|locale|del server)", "ip addr" if __import__("platform").system() != "Windows" else "ipconfig"),
    (r"(uptime|da quanto[  ]è acceso)", "uptime"),
    (r"chi sono|utente corrente", "whoami"),
    (r"file in questa cartella|cosa c.è qui", "ls -la"),
    (r"container docker (attivi|in esecuzione)", "docker ps"),
    (r"immagini docker", "docker images"),
    (r"(variabili|env) d.ambiente", "env"),
]


class TerminalAction(BaseAction):
    def __init__(self, config: dict, llm_client=None):
        super().__init__(config)
        self._llm = llm_client
        self._history: deque[dict] = deque(maxlen=MAX_HISTORY)

        term_cfg = config.get("terminal", {})
        self._enabled = term_cfg.get("enabled", True)
        self._timeout = term_cfg.get("timeout", 15)
        self._allowed_categories = set(
            term_cfg.get("allowed_categories", ["info", "filesystem", "python"])
        )
        raw_wd = term_cfg.get("working_dir", ".")
        self._working_dir = Path(raw_wd).resolve()

        logger.info(
            f"TerminalAction pronto — categorie abilitate: {self._allowed_categories}, "
            f"cwd: {self._working_dir}"
        )

    # ──────────────────────────────────────────────
    # Entry point
    # ──────────────────────────────────────────────

    async def execute(self, command: str, cwd: str | None = None, **kwargs) -> str:
        if not self._enabled:
            return "Il terminale sicuro è disabilitato. Abilitalo in settings.yaml (terminal.enabled: true)."

        work_dir = Path(cwd).resolve() if cwd else self._working_dir

        # Estrai il comando shell dalla frase naturale
        shell_cmd = self._resolve_command(command)
        if not shell_cmd:
            return (
                "Non ho capito quale comando eseguire. "
                "Prova a essere più specifico, ad esempio: 'JARVIS, esegui ls -la' "
                "oppure 'JARVIS, che versione di Python ho'."
            )

        logger.info(f"TerminalAction: '{command}' → '{shell_cmd}'")

        # Livello 1: blacklist
        blocked, reason = self._check_blacklist(shell_cmd)
        if blocked:
            self._log_entry(command, shell_cmd, blocked=True, reason=reason)
            return (
                f"⛔ Comando bloccato per sicurezza: {reason}\n"
                f"Se hai bisogno di questa operazione, eseguila direttamente nel terminale."
            )

        # Livello 2: whitelist
        allowed, category = self._check_whitelist(shell_cmd)
        if not allowed:
            self._log_entry(command, shell_cmd, blocked=True, reason="non in whitelist")
            bins = self._extract_binary(shell_cmd)
            return (
                f"⚠️ Il comando '{bins}' non è nella lista dei comandi consentiti.\n"
                f"Categorie abilitate: {', '.join(sorted(self._allowed_categories))}.\n"
                f"Puoi aggiungere categorie in settings.yaml → terminal.allowed_categories."
            )

        # Livello 3: esecuzione con timeout
        stdout, stderr, returncode = await self._run(shell_cmd, work_dir)
        output = (stdout + ("\n" + stderr if stderr else "")).strip()
        output_truncated = output[:MAX_OUTPUT_CHARS]
        if len(output) > MAX_OUTPUT_CHARS:
            output_truncated += f"\n[...output troncato a {MAX_OUTPUT_CHARS} caratteri]"

        self._log_entry(command, shell_cmd, output=output_truncated, returncode=returncode)

        if returncode != 0 and not output_truncated:
            return f"Il comando è terminato con errore (codice {returncode})."

        if not output_truncated:
            return "Comando eseguito senza output."

        return f"```\n{output_truncated}\n```"

    # ──────────────────────────────────────────────
    # Risoluzione linguaggio naturale → comando
    # ──────────────────────────────────────────────

    def _resolve_command(self, text: str) -> str | None:
        """
        Tenta di estrarre/mappare il comando shell dalla frase dell'utente.
        Ordine di priorità:
          1. Comando esplicito dopo "esegui" / "lancia" / "run"
          2. Mapping NL → comando predefinito
          3. Fallback: usa la frase intera come comando (rischioso → passa cmq per blacklist/whitelist)
        """
        lower = text.lower().strip()

        # 1. Comando esplicito
        explicit = re.search(
            r"(?:esegui|lancia|eseguire|run|execute|fai girare)\s+(.+)",
            lower
        )
        if explicit:
            return explicit.group(1).strip()

        # 2. Mapping lingua naturale
        for pattern, cmd in _NL_TO_CMD:
            if re.search(pattern, lower):
                return cmd

        # 3. Se inizia direttamente con un binario noto, usalo com'è
        first_word = lower.split()[0] if lower.split() else ""
        all_bins = {bin_ for cat in _CATEGORIES.values() for bin_ in cat}
        if first_word in all_bins:
            return lower

        return None

    # ──────────────────────────────────────────────
    # Controlli di sicurezza
    # ──────────────────────────────────────────────

    def _check_blacklist(self, cmd: str) -> tuple[bool, str]:
        cmd_lower = cmd.lower()
        for pattern in _BLACKLIST_PATTERNS:
            if re.search(pattern, cmd_lower):
                logger.warning(f"BLACKLIST MATCH: '{cmd}' → pattern: {pattern}")
                return True, f"pattern pericoloso rilevato: `{pattern}`"
        return False, ""

    def _check_whitelist(self, cmd: str) -> tuple[bool, str]:
        """
        Ritorna (True, categoria) se il comando è consentito,
        (False, "") altrimenti.
        """
        binary = self._extract_binary(cmd)
        args = cmd[len(binary):].strip()

        for category, bins in _CATEGORIES.items():
            if category not in self._allowed_categories:
                continue
            if binary not in bins:
                continue
            allowed_args = bins[binary]
            if allowed_args is None:
                # Tutti gli argomenti consentiti per questo binary
                return True, category
            # Controlla che gli argomenti matchino almeno uno dei pattern consentiti
            for arg_pattern in allowed_args:
                if re.match(arg_pattern, args):
                    return True, category
            # Il binary è in whitelist ma gli argomenti non sono consentiti
            logger.info(f"Whitelist: binary '{binary}' ok ma args '{args}' non consentiti")
            return False, ""

        return False, ""

    def _extract_binary(self, cmd: str) -> str:
        """Estrae il primo token (il binario) da un comando shell."""
        try:
            tokens = shlex.split(cmd)
            return tokens[0].lower() if tokens else cmd.split()[0].lower()
        except ValueError:
            return cmd.split()[0].lower()

    # ──────────────────────────────────────────────
    # Esecuzione asincrona
    # ──────────────────────────────────────────────

    async def _run(self, cmd: str, cwd: Path) -> tuple[str, str, int]:
        try:
            # Parse comando in argomenti per evitare shell injection
            cmd_parts = shlex.split(cmd)
            if not cmd_parts:
                return "", "Empty command", 1

            # Usa subprocess_exec (NO shell) invece di subprocess_shell
            # Questo previene shell injection vulnerabilità
            proc = await asyncio.create_subprocess_exec(
                cmd_parts[0],
                *cmd_parts[1:],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self._timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                logger.warning(f"Timeout ({self._timeout}s) per: {cmd}")
                return "", f"Timeout: il comando ha superato {self._timeout} secondi.", 124

            stdout = stdout_b.decode("utf-8", errors="replace")
            stderr = stderr_b.decode("utf-8", errors="replace")
            return stdout, stderr, proc.returncode

        except FileNotFoundError:
            return "", f"Comando non trovato: '{cmd_parts[0] if cmd_parts else 'unknown'}'", 127
        except ValueError as e:
            logger.error(f"Errore parsing comando '{cmd}': {e}")
            return "", f"Invalid command syntax: {e}", 1
        except Exception as e:
            logger.error(f"Errore esecuzione '{cmd}': {e}")
            return "", str(e), 1

    # ──────────────────────────────────────────────
    # History
    # ──────────────────────────────────────────────

    def _log_entry(self, natural: str, cmd: str, output: str = "",
                   returncode: int = 0, blocked: bool = False, reason: str = ""):
        self._history.append({
            "timestamp": datetime.now().isoformat(),
            "natural": natural,
            "command": cmd,
            "output": output[:500],       # salviamo solo i primi 500 char nell'history
            "returncode": returncode,
            "blocked": blocked,
            "reason": reason,
        })

    def get_history(self) -> list[dict]:
        return list(reversed(self._history))

    def get_allowed_commands(self) -> dict:
        """Ritorna la mappa dei comandi consentiti nelle categorie abilitate."""
        allowed = {}
        for cat in self._allowed_categories:
            if cat in _CATEGORIES:
                allowed[cat] = list(_CATEGORIES[cat].keys())
        return allowed

    def can_handle(self, intent: str) -> bool:
        return intent == "terminal"
