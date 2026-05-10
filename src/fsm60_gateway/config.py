import json
from pathlib import Path


def load_config(path: str) -> dict:
    config_path = Path(path)

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with config_path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    validate_config(config)
    return config


def validate_config(config: dict) -> None:
    if "mqtt" not in config:
        raise ValueError("Missing required config key: mqtt")

    if "devices" not in config:
        raise ValueError("Missing required config key: devices")

    if not isinstance(config["devices"], list) or not config["devices"]:
        raise ValueError("devices must be a non-empty list")

    mqtt = config["mqtt"]
    for key in ("host", "port"):
        if key not in mqtt:
            raise ValueError(f"Missing mqtt.{key}")

    for idx, device in enumerate(config["devices"], start=1):
        if "modbus" not in device:
            raise ValueError(f"Missing devices[{idx}].modbus")
        if "mqtt_topic" not in device:
            raise ValueError(f"Missing devices[{idx}].mqtt_topic")

        modbus = device["modbus"]
        for key in ("host", "port", "unit_id", "address", "quantity"):
            if key not in modbus:
                raise ValueError(f"Missing devices[{idx}].modbus.{key}")
