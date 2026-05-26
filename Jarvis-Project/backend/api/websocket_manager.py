import asyncio
import logging
import numpy as np
from fastapi import WebSocket
from wake_word.processor import WakeWordProcessor

logger = logging.getLogger("jarvis.api.ws")

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.info(f"Client connected ({len(self.active)} total)")

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)

    async def send_audio(self, ws: WebSocket, audio_data: bytes):
        await ws.send_bytes(audio_data)

manager = ConnectionManager()

async def handle_wake_word(ws: WebSocket, config: dict):
    ww_config = config["speech"]["wake_word"]
    processor = WakeWordProcessor(
        keyword=ww_config["keyword"],
        sensitivity=ww_config["sensitivity"],
    )

    frame_size = processor.frame_length
    buffer = bytearray()

    try:
        while True:
            data = await ws.receive_bytes()
            buffer.extend(data)

            while len(buffer) >= frame_size * 2:
                chunk = bytes(buffer[:frame_size * 2])
                buffer = buffer[frame_size * 2:]

                audio = np.frombuffer(chunk, dtype=np.int16)
                if processor.process(audio):
                    logger.info("Wake word detected via browser audio")
                    await ws.send_json({"type": "wake"})
    except Exception as e:
        logger.debug(f"Wake word connection closed: {e}")
    finally:
        processor.delete()

async def handle_audio_stream(ws: WebSocket, stt, brain, router, context, actions, tts):
    buffer = bytearray()
    while True:
        try:
            data = await ws.receive_bytes()
            buffer.extend(data)

            if len(buffer) > 32000:
                audio_np = np.frombuffer(buffer, dtype=np.int16).astype(np.float32) / 32768.0
                buffer.clear()

                text, lang = stt.transcribe(audio_np)

                if not text:
                    await ws.send_json({"type": "idle"})
                    continue

                context.set_language(lang)
                context.add_turn("user", text)

                await ws.send_json({
                    "type": "transcription",
                    "text": text,
                    "language": lang,
                })

                intent = router.route(text)
                if intent in actions:
                    response = await actions[intent].execute(text)
                else:
                    response = brain.chat(text, context.get_context())

                context.add_turn("assistant", response)

                await ws.send_json({
                    "type": "response",
                    "text": response,
                    "intent": intent,
                    "language": lang,
                })

                await ws.send_json({"type": "speaking_start"})
                audio_bytes = await tts.synthesize_async(response, language=lang)
                if audio_bytes:
                    await ws.send_bytes(audio_bytes)
                await ws.send_json({"type": "speaking_end"})
                await ws.send_json({"type": "idle"})

        except Exception as e:
            logger.error(f"Audio stream error: {e}")
            break
