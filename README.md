# fsm60-gateway

여러 대의 FSM60 유량센서를 Modbus TCP로 순차 읽기한 뒤, 각 장비별 MQTT 토픽으로 발행하는 Python 패키지입니다.

## 동작 구조

- `192.168.50.50:7070` → `/candh/FSM60/ID1`
- `192.168.50.51:7071` → `/candh/FSM60/ID2`
- `192.168.50.52:7072` → `/candh/FSM60/ID3`
- `192.168.50.53:7073` → `/candh/FSM60/ID4`
- `192.168.50.54:7074` → `/candh/FSM60/ID5`
- `192.168.50.55:7075` → `/candh/FSM60/ID6`

각 센서는 `unit_id=31`, `address=80`, `quantity=4`, `fc=4(Read Input Registers)` 기준입니다.

## 설치

Ubuntu 22.04에서 처음 설치하는 경우:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
cd ~
git clone https://github.com/sihyun-noh/py_mobbus_tcp_with_CandH.git
cd py_mobbus_tcp_with_CandH
chmod +x install.sh
./install.sh
```

프로젝트를 이미 내려받은 경우:

```bash
cd py_mobbus_tcp_with_CandH
./install.sh
```

`install.sh`는 현재 프로젝트 디렉터리에 `venv`와 `config.json`을 생성합니다. `/opt`로 복사하지 않으므로 설치 과정에는 `sudo`가 필요하지 않습니다.

수동 설치:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

## 실행

```bash
./venv/bin/fsm60-gateway --config config.json
```

또는:

```bash
source venv/bin/activate
fsm60-gateway --config config.json
```

## 설정 파일

`./install.sh` 실행 시 `config.json`이 없으면 `config.example.json`에서 자동 생성합니다.
현장 설정에 맞게 MQTT 서버 주소, 포트, Modbus 장비 IP/포트 등을 수정하세요.

```bash
nano config.json
```

## MQTT Payload 예시

```json
{
  "device": "FSM60",
  "id": "ID1",
  "modbus_host": "192.168.50.50",
  "modbus_port": 7070,
  "unit_id": 31,
  "address": 80,
  "instant": 12.34,
  "total": 5678.9,
  "instant_be": 12.34,
  "total_be": 5678.9,
  "instant_sw": 0.0,
  "total_sw": 0.0,
  "raw": [16709, 28836, 17842, 52429],
  "timestamp": 1710000000.123
}
```

## word_order

기본값은 `"be"`입니다.

```json
"word_order": "be"
```

값이 이상하면 `"swap"`으로 변경해서 테스트하세요.

```json
"word_order": "swap"
```

장비별로 다르게 적용할 수도 있습니다.

```json
{
  "device": "FSM60",
  "id": "ID1",
  "word_order": "swap",
  "modbus": { ... },
  "mqtt_topic": "/candh/FSM60/ID1"
}
```

## systemd 서비스 등록

수동 실행이 정상일 때만 systemd 서비스로 등록하세요. `./install.sh` 실행 후 현재 프로젝트 경로가 반영된 `fsm60-gateway.service`가 생성됩니다.

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

일반 설치와 수동 실행에는 `sudo`가 필요하지 않습니다. `sudo`는 `/etc/systemd/system/`에 서비스 파일을 복사하거나 `systemctl`로 서비스를 등록/시작할 때만 필요합니다.
