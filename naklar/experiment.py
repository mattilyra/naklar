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

            with open(os.path.join(root, 'SGE.txt'), 'r') as fin:
                for line in fin:
                    k, _, v = line.partition(' ')
                    if k in ['JOB_ID', 'TASK_ID', 'ITERATION']:
                        d.update({k.lower(): int(v)})

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
