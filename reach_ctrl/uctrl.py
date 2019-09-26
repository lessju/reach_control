import time
import logging


class Microcontroller:

    def __init__(self, itf, **kwargs):
        """
        Python module running on server side. Talk to microcontroller
        through serial port.
            itf     serial port, instance of pyserial
        """
        self._itf = itf
        logging.basicConfig()
        self.logger = kwargs.get('logger', logging.getLogger(__name__))
        self.term = kwargs.get('term', '\n')
        self.timeout = kwargs.get('timeout', 0.5)

        self._itf.timeout = self.timeout

        self.logger.info('Interface info: {}'.format(self._itf.name))

        if not self.is_alive():
            self.logger.error('Cannot reach to microcontroller')

    def init(self, **kwargs):
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

    def gpio(self, pin, val=None, **kwargs):

        if val==None:
            ret = self.get('gpio {}'.format(pin)).strip()
            try:
                return int(ret)
            except Exception as e:
                self.logger.warning('Got invalid value {} from gpio pin {}'.format(ret,pin),exc_info=True)
                return None
        else:
            self.set('gpio {} {}'.format(pin, val))

    def gpios(self, pins, vals=None, **kwargs):

        default = kwargs.get('default', 0)

        if vals==None:
            ret = []
            for p in pins:
                ret += [self.gpio(p)]
            return ret
        else:
            assert len(pins) == len(vals)
            self.logger.debug('Set gpio {} to {}'.format(pins, vals))
            for p in pins:
                self.gpio(p, default)
            for i in range(len(pins)):
                self.gpio(pins[i],vals[i])

