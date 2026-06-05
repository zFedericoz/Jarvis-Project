"""
GitAction — automazione Git per J.A.R.V.I.S.

Comandi vocali supportati:
  "JARVIS, fai il commit" / "JARVIS, committa tutto"
      → analizza le modifiche con git diff, genera un messaggio di commit
        professionale via LLM e fa il commit automaticamente

  "JARVIS, status git" / "JARVIS, che differenze ci sono"
      → mostra il git status in formato leggibile

  "JARVIS, mostrami il log git" / "JARVIS, ultimi commit"
      → mostra gli ultimi N commit con autore e data

  "JARVIS, push" / "JARVIS, fai il push"
      → esegue git push sull'origin corrente

  "JARVIS, crea un branch chiamato X"
      → crea e fa checkout di un nuovo branch

  "JARVIS, stash" / "JARVIS, salva le modifiche temporaneamente"
      → esegue git stash

Utilizzo da routes.py (già gestito dal multiagent tramite intent "git"):
    git_action = GitAction(config, llm_client)
    result = await git_action.execute("committa tutto", repo_path="C:/Dev/MioProgetto")
"""

import re
import logging
import asyncio
import subprocess
from pathlib import Path

from .base_action import BaseAction

logger = logging.getLogger("jarvis.actions.git")

# Pattern per il routing interno dei sottocomandi
_CMD_PATTERNS = [
    ("commit",  [r"\b(commit|committa|fai il commit|salva le modifiche nel repo)\b"]),
    ("status",  [r"\b(status|stato|git status|che differ|modifiche)\b"]),
    ("log",     [r"\b(log|ultimi commit|storia|cronologia|history)\b"]),
    ("push",    [r"\b(push|invia|carica sul remote|carica su github)\b"]),
    ("branch",  [r"\b(branch|ramo|crea branch|nuovo branch|checkout)\b"]),
    ("stash",   [r"\b(stash|salva temporane|metti da parte)\b"]),
    ("pull",    [r"\b(pull|aggiorna|scarica le modifiche)\b"]),
    ("diff",    [r"\b(diff|differenze|cosa ho cambiato|modifiche in dettaglio)\b"]),
]

# Prompt LLM per generare i commit message
_COMMIT_SYSTEM_PROMPT = """Sei un esperto di Git. Analizza il diff fornito e genera UN SOLO
messaggio di commit seguendo la Conventional Commits specification:

  <type>(<scope opzionale>): <descrizione breve in italiano>

  [corpo opzionale: spiega il PERCHÉ, non il cosa — max 3 righe]

Tipi validi: feat, fix, refactor, style, docs, test, chore, perf, ci
Regole:
- Prima riga: max 72 caratteri
- Usa l'imperativo presente ("aggiunge", "corregge", non "aggiunto" o "ho corretto")
- Non aggiungere punto finale alla prima riga
- Rispondi SOLO con il messaggio di commit, niente altro"""


