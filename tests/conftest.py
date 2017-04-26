import pytest


def pytest_addoption(parser):
    parser.addoption("--runsolr", action="store_true", help="run solr tests")
    parser.addoption("--runrabbit", action="store_true", help="run RabbitMQ tests")
    parser.addoption("--event-everywhere", action="store_true",
                     help="generate broker events for all test")
    parser.addoption("--solr-everywhere", action="store_true",
                     help="run solr for all test (really slow !)")


def pytest_runtest_setup(item):
    if 'solr' in item.keywords and not item.config.getoption("--runsolr"):
        pytest.skip("need --runsolr option to run")
    if 'rabbit' in item.keywords and not item.config.getoption("--runrabbit"):
        pytest.skip("need --runrabbit option to run")
