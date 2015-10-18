__author__ = 'Matti Lyra'

import os
import re


def translate_path(path, ptrn, replace):
    """Replace a directory path on file system with that of another.

    Given an existing directory `path` on one filesystem replace the path to
    its parent directory with the path to its parent directory on the current
    filesystem.

    :param str path: the path to be translated
    :param str root: the
    :return:

    >>> pth = '/mnt/lustre/scratch/inf/abc123/experiments'
    >>> os.getcwd() # /usr/local/home/
    >>> os.listdir(os.getcwd()) # ['.', '..', 'experiments']
    >>> translate_path(pth) # /usr
    """
    if path is None:
        return path
    pth = re.sub(ptrn, replace, path)
    pth = os.path.expandvars(pth)
    pth = os.path.expanduser(pth)
    pth = os.path.normpath(pth)
    if not os.path.exists(pth):
        UserWarning('Translated path \'{}\' does not exist.'.format(pth))
    return pth