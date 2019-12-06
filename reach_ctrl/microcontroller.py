import logging
import serial
import time


class Microcontroller:
    """ Class to communicate with the REACH receiver microcontroller
        and enable/disable GPIO pins """

    def __init__(self, port, baudrate, term="\n", timeout=0.5):
        """ Class constructor
        @param port: Serial prot
        @param baudrate: Serial connection baudrate 
        @param term: Command terminator
        @param timeout: Connection timeout """

        # Set terminator symbol
        self.term = term

        # Create serial connection
        self._itf = serial.Serial(port, baudrate)
        self._itf.timeout = timeout

        logging.info('Interface info: {}'.format(self._itf.name))

        if not self.is_alive():
            logging.error('Cannot reach to microcontroller')

    def init(self):
        return True

    def _write(self, cmd):
        assert isinstance(cmd, str)
        self._itf.write(cmd + self.term)

    def _read_all(self):
        return self._itf.read_all()

    def _readline(self):
        return self._itf.readline()

    def is_alive(self):
        return 'The following commands are available:' == self.get('help').strip()

    def exit(self):
        """
        Close serial port and itself, does not shutdown the microcontroller
        """
        self._itf.close()

    def set(self, cmd):
        self._write(cmd)

    def get(self, cmd):
        self._read_all()
        self._write(cmd)
        return self._readline()

    def gpio(self, pin, val=None):

        if val==None:
            ret = self.get('gpio {}'.format(pin)).strip()
            try:
                return int(ret)
            except Exception:
                logging.warning('Got invalid value {} from gpio pin {}'.format(ret, pin), exc_info=True)
                return None
        else:
            self.set('gpio {} {}'.format(pin, val))

    def gpios(self, pins, vals=None, default=0):

        if vals==None:
            ret = []
            for p in pins:
                ret += [self.gpio(p)]
            return ret
        else:
            assert len(pins) == len(vals)
            logging.debug('Set gpio {} to {}'.format(pins, vals))
            for p in pins:
                self.gpio(p, default)
            for i in range(len(pins)):
                self.gpio(pins[i],vals[i])

