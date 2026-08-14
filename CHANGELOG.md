# 更新日志

本项目遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [0.2.2] - 2026-08-14

### 修复

- 修复 Linux 官方源码已不含 `tools/download_models.py` 时静默跳过预训练模型、导致安装后启动失败的问题。
- 修复断点续传遇到不支持 Range 的下载源时追加文件并损坏压缩包的问题。
- Linux 启停改为管理完整进程组，降低残留子进程占用端口的风险。

### 改进

- Linux 一键安装直接下载、解压并校验 v2Pro 训练与推理所需预训练模型。
- Linux 源码固定到已审计的 GPT-SoVITS 提交，避免上游主分支漂移破坏安装流程。
- 依赖安装实时回传最新输出；安装状态补充系统、架构、阶段、百分比、服务 PID 和日志位置。
- Linux 自动检测 NVIDIA GPU；无可用驱动时回退到 CPU 与全精度推理配置。
- 取消安装时终止受插件管理的长时间安装命令。
- README 明确一键安装内容、平台检测时机和服务器基础环境边界。

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
# 0.2.1

- Linux 可在插件页面内下载静态 FFmpeg，无需使用系统包管理器。
- GPT-SoVITS 环境创建失败时自动准备 uv、下载 Python 3.11，并重建残缺的虚拟环境。
- 区分完整安装与残留目录，安装失败后仍可删除半成品或重新下载。
- 页面实时显示 Linux 工具下载、Python 准备和环境创建阶段，并返回完整命令错误。

# 0.2.0

- 新增 Windows/Linux 自动平台检测，并在下载、启动和训练操作前重新检查环境。
- Windows 保留 v2Pro 整合包流程；Linux 改用 GPT-SoVITS 官方源码和插件独立 Python 虚拟环境。
- Linux 自动使用当前 Python 创建 `.venv`，失败时通过已安装的 `uv` 获取 Python 3.11。
- Linux 不再执行 `7zr.exe`、`taskkill` 或 Windows runtime 补丁。
- FFmpeg、服务进程、训练路径和音色目录操作完成跨平台适配。
