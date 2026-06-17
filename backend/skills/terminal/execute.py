import logging, subprocess, shlex

logger = logging.getLogger("jarvis.skills.terminal")

ALLOWED_CATEGORIES = {"info": {"ps","df","free","uname","whoami","date","uptime","tasklist","systeminfo","ver","echo","dir","type","find"},
                     "filesystem": {"ls","dir","find","cat","head","tail","pwd","tree","wc","where","which","cd"},
                     "python": {"python","python3","pip"},
                     "docker_info": {"docker"}}


def _check_safe(cmd: str) -> bool:
    parts = shlex.split(cmd)
    if not parts:
        return False
    base = parts[0].lower()
    for category, cmds in ALLOWED_CATEGORIES.items():
        if base in cmds:
            return True
        if base.startswith("docker") and category == "docker_info":
            safe_sub = {"ps","images","logs","stats","inspect","version","info","network","volume"}
            sub = parts[1] if len(parts) > 1 else ""
            if sub in safe_sub:
                return True
    return False

def execute(command: str) -> str:
    if not _check_safe(command):
        return f"Comando non consentito: {command.split()[0] if command.split() else '?'}"
    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=15)
        out = (r.stdout or "") + (r.stderr or "")
        return out[:2000] or "Comando eseguito (nessun output)."
    except subprocess.TimeoutExpired:
        return "Timeout dopo 15 secondi."
    except Exception as e:
        return f"Errore: {e}"
