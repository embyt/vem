import logging
import paho.mqtt.client as mqtt

# self-defined modules
from vem.interpreter import Interpreter


class VaillantMessage():
    msg = None
    
    def __init__(self):
        self.mqtt = mqtt.Client()
        self.mqtt.on_connect = self._on_connect
        self.mqtt.connect("localhost")
        self.mqtt.loop_start()

    def __str__(self):
        if self.msg is not None:
            return str(self.msg)
        else:
            return "<empty>"

    def _on_connect(self, client, userdata, flags, rc):
        '''callback for when the client receives a CONNACK response from the MQTT server.'''
        logging.info("Connected to MQTT broker with result code "+str(rc))


    def interpret_msg(self, msg):
        # we rely on valid messages, with the protocoll already parsed
        assert type(msg) is Interpreter
        self.msg = msg
        # interpret message content
        msg_known = self._interpret_command()
        return msg_known
        

    def _interpret_command(self):
        # determine primary command
        if self.msg.cmd >> 8 == 0xb5:
            return self._interpret_cmd_vendor()
        else:
            logging.info("unknown message: " + str(self))
            return False
            
    def _interpret_cmd_vendor(self):
        if self.msg.cmd & 0xff == 0x04:
            # 0xb5 0x04: Get Data Block
            assert len(self.msg.data) == 1
            # ensure presense of slave data
            if self.msg.slave_data is None or len(self.msg.slave_data) == 0:
                logging.warning("no slave data in 0xb5 0x04 block")
                return False

            if self.msg.data[0] == 0:
                # status data block: timestamp and outside temperature
                assert len(self.msg.slave_data) == 0x0a
                # timestmap
                # the timestamp received here seems to be invalid; date is only 0xff
                # seconds count correctly but the absolute value is just totaly wrong
                # it seems the burner unit does not hold a valid time
                logging.debug("status data block 0: {}".format(":".join("{:02x}".format(c) for c in self.msg.slave_data)))
                # outside temperature
                outside_temp = (self.msg.slave_data[8] | (self.msg.slave_data[9]<<8) ) / 256
                self.mqtt.publish("vem/temp/outside", outside_temp)
                
            elif self.msg.data[0] == 1:
                assert len(self.msg.slave_data) == 0x09
                logging.info("set temperatures received")
            elif self.msg.data[0] == 2:
                assert len(self.msg.slave_data) == 0x07
                logging.info("set time windows received")
            elif self.msg.data[0] == 9:
                assert len(self.msg.slave_data) == 0x0a
                logging.info("set heater parameters received")
            elif self.msg.data[0] == 0x0d:
                assert len(self.msg.slave_data) == 0x05
                logging.info("set water parameters received")
            else:
                logging.warning("unknown get data block received")
                return False

        elif self.msg.cmd & 0xff == 0x05:
            # 0xb5 0x05: SetOperationMode
            # this is always 10:fe:b5:05:02:29:00:2c (in summer)
            # this message is sent once each hour
            logging.debug("unknown SetOperationMode message" + str(self))
            #return False

        elif self.msg.cmd & 0xff == 0x10:
            # 0xb5 0x10: Operational Data from Room Controller to Burner Control Unit
            assert len(self.msg.data) == 9
            heatingwater_temp = self.msg.data[2]/2
            water_temp = self.msg.data[3]/2
            heating_enabled = (self.msg.data[6] & 0x01) == 0
            water_enabled = (self.msg.data[6] & 0x04) == 0
            # skip interpretation of slave data
            
            logging.debug("set: heating enabled: {}; water enabled: {}; heating temp: {}; water temp: {}"
                    .format(heating_enabled, water_enabled, heatingwater_temp, water_temp))

        elif self.msg.cmd & 0xff == 0x11:
            # 0xb5 0x11: Operational Data of Burner Control Unit to Room Control Unit 
            assert len(self.msg.data) == 1
            # ensure presense of slave data
            if self.msg.slave_data is None or len(self.msg.slave_data) == 0:
                logging.warning("no slave data in 0xb5 0x11 block")
                return False

            if self.msg.data[0] == 0x01:
                assert len(self.msg.slave_data) == 9
                lead_heatingwater_temp = self.msg.slave_data[0] / 2
                return_heatingwater_temp = self.msg.slave_data[1] / 2
                outside_temp = (self.msg.slave_data[2] | (self.msg.slave_data[3]<<8) ) / 256
                water_temp = self.msg.slave_data[4] / 2
                storage_water_temp = self.msg.slave_data[5] / 2
                heating_enabled = (self.msg.slave_data[6] & 0x01) != 0
                water_enabled = (self.msg.slave_data[6] & 0x02) != 0
                logging.debug("state: heating enabled: {}; ".format(heating_enabled)+
                        "water enabled: {}; ".format(water_enabled) +
                        "lead heating temp: {}; ".format(lead_heatingwater_temp) +
                        "return heating temp: {}; ".format(return_heatingwater_temp) +
                        "outside temp: {}; ".format(outside_temp) +
                        "water temp: {}; ".format(water_temp) +
                        "storage temp: {}".format(storage_water_temp))
                self.mqtt.publish("vem/heating/enabled", heating_enabled)
                self.mqtt.publish("vem/heating/water_temp_lead", lead_heatingwater_temp)
                self.mqtt.publish("vem/heating/water_temp_return", return_heatingwater_temp)
                self.mqtt.publish("vem/water/enabled", water_enabled)
                self.mqtt.publish("vem/water/temp", water_temp)
                self.mqtt.publish("vem/water/storage_temp", storage_water_temp)
                self.mqtt.publish("vem/temp/outside", outside_temp)
                        
            elif self.msg.data[0] == 0x02:
                assert len(self.msg.slave_data) == 5
                water_target_temp = self.msg.slave_data[4] / 2
                logging.debug("water target temperature: {}".format(water_target_temp))
                self.mqtt.publish("vem/water/target_temp", water_target_temp)
                
            else:
                logging.warning("unknown 0xb5 0x11 block")
                return False
                    
        elif self.msg.cmd & 0xff == 0x12:
            # 0xb5 0x12: Various commands
            assert len(self.msg.data) == 0x02
            logging.debug("pump commands received: Nachladeverzögerung: {:02x} {:02x}"
                    .format(self.msg.data[0], self.msg.data[1]))
            
        elif self.msg.cmd & 0xff == 0x16:
            # 0xb5 0x16: Broadcast Service
            assert len(self.msg.data) > 0
            if self.msg.data[0] == 0x00:
                # Broadcast Date/Time
                assert len(self.msg.data) == 8
                sec = (self.msg.data[1]>>4)*10 + (self.msg.data[1]&0x0f)
                min = (self.msg.data[2]>>4)*10 + (self.msg.data[2]&0x0f)
                hour = (self.msg.data[3]>>4)*10 + (self.msg.data[3]&0x0f)
                day = (self.msg.data[4]>>4)*10 + (self.msg.data[4]&0x0f)
                month = (self.msg.data[5]>>4)*10 + (self.msg.data[5]&0x0f)
                weekday = (self.msg.data[6]>>4)*10 + (self.msg.data[6]&0x0f)
                year = 2000+(self.msg.data[7]>>4)*10 + (self.msg.data[7]&0x0f)
                timestamp = "{:02}.{:02}.{} {:02}:{:02}:{:02}".format(day, month, year, hour, min, sec)
                logging.debug("timestamp: {}".format(timestamp))
                self.mqtt.publish("vem/misc/timestamp", timestamp)
                
            elif self.msg.data[0] == 0x01:
                # Broadcast outside temp
                assert len(self.msg.data) == 3
                outside_temp = (self.msg.data[1] | (self.msg.data[2]<<8) ) / 256
                logging.debug("outside temperature: {}".format(outside_temp))
                # this is already published from 0xb5 0x11 message
                #self.mqtt.publish("vem/temp/outside", outside_temp)
            else:
            
                logging.warning("unknown vendor broadcast")
                return False
        else:
            logging.warning("unknown vendor message")
            return False
            
        # successfully interpreted data
        return True
