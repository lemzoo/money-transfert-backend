import pytest

from tests import common
from tests.fixtures import *


class TestUtilisateurOverallView(common.BaseTest):

    def test_get_utilisateur(self, user, administrateur, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = []
        set_user_accreditation(user, role='ADMINISTRATEUR_PREFECTURE', site_affecte=site)
        user.save()
        r = user_req.get('/utilisateurs/%s' % administrateur.id)
        assert r.status_code == 403, r
        assert r.data['_errors'][0] == 'Cet utilisateur est rattaché à un autre site et/ou a un role que vous ne pouvez pas voir'
        # Now call with overall
        r = user_req.get('/utilisateurs/%s?overall' % administrateur.id)
        assert r.status_code == 200, r

    def test_patch_utilisateur(self, user, administrateur, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = []
        set_user_accreditation(user, role='ADMINISTRATEUR_PREFECTURE', site_affecte=site)
        user.save()
        r = user_req.patch('/utilisateurs/%s' % administrateur.id, data={'nom': 'Doe'})
        assert r.status_code == 403, r
        assert r.data['_errors'][0] == 'Cet utilisateur est rattaché à un autre site et/ou a un role que vous ne pouvez pas voir'
        # Now call with overall
        r = user_req.patch('/utilisateurs/%s?overall' % administrateur.id, data={'nom': 'Doe'})
        assert r.status_code == 200, r
        assert r.data.get('nom', '<invalid>') == 'Doe'

    def test_get_utilisateur_list(self, user, administrateur, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = []
        set_user_accreditation(user, role='ADMINISTRATEUR_PREFECTURE', site_affecte=site)
        user.save()
        r = user_req.get('/utilisateurs')
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 0
        # Now call with overall
        r = user_req.get('/utilisateurs?overall')
        assert r.status_code == 200, r
        # User can see himself and administrateur
        assert len(r.data['_items']) == 2


class TestDroitOverallView(common.BaseTest):

    def test_get_droit(self, user, droit, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = []
        set_user_accreditation(user, role='RESPONSABLE_GU_ASILE_PREFECTURE', site_affecte=site)
        user.save()
        r = user_req.get('/droits/%s' % droit.id)
        assert r.status_code == 403, r
        assert r.data['_errors'][0] == 'Prefecture de rattachement invalide'
        # Now call with overall (must be 403)
        r = user_req.get('/droits/%s?overall' % droit.id)
        assert r.status_code == 403, r
        assert r.data['_errors'][0] == 'Prefecture de rattachement invalide'

    def test_get_droit_list(self, user, droit, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = []
        set_user_accreditation(user, role='RESPONSABLE_GU_ASILE_PREFECTURE', site_affecte=site)
        user.save()
        r = user_req.get('/droits')
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 0
        # Now call with overall
        r = user_req.get('/droits?overall')
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 1


class TestUsagerOverallView(common.BaseTest):

    def test_get_usager(self, user, usager, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = []
        set_user_accreditation(user, role='RESPONSABLE_GU_ASILE_PREFECTURE', site_affecte=site)
        user.save()
        r = user_req.get('/usagers/%s' % usager.id)
        assert r.status_code == 403, r
        assert r.data['_errors'][0] == 'Prefecture de rattachement invalide'
        # Now call with overall
        r = user_req.get('/usagers/%s?overall' % usager.id)
        assert r.status_code == 200, r

    def test_get_usager_localisation(self, user, usager, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = []
        set_user_accreditation(user, role='RESPONSABLE_GU_ASILE_PREFECTURE', site_affecte=site)
        user.save()
        r = user_req.get('/usagers/%s/localisations' % usager.id)
        assert r.status_code == 403, r
        assert r.data['_errors'][0] == 'Prefecture de rattachement invalide'
        # Now call with overall
        r = user_req.get('/usagers/%s/localisations?overall' % usager.id)
        assert r.status_code == 200, r

    def test_get_usager_list(self, user, usager, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = []
        set_user_accreditation(user, role='RESPONSABLE_GU_ASILE_PREFECTURE', site_affecte=site)
        user.save()
        r = user_req.get('/usagers')
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 0
        # Now call with overall
        r = user_req.get('/usagers?overall')
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 1


class TestDemandeAsileOverallView(common.BaseTest):

    def test_get_da(self, user, da_attente_ofpra, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = []
        set_user_accreditation(user, role='RESPONSABLE_GU_ASILE_PREFECTURE', site_affecte=site)
        user.save()
        r = user_req.get('/demandes_asile/%s' % da_attente_ofpra.id)
        assert r.status_code == 403, r
        assert r.data['_errors'][0] == 'Prefecture de rattachement invalide'
        # Now call with overall
        r = user_req.get('/demandes_asile/%s?overall' % da_attente_ofpra.id)
        assert r.status_code == 200, r

    def test_get_da_list(self, user, da_attente_ofpra, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = []
        set_user_accreditation(user, role='RESPONSABLE_GU_ASILE_PREFECTURE', site_affecte=site)
        user.save()
        r = user_req.get('/demandes_asile')
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 0
        # Now call with overall
        r = user_req.get('/demandes_asile?overall')
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 3
