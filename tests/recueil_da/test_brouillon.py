import pytest
from datetime import datetime, timedelta
from workdays import workday as add_days
import copy

from tests import common
from tests.fixtures import *
from tests.test_rendez_vous import add_free_creneaux

from sief.model.recueil_da import RecueilDA
from sief.model.fichier import Fichier
from sief.model.site import Creneau
from sief.permissions import POLICIES as p


def brouillon_payload():
    return {
        'usager_1': {
            'date_entree_en_france': datetime(1952, 1, 1),
            'date_depart':  datetime(1952, 1, 1),
            'date_depart_approximative': False,
            'date_entree_en_france_approximative': False,
            'nom': 'Plantagenêt', 'prenoms': ['Geoffroy', 'V'], 'sexe': 'M',
            'acceptation_opc': False,
            'date_naissance': datetime(1913, 8, 24),
            "ville_naissance": "Château-du-Loir",
            "nom_pere": "Foulque",
            "prenom_pere": "V",
            "nom_mere": "Erembourge",
            "prenom_mere": "Du Maine",
            "situation_familiale": "MARIE",
            "condition_entree_france": "REGULIERE",
            "present_au_moment_de_la_demande": False,
        },
        'usager_2': {
            'nom': "D'Angleterre", 'prenoms': ['Mathilde'], 'sexe': 'F',
            'date_naissance_approximative': True,
            "date_entree_en_france": datetime.utcnow(),
        },
        'enfants': [
            {
                'nom': 'Plantagenêt',
                'prenoms': ['Geoffroy', 'VI'],
                'sexe': 'M',
                'usager_1': True,
                'situation_familiale': 'CELIBATAIRE',
            },
            {
                'nom': 'Fitz-Emperesse',
                'prenoms': ['Guillaume'],
                'sexe': 'M',
                'usager_1': True,
                'usager_2': False,
                'situation_familiale': 'CELIBATAIRE',
            }
        ]
    }


@pytest.fixture
def brouillon(request, site_structure_accueil):
    u = user(request, nom='Brouillon', prenom='Setter')
    u.test_set_accreditation(site_affecte=site_structure_accueil)
    u.save()
    recueil = RecueilDA(structure_accueil=site_structure_accueil,
                        agent_accueil=u)
    recueil.save()
    return recueil


