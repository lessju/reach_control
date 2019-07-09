import logging
import time
import numpy as np

class SCPIInterface(object):

    def __init__(self, ip='localhost', port=5025, **kwargs):
        """ SCPI-1999
        """

        self.ip = ip
        self.port = port

        self.logger = kwargs.get('logger', logging.getLogger(__name__))
        self.logger.setLevel(kwargs.get('loggerlevel', logging.WARNING))
        self.term = kwargs.get('term', '\n')
        self.timeout = kwargs.get('timeout', 100000)

        import visa
        rm = visa.ResourceManager()
        #Connect to a Socket on the local machine at 5025
        #Use the IP address of a remote machine to connect to it instead
        try:
            self.CMT = rm.open_resource('TCPIP0::{}::{}::SOCKET'.format(ip,port))
        except Exception as e:
            self.logger.debug(e)
            self.logger.debug('Failure to connect to VNA at {}:{}!'.format(ip,port))

        #The VNA ends each line with this. Reads will time out without this
        self.CMT.read_termination = self.term

        #Set a really long timeout period for slow sweeps
        self.CMT.timeout = self.timeout

    def write(self, msg, **kwargs):

        assert msg.endswith(self.term), \
            '{}\nMissing read_termination in write message'.format(msg)

        val = kwargs.get('values', [])

        self.CMT.write_ascii_values(msg, val)


    def read(self, msg):

        assert msg.endswith(self.term), \
            '{}\nMissing read_termination in read message'.format(msg)

        return self.CMT.query(msg)



