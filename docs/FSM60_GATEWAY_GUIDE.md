# FSM60 Gateway 구조 및 운영 가이드

## 목적

이 모듈은 여러 대의 FSM60 유량 센서를 Modbus TCP로 읽고, 읽은 값을 장비별 MQTT topic으로 발행한다.

현재 기준 환경:

- OS: Ubuntu 22.04 LTS
- Python: 3.9
- Modbus: `pymodbus==3.6.9`
- MQTT: `paho-mqtt>=1.6.1,<2.0`

## 전체 구조

센서 6개는 서로 다른 IP/port를 가진 독립 장비이므로, 센서별 read thread를 따로 둔다. MQTT publish는 별도 thread 1개가 담당한다.

```text
ID1 SensorWorker ─┐
ID2 SensorWorker ─┤
ID3 SensorWorker ─┤
ID4 SensorWorker ─┼─> Queue ─> MQTTPublishWorker ─> MQTT Broker
ID5 SensorWorker ─┤
ID6 SensorWorker ─┘
```

이 구조의 장점:

- ID2가 timeout이어도 ID1/ID4/ID6 읽기 주기를 막지 않는다.
- MQTT publish는 한 thread에서만 실행되어 안정적이다.
- 센서 read 장애와 MQTT publish 처리가 분리된다.
- 센서별 `poll_interval`, `timeout`, `reconnect_interval`을 독립적으로 조절할 수 있다.

## 프로젝트 파일 구조

```text
src/fsm60_gateway/
├── app.py             # 설정 로드, signal 처리, worker 시작/종료
├── config.py          # JSON 설정 검증
├── modbus_reader.py   # Modbus TCP 연결/읽기/파싱
├── mqtt_publisher.py  # MQTT 연결/발행
└── worker.py          # 센서 worker, MQTT publish worker
```

## 핵심 코드 설명

### `app.py`

`run()`은 전체 실행을 조율한다. 설정에서 MQTT, devices, queue 크기를 읽고 MQTT publish worker 1개와 센서 worker 여러 개를 시작한다.

```python
payload_queue = queue.Queue(maxsize=queue_size)
stop_event = threading.Event()
```

`payload_queue`는 센서 thread와 MQTT thread 사이의 전달 통로다. 센서 thread는 값을 읽어 queue에 넣고, MQTT thread는 queue에서 꺼내 publish한다.

```python
mqtt_worker = MQTTPublishWorker(mqtt_cfg, payload_queue, stop_event)
sensor_workers = [
    SensorWorker(...)
    for device_cfg in devices
]
```

종료 시에는 `stop_event`를 켜고 모든 worker를 정리한다.

```python
stop_event.set()
for worker in sensor_workers:
    worker.join(timeout=5)
mqtt_worker.join(timeout=5)
```

### `worker.py`

`SensorWorker`는 센서 1대를 담당한다.

```python
parsed = self.reader.read_once()
payload = build_payload(self.device_cfg, parsed, self.word_order)
self.payload_queue.put((device_id, topic, payload), timeout=1)
```

센서 값을 읽은 뒤 payload를 만들어 queue에 넣는다. Modbus timeout이 발생해도 해당 센서 thread 안에서만 처리되므로 다른 센서 thread는 계속 동작한다.

`MQTTPublishWorker`는 queue에서 payload를 꺼내 MQTT로 발행한다.

```python
device_id, topic, payload = self.payload_queue.get(timeout=0.5)
payload_json = self.publisher.publish(topic, payload)
```

MQTT 연결 실패 시에는 `stop_event`를 켜서 전체 프로세스가 정리되도록 한다.

### `modbus_reader.py`

`FSM60ModbusReader`는 한 센서의 Modbus TCP 연결과 register 파싱을 담당한다.

```python
result = self._read_input_registers(self.client)
```

PyModbus 버전에 따라 unit id 인자명이 달라질 수 있어 `device_id`, `slave`, `unit` 중 지원되는 이름을 자동 선택한다.

