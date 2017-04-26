import pytest
from datetime import datetime, timedelta
import copy
from workdays import workday, networkdays

from tests import common
from tests.fixtures import *

from core.model_util import LinkedDocument
from sief.model.site import (Prefecture, Creneau, SiteActualite)
from sief.model.utilisateur import Utilisateur
from sief.model.recueil_da import RecueilDA
from sief.permissions import POLICIES as p


# Monkey patch on allowed document for rendez-vous for easier testing
def RDDoc_linker_builder(obj):
    return {'self': '/rddocs/%s' % obj.pk}


class RDDoc(LinkedDocument):
    meta = {'linker_builder': RDDoc_linker_builder}
Creneau.document_lie.choices += ("RDDoc",)


def attach_two_users(site):
    u1 = Utilisateur(nom='Foo', prenom='Bar', email='foo.bar@test.com')
    u1.controller.init_basic_auth()
    u1.controller.set_password(password='AP@ssw0rd')
    u1.controller.add_accreditation(**{'site_affecte': site})
    u1.site_affecte = site
    u1.save()
    u2 = Utilisateur(nom='Foo', prenom='Bar', email='foo2.bar@test.com')
    u2.controller.init_basic_auth()
    u2.controller.set_password(password='AP@ssw0rd')
    u2.controller.add_accreditation(**{'site_affecte': site})
    u2.site_affecte = site
    u2.save()
    return u1, u2


@pytest.fixture
def actualite_alerte_3_jrs(user, site_prefecture):
    NOW = datetime(2015, 6, 22, 12, 44, 32)
    doc = RDDoc().save()
    site_prefecture.controller.reserver_creneaux(doc, today=NOW, limite_rdv_jrs=3)
    actualite = SiteActualite.objects(site=site_prefecture)[0]
    return (actualite, site_prefecture, doc)


@pytest.fixture
def another_actualite_alerte_3_jrs(user, site_gu):
    NOW = datetime(2015, 6, 22, 12, 44, 32)
    doc = RDDoc().save()
    site_gu.controller.reserver_creneaux(doc, today=NOW, limite_rdv_jrs=3)
    actualite = SiteActualite.objects(site=site_gu)[0]
    return (actualite, site_gu, doc)


