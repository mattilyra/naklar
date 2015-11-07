import sys
import os
from os import path
import re
import glob
import types
import functools
import collections
try:
    import cPickle as pickle
except ImportError:
    import pickle

from sqlalchemy import create_engine, func
from sqlalchemy import Column, Integer, String, DateTime, Float, MetaData, \
    Table, Boolean
from sqlalchemy.sql.elements import BinaryExpression
from sqlalchemy.orm import Session, mapper
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.ext.declarative import declarative_base, DeferredReflection
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy.ext.hybrid import hybrid_property

import six

_engine = None
_ExperimentBase = declarative_base(cls=DeferredReflection)

DEFAULT_TABLENAME = 'experiment'
DEFAULT_COLUMN_PREFIX = '_'


def _E_iterator(self):
    for p in self.__mapper__.iterate_properties:
        yield (p.expression.key, getattr(self, p.expression.key))


def _E_getitem(self, attr):
    if hasattr(self, attr):
        return getattr(self, attr)
    else:
        raise AttributeError('{} does not have attribute {}'.format(self, attr))


def _from_existing_db(tablename):
    try:
        _ExperimentBase.__tablename__ = tablename
        _ExperimentBase.__table_args__ = {'autoload': True}
        _ExperimentBase.prepare(_engine)
    except NoSuchTableError:
        raise NoSuchTableError('Table \'{}\' does not exists in database.'
                               .format(tablename))
    return _ExperimentBase


def _decorate_function(f, f_code, d, key):
    if callable(f):
        if isinstance(f, functools.partial):
            fname = f.func.__name__
        else:
            fname = f.__name__

        # fname = '_{}'.format(fname)
        # mod = sys.modules[globals()['__name__']]
        # setattr(mod, fname, f)

        exec(f_code.format(key, fname), {}, d)
        print(fname in globals())
        d[fname] = f
        print(d)
    else:
        exec(f_code.format(key, None), {}, d)

    return d


def _find_conf_files(root_dir, dict_filename='conf.pkl'):
    for root, _, files in os.walk(root_dir, topdown=False):
        if dict_filename in files:
            pth = os.path.join(root, dict_filename)
            with open(pth, 'r') as fh:
                yield fh


def _read_conf_dicts(itr):
    for fh in itr:
        d = pickle.load(fh)
        yield d


def _bind_get(prop_name, f=None):
    def _get(self):
        v = getattr(self, '_{}'.format(prop_name))
        if callable(f):
            v = f(self, v)
        return v
    _get.__name__ = '_get_{}'.format(prop_name)
    return _get


def _bind_set(prop_name, f=None):
    def _set(self, v):
        if callable(f):
            v = f(self, v)
        setattr(self, '_{}'.format(prop_name), v)
    _set.__name__ = '_set_{}'.format(prop_name)
    return _set


def _load_conf(pth, load_func=None):
    try:
        if callable(load_func):
            d = load_func(pth)
        else:
            with open(pth, 'rb') as fh:
                d = pickle.load(fh)
    except EOFError:
        print(pth)
        raise
    return d


def _conf_from_files(files, restrict_keys=None, **kwargs):
    conf = {}
    for num_dicts, pth in enumerate(files):
        d = _load_conf(pth, **kwargs)
        keys = d.keys()
        if restrict_keys is not None:
            keys = keys & restrict_keys

        # from each configuration file update all keys into conf overwriting
        # None values from previously loaded confs
        # TODO: conf[k] should be a list to support enumerating all values found - consider cases where alpha \in {'auto', 'symmetric', .1, .01}
        for k in keys:
            v = d[k]
            if k in conf and (conf[k] is None and v is not None):
                conf[k] = v
            elif k not in conf:
                conf[k] = v

    if num_dicts == 0:
        msg = ('Did not find any files matching {} from {}. Table'
                'definition can not be created.'.format(dict_file, root_dir))
        raise RuntimeError(msg)

    return conf

