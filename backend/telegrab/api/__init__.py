"""External interfaces — pywebview JS bridge + FastAPI servers."""

from . import host
from .bridge import Bridge
from .rest import RestApiSupervisor
from .streaming import serve_streaming

__all__ = ["Bridge", "RestApiSupervisor", "serve_streaming", "host"]
