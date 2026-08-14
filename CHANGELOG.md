# 更新日志

本项目遵循[语义化版本](https://semver.org/lang/zh-CN/)。

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
# 0.2.0

- 新增 Windows/Linux 自动平台检测，并在下载、启动和训练操作前重新检查环境。
- Windows 保留 v2Pro 整合包流程；Linux 改用 GPT-SoVITS 官方源码和插件独立 Python 虚拟环境。
- Linux 自动使用当前 Python 创建 `.venv`，失败时通过已安装的 `uv` 获取 Python 3.11。
- Linux 不再执行 `7zr.exe`、`taskkill` 或 Windows runtime 补丁。
- FFmpeg、服务进程、训练路径和音色目录操作完成跨平台适配。
