#! /usr/bin/env python

from sys import exit
import logging
import time
import os

from tile_reach import Tile

__author__ = 'Alessio Magro'                     

class Spectrometer:

    def __init__(self, ip, port, lmc_ip, lmc_port, sampling_rate=800e6):
        """ Class which interfaces with TPM and spectrometer firmware """

        # Create Tile
        self._tile = Tile(ip=ip, port=port, lmc_ip=lmc_ip, lmc_port=lmc_port, sampling_rate=sampling_rate)

    def connect(self):
        """ Connect to TPM """
        self._tile.connect()

    def program(self, bitfile):
        """ Download a firmware to the TPM
        @param bitfile: Filepath to bitstream """

        if os.path.exists(bitfile) and os.path.isfile(bitfile):
            self._tile.program_fpgas(bitfile=bitfile)
        else:
            logging.error("Could not load bitfile %s, check filepath" % bitfile)

    def program_cpld(self, bitfile):
        """ Update CPLD firmware on TPM
        @param bitfile: Path to bitstream """

        if os.path.exists(bitfile) and os.path.isfile(bitfile):
            logging.info("Using CPLD bitfile {}".format(bitfile))
            self._tile.program_cpld(bitfile)
        else:
            logging.error("Could not load bitfile {}, check filepath".format(bitfile))

    def initialise(self, channel_trunction=2, integration_time=1 ,ada_gain=None):
        """ Initialise the TPM and spectrometer firmware """

        logging.info("Initialising TPM")
        self._tile.initialise(enable_ada=True if ada_gain is not None else False)

        # Set ada gain if enabled
        if ada_gain is not None:
            self._tile.tpm.tpm_ada.set_ada_gain(conf.ada_gain)

        logging.info("Using 1G for LMC traffic")
        self._tile.set_lmc_download("1g")
        self._tile.set_lmc_integrated_download("1g", 1024, 1024)

        # Set channeliser truncation
        logging.info("Configuring channeliser")
        self._tile.set_channeliser_truncation(channel_trunction)

        # Configure continuous transmission of integrated channel
        self._tile.stop_integrated_data()
        self._tile.configure_integrated_channel_data(integration_time)

        # Perform synchronisation
        self._tile.post_synchronisation()

        self._tile.synchronize_ddc(1600)

        logging.info("Setting data acquisition")
        self._tile.start_acquisition()

        self._tile.load_default_poly_coeffs()
        self._tile['fpga1.dsp_regfile.channelizer_fft_bit_round'] = 0xFFFF
        self._tile['fpga2.dsp_regfile.channelizer_fft_bit_round'] = 0xFFFF

        self._tile['board.regfile.ethernet_pause'] = 8000


if __name__ == "__main__":

    # Use OptionParse to get command-line arguments
    from optparse import OptionParser
    from sys import argv, stdout

    parser = OptionParser(usage="usage: %spectrometr [options]")
    parser.add_option("--ip", action="store", dest="ip",
                      default="10.0.10.2", help="IP [default: 10.0.10.2]")
    parser.add_option("--port", action="store", dest="port",
                      type="int", default="10000", help="Port [default: 10000]")
    parser.add_option("--lmc_ip", action="store", dest="lmc_ip",
                      default="10.0.10.200", help="IP [default: 10.0.10.200]")
    parser.add_option("--lmc_port", action="store", dest="lmc_port",
                      type="int", default="4660", help="Port [default: 4660]")
    parser.add_option("-f", "--bitfile", action="store", dest="bitfile",
                      default=None, help="Bitfile to use (-P still required)")
    parser.add_option("-P", "--program", action="store_true", dest="program",
                      default=False, help="Program FPGAs [default: False]")
    parser.add_option("-C", "--program-cpld", action="store_true", dest="program_cpld",
                      default=False, help="Program CPLD (cannot be used with other options) [default: False]")
    parser.add_option("-I", "--initialise", action="store_true", dest="initialise",
                      default=False, help="Initialise TPM [default: False]")
    parser.add_option("", "--channel-integration-time", action="store", dest="channel_integ",
                      type="float", default=1, help="Integrated channel integration time [default: -1 (disabled)]")
    parser.add_option("--ada-gain", action="store", dest="ada_gain",
                      default=None, type="int", help="ADA gain [default: 15]")
    parser.add_option("--chan-trunc-scale", action="store", dest="chan_trun",
                      default=2, type="int", help="Channelsier truncation scale [range: 0-7, default: 2]")
    (conf, args) = parser.parse_args(argv[1:])

    # Set logging
    log = logging.getLogger('')
    log.setLevel(logging.INFO)
    line_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    ch = logging.StreamHandler(stdout)
    ch.setFormatter(line_format)
    log.addHandler(ch)
    
    # Create tile instance
    tile = Spectrometer(conf.ip, conf.port, conf.lmc_ip, conf.lmc_port)

    # Program CPLD
    if conf.program_cpld:
        if conf.bitfile is not None:
            tile.program_cpld(conf.bitfile)
            exit()
        else:
            logging.error("No CPLD bitfile specified")
            exit(-1)

    # Program FPGAs if required
    if conf.program:
        logging.info("Programming FPGAs")
        if conf.bitfile is not None:
           tile.program(conf.bitfile)
        else:
            logging.error("No bitfile specified")
            exit(-1)

    # Initialise TPM if required
    if conf.initialise:
        tile.initialise(conf.chan_trun, conf.channel_integ, conf.ada_gain)

    # Connect to board
    tile.connect()
