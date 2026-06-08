"""
FocusMode — modalità di concentrazione per J.A.R.V.I.S.

Funzionalità:
  1. Timer Pomodoro (25 min lavoro / 5 min pausa, configurabile)
  2. Blocco siti distraenti via file hosts (richiede privilegi elevati su Windows)
  3. Silenziamento notifiche di sistema (Windows: Focus Assist / DND)
  4. Stato corrente della sessione Focus

Comandi vocali:
  "JARVIS, attiva la modalità focus"
  "JARVIS, inizia un pomodoro"
  "JARVIS, pomodoro da 45 minuti"
  "JARVIS, pausa focus"
  "JARVIS, disattiva focus"
  "JARVIS, quanto manca al pomodoro?"
  "JARVIS, aggiungi reddit alla blacklist focus"
  "JARVIS, rimuovi youtube dalla blacklist focus"

API REST (aggiunto a routes.py):
  POST /api/focus/start       { "duration_minutes": 25 }
  POST /api/focus/stop
  POST /api/focus/pause
  GET  /api/focus/status
  POST /api/focus/sites/add   { "site": "reddit.com" }
  POST /api/focus/sites/remove{ "site": "reddit.com" }
"""

import re
import time
import threading
import subprocess
import platform
import logging
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum

logger = logging.getLogger("jarvis.actions.focus")

# ── Configurazione defaults ────────────────────────────────────────────────────
DEFAULT_WORK_MINUTES = 25
DEFAULT_BREAK_MINUTES = 5
DEFAULT_LONG_BREAK_MINUTES = 15
POMODOROS_BEFORE_LONG_BREAK = 4

# ── Siti bloccati di default durante il focus ──────────────────────────────────
DEFAULT_BLOCKED_SITES = [
    "reddit.com", "www.reddit.com",
    "twitter.com", "www.twitter.com", "x.com",
    "facebook.com", "www.facebook.com",
    "instagram.com", "www.instagram.com",
    "tiktok.com", "www.tiktok.com",
    "youtube.com", "www.youtube.com",
    "twitch.tv", "www.twitch.tv",
    "9gag.com", "www.9gag.com",
]

# ── File hosts ────────────────────────────────────────────────────────────────
if platform.system() == "Windows":
    HOSTS_FILE = Path(r"C:\Windows\System32\drivers\etc\hosts")
else:
    HOSTS_FILE = Path("/etc/hosts")

HOSTS_MARKER_START = "# JARVIS-FOCUS-START"
HOSTS_MARKER_END   = "# JARVIS-FOCUS-END"
REDIRECT_IP        = "127.0.0.1"


class FocusState(str, Enum):
    IDLE      = "idle"
    WORKING   = "working"
    BREAK     = "break"
    PAUSED    = "paused"


