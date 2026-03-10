"""KB helper functions for cross-lingual retrieval."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from liao.knowledge.kb_manager import KBManager
    from liao.llm.base import BaseLLMClient

logger = logging.getLogger(__name__)


def detect_language(llm_client: "BaseLLMClient", text_sample: str) -> str:
    """Detect the language of a text sample using the LLM.

    Args:
        llm_client: Connected LLM client
        text_sample: Text to detect language of (ideally 100-500 chars)

    Returns:
        Language name in English (e.g., "Chinese", "English", "Japanese").
        Returns "English" as fallback on error.
    """
    if not text_sample or not text_sample.strip():
        return "English"

    try:
        response = llm_client.chat(
            [
                {
                    "role": "system",
                    "content": "You are a language detector. Reply with ONLY the language name in English, nothing else.",
                },
                {
                    "role": "user",
                    "content": f"What language is this text written in? Reply with ONLY the language name (e.g., 'Chinese', 'English', 'Japanese'):\n\n{text_sample[:500]}",
                },
            ],
            temperature=0.0,
        )
        lang = response.strip().strip("'\"").strip()
        if lang:
            logger.info(f"Detected language: {lang}")
            return lang
    except Exception as e:
        logger.warning(f"Language detection failed: {e}")

    return "English"


def translate_text(
    llm_client: "BaseLLMClient",
    text: str,
    source_lang: str,
    target_lang: str,
) -> str:
    """Translate text using the LLM.

    Args:
        llm_client: Connected LLM client
        text: Text to translate
        source_lang: Source language name
        target_lang: Target language name

    Returns:
        Translated text. Returns original text on error.
    """
    if not text or not text.strip():
        return text
    if source_lang.lower() == target_lang.lower():
        return text

    try:
        response = llm_client.chat(
            [
                {
                    "role": "system",
                    "content": "You are a translator. Output ONLY the translation, nothing else. No explanations, no notes.",
                },
                {
                    "role": "user",
                    "content": f"Translate the following from {source_lang} to {target_lang}. Output ONLY the translation:\n\n{text}",
                },
            ],
            temperature=0.1,
        )
        translated = response.strip()
        if translated:
            return translated
    except Exception as e:
        logger.warning(f"Translation failed ({source_lang} -> {target_lang}): {e}")

    return text


def sample_kb_documents(
    kb_manager: "KBManager",
    collections: list[str] | None = None,
    sample_count: int = 3,
) -> str:
    """Sample documents from KB collections for language detection.

    Args:
        kb_manager: Initialized KBManager
        collections: Specific collections to sample from (None = all)
        sample_count: Number of documents to sample

    Returns:
        Concatenated sample text (truncated to ~500 chars). Empty string on error.
    """
    try:
        if not kb_manager.retriever.is_available:
            return ""

        coll_names = collections
        if not coll_names:
            coll_names = kb_manager.retriever.list_collections()
        if not coll_names:
            return ""

        # Sample from the first available collection
        for coll_name in coll_names:
            try:
                coll = kb_manager.retriever.client.get_collection(coll_name)
                results = coll.peek(limit=sample_count)
                if results and results.get("documents"):
                    docs = results["documents"]
                    sample = "\n".join(d[:200] for d in docs if d)
                    return sample[:500]
            except Exception as e:
                logger.debug(f"Failed to sample from {coll_name}: {e}")
                continue

    except Exception as e:
        logger.warning(f"KB document sampling failed: {e}")

    return ""


def languages_differ(lang_a: str, lang_b: str) -> bool:
    """Check if two language names refer to different languages.

    Handles common aliases like "Chinese"/"Mandarin", "English"/"EN".
    """
    if not lang_a or not lang_b:
        return False

    a = lang_a.lower().strip()
    b = lang_b.lower().strip()

    # Normalize common aliases
    aliases = {
        "chinese": "chinese",
        "mandarin": "chinese",
        "zh": "chinese",
        "english": "english",
        "en": "english",
        "japanese": "japanese",
        "ja": "japanese",
        "korean": "korean",
        "ko": "korean",
    }

    a_norm = aliases.get(a, a)
    b_norm = aliases.get(b, b)

    return a_norm != b_norm
