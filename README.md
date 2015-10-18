naklar [na'klaɐ̯]
======

Naklar is a support framework for managing experiments with a focus on staying out of the way and providing and easy way to select experiment(s) based on SQL style queries.


features
========
- easy-to-use and flexible database connectors based on `sqlalchemy`
- autoloading table contents from dictionaries stored on disk
- column value transformations during get/set operations using Python properties

dependencies
============
Naklar uses a data base to search / store and retrieve experiment results and depends on `sqlalchemy` and some data base backend.
- sqlalchemy
  - Under the hood naklar uses sqlalchemy to perform data base queries
- SQLite / MySQL / PyMysql
  - for accessing a data base
- six
    - for Py2/3 compatibility

usage
=====
    # load a settings.pkl pickled dictionaries from disk
    from naklar import experiment
    experiment.initialise('./results/', primary_keys=['job_id', 'task_id'],
                          autoload=True,
                          dict_filename='settings.pkl')

    # get all experiments
    experiment.select()

    # get only those where C=1
    # you need to know which parameters are present
    for exp in experiment.select(C=1)
        print(exp.C, exp.kernel, exp.path)

    # load joblib dumps
    from functools import partial
    from naklar import experiment
    import joblib

    load_func = partial(joblib.load, mmap_mode='r')
    experiment.initialise('./results/', primary_keys=['job_id', 'task_id'],
                          autoload=True, dict_filename='conf.joblib',
                          load_func=load_func)

    # only load certain keys if some of the values are not compatible with
    # sqlalchemy, for instance NumPy arrays
    from functools import partial
    from naklar import experiment
    import joblib

    # use memmap to avoid expensive unnecessary load operations
    load_func = partial(joblib.load, mmap_mode='r')
    experiment.initialise('./results/', primary_keys=['job_id', 'task_id'],
                        autoload=True, dict_filename='conf.joblib',
                        load_func=load_func,
                        restrict_keys=set(['alpha', 'eta', 'path']))

what's missing
==============
- an easy way to inspect parameters (the keys) for experiments
- ...
