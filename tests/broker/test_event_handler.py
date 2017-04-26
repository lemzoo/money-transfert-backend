import pytest

from tests import common
from tests.broker.fixtures import *


@pytest.fixture
def handlers(request, broker):
    event = DEFAULT_EVENTS[0]
    for eh in [
        {'label': "test-evt-handler1", 'queue': "test-queue",
         'event': event, 'origin': 'john.doe@test.com',
         'processor': 'webhook',
         'context': {'test': 42, 'test2': 'test-string',
                     'test3': {'test_embeded': (1, 2, 3)}}},
        {'label': "test-evt-handler2", 'queue': "test-queue",
         'event': event, 'origin': 'john.doe@test.com',
         'processor': 'webhook',
         'context': {'test': 42, 'test2': 'test-string',
                     'test3': {'test_embeded': (1, 2, 3)}}},
        {'label': "test-evt-handler3", 'queue': "test-queue",
         'event': event, 'origin': 'john.doe@test.com',
         'processor': 'webhook',
         'context': {'test': 42, 'test2': 'test-string',
                     'test3': {'test_embeded': (1, 2, 3)}}}
        ]:
        broker.event_handler.append(eh)

    return broker.event_handler._items
