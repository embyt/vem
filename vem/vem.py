#!/usr/bin/env python3
import logging
import traceback
import signal
import os

# self-defined modules
from vem.ebus import EBusDaemon
from vem.interpreter import Interpreter
from vem.vaillant import VaillantMessage


def cb_signal_handler(received_signal, frame):
    """handles keyboard interrupts and exits execution."""
    logging.warning("Exiting with signal {}.\n".format(received_signal))
    exit()

def setup_logging():
    # set root logger to highest log level
    logging.getLogger().setLevel(logging.DEBUG)
        
    # create file and console handler
    log_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'vem.log')
    log_file = logging.FileHandler(log_filename)
    log_file.setLevel(logging.INFO)
    log_console = logging.StreamHandler()
    log_console.setLevel(logging.INFO)

    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    log_file.setFormatter(formatter)
    log_console.setFormatter(formatter)

    # add the handlers to the logger
    logging.getLogger().addHandler(log_file)
    logging.getLogger().addHandler(log_console)


def main():
    """entry point if called as an executable"""
    # setup logger
    #logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    setup_logging()
    
    # catch terminations for logging purposes
    signal.signal(signal.SIGTERM, cb_signal_handler)

    try:
        ebus = EBusDaemon()
        interpreter = Interpreter()
        vaillant = VaillantMessage()
        
        # start working
        while True:
            data = ebus._read_line()
            if data is not None:
                interpreter.interpret_msg(data)
                result_ok = vaillant.interpret_msg(interpreter)
                if not result_ok:
                    datadump = ":".join("{:02x}".format(c) for c in data)
                    logging.info("msg: " + datadump)

    # catch all possible exceptions
    except Exception:     # pylint: disable=broad-except
        logging.error(traceback.format_exc())

# check for execution
if __name__ == "__main__":
    main()
