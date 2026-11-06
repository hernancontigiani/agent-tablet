"""The names in a session file: the statusline script writes them, the app's context model reads
them. Standard library only and free of package imports, because the script loads this module
from its own directory, outside the app."""

SESSION_FIELDS = (
    "session_id",
    "session_name",
    "transcript_path",
    "cwd",
    "model",
    "percentage",
    "window",
    "input_tokens",
    "updated_at",
)
