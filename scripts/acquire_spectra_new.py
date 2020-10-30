from reach_ctrl.spectrometer.spectrometer import Spectrometer
from reach_ctrl.spectrometer.spectra import Spectra
from reach_ctrl.reach_config import REACHConfig

import matplotlib.pyplot as plt
import numpy as np
import threading
import datetime
import logging
import signal
import time
import h5py
import os

# Global pointer to data_file
data_file_name = None

# Global pointer to spectrometer
spectrometer = None

# Global thread stop flag
stop_acquisition = False


def _signal_handler(signum, frame):
    global stop_acquisition
    logging.info("Received interrupt, stopping acqusition")
    stop_acquisition = True


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


def add_spectrum_to_file(spectrum, timestamp, name="test"):
    """ Add spectrum to data file 
    :param spectrum: The spectrum
    :param name: The data name
    :param timestamp: Spectrum timestsamp
    :param name: Input source name """

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
                                (2, 0, nof_frequency_channels),
                                maxshape=(2, None, nof_frequency_channels),
                                chunks=True,
                                dtype='f8')

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


def add_rms_to_file(rms, timestamp, name="test"):
    """ Add RMS to data file
    :param spectrum: The spectrum
    :param name: The data name
    :param timestamp: Spectrum timestsamp
    :param name: Input source name """

    # Sanity check on rms
    if len(rms) == 0:
        return

    with h5py.File(data_file_name, 'a') as f:
        # Create dataset names
        dataset_name = "{}_rms".format(name)

        # Load observation data group
        dset = f['observation_info']

        # If data sets do not exist, add them
        if dataset_name not in dset.keys():
            dset.create_dataset(dataset_name,
                                (0, 5),
                                maxshape=(None, 5),
                                chunks=True,
                                dtype='f8')

            logging.info("Added {} dataset to output file".format(dataset_name))

        # Add spectrum and timestamp to buffer
        dset = f['observation_info/{}'.format(dataset_name)]
        dset.resize((dset.shape[0] + 1, dset.shape[1]))
        dset[-1, 0] = timestamp
        dset[-1, 1:] = rms


def add_temperatures_to_file(temps, timestamp, name="test"):
    """ Add RMS to data file
    :param temps: The temperatures
    :param name: The data name
    :param timestamp: Spectrum timestsamp
    :param name: Input source name """

    # Sanity check on temps
    if len(temps) == 0:
        return

    with h5py.File(data_file_name, 'a') as f:
        # Create dataset names
        dataset_name = "{}_temperatures".format(name)

        # Load observation data group
        dset = f['observation_info']

        if 'channel_names' not in dset.attrs.keys():
            dset.attrs['channel_names'] = "COLD_JUNCTION, COLD, HOT, LNA, LOAD, GORE28, GORE89, TPM, AMBIENT"

        # If data sets do not exist, add them
        if dataset_name not in dset.keys():
            dset.create_dataset(dataset_name,
                                (0, temps.shape[0] + 1),
                                maxshape=(None, temps.shape[0] + 1),
                                chunks=True,
                                dtype='f4')

            logging.info("Added {} dataset to output file".format(dataset_name))
            f.flush()

        # Add spectrum and timestamp to buffer
        dset = f['observation_info/{}'.format(dataset_name)]
        dset.resize((dset.shape[0] + 1, dset.shape[1]))
        dset[-1, 0] = timestamp
        dset[-1, 1:] = temps


def monitor_rms(cadence):
    """ Monitor RMS thread
    :param cadence: Time between measurements """
    global stop_acquisition

    # While acquiring
    while not stop_acquisition:
        # Get RMS
        rms = spectrometer._tile.get_adc_rms()

        # Get timestamp
        timestamp = time.time()

        # Add RMS to file
        add_rms_to_file(rms, timestamp)

        # Sleep for required time
        time.sleep(cadence)

