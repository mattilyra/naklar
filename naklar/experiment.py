import os
import re
try:
    import cPickle as pickle
except ImportError:
    import pickle

from sqlalchemy import create_engine, Column, Integer, String, DateTime, func,\
    Float, Enum
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.attributes import InstrumentedAttribute


_engine = create_engine('sqlite:///:memory:', echo=False)
Base = declarative_base()


def load_experiments(root_dir, engine=None):
    if engine == None:
        engine = _engine
    session = Session(bind=engine)
    cols = Experiment.__table__.columns.keys()
    exp_count = 0
    for root, _, files in os.walk(root_dir, topdown=False):
        if 'settings.pkl' in files:
            models = [h5 for h5 in os.listdir(root) if h5.endswith('.h5')]
            with open(os.path.join(root, 'settings.pkl'), 'rb') as fin:
                d = pickle.load(fin)
                d = {k: v for k, v in d.iteritems() if k in cols}

            # with open(os.path.join(root, 'SGE.txt'), 'r') as fin:
            #     for line in fin:
            #         k, _, v = line.partition(' ')
            #         if k in ['JOB_ID', 'TASK_ID', 'ITERATION']:
            #             d.update({k.lower(): int(v)})

            job_id, task_id = os.path.basename(root).split('_')
            d.update({'job_id': int(job_id), 'task_id': int(task_id)})

            # modify the results file path so that they become relative to
            # the root_dir on the current file system
            d.update({'home': os.path.abspath(root)})

            for model in models:
                model_name, _, _ = model.partition('.')
                ensemble_type, _, model_type = model_name.partition('_')
                d.update({'model_type': model_type})
                d.update({'ensemble_type': ensemble_type})
                d.update({'results_file': model})
                d.update({'index_file': '%s.idx.npz' % model_name})

                exp = Experiment(**d)
                session.add(exp)
                exp_count += 1
    
    print('Loaded {0} experiments'.format(exp_count))
    session.commit()
    session.close()

    session = Session(bind=engine)
    return session


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
    >> rows = retrieve(session, k=2)

    Retrieve specific columns from Experiments where Experiment.k == 2

    >> session = load_experiments('.')
    >> rows = retrieve(session, 'model_type', 'results_file', k=2)

    >> session = load_experiments('.')
    >> rows = retrieve(session, 'model_type', 'results_file', k=[1, 2, 3, 5, 8])
    """
    if columns:
        cols = []
        for col in columns:
            if isinstance(col, (str, unicode)):
                cols.append(getattr(Experiment, col))
            elif isinstance(col, InstrumentedAttribute):
                cols.append(col)
    else:
        cols = [Experiment]

    q = session.query(*cols)

    if filters:
        filts = []
        for k, v in filters.iteritems():
            if hasattr(v, 'split'):
                filts.append(getattr(Experiment, k) == v)
            elif hasattr(v, '__getitem__') or hasattr(v, '__iter__'):
                filts.append(getattr(Experiment, k).in_(v))
            else:
                filts.append(getattr(Experiment, k) == v)
        q = q.filter(*filts)
    rows = q.all()
    return rows


class Experiment(Base):
    """The Experiment class holds references to settings of an experiment.
    """

    __tablename__ = 'experiment'

    id = Column(Integer, primary_key=True)

    job_id = Column(Integer, default=0)
    task_id = Column(Integer, default=0)
    stream_id = Column(String, default='')
    iteration = Column(Integer)

    experiment = Column(String)
    datahome = Column(String)
    logfile = Column(String)
    home = Column(String)

    seed = Column(Integer)
    distance_metric = Column(String, default='l2')
    min_freq = Column(Float)
    max_freq = Column(Float)
    k = Column(Integer)
    num_documents = Column(Integer)
    train_ratio = Column(Float)
    eval_ratio = Column(Float)
    update_window_end = Column(Integer)
    update_window_interval = Column(Integer)

    model_type = Column(String)
    ensemble_type = Column(String)
    results_file = Column(String)
    index_file = Column(String)

    started_at = Column(DateTime, default=func.now())
    finished_at = Column(DateTime, default=func.now())


Base.metadata.create_all(_engine)