class TestCreateSite(common.BaseTest):

    def test_create_site(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        # Need permission to do it
        r = user_req.post('/sites', data=DEFAULT_SITE_PAYLOAD)
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions = [p.site.creer.name]
        user.save()
        r = user_req.post('/sites', data=DEFAULT_SITE_PAYLOAD)
        assert r.status_code == 201, r

    def test_create_unknown_address_site(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        # Need permission to do it
        r = user_req.post('/sites', data=DEFAULT_UNKNOWN_ADDRESS_SITE_PAYLOAD)
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions = [p.site.creer.name]
        user.save()
        r = user_req.post('/sites', data=DEFAULT_UNKNOWN_ADDRESS_SITE_PAYLOAD)
        assert r.status_code == 400, r
        assert r.data['_errors'][0]['adresse']["adresse_inconnue"] == 'Not a valid choice.'
        assert r.data['_errors'][0]['adresse']["voie"] == 'Missing data for required field.'
        assert r.data['_errors'][0]['adresse']["ville"] == 'Missing data for required field.'


class TestSite(common.BaseTest):

    def test_links_list(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.voir.name]
        user.save()
        r = user_req.get('/sites')
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'root'])
        user.permissions.append(p.site.creer.name)
        user.save()
        r = user_req.get('/sites')
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'create', 'root'])

    def test_links_single(self, user, site_prefecture):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.voir.name]
        user.test_set_accreditation(site_affecte=None)
        user.save()
        route = '/sites/%s' % site_prefecture.pk
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'parent'])
        assert r.data.get('type', '<not_defined>') == 'Prefecture'
        user.permissions.append(p.site.modifier.name)
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'update', 'parent'])
        user.permissions = [p.site.voir.name, p.historique.voir.name]
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'history', 'parent'])
        user.permissions.append(p.site.creneaux.gerer.name)
        user.test_set_accreditation(site_affecte=site_prefecture)
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'history', 'parent', 'creneaux'])

    def test_close_site(self, user, site):
        user_req = self.make_auth_request(user, user._raw_password)
        # Need permission to do it
        route = '/sites/{}'.format(site.id)
        r = user_req.delete(route)
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions = [p.site.fermer.name,
                            p.site.sans_limite_site_affecte.name]
        user.save()
        r = user_req.delete(route)
        assert r.status_code == 200, r
        assert 'date_fermeture' in r.data

    def test_close_with_site_affecte(self, user, site):
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/sites/{}'.format(site.id)
        user.permissions = [p.site.fermer.name]
        user.save()
        # Need to set site_affecte do to it
        r = user_req.delete(route)
        assert r.status_code == 403, r
        # Now provide the site_affecte
        user.test_set_accreditation(site_affecte=site)
        user.save()
        r = user_req.delete(route)
        assert r.status_code == 200, r
        assert 'date_fermeture' in r.data

    # TODO: multirole FIXME !!!
    @pytest.mark.xfail(reason="multirole: test must be converted to use accreditations")
    def test_change_site_affecte(self, user, site_gu, site, site_prefecture):
        user_req = self.make_auth_request(user, user._raw_password)
        assert site_gu.autorite_rattachement != site
        assert isinstance(site, Prefecture)
        user.test_set_accreditation(site_affecte=site_gu)
        route = '/sites/{}'.format(site_gu.id)
        user.permissions = [p.site.modifier.name]
        user.save()
        # Create some users linked to the site_gu
        gu_users = [
            Utilisateur(nom='X', prenom='Y', email='user%s@test.com' % i,
                        password='dummy', site_affecte=site_gu,
                        site_rattache=site_gu.autorite_rattachement,
                        ).save() for i in range(3)]
        # Another user, just here to watch...
        other_user = Utilisateur(
            nom='X', prenom='Y', email='other_user@test.com',
            password='dummy', site_affecte=site,
            site_rattache=site_prefecture,
        ).save()
        # Need to set site_affecte do to it
        r = user_req.patch(route, data={'autorite_rattachement': str(site.id)})
        assert r.status_code == 200, r
        # Second user should have been transferred to the new prefecture
        for gu_user in gu_users:
            gu_user.reload()
            assert gu_user.site_affecte == site_gu
            assert gu_user.site_rattache == site
        # User not linked with the gu should not have been altered
        other_user.reload()
        assert other_user.site_affecte == site
        assert other_user.site_rattache.id == site_prefecture.id

    def test_close_with_patch_site(self, user, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.modifier.name,
                            p.site.sans_limite_site_affecte.name]
        user.save()
        # Need permission to do it
        route = '/sites/{}'.format(site.id)
        payload = {'date_fermeture': '2015-06-10T23:22:54+00:00'}
        r = user_req.patch(route, data=payload)
        assert r.status_code == 403, r
        user.permissions.append(p.site.fermer.name)
        user.save()
        r = user_req.patch(route, data=payload)
        assert r.status_code == 200, r
        assert 'date_fermeture' in r.data

    def test_modify_site(self, user, site):
        user_req = self.make_auth_request(user, user._raw_password)
        # Need permission to do it
        route = '/sites/{}'.format(site.id)
        r = user_req.patch(route, data={'telephone': '0123456789'})
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions = [p.site.modifier.name,
                            p.site.sans_limite_site_affecte.name]
        user.save()
        r = user_req.patch(route, data={'telephone': '0123456789',
                                        'limite_rdv_jrs': 3})
        assert r.status_code == 200, r
        # Try to remove the non-mandatory field
        r = user_req.patch(route, data={'telephone': None})
        assert r.status_code == 200, r

    def test_modify_limite_site_affecte(self, user, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.modifier.name]
        user.save()
        route = '/sites/{}'.format(site.id)
        # Can only modify user's site_affecte
        r = user_req.patch(route, data={'telephone': '0123456789',
                                        'limite_rdv_jrs': 5})
        assert r.status_code == 403, r
        # Now set the site_affecte
        user.test_set_accreditation(site_affecte=site)
        user.save()
        r = user_req.patch(route, data={'telephone': '0123456789',
                                        'limite_rdv_jrs': 3})
        assert r.status_code == 200, r

    def test_bad_modify_site(self, user, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.modifier.name,
                            p.site.sans_limite_site_affecte.name]
        user.save()
        route = '/sites/{}'.format(site.id)
        for payload in ({'libelle': ''}, {'telephone': '12345e789'},
                        {'id': '55464d5d1d41c8698db77e8e'}):
            r = user_req.patch(route, data=payload)
            assert r.status_code == 400, r

    def test_get_site(self, user, site):
        user_req = self.make_auth_request(user, user._raw_password)
        # Need permission to do it
        r = user_req.get('/sites')
        assert r.status_code == 403, r
        r = user_req.get('/sites/{}'.format(site.id))
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions = [p.site.voir.name]
        user.save()
        r = user_req.get('/sites')
        assert r.status_code == 200, r
        r = user_req.get('/sites/{}'.format(site.id))
        assert r.status_code == 200, r


class TestGU(common.BaseTest):

    def test_add_gu(self, user, site_prefecture):
        user.permissions = [p.site.creer.name]
        user.save()
        user_req = self.make_auth_request(user, user._raw_password)
        r = user_req.post('/sites', data={
            "type": "GU",
            "libelle": "GU de Bordeaux",
            "adresse": DEFAULT_SITE_PAYLOAD['adresse'],
            "autorite_rattachement": str(site_prefecture.id)
        })
        assert r.status_code == 201, r

    def test_bad_add_gu(self, user, site_prefecture, site_structure_accueil):
        default_payload = {
            "type": "GU",
            "libelle": "GU de Libourne",
            "adresse": DEFAULT_SITE_PAYLOAD['adresse'],
            "autorite_rattachement": str(site_prefecture.pk)
        }
        user.permissions = [p.site.creer.name]
        user.save()
        user_req = self.make_auth_request(user, user._raw_password)
        not_set = object()
        for field, value in [('type', ''), ('type', None), ('type', 'dummy'),
                             ('type', not_set), ('type', {}),
                             ('libelle', not_set), ('libelle', None),
                             ('libelle', {}), ('adresse', {'bad': 'field'}),
                             ('adresse', ''), ('adresse', None),
                             ('autorite_rattachement', str(site_structure_accueil.pk)),
                             ('autorite_rattachement', None),
                             ('autorite_rattachement', {}),
                             ('autorite_rattachement', not_set),
                             ('autorite_rattachement', ''),
                             ('autorite_rattachement', 'not_an_objectid'),
                             ('autorite_rattachement', '55464d5d1d41c8698db77e8e'),
                             ('id', '55464d5d1d41c8698db77e8e')]:
            payload = default_payload.copy()
            if value is not_set:
                del payload[field]
            else:
                payload[field] = value
            r = user_req.post('/sites', data=payload)
            assert r.status_code == 400, (field, value)


