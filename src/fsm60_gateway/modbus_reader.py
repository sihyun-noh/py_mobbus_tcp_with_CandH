import inspect
import struct
import time
from pymodbus.client import ModbusTcpClient


class FSM60ModbusReader:
    def __init__(
        self,
        host,
        port,
        unit_id,
        address,
        quantity,
        timeout=1,
        retries=3,
        reconnect_interval=10,
    ):
        self.host = host
        self.port = int(port)
        self.unit_id = int(unit_id)
        self.address = int(address)
        self.quantity = int(quantity)
        self.timeout = float(timeout)
        self.retries = int(retries)
        self.reconnect_interval = float(reconnect_interval)
        self.next_connect_time = 0.0
        self.client = ModbusTcpClient(
            host=self.host,
            port=self.port,
            timeout=self.timeout,
            retries=self.retries,
        )

    @staticmethod
    def regs_to_float_be(w0, w1):
        raw = struct.pack(">HH", int(w0), int(w1))
        return struct.unpack(">f", raw)[0]

    @staticmethod
    def regs_to_float_swap(w0, w1):
        raw = struct.pack(">HH", int(w1), int(w0))
        return struct.unpack(">f", raw)[0]

    def _read_input_registers(self, client):
        read_input_registers = client.read_input_registers
        kwargs = {
            "address": self.address,
            "count": self.quantity,
        }

        try:
            parameters = inspect.signature(read_input_registers).parameters
        except (TypeError, ValueError):
            parameters = {}

        for unit_key in ("device_id", "slave", "unit"):
            if unit_key in parameters:
                kwargs[unit_key] = self.unit_id
                return read_input_registers(**kwargs)

        for unit_key in ("device_id", "slave", "unit"):
            try:
                return read_input_registers(**kwargs, **{unit_key: self.unit_id})
            except TypeError as exc:
                if "unexpected keyword argument" not in str(exc):
                    raise

        return read_input_registers(**kwargs)

    def connect(self):
        if self.client.is_socket_open():
            return True

        return self.client.connect()

    def close(self):
        self.client.close()

    def seconds_until_retry(self):
        return max(0.0, self.next_connect_time - time.monotonic())

    def read_once(self):
        wait_time = self.seconds_until_retry()
        if wait_time > 0:
            raise ConnectionError(
                f"Modbus reconnect pending: {self.host}:{self.port} retry_after={wait_time:.1f}s"
            )

        try:
            if not self.connect():
                raise ConnectionError(f"Modbus connect failed: {self.host}:{self.port}")

            result = self._read_input_registers(self.client)

            if result.isError():
                raise RuntimeError(
                    "Modbus read_input_registers failed "
                    f"host={self.host} port={self.port} unit_id={self.unit_id} "
                    f"address={self.address} quantity={self.quantity} "
                    f"timeout={self.timeout} retries={self.retries} error={result}"
                )

            registers = result.registers

            if len(registers) < 4:
                raise RuntimeError(f"Register length error: {registers}")

            self.next_connect_time = 0.0
            return self.parse_registers(registers)
        except Exception:
            self.close()
            self.next_connect_time = time.monotonic() + self.reconnect_interval
            raise

    def parse_registers(self, registers):
        return {
            "raw": registers,
            "instant_be": self.regs_to_float_be(registers[0], registers[1]),
            "total_be": self.regs_to_float_be(registers[2], registers[3]),
            "instant_sw": self.regs_to_float_swap(registers[0], registers[1]),
            "total_sw": self.regs_to_float_swap(registers[2], registers[3]),
        }
