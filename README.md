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

```bash
cd fsm60_gateway_package
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
fsm60-gateway --config config.example.json
```

또는:

```bash
python3 -m fsm60_gateway --config config.example.json
```

## 설정 파일

`config.example.json`을 복사해서 현장 설정으로 사용하세요.

```bash
cp config.example.json config.json
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

`./install.sh` 실행 후 현재 프로젝트 경로가 반영된 `fsm60-gateway.service`가 생성됩니다.

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
