import os
import re
try:
    import cPickle as pickle
except ImportError:
    import pickle

from sqlalchemy import create_engine, Column, Integer, String, DateTime, func,\
    Text
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm.attributes import InstrumentedAttribute


# _engine = create_engine('sqlite:///:memory:', echo=False)

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
                cols.append(getattr(experiment_cls_, col))
            elif isinstance(col, InstrumentedAttribute):
                cols.append(col)
    else:
        cols = [experiment_cls_]

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
    return rows


class _Experiment(object):
    """The Experiment class holds references to settings of an experiment.
    """
    @declared_attr
    def __tablename__(cls):
        return 'experiment'

    id = Column(Integer, primary_key=True)
    experiment_name = Column(String(255))
    experiment_comment = Column(Text(65535))
    home = Column(String(255))
    started_at = Column(DateTime, default=func.now())
    finished_at = Column(DateTime, default=func.now())

ExperimentBase = declarative_base(cls=_Experiment)

# the default experiment claass is ExperimentBase, this can be overridden by
# passing another experiment class to naklar.initialise
experiment_cls_ = ExperimentBase