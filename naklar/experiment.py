import os
import re
try:
    import cPickle as pickle
except ImportError:
    import pickle

from sqlalchemy import create_engine, func
from sqlalchemy import Column, Integer, String, DateTime, Float, MetaData, \
    Table, Boolean
from sqlalchemy.orm import Session, mapper
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


def _from_existing_db(tablename):
    try:
        ExperimentBase.__tablename__ = tablename
        ExperimentBase.__table_args__ = {'autoload': True}
        ExperimentBase.prepare(_engine)
    except NoSuchTableError:
        raise NoSuchTableError('Table \'{}\' does not exists in database.'
                               .format(tablename))
    return ExperimentBase


def _from_dict(root_dir, dict_filename='conf.pkl', primary_keys=['id'],
               autoload=True):
    conf = {}
    for root, _, files in os.walk(root_dir, topdown=False):
        if dict_filename in files:
            pth = os.path.join(root, dict_filename)
            with open(pth, 'r') as fh:
                d = pickle.load(fh)
            for k, v in d.iteritems():
                if k in conf and (conf[k] is None and v is not None):
                    conf[k] = v
                elif k not in conf:
                    conf[k] = v

    meta = MetaData(bind=_engine)
    table = Table('experiment', meta)
    types = [DateTime, Float, Integer, Boolean, String]
    for k, v in conf.iteritems():
        for column_type in types:
            if column_type().python_type is type(v):
                if hasattr(v, 'split'):
                    column_type = String(len(v) * 2)
        column = Column(k, column_type, primary_key=k in primary_keys)
        table.append_column(column)

    # if the conf dictionary does not contain all of the primary key columns
    # add the ones that are missing
    if not all([k in table.c.keys() for k in primary_keys]):
        for k in primary_keys:
            if k not in table.c.keys():
                column = Column(k, Integer, primary_key=True)
                table.append_column(column)
    mapper(_Exp, table)
    meta.create_all(bind=_engine)

    if autoload:
        populate_from_disk(root_dir, dict_filename)

    return _Exp


def initialise(experiment_table, *args, **kwargs):
    """Initialises a database connection to access the experiments DB.

    If no connection arguments are defined an in memory SQLite data base is
    created. The experiments table is also created after initialising the
    connection.

    Arguments
    =========
    experiment_table : sqlalchemy.base or string
        Either a declarative `sqlalchemy` definition of a table that extends
        `naklar.experiment.ExperimentBase` or a string. In case of string the
        parameter can be a local file path reference, or the name of an
        existing table in the database.

    *args: see sqlalchemy.create_engine
        The `args` are passed to sqlachemy when creating a data base
        connection. The parameter of most interest is the address of the
        database to connect to.
    **kwargs: see sqlalchemy.create_engine or list of primary keys

    Connect to an in memoroy SQLite database and create an experiment Table
    >>> from naklar import experiment
    >>> from sqlalchemy import Column, Integer, String
    >>> class Experiment(experiment.ExperimentBase):
    >>>     __tablename__ = 'experiment'
    >>>     id = Column(Integer, primary_key=True)
    >>>     experiment_name = Column(String(255))
    >>>     home = Column(String(255))
    >>> experiment.initialise(Experiment)

    Connect to an existing MySQL database using the PyMSQL module and reflect
    the definition of a table called `experiment`
    >>> from naklar import experiment
    >>> dbname = 'ab123'
    >>> addr = 'mysql.naklar.com'
    >>> usr_pass = 'user_123:pass-word'
    >>> protocol = 'mysql+pymsql'
    >>> connect_str = '{}://{}@{}/{}'.format(protocol, user_pass, addr, dbname)
    >>> experiment.initialise('experiment', connect_str)

    See Also
    ========
        `Link SQLAlchemy connect_engine <http://docs.sqlalchemy.org/en/latest/core/engines.html?highlight
        =create_engine>`_
    """
    if _engine is None:
        connect(*args, **kwargs)

    global experiment_cls_
    if hasattr(experiment_table, 'split'):
        # connect to a data base that does contain the experiments table
        # and infer the Experiment class via reflection
        if os.path.exists(experiment_table):
            experiment_cls_ = _from_dict(experiment_table, *args, **kwargs)
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


def populate_from_disk(root_directory, dict_file='conf.pkl', load_func=None):
    if load_func is not None:
        session = Session(bind=_engine)
        load_func(root_directory, session)
        session.commit()
        session.close()
    else:
        session = Session(bind=_engine)
        for root, _, files in os.walk(root_directory, topdown=False):
            if dict_file in files:
                with open(os.path.join(root, dict_file), 'r') as fh:
                    conf = pickle.load(fh)
                exp = experiment_cls_(**conf)
                session.add(exp)
        session.commit()
        session.close()


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


class _Exp(object):
    def __init__(self, **kwargs):
        for k, v in kwargs.iteritems():
            setattr(self, k, v)