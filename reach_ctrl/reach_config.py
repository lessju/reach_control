from logging.handlers import TimedRotatingFileHandler
import datetime
import logging
import yaml
import sys
import os


class _SingletonWrapper:
    """
    A singleton wrapper class. Its instances would be created
    for each decorated class.
    """

    def __init__(self, cls):
        self.__wrapped__ = cls
        self._instance = None

    def __call__(self, *args, **kwargs):
        """Returns a single instance of decorated class"""
        if self._instance is None:
            self._instance = self.__wrapped__(*args, **kwargs)
        return self._instance


def singleton(cls):
    """
    A singleton decorator. Returns a wrapper objects. A call on that object
    returns a single instance object of decorated class. Use the __wrapped__
    attribute to access decorated class directly in unit tests
    """
    return _SingletonWrapper(cls)


@singleton
class REACHConfig:
    def __init__(self, config_file_path=None):
        """ Initialise the REACH configuration
        :param config_file_path: The path to the REACH configuration file """

        # Set configuration files root
        if "REACH_CONFIG_DIRECTORY" not in os.environ:
            logging.error("REACH_CONFIG_DIRECTORY not defined, cannot configure")
            return

        self._config_root = os.path.expanduser(os.environ['REACH_CONFIG_DIRECTORY'])

        # Check if file path is valid
        if not os.path.exists(self._config_root) or not os.path.isdir(self._config_root):
            logging.error("REACH_CONFIG_DIRECTORY is invalid ({}), path does not exist".format(self._config_root))
            return

        # Temporary settings directory
        self._loaded_settings = {}

        # Initialise logging
        self._set_logging_config()

        # Load switches 
        self._load_from_file(os.path.join(self._config_root, "switches.yaml"))

        # Load instrument
        self._load_from_file(os.path.join(self._config_root, "instrument.yaml"))

        # Load required configuration file
        if config_file_path:
            self._load_from_file(os.path.join(self._config_root, config_file_path))
        else:
            self._load_from_file(os.path.join(self._config_root, "reach.yaml"))

    def _load_from_file(self, config_filepath):
        """ Load settings from a configuration file
        :param config_filepath: The path to the configuration file """

        # Load the requested configuration file
        try:
            with open(os.path.expanduser(config_filepath)) as f:
                config = yaml.load(f, Loader=yaml.FullLoader)
                if config is not None:
                    self._loaded_settings.update(config)
                logging.info('Loaded the {} configuration file.'.format(config_filepath))
        except IOError:
            logging.critical("Configuration file {} was not found".format(config_filepath))
        except Exception:
            logging.critical("Error loading configuration file {}".format(config_filepath), exc_info=True)

    def _set_logging_config(self):
        """ Load the logging configuration """

        # Load the logging configuration file
        config_filepath = os.path.join(self._config_root, 'logging.yaml')
        self._load_from_file(config_filepath)

        # Create directory for file log
        directory = os.path.join('/var/log/reach', '{:%Y_%m_%d}'.format(datetime.datetime.now()))
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except OSError:
                logging.warning("Could not create default logging directory. Using current working directory")
                directory = os.path.join(os.getcwd(), '{:%Y_%m_%d}'.format(datetime.datetime.now()))
                if not os.path.exists(directory):
                    os.makedirs(directory)

        # Create log path and logger
        log_path = os.path.join(directory, 'reach_logs.log')

        # Get root logger
        root_logger = logging.getLogger()

        # Clear previous handlers
        for _ in root_logger.handlers:
            root_logger.handlers.pop()

        # Apply logging config and override log path
        logging_level = self._loaded_settings['logging']['loggers']['REACH']['level']
        formatter = logging.Formatter(self._loaded_settings['logging']['formatters']['standard']['format'])
        root_logger.setLevel(logging_level)

        # Set file handler
        handler = TimedRotatingFileHandler(log_path, when="h", interval=1, backupCount=5, utc=True)
        handler.setFormatter(formatter)
        handler.setLevel(logging_level)
        root_logger.addHandler(handler)

        # Set console handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        handler.setLevel(logging_level)
        root_logger.addHandler(handler)

        return log_path

    def __getitem__(self, key):
        """ Override __getitem__, return settings from loaded configuration """
        if key in self._loaded_settings.keys():
            return self._loaded_settings[key]
        else:
            logging.error("Requested setting {} does not exist".format(key))


if __name__ == "__main__":
    REACHConfig()
    logging.info("All done")