```python
for unit_key in ("device_id", "slave", "unit"):
    if unit_key in parameters:
        kwargs[unit_key] = self.unit_id
        return read_input_registers(**kwargs)
```

읽기 실패 시 연결을 닫고 `reconnect_interval` 이후 다시 시도한다.

```python
except Exception:
    self.close()
    self.next_connect_time = time.monotonic() + self.reconnect_interval
    raise
```

### `mqtt_publisher.py`

`MQTTPublisher`는 MQTT 연결과 publish를 담당한다. 현재는 MQTT publish thread에서만 호출된다.

```python
info = self.client.publish(
    topic,
    payload=payload_json,
    qos=self.qos,
    retain=self.retain,
)
```

## MQTT Payload

기본 payload는 중복 필드를 줄이고 실제 서버에 필요한 값만 보낸다.

```json
{
  "device": "FSM60",
  "id": "ID1",
  "host": "192.168.50.50",
  "instant": 12.34,
  "total": 5678.9,
  "timestamp": 1710000000.123
}
```

디버깅용 raw register가 필요하면 장비 설정에 추가한다.

```json
"include_raw": true
```

## 설정 예시

```json
{
  "mqtt": {
    "host": "192.168.50.12",
    "port": 1884,
    "qos": 2,
    "retain": false
  },
  "poll_interval": 0.5,
  "queue_size": 100,
  "word_order": "swap",
  "devices": [
    {
      "device": "FSM60",
      "id": "ID1",
      "modbus": {
        "host": "192.168.50.50",
        "port": 7070,
        "unit_id": 31,
        "address": 80,
        "quantity": 4,
        "timeout": 1,
        "retries": 3,
        "reconnect_interval": 10
      },
      "mqtt_topic": "/candh/FSM60/ID1"
    }
  ]
}
```

주요 설정:

- `poll_interval`: 각 센서 thread의 읽기 주기. 기본 예시는 센서별 약 0.5초 주기다.
- `queue_size`: 센서 thread가 MQTT thread로 전달할 payload queue 크기.
- `word_order`: 기본 float word order. 현장 테스트 기준 예제값은 `swap`, 필요 시 `be`.
- `timeout`: Modbus 연결/읽기 timeout.
- `retries`: PyModbus 내부 재시도 횟수.
- `reconnect_interval`: 실패한 센서를 다시 연결 시도하기까지 대기하는 시간.

## Ubuntu 설치 및 실행

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
cd ~
git clone https://github.com/sihyun-noh/py_mobbus_tcp_with_CandH.git
cd py_mobbus_tcp_with_CandH
chmod +x install.sh
./install.sh
```

`install.sh`는 현재 프로젝트 디렉터리에 `venv`와 `config.json`을 생성한다. `/opt`로 복사하지 않으므로 일반 설치에는 `sudo`가 필요 없다.

패키지 버전을 명시적으로 맞추려면:

```bash
./venv/bin/pip install "pymodbus==3.6.9" "paho-mqtt<2"
./venv/bin/pip install -e .
```

수동 실행:

```bash
./venv/bin/fsm60-gateway --config config.json
```

## 배포 및 업데이트 절차

### 최초 배포

Ubuntu 장비에서 처음 배포할 때는 아래 순서로 진행한다.

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
cd ~
git clone https://github.com/sihyun-noh/py_mobbus_tcp_with_CandH.git
cd py_mobbus_tcp_with_CandH
chmod +x install.sh
./install.sh
```

설정 파일을 현장값으로 수정한다.

```bash
nano config.json
```

수동 실행으로 먼저 확인한다.

```bash
./venv/bin/fsm60-gateway --config config.json
```

정상 확인 후 systemd에 등록한다.

```bash
sudo cp fsm60-gateway.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable fsm60-gateway
sudo systemctl start fsm60-gateway
```

### 코드 업데이트 배포

GitHub에 새 코드가 push된 뒤 현장 Ubuntu 장비에서 반영할 때는 아래 순서로 진행한다.

```bash
cd ~/py_mobbus_tcp_with_CandH
git pull
./venv/bin/pip install -e .
sudo systemctl restart fsm60-gateway
```

