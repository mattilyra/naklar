naklar [na'klaɐ̯]
======

Naklar is a support framework for managing experiments with a focus on staying out of the way and providing and easy way to select experiment(s) based on SQL style queries.


features
========
- easy-to-use and flexible database connectors based on sqlalchemy
- autoloading table contents from dictionaries stored on disk
- columns value transformations during get/set operations using Python properties

dependencies
============
Naklar uses a data base to search / store and retrieve experiment results and depends on `sqlalchemy` and some data base backend.
- sqlalchemy
  - Under the hood naklar uses sqlalchemy to perform data base queries
- SQLite / MySQL / PyMysql
  - for accessing a data base
- six
    - for Py2/3 compatibility
