import logging
import queue
import threading
import time

from .modbus_reader import FSM60ModbusReader
from .mqtt_publisher import MQTTPublisher


LOGGER = logging.getLogger("fsm60_gateway")


def build_payload(device_cfg: dict, parsed: dict, selected_word_order: str) -> dict:
    modbus_cfg = device_cfg["modbus"]

    if selected_word_order == "swap":
        instant = parsed["instant_sw"]
        total = parsed["total_sw"]
    else:
        instant = parsed["instant_be"]
        total = parsed["total_be"]

    payload = {
        "device": device_cfg.get("device", "FSM60"),
        "id": device_cfg.get("id"),
        "host": modbus_cfg["host"],
        "instant": instant,
        "total": total,
        "timestamp": time.time(),
    }

    if device_cfg.get("include_raw", False):
        payload["raw"] = parsed["raw"]

    return payload


def build_reader(device_cfg: dict) -> FSM60ModbusReader:
    modbus_cfg = device_cfg["modbus"]

    return FSM60ModbusReader(
        host=modbus_cfg["host"],
        port=modbus_cfg["port"],
        unit_id=modbus_cfg["unit_id"],
        address=modbus_cfg["address"],
        quantity=modbus_cfg["quantity"],
        timeout=modbus_cfg.get("timeout", 1),
        retries=modbus_cfg.get("retries", 3),
        reconnect_interval=modbus_cfg.get("reconnect_interval", 10),
    )


class SensorWorker(threading.Thread):
    def __init__(
        self,
        device_cfg: dict,
        payload_queue: queue.Queue,
        stop_event: threading.Event,
        default_poll_interval: float,
        default_word_order: str,
    ):
        device_id = device_cfg.get("id", "unknown")
        super().__init__(name=f"sensor-{device_id}", daemon=True)
        self.device_cfg = device_cfg
        self.payload_queue = payload_queue
        self.stop_event = stop_event
        self.poll_interval = float(device_cfg.get("poll_interval", default_poll_interval))
        self.word_order = device_cfg.get("word_order", default_word_order)
        self.reader = build_reader(device_cfg)

    def run(self):
        modbus_cfg = self.device_cfg["modbus"]
        device_id = self.device_cfg.get("id", "unknown")
        topic = self.device_cfg["mqtt_topic"]
        LOGGER.info(
            "sensor worker started id=%s host=%s port=%s interval=%s",
            device_id,
            modbus_cfg["host"],
            modbus_cfg["port"],
            self.poll_interval,
        )

        try:
            while not self.stop_event.is_set():
                cycle_start = time.monotonic()

                try:
                    if self.reader.seconds_until_retry() > 0:
                        continue

                    parsed = self.reader.read_once()
                    payload = build_payload(self.device_cfg, parsed, self.word_order)
                    self.payload_queue.put((device_id, topic, payload), timeout=1)
                except queue.Full:
                    LOGGER.error("payload queue full id=%s topic=%s", device_id, topic)
                except Exception as exc:
                    LOGGER.error(
                        "device error id=%s host=%s port=%s error=%s",
                        device_id,
                        modbus_cfg.get("host"),
                        modbus_cfg.get("port"),
                        exc,
                    )

                elapsed = time.monotonic() - cycle_start
                sleep_time = max(0.0, self.poll_interval - elapsed)
                self.stop_event.wait(sleep_time)
        finally:
            self.reader.close()
            LOGGER.info("sensor worker stopped id=%s", device_id)


class MQTTPublishWorker(threading.Thread):
    def __init__(
        self,
        mqtt_cfg: dict,
        payload_queue: queue.Queue,
        stop_event: threading.Event,
    ):
        super().__init__(name="mqtt-publisher", daemon=True)
        self.mqtt_cfg = mqtt_cfg
        self.payload_queue = payload_queue
        self.stop_event = stop_event
        self.publisher = MQTTPublisher(
            host=mqtt_cfg["host"],
            port=mqtt_cfg["port"],
            qos=mqtt_cfg.get("qos", 0),
            retain=mqtt_cfg.get("retain", False),
            client_id=mqtt_cfg.get("client_id"),
        )

    def run(self):
        try:
            self.publisher.connect()
        except Exception as exc:
            LOGGER.error(
                "MQTT connect failed host=%s port=%s error=%s",
                self.mqtt_cfg["host"],
                self.mqtt_cfg["port"],
                exc,
            )
            self.stop_event.set()
            return

        LOGGER.info("MQTT connected: %s:%s", self.mqtt_cfg["host"], self.mqtt_cfg["port"])

        try:
            while not self.stop_event.is_set() or not self.payload_queue.empty():
                try:
                    device_id, topic, payload = self.payload_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                try:
                    payload_json = self.publisher.publish(topic, payload)
                    LOGGER.info("sent id=%s topic=%s payload=%s", device_id, topic, payload_json)
                except Exception as exc:
                    LOGGER.error("MQTT publish error id=%s topic=%s error=%s", device_id, topic, exc)
                finally:
                    self.payload_queue.task_done()
        finally:
            self.publisher.close()
            LOGGER.info("MQTT disconnected")
