from __future__ import print_function
from matplotlib import pyplot as plt
import numpy as np
import h5py
import os

if __name__ == "__main__":
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option("-f", "--file", dest="file", help="File to plot")
    parser.add_option("-d", "--dataset", dest="dataset", help="Dataset to plot")
    parser.add_option("-c", "--channel", dest="channel", default=0, type=int, help="Channel to plot (default: 0)")
    (options, args) = parser.parse_args()

    if options.file is None:
        print("Input file required")
        exit()

    if not os.path.exists(options.file) or not os.path.isfile(options.file):
        print("Provided filepath is not a file or does not exist")
        exit()


    with h5py.File(options.file, 'r') as f:
        dset = f['observation_data']

        if "{}_spectra".format(options.dataset) not in list(dset.keys()):
            print("Data set {} does not exist".format(options.dataset))
            exit()

        dset = f['observation_data/{}_spectra'.format(options.dataset)]
        
        # plt.plot(10*np.log10(np.sum(dset[options.channel, :, :], axis=0)))
        plt.plot(dset[options.channel, 0, :])
        plt.show()
