import time
import math
import socket
import h5py
import numpy as np
import matplotlib.pyplot as plt
from struct import *
from optparse import OptionParser


class SpeadRx:
    def __init__(self, write_hdf5):

        self.write_hdf5 = write_hdf5

        self.nof_signals = 4
        self.frequency_channels = 16*1024
        self.data_width = 64
        self.data_byte = self.data_width / 8
        self.byte_per_packet = 1024
        self.word_per_packet = self.byte_per_packet / (self.data_width / 8)
        self.expected_nof_packets = self.nof_signals * self.frequency_channels * (self.data_width / 8) / self.byte_per_packet

        self.data_reassembled = np.zeros((2, 2*self.frequency_channels), dtype=np.uint64)
        self.data_buff = np.zeros((self.nof_signals, self.frequency_channels), dtype=np.uint64)
        self.data_buff_scrambled = np.zeros((self.nof_signals, self.frequency_channels), dtype=np.uint64)

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
        self.id = 0
        self.is_spead = 0
        self.processed_frame = 0
        self.buffer_id = 0
        if self.write_hdf5:
            _time = time.strftime("%Y%m%d_%H%M%S")
            self.hdf5_channel = h5py.File('channel_data_' + _time + '.h5', 'a')

        plt.ion()
        #for n in range(self.nof_signals):
        #    plt.figure(n)
        #    plt.title("Integrated Channelized data " + str(n))
        #    self.line[n], = plt.plot([0]*self.frequency_channels)
        #    self.line[n].set_xdata(np.arange(self.frequency_channels))
        plt.figure(0)
        plt.title("Integrated Channelized data")
        self.line[0], = plt.plot([0]*self.frequency_channels)
        self.line[0].set_xdata(np.arange(self.frequency_channels))



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
                self.capture_mode = val
            elif spead_id == 0xA002:
                self.start_channel_id = (val & 0x000000FFFF000000) >> 24
                self.start_antenna_id = (val & 0x000000000000FF00) >> 8
                #self.start_antenna_id /= 2
            elif spead_id == 0xA003 or spead_id == 0xA001:
                self.buffer_id = (val & 0xFFFFFFFF) >> 16
            elif spead_id == 0x3300:
                self.offset = 9*8
            else:
                print "Error in SPEAD header decoding!"
                print "Unexpected item " + hex(spead_item) + " at position " + str(idx)

    def write_buff(self, data):
        idx = self.start_channel_id * 2
        self.data_reassembled[self.start_antenna_id / 2, idx:idx + (self.payload_length / self.data_byte)] = data
        self.recv_packets += 1
        print self.recv_packets
        print self.expected_nof_packets

    def buffer_demux(self):
        for b in range(2):
            for n in range(2*self.frequency_channels):
                self.data_buff_scrambled[(n % 2) + 2*b, n / 2] = self.data_reassembled[b, n]
        self.data_buff = self.data_buff_scrambled
        # for b in range(self.nof_signals):
        #     lo_idx = 0
        #     hi_idx = self.frequency_channels / 2
        #     for n in range(self.frequency_channels):
        #         if (n % 4) < 2:
        #             self.data_buff[b, lo_idx] = self.data_buff_scrambled[b, n]
        #             lo_idx += 1
        #         else:
        #             self.data_buff[b, hi_idx] = self.data_buff_scrambled[b, n]
        #             hi_idx += 1

    def detect_full_buffer(self):
        if self.prev_timestamp_channel != self.timestamp:
            self.recv_packets = 1
            self.prev_timestamp_channel = self.timestamp
        if self.recv_packets == self.expected_nof_packets:
            self.recv_packets = 0
            return True
        else:
            return False

    def bit_reversal(self):
        bit_width = int(np.log2(self.frequency_channels))
        bit_format = '{:0' + str(bit_width) + 'b}'
        print bit_format
        print int(bit_format.format(8192)[::-1], 2)
        temp_buff = np.zeros((self.nof_signals, self.frequency_channels), dtype=np.uint64)
        for b in range(4):
            for n in range(self.frequency_channels):
                channel = int(bit_format.format(n)[::-1], 2)
                temp_buff[b, channel] = self.data_buff[b, n]
                #print n
                #print channel
                #raw_input()
        self.data_buff = temp_buff

    def buff_descramble(self):
        temp_buff = np.zeros((self.nof_signals, self.frequency_channels), dtype=np.uint64)
        for b in range(4):
            for n in range(self.frequency_channels):
                if n % 2 == 0:
                    channel = n / 2
                else:
                    channel = n / 2 + self.frequency_channels / 2
                temp_buff[b, channel] = self.data_buff[b, n]
        self.data_buff = temp_buff


    def run(self, sock):
        num = 0
        while True:
            packet_ok = 0
            try:
                _pkt, _addr = sock.recvfrom(1024*10)
                packet_ok = 1
            except socket.timeout:
                print "socket timeout!"

            if packet_ok:
                self.spead_header_decode(_pkt)

                if self.is_spead:
                    self.write_buff(unpack('<' + 'q' * (self.payload_length / 8), _pkt[self.offset:]))
                    buffer_ready = self.detect_full_buffer()
                    if buffer_ready: # channelized data
                        self.buffer_demux()
                        self.buff_descramble()
                        # self.bit_reversal()
                        if self.write_hdf5:
                            self.hdf5_channel.create_dataset(str(self.timestamp), data=self.data_buff)
                        num += 1
                        print "Full buffer received: " + str(num)

                        plt.figure(0)
                        plt.clf()
                        plt.title("Integrated Channelized data %d" % num)
                        

                        for b in range(4):
                            for n in range(self.nof_signals):
                                log_plot = np.zeros(self.frequency_channels)
                                for n in range(self.frequency_channels):
                                    if self.data_buff[b, n] > 0:
                                        log_plot[n] = 10*np.log10(self.data_buff[b, n])
                                    else:
                                        log_plot[n] = 0.0
                            plt.plot(log_plot.tolist())
                            #plt.plot(self.data_buff[n].tolist())
                        plt.draw()
                        plt.pause(0.0001)

        self.hdf5_channel.close()

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-p",
                      dest="port",
                      default="4660",
                      help="UDP port")
    parser.add_option("-w",
                      dest="write_hdf5",
                      default=False,
                      action="store_true",
                      help="Write HDF5 files")

    (options, args) = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   # UDP
    sock.bind(("0.0.0.0", 4660))
    sock.settimeout(1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2*1024*1024)

    spead_rx_inst = SpeadRx(options.write_hdf5)

    spead_rx_inst.run(sock)
