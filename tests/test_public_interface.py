import subprocess
import sys

from arcana.config import setting


def test_new_configuration_names_override_legacy_names(monkeypatch):
    monkeypatch.delenv("MAGICOU_RECOGNIZER_API_KEY", raising=False)
    monkeypatch.delenv("MAGIC_RECOGNIZER_API_KEY", raising=False)
    monkeypatch.delenv("ARCANA_API_KEY", raising=False)
    assert setting("API_KEY", "fallback") == "fallback"
    monkeypatch.setenv("ARCANA_API_KEY", "legacy-test-value")
    assert setting("API_KEY") == "legacy-test-value"
    monkeypatch.setenv("MAGIC_RECOGNIZER_API_KEY", "previous-test-value")
    assert setting("API_KEY") == "previous-test-value"
    monkeypatch.setenv("MAGICOU_RECOGNIZER_API_KEY", "preferred-test-value")
    assert setting("API_KEY") == "preferred-test-value"
    monkeypatch.setenv("MAGICOU_RECOGNIZER_API_KEY", "")
    assert setting("API_KEY") == ""


def test_public_imports_preserve_existing_class_identity():
    from magicou_recognizer import Recognizer, get_price
    from arcana.recognizer import Recognizer as LegacyRecognizer
    from arcana.scryfall import prices
    assert Recognizer is LegacyRecognizer
    assert get_price is prices
    from magic_recognizer import Recognizer as PreviousRecognizer
    assert Recognizer is PreviousRecognizer


def test_module_cli_version():
    result = subprocess.run(
        [sys.executable, "-m", "magicou_recognizer", "--version"],
        capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == "magicou-recognizer 0.3.0"
