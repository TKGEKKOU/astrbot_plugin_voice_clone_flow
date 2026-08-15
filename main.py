import asyncio
import base64
import shutil
from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.api.web import PluginUploadFile, error_response, json_response, request
from astrbot.core.utils.astrbot_path import get_astrbot_data_path
from starlette.responses import HTMLResponse

if __package__:
    from .voice_clone_flow import PLUGIN_NAME
    from .voice_clone_flow.astrbot_api import ASRTestError, list_stt_providers, run_stt_test
    from .voice_clone_flow.services.studio import VoiceCloneStudio
    from .voice_clone_flow.separator_model import inspect_separator_model
    from .voice_clone_flow.material_pipeline import MaterialPipeline
    from .voice_clone_flow.dataset import DatasetRow, export_gpt_sovits_dataset
    from .voice_clone_flow.review_store import ReviewStore
    from .voice_clone_flow.separator_resources import SeparatorResourceManager
    from .voice_clone_flow.runtime_resources import FFmpegResourceManager
    from .voice_clone_flow.storage.json_repository import JsonTaskRepository
    from .voice_clone_flow.gpt_sovits import GPTSoVITSAdapter, GPTSoVITSConfig
    from .voice_clone_flow.gpt_sovits.install import GPTSoVITSInstallManager
    from .voice_clone_flow.gpt_sovits.synthesis import GPTSoVITSSynthesisService
    from .voice_clone_flow.gpt_sovits.voices import VoiceAsset, VoiceRegistry
    from .voice_clone_flow.gpt_sovits.training import TrainingDataInvalid, TrainingService
    from .voice_clone_flow.gpt_sovits.presets import get_training_preset, validate_training_epochs
    from .voice_clone_flow.gpt_sovits.provider import build_gsv_provider_config, apply_gsv_provider
    from .voice_clone_flow.path_actions import open_voice_directory, open_voices_root
    from .voice_clone_flow.data_cleanup import build_cleanup_preview, remove_cleanup_items
    from .voice_clone_flow.speech_output import BilingualTTSDecorator, JapaneseSpeechTranslator
    from .voice_clone_flow.platform_runtime import detect_platform_profile
else:
    from voice_clone_flow import PLUGIN_NAME
    from voice_clone_flow.astrbot_api import ASRTestError, list_stt_providers, run_stt_test
    from voice_clone_flow.services.studio import VoiceCloneStudio
    from voice_clone_flow.separator_model import inspect_separator_model
    from voice_clone_flow.material_pipeline import MaterialPipeline
    from voice_clone_flow.dataset import DatasetRow, export_gpt_sovits_dataset
    from voice_clone_flow.review_store import ReviewStore
    from voice_clone_flow.separator_resources import SeparatorResourceManager
    from voice_clone_flow.runtime_resources import FFmpegResourceManager
    from voice_clone_flow.storage.json_repository import JsonTaskRepository
    from voice_clone_flow.gpt_sovits import GPTSoVITSAdapter, GPTSoVITSConfig
    from voice_clone_flow.gpt_sovits.install import GPTSoVITSInstallManager
    from voice_clone_flow.gpt_sovits.synthesis import GPTSoVITSSynthesisService
    from voice_clone_flow.gpt_sovits.voices import VoiceAsset, VoiceRegistry
    from voice_clone_flow.gpt_sovits.training import TrainingDataInvalid, TrainingService
    from voice_clone_flow.gpt_sovits.presets import get_training_preset, validate_training_epochs
    from voice_clone_flow.gpt_sovits.provider import build_gsv_provider_config, apply_gsv_provider
    from voice_clone_flow.path_actions import open_voice_directory, open_voices_root
    from voice_clone_flow.data_cleanup import build_cleanup_preview, remove_cleanup_items
    from voice_clone_flow.speech_output import BilingualTTSDecorator, JapaneseSpeechTranslator
    from voice_clone_flow.platform_runtime import detect_platform_profile


class VoiceCloneFlowPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.data_dir = Path(get_astrbot_data_path()) / "plugin_data" / PLUGIN_NAME
        self.stt_provider_id = str(config.get("stt_provider_id", "")).strip()
        self.separator_model_path = str(config.get("separator_model_path", "")).strip()
        self.separator_model_url = str(config.get("separator_model_url", "")).strip()
        self.studio: VoiceCloneStudio
        self.background_tasks: set[asyncio.Task] = set()
        self.gpt_starting = False
        self.gpt_start_error = ""
        cleanup_settings = config.get("automatic_cleanup", {}) if isinstance(config.get("automatic_cleanup", {}), dict) else {}
        self.cleanup_enabled = bool(cleanup_settings.get("enabled", True))
        self.cleanup_retention_days = max(1, int(cleanup_settings.get("retention_days", 1)))
        self.cleanup_interval_hours = max(1, int(cleanup_settings.get("interval_hours", 24)))
        self.gpt_config = GPTSoVITSConfig(self.data_dir)
        gpt_settings = config.get("gpt_sovits", {}) if isinstance(config.get("gpt_sovits", {}), dict) else {}
        self.gpt_config.save(api_port=int(gpt_settings.get("api_port", 9880)))
        self.gpt_adapter = GPTSoVITSAdapter(self.gpt_config, self.data_dir)
        self.gpt_install = GPTSoVITSInstallManager(self.data_dir, self.gpt_config)
        self.gpt_synthesis = GPTSoVITSSynthesisService(self.gpt_adapter)
        self.voice_registry = VoiceRegistry(self.data_dir)
        self.gpt_training = TrainingService(self.data_dir, self.gpt_config, self.voice_registry)
        speech_settings = config.get("speech_translation", {})
        if not isinstance(speech_settings, dict):
            speech_settings = {}
        self.speech_decorator = None
        if bool(speech_settings.get("enabled", True)):
            translator = JapaneseSpeechTranslator(
                context,
                timeout_seconds=float(speech_settings.get("timeout_seconds", 15)),
            )
            self.speech_decorator = BilingualTTSDecorator(
                context,
                translator,
                clean_special_characters=bool(
                    speech_settings.get("clean_special_characters", True)
                ),
                max_voice_chars=int(speech_settings.get("max_voice_chars", 300)),
                target_language=str(speech_settings.get("target_language", "auto")),
            )
        download_urls = (self.separator_model_url,) if self.separator_model_url else None
        self.separator_resources = SeparatorResourceManager(
            self.data_dir,
            **({"download_urls": download_urls} if download_urls else {}),
        )
        self.ffmpeg_resources = FFmpegResourceManager(
            self.data_dir,
            str(config.get("ffmpeg_path", "")).strip(),
            str(config.get("ffmpeg_download_url", "")).strip() or None,
            configured_sha256=str(config.get("ffmpeg_sha256", "")).strip(),
        )
        context.register_web_api(
            f"/{PLUGIN_NAME}/debug", self.debug_page, ["GET"], "VoiceClone Flow development console"
        )
        context.register_web_api(
            f"/{PLUGIN_NAME}/stt/providers",
            self.page_stt_providers,
            ["GET"],
            "List STT providers for VoiceClone Flow",
        )
        context.register_web_api(
            f"/{PLUGIN_NAME}/stt/test/<provider_id>",
            self.page_stt_test,
            ["POST"],
            "Test STT provider with uploaded audio",
        )
        context.register_web_api(
            f"/{PLUGIN_NAME}/separator/status",
            self.page_separator_status,
            ["GET"],
            "Get voice separator model status",
        )
        context.register_web_api(f"/{PLUGIN_NAME}/separator/install", self.page_separator_install, ["POST"], "Install separator model")
        context.register_web_api(f"/{PLUGIN_NAME}/separator/delete", self.page_separator_delete, ["POST"], "Delete managed separator model")
        context.register_web_api(f"/{PLUGIN_NAME}/runtime/status", self.page_runtime_status, ["GET"], "Get runtime status")
        context.register_web_api(f"/{PLUGIN_NAME}/runtime/ffmpeg/install", self.page_ffmpeg_install, ["POST"], "Install FFmpeg")
        context.register_web_api(f"/{PLUGIN_NAME}/runtime/ffmpeg/delete", self.page_ffmpeg_delete, ["POST"], "Delete managed FFmpeg")
        context.register_web_api(f"/{PLUGIN_NAME}/gpt-sovits/status", self.page_gpt_status, ["GET"], "Get GPT-SoVITS status")
        context.register_web_api(f"/{PLUGIN_NAME}/gpt-sovits/install", self.page_gpt_install, ["POST"], "Install GPT-SoVITS")
        context.register_web_api(f"/{PLUGIN_NAME}/gpt-sovits/install/cancel", self.page_gpt_install_cancel, ["POST"], "Cancel GPT-SoVITS install")
        context.register_web_api(f"/{PLUGIN_NAME}/gpt-sovits/delete", self.page_gpt_delete, ["POST"], "Delete GPT-SoVITS")
        context.register_web_api(f"/{PLUGIN_NAME}/gpt-sovits/start", self.page_gpt_start, ["POST"], "Start GPT-SoVITS")
        context.register_web_api(f"/{PLUGIN_NAME}/gpt-sovits/stop", self.page_gpt_stop, ["POST"], "Stop GPT-SoVITS")
        context.register_web_api(f"/{PLUGIN_NAME}/gpt-sovits/voices", self.page_gpt_voices, ["GET"], "List voice assets")
        context.register_web_api(f"/{PLUGIN_NAME}/gpt-sovits/voices", self.page_gpt_voice_create, ["POST"], "Create voice asset")
        context.register_web_api(f"/{PLUGIN_NAME}/gpt-sovits/voices/<voice_id>", self.page_gpt_voice, ["GET"], "Get voice asset")
        context.register_web_api(f"/{PLUGIN_NAME}/gpt-sovits/voices/<voice_id>/reference", self.page_gpt_voice_reference, ["POST"], "Update voice reference")
        context.register_web_api(f"/{PLUGIN_NAME}/gpt-sovits/voices/<voice_id>/provider", self.page_gpt_provider, ["POST"], "Apply AstrBot GSV provider")
        context.register_web_api(f"/{PLUGIN_NAME}/gpt-sovits/voices/<voice_id>/open-folder", self.page_gpt_voice_folder, ["POST"], "Open voice folder")
        context.register_web_api(f"/{PLUGIN_NAME}/gpt-sovits/voices/open-folder", self.page_gpt_voices_folder, ["POST"], "Open voices root folder")
        context.register_web_api(f"/{PLUGIN_NAME}/gpt-sovits/synthesize", self.page_gpt_synthesize, ["POST"], "Synthesize voice")
        context.register_web_api(
            f"/{PLUGIN_NAME}/tasks/create/<provider_id>/<language>/<authorization>",
            self.page_create_task,
            ["POST"],
            "Create voice material task",
        )
        context.register_web_api(f"/{PLUGIN_NAME}/tasks", self.page_tasks, ["GET"], "List voice material tasks")
        context.register_web_api(f"/{PLUGIN_NAME}/tasks/<task_id>", self.page_task, ["GET"], "Get voice material task")
        context.register_web_api(f"/{PLUGIN_NAME}/tasks/<task_id>/audio/<audio_name>", self.page_task_audio, ["GET"], "Get review audio")
        context.register_web_api(f"/{PLUGIN_NAME}/tasks/<task_id>/dataset", self.page_task_dataset, ["POST"], "Export GPT-SoVITS dataset")
        context.register_web_api(f"/{PLUGIN_NAME}/tasks/<task_id>/train", self.page_task_train, ["POST"], "Train GPT-SoVITS voice")

    async def initialize(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        moved = self.voice_registry.migrate_readable_directories()
        discovery = self.voice_registry.discover_external()
        self.studio = VoiceCloneStudio(JsonTaskRepository(self.data_dir / "tasks"))
        recovered = self.studio.recover_interrupted()
        if self.cleanup_enabled:
            task = asyncio.create_task(self._automatic_cleanup_loop())
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)
        logger.info("VoiceClone Flow 已加载，恢复 %d 个任务，迁移 %d 个目录，导入 %d 个外部音色", len(recovered), len(moved), len(discovery.imported))

    def debug_page(self) -> HTMLResponse:
        return HTMLResponse(_build_debug_page())

    async def page_stt_providers(self):
        return json_response(
            {
                "providers": list_stt_providers(self.context, self.stt_provider_id),
                "configured_provider_id": self.stt_provider_id,
            }
        )

    async def page_separator_status(self):
        custom = inspect_separator_model(self.separator_model_path)
        managed = self.separator_resources.status()
        return json_response(
            {
                **managed,
                "custom_path": custom.configured_path,
                "custom_usable": custom.usable,
                "usable": custom.usable or bool(managed["ready"]),
                "active_model": custom.configured_path if custom.usable else managed["resolved_model"],
                "message": (
                    custom.message
                    if self.separator_model_path
                    else "人声分离模型可用"
                    if managed["ready"]
                    else str(managed["error"])
                    if managed["error"]
                    else "未安装人声分离模型"
                ),
            }
        )

    async def page_separator_install(self):
        started = self.separator_resources.start_install(self.separator_model_path)
        return json_response({**self.separator_resources.status(), "started": started})

    async def page_separator_delete(self):
        if self.separator_resources.installing:
            return error_response("模型正在下载，暂时不能删除", status_code=409)
        return json_response({"removed": self.separator_resources.delete_managed()})

    async def page_runtime_status(self):
        platform_profile = detect_platform_profile()
        custom = inspect_separator_model(self.separator_model_path)
        separator = self.separator_resources.status()
        separator["usable"] = custom.usable or bool(separator["ready"])
        separator["active_model"] = custom.configured_path if custom.usable else separator["resolved_model"]
        separator["source"] = "configured" if custom.usable else "managed" if separator["ready"] else "missing"
        return json_response({"platform": platform_profile.to_dict(), "ffmpeg": self.ffmpeg_resources.status(), "separator": separator})

    async def page_ffmpeg_install(self):
        try:
            return json_response({**self.ffmpeg_resources.status(), "started": self.ffmpeg_resources.start_install()})
        except RuntimeError as exc:
            return error_response(str(exc), status_code=409)

    async def page_ffmpeg_delete(self):
        if self.ffmpeg_resources.installing:
            return error_response("FFmpeg 正在下载，暂时不能删除", status_code=409)
        return json_response({"removed": self.ffmpeg_resources.delete_managed()})

    async def page_gpt_status(self):
        service = self.gpt_adapter.status()
        service.update({"starting": self.gpt_starting, "start_error": self.gpt_start_error})
        return json_response({"runtime": self.gpt_install.status(), "service": service, "voices": len(self.voice_registry.list())})

    async def page_gpt_install(self):
        payload = await request.json(default={})
        url = str(payload.get("url", "")).strip() if isinstance(payload, dict) else ""
        try:
            started = self.gpt_install.start_install(url or self.gpt_config.values().get("download_url"))
            return json_response({**self.gpt_install.status(), "started": started}, status_code=202)
        except (ValueError, RuntimeError) as exc:
            return error_response(str(exc), status_code=400)

    async def page_gpt_install_cancel(self):
        return json_response({"cancelled": self.gpt_install.cancel_install(), **self.gpt_install.status()})

    async def page_gpt_delete(self):
        try:
            self.gpt_adapter.stop_service()
            return json_response(self.gpt_install.remove_install())
        except RuntimeError as exc:
            return error_response(str(exc), status_code=409)

    async def page_gpt_start(self):
        runtime = self.gpt_install.status()
        if not runtime["installed"]:
            detail = "、".join(runtime.get("missing_models") or [])
            message = "GPT-SoVITS 运行环境不完整，请先点击下载安装"
            if detail:
                message += f"。缺少：{detail}"
            return error_response(message, status_code=409)
        if self.gpt_starting:
            return json_response({"starting": True, "started": False})
        if self.gpt_adapter.is_alive():
            return json_response({**self.gpt_adapter.status(), "started": False})
        self.gpt_starting = True
        self.gpt_start_error = ""
        task = asyncio.create_task(self._start_gpt_service())
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
        return json_response({"starting": True, "started": True}, status_code=202)

    async def _start_gpt_service(self):
        try:
            await asyncio.to_thread(self.gpt_adapter.ensure_service)
        except Exception as exc:
            self.gpt_start_error = str(exc)
            logger.exception("GPT-SoVITS service failed to start")
        finally:
            self.gpt_starting = False

    async def page_gpt_stop(self):
        self.gpt_starting = False
        await asyncio.to_thread(self.gpt_adapter.stop_service)
        return json_response(self.gpt_adapter.status())

    async def page_gpt_voices(self):
        discovery = self.voice_registry.discover_external()
        return json_response({
            "voices": [item.__dict__ for item in self.voice_registry.list()],
            "discovery": {"imported": list(discovery.imported), "skipped": list(discovery.skipped)},
        })

    async def page_gpt_voice_create(self):
        payload = await request.json(default={})
        if not isinstance(payload, dict) or not str(payload.get("name", "")).strip():
            return error_response("音色名称不能为空", status_code=400)
        try:
            asset = self.voice_registry.create(str(payload["name"]), **{key: str(value) for key, value in payload.items() if key != "name"})
            return json_response({"voice": asset.__dict__}, status_code=201)
        except (TypeError, ValueError) as exc:
            return error_response(str(exc), status_code=400)

    async def page_gpt_voice(self, voice_id: str):
        asset = self.voice_registry.get(voice_id)
        if asset is None:
            return error_response("音色不存在", status_code=404)
        return json_response({"voice": asset.__dict__, "provider": self._provider_config(asset)})

    async def page_gpt_voice_reference(self, voice_id: str):
        payload = await request.json(default={})
        if not isinstance(payload, dict):
            return error_response("请求格式无效", status_code=400)
        try:
            asset = self.voice_registry.update_reference(
                voice_id,
                str(payload.get("reference_audio_path", "")),
                str(payload.get("reference_text", "")),
            )
            return json_response({"voice": asset.__dict__, "provider": self._provider_config(asset)})
        except KeyError:
            return error_response("音色不存在", status_code=404)
        except FileNotFoundError as exc:
            return error_response(str(exc), status_code=404)
        except ValueError as exc:
            return error_response(str(exc), status_code=400)

    async def page_gpt_provider(self, voice_id: str):
        asset = self.voice_registry.get(voice_id)
        if asset is None:
            return error_response("音色不存在", status_code=404)
        if asset.status != "ready" or not asset.reference_language:
            return error_response("音色尚未配置参考语言，不能创建 Provider", status_code=409)
        try:
            config = build_gsv_provider_config(asset, self.gpt_adapter.base_url)
            provider_id = await apply_gsv_provider(self.context, config)
            return json_response({"provider_id": provider_id, "config": config})
        except Exception as exc:
            logger.exception("应用 GSV Provider 失败")
            return error_response(str(exc), status_code=502)

    async def page_gpt_voice_folder(self, voice_id: str):
        asset = self.voice_registry.get(voice_id)
        if asset is None:
            return error_response("音色不存在", status_code=404)
        try:
            target = await asyncio.to_thread(open_voice_directory, self.data_dir, asset.dir_name or voice_id)
            return json_response({"path": str(target)})
        except FileNotFoundError as exc:
            return error_response(str(exc), status_code=404)
        except ValueError as exc:
            return error_response(str(exc), status_code=400)

    async def page_gpt_voices_folder(self):
        try:
            target = await asyncio.to_thread(open_voices_root, self.data_dir)
            return json_response({"path": str(target)})
        except OSError as exc:
            return error_response(str(exc), status_code=500)

    def _provider_config(self, asset: VoiceAsset) -> dict:
        return {
            "api_base_url": self.gpt_adapter.base_url,
            "gpt_model_path": asset.gpt_weights_path,
            "sovits_model_path": asset.sovits_weights_path,
            "reference_audio_path": asset.refer_audio_path,
            "reference_audio_text": asset.reference_text,
            "reference_language": asset.reference_language,
            "text_language": asset.reference_language,
        }

    async def page_gpt_synthesize(self):
        payload = await request.json(default={})
        if not isinstance(payload, dict):
            return error_response("请求格式无效", status_code=400)
        text = str(payload.get("text", "")).strip()
        voice_id = str(payload.get("voice_id", "")).strip()
        asset = self.voice_registry.get(voice_id)
        if not text or not asset:
            return error_response("text 不能为空且音色必须存在", status_code=400)
        try:
            audio = await asyncio.to_thread(self.gpt_synthesis.synthesize, asset, text, payload.get("language"))
            return json_response({"content_type": "audio/wav", "base64": base64.b64encode(audio).decode("ascii")})
        except Exception as exc:
            return error_response(f"GPT-SoVITS 合成失败: {exc}", status_code=502)

    def _active_separator_model(self) -> Path | None:
        custom = inspect_separator_model(self.separator_model_path)
        if custom.usable:
            return Path(custom.configured_path)
        if self.separator_resources.status()["ready"]:
            return self.separator_resources.model_path
        return None

    async def page_create_task(self, provider_id: str, language: str, authorization: str):
        if authorization != "authorized":
            return error_response("必须确认拥有该声音的使用授权", status_code=400)
        model = self._active_separator_model()
        if model is None:
            return error_response("人声分离模型未安装或校验失败", status_code=409)
        files = await request.files()
        upload = files.get("file")
        if not isinstance(upload, PluginUploadFile):
            return error_response("请选择视频或音频素材", status_code=400)
        processing = self.config.get("processing", {})
        max_upload_mb = int(processing.get("max_upload_mb", 400)) if isinstance(processing, dict) else 400
        if upload.content_length and upload.content_length > max_upload_mb * 1024 * 1024:
            return error_response(f"素材不能超过 {max_upload_mb} MB", status_code=413)
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in {".wav", ".mp3", ".m4a", ".mp4", ".mpeg", ".webm", ".mov", ".mkv"}:
            return error_response("不支持该素材格式", status_code=400)
        task = self.studio.create_task(Path(upload.filename or "voice").stem, upload.filename or "source")
        root = self.data_dir / "sessions" / task.id
        source = root / f"source{suffix}"
        root.mkdir(parents=True, exist_ok=True)
        await upload.save(source)
        ffmpeg = self.ffmpeg_resources.resolve()
        pipeline = MaterialPipeline(self.context, provider_id, str(ffmpeg or ""), model, self.data_dir / "sessions")

        def transition(state):
            current = self.studio.repository.get(task.id)
            self.studio.repository.save(current.transition(state))

        async def execute():
            try:
                await pipeline.run(task.id, source, language, transition)
            except Exception as exc:
                current = self.studio.repository.get(task.id)
                if current.state not in {"failed", "cancelled", "ready"}:
                    self.studio.repository.save(current.transition("failed", str(exc)))
                logger.exception("Voice material task failed: %s", task.id)

        worker = asyncio.create_task(execute())
        self.background_tasks.add(worker)
        worker.add_done_callback(self.background_tasks.discard)
        return json_response({"task": task.to_dict()}, status_code=202)

    async def page_tasks(self):
        return json_response({"tasks": [item.to_dict() for item in self.studio.repository.list()]})

    async def page_task(self, task_id: str):
        try:
            task = self.studio.repository.get(task_id)
            reviews = MaterialPipeline(self.context, self.stt_provider_id, "", Path("unused"), self.data_dir / "sessions").reviews.load(task_id)
            return json_response({"task": task.to_dict(), "segments": reviews})
        except (ValueError, FileNotFoundError):
            return error_response("任务不存在", status_code=404)

    async def page_task_audio(self, task_id: str, audio_name: str):
        try:
            self.studio.repository.get(task_id)
        except (ValueError, FileNotFoundError):
            return error_response("任务不存在", status_code=404)
        if not audio_name.startswith("segment_") or Path(audio_name).name != audio_name:
            return error_response("音频路径无效", status_code=400)
        path = self.data_dir / "sessions" / task_id / "segments" / audio_name
        if not path.is_file():
            return error_response("音频不存在", status_code=404)
        content_type = "audio/wav" if path.suffix.lower() == ".wav" else "audio/mpeg"
        return json_response({"name": audio_name, "content_type": content_type, "base64": base64.b64encode(path.read_bytes()).decode("ascii")})


    async def page_task_dataset(self, task_id: str):
        try:
            payload = await request.json(default={})
            rows = payload.get("segments", []) if isinstance(payload, dict) else []
            store = ReviewStore(self.data_dir / "sessions")
            current = {str(row.get("audio_name")): row for row in store.load(task_id)}
            normalized = []
            for row in rows:
                name = str(row.get("audio_name", ""))
                if name not in current or Path(name).name != name:
                    continue
                item = {**current[name], "text": str(row.get("text", "")).strip(), "approved": bool(row.get("approved"))}
                normalized.append(item)
            store.save(task_id, normalized)
            dataset_rows = [DatasetRow(self.data_dir / "sessions" / task_id / "segments" / str(row["audio_name"]), str(row["text"]), str(row["language"]), bool(row["approved"])) for row in normalized]
            result = export_gpt_sovits_dataset(dataset_rows, self.data_dir / "datasets" / task_id)
            return json_response({"count": result.count, "skipped_count": result.skipped_count, "manifest": str(result.manifest), "dataset_dir": str(result.root)})
        except (ValueError, KeyError) as exc:
            return error_response(str(exc), status_code=400)

    async def page_task_train(self, task_id: str):
        payload = await request.json(default={})
        name = str(payload.get("name", "")).strip() if isinstance(payload, dict) else ""
        language = str(payload.get("language", "zh")).strip() if isinstance(payload, dict) else "zh"
        preset_id = str(payload.get("preset_id", "standard")).strip() if isinstance(payload, dict) else "standard"
        try:
            preset = get_training_preset(preset_id) if preset_id != "custom" else None
            gpt_epochs = int(payload.get("gpt_epochs", preset.gpt_epochs if preset else 15))
            sovits_epochs = int(payload.get("sovits_epochs", preset.sovits_epochs if preset else 30))
            validate_training_epochs(gpt_epochs, sovits_epochs)
        except (ValueError, TypeError) as exc:
            return error_response(str(exc), status_code=400)
        if not name:
            return error_response("音色名称不能为空", status_code=400)
        dataset = self.data_dir / "datasets" / task_id
        if not (dataset / "train.list").is_file():
            return error_response("请先生成训练数据", status_code=409)
        asset = self.voice_registry.create(name, status="created", reference_language=language, training_preset=preset_id, gpt_epochs=gpt_epochs, sovits_epochs=sovits_epochs)
        target = self.gpt_training.dataset_dir(asset.id)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(dataset, target, dirs_exist_ok=True)
        try:
            started = self.gpt_training.start_training(asset.id, expected_language=language, gpt_epochs=gpt_epochs, sovits_epochs=sovits_epochs)
        except TrainingDataInvalid as exc:
            asset.status = "failed"
            asset.error_message = str(exc)
            self.voice_registry.save(asset)
            return error_response(str(exc), status_code=422)
        if not started:
            return error_response("已有训练任务正在进行", status_code=409)
        return json_response({"voice": self.voice_registry.get(asset.id).__dict__}, status_code=202)

    def _cleanup_protected_tasks(self) -> set[str]:
        protected = set()
        active = self.gpt_training.status().get("active_asset_id")
        if active:
            asset = self.voice_registry.get(active)
            if asset and asset.dataset_dir:
                protected.add(Path(asset.dataset_dir).name)
        tasks = self.studio.repository.list()
        incomplete = [task for task in tasks if task.state not in {"ready", "failed", "cancelled"}]
        if incomplete:
            protected.add(incomplete[-1].id)
        return protected

    async def _automatic_cleanup_loop(self):
        while True:
            try:
                preview = await asyncio.to_thread(build_cleanup_preview, self.data_dir, self._cleanup_protected_tasks(), self.cleanup_retention_days)
                if preview.items:
                    removed = await asyncio.to_thread(remove_cleanup_items, preview, {item.relative_path for item in preview.items})
                    logger.info("VoiceClone Flow 自动清理完成：删除 %d 个历史目录，释放 %.1f MB", removed, preview.total_bytes / 1048576)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("VoiceClone Flow 自动清理失败")
            await asyncio.sleep(self.cleanup_interval_hours * 3600)

    async def page_stt_test(self, provider_id: str):
        files = await request.files()
        upload: PluginUploadFile | None = files.get("file")
        if not isinstance(upload, PluginUploadFile):
            return error_response("请选择测试音频", status_code=400)
        try:
            result = await run_stt_test(
                self.context,
                provider_id,
                upload.filename or "sample.wav",
                await upload.read(),
                self.data_dir / "temporary",
            )
            return json_response(result)
        except ASRTestError as exc:
            return error_response(str(exc), status_code=400)
        except Exception as exc:
            logger.warning("VoiceClone Flow ASR 通路测试失败：%s", exc)
            return error_response(f"ASR 调用失败：{exc}", status_code=502)

    @filter.command("voice_clone_flow")
    async def status(self, event: AstrMessageEvent):
        """查看 VoiceClone Flow 插件状态。"""
        yield event.plain_result("VoiceClone Flow 已就绪。")

    @filter.on_decorating_result()
    async def decorate_japanese_voice(self, event: AstrMessageEvent) -> None:
        """Keep Chinese text visible and add a Japanese voice rendition."""

        if self.speech_decorator is not None:
            await self.speech_decorator.decorate(event)

    async def terminate(self) -> None:
        for task in self.background_tasks:
            task.cancel()
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
        if self.speech_decorator is not None:
            await self.speech_decorator.terminate()
        await asyncio.to_thread(self.gpt_adapter.stop_service)
        logger.info("VoiceClone Flow 已停止")


