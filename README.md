<div align="center">

# VoiceClone Flow

**从音视频素材到音色管理**

面向 AstrBot 的 GPT-SoVITS 音色生产与接入工作流

[![AstrBot](https://img.shields.io/badge/AstrBot-%3E%3D4.24%2C%3C5-4c8bf5)](https://github.com/AstrBotDevs/AstrBot)
[![GPT-SoVITS](https://img.shields.io/badge/GPT--SoVITS-v2Pro-6f42c1)](https://github.com/RVC-Boss/GPT-SoVITS)
[![Platform](https://img.shields.io/badge/platform-Windows-0078d4)](#运行要求)
[![License](https://img.shields.io/badge/license-AGPL--3.0-555)](LICENSE)

</div>

VoiceClone Flow 将音视频素材处理、语音标注、GPT-SoVITS 训练、音色管理和 AstrBot TTS Provider 接入整合为一条完整工作流。

用户可以直接上传视频或音频素材，经由 FFmpeg、HT-Demucs、VAD 和 AstrBot STT Provider 生成可审核的语音片段与文字标注，完成 GPT-SoVITS 训练后，将音色登记为 AstrBot 可直接使用的 `GSV TTS(Local)` Provider。

运行环境、模型、训练素材和音色成果统一保存在 AstrBot 插件数据目录，不会写入插件源码或 Git 仓库。

## 功能概览

| 模块 | 功能 |
| --- | --- |
| 素材处理 | 支持常见视频和音频格式，自动提取标准训练音频 |
| 人声准备 | 使用 HT-Demucs ONNX 分离人声，通过 VAD 切分有效语音 |
| 语音标注 | 复用 AstrBot 已配置的 STT Provider 批量生成文字标注 |
| 片段审核 | 支持逐段试听、文本修订、片段选择与排除 |
| 模型训练 | 生成 GPT-SoVITS 数据集，提供训练预设、自定义 Epoch 和实时进度 |
| 音色管理 | 管理训练成果与外部音色，维护参考音频、文本和语言 |
| Provider 接入 | 创建或更新 AstrBot `GSV TTS(Local)` Provider |
| 消息输出 | 支持中文文字配合中文或日语语音，并按顺序发送长回复 |
| 数据清理 | 定期清理临时任务数据，保留训练成果与已登记音色 |

## 工作流程

```mermaid
flowchart LR
    A["视频 / 音频素材"] --> B["FFmpeg 音频提取"]
    B --> C["HT-Demucs 人声分离"]
    C --> D["VAD 语音切分"]
    D --> E["AstrBot STT 标注"]
    E --> F["试听与文本审核"]
    F --> G["生成训练数据"]
    G --> H["GPT-SoVITS 训练"]
    H --> I["音色登记"]
    I --> J["AstrBot TTS Provider"]
```

## 运行要求

- AstrBot `>=4.24,<5`
- Windows 10/11
- 已在 AstrBot 中启用的语音转文字（STT/ASR）Provider
- 足够的磁盘空间用于 GPT-SoVITS 运行包、模型和训练结果
- 建议使用 NVIDIA GPU 进行 GPT-SoVITS 训练和推理

FFmpeg、人声分离模型和 GPT-SoVITS 运行包均按需下载，不包含在插件仓库或插件市场安装包中。

插件当前专注于 **GPT-SoVITS v2Pro**，暂不作为通用多模型训练平台使用。

## 安装

### 从 AstrBot 插件市场安装

在 AstrBot 插件市场中搜索 `VoiceClone Flow`，安装后重载插件。

### 手动安装

```bash
cd AstrBot/data/plugins
git clone https://github.com/TKGEKKOU/astrbot_plugin_voice_clone_flow.git
```

安装完成后，返回 AstrBot 插件管理页重载插件，或重新启动 AstrBot。

## 使用方法

### 1. 配置 STT Provider

VoiceClone Flow 复用 AstrBot 已有的 STT Provider，不重复保存 API Key，也不内置云端语音识别服务。

使用前需要：

1. 进入 AstrBot 的“模型提供商”页面。
2. 新增并启用一个语音转文字（STT）Provider。
3. 在 VoiceClone Flow 插件配置中选择该 ASR Provider。
4. 保存配置并重新进入插件页面。

素材语言应按音频实际内容选择中文、日语或英语。该语言会用于生成 GPT-SoVITS 训练标注和音色配置。

### 2. 准备运行环境

进入 VoiceClone Flow 插件页面，在“运行环境”区域完成检查：

- 检测或下载 FFmpeg
- 下载 HT-Demucs 人声分离模型
- 下载并安装 GPT-SoVITS v2Pro 运行包
- 检查或启动 GPT-SoVITS TTS 服务

下载的运行环境与模型保存在 AstrBot 插件数据目录，不会进入插件仓库。

### 3. 处理音视频素材

上传拥有合法使用权的视频或音频素材，选择 ASR Provider 和素材语言后开始处理。

插件将依次执行：

```text
音频提取
-> 人声分离
-> VAD 语音切分
-> 批量 STT 标注
-> 生成可审核片段
```

![素材处理与运行环境](./assets/material-processing.png)

### 4. 审核训练片段

素材处理完成后，可以直接播放每个语音片段，并修改对应文字。

建议重点检查：

- 删除包含背景音乐、串音、爆音或明显噪声的片段
- 删除内容不完整或发音模糊的片段
- 修正 STT 产生的错字、漏字和标点
- 确保参考文字与实际语音完全一致
- 尽量保留音量稳定、音色一致的片段

确认片段后，点击“生成训练数据”。

训练素材的质量通常比单纯增加训练轮数更重要。

### 5. 训练 GPT-SoVITS 音色

生成训练数据后，可以选择预设档位或自定义 GPT、SoVITS Epoch。

| 训练档位 | GPT Epoch | SoVITS Epoch | 适用场景 |
| --- | ---: | ---: | --- |
| 轻量训练 | 5 | 10 | 验证数据和训练链路的最低可用配置 |
| 快速训练 | 10 | 20 | 低配置设备或快速迭代 |
| 标准训练 | 15 | 30 | 默认推荐，平衡训练时间和效果 |
| 增强训练 | 20 | 50 | 素材质量较好，需要提升稳定性 |
| 精细训练 | 30 | 100 | 算力和时间充足时使用 |
| 自定义 | 自定义 | 自定义 | 根据数据量和设备性能自行调整 |

训练期间，页面会显示：

- 当前训练阶段
- GPT / SoVITS 训练进度
- Epoch 和 Step
- 训练速度 `step/s`
- 预计剩余时间
- 运行日志摘要

更多 Epoch 不一定带来更好的效果。首次使用建议先通过轻量训练验证完整链路。

### 6. 登记音色并接入 AstrBot

训练完成后，插件会整理 GPT 和 SoVITS 权重，并生成可管理的音色目录。

在音色管理区域：

1. 选择训练完成或外部导入的音色。
2. 检查 GPT 权重和 SoVITS 权重。
3. 设置音色语言。
4. 选择参考音频。
5. 检查并修改参考音频文本。
6. 保存参考信息。
7. 点击“更新并启用此 TTS Provider”。

![音色管理与 Provider 接入](./assets/voice-management.png)

插件会创建或更新以下 AstrBot Provider：

```text
Provider ID: voice_clone_flow_gsv
Provider 类型: GSV TTS(Local)
```

之后在 AstrBot 对应会话或配置中选择该 TTS Provider，并确保 GPT-SoVITS TTS 服务处于运行状态，即可使用生成的音色。

## 外部音色导入

已有的 GPT-SoVITS 训练成果可以放入：

```text
AstrBot/data/plugin_data/astrbot_plugin_voice_clone_flow/voices/
```

音色目录通常需要包含：

```text
voice-name/
├── gpt.ckpt
├── sovits.pth
└── reference.wav
```

返回插件页面点击刷新后，插件会尝试发现外部音色。

导入后请重新检查：

- GPT 和 SoVITS 权重路径
- 参考音频
- 参考音频文本
- 音色语言

确认信息无误后，再更新对应的 TTS Provider。

## 多语言文字与语音消息

VoiceClone Flow 支持文字内容与语音内容分离输出。

当前提供以下组合：

| 可见文字 | 语音内容 | 输出行为 |
| --- | --- | --- |
| 中文 | 中文 | 先发送中文文字，再补发中文语音 |
| 中文 | 日语 | 先发送中文文字，翻译后补发日语语音 |

长回复可以按句切分为多条语音，并按照原始文本顺序依次发送。

当日语翻译或语音合成失败时，插件会保留已经发送的中文文字，不会使用错误语言继续朗读。

该功能可在插件配置中的“中文文字与日语语音”区域启用和调整。

## 数据目录

插件运行数据统一保存在：

```text
AstrBot/data/plugin_data/astrbot_plugin_voice_clone_flow/
```

主要目录：

| 目录 | 内容 | 自动清理 |
| --- | --- | --- |
| `runtime/` | FFmpeg 和 GPT-SoVITS 运行环境 | 否 |
| `models/` | 人声分离模型 | 否 |
| `downloads/` | 尚未完成或可复用的下载文件 | 按安装状态处理 |
| `tasks/` | 素材处理任务和中间文件 | 按插件配置 |
| `datasets/` | GPT-SoVITS 训练数据 | 按任务状态处理 |
| `voices/` | 训练成果和外部导入音色 | 否 |
| `logs/` | GPT-SoVITS 服务和训练日志 | 按运行产生 |

临时素材会按照插件配置定期检查和清理，训练成果及已登记音色不会自动删除。

迁移或更新 AstrBot 前，建议备份：

```text
AstrBot/data/plugin_data/astrbot_plugin_voice_clone_flow/voices/
```

## 常见问题

<details>
<summary><strong>ASR Provider 无法选择</strong></summary>

请确认 AstrBot 中已经创建并启用 STT Provider，并在插件配置中选择后保存。

聊天模型、STT Provider 和 TTS Provider 是三种不同类型，不能相互替代。

</details>

<details>
<summary><strong>运行环境显示未就绪</strong></summary>

请展开插件页面顶部的“运行环境”，分别检查：

- FFmpeg
- 人声分离模型
- GPT-SoVITS 运行包
- GPT-SoVITS TTS 服务

这些组件拥有独立状态，需要根据页面提示逐项处理。

</details>

<details>
<summary><strong>训练时间很长</strong></summary>

训练时间取决于 GPU 性能、训练片段数量和 Epoch。

首次使用建议先运行轻量训练，确认数据和训练链路没有问题后，再逐步提高训练档位。

</details>

<details>
<summary><strong>更新 Provider 后没有语音</strong></summary>

请检查：

- GPT-SoVITS TTS 服务是否正在运行
- 当前会话是否选择了 `voice_clone_flow_gsv`
- 参考音频、参考文本和语言是否匹配
- 当前消息平台是否支持 AstrBot `Record` 语音消息

</details>

<details>
<summary><strong>只有中文文字，没有日语语音</strong></summary>

请检查当前会话聊天模型、翻译超时、语音目标语言和 TTS Provider 的 `text_lang`。

翻译失败时只发送中文文字是插件的预期降级行为。

</details>

## 声音授权与安全声明

本插件仅用于处理你本人拥有或已经获得明确授权的声音素材。

不得使用本插件：

- 冒充或误导他人
- 生成、传播未授权语音
- 实施诈骗、骚扰、诽谤或身份欺骗
- 绕过平台风控、身份验证或内容审核
- 从事任何违反法律法规、平台规则或素材许可的行为

如果你不确定某个声音样本是否允许使用，请不要上传、训练或合成。

使用者应自行确认声音素材的授权范围，并承担因使用本插件产生的相应责任。

GPT-SoVITS、FFmpeg、人声分离模型及兼容补丁分别受其上游许可证约束，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 问题反馈

提交问题时，请尽量提供：

- AstrBot 版本
- VoiceClone Flow 插件版本
- 出现问题的操作阶段
- 已脱敏的错误日志
- 可稳定复现的操作步骤

请勿公开上传 API Key、未授权声音、私人训练素材或包含个人隐私的日志。

- GitHub Issues：[提交问题](https://github.com/TKGEKKOU/astrbot_plugin_voice_clone_flow/issues)
- QQ：**3198260896**

## 许可证

本项目采用 [GNU Affero General Public License v3.0](LICENSE)。
