"""Shared fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture
def data_dirs(tmp_path, monkeypatch):
    """Point every app data/cache directory at a throwaway location.

    Also resets the module-level SQLite connections and in-memory vault
    state so each test starts from a clean slate.
    """
    for var in ("APPDATA", "LOCALAPPDATA", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        monkeypatch.setenv(var, str(tmp_path / var.lower()))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    from telegrab.infra import store as store_mod
    from telegrab.services import localdb
    from telegrab.services import vault as vault_mod

    localdb.reset_for_tests()
    monkeypatch.setattr(vault_mod, "_VAULT_DB", None)
    monkeypatch.setattr(vault_mod, "_vault_db_healthy", True)
    vault_mod._session_keys.clear()
    vault_mod._remote_checked.clear()
    monkeypatch.setattr(store_mod, "_store", None)
    yield tmp_path
    localdb.reset_for_tests()
    vault_mod._zeroize_all_keys()
    if vault_mod._VAULT_DB is not None:
        vault_mod._VAULT_DB.close()
