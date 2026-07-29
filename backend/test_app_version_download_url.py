import unittest
from unittest.mock import patch

from starlette.requests import Request

from app.api.app_version import _resolve_download_url


def make_request(scheme: str, host: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": scheme,
            "server": (host, 443 if scheme == "https" else 80),
            "path": "/api/app-version/check",
            "root_path": "",
            "query_string": b"",
            "headers": [(b"host", host.encode("ascii"))],
        }
    )


class AppVersionDownloadUrlTest(unittest.TestCase):
    def test_relative_path_uses_request_server(self):
        request = make_request(
            "https",
            "siteapp.indonesiacentral.cloudapp.azure.com",
        )

        result = _resolve_download_url(
            request,
            "/uploads/apk/app_20260606_140049.apk",
        )

        self.assertEqual(
            result,
            "https://siteapp.indonesiacentral.cloudapp.azure.com/"
            "uploads/apk/app_20260606_140049.apk",
        )

    def test_absolute_download_url_is_preserved(self):
        request = make_request("https", "siteapp.savannafibre.com")

        result = _resolve_download_url(
            request,
            "https://cdn.example.com/releases/site-app.apk",
        )

        self.assertEqual(result, "https://cdn.example.com/releases/site-app.apk")

    def test_configured_public_base_url_overrides_internal_http_scheme(self):
        request = make_request("http", "siteapp.savannafibre.com")

        with patch(
            "app.api.app_version.settings.APP_PUBLIC_BASE_URL",
            "https://siteapp.savannafibre.com",
        ):
            result = _resolve_download_url(
                request,
                "/uploads/apk/app_20260606_170131.apk",
            )

        self.assertEqual(
            result,
            "https://siteapp.savannafibre.com/"
            "uploads/apk/app_20260606_170131.apk",
        )

    def test_scheme_relative_path_cannot_replace_request_server(self):
        request = make_request("https", "siteapp.savannafibre.com")

        result = _resolve_download_url(request, "//other.example.com/app.apk")

        self.assertEqual(
            result,
            "https://siteapp.savannafibre.com/other.example.com/app.apk",
        )


if __name__ == "__main__":
    unittest.main()
