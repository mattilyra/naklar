__author__ = 'mattilyra'

try:
    import cPickle as pickle
except ImportError:
    import pickle

import pytest

from naklar.experiment import _find_conf_files
from naklar.experiment import _read_conf_dicts


@pytest.fixture
def experiment_tree(tmpdir):
    for i in xrange(10):
        pth = tmpdir.mkdir('exp{}'.format(i)).join('conf.pkl')
        d = {'a': 1, 'b': 2}
        pth.write(pickle.dumps(d))
    return tmpdir


def test_conf_discovery(experiment_tree):
    confs = _find_conf_files(experiment_tree.strpath)
    assert(len(list(confs)) == 10)
    for i, fh in enumerate(confs):
        assert(fh.name.endswith('conf.pkl'))


def test_conf_dict_load(experiment_tree):
    confs = _find_conf_files(experiment_tree.strpath)
    dicts = _read_conf_dicts(confs)
    assert(len(list(dicts)) == 10)
