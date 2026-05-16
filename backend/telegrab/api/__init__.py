"""External interfaces — pywebview JS bridge + FastAPI servers."""

from .bridge import Bridge
from .rest import RestApiSupervisor
from .streaming import serve_streaming
from . import host

__all__ = ["Bridge", "RestApiSupervisor", "serve_streaming", "host"]