class TestStructureAccueil(common.BaseTest):

    def test_guichets_uniques(self, user, site_gu, site_prefecture):
        default_payload = {
            "type": "StructureAccueil",
            "libelle": "Structure d'accueil de Bordeaux",
            "adresse": DEFAULT_SITE_PAYLOAD['adresse'],
            "guichets_uniques": [str(site_gu.pk)]
        }
        user.permissions = [p.site.creer.name]
        user.save()
        user_req = self.make_auth_request(user, user._raw_password)
        not_set = object()
        for field, value in [
                ('guichets_uniques', None),
                ('guichets_uniques', ''),
                ('guichets_uniques', '55464d5d1d41c8698db77e8e'),
                ('guichets_uniques', not_set),
                ('guichets_uniques', []),
                ('guichets_uniques', [str(site_prefecture.pk)]),
                ('guichets_uniques', [str(site_gu.pk), str(site_prefecture.pk)]),
                ('autorite_rattachement', [str(site_gu.pk), '55464d5d1d41c8698db77e8e'])]:
            payload = default_payload.copy()
            if value is not_set:
                del payload[field]
            else:
                payload[field] = value
            r = user_req.post('/sites', data=payload)
            assert r.status_code == 400, (field, value)

    def test_good_structure_accueil(self, user, site_gu):
        payload = {
            "type": "StructureAccueil",
            "libelle": "Structure d'accueil de Libourne",
            "adresse": DEFAULT_SITE_PAYLOAD['adresse'],
            "guichets_uniques": [str(site_gu.pk)]
        }
        user.permissions = [p.site.creer.name]
        user.save()
        user_req = self.make_auth_request(user, user._raw_password)
        r = user_req.post('/sites', data=payload)
        assert r.status_code == 201, r.data


class TestEnsembleZonal(common.BaseTest):

    def test_prefectures(self, user, site_gu, site_prefecture):
        default_payload = {
            "type": "EnsembleZonal",
            "libelle": "Ensemble Zonal de Libourne",
            "adresse": DEFAULT_SITE_PAYLOAD['adresse'],
            "prefectures": [str(site_prefecture.pk)]
        }
        user.permissions = [p.site.creer.name]
        user.save()
        user_req = self.make_auth_request(user, user._raw_password)
        not_set = object()
        for field, value in [
                ('prefectures', None),
                ('prefectures', ''),
                ('prefectures', '55464d5d1d41c8698db77e8e'),
                ('prefectures', not_set),
                ('prefectures', []),
                ('prefectures', [str(site_gu.pk)]),
                ('prefectures', [str(site_gu.pk), str(site_prefecture.pk)])]:
            payload = default_payload.copy()
            if value is not_set:
                del payload[field]
            else:
                payload[field] = value
            r = user_req.post('/sites', data=payload)
            assert r.status_code == 400, (field, value)

    def test_good_structure_accueil(self, user, site_prefecture):
        payload = {
            "type": "EnsembleZonal",
            "libelle": "Ensemble Zonal de Bordeaux",
            "adresse": DEFAULT_SITE_PAYLOAD['adresse'],
            "prefectures": [str(site_prefecture.pk)]
        }
        user.permissions = [p.site.creer.name]
        user.save()
        user_req = self.make_auth_request(user, user._raw_password)
        r = user_req.post('/sites', data=payload)
        assert r.status_code == 201, r.data


class TestPaginationSite(common.BaseTest):

    def test_paginate_users(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.voir.name]
        user.save()
        # Start by creating a lot of sites
        for i in range(50):
            payload = DEFAULT_SITE_PAYLOAD.copy()
            del payload["type"]
            payload['libelle'] = 'Prefecture-%s' % i
            new_site = Prefecture(**payload)
            new_site.save()
        # Now let's test the pagination !
        common.pagination_testbed(user_req, '/sites')


