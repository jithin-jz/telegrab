"""External interfaces — pywebview JS bridge + streaming protocol."""

from . import host
from .bridge import Bridge
from .streaming import serve_streaming

__all__ = ["Bridge", "serve_streaming", "host"]
