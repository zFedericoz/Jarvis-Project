import logging, subprocess, os, re
from pathlib import Path

logger = logging.getLogger("jarvis.skills.git")

def execute(command: str, repo_path: str | None = None) -> str:
    try:
        repo = repo_path or "."
        repo = os.path.expanduser(repo)
        if not os.path.isdir(os.path.join(repo, ".git")):
            return f"'{repo}' non è un repository git valido."
        cmd_lower = command.lower()
        if "status" in cmd_lower or not cmd_lower:
            r = subprocess.run(["git", "status", "--short"], cwd=repo, capture_output=True, text=True, timeout=10)
            return r.stdout or "Nessuna modifica."
        elif "log" in cmd_lower or "commit" in cmd_lower and "ultim" in cmd_lower:
            n = 5
            m = re.search(r"(\d+)", cmd_lower)
            if m: n = int(m.group(1))
            r = subprocess.run(["git", "log", f"-{n}", "--oneline", "--decorate"], cwd=repo, capture_output=True, text=True, timeout=10)
            return r.stdout or "Nessun commit."
        elif "diff" in cmd_lower:
            r = subprocess.run(["git", "diff", "--stat"], cwd=repo, capture_output=True, text=True, timeout=10)
            return r.stdout or "Nessuna differenza."
        elif "branch" in cmd_lower:
            r = subprocess.run(["git", "branch", "-a"], cwd=repo, capture_output=True, text=True, timeout=10)
            return r.stdout or "Nessun branch."
        else:
            r = subprocess.run(["git", "status", "--short"], cwd=repo, capture_output=True, text=True, timeout=10)
            return r.stdout or "Comando non riconosciuto. Uso: status, log, diff, branch"
    except subprocess.TimeoutExpired:
        return "Git: timeout."
    except Exception as e:
        return f"Git: {e}"
