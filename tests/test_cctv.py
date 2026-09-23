import base64
import unittest
from unittest.mock import patch

from cctv import SwannClient, SwannConfig, build_basic_auth_header


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


if __name__ == "__main__":
    unittest.main()
