import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from voice_clone_flow.frp_manager import FrpManager


class FrpManagerTests(unittest.TestCase):
    def test_new_control_port_does_not_replace_existing_port(self):
        with TemporaryDirectory() as root:
            manager = FrpManager(Path(root))
            status = manager.status()
            self.assertEqual(status["bind_port"], 7001)
            self.assertTrue(status["existing_port_preserved"])

    def test_default_remote_port_is_not_7000(self):
        with TemporaryDirectory() as root:
            self.assertNotEqual(FrpManager(Path(root)).status()["remote_port"], 7000)
