"""Compatibility imports; new integrations should use magicou_recognizer."""
from magicou_recognizer import FooterOCR, Recognizer, __version__, get_price

__all__ = ["Recognizer", "FooterOCR", "get_price", "__version__"]
