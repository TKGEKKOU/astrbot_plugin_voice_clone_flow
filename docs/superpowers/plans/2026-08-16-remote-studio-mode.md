# Remote Studio Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 VoiceClone Flow 当前 `origin/main` 基线上新增可选远程模式，使服务器上的 AstrBot 插件通过 HTTP/HTTPS、FRP 和 Token 调用另一台电脑上的 VoiceClone Studio 进行推理，并同步远程音色。

**Architecture:** 保留现有本地 GPT-SoVITS 链路，新增独立的远程配置、`RemoteStudioClient` 和远程 TTS Provider。每个远程音色以稳定 `voice_id` 建立独立 Provider；Provider 不保存 Studio 地址、Token 或 Windows 文件路径，所有远程请求由客户端统一鉴权、状态化和错误降级。

**Tech Stack:** Python 3、AstrBot `Context`/`ProviderManager`、现有 `main.py` Web API、JSON 数据文件、现有 Vanilla JS 管理页、pytest。

## Global Constraints

- 第一版只支持远程推理与音色同步，不从 AstrBot 页面发起远程训练。
- Studio API 固定为 `/api/health`、`/api/voices`、`/api/tts`，不带版本号。
- Studio 地址必须是 AstrBot 服务器可访问的 `http://` 或 `https://` 地址；FRP 不由插件配置或实现。
- Token 使用显式文本输入，可查看、修改和清空；日志中必须脱敏为 `****`。
- 远程 Windows 权重路径和参考音频路径只读保存和展示，服务器不得做存在性检查、路径转换或文件读取。
- 本地模式功能保持回归；远程模式不得启动、探测或安装本地 GPT-SoVITS。
- 远程故障只显示在插件页面和日志，聊天侧沿用现有纯文字降级，不额外发送故障消息。
- 保留当前 QQ 逐句语音发送行为；Studio 到插件允许 HTTP 分块传输，但不得宣称 QQ 播放未完成的单条音频。
- Studio 负责并发队列和 GPU 调度；插件不维护服务器端任务队列。

## File Map

- Create `voice_clone_flow/remote_studio.py`: 地址校验、Bearer Token、健康检查、音色列表、TTS 分块响应和类型化异常。
- Create `voice_clone_flow/remote_config.py`: 远程模式配置的 JSON 持久化、脱敏读取和更新语义。
- Modify `_conf_schema.json`: 增加模式、Studio 地址、显式 Token 和超时的 AstrBot 配置入口或默认值。
- Modify `main.py`: 初始化远程配置/客户端，注册健康检查、连接测试、音色同步和远程 TTS 相关 Web API，按模式隔离本地服务与 Provider。
- Modify `voice_clone_flow/gpt_sovits/voices.py`: 扩展远程音色元数据模型和稳定 `voice_id` 保存，不触发本地路径验证。
- Modify `voice_clone_flow/gpt_sovits/provider.py` or create `voice_clone_flow/remote_provider.py`: 远程 Provider 配置生成、创建/更新/禁用和 ProviderManager 对接。
- Modify `pages/voice-clone/index.html`, `pages/voice-clone/app.js`, `pages/voice-clone/style.css`: 顶部模式切换、远程表单、连接/同步状态和只读远程音色列表。
- Create `tests/test_remote_studio.py`, `tests/test_remote_config.py`, `tests/test_remote_provider.py`, `tests/test_remote_mode.py`: 单元、契约、模式隔离和回归测试。
- Modify `README.md` or add API documentation only after implementation behavior is verified; document address semantics, FRP assumption, Studio API and current QQ behavior.

### Task 1: Add Remote Configuration and HTTP Client

**Files:**
- Create: `voice_clone_flow/remote_config.py`
- Create: `voice_clone_flow/remote_studio.py`
- Modify: `_conf_schema.json`
- Test: `tests/test_remote_config.py`, `tests/test_remote_studio.py`

**Interfaces:**
- Produces `RemoteStudioConfig(mode: str, base_url: str, token: str, timeout_seconds: float)`.
- Produces `RemoteStudioClient(config, opener=urlopen)` with `health()`, `list_voices()`, and `synthesize(payload, destination)` methods.
- Raises `RemoteStudioConfigError`, `RemoteStudioAuthError`, `RemoteStudioConnectionError`, `RemoteStudioBusyError`, and `RemoteStudioProtocolError`.

