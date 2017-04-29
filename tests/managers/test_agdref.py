#!/usr/bin/python

import pytest
import json

from tests.fixtures import *
from tests import common
from sief.model.site import Prefecture, GU
from sief.model.fields import AddressEmbeddedDocument
from broker.model import Message
from sief.managers.agdref_manager import delete_gu_loader_messages, mark_messages_as_deleted


@pytest.fixture
def prefecture(request):
    prefecture = Prefecture(libelle='PrefectureTest', code_departement='000',
                            adresse=AddressEmbeddedDocument(adresse_inconnue=True)).save()

    def finalizer():
        prefecture.delete()
    request.addfinalizer(finalizer)
    return prefecture


@pytest.fixture
def gu_loader(request, prefecture):
    gu = GU(libelle='loader-GU', autorite_rattachement=prefecture,
            adresse=AddressEmbeddedDocument(adresse_inconnue=True)).save()

    def finalizer():
        gu.delete()
    request.addfinalizer(finalizer)
    return gu


class TestAgdref(common.BaseLegacyBrokerTest):
    def test_delete_cancelled_messages(self, gu_loader):
        # Context that follows demande_asile format
        ctx1 = {
            "demande_asile": {
                "structure_guichet_unique": {
                    "id": str(gu_loader.id)
                }
            }
        }
        # Context with structure_guichet_unique at an arbitrary position
        ctx2 = {
            "a": "b",
            "c": {
                "d": "e",
                "structure_guichet_unique": {
                    "id": str(gu_loader.id)
                }
            }
        }
        # Context with structure_guichet_unique in a list
        ctx3 = {
            "a": [
                "b", "c", {
                    "structure_guichet_unique": {
                        "id": str(gu_loader.id)
                    }
                }
            ]
        }

        # Context with loader-GU id at an arbitrary position
        ctx4 = {
            "a": [{
                "b": "c"
            }, {
                "d": str(gu_loader.id)
            }]
        }

        dumped_ctx1 = json.dumps(ctx1)
        dumped_ctx2 = json.dumps(ctx2)
        dumped_ctx3 = json.dumps(ctx3)
        dumped_ctx4 = json.dumps(ctx4)

        msg_list = []
        # Should be set to DELETED
        msg_list.append(Message(queue='agdref',
                           handler='agdref-demande_asile.cree',
                           status='CANCELLED',
                           json_context=dumped_ctx1))
        # Should not be set to DELETED (status is not CANCELLED)
        msg_list.append(Message(queue='agdref',
                                handler='agdref-demande_asile.cree',
                                status='READY',
                                json_context=dumped_ctx1))
        # Should not be set to DELETED (queue is not agdref)
        msg_list.append(Message(queue='inerec',
                                handler='agdref-demande_asile.cree',
                                status='CANCELLED',
                                json_context=dumped_ctx1))
        # Should be set to DELETED
        msg_list.append(Message(queue='agdref',
                                handler='agdref-demande_asile.decision_definitive',
                                status='CANCELLED',
                                json_context=dumped_ctx2))
        # Should be set to DELETED
        msg_list.append(Message(queue='agdref',
                                handler='agdref-demande_asile.decision_definitive',
                                status='CANCELLED',
                                json_context=dumped_ctx3))

        prefecture_id = str(Prefecture.objects(libelle='PrefectureTest').first().id)
        ctx1['demande_asile']['structure_guichet_unique']['id'] = prefecture_id
        # Should not be set to DELETED (structure_guichet_unique id is not loader-GU's)
        msg_list.append(Message(queue='agdref',
                                handler='agdref-demande_asile.cree',
                                status='CANCELLED',
                                json_context=json.dumps(ctx1)))

        # Should be set to DELETED
        msg_list.append(Message(queue='agdref',
                                handler='agdref-usager.etat_civil.valide',
                                status='CANCELLED',
                                json_context=dumped_ctx4))

        for msg in msg_list:
            msg.save()

        delete_gu_loader_messages()

        assert Message.objects(status='DELETED').count() == 4
        assert all(m.id in (msg_list[0].id, msg_list[3].id, msg_list[4].id, msg_list[6].id)
                   for m in Message.objects(status='DELETED'))
        assert Message.objects(status='READY').count() == 1
        assert Message.objects(status='CANCELLED').count() == 2

        for msg in msg_list:
            msg.delete()

    def test_delete_cancelled_specific_messages(self):
        msg_list = []
        # Change status to DELETED
        msg_list.append(Message(queue='agdref', status='CANCELLED', handler='ignored',
                                json_context='{}'))
        # Do nothing (queue is inerec)
        msg_list.append(Message(queue='inerec', status='CANCELLED', handler='ignored',
                                json_context='{}'))
        # Do nothing (status is READY)
        msg_list.append(Message(queue='agdref', status='READY', handler='ignored',
                                json_context='{}'))

        for msg in msg_list:
            msg.save()

        mark_messages_as_deleted([msg.id for msg in msg_list])

        assert Message.objects(status='DELETED').count() == 1
        assert Message.objects(status__ne='DELETED').count() == 2
        assert Message.objects(status='DELETED').first().id == msg_list[0].id

        for msg in msg_list:
            msg.delete()

    def test_delete_cancelled_messages_from_recueil(self, gu_loader, pa_realise, da_orientation,
                                                    usager):
        da_orientation.recueil_da_origine = pa_realise
        da_orientation.usager = usager
        pa_realise.structure_guichet_unique = gu_loader
        da_orientation.save()
        pa_realise.save()
        msg = Message(queue='agdref', status='CANCELLED', handler='ignored',
                      json_context='{"usager": {"id": "' + str(usager.id) + '"}}')
        msg.save()
        delete_gu_loader_messages()
        msg.reload()
        assert msg.status == 'DELETED'
        msg.delete()
