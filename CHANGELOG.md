# 更新日志

本项目遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [0.3.0] - 2026-08-16

### 新增

- 新增可选远程工作室模式：服务器上的 AstrBot 可通过 FRP/HTTP(S) 调用另一台电脑上的 VoiceClone Studio。
- 新增远程音色同步和每音色独立 Provider。
- 远程模式不启动本地 GPT-SoVITS，故障时沿用文字降级。

## [0.1.0] - 2026-08-14

### 新增

- 从视频或音频素材到 GPT-SoVITS 可用音色的完整工作流。
- FFmpeg 提取、HT-Demucs 人声分离、VAD 切片和 AstrBot STT Provider 批量标注。
- 训练片段试听、文本修订、筛选及 GPT-SoVITS 数据集生成。
- 五档训练预设、自定义 Epoch 和实时训练进度。
- GPT-SoVITS 运行环境安装、状态检测、服务启停及日志反馈。
- 训练音色与外部音色发现、参考信息编辑和 AstrBot GSV TTS Provider 更新。
- 中文文字配合中文或日语语音输出，并保证多段语音顺序。
- 临时素材定时清理，保留训练成果和已注册音色。

### 文档

- 展示名称更新为 `VoiceClone Flow | 从音视频素材到音色管理`，并明确当前仅支持 GPT-SoVITS。
- 增加 AstrBot STT Provider 前置配置、完整训练操作、音色登记和 TTS Provider 接入指南。
- 补充多语言文字与语音消息组合、训练预设、数据清理和常见问题说明。
- 市场分类调整为“工具”。

[0.1.0]: https://github.com/TKGEKKOU/astrbot_plugin_voice_clone_flow/releases/tag/v0.1.0
