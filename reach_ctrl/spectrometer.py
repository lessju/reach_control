#!/usr/bin/env python
'''
This script demonstrates programming an FPGA, configuring a wideband spectrometer and plotting the received data using the Python KATCP library along with the katcp_wrapper distributed in the corr package. Designed for use with TUT3 at the 2009 CASPER workshop.\n

You need to have KATCP and CORR installed. Get them from http://pypi.python.org/pypi/katcp and http://casper.berkeley.edu/svn/trunk/projects/packetized_correlator/corr-0.4.0/

\nAuthor: Jason Manley, November 2009.

03/04/2012: Altered for 64 bit, dual channel use. Jack Hickish
'''

#TODO: add support for ADC histogram plotting.
#TODO: add support for determining ADC input level 

import time
import logging
import struct
from casperfpga import CasperFpga
import numpy as np


#START OF MAIN:
if __name__ == "__main__":

    import argparse
    from matplotlib import pyplot as plt

    logger = logging.getLogger(__name__)

    p = argparse.ArgumentParser(description='spectrometer',
        formatter_class=argparse.RawDescriptionHelpFormatter)

    p.add_argument('roach', type=str, metavar="ROACH_IP_OR_HOSTNAME")
    p.add_argument('-l', '--acc_len', type=int,
        help='Set the number of vectors to accumulate between dumps. E.g. 24414 for one second when nyquist frequency equals 200 MHz.')
    p.add_argument('-n', '--nch', type=int, required=True)
    p.add_argument('--soft', type=int, default=1)
    p.add_argument('-b', '--bitstream', type=str, )
    p.add_argument('-r', '--reset', action='store_true', default=False,)
#    p.add_argument('--adc', action='store_true', default=False,)
    p.add_argument('--linear', action='store_true', default=False,)
    p.add_argument('--shift', type=int,default=0xffffffff,)
    p.add_argument('--port', type=int, default=7147,)

    p.add_argument('-p', '--plot', nargs='?', type=str, default=None, const='',
        help='Plot figure')
    p.add_argument('--dump', nargs='?', type=str, default=None, const='spectrum.txt',
        help='Save data to file')

    args = p.parse_args()

    print('Connecting to server %s on port %i... '%(args.roach,args.port)),
    fpga = CasperFpga(args.roach, args.port, timeout=10)
    time.sleep(1)
    
    if not fpga.is_connected():
        raise RuntimeError('ERROR connecting to server %s on port %i.\n'%(roach,args.port))
    else:
        print 'done'
    
    print '------------------------'
    print 'Programming FPGA with %s...' % args.bitstream,
    if args.bitstream:
        fpga.upload_to_ram_and_program(args.bitstream)
        time.sleep(1)
        print 'done'
        fpga.write_int('fft_shift',args.shift)
    else:
        print 'Skipped.'
    
    print 'Configuring accumulation period with {}...'.format(args.acc_len),
    if args.acc_len:
        fpga.write_int('acc_len',args.acc_len)
        print 'done'
    else:
        print 'Skipped.'

    print 'Sync and reset...',
    if args.reset:
        fpga.write_int('cnt_rst',1) 
        fpga.write_int('cnt_rst',0) 
        fpga.write_int('sync_reg',1)
        fpga.write_int('sync_reg',0)
        print 'done'
    else:   
        print 'Skipped.'

    # sampling frequency
    freq = fpga.estimate_fpga_clock() * 1e6 * 4 / 2

    x = np.linspace(0, freq/1e6, args.nch)

    acc_len = fpga.read_uint('acc_len')
    acc_len_in_sec = round(acc_len * args.nch / (freq*2/4), 2)
    
### autocorrelation
    
    def get_data(ram0,ram1):
        data = np.zeros((args.nch))
        raw = fpga.read(ram0, args.nch/2*8,0)
        data[0::2] = struct.unpack('>{}Q'.format(args.nch/2),raw)
        raw = fpga.read(ram1, args.nch/2*8,0)
        data[1::2] = struct.unpack('>{}Q'.format(args.nch/2),raw)
        data[data==0]=1
        return data
    
    acc_num_prev = fpga.read_uint('acc_cnt')
    acc_num_curr = acc_num_prev

    da = np.zeros_like(get_data('even0','odd0'))
    db = np.zeros_like(da)
    dc = np.zeros_like(da)
    dd = np.zeros_like(da)

    print('Collecting auto-correlation data...')
    for i in range(args.soft):
        while acc_num_curr == acc_num_prev:
            time.sleep(acc_len_in_sec / 2)
            acc_num_curr = fpga.read_uint('acc_cnt')
        acc_num_prev = acc_num_curr
        print('Integration #{}'.format(i))
        da += get_data('even0','odd0')
        db += get_data('even1','odd1')
        dc += get_data('even2','odd2')
        dd += get_data('even3','odd3')

    data = np.asarray([da,db,dc,dd]).T
    #data = np.asarray([da,db]).T

    if args.dump is not None:
        data_to_file = np.asarray([x,da,db,dc,dd]).T
        np.savetxt(args.dump, data_to_file)

    print('Ploting auto-correlation...')
    #plt.ion()
    fig, ax = plt.subplots()
    
    if args.linear:
        ax.set_ylabel('Relative Power in linear scale')
    else:
        data[data==0]=1
        data = 10*np.log10(data)
        ax.set_ylabel('Relative Power in dBm scale')

    for i in range(data.shape[1]):
        ax.plot(x, data[:,i], label=str(i))


    if args.plot is not None:
        ax.set_xlabel('Frequency in MHz')
        ax.legend()

        sw_acc_len_in_sec = round(acc_len_in_sec * args.soft, 2)
        ax.set_title('hw int {}s, total int {}s.'.format(acc_len_in_sec, sw_acc_len_in_sec))
        
        # To dump data to file do something like:
        # #Wait for new accumulation
        # fout = open('output_file.dat','w')
        # ant0_acc_n, ant_0_data = get_data(0)
        # ant1_acc_n, ant_1_data = get_data(1)
        
        ax.legend(loc=0)
        plt.autoscale(enable=True,axis='both')

        if args.plot=='':
            plt.show()
        else:
            plt.savefig(args.plot, dpi=300)


