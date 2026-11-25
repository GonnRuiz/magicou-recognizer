"""Public Python interface for Magicou Recognizer.

Importing the package does not download assets or load a model. The internal
``arcana`` package remains available for compatibility with existing integrations.
"""
from arcana.recognizer import FooterOCR, Recognizer
from arcana.scryfall import prices as get_price

__version__ = "0.3.0"
__all__ = ["Recognizer", "FooterOCR", "get_price", "__version__"]
