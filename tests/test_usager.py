import pytest
from datetime import datetime, timedelta
import copy

from tests import common
from tests.fixtures import *
from mongoengine import NotUniqueError

from sief.model.usager import Usager, is_adult
from sief.model.fichier import Fichier
from sief.permissions import POLICIES as p


@pytest.fixture
def photo(request):
    return Fichier(name='photo.png').save()


class TestUsager(common.BaseTest):

    def test_links_list(self, user_with_site_affecte):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.voir.name]
        user.save()
        r = user_req.get('/usagers')
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'root'])
        user.permissions.append(p.usager.creer.name)
        user.save()
        r = user_req.get('/usagers')
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'create', 'root'])

    def test_links_single(self, user_with_site_affecte, usager):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.voir.name]
        user.save()
        route = '/usagers/%s' % usager.pk
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'parent', 'localisations'])
        user.permissions.append(p.usager.modifier.name)
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'update', 'parent', 'localisations',
                                'localisation_update'])
        user.permissions = [p.usager.voir.name, p.historique.voir.name]
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'history', 'parent', 'localisations'])

    def test_links_etat_civil(self, user_with_site_affecte, usager):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/usagers/%s' % usager.pk
        user.permissions = [p.usager.voir.name, p.usager.etat_civil.modifier.name]
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'parent', 'localisations', 'etat_civil_update'])
        user.permissions = [p.usager.voir.name, p.usager.etat_civil.valider.name]
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'parent', 'localisations', 'etat_civil_valider'])
        usager.ecv_valide = True
        usager.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'parent', 'localisations'])
        user.permissions.append(p.usager.etat_civil.modifier.name)
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'parent', 'localisations',
                                'etat_civil_update'])

    def test_update_usager(self, user_with_site_affecte, usager):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        payload = {'email': 'jdoe@test.com'}
        # Need permission to do it
        route = '/usagers/{}'.format(usager.pk)
        r = user_req.patch(route, data=payload)
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions = [p.usager.modifier.name]
        user.save()
        r = user_req.patch(route, data=payload)
        assert r.status_code == 200, r
        assert r.data.get('email', '<invalid>') == payload['email']

    def test_update_ofpra_usager(self, user_with_site_affecte, usager):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.modifier.name,
                            p.usager.modifier_ofpra.name]
        user.save()
        route = '/usagers/{}'.format(usager.pk)
        # Must use a route to validate etat-civil
        r = user_req.patch(route, data={'ecv_valide': True})
        assert r.status_code == 400, r
        # Test ofpra field modification
        r = user_req.patch(route, data={'enfant_de_refugie': True})
        assert r.status_code == 200, r
        # Non-ofpra fields cannot be touched
        for bad_payload in ({'identifiant_dna': 'cannot_set_me'},
                            {'identifiant_agdref': 'cannot_set_me'}):
            r = user_req.patch(route, data=bad_payload)
            assert r.status_code == 400, r

    def test_update_photo_usager(self, user_with_site_affecte, usager, photo):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.modifier.name,
                            p.usager.modifier_ofpra.name,
                            p.usager.etat_civil.modifier.name]
        user.save()
        route = '/usagers/{}/etat_civil'.format(usager.pk)
        # Must use a route to validate etat-civil
        r = user_req.patch(route, data={'photo': str(photo.pk)})
        assert r.status_code == 403, r
        # Test ofpra field modification
        user.permissions.append(p.usager.etat_civil.modifier_photo.name)
        user.save()
        r = user_req.patch(route, data={'photo': str(photo.pk)})
        assert r.status_code == 200, r

    def test_create_usager(self, user_with_site_affecte, usager_payload):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        # Need permission to do it
        r = user_req.post('/usagers', data=usager_payload)
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions = [p.usager.creer.name]
        user.save()
        r = user_req.post('/usagers', data=usager_payload)
        assert r.status_code == 201, r

    def test_update_etat_civil(self, user_with_site_affecte, usager, ref_nationalites):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        nat = ref_nationalites[1]
        # Need permission to do it
        route = '/usagers/{}/etat_civil'.format(usager.pk)
        payload = {'nom': 'Caesaire',
                   'nationalites': [{'code': str(nat.pk)}]}
        r = user_req.patch(route, data=payload)
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions = [p.usager.modifier.name,
                            p.usager.etat_civil.modifier.name]
        user.save()
        # Cannot change the etat civil with the main route
        r = user_req.patch('/usagers/{}'.format(usager.pk),
                           data=payload)
        assert r.status_code == 400, r
        # Now the correct one
        user.permissions = [p.usager.etat_civil.modifier.name]
        user.save()
        r = user_req.patch(route, data=payload)
        assert r.status_code == 200, r
        assert r.data.get('nom', '<invalid>') == 'Caesaire'
        assert r.data['nationalites'] == [{'code': str(nat.pk),
                                           'libelle': nat.libelle}]
        # Cannot use the etat civil route to update everything
        r = user_req.patch(route.format(usager.pk),
                           data={'email': 'kaiser@test.com'})
        assert r.status_code == 400, r

    def test_localisations(self, user_with_site_affecte, usager):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.voir.name, p.usager.modifier.name]
        user.save()
        payload_portail = {
            'adresse': {
                "ville": "Saint-Sylvain-d'Anjou",
                "code_insee": "49323",
                "code_postal": "49480",
                "voie": "Rue du Dery",
                "numero_voie": "49",
            },
            "organisme_origine": "PORTAIL"
        }
        payload_portail_two = {
            'adresse': {
                "ville": "Saint-Sylvain-d'Anjou",
                "code_insee": "49323",
                "code_postal": "49480",
                "voie": "Rue du Dery",
                "numero_voie": "48",
            },
            "organisme_origine": "PORTAIL"
        }
        payload_dna = {
            'adresse': {
                "ville": "Saint-Sylvain-d'Anjou",
                "code_insee": "49323",
                "code_postal": "49480",
                "voie": "Rue du Dery",
                "numero_voie": "47",
            },
            "organisme_origine": "DNA"
        }
        route = '/usagers/{}'.format(usager.pk)
        r = user_req.get(route)
        assert r.status_code == 200, r
        r = user_req.post(route + '/localisations', data=payload_dna)
        assert r.status_code == 200, r
        assert 'localisation' not in r.data
        # Cannot change localisation in the main route
        r = user_req.patch(route, data={'localisation': payload_portail})
        assert r.status_code == 400, r
        r = user_req.patch(route, data={'localisations': [payload_portail]})
        assert r.status_code == 400, r
        r = user_req.post(route + '/localisations', data=payload_portail)
        assert r.status_code == 200, r
        r = user_req.post(route + '/localisations', data=payload_portail_two)
        assert r.status_code == 200, r
        r = user_req.post(route + '/localisations', data=payload_dna)
        assert r.status_code == 200, r
        # Make sure we only have the last portail localisation in the main get
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert 'localisations' not in r.data
        assert r.data['localisation']['adresse'] == payload_portail_two['adresse']
        assert r.data['localisation']['organisme_origine'] == 'PORTAIL'
        r = user_req.post(route + '/localisations', data=payload_portail)
        assert r.status_code == 200, r
        r = user_req.get(route + '/localisations')
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 5, r
        r = user_req.post(route + '/localisations', data={
            'adresse': {
                "ville": "Saint-Sylvain-d'Anjo",
                "code_insee": None,
                "voie": "Rue du Dery",
                "numero_voie": "49",
            },
            "organisme_origine": "PORTAIL"})
        assert r.status_code == 200, r

    def test_bad_create_usager(self, user_with_site_affecte, usager_payload):
        user = user_with_site_affecte
        default_payload = usager_payload
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.creer.name]
        user.save()
        for route, value in [("id", "554534801d41c8de989d038e"),  # id is read only
                             ("unknown", "field"), ('sexe', common.NOT_SET),
                             ("sexe", "male"), ("nom", None), ("prenoms", None),
                             ("nom", common.NOT_SET), ("prenoms", common.NOT_SET),
                             ("nom", ''), ("prenoms", []), ("prenoms", 'Aimé'),
                             ("date_naissance", "1880-12-31T23:59:59+00:00")]:
            payload = default_payload.copy()
            common.update_payload(payload, route, value)
            r = user_req.post('/usagers', data=payload)
            assert r.status_code == 400, (route, value)

    def test_valider_etat_civil(self, user_with_site_affecte, usager,
                                ref_pays, ref_nationalites, photo):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/usagers/{}/etat_civil'.format(usager.pk)
        nat = ref_nationalites[1]
        payload = {
            'nom': 'Caesaire',
            'nationalites': [{'code': str(nat.pk)}],
            'situation_familiale': 'VEUF',
            'sexe': 'M',
            'prenoms': ["Aimé", "Fernand", "David"],
            'ville_naissance': 'Basse-Pointe',
            'photo': str(photo.pk),
            'nom_usage': None,
            'pays_naissance': str(ref_pays[0].pk),
            "date_naissance": datetime(1913, 6, 26).isoformat(),
            'date_naissance_approximative': False,
        }
        # Need permission to do it
        r = user_req.post(route, data=payload)
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions = [p.usager.etat_civil.valider.name]
        user.save()
        # Must provide the etat civil to validate it
        r = user_req.post(route)
        assert r.status_code == 400
        # All fields must be present to validate the etat civil
        bad_payload = copy.deepcopy(payload)
        del bad_payload['prenoms']
        del bad_payload['nom_usage']
        r = user_req.post(route, data=bad_payload)
        assert r.status_code == 400, r
        assert 'prenoms' in r.data
        assert 'nom_usage' in r.data
        r = user_req.post(route, data=payload)
        assert r.status_code == 200, r
        # Now cannot change the etat_civil without proper rights
        user.permissions = [p.usager.etat_civil.modifier.name]
        user.save()
        assert r.data['nom'] == 'Caesaire'
        r = user_req.patch(route, data={'prenoms': ['Aimé', 'Prospère']})
        assert r.status_code == 403, r
        user.permissions = [p.usager.etat_civil.modifier.name,
                            p.usager.etat_civil.valider.name]
        user.save()
        r = user_req.patch(route, data={'prenoms': ['Aimé', 'Prospère']})
        assert r.status_code == 200, r

    def test_valider_etat_civil_no_photo(self, user_with_site_affecte, usager,
                                         ref_pays, ref_nationalites, photo):
        user = user_with_site_affecte
        user.permissions = [p.usager.etat_civil.valider.name]
        user.save()
        usager.photo = photo
        usager.save()
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/usagers/{}/etat_civil'.format(usager.pk)
        nat = ref_nationalites[1]
        payload = {
            'nom': 'Caesaire',
            'nationalites': [{'code': str(nat.pk)}],
            'situation_familiale': 'VEUF',
            'sexe': 'M',
            'prenoms': ["Aimé", "Fernand", "David"],
            'ville_naissance': 'Basse-Pointe',
            'nom_usage': None,
            'pays_naissance': str(ref_pays[0].pk),
            "date_naissance": datetime(1913, 6, 26).isoformat(),
            'date_naissance_approximative': False,
        }
        r = user_req.post(route, data=payload)
        assert r.status_code == 200, r
        assert r.data['photo']['id'] == str(photo.pk)

    def test_agdref_update(self, user_with_site_affecte, usager):
        user = user_with_site_affecte
        payload = {
            'identifiant_agdref': 'new_agdref',  # len must be 10
            'date_enregistrement_agdref': datetime.utcnow(),
            'date_naturalisation': datetime.utcnow(),
            'eloignement': {'date_decision': datetime.utcnow()},
            'date_fuite': datetime.utcnow()
        }
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/usagers/{}'.format(usager.pk)
        user.permissions = [p.usager.modifier.name]
        user.save()
        r = user_req.patch(route, data=payload)
        assert r.status_code == 400, r
        # Special permission allow special modifications
        user.permissions.append(p.usager.modifier_agdref.name)
        user.save()
        r = user_req.patch(route, data=payload)
        assert r.status_code == 200, r

    def test_bad_agdref_update(self, user_with_site_affecte, usager):
        user = user_with_site_affecte
        default_payload = {
            'identifiant_agdref': 'new_agdref',  # len must be 10
            'date_enregistrement_agdref': datetime.utcnow(),
        }
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/usagers/{}'.format(usager.pk)
        user.permissions = [p.usager.modifier.name,
                            p.usager.modifier_agdref.name]
        user.save()
        for key, value in [("identifiant_agdref", "too_long_for_agdref"),
                           ("identifiant_agdref", "too_short"),
                           ("bad_field", 'dummy'),
                           ('identifiant_dna', '<dummy_dna_familly_id>'),
                           ('nom', "Shouldn't"),
                           ('id', '42')]:
            payload = default_payload.copy()
            common.update_payload(payload, key, value)
            r = user_req.patch(route, data=payload)
            assert r.status_code == 400, (key, value)

    def test_ofii_update(self, user_with_site_affecte, usager):
        user = user_with_site_affecte
        payload = {
            'identifiant_dna': '<dna_id>',
            'date_dna': datetime.utcnow(),
            'identifiant_famille_dna': '<dna_fam_id>',
            'vulnerabilite': {
                'date_saisie': '15/09/2015',
                'objective': False,
                'grossesse': True,
                'grossesse_date_terme': '15/01/2015',
                'malvoyance': False,
                'malentendance': False,
                'interprete_signe': False,
                'mobilite_reduite': False,
                'absence_raison_medicale': True
            }
        }
        # Special permission allow special modifications
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/usagers/{}'.format(usager.pk)
        user.permissions = [p.usager.modifier.name]
        user.save()
        r = user_req.patch(route, data=payload)
        assert r.status_code == 400, r
        user.permissions.append(p.usager.modifier_ofii.name)
        user.save()
        r = user_req.patch(route, data=payload)
        assert r.status_code == 200, r
        for field in ('date_saisie', 'objective', 'grossesse',
                      'grossesse_date_terme', 'malvoyance', 'malentendance',
                      'interprete_signe', 'mobilite_reduite', 'absence_raison_medicale'):
            assert r.data['vulnerabilite'].get(field) is not None, field

    def test_par_identifiant_agdref_search(self, user, usager):
        # Special permission allow special modifications
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.voir.name, p.usager.prefecture_rattachee.sans_limite.name]
        user.save()
        usager.identifiant_agdref = '1234567890'
        usager.save()
        r = user_req.get('/usagers/%s?par_identifiant_agdref' % usager.identifiant_agdref)
        assert r.status_code == 200, r
        r = user_req.get('/usagers/%s?par_identifiant_agdref' % usager.pk)
        assert r.status_code == 404, r
        r = user_req.get('/usagers/777777?par_identifiant_agdref')
        assert r.status_code == 404, r
        # Special case : id starting by 0
        usager.identifiant_agdref = '0004567890'
        usager.save()
        r = user_req.get('/usagers/{}?par_identifiant_agdref'.format(usager.identifiant_agdref))
        assert r.status_code == 200, r

    def test_duplicated_ids(self, usager_payload):
        # Start by creating a lot of usagers
        agdref_id = "0123456789"
        dna_id = "123456789"
        new_user = Usager(
            identifiant_agdref=agdref_id,
            identifiant_dna=dna_id,
            **usager_payload).save()
        with pytest.raises(NotUniqueError):
            Usager(identifiant_agdref=agdref_id, **usager_payload).save()
        with pytest.raises(NotUniqueError):
            Usager(identifiant_dna=dna_id, **usager_payload).save()


