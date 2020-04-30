#! /usr/bin/env python

from builtins import object
import numpy as np
import logging
import time
import os

from reach_ctrl.spectrometer.tile_reach import Tile
from reach_ctrl.spectrometer.spectra import Spectra
from reach_ctrl.reach_config import REACHConfig

__author__ = 'Alessio Magro'                     

class Spectrometer(object):

    def __init__(self, ip, port, lmc_ip, lmc_port, enable_spectra=True, sampling_rate=800e6):
        """ Class which interfaces with TPM and spectrometer firmware """

        # Create Tile
        self._tile = Tile(ip=ip, port=port, lmc_ip=lmc_ip, lmc_port=lmc_port, sampling_rate=sampling_rate)

        # Create and initialise receiver
        self._spectra = None
        if enable_spectra:
            self._spectra = Spectra(ip=lmc_ip, port=lmc_port)
            self._spectra.initialise()

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

    def initialise(self, channel_truncation=2, integration_time=1, channel_scaling=0xFFFF, ada_gain=None):
        """ Initialise the TPM and spectrometer firmware """

        logging.info("Initialising TPM")
        self._tile.initialise(enable_ada=True if ada_gain is not None else False)

        # Set ada gain if enabled
        if ada_gain is not None:
            self._tile.tpm.tpm_ada.set_ada_gain(ada_gain)

        logging.info("Using 1G for LMC traffic")
        self._tile.set_lmc_download("1g")
        self._tile.set_lmc_integrated_download("1g", 1024, 1024)

        # Set channeliser truncation
        logging.info("Configuring channeliser")
        self._tile.set_channeliser_truncation(channel_truncation)

        # Configure continuous transmission of integrated channel
        self._tile.stop_integrated_data()
        self._tile.configure_integrated_channel_data(integration_time)

        # Perform synchronisation
        self._tile.post_synchronisation()
        self._tile.synchronize_ddc(1600)

        logging.info("Setting data acquisition")
        self._tile.start_acquisition()

        self._tile.load_default_poly_coeffs()
        self._tile['fpga1.dsp_regfile.channelizer_fft_bit_round'] = channel_scaling
        self._tile['fpga2.dsp_regfile.channelizer_fft_bit_round'] = channel_scaling
        self._tile['board.regfile.ethernet_pause'] = 8000

    def acquire_spectrum(self, channel=0, nof_seconds=1):
        """ Acquire spectra for defined number of seconds """

        if self._spectra is None:
            logging.warning("Cannot acquire spectra. Acqusition not initialised")
            return None

        # Start receiver
        self._spectra.start_receiver(nof_seconds)

        # TODO: Start data transmission
        # ...

        # Wait for receiver to finish
        # Spectra will be received in spectra/signals/channel order
        timestamps, spectra = self._spectra.wait_for_receiver()

        # TODO: Stop data transmission 
        # ...

        # Return spectra
        spectra = np.sum(spectra, axis=0)
        return timestamps, spectra[channel, :]

if __name__ == "__main__":

    # Use OptionParse to get command-line arguments
    from optparse import OptionParser
    from sys import argv, stdout

    parser = OptionParser(usage="usage: %spectrometr [options]")
    parser.add_option("-f", "--bitfile", action="store", dest="bitfile",
                      default=None, help="Bitfile to use (-P still required)")
    parser.add_option("-P", "--program", action="store_true", dest="program",
                      default=False, help="Program FPGAs [default: False]")
    parser.add_option("-C", "--program-cpld", action="store_true", dest="program_cpld",
                      default=False, help="Program CPLD (cannot be used with other options) [default: False]")
    parser.add_option("-I", "--initialise", action="store_true", dest="initialise",
                      default=False, help="Initialise TPM [default: False]")
    parser.add_option("-S", "--enable-spectra", action="store_true", dest="spectra",
                      default=False, help="Enable acqusition of spectra on this connection [default: False]")
    (command_line_args, args) = parser.parse_args(argv[1:])

    # Initialise REACH config
    conf = REACHConfig()['spectrometer']
    
    # Create tile instance
    tile = Spectrometer(conf['ip'], int(conf['port']), conf['lmc_ip'], int(conf['lmc_port']), enable_spectra=command_line_args.spectra)

    # Program CPLD
    if command_line_args.program_cpld:
        logging.info("Programming CPLD")
        tile.program_cpld(command_line_args.bitfile)

    # Program FPGAs if required
    if command_line_args.program:
        logging.info("Programming FPGAs")
        tile.program(os.path.join(os.path.expanduser(os.environ['REACH_CONFIG_DIRECTORY']), conf['bitstream']))
    
    # Initialise TPM if required
    if command_line_args.initialise:
        tile.initialise(int(conf['channel_truncation']), int(conf['integration_time']), int(conf['channel_scaling']), int(conf['ada_gain']))

    # Connect to board
    tile.connect()
