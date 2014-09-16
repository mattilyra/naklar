import os
import re
try:
    import cPickle as pickle
except ImportError:
    import pickle

from sqlalchemy import create_engine, func
from sqlalchemy import Column, Integer, String, DateTime, Float, MetaData, \
    Table, Boolean
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


def from_existing_db(tablename):
    try:
        ExperimentBase.__tablename__ = tablename
        ExperimentBase.__table_args__ = {'autoload': True}
        ExperimentBase.prepare(_engine)
    except NoSuchTableError:
        raise NoSuchTableError('Table \'{}\' does not exists in database.'
                               .format(tablename))
    return ExperimentBase


def from_dict(root_dir, dict_filename='settings.pkl'):
    conf = {}
    for root, _, files in os.walk(root_dir, topdown=False):
        if dict_filename in files:
            pth = os.path.join(root, dict_filename)
            with open(pth, 'r') as fh:
                d = pickle.load(fh)
            for k, v in conf.iteritems():
                if k in conf and v is not None:
                    conf[k] = v
                elif k not in conf:
                    conf[k] = v

    if any(itm is None for itm in conf.values()):
        pth = os.path.join(root_dir, 'conf.txt')
        with open(pth, 'w') as fh:
            for k, v in conf.iteritems():
                fh.write('{}\t{}\t{}\n'.format(k, v, type(v)))

        raise AttributeError('Some attributes have None values and their '
                             'data type can not be inferred for creating the '
                             'table. Please edit the file {}, provide the '
                             'missing data types and then call '
                             'naklar.experiment.from_dict again.'.format(pth))

    meta = MetaData()
    table = Table('experiment', meta)
    types = [DateTime, Float, Integer, Boolean, String]
    for k, v in conf.iteritems():

        table.append_column()
    #todo: implement


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
        if os.path.exists(experiment_table):
            experiment_cls = _from_dict(experiment_table)
        else:
            experiment_cls_ = _from_existing_db(experiment_table)
    elif ExperimentBase in experiment_table.__bases__:
        # connect to a database and create a new table
        experiment_table.metadata.create_all(_engine)
        ExperimentBase.prepare(_engine)
        experiment_cls_ = experiment_table
    else:
        raise ValueError('Experiment class must extend '
                         'naklar.experiment.ExperimentBase, be a refence to a '
                         'pickled Python dictionary or be the name of '
                         'an existing table.')


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
