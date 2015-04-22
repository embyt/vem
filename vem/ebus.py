import serial
import logging
import time


class EBusDaemon():
    port = None

    def __init__(self):
        # init port
        self.port = serial.Serial()
        self.port.port = '/dev/ttyUSB0'
        self.port.baudrate = 2400
        self.port.timeout = 5   # seconds
        self.port.open()
        
        # special logging for ebus
        self.logger = logging.getLogger("ebus")
        self.logger.setLevel(logging.ERROR)
        
        
    def _read_line(self, timeout = 60):
        """reads an ebus message."""
        start_time = time.time()
        data_raw = b''

        # read until we receive 0xaa
        while len(data_raw) < 1 or data_raw[-1] != 0xaa:
            # check for timeout
            if time.time() - start_time > timeout:
                # in case of a normal data timeout we return None, no exception, no logging
                return None

            # get data
            data_raw += self.port.read(1)
        # message received
        # remove SYN
        data_raw = data_raw[:-1]

        # process escape pattern
        data = data_raw.replace(b'xa9x00', b'xa9')
        data = data.replace(b'xa9x01', b'xaa')

        datadump = ":".join("{:02x}".format(c) for c in data_raw)
        
        # check validity of message
        if len(data) > 0 and self._is_message_valid(data):
            # message valid
            self.logger.debug("got: {}".format(datadump))
            return data
        else:
            # broken message
            if len(data) > 0:
                self.logger.warning("got: {}".format(datadump))
            return None

            
    def _is_message_valid(self, data):
        # check length of master part
        if len(data) < 6:
            self.logger.warning("Message too short.")
            return False
        msg_length = data[4]
        if msg_length > 16:
            self.logger.warning("Illegal message length value: {:02x}".format(msg_length))
            return False
        if len(data) < msg_length+6:
            self.logger.warning("Message too short.")
            return False
        
        # check CRC of master part
        crc_calc = self._derive_crc(data[:msg_length+5])
        crc_rec = data[msg_length+5]
        if crc_calc != crc_rec:
            self.logger.warning("CRC error: {:02x} - {:02x}".format(crc_calc, crc_rec))
            return False
        
        # check message type:
        addr_target = data[1]
        if addr_target == 0xfe:
            # broadcast message received
            if len(data) != msg_length+6:
                self.logger.warning("Illegal size of broadchast message.")
                return False
            # nothing more to do
            pass
            
        else:
            # master-master message or master-slave message
            # check ACK
            if len(data) < msg_length+7:
                self.logger.warning("Non-broadcast message too short.")
                return False
            ack = data[msg_length+6]
            if ack != 0x00:
                self.logger.warning("Negative ACK in message: {:02x}".format(ack))
                return False

            # determine message type by message length
            if len(data) == msg_length+7:
                # master-master message
                # nothing more to do
                pass
            else:
                return self._is_slave_message_valid(data[msg_length+7:])
                    
        # passed all checks
        return True
        
    def _is_slave_message_valid(self, data):
        # master-slave message
        # check length of slave message part
        slave_length = data[0]
        if len(data) != slave_length+3:
            self.logger.warning("Slave message size mismatch: {} - {}.".format(len(data), slave_length+3))
            return False

        # check CRC of slave part
        crc_calc = self._derive_crc(data[:-2])
        crc_rec = data[-2]
        if crc_calc != crc_rec:
            self.logger.warning("slave CRC error: {:02x} - {:02x}".format(crc_calc, crc_rec))
            return False

        # check ACK
        master_ack = data[-1]
        if master_ack != 0x00:
            self.logger.warning("Negative master ACK in message.")
            return False

        # passed all checks
        return True

    def _derive_crc(self, data):
        crc = 0     # init value

        for byte in data:
            # perform again escaping of message since CRC os derived on excaped data
            if byte == 0xa9 or byte == 0xaa:
                # escaping needed
                crc = self._derive_crc_byte(0xa9, crc)
                crc = self._derive_crc_byte(byte-0xa9, crc)
            else:
                # normal data byte
                crc = self._derive_crc_byte(byte, crc)

        return crc

    def _derive_crc_byte(self, byte, crc):
        for _bit in range(8):
            if crc & 0x80:
                polynom = 0x9b  # specified CRC polynom
            else:
                polynom = 0
            crc = (crc & ~0x80) << 1
            if byte & 0x80:
                crc = crc | 1
            crc = crc ^ polynom
            byte = byte << 1

        return crc