class GitAction(BaseAction):
    def __init__(self, config: dict, llm_client=None):
        super().__init__(config)
        self._llm = llm_client
        # Cartella di default: leggibile dalle preferenze utente o dalla config
        default_repo = config.get("git", {}).get("default_repo", ".")
        self._default_repo = Path(default_repo).resolve()

    # ──────────────────────────────────────────────
    # Entry point
    # ──────────────────────────────────────────────

    async def execute(self, command: str, repo_path: str | None = None, **kwargs) -> str:
        cmd = command.lower()
        repo = Path(repo_path).resolve() if repo_path else self._default_repo

        if not self._is_git_repo(repo):
            return (
                f"La cartella '{repo}' non è un repository Git. "
                "Specifica il percorso corretto o imposta 'git.default_repo' in settings.yaml."
            )

        sub = self._route(cmd)
        logger.info(f"GitAction: sottocomando={sub}, repo={repo}")

        if sub == "commit":
            return await self._do_commit(repo, command)
        elif sub == "status":
            return self._do_status(repo)
        elif sub == "log":
            n = self._extract_number(cmd, default=5)
            return self._do_log(repo, n)
        elif sub == "push":
            return self._do_push(repo)
        elif sub == "branch":
            branch_name = self._extract_branch_name(command)
            return self._do_branch(repo, branch_name)
        elif sub == "stash":
            return self._do_stash(repo)
        elif sub == "pull":
            return self._do_pull(repo)
        elif sub == "diff":
            return self._do_diff(repo, summary=True)
        else:
            return "Comando Git non riconosciuto. Puoi chiedermi: commit, status, log, push, pull, branch, stash o diff."

    # ──────────────────────────────────────────────
    # Sottocomandi
    # ──────────────────────────────────────────────

    async def _do_commit(self, repo: Path, original_command: str) -> str:
        """
        Flusso:
          1. git diff --staged (se vuoto → git add -A prima)
          2. Genera commit message via LLM analizzando il diff
          3. git commit -m "<messaggio>"
          4. Ritorna conferma con il messaggio usato
        """
        # Controlla se ci sono modifiche staged
        diff_staged = self._run_git(repo, ["diff", "--staged", "--stat"])
        if not diff_staged.strip():
            # Nessun file staged: fai git add -A automaticamente
            add_out = self._run_git(repo, ["add", "-A"])
            logger.info(f"git add -A: {add_out.strip() or 'ok'}")
            diff_staged = self._run_git(repo, ["diff", "--staged", "--stat"])

        if not diff_staged.strip():
            return "Nessuna modifica da committare. Il working tree è pulito."

        # Ottieni il diff completo (limitato a 3000 caratteri per non saturare il contesto LLM)
        diff_full = self._run_git(repo, ["diff", "--staged"])
        diff_truncated = diff_full[:3000] + ("\n[...diff troncato...]" if len(diff_full) > 3000 else "")

        # Genera commit message con LLM
        commit_msg = await self._generate_commit_message(diff_truncated, diff_staged)

        if not commit_msg:
            return "Non sono riuscito a generare un messaggio di commit. Riprova o specificalo manualmente."

        # Esegui il commit
        result = self._run_git(repo, ["commit", "-m", commit_msg])

        if "nothing to commit" in result.lower():
            return "Nessuna modifica da committare."

        if "master" in result.lower() or "main" in result.lower() or "[" in result:
            logger.info(f"Commit eseguito: {commit_msg}")
            return f"✓ Commit eseguito:\n\n\"{commit_msg}\"\n\n{result.strip()}"

        # Se c'è stato un errore
        logger.warning(f"Commit output inatteso: {result}")
        return f"Commit completato (verifica il risultato):\n{result.strip()}"

    def _do_status(self, repo: Path) -> str:
        raw = self._run_git(repo, ["status", "--short", "--branch"])
        if not raw.strip():
            return "Il working tree è pulito, nessuna modifica."

        lines = raw.strip().split("\n")
        branch_line = next((l for l in lines if l.startswith("##")), "")
        changes = [l for l in lines if not l.startswith("##")]

        parts = []
        if branch_line:
            branch = branch_line.replace("##", "").strip()
            parts.append(f"Branch corrente: {branch}")

        if changes:
            staged = [l for l in changes if l[0] in ("A", "M", "D", "R") and l[0] != " "]
            unstaged = [l for l in changes if l[1:2] in ("M", "D", "?")]
            untracked = [l for l in changes if l.startswith("?")]

            if staged:
                parts.append(f"Staged ({len(staged)}): " + ", ".join(l[3:] for l in staged))
            if unstaged and not untracked:
                parts.append(f"Modificati ({len(unstaged)}): " + ", ".join(l[3:] for l in unstaged))
            if untracked:
                parts.append(f"Non tracciati ({len(untracked)}): " + ", ".join(l[3:] for l in untracked))
        else:
            parts.append("Nessuna modifica rilevata.")

        return "\n".join(parts)

    def _do_log(self, repo: Path, n: int = 5) -> str:
        fmt = "%h | %an | %ar | %s"
        raw = self._run_git(repo, ["log", f"--max-count={n}", f"--pretty=format:{fmt}"])
        if not raw.strip():
            return "Nessun commit trovato in questo repository."

        lines = raw.strip().split("\n")
        formatted = [f"{i+1}. {line}" for i, line in enumerate(lines)]
        return f"Ultimi {len(lines)} commit:\n" + "\n".join(formatted)

    def _do_push(self, repo: Path) -> str:
        result = self._run_git(repo, ["push"])
        if "error" in result.lower() or "fatal" in result.lower():
            return f"Push fallito:\n{result.strip()}"
        if "up-to-date" in result.lower() or "up to date" in result.lower():
            return "Il branch remoto è già aggiornato."
        return f"Push completato:\n{result.strip()}"

    def _do_pull(self, repo: Path) -> str:
        result = self._run_git(repo, ["pull"])
        if "error" in result.lower() or "fatal" in result.lower():
            return f"Pull fallito:\n{result.strip()}"
        if "already up to date" in result.lower():
            return "Il repository è già aggiornato."
        return f"Pull completato:\n{result.strip()}"

    def _do_branch(self, repo: Path, branch_name: str | None) -> str:
        if not branch_name:
            # Lista i branch esistenti
            raw = self._run_git(repo, ["branch", "--list"])
            if not raw.strip():
                return "Nessun branch trovato."
            return "Branch disponibili:\n" + raw.strip()

        # Crea e switcha al nuovo branch
        result = self._run_git(repo, ["checkout", "-b", branch_name])
        if "error" in result.lower() or "fatal" in result.lower():
            return f"Errore creazione branch '{branch_name}':\n{result.strip()}"
        return f"Branch '{branch_name}' creato e attivato."

    def _do_stash(self, repo: Path) -> str:
        result = self._run_git(repo, ["stash"])
        if "no local changes" in result.lower():
            return "Nessuna modifica locale da mettere in stash."
        return f"Modifiche salvate nello stash:\n{result.strip()}"

    def _do_diff(self, repo: Path, summary: bool = False) -> str:
        args = ["diff", "--stat"] if summary else ["diff"]
        raw = self._run_git(repo, args)
        if not raw.strip():
            return "Nessuna differenza rispetto all'ultimo commit."
        return raw.strip()[:1500]  # limita output vocale

    # ──────────────────────────────────────────────
    # LLM commit message generation
    # ──────────────────────────────────────────────

    async def _generate_commit_message(self, diff: str, stat: str) -> str | None:
        if not self._llm:
            # Fallback senza LLM: messaggio generico basato sulle statistiche
            return f"chore: aggiornamento automatico\n\n{stat.strip()[:200]}"

        prompt = f"Statistiche modifiche:\n{stat}\n\nDiff completo:\n{diff}"
        try:
            # Chiamata sincrona in executor per non bloccare l'event loop
            loop = asyncio.get_event_loop()
            msg = await loop.run_in_executor(
                None,
                lambda: self._llm.chat(
                    prompt,
                    system_override=_COMMIT_SYSTEM_PROMPT,
                    language="it",
                )
            )
            # Pulizia: rimuovi backtick, virgolette esterne, spazi
            msg = msg.strip().strip("`\"'")
            return msg if msg else None
        except Exception as e:
            logger.warning(f"LLM commit message generation fallita: {e}")
            return None

    # ──────────────────────────────────────────────
    # Utility
    # ──────────────────────────────────────────────

    def _run_git(self, repo: Path, args: list[str]) -> str:
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=str(repo),
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace",
            )
            output = (result.stdout + result.stderr).strip()
            logger.debug(f"git {' '.join(args)} → {output[:200]}")
            return output
        except subprocess.TimeoutExpired:
            return "Timeout: il comando Git ha impiegato troppo tempo."
        except FileNotFoundError:
            return "Git non trovato. Assicurati che Git sia installato e nel PATH."
        except Exception as e:
            logger.error(f"Errore git {args}: {e}")
            return f"Errore: {e}"

    def _is_git_repo(self, path: Path) -> bool:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=str(path),
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _route(self, cmd: str) -> str:
        for sub, patterns in _CMD_PATTERNS:
            for p in patterns:
                if re.search(p, cmd):
                    return sub
        return "status"  # default

    def _extract_number(self, text: str, default: int = 5) -> int:
        m = re.search(r"(\d+)", text)
        return int(m.group(1)) if m else default

    def _extract_branch_name(self, text: str) -> str | None:
        # "crea branch chiamato feature/login" → "feature/login"
        m = re.search(r"(?:chiamato|named?|branch)\s+([a-zA-Z0-9/_\-]+)", text, re.IGNORECASE)
        return m.group(1) if m else None
