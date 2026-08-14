# VoiceClone Flow

从视频或音频素材到可用 GPT-SoVITS 音色的一站式 AstrBot 插件。

VoiceClone Flow 在 AstrBot WebUI 内串联素材处理、训练数据审核、GPT-SoVITS 训练、音色管理和 TTS Provider 接入。运行环境、模型、训练素材及音色成果全部存放在 AstrBot 的插件数据目录中，不写入插件源码目录。

## 工作流程

```text
视频或音频素材
  -> FFmpeg 提取音频
  -> HT-Demucs 人声分离
  -> VAD 语音切片
  -> AstrBot STT Provider 批量标注
  -> 试听、编辑和筛选片段
  -> 生成 GPT-SoVITS 训练数据
  -> GPT / SoVITS 训练
  -> 注册音色并更新 AstrBot TTS Provider
```

## 主要功能

- 上传常见视频或音频格式，自动提取并清理人声。
- 复用 AstrBot 已配置的 STT Provider，不在插件中重复保存 API Key。
- 逐段试听、修改标注和选择训练片段。
- 提供轻量、快速、标准、增强、精细五档训练预设，并支持自定义 Epoch。
- 下载、检测、启动和停止 GPT-SoVITS 本地后端。
- 管理训练完成或外部导入的 GPT/SoVITS 模型、参考音频与参考文本。
- 一键更新并启用 AstrBot `GSV TTS(Local)` Provider。
- 可选“中文文字 + 日语语音”输出；翻译失败时仅保留中文文字。
- 自动清理过期临时素材，训练成果和已注册音色不会被自动删除。

## 环境要求

- AstrBot `>=4.24,<5`
- Windows 10/11
- Python 依赖由 AstrBot 按 `requirements.txt` 安装
- GPT-SoVITS 训练建议使用 NVIDIA GPU；具体显存需求取决于训练档位、素材长度和所下载的运行包
- 至少配置一个可用的 AstrBot STT Provider

FFmpeg、人声分离模型和 GPT-SoVITS 运行包可在插件页面按需下载，不包含在 Git 仓库及市场安装包中。

## 安装

### 从插件市场安装

在 AstrBot WebUI 的插件市场搜索 `VoiceClone Flow`，安装后重载插件。

### 手动安装

```bash
cd AstrBot/data/plugins
git clone https://github.com/TKGEKKOU/astrbot_plugin_voice_clone_flow.git
```

回到 AstrBot 插件管理页，重载插件或重启 AstrBot。

## 使用

1. 在 AstrBot 的模型提供商页面配置并验证 STT Provider。
2. 在插件配置中选择该 STT Provider，并按需调整素材限制、语音语言和自动清理策略。
3. 从插件管理页进入 VoiceClone Flow 页面，检查或下载 FFmpeg、人声分离模型和 GPT-SoVITS。
4. 上传已获授权的视频或音频，等待人声分离、切片和批量标注完成。
5. 试听片段，修正文本并取消不适合作为训练数据的片段。
6. 生成训练数据，选择训练档位和音色名称后开始训练。
7. 训练完成后选择音色，核对参考音频、参考文本和语言，点击“更新并启用此 TTS Provider”。
8. 在 AstrBot 会话配置中启用该 TTS Provider，即可向支持语音消息的平台输出克隆语音。

## 数据目录

所有大文件和用户数据位于：

```text
AstrBot/data/plugin_data/astrbot_plugin_voice_clone_flow/
```

主要子目录包括：

- `runtime/`：FFmpeg 与 GPT-SoVITS 运行环境
- `models/`：人声分离模型
- `tasks/`：素材处理任务
- `voices/`：训练成果和导入音色
- `logs/`：GPT-SoVITS 服务日志

卸载或更新插件源码前，请按需备份 `voices/`。不要把插件数据目录提交到 Git。

## 音色授权与安全

仅处理你本人拥有或已获得明确授权的声音素材。请勿将克隆音色用于冒充、欺诈、骚扰、规避身份验证或其他违法用途。使用者应自行遵守所在地法律、素材许可和平台规则。

插件下载的 GPT-SoVITS、FFmpeg 和模型文件分别受其上游许可证约束，详情见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 许可证

本项目采用 [GNU Affero General Public License v3.0](LICENSE)。
