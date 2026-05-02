from autoglm_phone_controller.config import DEFAULT_BASE_URL, DEFAULT_MODEL, load_config


def test_load_config_from_arguments() -> None:
    config = load_config(
        api_key="k",
        base_url="https://example.test/v4",
        model="autoglm-phone",
        device_id="device-1",
    )

    assert config.api_key == "k"
    assert config.base_url == "https://example.test/v4"
    assert config.model == "autoglm-phone"
    assert config.device_id == "device-1"


def test_load_config_defaults(monkeypatch) -> None:
    monkeypatch.delenv("BIGMODEL_API_KEY", raising=False)
    monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)
    monkeypatch.delenv("AUTOGLM_API_KEY", raising=False)
    monkeypatch.delenv("AUTOGLM_BASE_URL", raising=False)
    monkeypatch.delenv("AUTOGLM_MODEL", raising=False)
    monkeypatch.delenv("ANDROID_SERIAL", raising=False)

    config = load_config()

    assert config.api_key == ""
    assert config.base_url == DEFAULT_BASE_URL
    assert config.model == DEFAULT_MODEL
    assert config.device_id is None
