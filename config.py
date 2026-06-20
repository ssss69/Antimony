import json
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"

DEFAULT_CONFIG = {
    "default_persona": "soren",
    "use_openai": False,
    "use_ollama": True,
    "safe_mode": True,
    "require_permission_for_risky_tools": True,
    "model": "gpt-4o-mini",
    "ollama_model": "llama3.2:latest",
    "ollama_timeout": 180,
    "ollama_max_tokens": 700,
    "auto_ingest_files": True,
    "auto_save_chats": True,
    "auto_summarize_memories": True,
    "auto_search_before_answering": True,
    "auto_learn_corrections": True,
    "memory_summary_interval": 8,
    "public_search_limit": 2,
}


def load_config():
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_CONFIG)
    merged = dict(DEFAULT_CONFIG)
    merged.update({key: value for key, value in data.items() if key in DEFAULT_CONFIG})
    return merged


def save_config(config):
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
