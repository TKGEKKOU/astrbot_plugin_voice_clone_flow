import unittest
from pathlib import Path

from voice_clone_flow.remote_config import RemoteStudioConfig, RemoteStudioConfigError, RemoteStudioConfigStore


class RemoteConfigTests(unittest.TestCase):
  def test_config_round_trip_and_mask(self):
    import tempfile
    store = RemoteStudioConfigStore(Path(tempfile.mkdtemp()))
    config = store.save(RemoteStudioConfig("remote", "http://127.0.0.1:9090", "secret", 12))
    assert store.load().token == "secret"
    assert config.masked()["token"] == "****"


  def test_config_rejects_non_http_address(self):
    with self.assertRaises(RemoteStudioConfigError):
        RemoteStudioConfig("remote", "frp://studio:1", "secret").validate()


  def test_local_defaults_without_remote_values(self):
    self.assertEqual(RemoteStudioConfig().validate().mode, "local")
