import json
from pathlib import Path

from config import DouyinLifeConfig
from tool_schemas import TOOL_SCHEMAS


ROOT = Path(__file__).resolve().parents[1]


def test_manifest_uses_maibot_current_personality_only():
    manifest = json.loads((ROOT / "_manifest.json").read_text(encoding="utf-8"))
    assert "personality.get_current" in manifest["capabilities"]
    assert "personality.switch" not in manifest["capabilities"]
    assert manifest["manifest_version"] == 2
    assert (ROOT / "plugin.py").is_file()
    assert manifest["sdk"]["min_version"] == "2.20.0"


def test_no_independent_persona_or_host_configuration_fields():
    dumped = json.dumps(DouyinLifeConfig().model_dump(), ensure_ascii=False)
    for forbidden in ("personaPrompt", "persona_md", "dshBin", "workspace"):
        assert forbidden not in dumped


def test_original_license_and_port_attribution_are_kept():
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in license_text
    assert "TiAmoSS" in license_text
    assert "cixinshang/dsh-douyin-life-plus" in license_text
    assert len(TOOL_SCHEMAS) == 35


def test_delivery_contains_no_runtime_secrets_or_state():
    forbidden = {"config.toml", "ledger.json", "login-qr.png", "Cookies"}
    assert not any(path.name in forbidden for path in ROOT.rglob("*"))
    assert not any(path.name in {"browser", "chrome-cdp"} and path.is_dir() for path in ROOT.rglob("*"))
