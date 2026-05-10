import json
import paho.mqtt.client as mqtt


class MQTTPublisher:
    def __init__(self, host, port, qos=0, retain=False, client_id=None):
        self.host = host
        self.port = int(port)
        self.qos = int(qos)
        self.retain = bool(retain)
        self.client_id = client_id
        self.client = None

    def connect(self):
        # paho-mqtt 2.x 호환
        try:
            self.client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION1,
                client_id=self.client_id or "",
            )
        except AttributeError:
            # paho-mqtt 1.x 호환
            self.client = mqtt.Client(client_id=self.client_id or "")

        self.client.connect(self.host, self.port, keepalive=60)
        self.client.loop_start()

    def publish(self, topic: str, payload: dict):
        payload_json = json.dumps(payload, ensure_ascii=False)

        info = self.client.publish(
            topic,
            payload=payload_json,
            qos=self.qos,
            retain=self.retain,
        )

        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT publish failed rc={info.rc}")

        return payload_json

    def close(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
