from tests import common
from tests.fixtures import *

from tests.test_rendez_vous import add_free_creneaux
from analytics.manager import bootstrap, drop
from sief.permissions import POLICIES as p


class TestCreneau(common.BaseSolrTest):

    def test_creneau_ouvert(self, user, site_gu):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions.append(p.analytics.voir.name)
        user.save()
        bootstrap()
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_ouvert')
        assert r.data['hits'] == 0
        add_free_creneaux(15, site_gu)
        bootstrap()
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_ouvert')
        assert r.data['hits'] == 15
        add_free_creneaux(15, site_gu)
        bootstrap()
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_ouvert')
        assert r.data['hits'] == 30

    def test_creneau_supprime(self, user, site_gu):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions.extend([p.site.creneaux.gerer.name,
                                 p.site.sans_limite_site_affecte.name,
                                 p.analytics.voir.name])
        user.save()
        # First bootstrap
        bootstrap()
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_ouvert')
        assert r.data['hits'] == 0
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_supprime')
        assert r.data['hits'] == 0
        # Add 15 creneaux
        creneaux = add_free_creneaux(15, site_gu)
        bootstrap()
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_ouvert')
        assert r.data['hits'] == 15
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_supprime')
        assert r.data['hits'] == 0
        # Remove creneaux
        for creneau in creneaux:
            route = '/sites/{}/creneaux/{}'.format(site_gu.id, creneau.id)
            r = user_req.delete(route)
            assert r.status_code == 204
        bootstrap()
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_ouvert')
        assert r.data['hits'] == 15
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_supprime')
        assert r.data['hits'] == 15
        # Add 10 creaneaux and remove last created
        creneau = add_free_creneaux(10, site_gu)[-1]
        r = user_req.delete('/sites/{}/creneaux/{}'.format(site_gu.id, creneau.id))
        assert r.status_code == 204
        bootstrap()
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_ouvert')
        assert r.data['hits'] == 25
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_supprime')
        assert r.data['hits'] == 16


class TestCreneauInit(common.BaseSolrTest):

    def test_creneau(self, user, site_gu):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions.extend([p.site.creneaux.gerer.name,
                                 p.site.sans_limite_site_affecte.name,
                                 p.analytics.voir.name])
        user.save()
        # First bootstrap
        bootstrap()
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_ouvert')
        assert r.data['hits'] == 0
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_supprime')
        assert r.data['hits'] == 0
        # Add 15 creneaux
        creneaux = add_free_creneaux(15, site_gu)
        bootstrap()
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_ouvert')
        assert r.data['hits'] == 15
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_supprime')
        assert r.data['hits'] == 0
        # Remove creneaux
        for creneau in creneaux:
            route = '/sites/{}/creneaux/{}'.format(site_gu.id, creneau.id)
            r = user_req.delete(route)
            assert r.status_code == 204
        bootstrap()
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_ouvert')
        assert r.data['hits'] == 15
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_supprime')
        assert r.data['hits'] == 15
        # Clean Database
        drop()
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_ouvert')
        assert r.data['hits'] == 0
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_supprime')
        assert r.data['hits'] == 0
        # Bootstrap
        bootstrap()
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_ouvert')
        assert r.data['hits'] == 15
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_supprime')
        assert r.data['hits'] == 15
