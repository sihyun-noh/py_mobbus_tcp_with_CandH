import argparse
import logging
import signal
import sys
import time

from .config import load_config
from .modbus_reader import FSM60ModbusReader
from .mqtt_publisher import MQTTPublisher


LOGGER = logging.getLogger("fsm60_gateway")
RUNNING = True


def handle_signal(signum, frame):
    global RUNNING
    LOGGER.info("Received signal %s, shutting down...", signum)
    RUNNING = False


def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def build_payload(device_cfg: dict, parsed: dict, selected_word_order: str) -> dict:
    modbus_cfg = device_cfg["modbus"]

    if selected_word_order == "swap":
        instant = parsed["instant_sw"]
        total = parsed["total_sw"]
    else:
        instant = parsed["instant_be"]
        total = parsed["total_be"]

    return {
        "device": device_cfg.get("device", "FSM60"),
        "id": device_cfg.get("id"),
        "modbus_host": modbus_cfg["host"],
        "modbus_port": modbus_cfg["port"],
        "unit_id": modbus_cfg["unit_id"],
        "address": modbus_cfg["address"],
        "instant": instant,
        "total": total,
        "instant_be": parsed["instant_be"],
        "total_be": parsed["total_be"],
        "instant_sw": parsed["instant_sw"],
        "total_sw": parsed["total_sw"],
        "raw": parsed["raw"],
        "timestamp": time.time(),
    }


def read_device(device_cfg: dict) -> dict:
    modbus_cfg = device_cfg["modbus"]

    reader = FSM60ModbusReader(
        host=modbus_cfg["host"],
        port=modbus_cfg["port"],
        unit_id=modbus_cfg["unit_id"],
        address=modbus_cfg["address"],
        quantity=modbus_cfg["quantity"],
        timeout=modbus_cfg.get("timeout", 1),
    )

    return reader.read_once()


def run(config: dict):
    mqtt_cfg = config["mqtt"]
    devices = config["devices"]
    poll_interval = float(config.get("poll_interval", 1.0))
    default_word_order = config.get("word_order", "be")

    publisher = MQTTPublisher(
        host=mqtt_cfg["host"],
        port=mqtt_cfg["port"],
        qos=mqtt_cfg.get("qos", 0),
        retain=mqtt_cfg.get("retain", False),
        client_id=mqtt_cfg.get("client_id"),
    )

    publisher.connect()
    LOGGER.info("MQTT connected: %s:%s", mqtt_cfg["host"], mqtt_cfg["port"])

    try:
        while RUNNING:
            cycle_start = time.time()

            for device_cfg in devices:
                if not RUNNING:
                    break

                device_id = device_cfg.get("id", "unknown")
                topic = device_cfg["mqtt_topic"]
                word_order = device_cfg.get("word_order", default_word_order)

                try:
                    parsed = read_device(device_cfg)
                    payload = build_payload(device_cfg, parsed, word_order)
                    payload_json = publisher.publish(topic, payload)

                    LOGGER.info("sent id=%s topic=%s payload=%s", device_id, topic, payload_json)

                except Exception as exc:
                    modbus_cfg = device_cfg.get("modbus", {})
                    LOGGER.error(
                        "device error id=%s host=%s port=%s error=%s",
                        device_id,
                        modbus_cfg.get("host"),
                        modbus_cfg.get("port"),
                        exc,
                    )

            elapsed = time.time() - cycle_start
            sleep_time = max(0, poll_interval - elapsed)

            if sleep_time > 0:
                time.sleep(sleep_time)

    finally:
        publisher.close()
        LOGGER.info("MQTT disconnected")


def main():
    parser = argparse.ArgumentParser(
        description="Multi-device FSM60 Modbus TCP to MQTT Gateway"
    )
    parser.add_argument("--config", required=True, help="Path to config JSON file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logs")

    args = parser.parse_args()

    setup_logging(args.verbose)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        config = load_config(args.config)
        run(config)
    except Exception as exc:
        LOGGER.exception("fatal error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
