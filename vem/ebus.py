import serial
import logging
import time


class EBusDaemon():
    port = None
    in_sync = False

    def __init__(self):
        # init port
        self.port = serial.Serial()
        self.port.port = '/dev/ttyUSB0'
        self.port.baudrate = 2400
        self.port.timeout = 5   # seconds
        self.port.open()
        
        
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
        
        if self._is_message_valid(data_raw, data):
            # message valid
            logging.debug("got: {}".format(datadump))
            return data
        else:
            # broken message
            logging.warning("invalid data: {}".format(datadump))
            return None

            
    def _is_message_valid(self, data_raw, data):
        # check length of master part
        if len(data) < 6:
            logging.warning("Message too short.")
            return False
        msg_length = data[4]
        if msg_length > 16:
            logging.warning("Illegal message length value: {:02x}".format(msg_length))
            return False
        if len(data) < msg_length+6:
            logging.warning("Message too short.")
            return False
        
        # check CRC of master part
        crc_calc = self._derive_crc(data[:msg_length+5])
        crc_rec = data[msg_length+5]
        if crc_calc != crc_rec:
            logging.warning("CRC error: {:02x} - {:02x}".format(crc_calc, crc_rec))
            return False
        
        # check message type:
        addr_target = data[1]
        if addr_target == 0xfe:
            # broadcast message received
            # nothing more to do
            pass
        else:
            # master-master message or master-slave message
            # check ACK
            if len(data) < msg_length+7:
                logging.warning("Non-broadchast message too short.")
                return False
            ack = data[msg_length+6]
            if ack != 0x00:
                logging.warning("Negative ACK in message: {:02x}".format(ack))
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
        if len(data) != slave_length+2:
            logging.warning("Slave message size mismatch.")
            return False

        # check CRC of slave part
        crc_calc = self._derive_crc(data[:-2])
        crc_rec = data[-2]
        if crc_calc != crc_rec:
            logging.warning("slave CRC error: {:02x} - {:02x}".format(crc_calc, crc_rec))
            return False

        # check ACK
        master_ack = data[-1]
        if master_ack != 0x00:
            logging.warning("Negative master ACK in message.")
            return False

        # passed all checks
        return True

    def _derive_crc(self, data):
        crc = 0     # init value
        CRC_POLYNOM = 0x9b

        for byte in data:
            for _bit in range(8):
                if crc & 0x80:
                    polynom = CRC_POLYNOM
                else:
                    polynom = 0
                crc = (crc & ~0x80) << 1
                if byte & 0x80:
                    crc = crc | 1
                crc = crc ^ polynom
                byte = byte << 1

        return crc