class TestPaginationUsager(common.BaseTest):

    def test_paginate_usager(self, user_with_site_affecte, usager_payload):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.voir.name,
                            p.usager.prefecture_rattachee.sans_limite.name]
        user.save()
        # Start by creating a lot of usagers
        for i in range(1, 26):
            usager_payload['nom'] = 'Usager-%s' % chr(ord('a') + i)
            new_user = Usager(**usager_payload)
            new_user.save()
        for i in range(1, 26):
            usager_payload['nom'] = 'Usager-%s' % chr(ord('A') + i)
            new_user = Usager(**usager_payload)
            new_user.save()
        # Now let's test the pagination !
        common.pagination_testbed(user_req, '/usagers')


class TestExportUsager(common.BaseSolrTest):

    def test_export_usager(self, user_with_site_affecte, usager_payload):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.voir.name,
                            p.usager.prefecture_rattachee.sans_limite.name,
                            p.usager.export.name]
        user.save()

        # Step 1 : Start by creating 25 usagers
        date_from = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        for i in range(0, 25):
            usager_payload['nom'] = 'Usager-%s' % chr(ord('a') + i)
            new_user = Usager(**usager_payload)
            new_user.save()
        date_to_1 = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)

        route = '/usagers/export?fq=doc_created:[%s TO %s]&per_page=20&page=1' % (
            date_from, date_to_1)
        r = user_req.get(route)
        assert r.status_code == 200, r
        next_route = '/usagers/export?q=*:*&fq=doc_created:[%s TO %s]&per_page=20&page=2' % (
            date_from, date_to_1)
        assert r.data['_links'].get('next', None) == next_route
        assert r.data['_meta']['total'] == 25

        route = '/usagers/export?fq=doc_created:[%s TO %s]&page=2&per_page=20' % (
            date_from, date_to_1)
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['_links'].get('next', None) is None
        assert r.data['_meta']['total'] == 25

        # Step 2 : Create 25 new usagers
        for i in range(0, 25):
            usager_payload['nom'] = 'Usager-%s' % chr(ord('A') + i)
            new_user = Usager(**usager_payload)
            new_user.save()
        date_to_2 = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)

        route = '/usagers/export?fq=doc_created:[%s TO %s]&per_page=100' % (
            date_from, date_to_1)
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['_links'].get('next', None) is None
        assert r.data['_meta']['total'] == 25

        route = '/usagers/export?fq=doc_created:[%s TO %s]&per_page=100' % (
            date_from, date_to_2)
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['_links'].get('next', None) is None
        assert r.data['_meta']['total'] == 50

        route = '/usagers/export'
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['_links'].get('next', None) == '/usagers/export?per_page=20&page=2'
        assert r.data['_meta']['total'] == 50


class TestUnitUsager(common.BaseTest):

    def test_is_adult(self):
        usager = Usager()
        # Cannot determine the age
        assert is_adult(usager) is None

        today = datetime.now()
        birthday = datetime(today.year - 18, today.month, today.day)
        # Adult
        usager.date_naissance = birthday - timedelta(days=1)
        assert is_adult(usager) is True
        # Adult Birthday
        usager.date_naissance = birthday
        assert is_adult(usager) is True
        # Child
        usager.date_naissance = birthday + timedelta(days=1)
        assert is_adult(usager) is False
