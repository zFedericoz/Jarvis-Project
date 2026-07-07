import logging
import os
import subprocess

from .base_action import BaseAction

logger = logging.getLogger("jarvis.actions.media")

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
    _spotipy_available = True
except ImportError:
    _spotipy_available = False


class MediaPlayer(BaseAction):
    def __init__(self, config: dict):
        super().__init__(config)
        self._spotify = None
        self._try_init_spotify()

    def _try_init_spotify(self):
        if not _spotipy_available:
            return
        cid = os.getenv("SPOTIFY_CLIENT_ID")
        secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        if cid and secret:
            try:
                auth = SpotifyClientCredentials(client_id=cid, client_secret=secret)
                self._spotify = spotipy.Spotify(auth_manager=auth)
                logger.info("Spotify connesso")
            except Exception as e:
                logger.warning("Spotify init fallito: %s", e)
        else:
            logger.info("SPOTIFY_CLIENT_ID/SECRET non impostati — solo media keys")

    async def execute(self, command: str, **kwargs) -> str:
        cmd = command.lower()

        if "riproduci" in cmd or ("play" in cmd and "non" not in cmd):
            return self._play()
        if "pausa" in cmd or "pause" in cmd:
            return self._pause()
        if "stop" in cmd:
            return self._stop()
        if "next" in cmd or "skippa" in cmd or "successiva" in cmd or "prossima" in cmd:
            return self._next()
        if "precedente" in cmd or "previous" in cmd or "indietro" in cmd:
            return self._previous()
        if "volume" in cmd:
            return self._set_volume(cmd)
        if "info" in cmd or "cosa sta suonando" in cmd or "che musica" in cmd:
            return self._now_playing()

        return "Media command not recognized."

    def _play(self) -> str:
        if self._spotify:
            try:
                devices = self._spotify.devices()
                if devices.get("devices"):
                    self._spotify.start_playback()
                    return "Riproduzione avviata su Spotify."
            except Exception as e:
                logger.warning("Spotify play fallito: %s", e)
        self._send_media_key(0xB3)
        return "Play."

    def _pause(self) -> str:
        if self._spotify:
            try:
                self._spotify.pause_playback()
                return "Spotify in pausa."
            except Exception as e:
                logger.warning("Spotify pause fallito: %s", e)
        self._send_media_key(0xB3)
        return "Pausa."

    def _stop(self) -> str:
        if self._spotify:
            try:
                self._spotify.pause_playback()
                return "Spotify fermato."
            except Exception:
                pass
        return "Stop non supportato via media keys."

    def _next(self) -> str:
        if self._spotify:
            try:
                self._spotify.next_track()
                return "Prossima traccia su Spotify."
            except Exception as e:
                logger.warning("Spotify next fallito: %s", e)
        self._send_media_key(0xB0)
        return "Traccia successiva."

    def _previous(self) -> str:
        if self._spotify:
            try:
                self._spotify.previous_track()
                return "Traccia precedente su Spotify."
            except Exception as e:
                logger.warning("Spotify previous fallito: %s", e)
        self._send_media_key(0xB1)
        return "Traccia precedente."

    def _now_playing(self) -> str:
        if self._spotify:
            try:
                current = self._spotify.current_playback()
                if current and current.get("item"):
                    item = current["item"]
                    name = item["name"]
                    artist = ", ".join(a["name"] for a in item["artists"])
                    return f"Sta suonando {name} di {artist}."
            except Exception as e:
                logger.warning("Spotify now_playing fallito: %s", e)
        return "Info non disponibile."

    def _set_volume(self, cmd: str) -> str:
        return "Usa 'system_control' per regolare il volume."

    def _send_media_key(self, key_code: int):
        try:
            subprocess.run(
                ["powershell", "-c",
                 f"(New-Object -ComObject WScript.Shell).SendKeys([char]{hex(key_code)})"],
                capture_output=True, timeout=5,
            )
        except Exception as e:
            logger.warning("Media key fallita: %s", e)

    def can_handle(self, intent: str) -> bool:
        return intent == "media_player"