class TestCreneaux(common.BaseTest):

    def _add_creneaux(self, site, count=10, start=None):
        start = start if start else workday(datetime.utcnow(), days=1)
        creneaux = []
        # Trim start date to a working day
        if networkdays(start, start) == 0:
            start = workday(start, days=1)
        creneau_duration = timedelta(0, 45 * 60)
        for i in range(count):
            cr_start = start + creneau_duration * i
            cr_end = cr_start + creneau_duration
            creneau = Creneau(date_debut=cr_start, date_fin=cr_end, site=site)
            creneau.save()
            creneaux.append(creneau)
        return creneaux

    def test_delete_creneaux(self, user, site_prefecture):
        free_cr, res_cr = self._add_creneaux(site_prefecture, 2)
        user_req = self.make_auth_request(user, user._raw_password)
        # Need permission to do it
        route = '/sites/%s/creneaux/' % site_prefecture.id
        r = user_req.delete(route + str(free_cr.pk))
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions = [p.site.creneaux.gerer.name,
                            p.site.sans_limite_site_affecte.name]
        user.save()
        r = user_req.delete(route + str(free_cr.pk))
        assert r.status_code == 204, r
        r = user_req.delete(route + str(free_cr.pk))
        assert r.status_code == 404, r
        # Make sure we can't delete reserved creneaux
        rd_doc = RDDoc().save()
        res_cr.controller.reserver(rd_doc)
        res_cr.save()
        route = '/sites/%s/creneaux/' % site_prefecture.id
        r = user_req.delete(route + str(res_cr.pk))
        assert r.status_code == 400, r

    def test_reserved_creneaux_links(self, user, site_prefecture):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.creneaux.gerer.name,
                            p.site.voir.name]
        user.save()
        # Make sure we can't delete reserved creneaux
        # Create&book a creneau
        res_cr, = self._add_creneaux(site_prefecture, 1)
        rd_doc = RDDoc().save()
        res_cr.controller.reserver(rd_doc)
        res_cr.save()
        # Now make sure this creneaux display the linked document correctly
        r = user_req.get('/sites/%s/creneaux/%s' % (site_prefecture.id, res_cr.id))
        assert r.status_code == 200, r
        assert 'document_lie' in r.data
        assert r.data['document_lie']['id'] == str(rd_doc.pk)
        assert r.data['document_lie']['_cls'] == str(rd_doc._class_name)
        assert '_links' in r.data['document_lie']

    def test_links_creneaux(self, user, site_prefecture):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.voir.name]
        user.save()
        route = '/sites/%s/creneaux' % site_prefecture.id
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'site'])
        user.permissions.append(p.site.creneaux.gerer.name)
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'site'])
        user.test_set_accreditation(site_affecte=site_prefecture)
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'site', 'create'])

    def test_get_creneaux(self, user, site_prefecture):
        self._add_creneaux(site_prefecture, 10)
        # Old creneaux should not be visible
        self._add_creneaux(site_prefecture, count=10, start=datetime(2008, 1, 1))
        user_req = self.make_auth_request(user, user._raw_password)
        # Need permission to do it
        route = '/sites/%s/creneaux' % site_prefecture.id
        r = user_req.get(route)
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions = [p.site.voir.name]
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['_meta'] == {'page': 1, 'per_page': 20, 'total': 10}
        assert len(r.data['_items']) == 10
        # Test the pagination as well
        r = user_req.get(route + '?page=2&per_page=6')
        assert r.status_code == 200, r
        assert r.data['_meta'] == {'page': 2, 'per_page': 6, 'total': 10}
        assert len(r.data['_items']) == 4

    def test_bad_get_creneaux(self, user, site_structure_accueil):
        # Only sites with creneaux (i.g. GU) provide this route
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.voir.name,
                            p.site.sans_limite_site_affecte.name]
        user.save()
        r = user_req.get('/sites/%s/creneaux' % site_structure_accueil.id)
        assert r.status_code == 404, r
        # Same thing for the post
        r = user_req.post('/sites/%s/creneaux' % site_structure_accueil.id, data={})
        assert r.status_code == 404, r

    def test_add_creneaux(self, user, site_prefecture):
        user_req = self.make_auth_request(user, user._raw_password)

        # We need two users attached to the site because of the agent number protection
        attach_two_users(site_prefecture)

        start = datetime.utcnow()
        # 2 guichets, 4hours, 60mn/creneau ==> 8 creneaux
        payload = {
            'plage_debut': start.isoformat(),
            'plage_fin': (start + timedelta(hours=4)).isoformat(),
            'plage_guichets': 2,
            'duree_creneau': 60
        }
        # Need permission to do it
        route = '/sites/%s/creneaux' % site_prefecture.id
        r = user_req.post(route, data=payload)
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions = [p.site.creneaux.gerer.name,
                            p.site.sans_limite_site_affecte.name]
        user.save()

        r = user_req.post(route, data=payload)
        assert r.status_code == 201, r
        assert r.data['_meta'] == {'page': 1, 'per_page': 8, 'total': 8}
        assert len(r.data['_items']) == 8

    def test_limite_site_add_creneaux(self, user, site_prefecture):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.creneaux.gerer.name]
        user.save()

        # We need two users attached to the site because of the agent number protection
        attach_two_users(site_prefecture)

        start = datetime.utcnow()
        # 2 guichets, 4hours, 60mn/creneau ==> 8 creneaux
        payload = {
            'plage_debut': start.isoformat(),
            'plage_fin': (start + timedelta(hours=4)).isoformat(),
            'plage_guichets': 2,
            'duree_creneau': 60
        }
        route = '/sites/%s/creneaux' % site_prefecture.id
        # Need site_affecte to do it...
        r = user_req.post(route, data=payload)
        assert r.status_code == 403, r
        # Now provide site_affecte
        user.test_set_accreditation(site_affecte=site_prefecture)
        user.save()
        r = user_req.post(route, data=payload)
        assert r.status_code == 201, r
        assert r.data['_meta'] == {'page': 1, 'per_page': 8, 'total': 8}
        assert len(r.data['_items']) == 8

    def test_no_add_creneaux_on_closed_site(self, user, site_prefecture):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.fermer.name,
                            p.site.creneaux.gerer.name]
        user.test_set_accreditation(site_affecte=site_prefecture)
        user.save()
        route = '/sites/{}'.format(site_prefecture.id)
        r = user_req.delete(route)
        assert r.status_code == 200, r
        assert 'date_fermeture' in r.data
        # Cannot add creneaux to closed site
        start = datetime.utcnow()
        payload = {
            'plage_debut': start.isoformat(),
            'plage_fin': (start + timedelta(hours=4)).isoformat(),
            'plage_guichets': 2,
            'duree_creneau': 60
        }
        r = user_req.post(route + '/creneaux', data=payload)
        assert r.status_code == 400

    def test_add_creneaux_invalid_duree(self, user, site_prefecture):
        user_req = self.make_auth_request(user, user._raw_password)
        start = datetime.utcnow()
        # We need two users attached to the site because of the agent number protection
        attach_two_users(site_prefecture)
        # Need permission to do it
        route = '/sites/%s/creneaux' % site_prefecture.id
        user.permissions = [p.site.creneaux.gerer.name,
                            p.site.sans_limite_site_affecte.name]
        user.save()

        payload = {
            'plage_debut': start.isoformat(),
            'plage_fin': (start + timedelta(hours=4)).isoformat(),
            'plage_guichets': 2,
            'duree_creneau': 9
        }
        r = user_req.post(route, data=payload)
        assert r.status_code == 400
        assert len(r.data['_errors'])

        payload['duree_creneau'] = 100000
        r = user_req.post(route, data=payload)
        assert r.status_code == 400
        assert len(r.data['_errors'])

    def test_add_creneaux_date_too_far_apart(self, user, site_prefecture):
        user_req = self.make_auth_request(user, user._raw_password)
        start = datetime.utcnow()
        # We need two users attached to the site because of the agent number protection
        attach_two_users(site_prefecture)

        payload = {
            'plage_debut': start.isoformat(),
            'plage_fin': (start + timedelta(days=8)).isoformat(),
            'plage_guichets': 2,
            'duree_creneau': 60
        }
        # Need permission to do it
        route = '/sites/%s/creneaux' % site_prefecture.id
        user.permissions = [p.site.creneaux.gerer.name,
                            p.site.sans_limite_site_affecte.name]
        user.save()
        r = user_req.post(route, data=payload)
        assert r.status_code == 400
        assert len(r.data['_errors'])

    def test_add_creneaux_too_many(self, user, site_prefecture):
        user_req = self.make_auth_request(user, user._raw_password)
        start = datetime.utcnow()
        # We need two users attached to the site because of the agent number protection
        attach_two_users(site_prefecture)

        # 2 guichets, 1day, 10min/creneau ==> 288 creneaux
        payload = {
            'plage_debut': start.isoformat(),
            'plage_fin': (start + timedelta(days=1)).isoformat(),
            'plage_guichets': 2,
            'duree_creneau': 10
        }
        # Need permission to do it
        route = '/sites/%s/creneaux' % site_prefecture.id
        user.permissions = [p.site.creneaux.gerer.name,
                            p.site.sans_limite_site_affecte.name]
        user.save()
        r = user_req.post(route, data=payload)
        assert r.status_code == 400
        assert len(r.data['_errors'])

    def test_add_creneaux_insuficient_guichets(self, user, site_prefecture):
        user_req = self.make_auth_request(user, user._raw_password)
        start = datetime.utcnow()
        # Only two users are attached to the site
        attach_two_users(site_prefecture)

        route = '/sites/%s/creneaux' % site_prefecture.id
        # Need permission to do it
        user.permissions = [p.site.creneaux.gerer.name,
                            p.site.sans_limite_site_affecte.name]
        user.save()

        # 3 guichets, 1hour, 30min/creneau ==> 6 creneaux
        payload = {
            'plage_debut': start.isoformat(),
            'plage_fin': (start + timedelta(hours=1)).isoformat(),
            # 3 guichets but only two users attached
            'plage_guichets': 3,
            'duree_creneau': 10
        }
        r = user_req.post(route, data=payload)
        assert r.status_code == 400
        assert len(r.data['_errors'])

        payload['plage_guichets'] = 0
        r = user_req.post(route, data=payload)
        assert r.status_code == 400
        assert len(r.data['_errors'])

    def test_add_creneaux_marge(self, user, site_prefecture):
        user_req = self.make_auth_request(user, user._raw_password)
        start = datetime.utcnow()
        # 2 guichets, 4hours, 60mn/creneau ==> 8 creneaux
        payload = {
            'plage_debut': start.isoformat(),
            'plage_fin': (start + timedelta(hours=4)).isoformat(),
            'plage_guichets': 2,
            'duree_creneau': 60,
            'marge': 15,
            'marge_initiale': False
        }
        # Need permission to do it
        user.permissions = [p.site.creneaux.gerer.name,
                            p.site.sans_limite_site_affecte.name]
        user.test_set_accreditation(site_affecte=site_prefecture)
        user.save()

        attach_two_users(site_prefecture)

        r = user_req.post('/sites/%s/creneaux' % site_prefecture.id, data=payload)
        assert r.status_code == 201, r
        assert r.data['_meta'] == {'page': 1, 'per_page': 8, 'total': 8}
        assert len(r.data['_items']) == 8
        for item in r.data['_items'][:2]:
            assert 'marge' not in item
        for item in r.data['_items'][2:]:
            assert item['marge'] == 15

    def test_add_creneaux_marge_initiale(self, user, site_prefecture):
        user_req = self.make_auth_request(user, user._raw_password)
        start = datetime.utcnow()
        # 2 guichets, 4hours, 60mn/creneau ==> 8 creneaux
        payload = {
            'plage_debut': start.isoformat(),
            'plage_fin': (start + timedelta(hours=4)).isoformat(),
            'plage_guichets': 2,
            'duree_creneau': 60,
            'marge': 15,
            'marge_initiale': True
        }
        # Need permission to do it
        user.permissions = [p.site.creneaux.gerer.name,
                            p.site.sans_limite_site_affecte.name]
        user.test_set_accreditation(site_affecte=site_prefecture)
        user.save()

        attach_two_users(site_prefecture)

        r = user_req.post('/sites/%s/creneaux' % site_prefecture.id, data=payload)
        assert r.status_code == 201, r
        assert r.data['_meta'] == {'page': 1, 'per_page': 8, 'total': 8}
        assert len(r.data['_items']) == 8
        for item in r.data['_items']:
            assert item['marge'] == 15

    def test_add_bad_creneaux(self, user, site_prefecture):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(site_affecte=site_prefecture)
        user.permissions = [p.site.creneaux.gerer.name,
                            p.site.sans_limite_site_affecte.name]
        user.save()
        route = '/sites/%s/creneaux' % site_prefecture.id
        start = datetime.utcnow()
        default_payload = {
            'plage_debut': start.isoformat(),
            'plage_fin': (start + timedelta(hours=4)).isoformat(),
            'plage_guichets': 2,
            'duree_creneau': 60,
            'marge': 45
        }
        for key, value in [('plage_debut', None), ('plage_debut', ''),
                           ('plage_debut', 'not a date'), ('plage_debut', 42),
                           ('plage_debut', 0),
                           ('plage_fin', None), ('plage_fin', ''),
                           ('plage_fin', 'not a date'), ('plage_fin', 42),
                           ('plage_fin', 0), ('marge', -1),
                           ('plage_guichets', None), ('plage_guichets', ''),
                           ('plage_guichets', 'nan'), ('plage_guichets', -1),
                           ('duree_creneau', None), ('duree_creneau', ''),
                           ('duree_creneau', 'nan'), ('duree_creneau', -1)
                           ]:
            payload = default_payload.copy()
            if value is None:
                del payload[key]
            else:
                payload[key] = value
            r = user_req.post(route, data=payload)
            assert r.status_code == 400, (key, value)

    def test_delete_plage_creneaux(self, user, site):
        from workdays import workday as add_days
        now = datetime.utcnow().replace(hour=0, minute=0, second=0)
        self._add_creneaux(site, start=add_days(now, 1))
        self._add_creneaux(site, start=add_days(now, 2))
        self._add_creneaux(site, start=add_days(now, 3))
        res_cr, = self._add_creneaux(site, count=1,
                                     start=workday(now, 3))
        rd_doc = RDDoc().save()
        res_cr.controller.reserver(rd_doc)
        res_cr.save()
        user_req = self.make_auth_request(user, user._raw_password)
        # Need permission to do it
        route = '/sites/%s/creneaux' % site.id
        date_debut = workday(now, 2).strftime("%Y-%m-%dT00:00:00Z")
        date_fin = workday(now, 2).strftime("%Y-%m-%dT23:59:59Z")
        params = "?date_debut=%s&date_fin=%s" % (date_debut, date_fin)
        r = user_req.delete(route + params)
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions = [p.site.creneaux.gerer.name,
                            p.site.sans_limite_site_affecte.name,
                            p.site.voir.name]
        user.save()
        r = user_req.delete(route + params)
        assert r.status_code == 204, r
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['_meta'] == {'page': 1, 'per_page': 20, 'total': 21}
        assert len(r.data['_items']) == 20
        # test reserve creneaux
        date_debut = workday(now, 3).strftime("%Y-%m-%dT00:00:00Z")
        date_fin = workday(now, 4).strftime("%Y-%m-%dT23:59:59Z")
        params = "?date_debut=%s&date_fin=%s" % (date_debut, date_fin)
        r = user_req.delete(route + params)
        assert r.status_code == 204, r
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 11

    @pytest.mark.xfail(reason="route `/sites/%s/creneaux/%s/rendez_vous` has been deactivated")
    def test_rendez_vous_annuler(self, user, site_prefecture):
        free_cr, res_cr = self._add_creneaux(site_prefecture, 2)
        res_cr.controller.reserver(RecueilDA())
        res_cr.save()
        user_req = self.make_auth_request(user, user._raw_password)
        # Need permission to do it
        free_route = '/sites/%s/creneaux/%s/rendez_vous' % (site_prefecture.pk, free_cr.pk)
        res_route = '/sites/%s/creneaux/%s/rendez_vous' % (site_prefecture.pk, res_cr.pk)
        r = user_req.delete(res_route)
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions = [p.site.rendez_vous.gerer.name,
                            p.site.sans_limite_site_affecte.name]
        user.save()
        # The user also need to have the right site_affecte
        r = user_req.delete(res_route)
        assert r.status_code == 403, r
        user.test_set_accreditation(site_affecte=site_prefecture)
        user.save()
        r = user_req.delete(res_route)
        assert r.status_code == 200, r
        # Cannot annuler if already free
        r = user_req.delete(res_route)
        assert r.status_code == 400, r
        r = user_req.delete(free_route)
        assert r.status_code == 400, r

    @pytest.mark.xfail(reason="route `/sites/%s/creneaux/%s/rendez_vous` has been deactivated")
    def test_rendez_vous_reserve(self, user, site_prefecture):
        free_cr, res_cr = self._add_creneaux(site_prefecture, 2)
        rd_doc = RDDoc()
        rd_doc.save()
        res_cr.controller.reserver(rd_doc)
        res_cr.save()
        user_req = self.make_auth_request(user, user._raw_password)
        # Need permission to do it
        free_route = '/sites/%s/creneaux/%s/rendez_vous' % (site_prefecture.pk, free_cr.pk)
        res_route = '/sites/%s/creneaux/%s/rendez_vous' % (site_prefecture.pk, res_cr.pk)
        payload = {
            'document_type': rd_doc._class_name,
            'document_id': str(rd_doc.pk)
        }
        r = user_req.put(free_route, data=payload)
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions = [p.site.rendez_vous.gerer.name,
                            p.site.sans_limite_site_affecte.name]
        user.save()
        # The user also need to have the right site_affecte
        r = user_req.put(free_route, data=payload)
        assert r.status_code == 403, r
        user.test_set_accreditation(site_affecte=site_prefecture)
        user.save()
        r = user_req.put(free_route, data=payload)
        assert r.status_code == 200, r
        # Cannot reserver if already taken
        r = user_req.put(free_route, data=payload)
        assert r.status_code == 400, r
        r = user_req.put(res_route, data=payload)
        assert r.status_code == 400, r

    @pytest.mark.xfail(reason="route `/sites/%s/creneaux/%s/rendez_vous` has been deactivated")
    def test_rendez_vous_bad_reserve(self, user, site_prefecture):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.rendez_vous.gerer.name,
                            p.site.sans_limite_site_affecte.name]
        user.test_set_accreditation(site_affecte=site_prefecture)
        user.save()
        free_cr, = self._add_creneaux(site_prefecture, 1)
        free_route = '/sites/%s/creneaux/%s/rendez_vous' % (site_prefecture.pk, free_cr.pk)
        rd_doc = RDDoc()
        rd_doc.save()
        default_payload = {
            'document_type': rd_doc._class_name,
            'document_id': str(rd_doc.pk)
        }
        for key, value in (('document_type', common.NOT_SET),
                           ('document_id', common.NOT_SET),
                           ('document_type', 'bad_type'),
                           ('document_id', 'bad_id'),
                           ('document_id', '5577fbb91d41c8803cfdceaf'),
                           ):
            payload = copy.deepcopy(default_payload)
            common.update_payload(payload, key, value)
            r = user_req.put(free_route, data=payload)
            assert r.status_code == 400, (key, value)


