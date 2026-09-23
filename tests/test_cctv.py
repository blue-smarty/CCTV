import base64
import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from cctv import SwannClient, SwannConfig, build_basic_auth_header, main, parse_port


class SwannClientTests(unittest.TestCase):
    def test_base_url_with_http_and_https(self):
        self.assertEqual(SwannConfig(host="cam.local").base_url, "http://cam.local")
        self.assertEqual(SwannConfig(host="cam.local", https=True, port=8443).base_url, "https://cam.local:8443")

    def test_basic_auth_header(self):
        header = build_basic_auth_header("admin", "secret")
        expected = base64.b64encode(b"admin:secret").decode("ascii")
        self.assertEqual(header, f"Basic {expected}")
        self.assertIsNone(build_basic_auth_header(None, "secret"))

    def test_snapshot_url(self):
        client = SwannClient(SwannConfig(host="10.0.0.10"))
        self.assertEqual(
            client.snapshot_url(channel=2),
            "http://10.0.0.10/cgi-bin/snapshot.cgi?channel=2",
        )
        self.assertEqual(
            client.snapshot_url(channel=2, path="cgi-bin/snapshot.cgi"),
            "http://10.0.0.10/cgi-bin/snapshot.cgi?channel=2",
        )

    @patch("cctv.request.urlopen")
    def test_request_adds_auth_header(self, mock_urlopen):
        mock_response = mock_urlopen.return_value.__enter__.return_value
        mock_response.read.return_value = b"ok"

        client = SwannClient(SwannConfig("cam.local", "u", "p"))
        body = client.request(path="/api/status")
        self.assertEqual(body, b"ok")

        req = mock_urlopen.call_args.args[0]
        self.assertEqual(req.full_url, "http://cam.local/api/status")
        self.assertEqual(req.get_method(), "GET")
        self.assertTrue(req.headers["Authorization"].startswith("Basic "))

    @patch("cctv.request.urlopen")
    def test_request_normalizes_path_without_leading_slash(self, mock_urlopen):
        mock_response = mock_urlopen.return_value.__enter__.return_value
        mock_response.read.return_value = b"ok"
        client = SwannClient(SwannConfig("cam.local"))
        client.request(path="api/status")
        req = mock_urlopen.call_args.args[0]
        self.assertEqual(req.full_url, "http://cam.local/api/status")

    def test_parse_port_validates_range(self):
        self.assertEqual(parse_port("80"), 80)
        with self.assertRaisesRegex(Exception, "between 1 and 65535"):
            parse_port("0")
        with self.assertRaisesRegex(Exception, "between 1 and 65535"):
            parse_port("65536")

    @patch("cctv.request.urlopen")
    def test_main_http_error_to_stderr(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url="http://cam.local/api/status",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None,
        )
        stderr = io.StringIO()
        argv = [
            "cctv.py",
            "--host",
            "cam.local",
            "request",
            "--path",
            "/api/status",
        ]
        with patch("sys.argv", argv), redirect_stderr(stderr):
            exit_code = main()
        self.assertEqual(exit_code, 2)
        self.assertIn("HTTP error 401: Unauthorized", stderr.getvalue())

    @patch("cctv.request.urlopen")
    def test_main_url_error_to_stderr(self, mock_urlopen):
        mock_urlopen.side_effect = URLError("timed out")
        stderr = io.StringIO()
        argv = [
            "cctv.py",
            "--host",
            "cam.local",
            "request",
            "--path",
            "/api/status",
        ]
        with patch("sys.argv", argv), redirect_stderr(stderr):
            exit_code = main()
        self.assertEqual(exit_code, 3)
        self.assertIn("Connection error: timed out", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
