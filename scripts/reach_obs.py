#!/usr/bin/env python

import time
import struct
import sys
import logging
import numpy as np
import argparse
import serial
from reach_ctrl import uctrl, vna


if __name__ == '__main__':

    p = argparse.ArgumentParser(description='REACH control',
        formatter_class=argparse.RawDescriptionHelpFormatter)

    p.add_argument('--config', nargs=1, type=str, 
        help='Perform operations specified in the config file')

    args = p.parse_args()

    dict_inst = {}

    # prepare logger
    logger = logging.getLogger('REACH')
    
    def vna_init(**kwargs):
        # check if the instance exists
        if kwargs['name'] not in dict_inst:
    
            # create a spec instance
            from reach_ctrl.vna import SCPIInterface, VNA
            tr = VNA(SCPIInterface(), **kwargs)
    
            # add instance into dictionary
            dict_inst[kwargs['name']] = tr
    
        tr = dict_inst[kwargs['name']]
    
        # initialization
        if tr.init(**kwargs):
            logger.info('VNA ' + kwargs['name'] + ' initialization done.')
        else:
            logger.warn('VNA ' + kwargs['name'] + ' initialization failed.')
    
    def uc_init(**kwargs):

        # check if the instance exists
        if kwargs['name'] not in dict_inst:
    
            # create a spec instance
            import serial
            from reach_ctrl.uctrl import Microcontroller
            ser = serial.Serial(kwargs['port'],kwargs['baudrate'])
            uc = Microcontroller(ser, **kwargs)
    
            # add instance into dictionary
            dict_inst[kwargs['name']] = uc
    
        uc = dict_inst[kwargs['name']]
    
        # initialization
        if uc.init(**kwargs):
            logger.info('Microcontroller ' + kwargs['name'] + ' initialization done.')
        else:
            logger.warn('Microcontroller ' + kwargs['name'] + ' initialization failed.')
    
    def calibration(**kwargs):

        # TODO list

        # uctrl choose calibration std
        # vna calculate calibration data
        # uctrl choose calibration std
        # vna calculate calibration data
        # uctrl choose calibration std
        # vna calculate calibration data
        # vna apply calibration data

        logger.info('VNA calibration done')
    
    def signal_select(**kwargs):

        # switch signal

        logger.info('Signal switching done')
    
    def spec_init(**kwargs):
    
        # check if the instance exists
        if kwargs['name'] not in dict_inst:
    
            # create a spec instance
            from reach_ctrl.spectrometer import Spectrometer
            spec = Spectrometer(**kwargs)
    
            # add instance into dictionary
            dict_inst[kwargs['name']] = spec
    
        spec = dict_inst[kwargs['name']]
    
        # programming
        spec.prog(**kwargs)
    
        # setting parameters
        spec.init(**kwargs)

        logger.info('Spectrometer ' + kwargs['name'] + ' initialization done.')
    
    def spec_measure(**kwargs):

        # check if the instance exists
        spec = dict_inst[kwargs['name']]

        # setting parameters
        spec.init(**kwargs)

        # measure
        data = spec.measure(**kwargs)

        # save file
        path = kwargs.get('path','./')
        timestamp = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())
        filename = path + kwargs['name'] + '_' + timestamp + '.txt'
        np.savetxt(filename, data)

        logger.info('spectrum saved in ' + filename)

    def test(**kwargs):
        logger.info('test test')
    
    if args.config:
        import yaml
        from reach_ctrl.reachhelper import search
        fname = search(args.config[0])
        if fname is None:
            logger.critical('Cannot find {}'.format(args.config[0]))
            exit

        try:
            with open(fname, 'r') as fh:
                config = yaml.load(fh, Loader=yaml.FullLoader)
        except Exception as e:
            logger.critical('Cannot load {}'.format(args.config[0]))
            exit
    else:
        exit

    import logging.config
    logging.config.dictConfig(config['logging'])

    config['operations'] = [op.popitem() for op in config['operations']]

    # go through the operation list
    for op, params in config['operations']:

        if params['name'] not in dict_inst:
            params['logger'] = logger.getChild(params['name'])

        if op == 'init_spec':
            spec_init(**params)
        elif op == 'init_vna':
            vna_init(**params)
        elif op == 'init_uc':
            uc_init(**params)
        elif op == 'measure':
            spec_measure(**params)
        elif op == 'calib':
            calibration(**params)
        elif op == 'switch':
            signal_select(**params)
        elif op == 'test':
            test(**params)
        else:
            logger.warn('Operation {} not implemented'.format(op))






