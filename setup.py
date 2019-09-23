from __future__ import absolute_import, division, print_function
import os, glob
from setuptools import setup, find_packages

# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup_args = {
    'name' : "reach_ctrl",
    'version': '0.0.1',
    'author' : "Tian Huang",
    'author_email' : "ian.h.0628@gmail.com",
    'description' : ("Digital front-end control for REACH project"),
    'license' : "LICENSE",
    'keywords' : "digital control REACH",
    'url' : "https://github.com/ianmalcolm/reach_ctrl",
    'packages' : find_packages(),
    'include_package_data' : True,
    'package_data' : {'' : ['config/*.yaml', 'config/*.fpg'],},
    'scripts':glob.glob('scripts/*'),
    'install_requires':read('requirements.txt').splitlines(),
    'long_description':read('README.md'),
    'classifiers':[
        'Development Status :: 1 - Planning',
        'Topic :: Scientific/Engineering :: Astronomy',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
        #'Programming Language :: Python :: 3.6',
    ],
    #'zip_safe': False,
}

if __name__ == '__main__':

    setup(**setup_args)
