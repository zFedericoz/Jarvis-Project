from pydantic import BaseModel


class ChatRequest(BaseModel):
    text: str = ""
    file_content: str = ""
    session_id: int | None = None
    stream: bool = False


class ChatResponse(BaseModel):
    response: str
    intent: str
    language: str
    audio: str | None = None
    session_id: int | None = None
    sources: list[dict] = []
    pending_action: str | None = None


class PendingActionInfo(BaseModel):
    id: str
    label: str
    description: str
    dangerous: bool = True


class ConfirmRequest(BaseModel):
    action_id: str
    confirm: bool


class StatusResponse(BaseModel):
    status: str
    version: str
    name: str
    llm: str


class UploadResponse(BaseModel):
    filename: str
    size: int
    content: str


class FeedbackRequest(BaseModel):
    message_id: str = ""
    user_message: str
    assistant_response: str
    rating: int
    language: str = "it"
    intent: str = "chat"


class GitRequest(BaseModel):
    command: str
    repo_path: str | None = None


class TerminalRequest(BaseModel):
    command: str
    cwd: str | None = None


class FocusStartRequest(BaseModel):
    duration_minutes: int | None = None


class FocusSiteRequest(BaseModel):
    site: str


class RenameSessionRequest(BaseModel):
    title: str


class RPAClickRequest(BaseModel):
    x: int
    y: int
    button: str = "left"
    clicks: int = 1


class RPATypeRequest(BaseModel):
    text: str
    interval: float = 0.03


class RPAHotkeyRequest(BaseModel):
    keys: list[str]


class RPAOpenAppRequest(BaseModel):
    app: str


class RPAOpenFileRequest(BaseModel):
    path: str
    app: str | None = None


class RPAScrollRequest(BaseModel):
    direction: str = "down"
    clicks: int = 3


class RPADragRequest(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int


class RPACommandRequest(BaseModel):
    command: str


class RagThresholdRequest(BaseModel):
    threshold: float


class ExportMessage(BaseModel):
    role: str
    text: str


class ExportRequest(BaseModel):
    messages: list[ExportMessage]
    format: str = "pdf"


class VoiceSettingsRequest(BaseModel):
    wake_word_enabled: bool | None = None
    wake_word_sensitivity: float | None = None
    stt_model: str | None = None
    stt_language: str | None = None
    tts_engine: str | None = None
    tts_speed: float | None = None


class BatchStep(BaseModel):
    type: str  # "chat", "command", "wait"
    input: str = ""
    wait_seconds: float = 0


class BatchRequest(BaseModel):
    steps: list[BatchStep]


class BatchStepResult(BaseModel):
    step: int
    type: str
    input: str
    output: str
    status: str  # "ok", "error"
