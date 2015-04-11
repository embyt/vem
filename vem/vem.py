#!/usr/bin/env python3
import logging
import traceback
import signal

# self-defined modules
from vem.ebus import EBusDaemon
from vem.interpreter import Interpreter


def cb_signal_handler(received_signal, frame):
    """handles keyboard interrupts and exits execution."""
    logging.warning("Exiting with signal {}.\n".format(received_signal))
    exit()


def main():
    """entry point if called as an executable"""
    # setup logger
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    
    # catch terminations for logging purposes
    signal.signal(signal.SIGTERM, cb_signal_handler)

    try:
        ebus = EBusDaemon()
        interpreter = Interpreter()
        
        # start working
        while True:
            data = ebus._read_line()
            if data is not None:
                result_ok = interpreter.interpret_msg(data)
                if not result_ok:
                    datadump = ":".join("{:02x}".format(c) for c in data)
                    logging.info("msg: " + datadump)

    # catch all possible exceptions
    except Exception:     # pylint: disable=broad-except
        logging.error(traceback.format_exc())

# check for execution
if __name__ == "__main__":
    main()
