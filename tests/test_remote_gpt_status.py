import asyncio
import json
import unittest

from main import VoiceCloneFlowPlugin


class _RemoteConfig:
    mode = "remote"


class _FailingAdapter:
    def status(self):
        raise AssertionError("remote status must not inspect the local GPT adapter")


class _Install:
    def status(self):
        raise AssertionError("remote status must not inspect local installation state")


class RemoteGptStatusTests(unittest.TestCase):
    def test_remote_gpt_status_does_not_touch_local_runtime(self):
        plugin = VoiceCloneFlowPlugin.__new__(VoiceCloneFlowPlugin)
        plugin.remote_config = _RemoteConfig()
        plugin.gpt_adapter = _FailingAdapter()
        plugin.gpt_install = _Install()
        plugin.gpt_starting = False
        plugin.gpt_start_error = ""

        response = asyncio.run(plugin.page_gpt_status())
        payload = json.loads(response.body)

        self.assertEqual(payload["service"]["mode"], "remote")
        self.assertFalse(payload["service"]["service_running"])
        self.assertIn("远程模式", payload["service"]["error"])


if __name__ == "__main__":
    unittest.main()
