import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from .auth import get_current_user
from fastapi.responses import StreamingResponse

import skills
from .constants import MAX_CHAT_REQUESTS_PER_MINUTE, MAX_INPUT_LENGTH
from .dependencies import get_config, get_brain, get_speech, get_actions, get_memory, new_context, get_chat_manager
from .routes_common import (
    _check_rate_limit, _pending_actions, _is_dangerous,
    _cleanup_expired_actions, _push_log, _sse_events, _abort_response,
    FEEDBACK_FILE,
)
from .schemas import ChatRequest, ChatResponse, ConfirmRequest, FeedbackRequest, RenameSessionRequest, BatchRequest, BatchStepResult

logger = logging.getLogger("jarvis.api.routes")

router = APIRouter()


@router.post("/chat")
async def chat_text(payload: ChatRequest, request: Request = None, user: dict = Depends(get_current_user)):
    # ── Rate limiting
    client_ip = request.client.host if request else "unknown"
    if not await _check_rate_limit(client_ip):
        logger.warning(f"Rate limit exceeded for {client_ip}")
        raise HTTPException(status_code=429, detail=f"Rate limit: max {MAX_CHAT_REQUESTS_PER_MINUTE} requests/minute")

    config = get_config()
    text = payload.text.strip()
    file_content = payload.file_content
    session_id = payload.session_id

    if not text and not file_content:
        r = ChatResponse(response="No input provided.", intent="none", language="it", audio=None, session_id=session_id)
        if payload.stream:
            return StreamingResponse(_sse_events(r), media_type="text/event-stream")
        return r

    # ── Input length validation
    combined_length = len(text) + len(file_content)
    if combined_length > MAX_INPUT_LENGTH:
        raise HTTPException(
            status_code=413,
            detail=f"Input too long: {combined_length} chars (max {MAX_INPUT_LENGTH})"
        )

    if file_content:
        text = f"{text}\n\n[File content]:\n{file_content}" if text else f"[File content]:\n{file_content}"

    # ── Chat session handling ────────────────────────────────────────────────
    chat_mgr = get_chat_manager(user_id=user["user_id"])
    if session_id is not None:
        existing = chat_mgr.get_session(session_id)
        if not existing:
            session_id = None

    if session_id is None:
        session = chat_mgr.create_session()
        session_id = session["id"]

    chat_mgr.add_message(session_id, "user", payload.text.strip() or "[file]", "")

    llm, intent_router, multiagent = get_brain(config)
    context = new_context()
    actions = get_actions(config)
    speech = get_speech(config)
    _, persistent_memory = get_memory(config)

    if request and await request.is_disconnected():
        return _abort_response(session_id, payload.stream)

    lang = llm.detect_language(text)
    context.set_language(lang)
    original_query = text

    memories = persistent_memory.search(text, n_results=3)
    if memories:
        memory_context = "\n".join(f"Related memory: {m['text']}" for m in memories)
        prompt = f"{text}\n\n{memory_context}"
    else:
        prompt = text

    if request and await request.is_disconnected():
        return _abort_response(session_id, payload.stream)

    intent = intent_router.route(original_query)

    if intent in ("git", "terminal", "rpa", "productivity", "system_control", "media_player", "web_search"):
        if intent == "git":
            repo_path = persistent_memory.get_preference("cartella_progetti")
            response = await actions["git"].execute(original_query, repo_path=repo_path)
            _push_log("info", f"Git: {original_query[:60]}")
        elif intent == "web_search":
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: skills.execute("web_search", query=original_query))
                response = f"🔍 Risultati ricerca per '{original_query}':\n{result}"
            except Exception as e:
                logger.warning(f"Web search via skills failed, falling back: {e}")
                web_result, _ = multiagent._web_searcher.search(original_query)
                response = f"🔍 Risultati ricerca:\n{web_result}" if web_result else "Nessun risultato trovato."
        else:
            dangerous_key = _is_dangerous(original_query) if intent == "system_control" else None
            if dangerous_key:
                action_id = str(uuid.uuid4())
                _pending_actions[action_id] = {
                    "command": original_query,
                    "intent": intent,
                    "label": dangerous_key,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                r = ChatResponse(
                    response=f"⚠️ Richiesta azione pericolosa: `{dangerous_key}`. Attendo conferma.",
                    intent=intent, language=lang, audio=None,
                    session_id=session_id, pending_action=action_id,
                )
                if payload.stream:
                    return StreamingResponse(_sse_events(r), media_type="text/event-stream")
                return r

            try:
                response = await actions[intent].execute(original_query, session_key=str(session_id))
            except Exception as e:
                logger.error(f"Intent execution error ({intent}): {e}")
                response = "[Errore durante l'esecuzione del comando]"

        if request and await request.is_disconnected():
            return _abort_response(session_id, payload.stream)

        context.add_turn("user", original_query)
        context.add_turn("assistant", response)
        persistent_memory.store(original_query, metadata={"role": "user", "intent": intent})
        persistent_memory.store(response, metadata={"role": "assistant", "intent": intent})
        chat_mgr.add_message(session_id, "assistant", response, intent)
        chat_mgr.auto_title(session_id)

        r = ChatResponse(response=response, intent=intent, language=lang, audio=None, session_id=session_id)
        if payload.stream:
            return StreamingResponse(_sse_events(r), media_type="text/event-stream")
        return r

    # ── Streaming LLM response ───────────────────────────────────────────────
    if payload.stream:
        async def stream_events():
            full_response = ""
            cancelled = False
            try:
                for token in multiagent.chat_stream(prompt, context.get_context(), language=lang, intent=intent, search_query=original_query):
                    full_response += token
                    if request and await request.is_disconnected():
                        cancelled = True
                        logger.info("Stream cancelled by client during generation")
                        break
                    yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"
                if cancelled:
                    yield f"data: {json.dumps({'type': 'done', 'response': full_response, 'intent': intent, 'language': lang, 'session_id': session_id, 'sources': []})}\n\n"
                    return
            except asyncio.CancelledError:
                cancelled = True
                logger.info("Stream cancelled via CancelledError")
                full_response = full_response or "[Richiesta interrotta]"
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                full_response = full_response or "[Errore durante lo streaming della risposta]"
            sources = getattr(multiagent, 'last_sources', [])
            done = {'type': 'done', 'response': full_response or "[Nessuna risposta]", 'intent': intent, 'language': lang, 'session_id': session_id, 'sources': sources}
            yield f"data: {json.dumps(done)}\n\n"

            context.add_turn("user", original_query)
            context.add_turn("assistant", full_response)
            persistent_memory.store(original_query, metadata={"role": "user", "intent": intent})
            persistent_memory.store(full_response, metadata={"role": "assistant", "intent": intent})
            chat_mgr.add_message(session_id, "assistant", full_response, intent)
            chat_mgr.auto_title(session_id)

        return StreamingResponse(stream_events(), media_type="text/event-stream")

    # ── Non-streaming LLM response ───────────────────────────────────────────
    try:
        response = multiagent.chat(
            prompt, context.get_context(),
            language=lang, intent=intent,
            search_query=original_query,
        )
    except Exception as e:
        logger.error(f"LLM chat error: {e}")
        response = "[Errore durante l'elaborazione della richiesta]"

    if request and await request.is_disconnected():
        return _abort_response(session_id, payload.stream)

    context.add_turn("user", original_query)
    context.add_turn("assistant", response)
    persistent_memory.store(original_query, metadata={"role": "user", "intent": intent})
    persistent_memory.store(response, metadata={"role": "assistant", "intent": intent})
    chat_mgr.add_message(session_id, "assistant", response, intent)
    chat_mgr.auto_title(session_id)

    return ChatResponse(response=response, intent=intent, language=lang, audio=None, session_id=session_id, sources=multiagent.last_sources)


@router.post("/confirm")
async def confirm_action(payload: ConfirmRequest, user: dict = Depends(get_current_user)):
    _cleanup_expired_actions()  # Clean up before checking

    action = _pending_actions.get(payload.action_id)
    if not action:
        return {"status": "error", "message": "Action not found or expired"}

    if payload.confirm:
        config = get_config()
        actions = get_actions(config)
        intent = action["intent"]
        if intent in actions:
            result = await actions[intent].execute(action["command"], session_key=str(user["user_id"]))
            del _pending_actions[payload.action_id]
            logger.info(f"Action confirmed: {payload.action_id}")
            return {"status": "ok", "result": result, "action": payload.action_id}
        return {"status": "error", "message": f"Action handler '{intent}' not found"}
    else:
        cmd = _pending_actions.pop(payload.action_id, None)
        logger.info(f"Action cancelled: {payload.action_id}")
        return {"status": "cancelled", "message": f"Action cancelled: {cmd['command'] if cmd else '?'}"}


@router.post("/feedback")
async def submit_feedback(fb: FeedbackRequest, user: dict = Depends(get_current_user)):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message_id": fb.message_id,
        "user_message": fb.user_message,
        "assistant_response": fb.assistant_response,
        "rating": fb.rating,
        "language": fb.language,
        "intent": fb.intent,
    }
    try:
        with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info(f"Feedback: rating={fb.rating}, lang={fb.language}, intent={fb.intent}")
        return {"status": "saved", "rating": fb.rating}
    except Exception as e:
        logger.error(f"Feedback save failed: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.get("/chats")
async def list_chat_sessions(user: dict = Depends(get_current_user)):
    chat_mgr = get_chat_manager(user_id=user["user_id"])
    return {"sessions": chat_mgr.list_sessions()}


@router.get("/chats/{session_id}")
async def get_chat_session(session_id: int, user: dict = Depends(get_current_user)):
    chat_mgr = get_chat_manager(user_id=user["user_id"])
    session = chat_mgr.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": session}


@router.post("/chats")
async def create_chat_session(user: dict = Depends(get_current_user)):
    chat_mgr = get_chat_manager(user_id=user["user_id"])
    session = chat_mgr.create_session()
    return {"session": session}


@router.delete("/chats/{session_id}")
async def delete_chat_session(session_id: int, user: dict = Depends(get_current_user)):
    chat_mgr = get_chat_manager(user_id=user["user_id"])
    ok = chat_mgr.delete_session(session_id)
    return {"status": "deleted" if ok else "not_found"}


@router.patch("/chats/{session_id}")
async def rename_chat_session(session_id: int, payload: RenameSessionRequest, user: dict = Depends(get_current_user)):
    chat_mgr = get_chat_manager(user_id=user["user_id"])
    ok = chat_mgr.rename_session(session_id, payload.title)
    return {"status": "renamed" if ok else "not_found"}


@router.get("/chats/{session_id}/messages")
async def get_chat_messages(session_id: int, user: dict = Depends(get_current_user)):
    chat_mgr = get_chat_manager(user_id=user["user_id"])
    messages = chat_mgr.get_messages(session_id)
    return {"messages": messages}


@router.post("/batch")
async def run_batch(body: BatchRequest, request: Request = None, user: dict = Depends(get_current_user)):
    results = []
    for i, step in enumerate(body.steps):
        try:
            if step.type == "wait":
                await asyncio.sleep(step.wait_seconds)
                results.append(BatchStepResult(step=i, type=step.type, input=step.input, output=f"waited {step.wait_seconds}s", status="ok"))
            elif step.type == "command":
                import subprocess
                r = subprocess.run(step.input, shell=True, capture_output=True, text=True, timeout=30)
                out = r.stdout[:500] or r.stderr[:500]
                results.append(BatchStepResult(step=i, type=step.type, input=step.input, output=out, status="ok" if r.returncode == 0 else "error"))
            else:
                from .dependencies import get_brain, get_config
                cfg = get_config()
                llm, _, ma = get_brain(cfg)
                resp, _ = llm.chat(step.input)
                results.append(BatchStepResult(step=i, type=step.type, input=step.input, output=resp[:500], status="ok"))
        except Exception as e:
            results.append(BatchStepResult(step=i, type=step.type, input=step.input, output=str(e), status="error"))
            break
    return {"results": [r.model_dump() for r in results]}
