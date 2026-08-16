import io
import json
import unittest
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
