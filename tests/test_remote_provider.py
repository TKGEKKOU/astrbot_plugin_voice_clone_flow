from pathlib import Path
import unittest

from voice_clone_flow.gpt_sovits.voices import VoiceAsset, VoiceRegistry
from voice_clone_flow.remote_provider import build_remote_provider_config, remote_provider_id


class RemoteProviderTests(unittest.TestCase):
  def test_remote_voice_upsert_keeps_windows_paths_opaque(self):
    import tempfile
    registry = VoiceRegistry(Path(tempfile.mkdtemp()))
    asset = registry.upsert_remote_voice({
        "id": "voice-1", "name": "测试", "language": "zh",
        "gpt_weights_path": r"C:\models\gpt.ckpt",
        "reference_audio_path": r"C:\voices\ref.wav",
    })
    self.assertEqual(asset.source, "remote")
    self.assertEqual(asset.gpt_weights_path, r"C:\models\gpt.ckpt")
    self.assertEqual(asset.refer_audio_path, r"C:\voices\ref.wav")


  def test_provider_contains_voice_id_but_no_remote_paths(self):
    asset = VoiceAsset(id="remote_voice-1", name="测试", source="remote", remote_voice_id="voice-1", reference_language="zh", gpt_weights_path=r"C:\x")
    config = build_remote_provider_config(asset)
    self.assertEqual(config["id"], remote_provider_id("voice-1"))
    self.assertEqual(config["voice_id"], "voice-1")
    self.assertNotIn(r"C:\x", str(config))