@pytest.fixture
def payload_pa_fini(ref_langues_iso, ref_langues_ofpra, ref_nationalites, ref_pays):
    photo = Fichier(name='photo.png').save()
    payload = brouillon_payload()
    payload['profil_demande'] = 'FAMILLE'
    payload['usager_1']['demandeur'] = True
    payload['usager_1']['type_demande'] = 'PREMIERE_DEMANDE_ASILE'

    payload['usager_1']['present_au_moment_de_la_demande'] = True
    payload['usager_1']['langues'] = [{'code': str(ref_langues_iso[0].pk)}]
    payload['usager_1']['langues_audition_OFPRA'] = [{'code': str(ref_langues_ofpra[0].pk)}]
    payload['usager_1']['adresse'] = {'pays': {'code': str(ref_pays[0].pk)}}
    payload['usager_1']['pays_naissance'] = {'code': str(ref_pays[1].pk)}
    payload['usager_1']['nationalites'] = [{'code': str(ref_nationalites[1].pk)}]
    payload['usager_1']['nom_pere'] = "V d'Anjou"
    payload['usager_1']['date_entree_en_france'] = datetime.utcnow()
    payload['usager_1']['prenom_pere'] = "Foulque"
    payload['usager_1']['situation_familiale'] = "CONCUBIN"
    payload['usager_1']['photo_premier_accueil'] = str(photo.pk)
    payload['usager_1']['vulnerabilite'] = {'mobilite_reduite': False}
    payload['usager_1']['identite_approchante_select'] = True
    for field in ('date_entree_en_france', 'date_depart',
                  'date_depart_approximative',
                  'date_entree_en_france_approximative'):
        payload['usager_2'][field] = payload['usager_1'][field]
    payload['usager_2']['demandeur'] = True
    payload['usager_2']['type_demande'] = 'PREMIERE_DEMANDE_ASILE'

    payload['usager_2']['date_entree_en_france'] = datetime.utcnow()
    payload['usager_2']['present_au_moment_de_la_demande'] = True
    payload['usager_2']['date_naissance'] = datetime(1956, 1, 1)
    payload['usager_2']['ville_naissance'] = "Rambouillet"
    payload['usager_2']['pays_naissance'] = {'code': str(ref_pays[0].pk)}
    payload['usager_2']['nationalites'] = [{'code': str(ref_nationalites[1].pk)}]
    payload['usager_2']['langues'] = [{'code': str(ref_langues_iso[1].pk)}]
    payload['usager_2']['langues_audition_OFPRA'] = [{'code': str(ref_langues_ofpra[1].pk)}]
    payload['usager_2']['adresse'] = {'pays': {'code': str(ref_pays[0].pk)}}
    payload['usager_2']['nom_pere'] = "Ier D'Angleterre"
    payload['usager_2']['prenom_pere'] = "Henri"
    payload['usager_2']['photo_premier_accueil'] = str(photo.pk)
    payload['usager_2']['vulnerabilite'] = {'mobilite_reduite': False}
    payload['usager_2']['identite_approchante_select'] = True
    payload['enfants'][0]['demandeur'] = False
    payload['enfants'][0]['present_au_moment_de_la_demande'] = True
    payload['enfants'][0]['nationalites'] = [{'code': str(ref_nationalites[1].pk)}]
    payload['enfants'][0]['adresse'] = {'pays': {'code': str(ref_pays[0].pk)}}
    payload['enfants'][0]['date_naissance'] = datetime(1976, 2, 1)
    payload['enfants'][0]['ville_naissance'] = "Rambouillet"
    payload['enfants'][0]['pays_naissance'] = {'code': str(ref_pays[0].pk)}
    payload['enfants'][0]['nom_pere'] = "Plantagenêt"
    payload['enfants'][0]['prenom_pere'] = "Geoffroy"
    payload['enfants'][0]['vulnerabilite'] = {'mobilite_reduite': False}
    payload['enfants'][0]['identite_approchante_select'] = True
    payload['enfants'][1]['demandeur'] = False
    payload['enfants'][1]['present_au_moment_de_la_demande'] = False
    payload['enfants'][1]['langues'] = [{'code': str(ref_langues_iso[0].pk)}]
    payload['enfants'][1]['langues_audition_OFPRA'] = [{'code': str(ref_langues_ofpra[0].pk)}]
    payload['enfants'][1]['nationalites'] = [{'code': str(ref_nationalites[1].pk)}]
    payload['enfants'][1]['adresse'] = {'pays': {'code': str(ref_pays[0].pk)}}
    payload['enfants'][1]['date_naissance'] = datetime(1978, 2, 1)
    payload['enfants'][1]['ville_naissance'] = "Rambouillet"
    payload['enfants'][1]['pays_naissance'] = {'code': str(ref_pays[0].pk)}
    payload['enfants'][1]['nom_pere'] = "Plantagenêt"
    payload['enfants'][1]['prenom_pere'] = "Geoffroy"
    payload['enfants'][1]['vulnerabilite'] = {'mobilite_reduite': False}
    payload['enfants'][1]['identite_approchante_select'] = True
    return payload


