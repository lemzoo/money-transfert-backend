.. _tests:

Tests
-----

The project's tests use `pytest <http://pytest.org>`_, it is provided as
standalone to easily run tests ::

    ./runtests.py tests

By default, test involving Solr are skipped, to avoid this run ::

    ./runtests.py tests --runsolr

In case some code has been changed, it's a good practice to run flake8 on it ::

    flake8 .
