from __future__ import division
from builtins import hex
from builtins import str
from builtins import range
from builtins import object
from past.utils import old_div
import numpy as np
import threading
import logging
import socket
import struct

class Spectra(object):
    """ REACH spectrometer data receiver """
    
    def __init__(self, ip, port=4660, nof_signals=4, nof_channels=16384):
        """ Class constructor:
        @param ip: IP address to bind receiver to 
        @param port: Port to receive data on """

        # Initialise parameters
        self._nof_channels = nof_channels
        self._nof_signals = nof_signals
        self._port = port
        self._ip = ip

        # Create socket reference
        self._socket = None

        # Spectra containers
        self._data_reassembled = np.zeros((2, 2 * self._nof_channels), dtype=np.uint64)
        self._data_buffer = np.zeros((self._nof_signals, self._nof_channels), dtype=np.uint64)
        self._data_buffer_scrambled = np.zeros((self._nof_signals, self._nof_channels), dtype=np.uint64)

        # Packet header content 
        self._packet_counter = 0
        self._logical_channel_id = 0
        self._payload_length = 0
        self._sync_time = 0
        self._timestamp = 0
        self._lmc_mode = 0
        self._start_channel_id = 0
        self._start_antenna_id = 0
        self._buffer_id = 0
        self._offset = 9*8 
        
        # Payload data parameters
        self._data_width = 64
        self._data_byte = old_div(self._data_width, 8)
        self._byte_per_packet = 1024
        self._expected_nof_packets = old_div(self._nof_signals * self._nof_channels * (old_div(self._data_width, 8)), self._byte_per_packet)

        # Book keeping
        self._received_packets = 0
        self._previous_timestamp = 0

        # Received spectra placeholder
        self._receiver_thread = None
        self._received_spectra = None
        self._received_timestamps = None


    def initialise(self):
        """ Initilise socket and set local buffers """
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind((self._ip, self._port))
        self._socket.settimeout(2)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2*1024*1024)

    def receive_spectrum(self):
        """ Wait for a spead packet to arrive """
                
        # Clear receiver 
        self._clear_receiver()
        packet = None

        # Check if receiver has been initialised
        if self._socket is None:
            logging.error("Spectrum receiver not initialised")
            return

        # Loop until required to stop
        while True:
            # Try to acquire packet
            try:
                packet, _ = self._socket.recvfrom(9000)
            except socket.timeout:
                logging.info("Socket timeout")
                continue

            # We have a packet, check if it is a valid packet
            if not self._decode_spead_header(packet):
                continue

            # Valid packet, extract payload and add to buffer
            payload = struct.unpack('<' + 'q' * (old_div(self._payload_length, 8)), packet[self._offset:])
            self._add_packet_to_buffer(payload)

            # If the buffer is full, finalize packet buffer
            if self._detect_full_buffer():
                self._finalise_buffer()
                return self._timestamp, self._data_buffer

    def _receive_spectra_threaded(self, nof_spectra=1):
        """ Receive specified number of thread, should run in a separate thread """
        
        self._received_spectra = np.zeros((nof_spectra, self._nof_signals, self._nof_channels))
        self._received_timestamps = np.zeros((nof_spectra))
        for i in range(nof_spectra):
            self._received_timestamps[i], self._received_spectra[i] = self.receive_spectrum()

    def start_receiver(self, nof_spectra):
        """ Receive specified number of spectra """

        # Create and start thread and wait for it to stop
        self._receiver_thread = threading.Thread(target=self._receive_spectra_threaded, args=(nof_spectra, ))
        self._receiver_thread.start()
        
    def stop_receiver(self):
        """ Stop receiver """
        if self._receiver_thread is None:
            logging.error("Receiver not started")
        
        self._receiver_thread.join()

        # Return result
        return self._received_timestamps, self._received_spectra

    def _decode_spead_header(self, packet):
        """ Decode SPEAD packet header 
        @param: Received packet header """

        # Flag specifying whether packet is a valid SPEAD packet
        valid_packet = False

        # Unpack SPEAD header items
        try:
            items = struct.unpack('>' + 'Q'*9, packet[0:8*9])
        except:
            logging.error("Error processing packet")
            return False

        # Process all spead items
        for idx in range(len(items)):
            spead_item = items[idx]
            spead_id = spead_item >> 48
            val = spead_item & 0x0000FFFFFFFFFFFF
            if spead_id == 0x5304 and idx == 0:
                valid_packet = True
            elif spead_id == 0x8001:
                heap_counter = val
                self._packet_counter = heap_counter & 0xFFFFFF
                self._logical_channel_id = heap_counter >> 24
            elif spead_id == 0x8004:
                self._payload_length = val
            elif spead_id == 0x9027:
                self._sync_time = val
            elif spead_id == 0x9600:
                self._timestamp = val
            elif spead_id == 0xA004:
                self._lmc_mode = val
            elif spead_id == 0xA002:
                self._start_channel_id = (val & 0x000000FFFF000000) >> 24
                self._start_antenna_id = (val & 0x000000000000FF00) >> 8
            elif spead_id == 0xA003 or spead_id == 0xA001:
                self._buffer_id = (val & 0xFFFFFFFF) >> 16
            elif spead_id == 0x3300:
                pass
            else:
                logging.error("Error in SPEAD header decoding!")
                logging.error("Unexpected item {} at position {}".format(hex(spead_item)," at position " + str(idx)))

        return valid_packet

    def _add_packet_to_buffer(self, data):
        """ Add packet content to buffer """
        index = self._start_channel_id * 2
        self._data_reassembled[old_div(self._start_antenna_id, 2), index:index + (old_div(self._payload_length, self._data_byte))] = data
        self._received_packets += 1

    def _finalise_buffer(self):
        """ Demux and descramble buffer for persisting """

        # Demultipliex buffer
        for b in range(2):
            for n in range(2*self._nof_channels):
                self._data_buffer_scrambled[(n % 2) + 2*b, old_div(n, 2)] = self._data_reassembled[b, n]
        
        # Descramble buffer
        for b in range(4):
            for n in range(self._nof_channels):
                if n % 2 == 0:
                    channel = old_div(n, 2)
                else:
                    channel = old_div(n, 2) + old_div(self._nof_channels, 2)
                self._data_buffer[b, channel] = self._data_buffer_scrambled[b, n]

    def _detect_full_buffer(self):
        """ Check whether we have a full buffer """
        # Timestamp check
        if self._previous_timestamp != self._timestamp:
            self._received_packets = 1
            self._previous_timestamp = self._timestamp

        # If number of received packets is the expected number, return True, otherwise False
        if self._received_packets == self._expected_nof_packets:
            self._received_packets = 0
            return True
        else:
            return False

    def _clear_receiver(self):
        """ Reset receiver  """
        self._received_packets = 0
        self._previous_timestamp = 0

        self._data_buffer[:] = 0
        self._data_reassembled[:] = 0
        self._data_buffer_scrambled[:] = 0

if __name__ == "__main__":
    from optparse import OptionParser
    
    parser = OptionParser()
    parser.add_option("-p", dest="port", default=4660, type=int, help="UDP port (default:4660)")
    parser.add_option("-i", dest="ip", default="10.0.10.40", help="IP (default: 10.0.10.40)")
    (config, args) = parser.parse_args()

    spectra = Spectra(ip=config.ip, port=config.port)
    spectra.initialise()
    spectrum = 10 * np.log10(spectra.receive_spectrum()[1])
    
    from matplotlib import pyplot as plt
    plt.plot(spectrum[0], label="Channel 0")
    plt.plot(spectrum[1], label="Channel 1")
    plt.plot(spectrum[2], label="Channel 2")
    plt.plot(spectrum[3], label="Channel 3")
    plt.legend()
    plt.show()