def _create_table_definition(table_properties, conf, primary_keys=None):
    # global TABLE_PROPERTIES_
    # TABLE_PROPERTIES_ = {k:v for k, v in six.viewitems(_TABLE_PROP_TEMPLATE_)}
    if primary_keys is None:
        primary_keys = ['id']

    if '__tablename__' not in table_properties:
        table_properties['__tablename__'] = DEFAULT_TABLENAME

    if '__mapper_args__' not in table_properties:
        table_properties['__mapper_args__'] =\
            {'column_prefix': DEFAULT_COLUMN_PREFIX}

    sql_types = [DateTime, Float, Integer, Boolean, String]
    for k, v in six.iteritems(conf):
        for column_type in sql_types:
            if column_type().python_type is type(v):
                if hasattr(v, 'split'):
                    column_type = String(len(v) * 2)
                break

        column = Column(k, column_type, primary_key=k in primary_keys)
        attrname = '_{}'.format(k)
        table_properties[attrname] = column

    # if the conf dictionary does not contain all of the primary key columns
    # add the ones that are missing - this ensures that if no primary_keys
    # are defined at least a default id integer column is created
    if not all(['_{}'.format(k) in table_properties for k in primary_keys]):
        for k in primary_keys:
            attrname = '_{}'.format(k)
            if attrname not in table_properties:
                column = Column(k, Integer, primary_key=True)
                table_properties[attrname] = column
                conf[k] = None

    return table_properties


def add_decorators(functions, decorators=None, TABLE_DEF=None):
    if not decorators:
        decorators = []

    for k in functions:
        funcs = functions[k]
        if not funcs:
            g = _bind_get(k) # no-op default getter
            s = _bind_set(k) # no-op default setter
            prop = hybrid_property(g, s, None, None)
        elif len(funcs) == 1:
            g, = funcs
            g = _bind_get(k, g)
            s = _bind_set(k) # no-op default setter
            prop = hybrid_property(g, s, None, None)
        elif len(funcs) == 2:
            g, s = funcs
            g = _bind_get(k, g)
            s = _bind_set(k, s)
            prop = hybrid_property(g, s, None, None)
        elif len(funcs) == 3:
            g, s, column = funcs
            g = _bind_get(k, g)
            s = _bind_set(k, s)
            prop = hybrid_property(g, s, None, None)
            TABLE_DEF['_{}'.format(k)] = column
        else:
            raise ValueError('There should be exactly 2 decorator methods '
                             'provided for key \'{}\', found {}. The '
                             'method tuple should contain (getter, '
                             'setter).'.format(k, len(funcs)))
        decorators.append((k, prop))
    return decorators, TABLE_DEF

def find_files(root_dir, filename='conf.pkl'):
    """A generator over files called `filename` in any subdirectory of root.
    """
    if not os.path.exists(root_dir):
        raise ValueError('Directory {} does not exist.'.format(root_dir))

    root_dir = os.path.expandvars(root_dir)
    root_dir = os.path.abspath(os.path.expanduser(root_dir))
    for root, _, files in os.walk(root_dir, topdown=False):
        for f in files:
            if filename == f:
                pth = os.path.join(root, f)
                pth = os.path.abspath(pth)
                yield pth
                break


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


def initialise(files=None, root_dir=None, table_name=None,
               dict_file='conf.pickle', decorators=None, autoload=True,
               load_func=None, restrict_keys=None,
               *args, **kwargs):
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

    if files is None and root_dir is None:
        raise RuntimeError('Either files or root_dir must be set.')

    global E

    # CREATE A NEW DATABASE TABLE
    if files is None:
        files = find_files(root_dir, filename=dict_file)

    conf = _conf_from_files(files, load_func=load_func,
                            restrict_keys=restrict_keys)
    table = {}
    if table_name is not None:
        table = {'__tablename__': table_name}

    table_properties = _create_table_definition(table, conf, **kwargs)

    # create getter and setter methods for each key loaded from disk
    # NOTE these are explicitly for the conf keys only
    keys_ = conf.keys() - decorators.keys()
    decorators_, _ = add_decorators({k: None for k in keys_})
    decorators_, table_properties = add_decorators(decorators,
                                                   decorators=decorators_,
                                                   TABLE_DEF=table_properties)
    print(table_properties)
    # create a runtime class Exp that is going to be the experiment table
    # definition for sqlalchemy
    Exp = type('Exp', (_ExperimentBase,), table_properties)
    for k, prop in decorators_:
        setattr(Exp, k, prop)
    Exp.metadata.create_all(_engine)
    Exp.prepare(_engine)

    if autoload:
        E = Exp
        populate_from_disk(files, **kwargs)

    # REFLECT EXISTING DATABASE
    elif table_name is not None:
        raise NotImplementedError('Reflecting existing DB not supported yet.')
        if isinstance(table_name, six.string_types):
            # connect to a data base that contains the experiments table
            # and infer the Experiment class via reflection
            E = _from_existing_db(table_name)
        elif _ExperimentBase in table_name.__bases__:
            # connect to a database and create a new table
            experiment_table.metadata.create_all(_engine)
            _ExperimentBase.prepare(_engine)
            E = experiment_table
        else:
            raise ValueError('Experiment class must extend '
                             'naklar.experiment.ExperimentBase or be the name '
                             'of an existing table.')

    E.__iter__ = _E_iterator
    E.__getitem__ = _E_getitem


