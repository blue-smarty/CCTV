import unittest

from cctv_gui import GUIConnectionInput, build_config_from_input


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


if __name__ == "__main__":
    unittest.main()
