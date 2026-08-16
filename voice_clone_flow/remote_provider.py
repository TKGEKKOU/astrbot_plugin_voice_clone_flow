from __future__ import annotations

import asyncio

from .gpt_sovits.voices import VoiceAsset


def remote_provider_id(voice_id: str) -> str:
    safe = "".join(char if char.isalnum() or char in "-_" else "_" for char in str(voice_id))
    return f"voice_clone_flow_remote_{safe}"


_GSVI_LANGUAGE_LABELS = {
    "zh": "中文",
    "ja": "日文",
    "en": "英文",
    "ko": "韩文",
    "yue": "粤语",
}


def normalize_delivery_provider(config: dict, *, api_base: str, api_key: str) -> dict:
    if not isinstance(config, dict):
        raise ValueError("Studio Provider 配置格式无效")
    provider_id = str(config.get("id", "")).strip()
    character = str(config.get("character", "")).strip()
    if not provider_id.startswith("voice_clone_flow_remote_") or not character:
        raise ValueError("Studio Provider 缺少有效 id 或 character")
    if config.get("type") != "gsvi_tts_api" or config.get("provider_type") != "text_to_speech":
        raise ValueError("Studio Provider 类型必须是 GSVI TTS(API)")
    language = str(config.get("text_lang", "中文")).strip()
    if language not in set(_GSVI_LANGUAGE_LABELS.values()):
        raise ValueError("Studio Provider 语言无效")
    prompt_language = str(config.get("prompt_text_lang", language)).strip()
    if prompt_language not in set(_GSVI_LANGUAGE_LABELS.values()):
        raise ValueError("Studio Provider 参考语言无效")
    return {
        "id": provider_id,
        "type": "gsvi_tts_api",
        "provider": "gpt_sovits_inference",
        "provider_type": "text_to_speech",
        "enable": bool(config.get("enable", True)),
        "display_name": str(config.get("display_name") or character).strip(),
        "api_key": str(api_key),
        "api_base": str(api_base).rstrip("/"),
        "version": "v2Pro",
        "character": character,
        "prompt_text_lang": prompt_language,
        "emotion": str(config.get("emotion", "默认")).strip() or "默认",
        "text_lang": language,
        "timeout": 300,
    }


def build_remote_provider_config(
    asset: VoiceAsset,
    *,
    api_base: str,
    api_key: str,
) -> dict:
    voice_id = asset.remote_voice_id or asset.id
    language = _GSVI_LANGUAGE_LABELS.get(asset.reference_language or "zh", "中文")
    return {
        "id": remote_provider_id(voice_id),
        "type": "gsvi_tts_api",
        "provider": "gpt_sovits_inference",
        "provider_type": "text_to_speech",
        "enable": asset.status != "disabled",
        "display_name": asset.name,
        "api_key": str(api_key),
        "api_base": str(api_base).rstrip("/"),
        "version": "v2Pro",
        "character": voice_id,
        "prompt_text_lang": language,
        "emotion": "默认",
        "text_lang": language,
        "timeout": 300,
    }


async def finalize_remote_provider_delivery(
    client,
    task_id: str,
    provider_id: str,
    config: dict,
) -> dict:
    await asyncio.to_thread(
        client.report_provider_delivery,
        task_id,
        "registered",
        f"AstrBot Provider 已注册：{provider_id}",
    )
    try:
        probe = await asyncio.to_thread(
            client.verify_provider,
            str(config.get("character", "")),
            str(config.get("text_lang", "中文")),
        )
    except Exception as exc:
        await asyncio.to_thread(
            client.report_provider_delivery,
            task_id,
            "failed",
            f"AstrBot Provider 已注册，但短语音测试失败：{provider_id}",
            str(exc),
        )
        return {"verified": False, "provider_id": provider_id, "error": str(exc)}

    duration = float(probe.get("duration_seconds", 0))
    await asyncio.to_thread(
        client.report_provider_delivery,
        task_id,
        "verified",
        f"Provider 已通过 {duration:.2f} 秒短语音测试：{provider_id}",
    )
    return {"verified": True, "provider_id": provider_id, **probe}


async def apply_remote_provider(context, config: dict) -> str:
    manager = getattr(context, "provider_manager", None)
    if manager is None:
        raise RuntimeError("当前 AstrBot Context 未提供 ProviderManager")
    configured = {str(item.get("id")): item for item in getattr(manager, "providers_config", []) if isinstance(item, dict)}
    provider_id = str(config["id"])
    existed = provider_id in getattr(manager, "inst_map", {}) or provider_id in configured
    try:
        if existed:
            await manager.update_provider(provider_id, config)
        else:
            await manager.create_provider(config)
        if bool(config.get("enable", True)):
            instance = getattr(manager, "inst_map", {}).get(provider_id)
            tts_instances = getattr(manager, "tts_provider_insts", [])
            instance_config = getattr(instance, "provider_config", {}) if instance is not None else {}
            valid = (
                instance is not None
                and instance in tts_instances
                and isinstance(instance_config, dict)
                and instance_config.get("id") == provider_id
                and instance_config.get("type") == "gsvi_tts_api"
                and instance_config.get("character") == config.get("character")
                and str(instance_config.get("api_base", "")).rstrip("/")
                == str(config.get("api_base", "")).rstrip("/")
            )
            if not valid:
                raise RuntimeError("AstrBot 已保存配置，但未创建可用的 GSVI TTS 运行实例")
        return provider_id
    except Exception:
        if not existed and callable(getattr(manager, "delete_provider", None)):
            try:
                await manager.delete_provider(provider_id)
            except Exception:
                pass
        raise
