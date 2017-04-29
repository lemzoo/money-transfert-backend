import pytest
from datetime import datetime, timedelta

from tests import common
from tests.fixtures import *

from sief.model.site import Prefecture
from sief.model.demande_asile import DemandeAsile
from sief.permissions import POLICIES as p


class TestPrefectureRattacheeUsager(common.BaseTest):

    def test_prefecture_rattachee(self, user, usager, site, site_gu):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.voir.name]
        user.test_set_accreditation(site_affecte=site)
        user.save()
        # Sanity check
        assert isinstance(site, Prefecture)
        assert site != site_gu.autorite_rattachement

        def _test_view(size):
            r = user_req.get('/usagers')
            assert r.status_code == 200, r
            assert len(r.data['_items']) == size
            if len(r.data['_items']) == 1:
                route = r.data['_items'][0]['_links']['self']
                r = user_req.get(route)
                assert r.status_code == 200, r
                assert r.data['id'] == str(usager.id)
        _test_view(0)
        user.test_set_accreditation(site_affecte=site_gu.autorite_rattachement)
        user.save()
        _test_view(1)
        user.test_set_accreditation()
        user.permissions.append(p.usager.prefecture_rattachee.sans_limite.name)
        user.save()
        _test_view(1)

    def test_prefecture_rattachee_route(self, user, usager, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.voir.name]
        user.test_set_accreditation(site_affecte=site)
        user.save()
        # Sanity check
        assert isinstance(site, Prefecture)
        assert site != usager.prefecture_rattachee
        # Cannot see this usager...
        r = user_req.get('/usagers/%s' % usager.id)
        assert r.status_code == 403, r
        # ...but can ask who's it belong to
        r = user_req.get('/usagers/%s/prefecture_rattachee' % usager.id)
        assert r.status_code == 200, r
        assert 'prefecture_rattachee' in r.data
        assert r.data['prefecture_rattachee']['id'] == str(usager.prefecture_rattachee.id)

    def test_change_prefecture_rattachee(self, user, droit, site):
        usager = droit.usager
        da = droit.demande_origine
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.voir.name]
        user.test_set_accreditation(site_affecte=usager.prefecture_rattachee)
        user.save()
        da.save()
        payload = {'prefecture_rattachee': str(site.id)}
        # Sanity check
        assert isinstance(site, Prefecture)
        assert site != usager.prefecture_rattachee
        assert site != da.prefecture_rattachee
        assert site != droit.prefecture_rattachee
        # Need rights to do it...
        r = user_req.patch('/usagers/%s/prefecture_rattachee' % usager.id, data=payload)
        assert r.status_code == 403, r
        # ...provide it
        user.permissions.append(p.usager.prefecture_rattachee.modifier.name)
        user.save()
        r = user_req.patch('/usagers/%s/prefecture_rattachee' % usager.id, data=payload)
        assert r.status_code == 200, r
        # Now we can no longer acces this usager
        r = user_req.get('/usagers/%s' % usager.id)
        assert r.status_code == 403, r
        # Make sure usager's demande_asile and droit as been changed as well
        da.reload()
        assert da.prefecture_rattachee == site
        droit.reload()
        assert droit.prefecture_rattachee == site

    def test_change_prefecture_rattachee_from_outside(self, user, usager, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.voir.name,
                            p.usager.prefecture_rattachee.modifier.name]
        user.test_set_accreditation(site_affecte=site)
        user.save()
        payload = {'prefecture_rattachee': str(site.id)}
        # Sanity check
        assert isinstance(site, Prefecture)
        assert site != usager.prefecture_rattachee
        # Cannot access an usager for the moment
        r = user_req.get('/usagers/%s' % usager.id)
        assert r.status_code == 403, r
        # Now change the prefecture_rattachee to mine
        r = user_req.patch('/usagers/%s/prefecture_rattachee' % usager.id, data=payload)
        assert r.status_code == 200, r
        # Now we can access the usager
        r = user_req.get('/usagers/%s' % usager.id)
        assert r.status_code == 200, r

    def test_change_prefecture_rattachee_not_transferable(self, user, usager, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.voir.name,
                            p.usager.prefecture_rattachee.modifier.name]
        user.test_set_accreditation(site_affecte=site)
        user.save()
        usager.transferable = False
        usager.save()
        payload = {'prefecture_rattachee': str(site.id)}
        # Sanity check
        assert isinstance(site, Prefecture)
        assert site != usager.prefecture_rattachee
        # Cannot access an usager for the moment
        r = user_req.get('/usagers/%s' % usager.id)
        assert r.status_code == 403, r
        # Now change the prefecture_rattachee to mine
        r = user_req.patch('/usagers/%s/prefecture_rattachee' % usager.id, data=payload)
        assert r.status_code == 400, r
        assert '_errors' in r.data
        assert 'non transférable' in r.data['_errors'][0]['usager']
        usager.reload()
        assert site != usager.prefecture_rattachee


class TestUsagersCorrespondantsListAPI(common.BaseSolrTest):

    def test_recherche_portail(self, user_with_site_affecte, usager, da_orientation_payload):

        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.voir.name]
        user.save()
        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)
        route = '/recherche_usagers_tiers?usagers&nom=' + usager.nom
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['PLATEFORME'][0]['indicateurPresenceDemandeAsile'] == False
        da = DemandeAsile(**da_orientation_payload)
        da.usager = usager
        da.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['PLATEFORME'][0]['indicateurPresenceDemandeAsile'] == True
        da.statut = 'FIN_PROCEDURE'
        da.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['PLATEFORME'][0]['indicateurPresenceDemandeAsile'] == False
        da = DemandeAsile(**da_orientation_payload)
        da.usager = usager
        da.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['PLATEFORME'][0]['indicateurPresenceDemandeAsile'] == True