class TestActualite(common.BaseTest):

    def test_site_actualites_links(self, user, site_prefecture):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.voir.name, p.site.sans_limite_site_affecte.name]
        user.save()
        route = '/sites/%s/actualites' % site_prefecture.id
        # Need permission
        r = user_req.get(route)
        assert r.status_code == 403, r
        user.permissions.append(p.site.actualite.gerer.name)
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 0
        common.assert_response_contains_links(r, ['self', 'site'])

    def test_site_single_actualite_links(self, user, actualite_alerte_3_jrs,
                                         another_actualite_alerte_3_jrs):
        user_req = self.make_auth_request(user, user._raw_password)
        actualite, site, doc = actualite_alerte_3_jrs
        another_actualite, another_site, another_doc = another_actualite_alerte_3_jrs

        # 1. get without permissions
        route = '/sites/%s/actualites/%s' % (site.id, actualite.id)
        # Need permission
        r = user_req.get(route)
        assert r.status_code == 403, r

        # 2. get with wrong site
        user.test_set_accreditation(role='RESPONSABLE_GU_ASILE_PREFECTURE',
                                    site_affecte=site)
        user.save()
        route = '/sites/%s/actualites/%s' % (another_site.id, actualite.id)
        r = user_req.get(route)
        assert r.status_code == 403, r
        assert 'Vous n''avez pas le bon site affecté' in r.data['_errors']

        # 3. actualite not found
        route = '/sites/%s/actualites/%s' % (site.id, another_actualite.id)
        r = user_req.get(route)
        assert r.status_code == 404, r

        # 4. success
        route = '/sites/%s/actualites/%s' % (site.id, actualite.id)
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['contexte']['document_lie']['id'] == str(doc.id)
        assert r.data['contexte']['document_lie']['_cls'] == doc._class_name
        common.assert_response_contains_links(r, ['self', 'site', 'parent', 'cloturer'])

    def test_site_actualite_cloturer(self, user, actualite_alerte_3_jrs):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.voir.name, p.site.sans_limite_site_affecte.name]
        user.save()
        actualite, site, doc = actualite_alerte_3_jrs
        route = '/sites/%s/actualites/%s' % (site.id, actualite.id)
        # Need permission
        r = user_req.delete(route)
        assert r.status_code == 403, r
        user.permissions.append(p.site.actualite.gerer.name)
        user.save()
        r = user_req.delete(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'site', 'parent'])
        # Cannot do it two times in a row
        r = user_req.delete(route)
        assert r.status_code == 400, r
        assert 'Actualité déjà cloturée' in r.data['_errors']
        # Should not be visible by default in list...
        r = user_req.get('/sites/%s/actualites' % site.id)
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 0
        # ...but can still see it with special param
        r = user_req.get('/sites/%s/actualites?skip_cloturee=false' % site.id)
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 1


