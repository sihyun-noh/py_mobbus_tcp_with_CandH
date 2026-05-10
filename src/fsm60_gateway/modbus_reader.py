import inspect
import struct
from pymodbus.client import ModbusTcpClient


class FSM60ModbusReader:
    def __init__(self, host, port, unit_id, address, quantity, timeout=1):
        self.host = host
        self.port = int(port)
        self.unit_id = int(unit_id)
        self.address = int(address)
        self.quantity = int(quantity)
        self.timeout = float(timeout)

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

    def read_once(self):
        client = ModbusTcpClient(
            host=self.host,
            port=self.port,
            timeout=self.timeout,
        )

        try:
            if not client.connect():
                raise ConnectionError(f"Modbus connect failed: {self.host}:{self.port}")

            result = self._read_input_registers(client)

            if result.isError():
                raise RuntimeError(f"Modbus error: {result}")

            registers = result.registers

            if len(registers) < 4:
                raise RuntimeError(f"Register length error: {registers}")

            return self.parse_registers(registers)

        finally:
            client.close()

    def parse_registers(self, registers):
        return {
            "raw": registers,
            "instant_be": self.regs_to_float_be(registers[0], registers[1]),
            "total_be": self.regs_to_float_be(registers[2], registers[3]),
            "instant_sw": self.regs_to_float_swap(registers[0], registers[1]),
            "total_sw": self.regs_to_float_swap(registers[2], registers[3]),
        }