- [ ] **Step 1: Write failing config tests** for default local mode, independent JSON persistence, explicit token round-trip, empty-token clearing, and invalid non-HTTP(S) URL rejection.
- [ ] **Step 2: Run `pytest tests/test_remote_config.py -v`** and verify failures identify missing config types/functions.
- [ ] **Step 3: Implement JSON persistence** under the plugin data directory using atomic temporary-file replacement. Return a masked token only from status serialization; never log the raw token.
- [ ] **Step 4: Write failing client tests** with a fake opener covering `Authorization: Bearer`, `/api/health`, `/api/voices`, 401, connection timeout, 429, malformed JSON, and chunked WAV writing.
- [ ] **Step 5: Implement URL normalization and client requests**. Accept only `http://` and `https://`; join paths without duplicate slashes; never put Token in the URL; map status codes to typed exceptions; stream response chunks into the caller-provided temporary file.
- [ ] **Step 6: Run both test files** and verify all config/client tests pass.
- [ ] **Step 7: Commit** `feat: add remote studio client and config`.

### Task 2: Extend Voice Metadata Without Local Path Checks

**Files:**
- Modify: `voice_clone_flow/gpt_sovits/voices.py`
- Test: `tests/test_remote_mode.py`

**Interfaces:**
- Adds remote fields to `VoiceAsset`: `source` (`local`/`remote`), `remote_voice_id`, `remote_metadata`, `remote_provider_id`.
- Produces `VoiceRegistry.upsert_remote_voice(metadata)` and `VoiceRegistry.disable_missing_remote_voice_ids(ids)`.

- [ ] **Step 1: Write failing tests** for importing Windows paths as opaque strings, stable IDs across repeated sync, metadata-only updates, and no `Path.is_file`, `exists`, `resolve`, or path conversion on remote values.
- [ ] **Step 2: Run the focused tests** and verify they fail before implementation.
- [ ] **Step 3: Implement remote upsert** keyed by Studio `id`; preserve local assets; save complete metadata for read-only display; store remote paths as strings only.
- [ ] **Step 4: Implement missing-voice disable bookkeeping** without deleting registry rows or local assets.
- [ ] **Step 5: Run focused tests** and verify pass.
- [ ] **Step 6: Commit** `feat: store remote voice metadata safely`.

### Task 3: Implement Remote Provider Integration

**Files:**
- Create: `voice_clone_flow/remote_provider.py`
- Modify: `main.py`
- Test: `tests/test_remote_provider.py`

**Interfaces:**
- Produces `build_remote_provider_config(voice: VoiceAsset) -> dict` with ID `voice_clone_flow_remote_<remote_voice_id>`, source marker, and voice ID only.
- Produces `RemoteTTSProvider.get_audio(text: str) -> str` that calls `RemoteStudioClient.synthesize`, writes a temporary audio file, and returns its path.
- Produces `sync_remote_providers(context, voices, previous_ids)` that creates/updates new providers and disables missing providers without deleting them.

- [ ] **Step 1: Inspect the installed AstrBot ProviderManager contract** and record the exact create/update configuration shape in the test fixture; do not assume the current local GSV provider accepts custom headers.
- [ ] **Step 2: Write failing tests** for one-provider-per-voice IDs, no address/token/path in provider config, correct `voice_id` payload, and preservation of manually disabled provider state.
- [ ] **Step 3: Implement the remote provider adapter** against the verified AstrBot contract. It must resolve the current remote config at request time so changing the address or Token does not require recreating all providers.
- [ ] **Step 4: Add typed exception handling** so `get_audio` logs a masked error and raises a provider-level failure that existing `speech_output.py` catches as text-only degradation.
- [ ] **Step 5: Run `pytest tests/test_remote_provider.py -v`** and verify pass.
- [ ] **Step 6: Commit** `feat: add remote voice providers`.

### Task 4: Wire Plugin Lifecycle, APIs, and Mode Isolation

**Files:**
- Modify: `main.py`
- Modify: `voice_clone_flow/gpt_sovits/provider.py` only if shared ProviderManager helpers need extraction
- Test: `tests/test_remote_mode.py`

**Interfaces:**
- Registers `GET /<plugin>/remote/status`, `POST /<plugin>/remote/test`, and `POST /<plugin>/remote/sync`.
- `remote/status` returns mode, `configured`, connection state, last check/sync timestamps, masked token, and remote voice/provider summaries.
- `remote/test` validates URL and Token through `/api/health` without syncing or changing providers.
- `remote/sync` calls `/api/voices`, upserts metadata, updates providers, and disables missing remote providers.

- [ ] **Step 1: Write failing lifecycle tests** for local startup not calling remote, remote startup not calling `GPTSoVITSAdapter.probe/ensure_service`, test endpoint not mutating providers, and sync endpoint mutating only after explicit request.
- [ ] **Step 2: Implement plugin initialization** with separate local and remote state objects; load persisted mode on restart; keep local GPT objects constructed for local-mode compatibility but guard all start/install/train web actions in remote mode.
- [ ] **Step 3: Add endpoint handlers** with status-code mapping: 400 invalid config, 401 auth failure, 409 busy, 502 remote protocol/service failure, and 504 timeout. Return masked errors only.
- [ ] **Step 4: Implement mode transition handling** to enable/disable local and remote Provider groups without deleting rows or overriding user-disabled state.
- [ ] **Step 5: Run focused mode tests** and a local-mode regression subset; verify no remote request occurs in local mode.
- [ ] **Step 6: Commit** `feat: wire remote mode lifecycle and APIs`.

