__author__ = 'Matti Lyra'

import sys
import os
import shutil

from distutils.core import setup, Extension, Command
import numpy

# remove old build directory
if 'test' in sys.argv and os.path.exists('build'):
    shutil.rmtree('build')


class PyTest(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import sys
        import subprocess
        errno = subprocess.call([sys.executable, 'runtests.py'])
        raise SystemExit(errno)

setup(
    name='naklar',
    author='Matti Lyra',
    description='A package for handling large collections of result sets from experimentation.',
    version='0.1b',

    # make the build_ext command map to that defined by Cython.Distutils
    cmdclass={'test': PyTest},

    packages=['naklar',],
)
