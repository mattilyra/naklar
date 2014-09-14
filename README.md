naklar
======

Naklar is a support framework for managing experiments with a focus on staying out of the way and providing and easy way to select experiment(s) based on SQL style queries.


dependencies
============
Naklar uses a data base to search / store and retrieve experiment results and depends on `sqlalchemy` and some data base backend.
- sqlalchemy
  - Under the hood naklar uses sqlalchemy to perform data base queries
- SQLite / MySQL / PyMysql
  - for accessing a data base 
