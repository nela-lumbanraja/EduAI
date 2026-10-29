from pathlib import Path

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parents[2]   # .../ai/eduai-ai
DEFAULT_CONFIG = PACKAGE_ROOT / "config.yaml"


def load_config(path=None) -> dict:
    path = Path(path) if path else DEFAULT_CONFIG
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict) or "version" not in cfg:
        raise ValueError(f"{path} must define 'version' so results can be traced to a config")
    for section in ("sampling", "models", "quality", "baseline", "indicators", "evidence"):
        if section not in cfg:
            raise ValueError(f"{path} is missing the '{section}' section")
    return cfg


def resolve_model_path(p, base: Path = PACKAGE_ROOT) -> Path:
    p = Path(p)
    return p if p.is_absolute() else base / p
