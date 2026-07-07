# =============================================================================
# Configuration constants for J.A.R.V.I.S. API
# =============================================================================

# Upload & File Handling
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_INPUT_LENGTH = 10000  # Characters in chat input
UPLOAD_DIR_PATH = "data/uploads"

# Rate Limiting
MAX_CHAT_REQUESTS_PER_MINUTE = 10
PENDING_ACTION_TTL = 300  # 5 minutes

# Chat Session
DEFAULT_SESSION_TITLE = "Nuova chat"

# Metrics & Monitoring
METRICS_POLLING_INTERVAL = 5000  # milliseconds (frontend)
METRICS_CACHE_TTL = 5  # seconds
TOP_PROCESSES_LIMIT = 5

# Security
BLOCKED_EXTENSIONS = {
    '.env', '.key', '.pem', '.secret', '.db', '.git',
    '.cfg', '.ini', '.sql', '.pwd', '.pass'
}
ALLOWED_EXTENSIONS = {
    '.txt', '.pdf', '.md', '.json', '.csv', '.log',
    '.py', '.js', '.ts', '.jsx', '.tsx',
    '.yaml', '.yml', '.rst', '.html', '.css', '.xml',
    '.toml', '.docx', '.xlsx'
}

# Semantic Cache
SEMANTIC_CACHE_MAX_ENTRIES = 500
SEMANTIC_CACHE_TTL_SECONDS = 3600  # 1 hour

# RAG & Search
RAG_RESULTS_LIMIT = 3
WEB_SEARCH_RESULTS_LIMIT = 5

# Timeouts
CHAT_TIMEOUT_SECONDS = 120
COMMAND_EXECUTION_TIMEOUT = 15

# CORS
ALLOWED_HTTP_METHODS = ["GET", "POST", "OPTIONS", "DELETE", "PATCH"]
ALLOWED_HTTP_HEADERS = ["Content-Type", "Authorization"]
