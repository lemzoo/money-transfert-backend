import pytest
from datetime import datetime

from tests.fixtures import *
from tests.connector.common import Response, BrokerBox, MockRequests
from tests import common
from sief.events import EVENTS as e
from sief.permissions import POLICIES as p
from sief.model import DemandeAsile, Utilisateur


DATE_MAJ = datetime.utcnow().strftime("%Y%m%d")


@pytest.fixture
def usager_agdref(request, usager):
    usager.identifiant_agdref = '0123456789'
    usager.save()
    return usager


def utilisateur_agdref():
    new_user = Utilisateur.objects(email='agdref@test.com').first()
    if not new_user:
        new_user = Utilisateur(nom='Connector', prenom='Agdref', email='agdref@test.com')
        new_user.controller.init_basic_auth()
        new_user.controller.set_password('P@ssw0rd')
        new_user.permissions = []
        set_user_accreditation(new_user, role='SYSTEME_AGDREF')
        new_user.save()
    new_user._raw_password = 'P@ssw0rd'
    return new_user


class TestAGDREFConnectorSolr(common.BaseSolrTest):

    @classmethod
    def setup_class(cls):
        cls.mock_requests = MockRequests()
        super().setup_class(config={
            'CONNECTOR_AGDREF_REQUESTS': cls.mock_requests,
            'DISABLE_EVENTS': False
        })

    def setup_method(self, method):
        # Clean broker data
        self.app.extensions['broker'].model.Message.objects.delete()
        self.app.extensions['broker'].model.QueueManifest.objects.delete()
        super().setup_method(method)
        self.callbacks = []

    def callback(self, *args, **kwargs):
        current_callback = self.callbacks.pop()
        ret = current_callback(*args, **kwargs)
        return ret

    def callback_get_usager_backend(self, method, url, data=None, headers=None, **kwargs):
        user = utilisateur_agdref()
        user_req = self.make_auth_request(user, user._raw_password)
        assert method == 'GET'
        assert url.startswith(self.app.config['BACKEND_URL'] + '/recueils_da')
        route = '/recueils_da?%s' % url.rsplit('?', 1)[1]
        ret = user_req.get(route)
        return Response(ret.status_code, json=ret.data)

    def callback_get_demandes_asile(self, method, url, data=None, headers=None, **kwargs):
        user = utilisateur_agdref()
        user_req = self.make_auth_request(user, user._raw_password)
        assert method == 'GET'
        assert url.startswith(self.app.config['BACKEND_URL'] + '/demandes_asile')
        route = '/demandes_asile?%s' % url.rsplit('?', 1)[1]
        ret = user_req.get(route)
        return Response(ret.status_code, json=ret.data)

    def callback_get_backend(self, method, url, data=None, headers=None, **kwargs):
        user = utilisateur_agdref()
        user_req = self.make_auth_request(user, user._raw_password)
        assert method == 'GET'
        assert url.startswith(self.app.config['BACKEND_URL'] + '/sites')
        ret = user_req.get('/sites/%s' % url.rsplit('/', 1)[1])
        return Response(ret.status_code, json=ret.data)


class TestAGDREFConnector(common.BaseLegacyBrokerTest):

    @classmethod
    def setup_class(cls):
        cls.mock_requests = MockRequests()
        super().setup_class(config={
            'CONNECTOR_AGDREF_REQUESTS': cls.mock_requests,
        })

    def setup_method(self, method):
        # Clean broker data
        self.app.extensions['broker'].model.Message.objects.delete()
        self.app.extensions['broker'].model.QueueManifest.objects.delete()
        super().setup_method(method)

    def callback_get_backend(self, method, url, data=None, headers=None, **kwargs):
        user = utilisateur_agdref()
        user_req = self.make_auth_request(user, user._raw_password)
        assert method == 'GET'
        assert url.startswith(self.app.config['BACKEND_URL'] + '/sites')
        ret = user_req.get('/sites/%s' % url.rsplit('/', 1)[1])
        return Response(ret.status_code, json=ret.data)
