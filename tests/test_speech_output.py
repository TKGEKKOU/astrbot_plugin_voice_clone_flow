import unittest

from astrbot.api.message_components import Plain
from astrbot.core.message.message_event_result import ResultContentType

from voice_clone_flow.speech_output import BilingualTTSDecorator


class _Meta:
    def __init__(self, provider_id):
        self.id = provider_id


class _Provider:
    def __init__(self, provider_id, audio_path="C:/temp/voice.wav"):
        self._meta = _Meta(provider_id)
        self.default_params = {"text_lang": "ja"}
        self.inputs = []
        self.audio_path = audio_path

    def meta(self):
        return self._meta

    async def get_audio(self, text):
        self.inputs.append(text)
        return self.audio_path


class _Context:
    def __init__(self, provider):
        self.provider = provider
        self.sent = []

    async def get_using_tts_provider_async(self, _umo):
        return self.provider

    async def send_message(self, umo, chain):
        self.sent.append((umo, chain))


class _Translator:
    def __init__(self):
        self.inputs = []

    async def translate(self, umo, text):
        self.inputs.append((umo, text))
        return "日本語"


class _Result:
    def __init__(self, text="", is_llm=False):
        self.chain = [Plain(text)] if text else []
        self._is_llm = is_llm
        self.result_content_type = (
            ResultContentType.LLM_RESULT if is_llm else ResultContentType.GENERAL_RESULT
        )

    def is_llm_result(self):
        return self._is_llm


class _Event:
    def __init__(self, result):
        self.result = result
        self.extras = {}
        self.unified_msg_origin = "umo-1"

    def get_result(self):
        return self.result

    def set_extra(self, key, value):
        self.extras[key] = value

    def get_extra(self, key, default=None):
        return self.extras.get(key, default)


class _Response:
    def __init__(self, text):
        self.completion_text = text


class SpeechOutputTests(unittest.IsolatedAsyncioTestCase):
    async def test_remote_voice_clone_provider_receives_chinese_without_server_translation(self):
        provider = _Provider("voice_clone_flow_remote_voice-1")
        context = _Context(provider)
        translator = _Translator()
        decorator = BilingualTTSDecorator(context, translator, target_language="ja")

        await decorator._render_sentence("umo-1", "你好，今天怎么样？")

        self.assertEqual(provider.inputs, ["你好，今天怎么样？"])
        self.assertEqual(translator.inputs, [])
        self.assertEqual(len(context.sent), 1)

    async def test_other_japanese_provider_keeps_server_translation(self):
        provider = _Provider("other_japanese_tts")
        context = _Context(provider)
        translator = _Translator()
        decorator = BilingualTTSDecorator(context, translator, target_language="ja")

        await decorator._render_sentence("umo-1", "你好")

        self.assertEqual(translator.inputs, [("umo-1", "你好")])
        self.assertEqual(provider.inputs, ["日本語"])

    async def test_missing_provider_keeps_text_only(self):
        context = _Context(None)
        translator = _Translator()
        decorator = BilingualTTSDecorator(context, translator, target_language="ja")

        await decorator._render_sentence("umo-1", "你好")

        self.assertEqual(translator.inputs, [])
        self.assertEqual(context.sent, [])

    async def test_missing_audio_keeps_text_only(self):
        provider = _Provider("voice_clone_flow_remote_voice-1", audio_path="")
        context = _Context(provider)
        translator = _Translator()
        decorator = BilingualTTSDecorator(context, translator, target_language="ja")

        await decorator._render_sentence("umo-1", "你好")

        self.assertEqual(provider.inputs, ["你好"])
        self.assertEqual(context.sent, [])

    async def test_cached_llm_marker_allows_general_result_and_prefers_visible_text(self):
        provider = _Provider("voice_clone_flow_remote_voice-1")
        decorator = BilingualTTSDecorator(_Context(provider), _Translator(), target_language="ja")
        event = _Event(_Result("最终发送给 QQ 的文字", is_llm=False))
        decorator.capture_llm_response(event, _Response("模型原始回复"))

        await decorator.decorate(event)
        await decorator.wait_for_tasks()

        self.assertEqual(provider.inputs, ["最终发送给 QQ 的文字"])

    async def test_cached_llm_text_is_fallback_when_result_has_no_plain_text(self):
        provider = _Provider("voice_clone_flow_remote_voice-1")
        decorator = BilingualTTSDecorator(_Context(provider), _Translator(), target_language="ja")
        event = _Event(_Result(is_llm=False))
        decorator.capture_llm_response(event, _Response("模型完整回复"))

        await decorator.decorate(event)
        await decorator.wait_for_tasks()

        self.assertEqual(provider.inputs, ["模型完整回复"])

    async def test_same_event_is_scheduled_only_once(self):
        provider = _Provider("voice_clone_flow_remote_voice-1")
        decorator = BilingualTTSDecorator(_Context(provider), _Translator(), target_language="ja")
        event = _Event(_Result("只发送一次", is_llm=False))
        decorator.capture_llm_response(event, _Response("只发送一次"))

        await decorator.decorate(event)
        await decorator.decorate(event)
        await decorator.wait_for_tasks()

        self.assertEqual(provider.inputs, ["只发送一次"])

    async def test_general_plugin_message_without_llm_marker_is_not_spoken(self):
        provider = _Provider("voice_clone_flow_remote_voice-1")
        decorator = BilingualTTSDecorator(_Context(provider), _Translator(), target_language="ja")
        event = _Event(_Result("命令执行成功", is_llm=False))

        await decorator.decorate(event)
        await decorator.wait_for_tasks()

        self.assertEqual(provider.inputs, [])


if __name__ == "__main__":
    unittest.main()
