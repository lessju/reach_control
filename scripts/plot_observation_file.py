from matplotlib import pyplot as plt
import numpy as np
import h5py
import os

if __name__ == "__main__":
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option("-f", "--file", dest="file", help="File to plot")
    parser.add_option("-d", "--dataset", dest="dataset", help="Dataset to plot")
    (options, args) = parser.parse_args()

    if options.file is None:
        print("Input file required")
        exit()

    if not os.path.exists(options.file) or not os.path.isfile(options.file):
        print("Provided filepath is not a file or does not exist")
        exit()


    with h5py.File(options.file, 'r') as f:
        dset = f['observation_data']

        if "{}_spectra".format(options.dataset) not in dset.keys():
            print("Data set {} does not exist".format(options.dataset))
            exit()

        dset = f['observation_data/{}_spectra'.format(options.dataset)]
        
        plt.plot(10*np.log10(dset[0, :]))
        plt.show()
