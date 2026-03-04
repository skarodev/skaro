"""Skaro Core — Spec-Guided Development engine."""

try:
    from importlib.metadata import version as _pkg_version

    __version__: str = _pkg_version("skaro")
except Exception:
    __version__ = "0.0.0-dev"