의존성 버전까지 다시 맞추고 싶으면:

```bash
./venv/bin/pip install "pymodbus==3.6.9" "paho-mqtt<2"
./venv/bin/pip install -e .
sudo systemctl restart fsm60-gateway
```

### 설정 변경 배포

`config.json`만 수정한 경우에는 Python 패키지 재설치가 필요 없다.

```bash
cd ~/py_mobbus_tcp_with_CandH
nano config.json
sudo systemctl restart fsm60-gateway
```

### 배포 후 확인

```bash
systemctl status fsm60-gateway
journalctl -u fsm60-gateway -f
```

정상 로그 예:

```text
MQTT connected: 192.168.50.12:1884
sensor worker started id=ID1 host=192.168.50.50 port=7070 interval=1.0
sent id=ID1 topic=/candh/FSM60/ID1 payload={...}
```

### 서비스 재생성

프로젝트 위치를 옮겼거나 실행 유저가 바뀐 경우에는 `install.sh`를 다시 실행해서 현재 경로 기준 service 파일을 재생성한다.

```bash
./install.sh
sudo cp fsm60-gateway.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart fsm60-gateway
```

## systemd 등록

`./install.sh` 실행 후 현재 프로젝트 경로가 반영된 `fsm60-gateway.service`가 생성된다.

systemd에 등록할 때 `/etc/systemd/system/`으로 복사하는 것은 서비스 파일뿐이다. 실행 파일, `venv`, `config.json`을 systemd 폴더로 옮기는 것이 아니다.

서비스 파일은 아래처럼 프로젝트 안의 실행 파일과 설정 파일 경로를 가리킨다.

```ini
WorkingDirectory=/home/사용자/py_mobbus_tcp_with_CandH
ExecStart=/home/사용자/py_mobbus_tcp_with_CandH/venv/bin/fsm60-gateway --config /home/사용자/py_mobbus_tcp_with_CandH/config.json
```

따라서 `config.json`은 프로젝트 폴더에 그대로 둔다. 설정값을 바꾸면 서비스만 재시작하면 새 설정이 반영된다.

```bash
sudo cp fsm60-gateway.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable fsm60-gateway
sudo systemctl start fsm60-gateway
```

상태 확인:

```bash
systemctl status fsm60-gateway
journalctl -u fsm60-gateway -f
```

설정 변경 후 재시작:

```bash
sudo systemctl restart fsm60-gateway
```

중지:

```bash
sudo systemctl stop fsm60-gateway
```

변경 내용별 필요한 명령:

| 변경한 것 | 필요한 명령 |
|---|---|
| `config.json` 수정 | `sudo systemctl restart fsm60-gateway` |
| Python 코드 수정 또는 `git pull` | `./venv/bin/pip install -e .` 후 `sudo systemctl restart fsm60-gateway` |
| `fsm60-gateway.service` 수정 | `sudo systemctl daemon-reload` 후 `sudo systemctl restart fsm60-gateway` |
| 최초 서비스 등록 | `sudo cp`, `sudo systemctl daemon-reload`, `sudo systemctl enable`, `sudo systemctl start` |

`daemon-reload`는 service 파일 자체가 바뀌었을 때 필요하다. `config.json`만 수정한 경우에는 필요하지 않다.

## 운영 중 확인 포인트

TCP 포트 확인:

```bash
nc -vz 192.168.50.50 7070
```

로그에서 정상 publish 예:

```text
sent id=ID1 topic=/candh/FSM60/ID1 payload={"device": "FSM60", ...}
```

연결 실패 예:

```text
device error id=ID2 host=192.168.50.51 port=7071 error=Modbus connect failed
```

이 경우 해당 센서 thread만 실패 처리되고, 다른 센서 thread는 계속 동작한다.

## Git 브랜치 메모

현재 main 브랜치는 thread/queue 구조를 사용한다.

이전 순차 polling에서 재연결 시도 수를 제한하던 실험은 아래 브랜치에 보존했다.

```text
sequential-reconnect-limit
```
