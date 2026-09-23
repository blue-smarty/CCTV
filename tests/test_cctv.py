import base64
import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from cctv import (
    SwannClient,
    SwannConfig,
    build_basic_auth_header,
    detect_charset,
    main,
    parse_channel,
    parse_port,
    parse_timeout,
)


class SwannClientTests(unittest.TestCase):
    class _FakeStdout:
        def __init__(self):
            self.buffer = io.BytesIO()

        def write(self, _text):
            return 0

        def flush(self):
            return None

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

    def test_parse_timeout_validates_positive(self):
        self.assertEqual(parse_timeout("10"), 10)
        with self.assertRaisesRegex(Exception, "positive integer"):
            parse_timeout("0")
        with self.assertRaisesRegex(Exception, "positive integer"):
            parse_timeout("-5")

    def test_parse_channel_validates_positive(self):
        self.assertEqual(parse_channel("1"), 1)
        with self.assertRaisesRegex(Exception, "positive integer"):
            parse_channel("0")

    def test_detect_charset(self):
        self.assertEqual(detect_charset("text/plain; charset=iso-8859-1"), "iso-8859-1")
        self.assertEqual(detect_charset("text/plain"), "utf-8")

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

    @patch("cctv.request.urlopen")
    def test_main_request_writes_binary_to_stdout_buffer(self, mock_urlopen):
        mock_response = mock_urlopen.return_value.__enter__.return_value
        mock_response.read.return_value = b"\xff\xd8"
        mock_response.headers = {"Content-Type": "image/jpeg"}
        fake_stdout = self._FakeStdout()
        argv = [
            "cctv.py",
            "--host",
            "cam.local",
            "request",
            "--path",
            "/snapshot.bin",
        ]
        with patch("sys.argv", argv), patch("sys.stdout", fake_stdout):
            exit_code = main()
        self.assertEqual(exit_code, 0)
        self.assertEqual(fake_stdout.buffer.getvalue(), b"\xff\xd8\n")

    @patch("cctv.request.urlopen")
    def test_main_request_writes_text_for_text_content_type(self, mock_urlopen):
        mock_response = mock_urlopen.return_value.__enter__.return_value
        mock_response.read.return_value = b"camera online"
        mock_response.headers = {"Content-Type": "text/plain; charset=utf-8"}
        out = io.StringIO()
        argv = [
            "cctv.py",
            "--host",
            "cam.local",
            "request",
            "--path",
            "/status.txt",
        ]
        with patch("sys.argv", argv), redirect_stdout(out):
            exit_code = main()
        self.assertEqual(exit_code, 0)
        self.assertEqual(out.getvalue(), "camera online\n")

    @patch("cctv.request.urlopen")
    def test_main_request_respects_text_charset(self, mock_urlopen):
        mock_response = mock_urlopen.return_value.__enter__.return_value
        mock_response.read.return_value = "caf\xe9".encode("iso-8859-1")
        mock_response.headers = {"Content-Type": "text/plain; charset=iso-8859-1"}
        out = io.StringIO()
        argv = [
            "cctv.py",
            "--host",
            "cam.local",
            "request",
            "--path",
            "/status.txt",
        ]
        with patch("sys.argv", argv), redirect_stdout(out):
            exit_code = main()
        self.assertEqual(exit_code, 0)
        self.assertEqual(out.getvalue(), "café\n")

    def test_main_rejects_partial_credentials(self):
        stderr = io.StringIO()
        argv = ["cctv.py", "--host", "cam.local", "--username", "admin", "snapshot-url"]
        with patch("sys.argv", argv), redirect_stderr(stderr):
            exit_code = main()
        self.assertEqual(exit_code, 4)
        self.assertIn("Both --username and --password must be provided together", stderr.getvalue())

    def test_main_allows_empty_credential_values_when_both_present(self):
        out = io.StringIO()
        argv = [
            "cctv.py",
            "--host",
            "cam.local",
            "--username",
            "",
            "--password",
            "",
            "snapshot-url",
        ]
        with patch("sys.argv", argv), redirect_stdout(out):
            exit_code = main()
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
