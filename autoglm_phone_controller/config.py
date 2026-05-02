from __future__ import annotations

import os
from dataclasses import dataclass

from .runtime import resource_path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - keeps pre-install error messages friendly
    load_dotenv = None


DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
DEFAULT_MODEL = "autoglm-phone"


@dataclass(frozen=True)
class AppConfig:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    device_id: str | None = None


def load_config(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    device_id: str | None = None,
) -> AppConfig:
    if load_dotenv is not None:
        load_dotenv()
        packaged_env = resource_path(".env")
        if packaged_env.exists():
            load_dotenv(packaged_env, override=False)

    resolved_api_key = (
        api_key
        or os.getenv("BIGMODEL_API_KEY")
        or os.getenv("ZHIPUAI_API_KEY")
        or os.getenv("AUTOGLM_API_KEY")
        or ""
    )

    return AppConfig(
        api_key=resolved_api_key,
        base_url=base_url or os.getenv("AUTOGLM_BASE_URL") or DEFAULT_BASE_URL,
        model=model or os.getenv("AUTOGLM_MODEL") or DEFAULT_MODEL,
        device_id=device_id or os.getenv("ANDROID_SERIAL") or None,
    )