class TestExportSite(common.BaseSolrTest):

    def test_export_site(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.creer.name, p.site.export.name]
        user.save()

        # Step 1 : Start by creating 25 sites
        date_from = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        for i in range(0, 25):
            payload = DEFAULT_SITE_PAYLOAD
            payload['libelle'] = 'Site-%s' % chr(ord('a') + i)
            r = user_req.post('/sites', data=payload)
            assert r.status_code == 201, r
        date_to_1 = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)

        route = '/sites/export?fq=doc_created:[%s TO %s]&per_page=20&page=1' % (
            date_from, date_to_1)
        r = user_req.get(route)
        assert r.status_code == 200, r
        next_route = '/sites/export?q=*:*&fq=doc_created:[%s TO %s]&per_page=20&page=2' % (
            date_from, date_to_1)
        assert r.data['_links'].get('next', None) == next_route
        assert r.data['_meta']['total'] == 25

        route = '/sites/export?fq=doc_created:[%s TO %s]&page=2&per_page=20' % (
            date_from, date_to_1)
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['_links'].get('next', None) is None
        assert r.data['_meta']['total'] == 25

        # Step 2 : Create 25 new sites
        for i in range(0, 25):
            payload = DEFAULT_SITE_PAYLOAD
            payload['libelle'] = 'Pref-%s' % chr(ord('a') + i)
            r = user_req.post('/sites', data=payload)
            assert r.status_code == 201, r
        date_to_2 = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)

        route = '/sites/export?fq=doc_created:[%s TO %s]&per_page=100' % (
            date_from, date_to_1)
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['_links'].get('next', None) is None
        assert r.data['_meta']['total'] == 25

        route = '/sites/export?fq=doc_created:[%s TO %s]&per_page=100' % (
            date_from, date_to_2)
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['_links'].get('next', None) is None
        assert r.data['_meta']['total'] == 50

        route = '/sites/export'
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['_links'].get('next', None) == '/sites/export?per_page=20&page=2'
        assert r.data['_meta']['total'] == 50


