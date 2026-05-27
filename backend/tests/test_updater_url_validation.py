"""Tests for URL domain validation in the auto-updater."""

import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock webview before importing updater to avoid ModuleNotFoundError
sys.modules.setdefault("webview", MagicMock())

# Load the updater module directly to avoid import chain issues
_updater_path = Path(__file__).resolve().parent.parent / "telegrab" / "services" / "updater.py"
_spec = __import__("importlib").util.spec_from_file_location(
    "telegrab.services.updater", str(_updater_path)
)
_updater_mod = __import__("importlib").util.module_from_spec(_spec)
_spec.loader.exec_module(_updater_mod)

_validate_url_domain = _updater_mod._validate_url_domain
_GitHubOnlyRedirectHandler = _updater_mod._GitHubOnlyRedirectHandler
cmd_download_and_install_update = _updater_mod.cmd_download_and_install_update


class TestValidateUrlDomain:
    """Unit tests for _validate_url_domain."""

    # --- Valid domains ---

    def test_accepts_github_com(self):
        assert _validate_url_domain("https://github.com/user/repo/releases/download/v1.0/file.exe") is True

    def test_accepts_github_com_http(self):
        assert _validate_url_domain("http://github.com/path") is True

    def test_accepts_subdomain_objects(self):
        assert _validate_url_domain("https://objects.githubusercontent.com/path/file.exe") is True

    def test_accepts_subdomain_codeload(self):
        assert _validate_url_domain("https://codeload.github.com/user/repo/tar.gz/v1.0") is True

    def test_accepts_subdomain_api(self):
        assert _validate_url_domain("https://api.github.com/repos/user/repo") is True

    def test_accepts_deep_subdomain(self):
        assert _validate_url_domain("https://a.b.c.github.com/path") is True

    def test_accepts_case_insensitive_github(self):
        assert _validate_url_domain("https://GitHub.COM/user/repo") is True

    def test_accepts_case_insensitive_subdomain(self):
        assert _validate_url_domain("https://Objects.GitHubusercontent.GITHUB.COM/file") is True

    # --- Invalid domains ---

    def test_rejects_evil_github_com(self):
        assert _validate_url_domain("https://evil-github.com/file.exe") is False

    def test_rejects_notgithub_com(self):
        assert _validate_url_domain("https://notgithub.com/file.exe") is False

    def test_rejects_github_com_evil(self):
        assert _validate_url_domain("https://github.com.evil.com/file.exe") is False

    def test_rejects_random_domain(self):
        assert _validate_url_domain("https://example.com/file.exe") is False

    def test_rejects_malicious_lookalike(self):
        assert _validate_url_domain("https://github.co/file.exe") is False

    def test_rejects_empty_string(self):
        assert _validate_url_domain("") is False

    def test_rejects_no_hostname(self):
        assert _validate_url_domain("file:///etc/passwd") is False

    def test_rejects_relative_path(self):
        assert _validate_url_domain("/path/to/file") is False

    def test_rejects_just_path(self):
        assert _validate_url_domain("path/to/file") is False

    def test_rejects_localhost(self):
        assert _validate_url_domain("http://localhost/file.exe") is False

    def test_rejects_ip_address(self):
        assert _validate_url_domain("http://192.168.1.1/file.exe") is False

    def test_rejects_github_com_as_subdomain_of_other(self):
        # github.com.attacker.com should NOT pass
        assert _validate_url_domain("https://github.com.attacker.com/file") is False

    def test_rejects_suffix_attack(self):
        # fakegithub.com should NOT pass
        assert _validate_url_domain("https://fakegithub.com/file") is False


class TestGitHubOnlyRedirectHandler:
    """Tests for the redirect handler that rejects non-GitHub redirects."""

    def test_allows_redirect_to_github(self):
        handler = _GitHubOnlyRedirectHandler()
        req = MagicMock()
        req.get_method.return_value = "GET"
        req.full_url = "https://github.com/original"
        result = handler.redirect_request(
            req, None, 302, "Found", {}, "https://objects.githubusercontent.com/file"
        )
        assert result is not None

    def test_rejects_redirect_to_non_github(self):
        handler = _GitHubOnlyRedirectHandler()
        req = MagicMock()
        req.get_method.return_value = "GET"
        req.full_url = "https://github.com/original"
        with pytest.raises(urllib.error.URLError, match="non-GitHub domain rejected"):
            handler.redirect_request(
                req, None, 302, "Found", {}, "https://evil.com/file.exe"
            )


class TestDownloadUrlValidationIntegration:
    """Integration tests for URL validation in cmd_download_and_install_update."""

    def test_rejects_non_github_download_url(self):
        with pytest.raises(ValueError, match="hostname is not github.com"):
            cmd_download_and_install_update("https://evil.com/malware.exe", expected_sha256="a" * 64)

    def test_rejects_empty_download_url(self):
        with pytest.raises(ValueError, match="No download URL provided"):
            cmd_download_and_install_update("")

    def test_aborts_when_no_checksum_provided(self):
        """Verify that missing checksum aborts before domain validation."""
        with pytest.raises(RuntimeError, match="no SHA-256 checksum found"):
            cmd_download_and_install_update(
                "https://github.com/user/repo/releases/download/v1.0/file.exe"
            )

    @patch("shutil.disk_usage")
    def test_accepts_github_url_passes_domain_check(self, mock_disk):
        """Verify that a valid github.com URL passes domain validation.

        The function will proceed past domain validation but may fail on
        disk space or network — we just ensure it doesn't reject the domain.
        """
        # Make it fail on disk space check (which happens after domain validation)
        mock_disk.return_value = MagicMock(free=100)  # Less than 200MB

        with pytest.raises(RuntimeError, match="Insufficient disk space"):
            cmd_download_and_install_update(
                "https://github.com/user/repo/releases/download/v1.0/file.exe",
                expected_sha256="a" * 64,
            )
