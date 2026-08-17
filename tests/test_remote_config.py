import unittest
from pathlib import Path

from voice_clone_flow.remote_config import RemoteStudioConfig, RemoteStudioConfigError, RemoteStudioConfigStore, resolve_astrbot_remote_config


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


  def test_astrbot_settings_override_stale_runtime_mode(self):
    stored = RemoteStudioConfig("local", "", "", 300)
    resolved = resolve_astrbot_remote_config(
      stored,
      {
        "remote_mode": "remote",
        "remote_studio": {
          "base_url": "http://127.0.0.1:19090",
          "token": "secret",
          "timeout_seconds": 120,
        },
      },
    )

    self.assertEqual(resolved.mode, "remote")
    self.assertEqual(resolved.base_url, "http://127.0.0.1:19090")
    self.assertEqual(resolved.token, "secret")
    self.assertEqual(resolved.timeout_seconds, 120)