def populate_from_disk(files, load_func=None):
    session = Session(bind=_engine)
    for found_dicts, pth in enumerate(files):
        if load_func is None:
            with open(pth, 'rb') as fh:
                conf = pickle.load(fh)
        else:
            conf = load_func(pth)

        # in order for the set decorators to work correctly the values of
        # of the experiment object have to be set explicitly
        exp = E()
        for k, v in six.iteritems(conf):
            if isinstance(v, collections.Container):
                v = str(v)
            setattr(exp, k, v)
        session.add(exp)
    if found_dicts == 0:
        raise Warning('Did not find files matching {} from {}'
                      ''.format(dict_file, root_dir))
    session.commit()
    session.close()


def select(*columns, **filters):
    """Get rows from the Experiment table associated with session.

    Parameters
    ----------
    session : Session

    *columns : str or InstrumentedAttribute, optional
        Optional parameters to retrieve only specific column values
        from the Experiment table. If none are specified the whole
        Experiment object is returned.

    **filters
        Optional keys to filter the returned Experiments by.

    Returns
    -------
    list
        A list of Experiment objects or KeyedTuples.


    See Also
    --------
    sqlalchemy.orm.session.Session,
    sqlalchemy.orm.attributes.InstrumentedAttribute,
    sqlalchemy.util._collections.KeyedTuple

    Retrieve all Experiments where Experiment.k == 2

    >> initialise('.')
    >> rows = select(k=2)

    Retrieve specific columns from Experiments where Experiment.k == 2

    >> initialise('.')
    >> rows = select('model_type', 'results_file', k=2)

    >> initialise('.')
    >> rows = select('model_type', 'results_file', k=[1, 2, 3, 5, 8])
    """
    cols, filts = [], []
    if columns:
        for col in columns:
            if isinstance(col, six.string_types):
                cols.append(getattr(E, col))
            elif isinstance(col, InstrumentedAttribute):
                cols.append(col)
            elif isinstance(col, BinaryExpression):
                filts.append(col)

    if not cols: # in case all *args were BinaryExpression (filters)
        cols = [E]

    session = Session(bind=_engine)
    q = session.query(*cols)

    if filters or filts:
        for k, v in six.iteritems(filters):
            if isinstance(v, BinaryExpression):
                filts.append(v)
            elif hasattr(v, 'split'):
                filts.append(getattr(E, k) == v)
            elif hasattr(v, '__getitem__') or hasattr(v, '__iter__'):
                filts.append(getattr(E, k).in_(v))
            else:
                filts.append(getattr(E, k) == v)
        q = q.filter(*filts)
    rows = q.all()
    session.close()
    return rows


def reset():
    try:
        _engine.dispose()
        E.metadata.clear()
    except AttributeError:
        pass

    connect()
    TABLE_PROPERTIES_ = {}
    global _ExperimentBase
    _ExperimentBase = declarative_base(cls=DeferredReflection)


def show_params(experiments=None, as_pandas=False):
    """Show all keys and their values for experiments.

    Returns
    --------
        A list of dictionaries or a Pandas `DataFrame` if `as_pandas=True`.
    """
    if experiments is None:
        experiments = select()

    rows = []
    for exp in experiments:
        rows.append({k: v for k, v in exp})

    if as_pandas:
        import pandas as pd
        df = pd.DataFrame(rows)
        return df

    return rows
