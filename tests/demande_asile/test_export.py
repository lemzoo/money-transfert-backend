from tests import common
from tests.fixtures import *

from datetime import datetime, timedelta

from sief.model.demande_asile import DemandeAsile
from sief.permissions import POLICIES as p


class TestExportDemandeAsile(common.BaseSolrTest):

    def test_export_da(self, user_with_site_affecte, da_orientation_payload):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name, p.demande_asile.export.name]
        user.save()

        # Step 1 : Start by creating 25 DAs
        date_from = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        for i in range(0, 25):
            da = DemandeAsile(**da_orientation_payload)
            da.usager.identifiant_dna = format(i, '08d')
            da.usager.save()
            da.save()
        date_to_1 = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)

        route = '/demandes_asile/export?fq=doc_created:[%s TO %s]&per_page=20&page=1' % (
            date_from, date_to_1)
        r = user_req.get(route)
        assert r.status_code == 200, r
        next_route = '/demandes_asile/export?q=*:*&fq=doc_created:[%s TO %s]&per_page=20&page=2' % (
            date_from, date_to_1)
        assert r.data['_links'].get('next', None) == next_route
        assert r.data['_meta']['total'] == 25

        route = '/demandes_asile/export?fq=doc_created:[%s TO %s]&page=2&per_page=20' % (
            date_from, date_to_1)
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['_links'].get('next', None) is None
        assert r.data['_meta']['total'] == 25

        # Step 2 : Create 25 new DAs
        for i in range(0, 25):
            da = DemandeAsile(**da_orientation_payload)
            da.usager.identifiant_dna = format(25 + i, '08d')
            da.usager.save()
            da.save()
        date_to_2 = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)

        route = '/demandes_asile/export?fq=doc_created:[%s TO %s]&per_page=100' % (
            date_from, date_to_1)
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['_links'].get('next', None) is None
        assert r.data['_meta']['total'] == 25

        route = '/demandes_asile/export?fq=doc_created:[%s TO %s]&per_page=100' % (
            date_from, date_to_2)
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['_links'].get('next', None) is None
        assert r.data['_meta']['total'] == 50


class TestExportDemandeAsileSpecific(common.BaseTest):

    def test_export_condition_exceptionnelle(self, user_with_site_affecte, da_orientation_payload):
        from sief.roles import ROLES
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)

        route = '/demandes_asile/condition_exceptionnelle/export'
        for key in ROLES:
            permissions = []
            for permission in ROLES[key]:
                permissions.append(permission.name)
            user.permissions = permissions
            user.save()
            r = user_req.get(route)
            if key == 'EXTRACTEUR' or key == 'ADMINISTRATEUR':
                assert r.status_code == 200
                assert "nom,prénoms,date de naissance,Numéro AGDREF,date arrivée en France" in r.data[
                    '_data']
            else:
                assert r.status_code == 403


    def test_export_introduction_ofpra(self, user_with_site_affecte, da_attente_ofpra):
        from sief.roles import ROLES
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)

        route = '/demandes_asile/en_attente_introduction_ofpra/export'
        for key in ROLES:
            permissions = []
            for permission in ROLES[key]:
                permissions.append(permission.name)
            user.permissions = permissions
            user.save()
            r = user_req.get(route)
            if key == 'EXTRACTEUR' or key == 'ADMINISTRATEUR':
                assert r.status_code == 200
                assert "nom,prénoms,date de naissance,Numéro étranger,date arrivée en France" in r.data[
                    '_data']
            else:
                assert r.status_code == 403
