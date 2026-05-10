import argparse
import logging
import signal
import sys
import queue
import threading
import time

from .config import load_config
from .worker import MQTTPublishWorker, SensorWorker


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


def run(config: dict):
    mqtt_cfg = config["mqtt"]
    devices = config["devices"]
    poll_interval = float(config.get("poll_interval", 1.0))
    default_word_order = config.get("word_order", "be")
    queue_size = int(config.get("queue_size", 100))
    payload_queue = queue.Queue(maxsize=queue_size)
    stop_event = threading.Event()
    mqtt_worker = MQTTPublishWorker(mqtt_cfg, payload_queue, stop_event)
    sensor_workers = [
        SensorWorker(
            device_cfg=device_cfg,
            payload_queue=payload_queue,
            stop_event=stop_event,
            default_poll_interval=poll_interval,
            default_word_order=default_word_order,
        )
        for device_cfg in devices
    ]

    try:
        mqtt_worker.start()
        for worker in sensor_workers:
            worker.start()

        while RUNNING and not stop_event.is_set():
            time.sleep(0.5)

    finally:
        stop_event.set()
        for worker in sensor_workers:
            worker.join(timeout=5)
        mqtt_worker.join(timeout=5)


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
