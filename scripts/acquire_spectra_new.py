from reach_ctrl.spectrometer.spectrometer import Spectrometer
from reach_ctrl.spectrometer.spectra import Spectra
from reach_ctrl.reach_config import REACHConfig

import matplotlib.pyplot as plt
import numpy as np
import datetime
import logging
import time
import h5py
import os


def create_output_file(data_file_name, name="test"):
    """ Create HDF5 output file """
    # Create HDF5 file which will store observation data
    with h5py.File(data_file_name, 'w') as f:
        # Create group which will contain observation info
        info = f.create_group('observation_info')

        # Add attributes to group
        info.attrs['observation_name'] = name
        info.attrs['start_time'] = time.time()

        # Create group which will contain all observation data
        f.create_group("observation_data")

    logging.info("Created output file")


def add_spectrum_to_file(data_file_name, spectrum, timestamp, name="test"):
    """ Add spectrum to data file 
    :param spectrum: The spectrum
    :param name: The data name
    :param timestamp: Spectrum timestsamp """

    nof_frequency_channels = REACHConfig()['spectrometer']['nof_frequency_channels']

    with h5py.File(data_file_name, 'a') as f:
        # Create dataset names
        dataset_name = "{}_spectra".format(name)
        timestamp_name = "{}_timestamps".format(name)

        # Load observation data group
        dset = f['observation_data']

        # If data sets do not exist, add them
        if dataset_name not in dset.keys():
            dset.create_dataset(dataset_name,
                                (4, 0, nof_frequency_channels),
                                maxshape=(4, None, nof_frequency_channels),
                                chunks=True,
                                dtype='u8')

            dset.create_dataset(timestamp_name, (0,),
                                maxshape=(None,), chunks=True, dtype='f8')

            logging.info("Added {} dataset to output file".format(dataset_name))

        # Add spectrum and timestamp to buffer
        dset = f['observation_data/{}'.format(dataset_name)]
        dset.resize((dset.shape[0], dset.shape[1] + 1, dset.shape[2]))
        dset[:, -1, :] = spectrum

        dset = f['observation_data/{}'.format(timestamp_name)]
        dset.resize((dset.shape[0] + 1,))
        dset[-1] = timestamp


if __name__ == "__main__":

    # Use OptionParse to get command-line arguments
    from optparse import OptionParser
    from sys import argv, stdout

    parser = OptionParser(usage="usage: %spectrometr [options]")
    parser.add_option("-I", dest="initialise", default=False, action="store_true", 
                      help="Initialise spectrometer (default: False)")
    parser.add_option("-a", dest="accumulate", default=1, type=int, 
                      help="Number of spectra to accumulate (default: 1)")
    parser.add_option("-n", dest="nof_spectra", default=-1, type=int, 
                      help="Number of accumulated samples (default: -1)")
    parser.add_option("-f", dest="output", default="", 
                      help="Write spectra to file using provided filename (default: No output)")
    (options, args) = parser.parse_args()

    # Initialise REACH config
    conf = REACHConfig()['spectrometer']

    # Pointer to spectra receiver
    spectra = None

    # Initialise spectrometer
    if options.initialise:
        spectrometer = Spectrometer(ip=conf['ip'], 
                                    port=conf['port'],
                                    lmc_ip=conf['lmc_ip'], 
                                    lmc_port=conf['lmc_port'])

        bitstream = os.path.join(os.environ['REACH_CONFIG_DIRECTORY'], conf['bitstream'])

        logging.info("Initialising spectrometer")
        spectrometer.program(bitstream)
        spectrometer.initialise(channel_truncation=conf['channel_truncation'],
                                integration_time=conf['integration_time'],
                                ada_gain=conf['ada_gain'])
        logging.info("Initialised spectrometer")

        # Hack, get existing spectrum receive
        spectra = spectrometer._spectra

    else:
        # Create and initialise receiver
        spectra = Spectra(ip=conf['lmc_ip'], port=int(conf['lmc_port']))
        spectra.initialise()

    # If number of spectra is not defined, use a large number
    if options.nof_spectra == -1:
        options.nof_spectra = int(1e6)

    # If a file is specified, create file
    if options.output != "":
        options.output = "{}.hdf5".format(options.output)
        create_output_file(options.output)

    # Kickstart plotting
    plt.figure()

    # Look over number of required accumulations
    for accumulation in range(options.nof_spectra):
        
        # Grab spectra
        spectra.start_receiver(options.accumulate)
        timestamps, data = spectra.wait_for_receiver()

        # # Generate accumulated spectra
        data = 10 * np.log10(np.sum(data, axis=0))

        # If writing to file, add
        if options.output != "":
            add_spectrum_to_file(options.output, data, timestamps[0], name="test")

        # Update plot
        plt.clf()
        plt.title("Integrated Channelized data {} - {}".format(accumulation, datetime.datetime.fromtimestamp(timestamps[0]).strftime("%H:%M:%S")))
        plt.plot(data[0, :], label="Channel 0")
        plt.plot(data[1, :], label="Channel 1")
        plt.plot(data[2, :], label="Channel 2")
        plt.plot(data[3, :], label="Channel 3")
        plt.xlabel("Frequency Channel")
        plt.ylabel("Arbitrary Power (dB)")
        plt.legend()
        plt.draw()
        plt.pause(0.0001)

        logging.info("Received accumulated spectrum")



