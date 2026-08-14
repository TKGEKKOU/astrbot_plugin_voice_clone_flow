# VoiceClone Flow

**从音视频素材到音色管理**

[![AstrBot](https://img.shields.io/badge/AstrBot-%3E%3D4.24%2C%3C5-4c8bf5)](https://github.com/AstrBotDevs/AstrBot)
[![GPT-SoVITS](https://img.shields.io/badge/GPT--SoVITS-v2Pro-6f42c1)](https://github.com/RVC-Boss/GPT-SoVITS)
[![License](https://img.shields.io/badge/license-AGPL--3.0-555)](LICENSE)

VoiceClone Flow 是一个面向 AstrBot 的 GPT-SoVITS 音色工作流插件，一站式完成音视频素材音频提取、人声分离、语音切分、STT 标注、片段审核、GPT-SoVITS 训练、音色登记和 AstrBot TTS Provider 接入。

插件当前专注于 GPT-SoVITS。运行环境、模型、训练素材和音色成果保存在 AstrBot 插件数据目录，不会写入插件源码或 Git 仓库。

## 核心流程

```text
视频/音频素材
  -> FFmpeg 提取音频
  -> HT-Demucs 人声分离
  -> VAD 语音切分
  -> AstrBot STT Provider 标注
  -> 片段试听与文本审核
  -> 生成训练数据
  -> GPT-SoVITS 训练
  -> 音色登记
  -> AstrBot GSV TTS(Local) Provider
```

## 页面预览

素材处理页面：

![素材处理页面](./assets/material-processing.png)

音色管理与 TTS Provider 页面：

![音色管理页面](./assets/voice-management.png)

## 使用前准备

- AstrBot `>=4.24,<5`
- Windows 10/11
- 一个已经在 AstrBot“模型提供商”中启用的语音转文字（STT/ASR）Provider
- 可运行 GPT-SoVITS 的环境，建议使用 NVIDIA GPU
- 足够的磁盘空间用于运行包、模型和训练结果

FFmpeg、人声分离模型和 GPT-SoVITS 运行包均按需下载，不包含在插件仓库或插件市场安装包中。

### STT Provider

插件复用 AstrBot 已配置的 STT Provider，不重复保存 API Key，也不内置云端语音识别服务。安装插件后，在插件配置页选择对应的 ASR Provider；素材语言请按实际内容选择中文、日语或英语。

## 安装

在 AstrBot 插件市场搜索 `VoiceClone Flow`，或手动安装：

```bash
cd AstrBot/data/plugins
git clone https://github.com/TKGEKKOU/astrbot_plugin_voice_clone_flow.git
```

安装后在 AstrBot 插件管理页重载插件。

## 基本使用

1. 在插件页面准备运行环境，检查或下载 FFmpeg、人声分离模型和 GPT-SoVITS 运行包。
2. 上传视频或音频素材，选择 ASR Provider，确认拥有声音素材的使用权后开始处理。
3. 试听并审核切分片段，修订识别文本，点击“生成训练数据”。
4. 选择训练预设或自定义 GPT/SoVITS Epoch，开始训练并查看实时进度。
5. 训练完成后登记音色，检查参考音频、参考文本和语言，点击“更新并启用此 TTS Provider”。
6. 在 AstrBot 对应会话或配置中选择 `voice_clone_flow_gsv`，即可使用生成的音色。

训练结果和外部导入音色位于：

```text
AstrBot/data/plugin_data/astrbot_plugin_voice_clone_flow/voices/
```

外部 GPT-SoVITS 音色可直接放入该目录，返回插件页面刷新后登记使用。

## 消息输出

支持输出多语言文字与语音消息组合。当前可配置为保留中文文字，并补发中文或日语语音；长文本会按顺序分段发送。翻译或语音合成失败时，仍会发送中文文字，不会继续朗读错误语言。

## 数据与清理

插件数据默认存放在：

```text
AstrBot/data/plugin_data/astrbot_plugin_voice_clone_flow/
```

临时素材按插件配置定期清理，训练成果和已登记音色不会自动删除。迁移或更新 AstrBot 前，建议备份 `voices/` 目录。

## 声音授权与安全声明

仅上传你本人拥有或已获得明确授权的声音素材。不得使用本插件冒充他人、误导他人、生成未授权语音、实施诈骗、骚扰、诽谤、绕过平台风控或其他违法违规行为。

如果你不确定某个声音样本是否允许使用，请不要上传或合成。使用者应自行遵守所在地法律、素材许可和平台规则。GPT-SoVITS、FFmpeg、人声分离模型及兼容补丁分别受其上游许可证约束，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 问题反馈

请通过 [GitHub Issues](https://github.com/TKGEKKOU/astrbot_plugin_voice_clone_flow/issues) 提交问题，或联系作者 QQ：**3198260896**。反馈时请附 AstrBot 版本、插件版本、操作阶段和已脱敏日志；请勿上传 API Key、未授权声音或私人训练素材。

## 许可证

本项目采用 [GNU Affero General Public License v3.0](LICENSE)。
