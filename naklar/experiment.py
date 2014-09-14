import os
import re
try:
    import cPickle as pickle
except ImportError:
    import pickle

from sqlalchemy import create_engine, Column, Integer, String, DateTime, func,\
    Text, MetaData
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm.attributes import InstrumentedAttribute


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


def initialise(experiment_table, *args, **kwargs):
    """Initialises a database connection to access the experiments DB.

    If no arguments are defined an in memory SQLite data base is created. The
    experiments table is also created after initialising the connection.
    """
    if _engine is None:
        connect(*args, **kwargs)
    print(_engine)
    global _Experiment
    if hasattr(experiment_table, 'split'):
        meta = MetaData()
        meta.reflect(bind=_engine)
        for k, v in meta.tables.iteritems():
            if k == experiment_table:
                _Experiment = v
                break
        else:
            raise ValueError('Table \'{}\' not found in database.'
                             .format(experiment_table))
    elif ExperimentBase in experiment_table.__bases__:
        _Experiment = declarative_base(cls=experiment_table)
        _Experiment.metadata.create_all(_engine)

    else:
        raise ValueError('Experiment class must extend '
                         'naklar.experiment.ExperimentBase')

    global experiment_cls_
    experiment_cls_ = _Experiment


def populate_from_disk(root_directory, load_func=None):
    global session_
    if callable is not None:
        session_ = Session(bind=_engine)
        load_func(root_directory, session_)
        session_.commit()
        session_.close()
        session_ = Session(bind=_engine)


def get_rows(session, *columns, **filters):
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
                cols.append(getattr(_Experiment, col))
            elif isinstance(col, InstrumentedAttribute):
                cols.append(col)
    else:
        cols = [_Experiment]

    q = session.query(*cols)

    if filters:
        filts = []
        for k, v in filters.iteritems():
            if hasattr(v, 'split'):
                filts.append(getattr(_Experiment, k) == v)
            elif hasattr(v, '__getitem__') or hasattr(v, '__iter__'):
                filts.append(getattr(_Experiment, k).in_(v))
            else:
                filts.append(getattr(_Experiment, k) == v)
        q = q.filter(*filts)
    rows = q.all()
    return rows

_Base = declarative_base()
class ExperimentBase(_Base):
    """The Experiment class holds references to settings of an experiment.
    """
    # @declared_attr
    # def __tablename__(cls):
    #     return 'experiment'

    id = Column(Integer, primary_key=True)
    experiment_name = Column(String(255))
    experiment_comment = Column(Text(65535))
    home = Column(String(255))
    started_at = Column(DateTime, default=func.now())
    finished_at = Column(DateTime, default=func.now())

# the default experiment claass is ExperimentBase, this can be overridden by
# passing another experiment class to naklar.initialise
# experiment_cls_ = ExperimentBase