def _build_debug_page() -> str:
    api_root = f"/api/plugins/extensions/{PLUGIN_NAME}"
    providers_url = f"{api_root}/stt/providers"
    test_url = f"{api_root}/stt/test/"
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VoiceClone Flow 调试台</title><style>
:root{{--bg:#f4f6f8;--panel:#fff;--text:#17202a;--muted:#667085;--line:#d7dce2;--accent:#1769aa;--ok:#087443;--bad:#b42318}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,"Microsoft YaHei",sans-serif}}
main{{width:min(760px,calc(100% - 32px));margin:48px auto}}header{{margin-bottom:22px}}h1{{margin:0 0 6px;font-size:25px;letter-spacing:0}}p{{margin:0;color:var(--muted)}}
section{{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:22px}}label{{display:block;font-weight:650;margin:0 0 7px}}select,input{{width:100%;height:42px;border:1px solid var(--line);border-radius:6px;padding:8px 10px;background:#fff}}.field{{margin-bottom:18px}}
button{{height:42px;border:0;border-radius:6px;padding:0 18px;background:var(--accent);color:#fff;font-weight:650;cursor:pointer}}button:disabled{{opacity:.5;cursor:not-allowed}}
#status{{margin-left:12px;color:var(--muted)}}#result{{margin-top:20px;padding:15px;border-left:3px solid var(--line);background:#f8fafc;white-space:pre-wrap;min-height:58px}}#result.ok{{border-color:var(--ok)}}#result.bad{{border-color:var(--bad);color:var(--bad)}}
</style></head><body><main><header><h1>VoiceClone Flow 调试台</h1><p>验证 AstrBot STT Provider 的真实音频识别通路</p></header>
<section><div class="field"><label for="provider">语音识别提供商</label><select id="provider"><option>正在读取...</option></select></div>
<div class="field"><label for="audio">测试音频</label><input id="audio" type="file" accept="audio/*,video/mp4,video/webm"></div>
<button id="run" disabled>开始识别</button><span id="status"></span><div id="result">等待测试</div></section></main>
<script>
const provider=document.querySelector('#provider'),audio=document.querySelector('#audio'),run=document.querySelector('#run'),statusEl=document.querySelector('#status'),result=document.querySelector('#result');
function ready(){{run.disabled=!provider.value||!audio.files.length}}
audio.addEventListener('change',ready);provider.addEventListener('change',ready);
async function load(){{try{{const r=await fetch('{providers_url}');if(!r.ok)throw new Error('HTTP '+r.status);const d=await r.json(),rows=d.providers||[];provider.innerHTML='';for(const p of rows)provider.add(new Option(p.id+(p.model?' · '+p.model:''),p.id,false,p.selected));if(!rows.length)provider.add(new Option('没有可用的 STT Provider',''));statusEl.textContent=rows.length+' 个 Provider 可用';ready()}}catch(e){{provider.innerHTML='<option value="">读取失败</option>';result.className='bad';result.textContent=e.message}}}}
run.addEventListener('click',async()=>{{const file=audio.files[0];if(!file)return;run.disabled=true;statusEl.textContent='正在识别...';result.className='';result.textContent='音频已提交给 '+provider.value;const body=new FormData();body.append('file',file);try{{const r=await fetch('{test_url}'+encodeURIComponent(provider.value),{{method:'POST',body}});const d=await r.json();if(!r.ok||d.status==='error')throw new Error(d.message||'识别失败');result.className='ok';result.textContent=d.text;statusEl.textContent=d.elapsed_ms+' ms'}}catch(e){{result.className='bad';result.textContent=e.message;statusEl.textContent='识别失败'}}finally{{ready()}}}});load();
</script></body></html>'''
