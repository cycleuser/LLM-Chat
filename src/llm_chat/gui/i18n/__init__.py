"""Internationalization (i18n) support for vision-gui-agent GUI."""

from .translator import Translator, get_translator, set_locale, tr

__all__ = [
    "Translator",
    "get_translator",
    "set_locale",
    "tr",
]
