# VoiceClone Studio Remote API

VoiceClone Flow 远程模式要求独立的 VoiceClone Studio 提供以下接口。Studio 可运行在另一台 Windows 电脑上，服务器通过 FRP 或其他网络通道访问它。

## 地址与鉴权

插件填写的地址必须是从 AstrBot 服务器可访问的 `http://` 或 `https://` 地址。所有请求携带：

```http
Authorization: Bearer <token>
```

`127.0.0.1` 指向发起请求的服务器本机，不指向运行 Studio 的 Windows 电脑。

## `GET /api/health`

健康检查同时验证连通性和 Token。建议返回：

```json
{"status": "ok", "studio_version": "0.1.0"}
```

## `GET /api/voices`

返回稳定 `id` 的音色列表：

```json
{
  "voices": [
    {
      "id": "voice_xxx",
      "name": "示例音色",
      "language": "zh",
      "reference_text": "参考音频文本",
      "gpt_weights_path": "C:\\VoiceClone\\models\\gpt.ckpt",
      "sovits_weights_path": "C:\\VoiceClone\\models\\sovits.pth",
      "reference_audio_path": "C:\\VoiceClone\\voices\\ref.wav",
      "status": "ready"
    }
  ]
}
```

这些 Windows 路径仅用于展示和 Studio 自己的路由，AstrBot 服务器不得检查或读取。

## `POST /api/tts`

请求体：

```json
{
  "voice_id": "voice_xxx",
  "text": "要合成的文本",
  "text_language": "zh",
  "prompt_text": "参考音频文本",
  "prompt_language": "zh",
  "stream": true
}
```

成功响应为 `audio/wav`。允许使用 HTTP chunked transfer 分块返回当前句子的音频数据。插件会在当前句子接收完成后交给 AstrBot 现有 QQ 发送链路。

错误状态：`401/403` 表示 Token 无效，`429` 表示 Studio 队列已满，`5xx` 表示 Studio 内部错误。
