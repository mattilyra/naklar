import os
import re
try:
    import cPickle as pickle
except ImportError:
    import pickle

from sqlalchemy import create_engine, func
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.ext.declarative import declarative_base, DeferredReflection
from sqlalchemy.exc import NoSuchTableError


_engine = None
ExperimentBase = declarative_base(cls=DeferredReflection)


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


def initialise(experiment_table, *args, **kwargs):
    """Initialises a database connection to access the experiments DB.

    If no arguments are defined an in memory SQLite data base is created. The
    experiments table is also created after initialising the connection.
    """
    if _engine is None:
        connect(*args, **kwargs)

    global experiment_cls_
    if hasattr(experiment_table, 'split'):
        # connect to a data base that does contain the experiments table
        # and infer the Experiment class via reflection
        try:
            ExperimentBase.__tablename__ = experiment_table
            ExperimentBase.__table_args__ = {'autoload': True}
            ExperimentBase.prepare(_engine)
            experiment_cls_ = ExperimentBase
        except NoSuchTableError:
            raise NoSuchTableError('Table \'{}\' does not exists in database.'
                                   .format(experiment_table))
    elif ExperimentBase in experiment_table.__bases__:
        # connect to a data base that does not contain the experiments table
        experiment_table.metadata.create_all(_engine)
        ExperimentBase.prepare(_engine)
        experiment_cls_ = experiment_table
    else:
        raise ValueError('Experiment class must extend '
                         'naklar.experiment.ExperimentBase')


def populate_from_disk(root_directory, load_func=None):
    if callable is not None:
        session = Session(bind=_engine)
        load_func(root_directory, session)
        session.commit()
        session.close()
    else:
        raise NotImplementedError('Autoloading experiments from disk not '
                                  'implemented yet, please provide a load '
                                  'function.')


def select(*columns, **filters):
    """Get rows from the Experiment table associated with session.

    Parameters
    ----------
    session : Session

    *columns : str, unicode or InstrumentedAttribute, optional
        Optional parameters to retrieve only specific column values
        from the Experiment table. If none are specified the whole
        Experiment object is returned.

    **filters
        Optional keys to filter the returned Experiments by.

    Returns
    -------
    list
        A list of Experiment or KeyedTuple.


    See Also
    --------
    sqlalchemy.orm.session.Session,
    sqlalchemy.orm.attributes.InstrumentedAttribute,
    sqlalchemy.util._collections.KeyedTuple

    Retrieve all Experiments where Experiment.k == 2

    >> session = load_experiments('.')
    >> rows = get_rows(session, k=2)

    Retrieve specific columns from Experiments where Experiment.k == 2

    >> session = load_experiments('.')
    >> rows = get_rows(session, 'model_type', 'results_file', k=2)

    >> session = load_experiments('.')
    >> rows = get_rows(session, 'model_type', 'results_file', k=[1, 2, 3, 5, 8])
    """
    if columns:
        cols = []
        for col in columns:
            if isinstance(col, (str, unicode)):
                cols.append(getattr(experiment_cls_, col))
            elif isinstance(col, InstrumentedAttribute):
                cols.append(col)
    else:
        cols = [experiment_cls_]

    session = Session(bind=_engine)
    q = session.query(*cols)

    if filters:
        filts = []
        for k, v in filters.iteritems():
            if hasattr(v, 'split'):
                filts.append(getattr(experiment_cls_, k) == v)
            elif hasattr(v, '__getitem__') or hasattr(v, '__iter__'):
                filts.append(getattr(experiment_cls_, k).in_(v))
            else:
                filts.append(getattr(experiment_cls_, k) == v)
        q = q.filter(*filts)
    rows = q.all()
    session.close()
    return rows
