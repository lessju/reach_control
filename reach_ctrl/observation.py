from datetime import datetime, timedelta
import logging
import h5py
import os

from reach_ctrl.ucontroller.microcontroller import Microcontroller
from reach_ctrl.spectrometer.spectrometer import Spectrometer
from reach_ctrl.reach_config import REACHConfig
from reach_ctrl.vna.vna import VNA
from reach_ctrl import utils


class REACHObservation:
    """ Class which implements the functionality for the observation """

    def __init__(self, observation, operations):
        """ Class constructor
        :param observation: Observation parameters in dictionary format
        :params operations: List of operations """

        # Sanity check
        if not type(observation) is dict:
            logging.error("No observation parameters defined")
        if not type(operations) is list and len(operations) == 0:
            logging.error("No operations defined")

        # Store observation parameters and operations
        self._simulation_mode = False
        self._observation_name = observation.get("name", "test_observation")
        self._start_time = observation.get("start_time", "now")
        self._scheduling_mode = observation.get("scheduling_mode", "UCT").upper()
        self._output_directory = observation.get("output_directory", "/tmp/reach_test_obs")
        self._longitude, self._latitude = observation.get("longitude"), observation.get("latitude")
        self._operations = operations

        # Check if directory exists, and if not try to create it
        if not os.path.exists(self._output_directory):
            try:
                os.makedirs(self._output_directory)
            except IOError:
                logging.error("Could not create output directory {}".format(self._output_directory))
                return
        elif os.path.isfile(self._output_directory):
            logging.error("Specfied output path {} is a file, must be a directory".format(self._output_directory))

        # Placeholder for hardware devices
        self._spectrometer = None
        self._ucontroller = None
        self._vna = None

        # Placeholder for spectra data file
        current_time = datetime.utcnow()
        self._observation_data_file = os.path.join(self._output_directory, "{}_{}.hdf5".format(self._observation_name,
                                                                                               current_time.strftime(
                                                                                                   "%Y%m%d_%H%M%S")))

    def run_observation(self, operations=None):
        """ Run observation, go through all operations 
        :param operations: List of operations to run. If this is not specified
                           then the locally saved operations will be used """

        # Wait for observation to start
        if not self._simulation_mode:
            utils.schedule(self._start_time, mode=self._scheduling_mode)
        else:
            logging.info("Operations will start at {}".format(self._start_time))

        # If a list of operations is not passed on as an argument then use
        # the list in the object instance
        if operations is None:
            operations = self._operations

        # Create output file 
        if not self._simulation_mode:
            self._create_output_file()

        # Go through list of operations and run them
        for operation in operations:
            if type(operation) is not dict:
                self.run_operation(operation)
            else:
                key = list(operation.keys())
                if len(key) != 1:
                    logging.error("Operation entry can only have one key ({} is invalid). Skipping".format(operation))
                    continue

                self.run_operation(key[0], operation[key[0]])

    def run_operation(self, operation, parameters=None):
        """ Execute an operation
        :param operation: Operation to be performed
        :param parameters: Dict containing any required parameters"""

        # Execute the function associated with the operation
        if operation == "power_on_spectrometer":
            self._initialise_spectrometer(parameters['initialise'])
        elif operation == "power_on_vna":
            self._initialise_vna()
        elif operation == "power_on_ucontroller":
            self._initialise_ucontroller()
        elif operation == "power_off_ucontroller":
            self._switch_off_ucontroller()
        elif operation == "power_off_vna":
            self._switch_off_vna()
        elif operation == "power_off_spectrometer":
            self._switch_off_spectrometer()
        elif operation == "switch_on_mts":
            self._switch_mts(True)
        elif operation == "switch_off_mts":
            self._switch_mts(False)
        elif operation == "calibrate_vna":
            self._calibrate_vna()
        elif operation == "measure_s":
            self._measure_s(parameters['name'], parameters['source'])
        elif operation == "measure_spectrum":
            self._measure_spectrum(parameters['name'], parameters['source'], parameters['duration'])

        # Main observation with repeated readings
        elif operation == "observation_operations":
            # Running a repeated obs. Check start time and repetition period
            local_start = parameters.get('start_time', "now")
            period = parameters.get("every", 0)

            # If "now", then schedule in 10 seconds
            if local_start == "now":
                local_start = datetime.now() + timedelta(seconds=10)

            # Wait for observation start
            if not self._simulation_mode:
                utils.schedule(local_start, mode=self._scheduling_mode)
            else:
                logging.info("Observation will start at {}".format(self._start_time))

            # Process the repeating observation operations
            for i in range(parameters.get('repetitions', 1)):
                # Update start time to reflect current iteration
                if period == "now":
                    self._start_time = "now"
                else:
                    self._start_time = local_start + timedelta(seconds=period * i)

                self.run_observation(parameters.get('operations', []))
        else:
            logging.warning("Operation {} not supported. Skipping".format(operation))

    def dry_run_operations(self):
        """ Perform a dry run of the operations to make sure that configuration is valid """

        # Enable simulation mode
        self._simulation_mode = True

        # Run operations
        self.run_observation()

        # Disable simulation mode
        self._simulation_mode = False

    def _create_output_file(self):
        """ Create HDF5 output file """
        # Create HDF5 file which will store observation data
        with h5py.File(self._observation_data_file, 'w') as f:
            # Create group which will contain observation info
            info = f.create_group('observation_info')

            # Add attributes to group
            info.attrs['observation_name'] = self._observation_name
            info.attrs['start_time'] = self._start_time
            info.attrs['start_lst'] = utils.get_sidereal_time(self._longitude, self._latitude,
                                                              self._start_time.timestamp(0))
            # info.attrs['operations'] = self._operations
            # TODO: Add more when required

            # Create group which will contain all observation data
            f.create_group("observation_data")

        logging.info("Created output file")

    def _add_spectrum_to_file(self, spectrum, name, timestamp):
        """ Add spectrum to data file 
        :param spectrum: The spectrum
        :param name: The data name
        :param timestamp: Spectrum timestsamp """

        nof_frequency_channels = REACHConfig()['spectrometer']['nof_frequency_channels']

        with h5py.File(self._observation_data_file, 'a') as f:
            # Create dataset names
            dataset_name = "{}_spectra".format(name)
            timestamp_name = "{}_timestamps".format(name)
            lst_name = "{}_lst_time".format(name)

            # Load observation data group
            dset = f['observation_data']

            # If data sets do not exist, add them
            if dataset_name not in dset.keys():
                dset.create_dataset(dataset_name,
                                    (0, nof_frequency_channels),
                                    maxshape=(None, nof_frequency_channels),
                                    chunks=True,
                                    dtype='u8')

                dset.create_dataset(timestamp_name, (0,),
                                    maxshape=(None,), chunks=True, dtype='f8')

                dset.create_dataset(lst_name, (0,),
                                    maxshape=(None,), chunks=True, dtype='f8')

                logging.info("Added {} dataset to output file".format(dataset_name))

            # Add spectrum and timestamp to buffer
            dset = f['observation_data/{}'.format(dataset_name)]
            dset.resize((dset.shape[0] + 1, dset.shape[1]))
            dset[-1, :] = spectrum

            dset = f['observation_data/{}'.format(timestamp_name)]
            dset.resize((dset.shape[0] + 1,))
            dset[-1] = timestamp

            dset = f['observation_data/{}'.format(lst_name)]
            dset.resize((dset.shape[0] + 1,))
            dset[-1] = utils.get_sidereal_time(self._longitude, self._latitude, timestamp)

    def _measure_s(self, name, source):
        """ Measure S parameters of a specific source """

        # Simulation mode logging
        if self._simulation_mode:
            logging.info("S parameters for {} will be measured".format(name))
            return

        # Sanity check
        if self._vna is None or self._ucontroller is None:
            logging.error("VNA and ucontroller must be initialised to measure S parameters")
            exit()

        # Toggle switch
        self._enable_source(source)

        # Measure with VNA
        # TODO: Define file name
        file_name = ""
        self._vna.snp_save(file_name)

        logging.info("Measured S parameters for {}".format(name))

    def _measure_spectrum(self, name, source, duration):
        """ Measure spectrum of specific source """

        # Simulation mode logging
        if self._simulation_mode:
            logging.info("Spectrum for {} will be measured".format(name))
            return

        # Sanity check
        if self._spectrometer is None:
            logging.error("Spectrometer must be initialised to measure spectra.")
            exit()

        if source != "none" and self._ucontroller is None:
            logging.error("Microcontroller must be initialised to measure spectra.")
            exit()

        # Toggle switch
        if source != "none":
            self._enable_source(source)

        # Get spectrum and save to file
        timestamps, spectra = self._spectrometer.acquire_spectrum(nof_seconds=duration)
        self._add_spectrum_to_file(spectra, name, timestamps[0])

        logging.info("Measured spectrum for {}".format(name))

    def _calibrate_vna(self):
        """ Calibrate VNA """

        # Simulation mode logging
        if self._simulation_mode:
            logging.info("VNA will be calibrated")
            return

        # Sanity check
        if self._vna is None or self._ucontroller is None:
            logging.error("VNA and ucontroller must be initialised to measure spectra.")
            exit()

        # Measure open
        self._enable_source("vna_open")
        self._vna.calib('open')
        self._vna.wait()

        # Measure short
        self._enable_source("vna_short")
        self._vna.calib('short')
        self._vna.wait()

        # Measure load
        self._enable_source("vna_load")
        self._vna.calib('load')
        self._vna.wait()

        logging.info("Performed VNA calibration")

        # Apply calibration data
        self._vna.calib("apply")
        logging.info("Applied VNA calibration")

        # Save calibration
        # TODO: Define file name
        file_name = "file"
        self._vna.state_save(file_name)
        logging.info("Saved VNA calibration")

    def _enable_source(self, source):
        """ Enable source through microcontroller 
        :param source: Source defined in switches """

        # Simulation mode logging
        if self._simulation_mode:
            logging.info("Source {} will be enabled".format(source))
            return

        # Get switch info
        switch_info = REACHConfig()['sources'][source]

        # Toggle required switches
        for switch in switch_info:
            # TODO: Implement properly
            self._toggle_switch(switch, 1)

    def _toggle_switch(self, switch, on):
        """ Toggle switch through microcontroller
        :param switch: Switch name
        :param on: True if switch is turned on, off otherwise """
        # TODO: Implement properly
        return

    def _switch_mts(self, on):
        """ Switch on or off the MTS switch 
        :param on: True if MTS needs to be switched off, False otherwise """

        # Simulation mode logging
        if self._simulation_mode:
            logging.info("MTS will be switched {}".format("on" if on else "off"))
            return

        self._toggle_switch("MTS", on)

    def _initialise_ucontroller(self):
        """ Initialise ucontroller """

        # Simulation mode logging
        if self._simulation_mode:
            logging.info("Microcontroller will be initialsied")
            return

        if self._ucontroller is not None:
            logging.warning("uController already initialiased, skipping")
            return

        conf = REACHConfig()['ucontroller']
        self._ucontroller = Microcontroller(conf['port'], conf['baudrate'])

        logging.info("Initialised ucontroller")

    def _initialise_vna(self):
        """ Initialise VNA """

        # Simulation mode logging
        if self._simulation_mode:
            logging.info("VNA will be initialised")
            return

        if self._vna is not None:
            logging.warning("VNA already initialiased, skipping")
            return

        # Create VNA instance
        conf = REACHConfig()['vna']
        self._vna = VNA()
        self._vna.initialise(channel=conf['channel'],
                             freqstart=conf['freqstart'],
                             freqstop=conf['freqstop'],
                             ifbw=conf['ifbw'],
                             average=conf['average'],
                             calib_kit=conf['calib_kit'],
                             power_level=conf['power_level'])

        logging.info("Initialised VNA")

    def _initialise_spectrometer(self, initialise=False):
        """ Initialise spectrometer """

        # Simulation mode logging
        if self._simulation_mode:
            logging.info("Spectrometer will be initialised (initialise={})".format(initialise))
            return

        if self._spectrometer is not None:
            logging.warning("Spectrometer already initialiased, skipping")
            return

        # Create spectrometer instance    
        conf = REACHConfig()['spectrometer']
        self._spectrometer = Spectrometer(ip=conf['ip'], port=conf['port'],
                                          lmc_ip=conf['lmc_ip'], lmc_port=conf['lmc_port'])

        bitstream = os.path.join(os.environ['REACH_CONFIG_DIRECTORY'], conf['bitstream'])

        if initialise:
            logging.info("Initialising spectrometer")
            self._spectrometer.program(bitstream)
            self._spectrometer.initialise(channel_truncation=conf['channel_truncation'],
                                          integration_time=conf['integration_time'],
                                          ada_gain=conf['ada_gain'])

        logging.info("Initialised spectrometer")

    def _switch_off_ucontroller(self):
        """ Switch off ucontroller """
        # Simulation mode logging
        if self._simulation_mode:
            logging.info("Ucontroller will be switched off")
            return

        # TODO: What do we need?
        logging.info("Power off ucontroller")

    def _switch_off_vna(self):
        """ Switch off VNA """
        # Simulation mode logging
        if self._simulation_mode:
            logging.info("VNA will be switched off")
            return

        # Terminate VNA
        if self._vna is None:
            self._vna.terminate()

        logging.info("Power off VNA")

    def _switch_off_spectrometer(self):
        """ Switch off spectrometer """
        # Simulation mode logging
        if self._simulation_mode:
            logging.info("Spectrometer will be switched off")
            return

        # TODO: Reset PDU power to TPM
        logging.info("Power off spectrometer")


if __name__ == "__main__":
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option("--config", dest="config_file", default="reach", help="Configuration file (default: reach)")
    (options, args) = parser.parse_args()

    # Sanity check on provided config file
    if not options.config_file.endswith(".yaml"):
        options.config_file += ".yaml"

    # Check that REACH_CONFIG_DIRECTORY is defined in the environment
    if "REACH_CONFIG_DIRECTORY" not in os.environ:
        print("REACH_CONFIG_DIRECTORY must be defined in the environment")
        exit()

    # Check if file exists
    full_path = os.path.join(os.environ['REACH_CONFIG_DIRECTORY'], options.config_file)
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        print("Provided file ({}, fullpath {}) could not be found or is not a file".format(options.config_file,
                                                                                           full_path))
        exit()

    # Load configuration
    c = REACHConfig(options.config_file)

    # Create observation instance
    obs = REACHObservation(c['observation'], c['operations'])

    # Perform a dry run to test the observation config
    obs.dry_run_operations()

    # Run the observation
    # obs.run_observation()
