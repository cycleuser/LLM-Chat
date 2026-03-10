"""Knowledge base configuration for Liao."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_KB_DIR = Path.home() / ".liao" / "kb"


@dataclass
class KBConfig:
    """Configuration for the knowledge base subsystem.

    Attributes:
        embedding_model: Ollama embedding model name
        chunk_size: Size of text chunks for indexing
        chunk_overlap: Overlap between chunks
        min_chunk_size: Minimum chunk size to index
        top_k: Default number of results to retrieve
        docs_dir: Directory for document storage
        chroma_dir: Directory for ChromaDB persistence
        ollama_url: Ollama API URL
        strict_kb_mode: If True, refuse to answer when KB has no results
        kb_scope: List of KB collection names to search (empty = all)
    """

    embedding_model: str = "nomic-embed-text"
    chunk_size: int = 800
    chunk_overlap: int = 150
    min_chunk_size: int = 50
    top_k: int = 10
    docs_dir: str = ""
    chroma_dir: str = ""
    ollama_url: str = "http://localhost:11434"
    strict_kb_mode: bool = False
    kb_scope: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.docs_dir:
            self.docs_dir = str(_DEFAULT_KB_DIR / "docs")
        if not self.chroma_dir:
            self.chroma_dir = str(_DEFAULT_KB_DIR / "chroma")

    @property
    def docs_path(self) -> Path:
        return Path(self.docs_dir)

    @property
    def chroma_path(self) -> Path:
        return Path(self.chroma_dir)

    @property
    def user_kbs_path(self) -> Path:
        """Path to the user KB manifest JSON."""
        return Path(self.docs_dir).parent / "user_kbs.json"


def load_kb_config(path: str | Path | None = None) -> KBConfig:
    """Load KB config from JSON, merging with defaults.

    Args:
        path: Optional custom config file path

    Returns:
        KBConfig instance
    """
    config_path = Path(path) if path else _DEFAULT_KB_DIR / "config.json"
    if config_path.is_file():
        try:
            with open(config_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            # Only pass known fields
            known = {f.name for f in KBConfig.__dataclass_fields__.values()}
            filtered = {k: v for k, v in data.items() if k in known}
            return KBConfig(**filtered)
        except Exception:
            logger.warning("Failed to load KB config from %s, using defaults", config_path)
    return KBConfig()


def save_kb_config(config: KBConfig, path: str | Path | None = None) -> None:
    """Persist KB config to JSON.

    Args:
        config: KBConfig to save
        path: Optional custom config file path
    """
    config_path = Path(path) if path else _DEFAULT_KB_DIR / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as fh:
        json.dump(asdict(config), fh, indent=2, ensure_ascii=False)


# -- User KB manifest helpers --------------------------------------------------


def sanitize_kb_name(name: str) -> str:
    """Convert a user-supplied KB name to a safe ``user_``-prefixed internal name.

    Non-ASCII characters are stripped, spaces/hyphens become underscores,
    and if the result is too short an MD5 hash of the original is used.

    Args:
        name: User-provided KB name

    Returns:
        Sanitized internal name with user_ prefix
    """
    # Remove non-ASCII, keep alphanumeric + space + hyphen
    cleaned = re.sub(r"[^a-zA-Z0-9 \-]", "", name)
    cleaned = re.sub(r"[\s\-]+", "_", cleaned).strip("_").lower()
    if len(cleaned) < 3:
        cleaned = "kb_" + hashlib.md5(name.encode()).hexdigest()[:8]
    return f"user_{cleaned}"


def load_user_kbs(config: KBConfig) -> dict:
    """Load the user KB manifest.  Returns ``{}`` on missing or corrupt file.

    Args:
        config: KBConfig

    Returns:
        Dict of user KB entries
    """
    path = config.user_kbs_path
    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
        except Exception:
            logger.warning("Failed to load user KB manifest from %s", path)
    return {}


def save_user_kb(
    config: KBConfig,
    internal_name: str,
    display_name: str,
    file_count: int,
    languages: list[str] | None = None,
) -> None:
    """Add or update an entry in the user KB manifest.

    Args:
        config: KBConfig
        internal_name: Internal KB identifier
        display_name: Human-readable name
        file_count: Number of files in KB
        languages: List of languages detected
    """
    manifest = load_user_kbs(config)
    manifest[internal_name] = {
        "display_name": display_name,
        "created": manifest.get(internal_name, {}).get(
            "created", datetime.now().isoformat()
        ),
        "file_count": file_count,
        "languages": languages or [],
    }
    path = config.user_kbs_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)


def delete_user_kb_entry(config: KBConfig, internal_name: str) -> bool:
    """Remove an entry from the user KB manifest.  Returns ``True`` if found.

    Args:
        config: KBConfig
        internal_name: Internal KB identifier

    Returns:
        True if entry was deleted
    """
    manifest = load_user_kbs(config)
    if internal_name not in manifest:
        return False
    del manifest[internal_name]
    with open(config.user_kbs_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    return True
