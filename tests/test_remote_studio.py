import io
import json
import unittest
import wave
from pathlib import Path

from voice_clone_flow.remote_config import RemoteStudioConfig
from voice_clone_flow.remote_studio import RemoteStudioClient


class Response:
    def __init__(self, body: bytes):
        self.body = io.BytesIO(body)

    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, size=-1): return self.body.read(size)


class RemoteStudioTests(unittest.TestCase):
  def test_health_and_voices_send_bearer_header(self):
    seen = []
    def opener(request, timeout):
        seen.append((request.full_url, request.get_header("Authorization"), timeout))
        if request.full_url.endswith("/health"):
            return Response(json.dumps({"status": "ok"}).encode())
        return Response(json.dumps({"voices": [{"id": "voice-1", "name": "A"}]}).encode())

    client = RemoteStudioClient(RemoteStudioConfig("remote", "https://studio.example/base", "secret", 7), opener)
    self.assertEqual(client.health()["status"], "ok")
    self.assertEqual(client.list_voices()[0]["id"], "voice-1")
    self.assertEqual(seen[0][1], "Bearer secret")
    self.assertEqual(seen[0][2], 7)


  def test_synthesize_streams_to_file(self):
    import tempfile
    tmp_path = Path(tempfile.mkdtemp())
    client = RemoteStudioClient(RemoteStudioConfig("remote", "https://studio.example", "secret"), lambda request, timeout: Response(b"RIFF" + b"audio"))
    target = client.synthesize({"voice_id": "voice-1", "text": "hello", "stream": True}, tmp_path / "x.wav")
    self.assertEqual(target.read_bytes(), b"RIFFaudio")


  def test_provider_delivery_claim_and_report_use_authenticated_json(self):
    seen = []
    def opener(request, timeout):
      seen.append((request.full_url, request.get_header("Authorization"), json.loads(request.data.decode("utf-8"))))
      if request.full_url.endswith("/claim"):
        return Response(json.dumps({"delivery": {"id": "task-1", "provider_config": {"id": "provider-1"}}}).encode())
      return Response(json.dumps({"delivery": {"id": "task-1", "stage": "registered"}}).encode())

    client = RemoteStudioClient(RemoteStudioConfig("remote", "https://studio.example", "secret"), opener)
    delivery = client.claim_provider_delivery()
    self.assertEqual(delivery["id"], "task-1")
    result = client.report_provider_delivery("task-1", "registered", "Provider 已注册")
    self.assertEqual(result["stage"], "registered")
    self.assertTrue(seen[0][0].endswith("/api/provider-deliveries/claim"))
    self.assertEqual(seen[0][1], "Bearer secret")
    self.assertEqual(seen[1][2]["stage"], "registered")


  def test_verify_provider_downloads_a_bounded_wav_from_same_studio(self):
    def wav_bytes(seconds):
      target = io.BytesIO()
      with wave.open(target, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\x00\x00" * int(16000 * seconds))
      return target.getvalue()

    seen = []
    def opener(request, timeout):
      seen.append(request)
      if request.full_url.endswith("/infer_single"):
        return Response(json.dumps({"audio_url": "https://studio.example/api/audio/ticket-1"}).encode())
      return Response(wav_bytes(1.5))

    client = RemoteStudioClient(RemoteStudioConfig("remote", "https://studio.example", "secret"), opener)
    result = client.verify_provider("voice-1", "日文")
    request_payload = json.loads(seen[0].data.decode("utf-8"))
    self.assertTrue(request_payload["provider_verification"])
    self.assertEqual(request_payload["model_name"], "voice-1")
    self.assertEqual(request_payload["text_lang"], "日文")
    self.assertLessEqual(result["duration_seconds"], 1.5)


  def test_verify_provider_rejects_oversized_or_foreign_audio(self):
    foreign = lambda request, timeout: Response(json.dumps({"audio_url": "https://evil.example/audio.wav"}).encode())
    client = RemoteStudioClient(RemoteStudioConfig("remote", "https://studio.example", "secret"), foreign)
    with self.assertRaisesRegex(Exception, "地址"):
      client.verify_provider("voice-1", "中文")