class TestRecueilDABrouillon(common.BaseTest):

    def test_get_recueil_da(self, user, site_prefecture, brouillon):
        user_req = self.make_auth_request(user, user._raw_password)
        r = user_req.get('/recueils_da')
        assert r.status_code == 403, r
        route = '/recueils_da/%s' % brouillon.pk
        r = user_req.get(route)
        assert r.status_code == 403, r
        # Provide permission
        user.permissions = [p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]
        user.save()
        r = user_req.get('/recueils_da')
        assert r.status_code == 200, r
        r = user_req.get(route)
        assert r.status_code == 200, r
        # Now limit the view to the user's site_affecte
        user.permissions = [p.recueil_da.voir.name]
        user.test_set_accreditation(site_affecte=site_prefecture)
        user.save()
        r = user_req.get('/recueils_da')
        assert r.status_code == 200, r
        assert len(r.data['_items']) == r.data['_meta']['total'] == 0
        r = user_req.get(route)
        assert r.status_code == 403, r
        # Set the right site_affecte and retry
        user.test_set_accreditation(site_affecte=brouillon.structure_accueil)
        user.save()
        r = user_req.get('/recueils_da')
        assert r.status_code == 200, r
        r = user_req.get(route)
        assert r.status_code == 200, r

    def test_get_links(self, user, brouillon):
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/recueils_da/%s' % brouillon.pk
        user.permissions = [p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]
        user.save()
        r = user_req.get('/recueils_da')
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ('self', 'root'))
        user.permissions.append(p.recueil_da.creer_brouillon.name)
        user.save()
        r = user_req.get('/recueils_da')
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ('self', 'root', 'create_brouillon'))
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ('self', 'parent'))
        user.permissions.append(p.recueil_da.modifier_brouillon.name)
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ('self', 'parent', 'replace',
                                'pa_realiser', 'delete'))

    def test_create_recueil_da(self, user, site_structure_accueil):
        user_req = self.make_auth_request(user, user._raw_password)
        user_site_affecte = site_structure_accueil
        user.test_set_accreditation(site_affecte=user_site_affecte)
        user.save()
        # recueil_da can be created empty
        payload = {}
        # Need permission to do it
        r = user_req.post('/recueils_da', data=payload)
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]
        user.save()
        r = user_req.post('/recueils_da', data=payload)
        assert r.status_code == 201, r
        # `structure_accueil` and `agent_accueil` should have been set
        route = '/recueils_da/%s' % r.data['id']
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert (r.data.get('structure_accueil', '<not_set>')['id'] ==
                str(user_site_affecte.pk))
        assert r.data.get('agent_accueil', '<not_set>')['id'] == str(user.pk)

    def test_recueil_da_mobilite_reduite_is_false(self, user, site_structure_accueil):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(site_affecte=site_structure_accueil)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]
        user.save()
        payload = brouillon_payload()
        payload['usager_1']['vulnerabilite'] = {'mobilite_reduite': False}
        payload['usager_2']['vulnerabilite'] = {'mobilite_reduite': False}
        for enfant in payload['enfants']:
            enfant['vulnerabilite'] = {'mobilite_reduite': False}

        r = user_req.post('/recueils_da', data=payload)
        route = '/recueils_da/%s' % r.data['id']

        result = user_req.get(route)
        assert result.data['usager_1']['vulnerabilite']['mobilite_reduite'] == False
        assert result.data['usager_2']['vulnerabilite']['mobilite_reduite'] == False
        assert result.data['enfants'][0]['vulnerabilite']['mobilite_reduite'] == False
        assert result.data['enfants'][1]['vulnerabilite']['mobilite_reduite'] == False

    def test_recueil_da_mobilite_reduite_undefined(self, user, site_structure_accueil):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(site_affecte=site_structure_accueil)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]
        user.save()

        r = user_req.post('/recueils_da', data=brouillon_payload())
        route = '/recueils_da/%s' % r.data['id']

        result = user_req.get(route)
        assert 'vulnerabilite' not in result.data['usager_1']
        assert 'vulnerabilite' not in result.data['enfants'][0]

    def test_recueil_da_mobilite_reduite_is_true(self, user, site_structure_accueil):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(site_affecte=site_structure_accueil)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]
        user.save()
        payload = brouillon_payload()
        payload['usager_1']['vulnerabilite'] = {'mobilite_reduite': True}
        for enfant in payload['enfants']:
            enfant['vulnerabilite'] = {'mobilite_reduite': True}
        r = user_req.post('/recueils_da', data=payload)
        route = '/recueils_da/%s' % r.data['id']
        result = user_req.get(route)
        assert result.data['usager_1']['vulnerabilite']['mobilite_reduite'] == True
        assert result.data['enfants'][0]['vulnerabilite']['mobilite_reduite'] == True
        assert result.data['enfants'][1]['vulnerabilite']['mobilite_reduite'] == True

    def test_bad_create_recueil_da(self, user, site_structure_accueil):
        user_req = self.make_auth_request(user, user._raw_password)
        payload = {}
        # user must have a site_affecte to create a recueil_da
        user.permissions = [p.recueil_da.creer_brouillon.name]
        user.save()
        r = user_req.post('/recueils_da', data=payload)
        assert r.status_code == 400, r
        user_site_affecte = site_structure_accueil
        user.test_set_accreditation(site_affecte=user_site_affecte)
        user.save()
        # Send various dummy payloads
        r = user_req.post('/recueils_da', data={'bad': "doesn't exists"})
        assert r.status_code == 400, r
        # Try to force structure_accueil and agent_accueil
        r = user_req.post('/recueils_da', data={'statut': 'ANNULE'})
        assert r.status_code == 403, r
        r = user_req.post('/recueils_da', data={'statut': 'PA_REALISE'})
        assert r.status_code == 403, r
        r = user_req.post('/recueils_da',
                          data={'structure_accueil': str(user_site_affecte.pk)})
        assert r.status_code == 400, r
        r = user_req.post('/recueils_da', data={'agent_accueil': str(user.pk)})
        assert r.status_code == 400, r

    def test_delete_brouillon(self, user, site_prefecture, brouillon):
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/recueils_da/%s' % str(brouillon.pk)
        r = user_req.delete(route)
        assert r.status_code == 403, r
        user.permissions = [p.recueil_da.modifier_brouillon.name]
        user.test_set_accreditation(site_affecte=site_prefecture)
        user.save()
        r = user_req.delete(route)
        assert r.status_code == 403, r
        user.test_set_accreditation(site_affecte=brouillon.structure_accueil)
        user.save()
        r = user_req.delete(route)
        assert r.status_code == 204, r
        user.permissions = [p.recueil_da.voir.name]
        user.save()
        r = user_req.get(route)
        assert r.status_code == 404, r

    def test_replace_brouillon(self, user, site_prefecture, brouillon):
        user.test_set_accreditation(site_affecte=site_prefecture)
        user.save()
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/recueils_da/%s' % str(brouillon.pk)
        payload = brouillon_payload()
        r = user_req.put(route, data=payload)
        assert r.status_code == 403, r
        user.permissions = [p.recueil_da.modifier_brouillon.name]
        user.save()
        r = user_req.put(route, data=payload)
        assert r.status_code == 403, r
        user.test_set_accreditation(site_affecte=brouillon.structure_accueil)
        user.save()
        r = user_req.put(route, data=payload)
        assert r.status_code == 200, r
        # Try few elements of the result
        assert r.data['usager_1']['prenom_mere'] == payload['usager_1']['prenom_mere']
        assert r.data['usager_2']['prenoms'] == payload['usager_2']['prenoms']
        assert len(r.data['enfants']) == len(payload['enfants'])
        assert r.data.get('structure_accueil', None)
        assert r.data.get('agent_accueil', None)

    def test_bad_replace_brouillon(self, user, site_structure_accueil, brouillon):
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/recueils_da/%s' % str(brouillon.pk)
        user.permissions = [p.recueil_da.modifier_brouillon.name]
        user.test_set_accreditation(site_affecte=brouillon.structure_accueil)
        user.save()
        for key, value in (('usager_1', 'must_be_dict'),
                           ('usager_1.prenome_mere', "old bug..."),
                           ('usager_1.nom', "'"),
                           ('usager_1.nom', "-"),
                           ('usager_1.nom', ""),
                           ('usager_1.nom', "badend'"),
                           ('usager_1.nom', "badend-"),
                           ('usager_1.nom', ""),
                           ('usager_1.sexe', "other"),
                           ('usager_1.invalid_field', "doesn't exist"),
                           ('usager_1.motif_refus', "Cannot set this field"),
                           ('usager_1.date_notification_refus', datetime.utcnow()),
                           ('usager_2', 'must_be_dict'),
                           ('usager_2.demandeur', 'not_a_boolean'),
                           ('usager_2', []),
                           ('enfants', 'must_be_list'),
                           ('enfants', ['list', 'of', 'dicts']),
                           ('enfants.1', 'must_be_dict'),
                           ('enfants.1', []),
                           ('id', '559401b813adf24c51910d74'),
                           ('_version', 4),
                           ('_links', {'self': '/wtf'}),
                           ):
            payload = brouillon_payload()
            common.update_payload(payload, key, value)
            r = user_req.put(route, data=payload)
            assert r.status_code == 400, (key, value)

    def test_recueil_en_reexamen(self, user, brouillon):

        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name, p.recueil_da.modifier_brouillon.name]
        user.test_set_accreditation(site_affecte=brouillon.structure_accueil)
        user.save()
        payload = brouillon_payload()
        payload['usager_1']['type_demande'] = 'PREMIERE_DEMANDE_ASILE'  # Premier cas simple.
        ret = user_req.post('/recueils_da', data=payload)
        assert ret.status_code == 201
        assert ret.data['usager_1']['type_demande'] == 'PREMIERE_DEMANDE_ASILE'
        assert 'numero_reexamen' not in ret.data

        payload['usager_1']['type_demande'] = 'REEXAMEN'
        ret = user_req.post('/recueils_da', data=payload)
        assert ret.status_code == 201

        payload['usager_1']['type_demande'] = 'REEXAMEN'
        payload['usager_1']['numero_reexamen'] = 'aaa'
        ret = user_req.post('/recueils_da', data=payload)
        assert ret.status_code == 400

        payload['usager_1']['type_demande'] = 'REEXAMEN'
        payload['usager_1']['numero_reexamen'] = '1'
        ret = user_req.post('/recueils_da', data=payload)
        assert ret.status_code == 201
        assert ret.data['usager_1']['type_demande'] == 'REEXAMEN'
        assert ret.data['usager_1']['numero_reexamen'] == 1

        payload['usager_1']['type_demande'] = 'REOUVERTURE_DOSSIER'
        del payload['usager_1']['numero_reexamen']
        ret = user_req.post('/recueils_da', data=payload)
        assert ret.status_code == 201
        assert ret.data['usager_1']['type_demande'] == 'REOUVERTURE_DOSSIER'

        payload['usager_1']['type_demande'] = 'REEXAMEN'
        payload['usager_1']['numero_reexamen'] = 2
        ret = user_req.post('/recueils_da', data=payload)
        assert ret.status_code == 201
        assert ret.data['usager_1']['type_demande'] == 'REEXAMEN'
        assert ret.data['usager_1']['numero_reexamen'] == 2

    def test_type_recueil_en_reexamen(self, user, brouillon):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name, p.recueil_da.modifier_brouillon.name]
        user.test_set_accreditation(site_affecte=brouillon.structure_accueil)
        user.save()

        payload = brouillon_payload()
        payload['usager_1']['type_demande'] = 'REEXAMEN'
        ret = user_req.post('/recueils_da', data=payload)
        assert ret.status_code == 201

        payload['usager_1']['type_demande'] = 'REEXAMEN'
        payload['usager_1']['numero_reexamen'] = -2
        ret = user_req.post('/recueils_da', data=payload)
        assert ret.status_code == 400

        payload['usager_1']['type_demande'] = 'REEXAMEN'
        payload['usager_1']['numero_reexamen'] = 0
        r = user_req.post('/recueils_da', data=payload)
        assert r.status_code == 400

        payload['usager_1']['type_demande'] = 'REEXAMEN'
        payload['usager_1']['numero_reexamen'] = 2
        ret = user_req.post('/recueils_da', data=payload)
        assert ret.status_code == 201
        assert ret.data['usager_1']['type_demande'] == 'REEXAMEN'
        assert ret.data['usager_1']['numero_reexamen'] == 2


