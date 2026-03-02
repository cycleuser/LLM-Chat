"""Internationalization (i18n) translator."""

from __future__ import annotations

import json
import locale
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Translation files directory
I18N_DIR = Path(__file__).parent

# Global translator instance
_global_translator: "Translator | None" = None


class Translator:
    """Translator for bilingual UI support.
    
    Loads translations from JSON files and provides translation lookup.
    
    Example:
        tr = Translator(locale="en_US")
        label = tr.tr("connection.connect")  # Returns "Connect"
        
        tr.set_locale("zh_CN")
        label = tr.tr("connection.connect")  # Returns "连接"
    """

    def __init__(self, locale_code: str | None = None):
        """Initialize translator.
        
        Args:
            locale_code: Locale code (e.g., "en_US", "zh_CN"). Auto-detected if None.
        """
        self._translations: dict[str, Any] = {}
        self._fallback: dict[str, Any] = {}
        self._locale = locale_code or self._detect_locale()
        self._load_translations()

    @staticmethod
    def _detect_locale() -> str:
        """Detect system locale."""
        try:
            loc, _ = locale.getdefaultlocale()
            if loc and loc.startswith("zh"):
                return "zh_CN"
        except Exception:
            pass
        return "en_US"

    def _load_translations(self) -> None:
        """Load translation files."""
        # Load fallback (English)
        en_file = I18N_DIR / "en_US.json"
        if en_file.exists():
            try:
                with open(en_file, "r", encoding="utf-8") as f:
                    self._fallback = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load en_US.json: {e}")
        
        # Load target locale
        locale_file = I18N_DIR / f"{self._locale}.json"
        if locale_file.exists():
            try:
                with open(locale_file, "r", encoding="utf-8") as f:
                    self._translations = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load {self._locale}.json: {e}")
        else:
            self._translations = self._fallback

    @property
    def locale(self) -> str:
        """Get current locale code."""
        return self._locale

    def set_locale(self, locale_code: str) -> None:
        """Set locale and reload translations.
        
        Args:
            locale_code: New locale code
        """
        self._locale = locale_code
        self._load_translations()

    def tr(self, key: str, **kwargs: Any) -> str:
        """Translate a key.
        
        Args:
            key: Translation key (e.g., "connection.connect")
            **kwargs: Format arguments
            
        Returns:
            Translated string
        """
        # Navigate nested keys
        value = self._get_nested(self._translations, key)
        if value is None:
            value = self._get_nested(self._fallback, key)
        if value is None:
            return key
        
        # Apply format arguments
        if kwargs:
            try:
                return value.format(**kwargs)
            except (KeyError, ValueError):
                return value
        return value

    @staticmethod
    def _get_nested(data: dict, key: str) -> str | None:
        """Get nested dictionary value by dot-separated key."""
        keys = key.split(".")
        current = data
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None
        return current if isinstance(current, str) else None

    def get_available_locales(self) -> list[str]:
        """Get list of available locales.
        
        Returns:
            List of locale codes
        """
        locales = []
        for f in I18N_DIR.glob("*.json"):
            locales.append(f.stem)
        return sorted(locales)


def get_translator() -> Translator:
    """Get the global translator instance.
    
    Returns:
        Global Translator instance
    """
    global _global_translator
    if _global_translator is None:
        _global_translator = Translator()
    return _global_translator


def set_locale(locale_code: str) -> None:
    """Set locale for the global translator.
    
    Args:
        locale_code: Locale code
    """
    get_translator().set_locale(locale_code)


def tr(key: str, **kwargs: Any) -> str:
    """Translate a key using the global translator.
    
    Args:
        key: Translation key
        **kwargs: Format arguments
        
    Returns:
        Translated string
    """
    return get_translator().tr(key, **kwargs)
