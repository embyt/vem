import logging
import pprint


class Interpreter():
    def __init__(self):
        self._clear_data()

    def __str__(self):
        return pprint.pformat(self.__dict__)

    def _clear_data(self):
        self.raw = []
        
        self.addr_src = None
        self.addr_dest = None
        self.cmd = None
        self.data = None
        self.slave_data = None

    def interpret_msg(self, msg):
        # we rely on valid messages, please ensure this using the ebus class before
        self._clear_data()
        # set message content
        self.raw = msg
        # extract various message parts
        self._parse_protocol()
        
    def _parse_protocol(self):
        # extract address information
        self.addr_src = self.raw[0]
        # indicate broadcast messages with destination address None
        self.addr_dest = self.raw[1] if self.raw[1] != 0xf8 else None
        
        # extract command bytes
        self.cmd = (self.raw[2]<<8) | self.raw[3]
        
        # extract master data
        self.data = []
        for i in range(self.raw[4]):
            self.data.append(self.raw[5+i])
        
        # do we face a client response message?
        if len(self.raw) > 7+len(self.data):
            # extract slave response data
            self.slave_data = []
            for i in range(self.raw[7+len(self.data)]):
                self.slave_data.append(self.raw[8+len(self.data)+i])

