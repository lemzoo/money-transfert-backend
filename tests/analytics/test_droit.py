from tests import common
from tests.fixtures import *

from analytics.manager import bootstrap
from datetime import datetime, timedelta
from sief.model import Droit
from sief.permissions import POLICIES as p

renouvellements_value = ['PREMIERE_DELIVRANCE', 'PREMIER_RENOUVELLEMENT',
                         'EN_RENOUVELLEMENT']


def create_droit(renouvellement, da_orientation, user):
    usager = da_orientation.usager
    droit = Droit(
        demande_origine=da_orientation,
        agent_createur=user,
        type_document='ATTESTATION_DEMANDE_ASILE',
        sous_type_document=renouvellement,
        usager=usager,
        date_fin_validite=datetime.utcnow() + timedelta(180),
        date_debut_validite=datetime.utcnow(),
        prefecture_rattachee=da_orientation.prefecture_rattachee
    ).save()
    return droit


def insert_attestation_demande_asile(count, user, da_orientation, renouvellement):
    droits = []
    for _ in range(count):
        d = create_droit(renouvellement, da_orientation, user)
        droits.append(d)
    return droits


class TestDroit(common.BaseSolrTest):

    def test_droit(self, user, da_orientation):
        user.permissions.append(p.analytics.voir.name)
        user.save()
        user_req = self.make_auth_request(user, user._raw_password)
        bootstrap()
        r = user_req.get('/analytics?fq=doc_type:droit_cree')
        assert r.data['hits'] == 0
        droits = insert_attestation_demande_asile(
            15, user, da_orientation, renouvellements_value[0])
        bootstrap()
        r = user_req.get('/analytics?fq=doc_type:droit_cree')
        assert r.data['hits'] == 15
        droits.extend(insert_attestation_demande_asile(
            15, user, da_orientation, renouvellements_value[1]))
        bootstrap()
        r = user_req.get('/analytics?fq=doc_type:droit_cree')
        assert r.data['hits'] == 30
        droits.extend(insert_attestation_demande_asile(
            15, user, da_orientation, renouvellements_value[2]))
        bootstrap()
        r = user_req.get('/analytics?fq=doc_type:droit_cree')
        assert r.data['hits'] == 45
        r = user_req.get('/analytics?fq=doc_type:droit_cree&fq=renouvellement_i:0')
        assert r.data['hits'] == 15
        r = user_req.get('/analytics?fq=doc_type:droit_cree&fq=renouvellement_i:1')
        assert r.data['hits'] == 15
        r = user_req.get('/analytics?fq=doc_type:droit_cree&fq=renouvellement_i:2')
        assert r.data['hits'] == 15
