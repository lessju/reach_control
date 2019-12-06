import logging
import visa

class SCPIInterface(object):

    def __init__(self, ip='localhost', port=5025, term='\n', timeout=100000):
        """ SCPI-1999 for Copper Mountain VNA
            Please ensure that you run VNA GUI and enable TCP interface
            before instantiate this class

            ip          default value is localhost
            port        default value is 5025
            term        termination. default value is LF (Line Feed)

            Please refer to the link below for a full list of commands
            https://coppermountaintech.com/wp-content/uploads/2019/08/TRVNA_Programming_Manual_SCPI.pdf
        """

        # Command terminal symbol
        self.term = term

        # Create VISA resource manager instance
        rm = visa.ResourceManager()

        # Connect to VISA device
        try:
            self.CMT = rm.open_resource('TCPIP0::{}::{}::SOCKET'.format(ip, port))
        except Exception:
            logging.critical('Cannot establish SCPI connection!', exc_info=True)

        # The VNA ends each line with this. Reads will timeout without this
        self.CMT.read_termination = self.term

        # Set a really long timeout period for slow sweeps
        self.CMT.timeout = timeout

    def write(self, msg, values=[]):
        """ Send a message through SCPI A termination is appended for each message """

        assert msg.endswith(self.term), '{}\nMissing read_termination in write message'.format(msg)
        self.CMT.write_ascii_values(msg, values)


    def read(self, msg):
        """ Read value or state through SCPI """
        
        assert msg.endswith(self.term), '{}\nMissing read_termination in read message'.format(msg)
        return self.CMT.query(msg)