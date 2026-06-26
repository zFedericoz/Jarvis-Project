"""
Riconoscimento facciale — riconosce l'utente registrato tramite webcam.
Usa face_recognition (dlib) o deepface come fallback.
"""
import logging
import os
import threading
from pathlib import Path

import numpy as np

logger = logging.getLogger("jarvis.face_auth")

FACES_DIR = Path("data/known_faces")
FACE_TOLERANCE = 0.5  # distanza massima per match (più basso = più stretto)


class FaceAuth:
    def __init__(self):
        self._known_encodings: list[tuple[str, np.ndarray]] = []
        self._known_names: list[str] = []
        self._lock = threading.Lock()
        self._backend = self._detect_backend()
        self._load_known_faces()

    def _detect_backend(self) -> str:
        try:
            import face_recognition
            logger.info("FaceAuth backend: face_recognition (dlib)")
            return "face_recognition"
        except ImportError:
            pass
        try:
            from deepface import DeepFace
            logger.info("FaceAuth backend: DeepFace")
            return "deepface"
        except ImportError:
            logger.warning("Nessun backend face recognition disponibile. `pip install face_recognition` o `deepface`")
            return "none"

    def _load_known_faces(self):
        if self._backend == "none":
            return
        FACES_DIR.mkdir(parents=True, exist_ok=True)
        import face_recognition
        for f in FACES_DIR.glob("*.jpg") or FACES_DIR.glob("*.png"):
            try:
                img = face_recognition.load_image_file(str(f))
                enc = face_recognition.face_encodings(img)
                if enc:
                    name = f.stem.replace("_", " ").title()
                    self._known_encodings.append((name, enc[0]))
                    self._known_names.append(name)
                    logger.info(f"Faccia registrata: {name}")
            except Exception as e:
                logger.warning(f"Errore caricamento {f.name}: {e}")
        logger.info(f"Volti noti: {len(self._known_names)}")

    def register_face(self, name: str, image: np.ndarray) -> bool:
        """Registra un nuovo volto."""
        if self._backend == "none":
            return False
        import face_recognition
        enc = face_recognition.face_encodings(image)
        if not enc:
            logger.warning(f"Nessun volto trovato nell'immagine per {name}")
            return False
        FACES_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = name.lower().replace(" ", "_")
        path = FACES_DIR / f"{safe_name}.jpg"
        from PIL import Image
        Image.fromarray(image).save(str(path))
        with self._lock:
            self._known_encodings.append((name, enc[0]))
            self._known_names.append(name)
        logger.info(f"Volto registrato: {name}")
        return True

    def recognize(self, image: np.ndarray) -> dict:
        """Riconosce un volto in un'immagine. Restituisce {name, confidence, location}."""
        if self._backend == "none" or not self._known_encodings:
            return {"name": None, "confidence": 0.0, "location": None}

        import face_recognition
        face_locs = face_recognition.face_locations(image)
        if not face_locs:
            return {"name": None, "confidence": 0.0, "location": None}

        encodings = face_recognition.face_encodings(image, face_locs)
        if not encodings:
            return {"name": None, "confidence": 0.0, "location": None}

        best_match, best_dist = None, float("inf")
        for enc in encodings:
            distances = face_recognition.face_distance(self._known_encodings, enc)
            min_dist = min(distances) if len(distances) > 0 else float("inf")
            if min_dist < best_dist:
                best_dist = min_dist
                best_match = self._known_names[int(np.argmin(distances))] if len(distances) > 0 else None

        if best_match and best_dist <= FACE_TOLERANCE:
            confidence = max(0, 1 - (best_dist / FACE_TOLERANCE))
            top, right, bottom, left = face_locs[0]
            return {"name": best_match, "confidence": round(confidence, 2), "location": [top, right, bottom, left]}
        return {"name": None, "confidence": 0.0, "location": None}

    def list_faces(self) -> list[str]:
        return list(self._known_names)

    def delete_face(self, name: str) -> bool:
        safe = name.lower().replace(" ", "_")
        path = FACES_DIR / f"{safe}.jpg"
        if path.exists():
            path.unlink()
            self._load_known_faces()  # reload
            return True
        return False


_face_auth: FaceAuth | None = None


def get_face_auth() -> FaceAuth:
    global _face_auth
    if _face_auth is None:
        _face_auth = FaceAuth()
    return _face_auth
