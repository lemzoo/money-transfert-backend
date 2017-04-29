from tests import common
from tests.fixtures import *

from datetime import datetime, timedelta

from sief.model.recueil_da import RecueilDA
from sief.permissions import POLICIES as p


class TestExportRecueil(common.BaseSolrTest):

    def test_export_recueil(self, user, site_structure_accueil):
        user_req = self.make_auth_request(user, user._raw_password)
        user.site_affecte = site_structure_accueil
        user.permissions = [p.recueil_da.voir.name, p.recueil_da.export.name]
        user.save()

        # Step 1 : Start by creating 25 recueils (Brouillon)
        date_from = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        for _ in range(0, 25):
            recueil = RecueilDA(structure_accueil=site_structure_accueil,
                                agent_accueil=user)
            recueil.save()
        date_to_1 = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)

        route = '/recueils_da/export?fq=doc_created:[%s TO %s]&per_page=20&page=1' % (
            date_from, date_to_1)
        r = user_req.get(route)
        assert r.status_code == 200, r
        next_route = '/recueils_da/export?q=*:*&fq=doc_created:[%s TO %s]&per_page=20&page=2' % (
            date_from, date_to_1)
        assert r.data['_links'].get('next', None) == next_route
        assert r.data['_meta']['total'] == 25

        route = '/recueils_da/export?fq=doc_created:[%s TO %s]&page=2&per_page=20' % (
            date_from, date_to_1)
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['_links'].get('next', None) is None
        assert r.data['_meta']['total'] == 25

        # Step 2 : Create 25 new recueils (Brouillon)
        for _ in range(0, 25):
            recueil = RecueilDA(structure_accueil=site_structure_accueil,
                                agent_accueil=user)
            recueil.save()
        date_to_2 = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)

        route = '/recueils_da/export?fq=doc_created:[%s TO %s]&per_page=100' % (
            date_from, date_to_1)
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['_links'].get('next', None) is None
        assert r.data['_meta']['total'] == 25

        route = '/recueils_da/export?fq=doc_created:[%s TO %s]&per_page=100' % (
            date_from, date_to_2)
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['_links'].get('next', None) is None
        assert r.data['_meta']['total'] == 50

        route = '/recueils_da/export'
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['_links'].get('next', None) == '/recueils_da/export?per_page=20&page=2'
        assert r.data['_meta']['total'] == 50