### Task 5: Add Management Page Controls

**Files:**
- Modify: `pages/voice-clone/index.html`
- Modify: `pages/voice-clone/app.js`
- Modify: `pages/voice-clone/style.css`
- Test: `tests/test_remote_mode.py` and browser smoke check

**Interfaces:**
- Page consumes the three remote endpoints from Task 4.
- Page displays explicit mode switch, Studio URL, plain-text Token, timeout, test/sync controls, connection state, timestamps, error summary, and read-only remote voice metadata.

- [ ] **Step 1: Add failing DOM assertions** for the top mode control, fixed recommendation text, remote fields, test/sync buttons, and local-section visibility classes.
- [ ] **Step 2: Implement mode-aware rendering** while preserving existing local controls and current page styling; remote mode hides local install/train/path actions and local mode hides remote controls.
- [ ] **Step 3: Implement save/test/sync actions** with disabled/loading states, status messages, and no raw Token in API response rendering or browser console logs.
- [ ] **Step 4: Add read-only voice table** showing name, ID, language, status, reference text and remote paths without edit/open-folder controls.
- [ ] **Step 5: Run a local browser smoke check** against the plugin page and verify both modes at desktop and narrow viewport widths.
- [ ] **Step 6: Commit** `feat: add remote studio management UI`.

### Task 6: Preserve Sentence-Level QQ Streaming Behavior and Cleanup

**Files:**
- Modify: `voice_clone_flow/speech_output.py` only if provider failures or temporary audio lifecycle require a narrow adapter hook
- Modify: `voice_clone_flow/remote_provider.py`
- Test: `tests/test_remote_provider.py`, `tests/test_remote_mode.py`

**Interfaces:**
- `RemoteTTSProvider.get_audio` returns a complete temporary file for one sentence; cleanup occurs after the existing `Record` send lifecycle or through the project’s temporary-file cleanup helper.

- [ ] **Step 1: Write failing tests** proving text is sent first, sentences remain sequential, each remote sentence starts its own request, and one failed sentence does not cancel later text-only behavior.
- [ ] **Step 2: Implement only the minimal temporary-file ownership needed**; do not change sentence splitting or QQ message composition.
- [ ] **Step 3: Run existing speech-output tests plus new remote tests** and verify the current behavior remains unchanged.
- [ ] **Step 4: Commit** `fix: preserve sentence-level remote audio delivery`.

### Task 7: Documentation, Full Verification, and Studio Contract Fixture

**Files:**
- Modify: `README.md`
- Create: `docs/remote-studio-api.md`
- Test: `tests/test_remote_studio.py`, full test suite

- [ ] **Step 1: Document deployment topology**: AstrBot/NapCat/server role, separate Windows Studio role, server-perspective address examples, FRP assumption, explicit Token, remote-mode limitations, and current sentence-level QQ behavior.
- [ ] **Step 2: Document exact API schemas** for `/api/health`, `/api/voices`, and `/api/tts`, including required headers, `voice_id`, metadata fields, WAV content type, chunked transfer, status codes, and 429 semantics.
- [ ] **Step 3: Add a deterministic fake Studio fixture** that serves health, voice sync, chunked WAV, auth failure, timeout and busy responses without real GPU dependencies.
- [ ] **Step 4: Run `pytest -q`** and record the result; run `git diff --check`.
- [ ] **Step 5: Run a manual two-machine smoke checklist**: server reaches FRP address, health succeeds, sync creates multiple Providers, one voice synthesizes, Studio shutdown leaves AstrBot alive, and local mode still trains/synthesizes.
- [ ] **Step 6: Commit** `docs: document remote studio deployment and API`.

## Self-Review Checklist

- Spec coverage: mode isolation (Tasks 1, 4, 5), address and Token semantics (Tasks 1, 4, 5, 7), voice metadata (Task 2), one Provider per voice (Task 3), streaming/QQ behavior (Task 6), errors and status (Tasks 1, 4, 5, 7), regression and deployment acceptance (Task 7).
- No placeholder implementation steps remain; every task names files, interfaces, tests and expected commands.
- Provider and client names are consistent: `RemoteStudioConfig`, `RemoteStudioClient`, `RemoteTTSProvider`, `build_remote_provider_config`.
- The plan does not add remote training, FRP management, GPT-SoVITS model changes, or unfinished QQ-message streaming.
