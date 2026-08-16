import unittest

from voice_clone_flow.gpt_sovits.voices import VoiceAsset, VoiceRegistry
from voice_clone_flow.remote_provider import apply_remote_provider, build_remote_provider_config, finalize_remote_provider_delivery, normalize_delivery_provider, remote_provider_id


class RemoteProviderTests(unittest.TestCase):
  def test_remote_voice_upsert_keeps_windows_paths_opaque(self):
    registry = VoiceRegistry("unused")
    registry.save = lambda asset: asset
    asset = registry.upsert_remote_voice({
        "id": "voice-1", "name": "测试", "language": "zh",
        "gpt_weights_path": r"C:\models\gpt.ckpt",
        "reference_audio_path": r"C:\voices\ref.wav",
    })
    self.assertEqual(asset.source, "remote")
    self.assertEqual(asset.gpt_weights_path, r"C:\models\gpt.ckpt")
    self.assertEqual(asset.refer_audio_path, r"C:\voices\ref.wav")


  def test_provider_uses_astrbot_gsvi_contract_without_remote_paths(self):
    asset = VoiceAsset(id="remote_voice-1", name="测试", source="remote", remote_voice_id="voice-1", reference_language="zh", gpt_weights_path=r"C:\x")
    config = build_remote_provider_config(
        asset,
        api_base="http://127.0.0.1:19090",
        api_key="studio-secret",
    )
    self.assertEqual(config["id"], remote_provider_id("voice-1"))
    self.assertEqual(config["type"], "gsvi_tts_api")
    self.assertEqual(config["provider"], "gpt_sovits_inference")
    self.assertEqual(config["api_base"], "http://127.0.0.1:19090")
    self.assertEqual(config["api_key"], "studio-secret")
    self.assertEqual(config["character"], "voice-1")
    self.assertEqual(config["prompt_text_lang"], "中文")
    self.assertEqual(config["text_lang"], "中文")
    self.assertNotIn("api_token", config)
    self.assertNotIn(r"C:\x", str(config))


  def test_apply_requires_loaded_tts_instance_and_removes_new_orphan(self):
    class Manager:
      def __init__(self):
        self.providers_config = []
        self.inst_map = {}
        self.tts_provider_insts = []
        self.deleted = []
      async def create_provider(self, config):
        self.providers_config.append(config)
      async def delete_provider(self, provider_id):
        self.deleted.append(provider_id)
        self.providers_config = [item for item in self.providers_config if item["id"] != provider_id]

    manager = Manager()
    context = type("Context", (), {"provider_manager": manager})()
    config = {
      "id": "voice_clone_flow_remote_voice-1", "type": "gsvi_tts_api",
      "provider": "gpt_sovits_inference", "provider_type": "text_to_speech",
      "enable": True, "api_base": "http://127.0.0.1:19090", "api_key": "secret",
      "character": "voice-1", "prompt_text_lang": "日文", "emotion": "默认",
      "text_lang": "日文", "version": "v2Pro",
    }
    with self.assertRaisesRegex(RuntimeError, "运行实例"):
      __import__("asyncio").run(apply_remote_provider(context, config))
    self.assertEqual(manager.deleted, [config["id"]])


  def test_apply_accepts_provider_only_after_instance_is_registered(self):
    class Instance:
      def __init__(self, config): self.provider_config = config
    class Manager:
      def __init__(self):
        self.providers_config = []
        self.inst_map = {}
        self.tts_provider_insts = []
      async def create_provider(self, config):
        self.providers_config.append(config)
        instance = Instance(config)
        self.inst_map[config["id"]] = instance
        self.tts_provider_insts.append(instance)

    manager = Manager()
    context = type("Context", (), {"provider_manager": manager})()
    config = {
      "id": "voice_clone_flow_remote_voice-1", "type": "gsvi_tts_api",
      "provider": "gpt_sovits_inference", "provider_type": "text_to_speech",
      "enable": True, "api_base": "http://127.0.0.1:19090", "api_key": "secret",
      "character": "voice-1", "prompt_text_lang": "日文", "emotion": "默认",
      "text_lang": "日文", "version": "v2Pro",
    }
    provider_id = __import__("asyncio").run(apply_remote_provider(context, config))
    self.assertEqual(provider_id, config["id"])


  def test_delivery_config_is_whitelisted_and_uses_plugin_connection(self):
    received = {
      "id": "voice_clone_flow_remote_voice-1",
      "type": "gsvi_tts_api",
      "provider": "gpt_sovits_inference",
      "provider_type": "text_to_speech",
      "enable": True,
      "display_name": "Viola",
      "api_key": "untrusted-studio-value",
      "api_base": "https://untrusted.example",
      "version": "v2Pro",
      "character": "voice-1",
      "prompt_text_lang": "日文",
      "emotion": "默认",
      "text_lang": "日文",
      "timeout": 300,
      "default_params": {"bad": True},
    }
    config = normalize_delivery_provider(
      received,
      api_base="http://127.0.0.1:19090",
      api_key="plugin-token",
    )
    self.assertEqual(config["api_base"], "http://127.0.0.1:19090")
    self.assertEqual(config["api_key"], "plugin-token")
    self.assertNotIn("default_params", config)
    self.assertEqual(config["character"], "voice-1")


  def test_delivery_is_verified_only_after_short_audio_probe(self):
    class Client:
      def __init__(self): self.reports = []
      def report_provider_delivery(self, task_id, stage, message="", error=""):
        self.reports.append((task_id, stage, message, error))
        return {"stage": stage}
      def verify_provider(self, voice_id, text_language):
        self.probe = (voice_id, text_language)
        return {"duration_seconds": 1.5, "size_bytes": 48044}

    client = Client()
    result = __import__("asyncio").run(finalize_remote_provider_delivery(
      client,
      "task-1",
      "provider-1",
      {"character": "voice-1", "text_lang": "日文"},
    ))
    self.assertTrue(result["verified"])
    self.assertEqual(client.probe, ("voice-1", "日文"))
    self.assertEqual([item[1] for item in client.reports], ["registered", "verified"])


  def test_failed_audio_probe_keeps_registered_provider_and_reports_failure(self):
    class Client:
      def __init__(self): self.reports = []
      def report_provider_delivery(self, task_id, stage, message="", error=""):
        self.reports.append((task_id, stage, message, error))
        return {"stage": stage}
      def verify_provider(self, voice_id, text_language):
        raise RuntimeError("Studio 离线")

    client = Client()
    result = __import__("asyncio").run(finalize_remote_provider_delivery(
      client,
      "task-1",
      "provider-1",
      {"character": "voice-1", "text_lang": "中文"},
    ))
    self.assertFalse(result["verified"])
    self.assertEqual([item[1] for item in client.reports], ["registered", "failed"])
    self.assertIn("已注册", client.reports[-1][2])
    self.assertIn("Studio 离线", client.reports[-1][3])
