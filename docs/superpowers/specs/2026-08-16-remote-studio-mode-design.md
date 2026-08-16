# VoiceClone Flow 远程工作室模式设计

## 1. 目标与范围

本设计基于当前 `origin/main` 版本，新增可选的远程连接模式：AstrBot、VoiceClone Flow 和 NapCat 运行在服务器上，GPT-SoVITS 推理由另一台可访问的 Windows 电脑上的 VoiceClone Studio 执行。

第一版范围为“远程推理 + 音色同步”，不从 AstrBot 页面发起远程训练。训练在 VoiceClone Studio 中完成，插件同步训练成果并转发合成请求。现有本地模式的安装、训练和推理功能保持不变。

## 2. 模式与配置

插件提供 `local` 和 `remote` 两种互斥模式，并在管理页顶部提供切换控件及提示：轻量服务器可切换远程模式。

远程配置独立保存：

```text
mode: local | remote
remote_studio:
  base_url: http://47.103.73.128:9090
  token: 用户配置的 Token
  timeout_seconds: 300
```

`base_url` 必须是从 AstrBot 服务器视角可访问的标准 `http://` 或 `https://` 地址。`127.0.0.1` 只表示服务器本机；只有 FRP 已把 Studio 映射到服务器本机端口时才可使用。插件不支持 `frp://` 专用地址，也不猜测或改写用户填写的地址。

Token 使用显式文本输入，可查看、修改和清空。配置文件保存原值，日志和错误信息中统一脱敏为 `****`。

两种模式的配置互不覆盖。远程模式不启动、不探测、不安装本地 GPT-SoVITS，并隐藏本地环境管理、训练和路径操作。切回本地模式后恢复本地功能。

## 3. Studio API 契约

Studio 是独立应用，本需求不实现 Studio 本身，但定义插件所依赖的接口：

```text
GET  /api/health
GET  /api/voices
POST /api/tts
```

所有请求携带：

```http
Authorization: Bearer <token>
```

### 3.1 健康检查

`GET /api/health` 同时验证 Studio 连通性和 Token 有效性，返回可供页面展示的状态信息。

### 3.2 音色列表

`GET /api/voices` 返回稳定的音色 `id`、显示名称、语言、参考文本、权重路径、参考音频路径和状态等元数据。Windows 路径仅作为远程元数据保存和只读展示，服务器不得执行存在性检查、路径转换或文件读取。

### 3.3 语音合成

`POST /api/tts` 至少接收 `voice_id`、文本、文本语言、参考文本、参考语言和 `stream` 参数，并返回 WAV 音频。允许使用 HTTP 分块传输，让 Studio 与插件边生成边传输当前句子的音频。

## 4. Provider 与地址链路

采用插件专用的远程 TTS Provider，而不是让现有本地 GSV Provider 直接访问 Studio，也不建立额外的本机 HTTP 兼容代理。

地址链路固定为：

```text
AstrBot 远程 Provider
  -> RemoteStudioClient
  -> 用户配置的 HTTP/HTTPS Studio 地址
  -> FRP 或其他网络通道
  -> Windows VoiceClone Studio
```

每个远程音色创建一个独立 Provider，例如 `voice_clone_flow_remote_<voice_id>`。Provider 实际只保存稳定的 `voice_id`；Studio 地址和 Token 由插件统一管理，不分散到 Provider 配置中；远程 Windows 文件路径不作为服务器本地路径使用。

同步规则：

- 手动点击“同步远程音色”才拉取列表并更新 Provider；
- 新音色创建 Provider，已有音色更新 Provider；
- Studio 已删除的音色对应 Provider 禁用，不直接删除；
- 本地 Provider 与远程 Provider 按当前模式启用或禁用，不删除；
- 用户手动禁用的 Provider 状态不因模式切换被强制恢复；
- 管理页只读展示同步后的远程元数据和 Provider 状态。

## 5. 语音输出与实时性

保留当前 VoiceClone Flow 的 QQ 输出行为：文字先发送，语音按现有句子切分规则逐句生成并发送。每个句子调用一次远程 Provider；Studio 可通过分块响应边生成边传输，插件将当前句子的返回数据写入临时音频文件，句子音频接收完成后立即交给现有 QQ 发送逻辑，再处理下一句。

当前 AstrBot TTS Provider 接口返回完整音频路径，不能把一条尚未完成的音频流直接交给 QQ 播放。因此第一版提供“Studio 到插件的实时传输”和“按句尽早发送”，不改变现有 QQ 消息行为；未来若 AstrBot 或 Studio 提供音频分片回调，可在此接口上扩展更细粒度的实时发送。

## 6. 状态、错误与降级

远程客户端统一维护以下状态：未配置、未连接、鉴权失败、服务繁忙、请求超时、接口错误、已连接、同步中。

- 页面显示当前状态、最近连接检查时间、最近同步时间和脱敏错误摘要；
- 插件启动和管理页打开时可执行轻量连接检查，但不自动同步音色或修改 Provider；
- 远程 Provider 异常不得传播为 AstrBot 主循环崩溃；
- Studio 不可用、鉴权失败、超时或返回错误时，沿用当前行为，仅保留文字回复；
- 不向 QQ 或其他聊天渠道额外发送故障提示；
- 日志记录类型化错误，但不得输出 Token、完整鉴权头或敏感路径；
- Studio 负责并发队列和 GPU 调度；插件不维护服务器端任务队列。Studio 忙时可返回 `429`，页面显示服务繁忙。

## 7. 页面行为

远程模式页面展示：模式开关、Studio 地址、显式 Token、连接测试、同步远程音色、连接状态、同步时间和只读音色列表。

远程模式隐藏或禁用：本地 GPT-SoVITS 安装、启动、停止、删除、模型管理、训练、打开本地训练目录和本地路径编辑操作。

本地模式隐藏远程连接配置和远程同步操作，现有本地管理页面保持原行为。

## 8. 测试与验收

插件侧必须覆盖：

- 本地模式安装、启动、停止、训练、试听和本地 Provider 回归；
- 远程模式不启动、不探测本地 GPT-SoVITS；
- HTTP/HTTPS 地址校验和服务器视角的 `127.0.0.1` 语义；
- Token 请求头、显式配置和日志脱敏；
- 健康检查成功、连接失败、鉴权失败和超时；
- 音色新增、更新、删除后的 Provider 禁用；
- Windows 远程路径不执行服务器存在性检查；
- 多音色使用正确 `voice_id`；
- 文本、语言、参考文本和流式参数透传；
- Studio 关闭或出错时 AstrBot 不崩溃且只保留文字；
- 模式切换时两套配置不覆盖、Provider 状态正确；
- 临时音频发送后清理，远程音色元数据保留。

Studio 联调必须验证：`/api/health`、`/api/voices`、`/api/tts`、Bearer Token、FRP 映射可达、流式响应和 `voice_id` 路由。服务器不安装 GPT-SoVITS，也不持有 Studio 模型文件。

## 9. 范围外

- VoiceClone Studio 的实现；
- FRP 服务端或客户端配置教程；
- 远程训练 API 和 AstrBot 页面训练入口；
- GPT-SoVITS 模型文件修改；
- QQ 单条语音消息的未完成流直接播放。
