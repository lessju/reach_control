import numpy as np
import logging
import time

from reach_ctrl.scpi_interface import SCPIInterface

class VNA(object):

    def __init__(self, term="\n"):
        """ Tested on Copper Mountain VNA TR1300/1
            interface       SCPIInterface
            term
        """
        # Create VISA interface
        self.itf = SCPIInterface()

        # Set termination symbol
        self.term = term

    def init(self, channel=1, freqstart=40, freqstop=180, ifbw=1000, average=20, calib_kit=23, power_level=-5):
        """ VNA Initialization

            Possible options are:
            channel     1
            freqstart   start frequency in MHz
            freqstop    stop frequency in MHz
            ifbw        intermediate frequency bandwidth
            average     e.g. 10
            power_level in dBm
            calib_kit   defined in VNA GUI
        """
        
        # Set parameters
        self.channel(channel)
        self.freq(start=freqstart, stop=freqstop)
        self.ifbw(ifbw)
        self.average(average)
        self.calib_kit(calib_kit)
        self.power_level(power_level)

        return True

    def write(self, cmd):
        assert isinstance(cmd, str)
        self.itf.write(cmd + self.term)

    def read(self, cmd):
        assert isinstance(cmd, str)
        return self.itf.read(cmd + self.term)

    def freq(self, start=None, stop=None):
        """ Set start and stop frequency in MHz
            If no parameters provided, this method returns current frequency

        The corresponding SCPI commands are:
        SENSe<Ch>:FREQuency:STARt <frequency>
        SENSe<Ch>:FREQuency:STOP <frequency>
        """
        assert isinstance(start, int) or start == None
        assert isinstance(stop, int) or stop == None
        if isinstance(start, int) and isinstance(stop, int):
            assert start < stop

        if isinstance(start, int):
            self.write('SENS1:FREQ:STAR {} MHZ'.format(start))
            logging.debug('Set start frequency to {} MHz'.format(start))
        if isinstance(start, int):
            self.write('SENS1:FREQ:STOP {} MHZ'.format(stop))
            logging.debug('Set stop frequency to {} MHz'.format(stop))

        if start is None and stop is None:
            start = self.read('SENS1:FREQ:STAR?').strip()
            stop = self.read('SENS1:FREQ:STOP?').strip()
            return (float(start), float(stop))

    def ifbw(self, res=None):
        """ Set IF bandwidth resolution
            if no parameter provided, this returns current ifbw resolution

        The corresponding SCPI command is:
        SENSe<Ch>:BWIDth[:RESolution] <frequency>
        available options are:
            10, 30, 100, 300, 1000, 3000, 10000, 30000
        """
        STEP = [1, 3, 10, 30, 100, 300, 1000, 3000, 10000, 30000]
        if res:
            assert res in STEP
            self.write('SENS1:BWID {} HZ'.format(res))
            logging.debug('Set IF bandwidth to {}'.format(res))
        else:
            self.read('SENS1:BWID?')

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
        logging.debug('Calibration kit #{} selected'.format(kit))

    def calib(self, std=None, port=1, source_port=1, receive_port=2):
        """ Calculate calibration data and apply

        E.g.
        calib('open')   switch to open standard and calculate
        calib('short')  switch to short standard and calculate
        calib('load')   switch to load standard and calculate
        calib('apply')  Apply calibration data

        SENSe<Ch>:CORRection:COLLect:METHod[:RESPonse]:OPEN <port>
        SENSe<Ch>:CORRection:COLLect:METHod[:RESPonse]:SHORt <port>
        SENSe<Ch>:CORRection:COLLect:METHod[:RESPonse]:LOAD <port>
        SENSe<Ch>:CORRection:COLLect:METHod:ERESponse <rcvport>, <srcport>

        SENSe<Ch>:CORRection:COLLect[:ACQuire]:OPEN <port>
        SENSe<Ch>:CORRection:COLLect[:ACQuire]:SHORt <port>
        SENSe<Ch>:CORRection:COLLect[:ACQuire]:LOAD <port>
        SENSe<Ch>:CORRection:COLLect[:ACQuire]:THRU <rcvport>, <srcport>

        SENSe<Ch>:CORRection:COLLect:METHod:SOLT1 <port>
        SENSe<Ch>:CORRection:COLLect:METHod:TYPE?
        SENSe<Ch>:CORRection:STATe {ON|OFF|1|0}
        SENSe<Ch>:CORRection:STATe?
        SENSe<Ch>:CORRection:COLLect:SAVE
        """

        STD = ['open',
            'short',
            'load',
            'thru', #(through)

            'off',
            'on',
            'apply',
            None,

            'sload', #(sliding load)
            'arbi', #(arbitrary)
            'databased', #(data-based)
        ]

        srcport = source_port
        rcvport = receive_port

        std = std.lower()
        assert std in STD

        if std=='thru':
            port = '{},{}'.format(rcvport, srcport)

        if std in ['open', 'short', 'load',]:
            logging.debug('Select calibration standard {}'.format(std))
            self.write('SENS1:CORR:COLL:METH:{} {}'.format(std, port))
            logging.debug('Measure under calibration standard {}'.format(std))
            self.write('SENS1:CORR:COLL:{} {}'.format(std, port))

        elif std == 'thru':
            logging.debug('Select calibration standard {}'.format(std))
            self.write('SENS1:CORR:COLL:METH:{} {}'.format('ERES', port))
            logging.debug('Measure under calibration standard {}'.format(std))
            self.write('SENS1:CORR:COLL:{} {}'.format(std, port))

        elif std in ['on','off']:
            logging.debug('Switch {} calibration'.format(std))
            self.write('SENS1:CORR:COLL:STAT {}'.format(std))

        elif std == 'apply':
            logging.debug('Apply calibration data')
            self.write('SENS1:CORR:COLL:SAVE')

        elif std == None:
            ret = self.read('SENS1:CORR:STAT?').strip()
            return int(ret)

        else:
            logging.warn('calibration standard {} not implemented'.format(std))

    def state_save(self, filename, stype="CSTate"):
        """
        MMEMory:STORe:STYPe {STATe|CSTate|DSTate|CDSTate}
            STATe       Measurement conditions
            CSTate      Measurement conditions and calibration tables
            DSTate      Measurement conditions and data traces
            CDSTate     Measurement conditions, calibration tables and data
                        traces

        MMEMory:STORe[:STATe] <string>
        """


        STYPE = ['state', 'cstate', 'dstate', 'cdstate',]
        assert stype.lower() in STYPE

        self.write('MMEM:STOR:STYP {}'.format(stype))
        self.write('MMEM:STOR "{}"'.format(filename))
        logging.debug('Save system state of type {} to file {}'.format(stype, filename))

    def state_recall(self, filename):
        """
        MMEMory:LOAD[:STATe] <string>
        """
        self.write('gMMEM:LOAD {}'.format(filename))
        loggin.debug('Load system state from file {}'.format(filename))
        

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

    def snp_save(self, name, save_format="ri"):
        """ Save measurement in touchstone file
            fmt     save format
                    
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
        assert save_format.lower() in FORMAT

        self.write('MMEM:STOR:SNP:TYPE:S2P 1,2') # not mentioned in manual
        self.write('MMEM:STOR:SNP:FORM {}'.format(save_format))
        self.write('MMEM:STOR:SNP "{}"'.format(name))
        logging.debug('Save touchstone file in {} format at {}'.format(save_format, name))

    def power_level(self, dbm=None):
        """
        SOURce<Ch>:POWer[:LEVel][:IMMediate][:AMPLitude] <power>
            <power>     the power level from -55 to +3
                        Resolution 0.05
        """

        def myround(x, base=0.05):
            return base * round(x / base)

        if dbm == None:
            return self.read('SOUR1:POW?') #Get data as string
        elif dbm <=3 and dbm >=-55:
            mydbm = myround(dbm)
            self.write('SOUR1:POW {}'.format(mydbm))
            logging.debug('Set power level to {}'.format(mydbm))
        else:
            raise ValueError('Invalid parameter')

    def power_slope(self, slope=None):
        """
        SOURce<Ch>:POWer[:LEVel]:SLOPe[:DATA] <power>
            <power>     the power slope value from -2 to +2
                        Resolution 0.1
        """
        if slope == None:
            return self.read('SOUR1:POW:SLOP?') #Get data as string
        elif dbm <=3 and dbm >=-55:
            myslope = round(slope, 1)
            self.write('SOUR1:POW:SLOP {}'.format(myslope))
            logging.debug('Set power slope to {}'.format(myslope))
        else:
            raise ValueError('Invalid parameter')

    def power_freq(self, freq=None):
        """
        SENSe<Ch>:FREQuency[:CW] <frequency>
            <frequency> for TR1300/1 between 3e5 and 1.3e9
        """
        if freq == None:
            return self.read('SENS1:FREQuency?') #Get data as string
        elif freq in range(3e5, 1.3e9+1):
            self.write('SENS1:FREQ {}'.format(freq))
            logging.debug('Set power frequency to {}'.format(freq))
        else:
            raise ValueError('Invalid parameter')

    def power_enable(self, enable=None):
        """
        OUTPut[:STATe] {ON|OFF|1|0}
        """
        if enable == None:
            return self.read('OUTP?') #Get data as string
        elif enable:
            self.write('OUTP 1')
            logging.debug('Enable power output')
        elif not enable:
            self.write('OUTP 0')
            logging.debug('Disable power output')
        else:
            raise ValueError('Invalid parameter')

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

    def average(self, cnt=None):
        """
        SENSe<Ch>:AVERage[:STATe] {ON|OFF|1|0}
        SENSe<Ch>:AVERage[:STATe]?
        SENSe<Ch>:AVERage:COUNt <numeric>
        SENSe<Ch>:AVERage:COUNt?
        """
        if cnt == None:
            if self.read('SENS1:AVER?') == '0':
                return 0
            else:
                ret = self.read('SENS1:AVER:COUN?')
                return int(ret)
        else:
            if cnt == 0:
                self.write('SENS1:AVER 0')
                logging.debug('Disable average')
            else:
                self.write('SENS1:AVER 1')
                self.write('SENS1:AVER:COUN {}'.format(cnt))
                logging.debug('Set average to {}'.format(cnt))

    def sweep(self, spoints=None, stime=None, stype=None):
        """
        SENSe<Ch>:SWEep:POINts <numeric>
        SENSe<Ch>:SWEep:POINts?
        SENSe<Ch>:SWEep:POINt:TIME <time>
        SENSe<Ch>:SWEep:POINt:TIME?
        SENSe<Ch>:SWEep:TYPE {LINear|LOGarithmic|SEGMent|POWer|VVM}
        SENSe<Ch>:SWEep:TYPE?
        """

        STYPE = ['linear','logarithmic','segment','power','vvm']
        if spoints == None and stime == None and stype == None:
            spoints = int(self.read('SENS1:SWE:POIN?'))
            stime = float(self.read('SENS1:SWE:POIN:TIME?'))
            stype = self.read('SENS1:SWE:TYPE?')
            return {'points':spoints,'time':stime,'type':stype}
        else:
            if isinstance(spoints, int):
                self.write('SENS1:SWE:POIN {}'.format(spoints))
                logging.debug('Set sweep points to {}'.format(spoints))
            if isinstance(stime, int):
                self.write('SENS1:SWE:POIN:TIME {}'.format(stime))
                logging.debug('Set sweep time to {} second(s)'.format(stime))
            if isinstance(stype, str) and stype.lower() in STYPE:
                self.write('SENS1:SWE:TYPE {}'.format(stype))
                logging.debug('Set sweep type to {} '.format(stype))

