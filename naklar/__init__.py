__author__ = 'Matti Lyra'

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from naklar import experiment


session_ = None
_engine = None


def connect(*args, **kwargs):
    """Initialises a database connection to access the experiments DB.

    :param args:
    :param kwargs:
    """
    global _engine
    if not args:
        _engine = create_engine('sqlite:///:memory:', echo=False)
    else:
        _engine = create_engine(*args, **kwargs)


def initialise(exp_class, *args, **kwargs):
    """Initialises a database connection to access the experiments DB.

    If no arguments are defined an in memory SQLite data base is created. The
    experiments table is also created after initialising the connection.
    """
    if _engine is None:
        connect(*args, **kwargs)
    
    if experiment.ExperimentBase in exp_class.__bases__:
        experiment.experiment_cls_ = exp_class
        exp_class.metadata.create_all(_engine)
    else:
        raise ValueError('Experiment class must extend '
                         'naklar.experiment.ExperimentBase')


def populate_from_disk(root_directory, load_func=None):
    global session_
    if callable is not None:
        session_ = Session(bind=_engine)
        load_func(root_directory, session_)
        session_.commit()
        session_.close()
        session_ = Session(bind=_engine)