class TestGUModele(common.BaseTest):

    def test_site_modeles_links1(self, user, site_gu):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.voir.name, p.site.sans_limite_site_affecte.name]
        user.save()
        route = '/sites/%s/modeles' % site_gu.id
        # Need permission
        r = user_req.get(route)
        assert r.status_code == 403, r
        user.permissions.append(p.site.modele.gerer.name)
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 0
        common.assert_response_contains_links(r, ['self', 'site'])

    def test_site_modeles_links2(self, user, site_gu):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.voir.name, p.site.modele.gerer.name]
        user.save()
        route = '/sites/%s/modeles' % site_gu.id
        # Need to set site_affecte do to it
        r = user_req.get(route)
        assert r.status_code == 403, r
        # Now provide the site_affecte
        user.test_set_accreditation(site_affecte=site_gu)
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 0
        common.assert_response_contains_links(r, ['self', 'site'])

    def test_create_modele(self, user, site_gu):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.voir.name, p.site.sans_limite_site_affecte.name]
        route = '/sites/%s/modeles' % site_gu.id
        payload = DEFAULT_SITE_MODELE_PAYLOAD
        # Need permission to do it
        r = user_req.post(route, data=payload)
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions.append(p.site.modele.gerer.name)
        user.save()
        # Check modeles is an empty list
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 0
        # Add Modele
        r = user_req.post(route, data=payload)
        assert r.status_code == 201, r
        assert len(r.data['_items']) == 1
        # ERROR: Add Modele with same libelle value
        r = user_req.post(route, data=payload)
        assert r.status_code == 400, r
        assert r.data['_errors'][0][
            'libelle'] == "Not a valid choice. Already use for another model: QUOTIDIEN."

    def test_patch_modele(self, user, site_gu):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.voir.name, p.site.sans_limite_site_affecte.name]
        route = '/sites/%s/modeles' % site_gu.id
        payload = DEFAULT_SITE_MODELE_PAYLOAD
        # Need permission to do it
        r = user_req.patch(route, data=payload)
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions.append(p.site.modele.gerer.name)
        user.save()
        # Add Modele
        r = user_req.post(route, data=payload)
        assert r.status_code == 201, r
        assert len(r.data['_items']) == 1
        assert r.data['_items'][0]['type'] == 'QUOTIDIEN'
        # Patch Modele
        payload["type"] = "HEBDOMADAIRE"
        r = user_req.patch(route, data=payload)
        assert r.status_code == 201, r
        assert len(r.data['_items']) == 1
        assert r.data['_items'][0]['type'] == 'HEBDOMADAIRE'
        # ERROR: PATCH unexist modele
        payload["libelle"] = "UNKNOWN"
        r = user_req.patch(route, data=payload)
        assert r.status_code == 400, r
        assert r.data['_errors'][0]['libelle'] == 'Not a valid choice.'

    def test_delete_modele(self, user, site_gu):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.voir.name, p.site.sans_limite_site_affecte.name]
        route = '/sites/%s/modeles' % site_gu.id
        payload = DEFAULT_SITE_MODELE_PAYLOAD
        # Need permission to do it
        r = user_req.patch(route, data=payload)
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions.append(p.site.modele.gerer.name)
        user.save()
        # Add Modele
        r = user_req.post(route, data=payload)
        assert r.status_code == 201, r
        assert len(r.data['_items']) == 1
        # Delete Modele
        payload["plages"] = []
        r = user_req.patch(route, data=payload)
        assert r.status_code == 201, r
        assert len(r.data['_items']) == 0
