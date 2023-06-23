from __future__ import annotations

try:
    import importlib.metadata as importlib_metadata

    __version__ = importlib_metadata.version("pytest-dir-equal")
except Exception:
    __version__ = "0.0.0.dev"