class VNA(object):

    def __init__(self, interface, **kwargs):

        self.itf = interface
        self.logger = kwargs.get('logger', logging.getLogger(__name__))
        self.logger.setLevel(kwargs.get('loggerlevel', logging.WARNING))
        self.term = kwargs.get('term', '\n')

    def init(self):
        # To do list
        # Set frequency range
        # Set IF bandwidth
        
        self.channel(1)
        self.freq(0,200)
        self.ifbw(1000)
        self.write('TRIG:SOUR BUS')
        self.calib_kit(23)

    def write(self, cmd):
        assert isinstance(cmd, str)
        self.itf.write(cmd + self.term)

    def read(self, cmd):
        assert isinstance(cmd, str)
        return self.itf.read(cmd + self.term)

    def freq(self, start=50, stop=150):
        """
        SENSe<Ch>:FREQuency:STARt <frequency>
        SENSe<Ch>:FREQuency:STOP <frequency>
        """
        assert isinstance(start, int)
        assert isinstance(stop, int)
        assert start < stop
        self.write('SENS1:FREQ:STAR {} MHZ'.format(start))
        self.write('SENS1:FREQ:STOP {} MHZ'.format(stop))

    def ifbw(self, res=1000):
        """
        SENSe<Ch>:BWIDth[:RESolution] <frequency>
        In steps of 10, 30, 100, 300, 1000, 3000, 10000, 30000
        """
        STEP = [1, 3, 10, 30, 100, 300, 1000, 3000, 10000, 30000]
        assert isinstance(res, int) and res in range(1,30001)
        assert any([res % step == 0 for step in STEP if res >= step])
        self.write('SENS1:BWID {} HZ'.format(res))

    def channel(self, ch=1):
        """
        DISPlay:WINDow<Ch>:ACTivate
        Sets the active channel (no query)
        """
        
        self.write('DISP:WIND{}:ACT'.format(ch))

    def calib_kit(self, kit=15):
        """
        SENSe<cnum>:CORRection:COLLect:CKIT[:SELect] <numeric>
        MMEMory:LOAD:CKIT<Ck> <string>
        """
        self.write('SENS1:CORR:COLL:CKIT {}'.format(kit))

    def calib(self, std, **kwargs):
        """
        SENSe<Ch>:CORRection:COLLect[:ACQuire]:OPEN <port>
        SENSe<Ch>:CORRection:COLLect[:ACQuire]:SHORt <port>
        SENSe<Ch>:CORRection:COLLect[:ACQuire]:LOAD <port>
        SENSe<Ch>:CORRection:COLLect[:ACQuire]:THRU <rcvport>, <srcport>
        """

        STD = ['open',
            'short',
            'load',
            'sload', #(sliding load)
            'thru', #(through)
            'arbi', #(arbitrary)
            'databased', #(data-based)
        ]

        port = kwargs.get('port', 1)
        srcport = kwargs.get('srcport', 1)
        rcvport = kwargs.get('rcvport', 2)

        std = std.lower()
        assert std in STD

        if std=='thru':
            port = '{},{}'.format(rcvport, srcport)

        self.write('SENS1:CORR:COLL:{} {}'.format(std, port))

    def calib_apply(self):
        """
        SENSe<Ch>:CORRection:COLLect:SAVE
        """
        self.write('SENS1:CORR:COLL:SAVE')

    def state_save(self, stype='CSTate', reg='A'):
        """
        MMEMory:STORe:STYPe {STATe|CSTate|DSTate|CDSTate}
            STATe       Measurement conditions
            CSTate      Measurement conditions and calibration tables
            DSTate      Measurement conditions and data traces
            CDSTate     Measurement conditions, calibration tables and data
                        traces
        MMEMory:STORe:CHANnel[:STATe] {A|B|C|D}
            A   Save to register A
            B   Save to register B
            C   Save to register C
            D   Save to register D
        """
        STYPE = ['state', 'cstate', 'dstate', 'cdstate',]
        REG = ['a','b','c','d',]
        assert stype.lower() in STYPE
        assert reg.lower() in REG

        self.write('MMEM:STOR:STYP {}'.format(stype))
        self.write('MMEM:STOR:CHAN {}'.format(reg))

    def state_recall(self, reg='A'):
        """
        MMEMory:LOAD:CHANnel[:STATe] {A|B|C|D}
            A   Recall from register A
            B   Recall from register B
            C   Recall from register C
            D   Recall from register D
        """
        REG = ['a','b','c','d',]
        assert reg.lower() in REG
        self.write('MMEM:LOAD:CHAN {}'.format(reg))

    def trace(self, s11='MLOG', s21='MLOG', res=1001):

        #Set up 2 traces, S11, S21
        self.write('CALC1:PAR:COUN 2') # 2 Traces
        self.write('CALC1:PAR1:DEF S11') #Choose S11 for trace 1
        self.write('CALC1:TRAC1:FORM {}'.format(s11))  #log Mag format
        
        #Format can be SMIT or POL or SWR and many other types
        self.write('CALC1:PAR2:DEF S21') #Choose S21 for trace 2
        self.write('CALC1:TRAC2:FORM {}'.format(s21)) #Log Mag format
        self.write('DISP:WIND1:TRAC2:Y:RPOS 1') #Move S21 up
        self.write('SENS1:SWE:POIN {}'.format(res))  #Number of points

    def snp_save(self, name, fmt='ri'):
        """
        MMEMory:STORe:SNP:FORMat {RI|DB|MA}
            " MA" Logarithmic Magnitude / Angle format
            " DB" Linear Magnitude / Angle format
            " RI" Real part /Imaginary part format
        MMEMory:STORe:SNP[:DATA] <string>
            Saves the measured S-parameters of the active channel into a
            Touchstone file. The file type (1-port or 2-port) is set by the
            MMEM:STOR:SNP:TYPE:S1P and MMEM:STOR:SNP:TYPE:S2P
            commands. 1-port type file saves one reflection parameter: S11 or
            S22. 2-port type file saves all the four parameters: S11, S21, S12,
            S22. (no query)
        """

        FORMAT = ['ri','db','ma']
        assert fmt.lower() in FORMAT

        self.write('MMEM:STOR:SNP:TYPE:S2P 1,2') # not mentioned in manual
        self.write('MMEM:STOR:SNP:FORM {}'.format(fmt))
        self.write('MMEM:STOR:SNP "{}"'.format(name))
        

    def measure(self):

        #Trigger a measurement
        self.write('TRIG:SEQ:SING') #Trigger a single sweep
        self.wait()
        Freq = self.read('SENS1:FREQ:DATA?') #Get data as string
        S11 = self.read('CALC1:TRAC1:DATA:FDAT?') #Get data as string
        S21 = self.read('CALC1:TRAC2:DATA:FDAT?') #Get data as string
        
        #split the long strings into a string list
        #also take every other value from magnitues since second value is 0
        #If complex data were needed we would use polar format and the second
        #value would be the imaginary part
        Freq = Freq.split(',')
        S11 = S11.split(',')
        #S11 = S11[::2]
        S21 = S21.split(',')
        #S21 = S21[::2]

        #Chage the string values into numbers
        S11 = np.asarray([float(s) for s in S11])
        S21 = np.asarray([float(s) for s in S21])
        S11 = S11[::2] + 1j * S11[1::2]
        S21 = S21[::2] + 1j * S21[1::2]
        Freq = [float(f)/1e6 for f in Freq]
        return np.vstack((Freq,S11,S21)).T

    def wait(self):
        self.read('*OPC?') #Wait for measurement to complete
