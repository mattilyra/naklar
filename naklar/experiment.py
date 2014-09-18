import os
from os import path
import re
import types
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
from sqlalchemy.ext.hybrid import hybrid_property


_engine = None
ExperimentBase = declarative_base(cls=DeferredReflection)


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
               autoload=True, decorators={}):
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

    # meta = MetaData(bind=_engine)
    # table = Table('experiment', meta)
    ExperimentBase.__tablename__ = 'experiment'
    ExperimentBase.__mapper_args__ = {'column_prefix': '_'}
    sql_types = [DateTime, Float, Integer, Boolean, String]
    for k, v in conf.iteritems():
        for column_type in sql_types:
            if column_type().python_type is type(v):
                if hasattr(v, 'split'):
                    column_type = String(len(v) * 2)
                break
        column = Column(k, column_type, primary_key=k in primary_keys)
        # table.append_column(column)
        setattr(ExperimentBase, k, column)

    # create a dictionary that will be passed to the mapper
    # props = {}

    # if the conf dictionary does not contain all of the primary key columns
    # add the ones that are missing
    # if not all([k in table.c.keys() for k in primary_keys]):
    #     for k in primary_keys:
    #         if k not in table.c.keys():
    #             column = Column(k, Integer, primary_key=True)
    #             table.append_column(column)
    #
    #             if k in decorators:
    #                 props['_{}'.format(k)] = table.c[k]
    #
    # if decorators:
    #     for k, (get, set, delete) in decorators.iteritems():
            # if get is None:
            #     def _g(self):
            #         return getattr(self, '_{}'.format(k))
            #     get = types.MethodType(_g, None, _Exp)

            # if callable(get) and callable(set) and callable(delete):
            # setattr(_Exp, k, property(get, set, delete))
            # setattr(_Exp, '_{}'.format(k), table.c[k])
            # else:
            #     raise ValueError('Decorator functions must be callable. Found a'
            #                      ' decorator \'{}\' that is {}'
            #                      .format(k, v))

    ExperimentBase.metadata.create_all(_engine)
    ExperimentBase.prepare(_engine)
    # mapper(_Exp, table, properties=props)
    # meta.create_all(bind=_engine)

    if autoload:
        global experiment_cls_
        experiment_cls_ = ExperimentBase
        populate_from_disk(root_dir, dict_filename)

    return ExperimentBase


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
    """Initialises a database connection to access the experiments Table.

    If no connection arguments are defined an in memory SQLite database is
    created. The experiments table is also created after initialising the
    connection.

    The database connection is defined in a manner similar to SQLAlchemy.
    After a database connection is established an experiments table can be
    created and populated in one of three ways:
    1. Reflect the table definition from an existing table. In this case the
    name of an existing table should be provided to `initialise`.
    2. Create a new table from a declarative table definition. In this case a
    `experiment_table` should be a reference to a class that extends
    experiment.ExperimentBase.
    3. Infer the table definition from locally stored dictionaries. If
    `experiment_table` is a local path reference the directory tree rooted at
    that path is traversed, looking for pickled dictionaries in `conf.pkl`
    files. The table definition is inferred from the dictionaries and the
    created table is populated automatically.

    In the third case above it is necessary to define primary key(s) for the
    table. If nothing is provided an `id` column is defined by default. Other
    column names can be provided by setting the `primary_keys` parameter,
    see doctest examples below.

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

    Infer table definition from a dictionary and auto populate the table
    >>> from pickle import dump
    >>> with open('experiments/EXP_1/conf.pkl', 'w') as fh_1,\
                open('experiments/EXP_2/conf.pkl', 'w') as fh_2,\
                open('experiments/EXP_3/conf.pkl', 'w') as fh_1:
    >>>     dump({'exp_id': 0, 'name': 'EXP_1', 'F1': .35}, fh_1)
    >>>     dump({'exp_id': 1, 'name': 'EXP_2', 'F1': .72}, fh_2)
    >>>     dump({'exp_id': 2, 'name': 'EXP_3', 'F1': .80}, fh_3)
    >>> from naklar import experiment
    >>> experiment.initialise('experiments', primary_keys=['exp_id'])
    >>> experiment.select()[0].exp_id
    0
    >>> experiment.select()[2].F1
    0.80

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


# class _Exp(ExperimentBase):
#     __mapper_args__ = {'column_prefix': '_'}
    # def __init__(self, **kwargs):
    #     for k, v in kwargs.iteritems():
    #         setattr(self, k, v)