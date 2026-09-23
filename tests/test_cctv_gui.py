import unittest
from unittest.mock import Mock, patch

from cctv_gui import (
    GUIConnectionInput,
    build_config_from_input,
    format_request_output,
    parse_channel_from_input,
    perform_formatted_request,
)


class GUIConfigTests(unittest.TestCase):
    def test_build_config_from_input_defaults_to_https_and_timeout(self):
        config = build_config_from_input(GUIConnectionInput(host="cam.local"))
        self.assertEqual(config.host, "cam.local")
        self.assertIsNone(config.username)
        self.assertIsNone(config.password)
        self.assertIsNone(config.port)
        self.assertTrue(config.https)
        self.assertEqual(config.timeout, 10)

    def test_build_config_from_input_parses_connection_values(self):
        config = build_config_from_input(
            GUIConnectionInput(
                " cam.local ",
                " admin ",
                " secret ",
                "8443",
                True,
                "15",
            )
        )
        self.assertEqual(config.host, "cam.local")
        self.assertEqual(config.username, "admin")
        self.assertEqual(config.password, "secret")
        self.assertEqual(config.port, 8443)
        self.assertEqual(config.timeout, 15)

    def test_build_config_from_input_rejects_empty_host(self):
        with self.assertRaisesRegex(ValueError, "Host is required"):
            build_config_from_input(GUIConnectionInput(host="   "))

    def test_parse_channel_from_input_strips_whitespace(self):
        self.assertEqual(parse_channel_from_input(" 2 "), 2)

    def test_parse_channel_from_input_rejects_invalid_value(self):
        with self.assertRaisesRegex(Exception, "positive integer"):
            parse_channel_from_input("0")

    def test_format_request_output_for_text(self):
        rendered = format_request_output(b"camera online", "text/plain; charset=utf-8")
        self.assertEqual(rendered, "camera online")

    def test_format_request_output_for_json(self):
        rendered = format_request_output(b'{"ok":true}', "application/json")
        self.assertEqual(rendered, '{\n  "ok": true\n}')

    def test_format_request_output_for_binary(self):
        rendered = format_request_output(b"\xff\xd8", "image/jpeg")
        self.assertEqual(rendered, "ffd8")

    @patch("cctv_gui.render_content", return_value=(True, b"\x01\x02"))
    def test_format_request_output_prefers_rendered_binary_bytes(self, _mock_render_content):
        rendered = format_request_output(b"\xff\xd8", "image/jpeg")
        self.assertEqual(rendered, "0102")

    def test_perform_formatted_request_uses_client_response(self):
        client = Mock()
        client.request_response.return_value = (b"camera online", "text/plain; charset=utf-8")
        rendered = perform_formatted_request(client, "/status", "GET", "text/plain")
        client.request_response.assert_called_once_with(path="/status", method="GET", accept="text/plain")
        self.assertEqual(rendered, "camera online")

    def test_perform_formatted_request_formats_binary_response(self):
        client = Mock()
        client.request_response.return_value = (b"\xff\xd8", "image/jpeg")
        rendered = perform_formatted_request(client, "/snapshot", "GET", "image/jpeg")
        self.assertEqual(rendered, "ffd8")

    def test_perform_formatted_request_supports_head_method(self):
        client = Mock()
        client.request_response.return_value = (b"", "text/plain; charset=utf-8")
        rendered = perform_formatted_request(client, "/status", "HEAD", "text/plain")
        client.request_response.assert_called_once_with(path="/status", method="HEAD", accept="text/plain")
        self.assertEqual(rendered, "")


if __name__ == "__main__":
    unittest.main()
