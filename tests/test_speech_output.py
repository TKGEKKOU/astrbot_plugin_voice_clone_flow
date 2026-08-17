import unittest

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


if __name__ == "__main__":
    unittest.main()