class FocusMode:
    def __init__(self, config: dict, tts=None, persistent_memory=None):
        self._config = config
        self._tts = tts
        self._mem = persistent_memory

        focus_cfg = config.get("focus", {})
        self._work_min   = focus_cfg.get("work_minutes", DEFAULT_WORK_MINUTES)
        self._break_min  = focus_cfg.get("break_minutes", DEFAULT_BREAK_MINUTES)
        self._long_break = focus_cfg.get("long_break_minutes", DEFAULT_LONG_BREAK_MINUTES)
        self._block_sites = focus_cfg.get("block_sites", True)
        self._mute_notifications = focus_cfg.get("mute_notifications", True)

        # Carica la lista siti personalizzata dalla memoria persistente
        if self._mem:
            saved = self._mem.get_preference("focus_blocked_sites")
            self._blocked_sites: list[str] = saved if saved else list(DEFAULT_BLOCKED_SITES)
        else:
            self._blocked_sites = list(DEFAULT_BLOCKED_SITES)

        # Stato sessione
        self._state = FocusState.IDLE
        self._pomodoro_count = 0
        self._session_start: datetime | None = None
        self._phase_end: datetime | None = None
        self._timer_thread: threading.Thread | None = None
        self._pause_remaining: float = 0.0

    # ──────────────────────────────────────────────
    # API pubblica
    # ──────────────────────────────────────────────

    def start(self, work_minutes: int | None = None) -> str:
        if self._state == FocusState.WORKING:
            remaining = self._seconds_remaining()
            return f"Modalità focus già attiva. Mancano {self._fmt(remaining)} al termine della sessione."

        duration = work_minutes or self._work_min
        self._state = FocusState.WORKING
        self._session_start = datetime.now()
        self._phase_end = datetime.now() + timedelta(minutes=duration)
        self._pomodoro_count += 1

        # Blocca siti e silenzia notifiche
        if self._block_sites:
            blocked_count = self._apply_hosts_block()
        else:
            blocked_count = 0

        if self._mute_notifications:
            self._set_focus_assist(True)

        # Avvia il timer in background
        self._start_timer_thread(duration * 60)

        parts = [f"🍅 Pomodoro #{self._pomodoro_count} avviato — {duration} minuti di lavoro."]
        if blocked_count:
            parts.append(f"{blocked_count} siti bloccati.")
        if self._mute_notifications:
            parts.append("Notifiche silenziato.")
        parts.append("Buona concentrazione.")
        return " ".join(parts)

    def stop(self) -> str:
        if self._state == FocusState.IDLE:
            return "Nessuna sessione focus attiva."

        self._cancel_timer()
        self._state = FocusState.IDLE
        self._phase_end = None

        if self._block_sites:
            self._remove_hosts_block()
        if self._mute_notifications:
            self._set_focus_assist(False)

        elapsed = ""
        if self._session_start:
            secs = int((datetime.now() - self._session_start).total_seconds())
            elapsed = f" Sessione durata: {self._fmt(secs)}."

        return f"Modalità focus disattivata.{elapsed} Ottimo lavoro."

    def pause(self) -> str:
        if self._state != FocusState.WORKING:
            return "Non c'è una sessione focus attiva da mettere in pausa."

        self._cancel_timer()
        self._pause_remaining = self._seconds_remaining()
        self._state = FocusState.PAUSED

        if self._block_sites:
            self._remove_hosts_block()

        return f"Focus in pausa. Mancano {self._fmt(self._pause_remaining)} quando riprendi."

    def resume(self) -> str:
        if self._state != FocusState.PAUSED:
            return "Il focus non è in pausa."

        self._state = FocusState.WORKING
        self._phase_end = datetime.now() + timedelta(seconds=self._pause_remaining)

        if self._block_sites:
            self._apply_hosts_block()

        self._start_timer_thread(self._pause_remaining)
        return f"Focus ripreso. {self._fmt(self._pause_remaining)} rimanenti."

    def status(self) -> dict:
        remaining = self._seconds_remaining() if self._state in (FocusState.WORKING, FocusState.PAUSED) else 0
        return {
            "state": self._state.value,
            "pomodoro_count": self._pomodoro_count,
            "remaining_seconds": int(remaining),
            "remaining_formatted": self._fmt(remaining),
            "session_start": self._session_start.isoformat() if self._session_start else None,
            "phase_end": self._phase_end.isoformat() if self._phase_end else None,
            "blocked_sites": self._blocked_sites,
            "notifications_muted": self._mute_notifications and self._state == FocusState.WORKING,
        }

    def status_text(self) -> str:
        s = self.status()
        if s["state"] == "idle":
            return f"Nessuna sessione focus attiva. Completati oggi: {s['pomodoro_count']} pomodori."
        if s["state"] == "paused":
            return f"Focus in pausa. Rimanenti quando riprendi: {s['remaining_formatted']}."
        return (
            f"Focus attivo — Pomodoro #{s['pomodoro_count']}. "
            f"Mancano {s['remaining_formatted']}."
        )

    # ── Gestione siti ─────────────────────────────────────────────────────────

    def add_site(self, site: str) -> str:
        site = site.strip().lower()
        if not site.startswith("www."):
            variants = [site, f"www.{site}"]
        else:
            variants = [site, site[4:]]

        added = []
        for v in variants:
            if v not in self._blocked_sites:
                self._blocked_sites.append(v)
                added.append(v)

        self._save_sites()
        if not added:
            return f"'{site}' è già nella blacklist focus."
        return f"Aggiunto alla blacklist focus: {', '.join(added)}."

    def remove_site(self, site: str) -> str:
        site = site.strip().lower()
        variants = [site, f"www.{site}", site.replace("www.", "")]
        removed = [v for v in variants if v in self._blocked_sites]
        self._blocked_sites = [s for s in self._blocked_sites if s not in variants]
        self._save_sites()

        if not removed:
            return f"'{site}' non era nella blacklist focus."
        return f"Rimosso dalla blacklist: {', '.join(removed)}."

    def list_sites(self) -> str:
        if not self._blocked_sites:
            return "La blacklist focus è vuota."
        return "Siti bloccati durante il focus:\n" + "\n".join(f"  - {s}" for s in sorted(self._blocked_sites))

    # ──────────────────────────────────────────────
    # Timer interno
    # ──────────────────────────────────────────────

    def _start_timer_thread(self, seconds: float):
        self._cancel_timer()
        self._timer_thread = threading.Thread(
            target=self._timer_loop,
            args=(seconds,),
            daemon=True,
            name="jarvis-focus-timer",
        )
        self._timer_thread.start()

    def _cancel_timer(self):
        if self._timer_thread and self._timer_thread.is_alive():
            # Usiamo un evento per interrompere il loop
            self._timer_stop = True
        self._timer_thread = None

    def _timer_loop(self, total_seconds: float):
        self._timer_stop = False
        interval = 0.5
        elapsed = 0.0
        while elapsed < total_seconds:
            if self._timer_stop:
                return
            time.sleep(interval)
            elapsed += interval

        if not self._timer_stop:
            if self._state == FocusState.WORKING:
                self._on_work_complete()
            elif self._state == FocusState.BREAK:
                self._on_break_complete()

    def _on_work_complete(self):
        self._pomodoro_count_completed = getattr(self, "_pomodoro_count_completed", 0) + 1
        is_long = self._pomodoro_count_completed % POMODOROS_BEFORE_LONG_BREAK == 0
        break_min = self._long_break if is_long else self._break_min
        break_type = "lunga" if is_long else "breve"

        logger.info(f"Pomodoro completato! Pausa {break_type} di {break_min} minuti.")
        self._notify(
            f"🍅 Pomodoro completato! Pausa {break_type} di {break_min} minuti.",
            speak=True,
        )

        # Avvia la pausa automaticamente
        self._state = FocusState.BREAK
        self._phase_end = datetime.now() + timedelta(minutes=break_min)

        if self._block_sites:
            self._remove_hosts_block()

        self._start_timer_thread(break_min * 60)

    def _on_break_complete(self):
        logger.info("Pausa terminata. Pronto per un nuovo pomodoro.")
        self._notify("Pausa terminata. Pronto per ricominciare!", speak=True)
        self._state = FocusState.IDLE
        self._phase_end = None

    # ──────────────────────────────────────────────
    # Blocco siti (file hosts)
    # ──────────────────────────────────────────────

    def _apply_hosts_block(self) -> int:
        """Aggiunge le voci al file hosts. Ritorna il numero di siti bloccati."""
        try:
            content = HOSTS_FILE.read_text(encoding="utf-8", errors="replace")

            # Rimuovi eventuali blocchi precedenti rimasti
            content = self._strip_hosts_block(content)

            lines = [f"\n{HOSTS_MARKER_START}"]
            for site in self._blocked_sites:
                lines.append(f"{REDIRECT_IP}  {site}")
            lines.append(HOSTS_MARKER_END)

            new_content = content + "\n".join(lines) + "\n"
            self._write_hosts(new_content)
            logger.info(f"Hosts bloccati: {len(self._blocked_sites)} siti")
            return len(self._blocked_sites)

        except PermissionError:
            logger.warning(
                "Permessi insufficienti per modificare il file hosts. "
                "Avvia JARVIS come amministratore per abilitare il blocco siti."
            )
            return 0
        except Exception as e:
            logger.error(f"Errore blocco hosts: {e}")
            return 0

    def _remove_hosts_block(self):
        """Rimuove le voci JARVIS dal file hosts."""
        try:
            content = HOSTS_FILE.read_text(encoding="utf-8", errors="replace")
            new_content = self._strip_hosts_block(content)
            if new_content != content:
                self._write_hosts(new_content)
                logger.info("Blocco hosts rimosso")
        except PermissionError:
            logger.warning("Permessi insufficienti per ripristinare il file hosts.")
        except Exception as e:
            logger.error(f"Errore rimozione hosts: {e}")

    def _strip_hosts_block(self, content: str) -> str:
        """Rimuove il blocco JARVIS dal testo del file hosts."""
        lines = content.split("\n")
        result = []
        inside = False
        for line in lines:
            if HOSTS_MARKER_START in line:
                inside = True
                continue
            if HOSTS_MARKER_END in line:
                inside = False
                continue
            if not inside:
                result.append(line)
        return "\n".join(result)

    def _write_hosts(self, content: str):
        """Scrive il file hosts con la giusta modalità (admin su Windows)."""
        if platform.system() == "Windows":
            # Su Windows scriviamo via PowerShell per gestire l'UAC
            ps_cmd = f'Set-Content -Path "{HOSTS_FILE}" -Value @\'\n{content}\n\'@'
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, check=True, timeout=10,
            )
        else:
            HOSTS_FILE.write_text(content, encoding="utf-8")

    # ──────────────────────────────────────────────
    # Notifiche e Focus Assist (Windows)
    # ──────────────────────────────────────────────

    def _set_focus_assist(self, enable: bool):
        """
        Windows: attiva/disattiva Focus Assist (modalità Non disturbare).
        Livello: 1 = Priority only, 2 = Alarms only (più restrittivo).
        Su Linux/Mac: nessuna azione (la funzionalità non è disponibile nativamente).
        """
        if platform.system() != "Windows":
            logger.info("Focus Assist disponibile solo su Windows — skip.")
            return
        try:
            value = "1" if enable else "0"   # 0 = off, 1 = priority, 2 = alarms only
            ps_cmd = (
                f'Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\CloudStore'
                f'\\Store\\Cache\\DefaultAccount\\$$windows.data.notifications.quiethourssettings'
                f'\\Current\\Data" -Name "Data" -Value {value} -Type DWord -ErrorAction SilentlyContinue'
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, timeout=5,
            )
            logger.info(f"Focus Assist: {'attivato' if enable else 'disattivato'}")
        except Exception as e:
            logger.warning(f"Focus Assist fallito: {e}")

    def _notify(self, message: str, speak: bool = False):
        """Notifica toast di Windows + TTS opzionale."""
        # Toast Windows
        try:
            ps_script = f"""
$null = [System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms")
$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::Information
$notify.BalloonTipTitle = "J.A.R.V.I.S. Focus"
$notify.BalloonTipText = "{message}"
$notify.Visible = $true
$notify.ShowBalloonTip(8000)
Start-Sleep -Seconds 8
$notify.Dispose()
"""
            subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", ps_script],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.warning(f"Toast notification fallita: {e}")

        # TTS
        if speak and self._tts:
            try:
                audio = self._tts.synthesize(message, language="it")
                if audio:
                    self._play_audio(audio)
            except Exception as e:
                logger.warning(f"TTS notifica focus fallita: {e}")

    def _play_audio(self, audio_bytes: bytes):
        """Riproduce l'audio WAV via PowerShell (senza dipendenze esterne)."""
        try:
            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_bytes)
                tmp_path = f.name
            ps_cmd = (
                f'$player = New-Object System.Media.SoundPlayer "{tmp_path}"; '
                f'$player.PlaySync(); Remove-Item "{tmp_path}" -ErrorAction SilentlyContinue'
            )
            subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.warning(f"Riproduzione audio focus fallita: {e}")

    # ──────────────────────────────────────────────
    # Utility
    # ──────────────────────────────────────────────

    def _seconds_remaining(self) -> float:
        if not self._phase_end:
            return 0.0
        delta = (self._phase_end - datetime.now()).total_seconds()
        return max(0.0, delta)

    def _fmt(self, seconds: float) -> str:
        seconds = int(seconds)
        if seconds <= 0:
            return "0 secondi"
        m, s = divmod(seconds, 60)
        if m and s:
            return f"{m} min {s} sec"
        if m:
            return f"{m} minuti"
        return f"{s} secondi"

    def _save_sites(self):
        if self._mem:
            self._mem.set_preference("focus_blocked_sites", self._blocked_sites)
