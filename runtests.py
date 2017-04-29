#! /bin/sh
pip install pytest
py.test $@ --runsolr --runrabbit