class Spectrometer():

    def __init__(self, **kwargs):
        """
        Python module running on server side. Talk to microcontroller
        through serial port.
            itf     serial port, instance of pyserial
        """
        self.host = kwargs.get('host', 7147)
        self.port = kwargs.get('port', 7147)
        self.timeout = kwargs.get('timeout', 10)
        self.nch = kwargs.get('nch', 16384)

        self.logger = kwargs.get('logger', logging.getLogger(__name__))

        msg = 'Connecting to server {} on port {}... '.format(self.host, self.port)
        self.logger.debug(msg)
        try:
            self.fpga = CasperFpga(self.host, self.port, timeout=self.timeout)
            time.sleep(1)
            assert self.fpga.is_connected()
            self.logger.debug('Connection established.')
        except Exception as e:
            msg = 'Cannot connect to server {} on port {}.'.format(self.host, self.port)
            sel.logger.critical(msg, exc_info=True)


    def prog(self, **kwargs):

        if 'bitstream' not in kwargs:
            return False
        
        bitstream = kwargs.get('bitstream')
        from reach_ctrl.reachhelper import search
        bitstream = search(bitstream)
        if bitstream is None:
            self.logger.critical('Cannot find {}'.format(kwargs.get('bitstream')))
            return False

        self.logger.debug('Programming FPGA with {}...'.format(bitstream))
        try:
            self.fpga.upload_to_ram_and_program(bitstream)
            time.sleep(1)
            assert self.fpga.is_running()
            self.logger.debug('Programming done')
            self.nch = kwargs.get('nch', 16384)
            return True
        except Exception as e:
            msg = 'Cannot program FPGA with {}!'.format(bitstream)
            self.logger.critical(msg, exc_info=True)
            return False


    def init(self, **kwargs):

        if 'soft' not in kwargs and 'length' not in kwargs and 'shift' not in kwargs:
            return False

        if 'soft' in kwargs:
            self.soft = kwargs.get('soft')
            self.logger.debug('Set software accumulation period to {}'.format(self.soft))

        try:
            if 'shift' in kwargs:
                self.shift = kwargs.get('shift')
                self.fpga.write_int('fft_shift', self.shift)
                self.logger.debug('Set fft_shift to {}'.format(self.shift))
                
            if 'length' in kwargs:
                self.length = kwargs.get('length')
                self.fpga.write_int('acc_len', self.length)
                self.logger.debug('Set integration period to {}'.format(self.length))

            self.fpga.write_int('cnt_rst', 1) 
            self.fpga.write_int('cnt_rst', 0) 
            self.fpga.write_int('sync_reg', 1)
            self.fpga.write_int('sync_reg', 0)
            self.logger.debug('Sync and reset')
            return True
        except Exception as e:
            self.logger.error('Cannot initialize the spectometer', exc_info=True)
            return False


    def measure(self, **kwargs):

        try:
            freq = self.fpga.estimate_fpga_clock() * 1e6 * 4 / 2
            x = np.linspace(0, freq/1e6, self.nch)
            acc_len = self.fpga.read_uint('acc_len')
            acc_len_in_sec = round(acc_len * self.nch / (freq*2/4), 2)
            acc_num_prev = self.fpga.read_uint('acc_cnt')
            acc_num_curr = acc_num_prev
            self.logger.debug('Current accumulation counter: {}'.format(acc_num_curr))
        except Exception as e:
            self.logger.error('Cannot initialize measurement.', exc_info=True)

        def get_data(ram0,ram1):
            data = np.zeros((self.nch))
            raw = self.fpga.read(ram0, self.nch/2*8,0)
            data[0::2] = struct.unpack('>{}Q'.format(self.nch/2),raw)
            raw = self.fpga.read(ram1, self.nch/2*8,0)
            data[1::2] = struct.unpack('>{}Q'.format(self.nch/2),raw)
            data[data==0]=1
            return data
    
        da = np.zeros_like(get_data('even0','odd0'))
        db = np.zeros_like(da)
        dc = np.zeros_like(da)
        dd = np.zeros_like(da)
    
        self.logger.info('Spectrum integration length {}x{}'.format(acc_len, self.soft))
        try:
            for i in range(self.soft):
                while acc_num_curr == acc_num_prev:
                    time.sleep(acc_len_in_sec / 2)
                    acc_num_curr = self.fpga.read_uint('acc_cnt')
                acc_num_prev = acc_num_curr
                self.logger.debug('Integration #{}'.format(i))
                da += get_data('even0','odd0')
                db += get_data('even1','odd1')
                dc += get_data('even2','odd2')
                dd += get_data('even3','odd3')
        except Exception as e:
            self.logger.error('Cannot get measurement.', exc_info=True)
            return None
    
        data = np.asarray([da,db,dc,dd]).T
    
        return np.asarray([x,da,db,dc,dd]).T


