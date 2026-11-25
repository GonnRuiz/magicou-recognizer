"""Process configuration, with compatibility for the original environment names."""
import os


def setting(name, default=None):
    return os.environ.get("MAGICOU_RECOGNIZER_" + name,
                          os.environ.get("MAGIC_RECOGNIZER_" + name,
                                         os.environ.get("ARCANA_" + name, default)))
