import json

from tests import common
from tests.test_auth import user
from tests.broker.fixtures import *

from broker import Broker


class TestBroker(common.BaseLegacyBrokerTest):

    @pytest.mark.xfail(reason='Check the index on codeship')
    def test_ensure_indexes(self, app, default_handler):
        expected_queue_manifest_indexes = {
            '_id_': {'key': [('_id', 1)], 'v': 1},
            'status_1': {
                'background': False,
                'dropDups': False,
                'key': [('status', 1)],
                'v': 1
            }
        }
        expected_message_indexes = {
            '_id_': {'key': [('_id', 1)], 'v': 1},
            'created_1': {
                'background': False,
                'dropDups': False,
                'key': [('created', 1)],
                'v': 1
            },
            'queue_1': {
                'background': False,
                'dropDups': False,
                'key': [('queue', 1)],
                'v': 1
            },
            'status_1': {
                'background': False,
                'dropDups': False,
                'key': [('status', 1)],
                'v': 1
            },
            'queue_1_status_1_created_1': {
                'background': False,
                'dropDups': False,
                'key': [('queue', 1), ('status', 1), ('created', 1)],
                'v': 1
            }
        }
        # Clean the broker database of all indexes
        from pymongo import MongoClient
        c = MongoClient(host=get_broker_legacy_db_url())
        db = c.get_default_database()
        common.assert_indexes(db.queue_manifest, {})
        common.assert_indexes(db.message, {})
        # Now initialize the broker
        broker = Broker()
        event_handler = EventHandler([default_handler])
        broker.init_app(app, event_handler)
        # Make sure indexes are created during broker init
        queue_cls = broker.model.QueueManifest
        assert queue_cls.list_indexes() == [[('status', 1)], [('_id', 1)]]
        common.assert_indexes(db.queue_manifest,
                              expected_queue_manifest_indexes)
        assert app.extensions['broker'].model.Message.list_indexes() == [
            [('queue', 1)], [('created', 1)], [('status', 1)],
            [('queue', 1), ('status', 1), ('created', 1)], [('_id', 1)]]
        common.assert_indexes(db.message, expected_message_indexes)

        # Now drop collections, indexes should be gone as well
        app.extensions['broker'].model.Message.drop_collection()
        queue_cls.drop_collection()
        common.assert_indexes(db.queue_manifest, {})
        common.assert_indexes(db.message, {})

        # Inserting objects should recreate the indexes
        queue_cls(queue='test').save()
        common.assert_indexes(db.queue_manifest, expected_queue_manifest_indexes)

        broker.event_handler.flush()
        eh = EventHandlerItem({'label': 'test-handler',
                               'event': 'event-test',
                               'queue': 'test'})
        broker.event_handler.append(eh)
        app.extensions['broker'].model.Message(queue='test', handler='test-handler').save()
        common.assert_indexes(db.message, expected_message_indexes)

    def test_send_event(self, broker, event_handler_item, message_dump):
        # Now an interesting event
        broker.send(message_dump)
        msgs = broker.model.Message.objects()
        assert msgs.count() == 1
        msg = msgs[0]
        handler = broker.event_handler.get(msg.handler)
        assert handler == event_handler_item
        assert msg.queue == event_handler_item.queue
        assert msg.status == 'READY'
        assert msg.context == json.loads(message_dump['json_context'])
        assert msg.created
        assert msg.origin == 'my-origin'


class TestOnError(common.BaseLegacyBrokerTest):

    def test_unknown_processor_cancel_on_error(self, event_handler_item, broker, user, message_dump):
        from sief.event_handler import canceled_message_and_send_mail
        from sief.permissions import POLICIES as p
        from sief.tasks.email import mail

        user.permissions = [p.utilisateur.creer.name,
                            p.utilisateur.modifier.name]
        user.test_set_accreditation(role='ADMINISTRATEUR_NATIONAL')
        user.save()

        with mail.record_messages() as outbox:
            event_handler_item.modify(processor='unknown_processor')
            event_handler_item.on_error_callback = canceled_message_and_send_mail
            broker.send(message_dump)
            msg = broker.model.Message.objects.first()
            handler = broker.event_handler.get(msg.handler)
            assert handler == event_handler_item
            assert msg.status == 'READY'
            broker.event_handler.execute_legacy(msg)
            msg.reload()
            assert msg.status == 'CANCELLED'
            assert len(outbox) == 1
            assert user.email in outbox[0].recipients
