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
        self.logger = kwargs.get('logger', logging.getLogger(__name__))
        self.logger.setLevel(kwargs.get('loggerlevel', logging.WARNING))
        self.term = kwargs.get('term', '\n')
        self.timeout = kwargs.get('timeout', 0.5)

        self._itf.timeout = self.timeout

        self.logger.info('Interface info: {}'.format(self._itf.name))

        if not self.is_alive():
            logger.error('Cannot reach to microcontroller')

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