def monitor_temperatures(cadence):
    """ Monitor temperatures thread
    :param cadence: Time between measurements """
    global stop_acquisition

    # Initialise picologger device
    import ctypes
    from picosdk.usbtc08 import usbtc08 as tc08
    from picosdk.functions import assert_pico2000_ok

    # Create chandle and status ready for use
    chandle = ctypes.c_int16()
    status = {}

    # open unit
    chandle = None
    try:
        ret = tc08.usb_tc08_open_unit()
        assert_pico2000_ok(ret)
        chandle = ret   
    except:
        logging.error("Could not initialised picologger. Not getting temperatures")
        return

    try:
        # Set mains rejection to 50 Hz
        status["set_mains"] = tc08.usb_tc08_set_mains(chandle,0)
        assert_pico2000_ok(status["set_mains"])

        # Set up channels (all type K, cold junction needs to be C)
        typeC = ctypes.c_int8(67)        
        assert_pico2000_ok(tc08.usb_tc08_set_channel(chandle, 0, typeC))

        typeK = ctypes.c_int8(75)        
        for channel in range(1, 9):
            assert_pico2000_ok(tc08.usb_tc08_set_channel(chandle, channel, typeK))
    except:
        logging.error("Error while setting up picologger. Not getting temperatures")
        tc08.usb_tc08_close_unit(chandle)
        return

    temp = (ctypes.c_float * 9)()
    overflow = ctypes.c_int16(0)
    units = tc08.USBTC08_UNITS["USBTC08_UNITS_CENTIGRADE"]
        
    # Read temperatures till told to stop
    while not stop_acquisition:
        # Read temperatures
        try:
            assert_pico2000_ok(tc08.usb_tc08_get_single(chandle,ctypes.byref(temp), ctypes.byref(overflow), units))
        except:
            logging.error("Error while getting temperatures, not reading temperatures anymore")
            tc08.usb_tc08_close_unit(chandle)
            return
            
        # Get timestamp
        timestamp = time.time()

        # Add RMS to file
        add_temperatures_to_file(np.array(temp), timestamp)

        # Sleep for required time
        time.sleep(cadence)


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
    parser.add_option("--rms-cadence", dest="rms_cadence", type=int, default=-1,
                      help="Number of seconds between RMS measurements (default: -1 seconds, do not record)")
    parser.add_option("--temp-cadence", dest="temp_cadence", type=int, default=-1, 
                      help="Number of seconds between temperature measurements (default: -1 seconds, do not record)")
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
                                channel_scaling=conf['channel_scaling'],
                                ada_gain=conf['ada_gain'])
        logging.info("Initialised spectrometer")

        # Connect to spectrometer
        spectrometer.connect()

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
        data_file_name = options.output

    # Sanity check on RMS measurements
    if options.temp_cadence != -1:
        if options.output == "":
            logging.warning("Temperature monitoring can only be enabled when writing to file, ignoring")
            options.temp_cadence = False
        else:
            # Create RMS thread
            temp_thread = threading.Thread(target=monitor_temperatures, args=(options.temp_cadence, ))
            temp_thread.start()

    # Sanity check on RMS measurements
    if options.rms_cadence != -1:
        if options.output == "":
            logging.warning("RMS monitoring can only be enabled when writing to file, ignoring")
            options.rms_cadence = False
        else:
            # If spectrometer is not connected, connect it
            spectrometer = Spectrometer(ip=conf['ip'],
                                        port=conf['port'],
                                        lmc_ip=conf['lmc_ip'],
                                        lmc_port=conf['lmc_port'],
                                        enable_spectra=False)
            spectrometer.connect()

            # Create RMS thread
            rms_thread = threading.Thread(target=monitor_rms, args=(options.rms_cadence,))
            rms_thread.start()

    # Wait for exit or termination
    signal.signal(signal.SIGINT, _signal_handler)

    # Kickstart plotting
    plt.figure()

    # Look over number of required accumulations
    for accumulation in range(options.nof_spectra):

        # Grab spectra
        spectra.start_receiver(options.accumulate)
        timestamps, data = spectra.wait_for_receiver()

        # # Generate accumulated spectra
        data = np.sum(data, axis=0)

        # If writing to file, add
        if options.output != "":
            add_spectrum_to_file(data, timestamps[0], name="test")

        data = 10 * np.log10(data)

        # Update plot
        plt.clf()
        plt.title("Integrated Channelized data {} - {}".format(accumulation,
                                                               datetime.datetime.fromtimestamp(timestamps[0]).strftime(
                                                                   "%H:%M:%S")))
        plt.plot(data[0, :], label="Channel 0")
        plt.plot(data[1, :], label="Channel 1")
#        plt.plot(data[2, :], label="Channel 2")
#        plt.plot(data[3, :], label="Channel 3")
        plt.xlabel("Frequency Channel")
        plt.ylabel("Arbitrary Power (dB)")
        plt.legend()
        plt.draw()
        plt.pause(0.0001)

        logging.info("Received accumulated spectrum")

        # Stop if Ctrl-C was issued
        if stop_acquisition:
            break

    # Finished acquiring data
    logging.info("Finished acquiring data. Press Enter to quit")
    input()
