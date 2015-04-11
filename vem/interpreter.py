import logging
import pprint


class Interpreter():
    def __init__(self):
        self._clear_data()

    def __str__(self):
        return pprint.pformat(self.__dict__)

    def _clear_data(self):
        self.msg = []
        
        self.addr_src = None
        self.addr_dest = None
        self.cmd = None
        self.data = None
        self.slave_data = None

    def interpret_msg(self, msg):
        # we rely on valid messages, please ensure this using the ebus class before
        self._clear_data()
        # set message content
        self.msg = msg
        # extract various message parts
        self._parse_protocol()
        # interpret message content
        msg_known = self._interpret_command()
        return msg_known
        
    def _parse_protocol(self):
        # extract address information
        self.addr_src = self.msg[0]
        # indicate broadcast messages with destination address None
        self.addr_dest = self.msg[1] if self.msg[1] != 0xf8 else None
        
        # extract command bytes
        self.cmd = (self.msg[2]<<8) | self.msg[3]
        
        # extract master data
        self.data = []
        for i in range(self.msg[4]):
            self.data.append(self.msg[5+i])
        
        # do we face a client response message?
        if len(self.msg) > 7+len(self.data):
            # extract slave response data
            self.slave_data = []
            for i in range(self.msg[7+len(self.data)]):
                self.slave_data.append(self.msg[8+len(self.data)+i])

    def _interpret_command(self):
        # determine primary command
        if self.cmd >> 8 == 0xb5:
            return self._interpret_cmd_vendor()
        else:
            logging.info("unknown message: " + str(self))
            return False
            
    def _interpret_cmd_vendor(self):
        if self.cmd & 0xff == 0x04:
            # 0xb5 0x04: Get Data Block
            assert len(self.data) == 1
            if self.data[0] == 0:
                assert len(self.slave_data) == 0x0a
                logging.info("set date/time received")
            elif self.data[0] == 1:
                assert len(self.slave_data) == 0x09
                logging.info("set temperatures received")
            elif self.data[0] == 2:
                assert len(self.slave_data) == 0x07
                logging.info("set time windows received")
            elif self.data[0] == 9:
                assert len(self.slave_data) == 0x0a
                logging.info("set heater parameters received")
            elif self.data[0] == 0x0d:
                assert len(self.slave_data) == 0x05
                logging.info("set water parameters received")
            else:
                logging.warning("unknown get data block received")
                return False

        elif self.cmd & 0xff == 0x10:
            # 0xb5 0x10: Operational Data from Room Controller to Burner Control Unit
            assert len(self.data) == 9
            heatingwater_temp = self.data[2]/2
            water_temp = self.data[3]/2
            heating_enabled = (self.data[6] & 0x01) == 0
            water_enabled = (self.data[6] & 0x04) == 0
            logging.info("set: heating enabled: {}; water enabled: {}; heating temp: {}; water temp: {}"
                    .format(heating_enabled, water_enabled, heatingwater_temp, water_temp))
            # skip interpretation of slave data

        elif self.cmd & 0xff == 0x11:
            # 0xb5 0x11: Operational Data of Burner Control Unit to Room Control Unit 
            assert len(self.data) == 1
            if self.data[0] == 0x01:
                assert len(self.slave_data) == 9
                lead_heatingwater_temp = self.slave_data[0] / 2
                return_heatingwater_temp = self.slave_data[1] / 2
                outside_temp = (self.slave_data[2] | (self.slave_data[3]<<8) ) / 256
                water_temp = self.slave_data[4] / 2
                storage_water_temp = self.slave_data[5] / 2
                heating_enabled = (self.slave_data[6] & 0x01) != 0
                water_enabled = (self.slave_data[6] & 0x02) != 0
                logging.info("state: heating enabled: {}; ".format(heating_enabled)+
                        "water enabled: {}; ".format(water_enabled) +
                        "lead heating temp: {}; ".format(lead_heatingwater_temp) +
                        "return heating temp: {}; ".format(return_heatingwater_temp) +
                        "outside temp: {}; ".format(outside_temp) +
                        "water temp: {}; ".format(water_temp) +
                        "storage temp: {}".format(storage_water_temp))
            elif self.data[0] == 0x02:
                assert len(self.slave_data) == 5
                water_target_temp = self.slave_data[4] / 2
                logging.info("water target temperature: {}".format(water_target_temp))
            else:
                logging.warning("unknown 0xb5 0x11 block")
                return False
                    
        elif self.cmd & 0xff == 0x12:
            # 0xb5 0x12: Various commands
            assert len(self.data) == 0x02
            logging.info("pump commands received")
            
        elif self.cmd & 0xff == 0x16:
            # 0xb5 0x16: Broadcast Service
            assert len(self.data) > 0
            if self.data[0] == 0x00:
                # Broadcast Date/Time
                assert len(self.data) == 8
                sec = (self.data[1]>>4)*10 + (self.data[1]&0x0f)
                min = (self.data[2]>>4)*10 + (self.data[2]&0x0f)
                hour = (self.data[3]>>4)*10 + (self.data[3]&0x0f)
                day = (self.data[4]>>4)*10 + (self.data[4]&0x0f)
                month = (self.data[5]>>4)*10 + (self.data[5]&0x0f)
                weekday = (self.data[6]>>4)*10 + (self.data[6]&0x0f)
                year = 2000+(self.data[7]>>4)*10 + (self.data[7]&0x0f)
                logging.info("timestamp: {:02}.{:02}.{} {:02}:{:02}:{:02} day {}"
                        .format(day, month, year, hour, min, sec, weekday))
            elif self.data[0] == 0x01:
                # Broadcast inside temp
                assert len(self.data) == 3
                outside_temp = (self.data[1] | (self.data[2]<<8) ) / 256
                logging.info("outside temperature: {}".format(outside_temp))
            else:
                logging.warning("unknown vendor broadcast")
                return False
        else:
            logging.warning("unknown vendor message")
            return False
            
        # successfully interpreted data
        return True