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
        """ Initialize VNA
            It creates a VNA instance if it does not exist
            Please refer to reach_ctrl.vna for parameter details
        """
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
        """ Initialize Microcontroller
            It creates a microcontroller instance if it does not exist
            Please refer to reach_ctrl.uctrl for parameter details
        """

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
        if not uc.init(**kwargs):
            logger.warn('Microcontroller ' + kwargs['name'] + ' initialization failed.')

        logger.info('Microcontroller ' + kwargs['name'] + ' initialization done.')

    def switch(**kwargs):
        """ switching
            relay       the name of the relay in big letter
            sw          the name of the switch in big letter
            position    integer
        """
        SWITCH = {
                    'MS1':range(24,32),
                    'MS2':range(33,39),
                    'MS3':[],
                    'MS4':[],
                    'MTS':None, # replace None with a gpio pin number
                }
        uc = dict_inst[kwargs['name']]
        pos = kwargs['position']
        relay = kwargs['relay']

        if len(SWITCH[relay]) == 1:
            uc.gpio(SWITCH[relay], pos)
        else: # greater than 1
            val = [0] * len(SWITCH[relay])
            val[int(pos)-1] = 1
            uc.gpios(SWITCH[relay], val)

    def calibration(**kwargs):

        # This is just an example, a complete implementation subject to
        # a detailed calibration procedure

        vna = kwargs.get('name')
        vna_h = dict_inst[vna]
        uc_h = dict_inst[uc]
        
        # calibration std 'open'
        for sw in kwargs['open']:
            switch(sw['switch'])
        vna_h.calib('open')
        vna_h.wait() # calib takes a couple of seconds. use wait to sync

        # calibration std 'short'
        for sw in kwargs['short']:
            switch(sw['switch'])
        vna_h.calib('short')
        vna_h.wait()

        # calibration std 'load'
        for sw in kwargs['load']:
            switch(sw['switch'])
        vna_h.calib('load')
        vna_h.wait()

        # vna apply calibration data
        vna_h.calib('apply')
        logger.info('Calibration done.')

    def calib_save(**kwargs):
        fname = vna + time.strftime(kwargs['file_name_fmt'], time.localtime())
        vna_h.state_save(fname, kwargs)
        logger.info('Save system state and calibration data in file ' + fname)
    
    def vna_measure(**kwargs):
        for sw in kwargs['source']:
            switch(sw['switch'])
        fname = vna + time.strftime(kwargs['file_name_fmt'], time.localtime())
        vna_h.snp_save(fname, kwargs)
        logger.info('Save S parameter measurement in file ' + fname)

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

        for sw in kwargs['source']:
            switch(sw['switch'])

        # check if the instance exists
        spec = dict_inst[kwargs['name']]

        # setting parameters
        spec.init(**kwargs)

        # measure
        data = spec.measure(**kwargs)

        # save file
        path = kwargs.get('path','./')
        t = time.strftime(kwargs['file_name_fmt'], time.localtime())
        fname = spec + t + '.txt'
        np.savetxt(fname, data)

        logger.info('spectrum saved in ' + fname)

    def test(**kwargs):
        logger.info('test test')

    def power(**kwargs):
        uc = dict_inst[kwargs['name']]
        if '5v' in kwargs:
            uc.gpio(21, kwargs['5v']) 
        if '12v' in kwargs:
            uc.gpio(22, kwargs['12v']) 
        if '24v' in kwargs:
            uc.gpio(23, kwargs['24v']) 
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
        elif op == 'measure_spec':
            spec_measure(**params)
        elif op == 'calib':
            calibration(**params)
        elif op == 'save_calib':
            calib_save(**params)
        elif op == 'switch':
            switch(**params)
        elif op == 'measure_s':
            vna_measure(**params)
        elif op == 'power':
            power(**params)
        elif op == 'test':
            test(**params)
        else:
            logger.warn('Operation {} not implemented'.format(op))






