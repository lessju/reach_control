import time
import math
import socket
import h5py
import numpy as np
import matplotlib.pyplot as plt
from struct import *
from optparse import OptionParser


class SpeadRx:
    def __init__(self, write_hdf5, nof_fpga, show_plot=True):

        self.write_hdf5 = write_hdf5

        self.nof_fpga = nof_fpga
        self.nof_signals_per_fpga = 1
        self.nof_signals = self.nof_signals_per_fpga * nof_fpga
        self.frequency_channels = 16*1024
        self.data_width = 64
        self.data_byte = int(self.data_width / 8)
        self.byte_per_packet = 1024
        self.word_per_packet = int(self.byte_per_packet / self.data_byte)
        self.expected_nof_packets = int(self.nof_signals * self.frequency_channels * self.data_byte / self.byte_per_packet)

        self.line = [0]*self.nof_signals
        self.recv_packets = 0
        self.center_frequency = 0
        self.payload_length = 0
        self.sync_time = 0
        self.timestamp = 0
        self.prev_timestamp_ivqu = 0
        self.prev_timestamp_channel = 0
        self.csp_channel_info = 0
        self.csp_antenna_info = 0
        self.capture_mode = 0
        self.tpm_info = 0
        self.fpga_id = 0
        self.offset = 13 * 8
        self.pkt_cnt = 0
        self.logical_channel_id = 0
        self.packet_counter = 0
        self.start_antenna_id = 0
        self.id = 0
        self.is_spead = 0
        self.processed_frame = 0
        self.buffer_id = 0
        self.is_floating_point = 0
        self.first_packet = True
        if self.write_hdf5:
            _time = time.strftime("%Y%m%d_%H%M%S")
            self.hdf5_file_name = 'channel_data_' + _time + '.h5'
            self.hdf5_channel = h5py.File(self.hdf5_file_name, 'a')

        self.show_plot = show_plot
        if show_plot:
            plt.ion()
            plt.figure(0)
            plt.title("Integrated Channelized data")
            self.line[0], = plt.plot([0]*self.frequency_channels)
            self.line[0].set_xdata(np.arange(self.frequency_channels))

    def allocate_buffers(self):
        self.first_packet = False
        if self.is_floating_point == 1:
            self.data_type = np.double  # np.uint64
        else:
            self.data_type = np.uint64
        self.data_reassembled = np.zeros((self.nof_fpga, self.nof_signals_per_fpga * self.frequency_channels),
                                         dtype=self.data_type)
        self.data_buff = np.zeros((self.nof_signals, self.frequency_channels), dtype=self.data_type)
        self.data_buff_scrambled = np.zeros((self.nof_signals, self.frequency_channels), dtype=self.data_type)
        self.data_buff_accu = np.zeros((self.nof_signals, self.frequency_channels), dtype=self.data_type)

    def spead_header_decode(self, pkt):
        items = unpack('>' + 'Q'*9, pkt[0:8*9])
        self.is_spead = 0
        for idx in range(len(items)):
            spead_item = items[idx]
            spead_id = spead_item >> 48
            val = spead_item & 0x0000FFFFFFFFFFFF
            if spead_id == 0x5304 and idx == 0:
                self.is_spead = 1
            elif spead_id == 0x8001:
                heap_counter = val
                self.packet_counter = heap_counter & 0xFFFFFF
                self.logical_channel_id = heap_counter >> 24
            elif spead_id == 0x8004:
                self.payload_length = val
            elif spead_id == 0x9027:
                self.sync_time = val
            elif spead_id == 0x9600:
                self.timestamp = val
            elif spead_id == 0xA004:
                self.capture_mode = val & 0xEF
                self.is_floating_point = (val >> 7) & 0x1
                if self.first_packet:
                    self.allocate_buffers()
            elif spead_id == 0xA002:
                self.start_channel_id = (val & 0x000000FFFF000000) >> 24
                self.start_antenna_id = (val & 0x000000000000FF00) >> 8
            elif spead_id == 0xA003 or spead_id == 0xA001:
                self.buffer_id = (val & 0xFFFFFFFF) >> 16
            elif spead_id == 0x3300:
                self.offset = 9*8
            else:
                print "Error in SPEAD header decoding!"
                print "Unexpected item " + hex(spead_item) + " at position " + str(idx)
        if self.start_antenna_id >= self.nof_signals:
            # print "Dropping packet from FPGA2"
            self.is_spead = 0

    def write_buff(self, data):
        idx = self.start_channel_id * self.nof_signals_per_fpga
        self.data_reassembled[self.start_antenna_id / self.nof_signals_per_fpga, idx:idx + (self.payload_length / self.data_byte)] = data
        self.recv_packets += 1

    def buffer_demux(self):
        if self.nof_signals_per_fpga == 1:
            self.data_buff = self.data_reassembled
        else:
            for b in range(self.nof_fpga):
                for n in range(self.nof_signals_per_fpga * self.frequency_channels):
                    self.data_buff_scrambled[(n % self.nof_signals_per_fpga) + self.nof_signals_per_fpga * b, n / self.nof_signals_per_fpga] = self.data_reassembled[b, n]
            self.data_buff = self.data_buff_scrambled

    def detect_full_buffer(self):
        if self.prev_timestamp_channel != self.timestamp:
            self.recv_packets = 1
            self.prev_timestamp_channel = self.timestamp
        if self.recv_packets == self.expected_nof_packets:
            self.recv_packets = 0
            return True
        else:
            return False

    def reverse_bit(self, num):
        step = int(np.log2(self.frequency_channels))
        result = 0
        for n in range(step):
            result += (num & 1) << (step - n - 1)
            num >>= 1
        return result

    def bit_reversal(self):
        temp_buff = np.zeros((self.nof_signals, self.frequency_channels), dtype=self.data_type)
        for b in range(self.nof_signals):
            for n in range(self.frequency_channels):
                channel = self.reverse_bit(n)
                temp_buff[b, channel] = self.data_buff[b, n]
                # print n
                # print channel
                # raw_input()
        self.data_buff = temp_buff

    def buff_descramble(self):
        if self.nof_signals_per_fpga == 1:
            return
        temp_buff = np.zeros((self.nof_signals, self.frequency_channels), dtype=self.data_type)
        for b in range(self.nof_signals):
            for n in range(self.frequency_channels):
                if n % 2 == 0:
                    channel = n / 2
                else:
                    channel = n / 2 + self.frequency_channels / 2
                temp_buff[b, channel] = self.data_buff[b, n]
        self.data_buff = temp_buff

    def run(self, sock, accu=1, nof_samples=-1):
        num = 0
        accu_num = 0
        while accu_num < nof_samples or nof_samples <= 0:
            packet_ok = 0
            try:
                _pkt, _addr = sock.recvfrom(1024*10)
                packet_ok = 1
            except socket.timeout:
                print "socket timeout!"

            if packet_ok:
                self.spead_header_decode(_pkt)

                if self.is_spead:
                    if self.is_floating_point == 1:
                        unpack_type = 'd'
                    else:
                        unpack_type = 'q'
                    self.write_buff(unpack('<' + unpack_type * (self.payload_length / 8), _pkt[self.offset:]))

                    buffer_ready = self.detect_full_buffer()
                    if buffer_ready: # channelized data
                        self.buffer_demux()
                        self.buff_descramble()
                        if self.is_floating_point == 1:
                            self.bit_reversal()

                        num += 1
                        print("Full buffer received: " + str(num))

                        if num % accu == 1 or accu == 1:
                            self.data_buff_accu = self.data_buff
                        else:
                            self.data_buff_accu += self.data_buff

                        if num % accu == 0 or accu == 1:
                            accu_num += 1
                            print "Full integration " + str(accu_num) + " ready"
                            if self.write_hdf5:
                                self.hdf5_channel.create_dataset(str(self.timestamp), data=self.data_buff_accu)

                        if self.show_plot:
                            plt.figure(0)
                            plt.clf()
                            plt.title("Integrated Channelized data %d" % num)

                            for b in range(self.nof_signals):
                                log_plot = np.zeros(self.frequency_channels)
                                for n in range(self.frequency_channels):
                                    if self.data_buff[b, n] > 0:
                                        log_plot[n] = 10 * np.log10(self.data_buff_accu[b, n])
                                    else:
                                        log_plot[n] = 0.0
                                plt.plot(log_plot.tolist())
                                #plt.plot(self.data_buff[n].tolist())
                            plt.draw()
                            plt.pause(0.0001)
                        return self.data_buff_accu

        if self.write_hdf5:
            self.hdf5_channel.close()

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-p",
                      dest="port",
                      default="4660",
                      help="UDP port")
    parser.add_option("-a",
                      dest="accu",
                      default="1",
                      help="Number of spectra to accumulate")
    parser.add_option("-w",
                      dest="write_hdf5",
                      default=False,
                      action="store_true",
                      help="Write HDF5 files")
    parser.add_option("-i",
                      dest="ignore_fpga2",
                      default=False,
                      action="store_true",
                      help="Ignore data from FPGA2")
    parser.add_option("-n",
                      dest="num",
                      default="-1",
                      help="Number of accumulated samples")

    (options, args) = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   # UDP
    sock.bind(("0.0.0.0", 4660))
    sock.settimeout(1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2*1024*1024)

    nof_fpga = 2
    if options.ignore_fpga2:
        nof_fpga = 1
    spead_rx_inst = SpeadRx(options.write_hdf5, nof_fpga)

    spead_rx_inst.run(sock, int(options.accu), int(options.num))
