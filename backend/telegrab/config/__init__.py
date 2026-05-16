"""Configuration values & on-disk paths.

Pure data — no business logic, no I/O beyond reading/writing settings files.
"""

from .api_settings import (
    DEFAULT_API_PORT,
    ApiSettingsFile,
    hash_key,
    load_settings,
    save_settings,
    verify_key,
)
from .paths import (
    APP_NAME,
    api_settings_path,
    app_cache_dir,
    app_data_dir,
    bandwidth_path,
    preview_cache_dir,
    session_path,
    store_path,
    thumbnail_cache_dir,
)
from .stream import STREAM_PORT, StreamConfig, get_stream_config

__all__ = [
    # paths
    "APP_NAME",
    "app_data_dir",
    "app_cache_dir",
    "session_path",
    "bandwidth_path",
    "api_settings_path",
    "store_path",
    "preview_cache_dir",
    "thumbnail_cache_dir",
    # stream
    "STREAM_PORT",
    "StreamConfig",
    "get_stream_config",
    # api settings
    "DEFAULT_API_PORT",
    "ApiSettingsFile",
    "hash_key",
    "verify_key",
    "load_settings",
    "save_settings",
]