class TestRecueilDASwitchToPARealise(common.BaseTest):

    def setup(self):
        Creneau.drop_collection()

    def test_get_creneaux(self, user, site_structure_accueil, payload_pa_fini):
        from workdays import workday as add_days

        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name]

        # Create creneaux
        # Must remove hours to avoid switching to the next day by creating
        # consecutive creneaux when the tests are run near midnight
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        next_day = add_days(today, 2)
        out_of_3days_creneau = add_days(today, 5)
        add_free_creneaux(2, site_structure_accueil.guichets_uniques[0])
        add_free_creneaux(3, site_structure_accueil.guichets_uniques[0], next_day)
        add_free_creneaux(4, site_structure_accueil.guichets_uniques[0], out_of_3days_creneau)

        user.test_set_accreditation(site_affecte=site_structure_accueil)
        user.save()
        r = user_req.post('/recueils_da', data=payload_pa_fini)
        assert r.status_code == 201, r
        route = '/recueils_da/%s' % r.data['id']

        # Get free creneaux (initial limite_rdv_jrs == 3)
        r = user_req.get(route + '/rendez_vous')
        assert r.status_code == 200, r
        # Only one GU
        assert len(r.data['_items']) == 1
        # Five free creneaux in GU1
        assert len(r.data['_items'][0]) == 5

        # Get first three days whith free creneaux
        site_structure_accueil.guichets_uniques[0].limite_rdv_jrs = 0
        site_structure_accueil.guichets_uniques[0].save()
        r = user_req.get(route + '/rendez_vous')
        assert r.status_code == 200, r
        # Only one GU
        assert len(r.data['_items']) == 1
        # Nine free creneaux in GU1
        assert len(r.data['_items'][0]) == 9

    def test_get_creneaux_no_limit_famille(self, user, site_structure_accueil, payload_pa_fini):
        from workdays import workday as add_days

        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.modifier_brouillon.name]
        user.test_set_accreditation(site_affecte=site_structure_accueil)
        user.save()
        # Create creneaux
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        out_of_3days_creneau = add_days(today, 5)
        add_free_creneaux(1, site_structure_accueil.guichets_uniques[0])
        add_free_creneaux(2, site_structure_accueil.guichets_uniques[0], out_of_3days_creneau)
        out_of_3days_creneau = add_days(out_of_3days_creneau, 1)
        add_free_creneaux(1, site_structure_accueil.guichets_uniques[0], out_of_3days_creneau)

        r = user_req.post('/recueils_da', data=payload_pa_fini)
        assert r.status_code == 201, r
        route = '/recueils_da/%s' % r.data['id']

        # Get first three days whith consecutive free creneaux
        site_structure_accueil.guichets_uniques[0].limite_rdv_jrs = 0
        site_structure_accueil.guichets_uniques[0].save()
        r = user_req.get(route + '/rendez_vous')
        assert r.status_code == 200, r
        # Only one GU
        assert len(r.data['_items']) == 1
        # Two consecutive free creneaux in GU1
        assert len(r.data['_items'][0]) == 2

    def test_switch_to_pa_realise(self, user, site_structure_accueil, payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.modifier_brouillon.name]
        add_free_creneaux(4, site_structure_accueil.guichets_uniques[0])
        user.test_set_accreditation(site_affecte=site_structure_accueil)
        user.save()
        r = user_req.post('/recueils_da', data=payload_pa_fini)
        assert r.status_code == 201, r

        route = '/recueils_da/%s' % r.data['id']

        r = user_req.get(route + '/rendez_vous')
        assert r.status_code == 200, r
        data = {'creneaux': [[r.data['_items'][0][0][0]['id']]]}
        r = user_req.put(route + '/pa_realise', data=data)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'PA_REALISE'
        # Bonus: test creneau view of the rdv
        user.permissions.append(p.site.voir.name)
        user.save()
        assert 'rendez_vous_gu' in r.data
        gu = r.data.get('structure_guichet_unique')
        assert gu
        for creneau in r.data['rendez_vous_gu']['creneaux']:
            creneau_route = creneau['_links']['self']
            r = user_req.get(creneau_route)
            assert r.status_code == 200, r
            assert r.data['site'] == gu
            assert r.data['reserve'] == True
            assert 'document_lie' in r.data
            assert r.data['document_lie']['_links']['self'].endswith(route)

    def test_switch_to_pa_realise_reexamen(self, user, site_structure_accueil, payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.modifier_brouillon.name]
        add_free_creneaux(4, site_structure_accueil.guichets_uniques[0])
        user.test_set_accreditation(site_affecte=site_structure_accueil)
        user.save()
        payload_pa_fini['usager_1']['type_demande'] = 'REEXAMEN'
        ret = user_req.post('/recueils_da', data=payload_pa_fini)
        assert ret.status_code == 201

        route = '/recueils_da/%s' % ret.data['id']

        r = user_req.get(route + '/rendez_vous')
        assert r.status_code == 200, r
        data = {'creneaux': [[r.data['_items'][0][0][0]['id']]]}
        r = user_req.put(route + '/pa_realise', data=data)
        assert r.status_code == 400, r
        payload_pa_fini['usager_1']['numero_reexamen'] = 1
        r = user_req.put(route, data=payload_pa_fini)
        assert r.status_code == 200
        r = user_req.put(route + '/pa_realise', data=data)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'PA_REALISE'
        # Bonus: test creneau view of the rdv
        user.permissions.append(p.site.voir.name)
        user.save()
        assert 'rendez_vous_gu' in r.data
        gu = r.data.get('structure_guichet_unique')
        assert gu
        for creneau in r.data['rendez_vous_gu']['creneaux']:
            creneau_route = creneau['_links']['self']
            r = user_req.get(creneau_route)
            assert r.status_code == 200, r
            assert r.data['site'] == gu
            assert r.data['reserve'] == True
            assert 'document_lie' in r.data
            assert r.data['document_lie']['_links']['self'].endswith(route)

    def test_switch_check_site(self, user, site_structure_accueil, site_prefecture,
                               payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.modifier_brouillon.name,
                            p.site.voir.name]
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        add_free_creneaux(4, site_prefecture, start=tomorrow)
        add_free_creneaux(4, site_structure_accueil.guichets_uniques[0],
                          start=add_days(tomorrow, 1))
        user.test_set_accreditation(site_affecte=site_structure_accueil)
        user.save()
        r = user_req.post('/recueils_da', data=payload_pa_fini)
        assert r.status_code == 201, r
        route = '/recueils_da/%s' % r.data['id']

        r = user_req.get(route + '/rendez_vous')
        assert r.status_code == 200, r
        data = {'creneaux': [[r.data['_items'][0][0][0]['id']]]}
        r = user_req.put(route + '/pa_realise', data=data)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'PA_REALISE'
        # Make sure the reserved creneaux are part of the correct site
        for c in r.data['rendez_vous_gu']['creneaux']:
            creneau_route = c['_links']['self']
            r = user_req.get(creneau_route)
            assert r.status_code == 200, r
            assert r.data['reserve'] == True
            assert r.data['site']['id'] == str(site_structure_accueil.guichets_uniques[0].id)

    def test_switch_but_not_rdv(self, user, site_structure_accueil, payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.modifier_brouillon.name]
        # We should be able to switch, but there is no creneaux available
        user.test_set_accreditation(site_affecte=site_structure_accueil)
        user.save()
        r = user_req.post('/recueils_da', data=payload_pa_fini)
        assert r.status_code == 201, r
        r = user_req.put('/recueils_da/%s/pa_realise' % r.data['id'], data={})
        assert r.status_code == 400, r

    def test_bad_switch_to_pa_realise(self, user, site_structure_accueil, payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.modifier_brouillon.name]
        user.test_set_accreditation(site_affecte=site_structure_accueil)
        user.save()
        creneaux = add_free_creneaux(4, site_structure_accueil.guichets_uniques[0])
        r = user_req.post('/recueils_da', data={})
        assert r.status_code == 201, r
        route = '/recueils_da/%s' % r.data['id']
        for key, value in (
            ('usager_1.demandeur', common.NOT_SET),
            ('usager_1.sexe', common.NOT_SET),
            ('usager_1.date_naissance', common.NOT_SET),
            ('usager_1.pays_naissance', common.NOT_SET),
            ('usager_1.ville_naissance', common.NOT_SET),
            ('usager_1.nationalites', common.NOT_SET),
            ('usager_2.demandeur', common.NOT_SET),
            ('usager_2.date_naissance', common.NOT_SET),
            ('usager_2.pays_naissance', common.NOT_SET),
            ('usager_2.ville_naissance', common.NOT_SET),
            ('usager_2.nationalites', common.NOT_SET),
            ('enfants.0.demandeur', common.NOT_SET),
            ('enfants.0.nom', common.NOT_SET),
            ('enfants.0.sexe', common.NOT_SET),
            ('enfants.0.prenoms', []),
            ('enfants.0.adresse', common.NOT_SET)
        ):
            payload = copy.deepcopy(payload_pa_fini)
            common.update_payload(payload, key, value)
            r = user_req.put(route, data=payload)
            assert r.status_code == 200, (key, value)
            r = user_req.put(route + '/pa_realise', data={})
            assert r.status_code == 400, (key, value)
            # Make sure all the creneaux are still free
            for c in creneaux:
                c.reload()
                assert not c.reserve, (c.linked_cls, c.linked_pk)

    def test_no_demandeurs_to_swtich(self, user, site_structure_accueil, payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.modifier_brouillon.name]
        user.test_set_accreditation(site_affecte=site_structure_accueil)
        user.save()
        creneaux = add_free_creneaux(4, site_structure_accueil.guichets_uniques[0])
        r = user_req.post('/recueils_da', data={})
        assert r.status_code == 201, r
        route = '/recueils_da/%s' % r.data['id']

        def cancel_demandeur(usager):
            usager['demandeur'] = False
            for field in ('date_entree_en_france', 'date_depart', 'photo', 'photo_premier_accueil'):
                if field in usager:
                    del usager[field]

        cancel_demandeur(payload_pa_fini['usager_1'])
        cancel_demandeur(payload_pa_fini['usager_2'])
        for child in payload_pa_fini['enfants']:
            cancel_demandeur(child)
        r = user_req.put(route, data=payload_pa_fini)
        assert r.status_code == 200, (key, value)
        r = user_req.put(route + '/pa_realise', data={})
        assert r.status_code == 400, (key, value)
        # Make sure all the creneaux are still free
        for c in creneaux:
            c.reload()
            assert not c.reserve, (c.linked_cls, c.linked_pk)

    def test_invalid_switches(self, user, site_structure_accueil, payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.modifier_brouillon.name,
                            p.recueil_da.modifier_pa_realise.name,
                            p.recueil_da.modifier_demandeurs_identifies.name,
                            p.recueil_da.modifier_exploite.name,
                            p.recueil_da.purger.name]
        user.test_set_accreditation(site_affecte=site_structure_accueil)
        user.save()
        r = user_req.post('/recueils_da', data=payload_pa_fini)
        assert r.status_code == 201, r
        route = '/recueils_da/%s' % r.data['id']

        for action in ['demandeurs_identifies', 'exploite', 'annule', 'purge']:
            r = user_req.post(route + '/' + action)
            assert r.status_code == 400, action

    def test_double_booking(self, user, site_structure_accueil, payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.modifier_brouillon.name]
        # Two slots of three consecutives creneaux
        creneaux_slot_1 = add_free_creneaux(3, site_structure_accueil.guichets_uniques[0])
        creneaux_slot_2 = add_free_creneaux(3, site_structure_accueil.guichets_uniques[0])
        user.test_set_accreditation(site_affecte=site_structure_accueil)
        user.save()

        concurrency = 10
        recueils = []

        for _ in range(concurrency):
            r = user_req.post('/recueils_da', data=payload_pa_fini)
            assert r.status_code == 201, r
            recueils.append(r.data['id'])

        payload = {'creneaux': [
            [str(creneaux_slot_1[0].id), str(creneaux_slot_2[0].id)]
        ]}

        def switch_to_pa_realise(receuil_id):
            return user_req.put('/recueils_da/%s/pa_realise' % receuil_id, data=payload)

        # Try to book the same creneaux for each recueil at the same time...
        from multiprocessing.pool import ThreadPool
        pool = ThreadPool(processes=concurrency)
        results = pool.map(switch_to_pa_realise, recueils)

        # ...only two should succeed
        successes = [r for r in results if r.status_code == 200]
        errors = [r for r in results if r.status_code != 200]
        assert len(successes) == 2, results
        len(successes[0].data['rendez_vous_gu']['creneaux']) == 1
        len(successes[1].data['rendez_vous_gu']['creneaux']) == 1
        successes[0].data['rendez_vous_gu']['creneaux'][0]['id']
        successes[1].data['rendez_vous_gu']['creneaux'][0]['id']

        creneaux = {str(c.id): c for c in Creneau.objects()}

        c0 = creneaux.pop(successes[0].data['rendez_vous_gu']['creneaux'][0]['id'])
        assert c0.reserve
        assert str(c0.document_lie.id) == successes[0].data['id']
        c1 = creneaux.pop(successes[1].data['rendez_vous_gu']['creneaux'][0]['id'])
        assert c1.reserve
        assert str(c1.document_lie.id) == successes[1].data['id']

        for free_creneau in creneaux.values():
            assert not free_creneau.reserve, free_creneau

        assert len(errors) == concurrency - 2, results

    def test_familly_double_booking(self, user, site_structure_accueil, payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.modifier_brouillon.name]
        # Two slots of three consecutives creneaux
        creneaux_slot_1 = add_free_creneaux(3, site_structure_accueil.guichets_uniques[0])
        creneaux_slot_2 = add_free_creneaux(3, site_structure_accueil.guichets_uniques[0])
        user.test_set_accreditation(site_affecte=site_structure_accueil)
        user.save()

        concurrency = 10
        recueils = []

        for _ in range(concurrency):
            r = user_req.post('/recueils_da', data=payload_pa_fini)
            assert r.status_code == 201, r
            recueils.append(r.data['id'])

        payload = {'creneaux': [
            [str(creneaux_slot_1[1].id), str(creneaux_slot_2[1].id)],
            [str(creneaux_slot_1[2].id), str(creneaux_slot_2[2].id)]
        ]}

        def switch_to_pa_realise(receuil_id):
            return user_req.put('/recueils_da/%s/pa_realise' % receuil_id, data=payload)

        # Try to book the same creneaux for each recueil at the same time...
        from multiprocessing.pool import ThreadPool
        pool = ThreadPool(processes=concurrency)
        results = pool.map(switch_to_pa_realise, recueils)

        # ...maximum two should succeed (but probably less due to concurrency
        # access&reverts)
        successes = [r for r in results if r.status_code == 200]
        errors = [r for r in results if r.status_code != 200]
        assert 1 <= len(successes) <= 2, results

        creneaux = {str(c.id): c for c in Creneau.objects()}
        c0 = creneaux.pop(successes[0].data['rendez_vous_gu']['creneaux'][0]['id'])
        assert c0.reserve
        assert str(c0.document_lie.id) == successes[0].data['id']
        c1 = creneaux.pop(successes[0].data['rendez_vous_gu']['creneaux'][1]['id'])
        assert c1.reserve
        assert str(c1.document_lie.id) == successes[0].data['id']
        if len(successes) == 2:
            c0 = creneaux.pop(successes[1].data['rendez_vous_gu']['creneaux'][0]['id'])
            assert c0.reserve
            assert str(c0.document_lie.id) == successes[1].data['id']
            c1 = creneaux.pop(successes[1].data['rendez_vous_gu']['creneaux'][1]['id'])
            assert c1.reserve
            assert str(c1.document_lie.id) == successes[1].data['id']

        for free_creneau in creneaux.values():
            assert not free_creneau.reserve, free_creneau
