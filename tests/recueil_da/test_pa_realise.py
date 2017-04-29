import pytest
from uuid import uuid4
from datetime import datetime
import copy
import random

from tests import common
from tests.fixtures import *
from tests.test_rendez_vous import add_free_creneaux

from sief.model.recueil_da import RecueilDA, RendezVousGu, UsagerSecondaireRecueil
from sief.model.fichier import Fichier
from sief.permissions import POLICIES as p

from sief.model.eurodac import generate_eurodac_ids

from sief.model.site import CreneauReserverError, creneaux_multi_reserver
PA_REALISE_USERS_COUNT = 0


@pytest.fixture
def pa_realise(request, payload_pa_fini, site_structure_accueil):
    global PA_REALISE_USERS_COUNT
    u = user(request, nom='Parealise', prenom='Setter',
             email='parealise-%s@test.com' % PA_REALISE_USERS_COUNT)
    u.test_set_accreditation(site_affecte=site_structure_accueil)
    u.save()
    PA_REALISE_USERS_COUNT += 1
    recueil = RecueilDA(agent_accueil=u,
                        structure_accueil=site_structure_accueil,
                        **payload_pa_fini)
    creneaux = add_free_creneaux(4, site_structure_accueil.guichets_uniques[0])

    creneaux_multi_reserver([creneaux[0], creneaux[1]], recueil)

    recueil.controller.pa_realiser(creneaux=[creneaux[0], creneaux[1]])
    recueil.save()
    return recueil


@pytest.fixture
def photo(request):
    return Fichier(name='photo.png').save()


def _add_mandatory_photo(usager, photo_pk):
    if usager and usager['demandeur'] == True:
        usager['origine_nom'] = 'EUROPE'
        if usager.get('nom_usage'):
            usager['origine_nom_usage'] = 'EUROPE'
        if not 'photo' in usager.keys():
            usager['photo'] = photo_pk


def _add_numero_eurodac(usager):
    if usager and usager['demandeur'] == True:
        usager['identifiant_eurodac'] = generate_eurodac_ids()[0]


@pytest.fixture
def demandeurs_identifies_pret(request, payload_pa_fini, site_structure_accueil, photo):
    # Mandatory fields for demandeurs: nom, prenoms, date_naissance,
    # pays_naissance, ville_naissance nationalites, sexe, photo.
    # Photo is not needed before,
    # so we have to add it if not present.
    _add_mandatory_photo(payload_pa_fini['usager_1'], str(photo.pk))
    _add_numero_eurodac(payload_pa_fini['usager_1'])
    _add_mandatory_photo(payload_pa_fini['usager_2'], str(photo.pk))
    _add_numero_eurodac(payload_pa_fini['usager_2'])
    for i, child in enumerate(payload_pa_fini['enfants']):
        _add_mandatory_photo(child, str(photo.pk))
        _add_numero_eurodac(child)

    recueil = pa_realise(request, payload_pa_fini, site_structure_accueil)
    return recueil


@pytest.fixture
def demandeurs_identifies_pret2(request, payload_pa_fini, site_structure_accueil, photo):

    _add_mandatory_photo(payload_pa_fini['usager_1'], str(photo.pk))
    _add_numero_eurodac(payload_pa_fini['usager_1'])
    _add_mandatory_photo(payload_pa_fini['usager_2'], str(photo.pk))
    _add_numero_eurodac(payload_pa_fini['usager_2'])
    for i, child in enumerate(payload_pa_fini['enfants']):
        _add_mandatory_photo(child, str(photo.pk))
        _add_numero_eurodac(child)

    recueil = pa_realise(request, payload_pa_fini, site_structure_accueil)
    return recueil


@pytest.fixture
def demandeurs_identifies_mineur_pret(request, payload_pa_fini_mineur, site_structure_accueil, photo):
    # Mandatory fields for demandeurs: nom, prenoms, date_naissance,
    # pays_naissance, ville_naissance nationalites, sexe, photo.
    # Photo is not needed before,
    # so we have to add it if not present.

    _add_mandatory_photo(payload_pa_fini_mineur['usager_1'], str(photo.pk))
    _add_numero_eurodac(payload_pa_fini_mineur['usager_1'])
    recueil = pa_realise(request, payload_pa_fini_mineur, site_structure_accueil)

    return recueil


@pytest.fixture
def payload_pa_fini_mineur(ref_langues_iso, ref_langues_ofpra, ref_nationalites, ref_pays):
    photo = Fichier(name='photo.png').save()

    return {
        'usager_1': {
            'date_entree_en_france': datetime(2001, 1, 1),
            'date_depart': datetime(2001, 1, 1),
            'date_depart_approximative': False,
            'date_entree_en_france_approximative': False,
            'nom': 'Plantagenêt', 'prenoms': ['Geoffroy', 'V'], 'sexe': 'M',
            'acceptation_opc': False,
            'date_naissance': datetime(2000, 8, 24),
            "ville_naissance": "Château-du-Loir",
            "nom_pere": "Foulque",
            "prenom_pere": "V",
            "nom_mere": "Erembourge",
            "prenom_mere": "Du Maine",
            "situation_familiale": "CELIBATAIRE",
            "condition_entree_france": "REGULIERE",
            "present_au_moment_de_la_demande": True,
            'demandeur': True,
            'langues': [{'code': str(ref_langues_iso[0].pk)}],
            'langues_audition_OFPRA': [{'code': str(ref_langues_ofpra[0].pk)}],
            'adresse': {'pays': {'code': str(ref_pays[0].pk)}},
            'pays_naissance': {'code': str(ref_pays[1].pk)},
            'nationalites': [{'code': str(ref_nationalites[1].pk)}],
            'photo_premier_accueil': str(photo.pk),
            'representant_legal_prenom': "Erembourge",
            'representant_legal_nom': "Du Maine",
            'vulnerabilite': {'mobilite_reduite': False},
            'identite_approchante_select': True
        },
        "profil_demande": "MINEUR_ISOLE",
    }


@pytest.fixture
def payload_post_pa_realise(photo, ref_pays, ref_nationalites, ref_langues_iso, ref_langues_ofpra):
    return {
        "usager_1": {
            "situation_familiale": "CELIBATAIRE",
            "date_naissance": "1980-12-26T00:00:00+00:00",
            "prenoms": ["Lesley"],
            "nationalites": [ref_nationalites[0].code],
            "adresse": {"adresse_inconnue": True},
            "nom": "Burnit",
            "pays_naissance": ref_pays[0].code,
            "demandeur": True,
            "ville_naissance": "Kiev",
            "sexe": "F",
            "date_entree_en_france": "2015-09-29T00:00:00+00:00",
            "date_depart": "2015-09-28T00:00:00+00:00",
            "present_au_moment_de_la_demande": True,
            "photo": str(photo.id),
            "langues_audition_OFPRA": [ref_langues_ofpra[0].code],
            "langues": [ref_langues_iso[0].code],
            "vulnerabilite": {"mobilite_reduite": False}
        },
        "profil_demande": "ADULTE_ISOLE",
        "statut": "PA_REALISE"
    }


@pytest.fixture
def payload_famille_post_pa_realise(photo, ref_pays, ref_nationalites, ref_langues_iso, ref_langues_ofpra):
    return {
        'usager_1': {
            "date_naissance": "1980-12-26T00:00:00+00:00",
            'situation_familiale': 'MARIE',
            "prenoms": ["Lesley"],
            "nationalites": [ref_nationalites[0].code],
            "adresse": {"adresse_inconnue": True},
            "nom": "Burnit",
            "pays_naissance": ref_pays[0].code,
            "demandeur": True,
            "ville_naissance": "Kiev",
            "sexe": "F",
            "date_entree_en_france": "2015-09-29T00:00:00+00:00",
            "date_depart": "2015-09-28T00:00:00+00:00",
            "present_au_moment_de_la_demande": True,
            "photo": str(photo.id),
            "langues_audition_OFPRA": [ref_langues_ofpra[0].code],
            "langues": [ref_langues_iso[0].code]
        },
        'usager_2': {
            "date_naissance": "1980-12-26T00:00:00+00:00",
            "prenoms": ["Lesley"],
            "nationalites": [ref_nationalites[0].code],
            "adresse": {"adresse_inconnue": True},
            "nom": "Burnit",
            "pays_naissance": ref_pays[0].code,
            "demandeur": True,
            "ville_naissance": "Kiev",
            "sexe": "F",
            "date_entree_en_france": "2015-09-29T00:00:00+00:00",
            "date_depart": "2015-09-28T00:00:00+00:00",
            "present_au_moment_de_la_demande": True,
            "photo": str(photo.id),
            "langues_audition_OFPRA": [ref_langues_ofpra[0].code],
            "langues": [ref_langues_iso[0].code]
        },
        'enfants': [
            {
                "date_naissance": "1980-12-26T00:00:00+00:00",
                'situation_familiale': 'CELIBATAIRE',
                "prenoms": ["Lesley"],
                "nationalites": [ref_nationalites[0].code],
                "adresse": {"adresse_inconnue": True},
                "nom": "Burnit",
                "pays_naissance": ref_pays[0].code,
                'usager_1': True,
                'usager_2': True,
                "demandeur": True,
                "ville_naissance": "Kiev",
                "sexe": "F",
                "date_entree_en_france": "2015-09-29T00:00:00+00:00",
                "date_depart": "2015-09-28T00:00:00+00:00",
                "present_au_moment_de_la_demande": True,
                "photo": str(photo.id),
                "langues_audition_OFPRA": [ref_langues_ofpra[0].code],
                "langues": [ref_langues_iso[0].code]
            },
            {
                "date_naissance": "1980-12-26T00:00:00+00:00",
                'situation_familiale': 'CELIBATAIRE',
                "prenoms": ["Lesley"],
                "nationalites": [ref_nationalites[0].code],
                "adresse": {"adresse_inconnue": True},
                "nom": "Burnit",
                "pays_naissance": ref_pays[0].code,
                'usager_1': True,
                'usager_2': True,
                "demandeur": True,
                "ville_naissance": "Kiev",
                "sexe": "F",
                "date_entree_en_france": "2015-09-29T00:00:00+00:00",
                "date_depart": "2015-09-28T00:00:00+00:00",
                "present_au_moment_de_la_demande": True,
                "photo": str(photo.id),
                "langues_audition_OFPRA": [ref_langues_ofpra[0].code],
                "langues": [ref_langues_iso[0].code]
            },
            {
                "date_naissance": "1980-12-26T00:00:00+00:00",
                'situation_familiale': 'CELIBATAIRE',
                "prenoms": ["Lesley"],
                "nationalites": [ref_nationalites[0].code],
                "adresse": {"adresse_inconnue": True},
                "nom": "Burnit",
                "pays_naissance": ref_pays[0].code,
                'usager_1': True,
                'usager_2': True,
                "demandeur": True,
                "ville_naissance": "Kiev",
                "sexe": "F",
                "date_entree_en_france": "2015-09-29T00:00:00+00:00",
                "date_depart": "2015-09-28T00:00:00+00:00",
                "present_au_moment_de_la_demande": True,
                "photo": str(photo.id),
                "langues_audition_OFPRA": [ref_langues_ofpra[0].code],
                "langues": [ref_langues_iso[0].code]
            }
        ],
        "profil_demande": "FAMILLE",
        "statut": "PA_REALISE"}


class TestRecueilDAPARealise(common.BaseTest):

    def test_get_rdv(self, user, pa_realise):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]
        user.save()
        r = user_req.get('/recueils_da/%s' % pa_realise.pk)
        assert r.status_code == 200, r
        assert 'rendez_vous_gu' in r.data
        rdv = r.data['rendez_vous_gu']
        assert 'site' in r.data['rendez_vous_gu']
        assert 'creneaux' in r.data['rendez_vous_gu']
        assert '_links' in r.data['rendez_vous_gu']['site']
        creneaux = r.data['rendez_vous_gu']['creneaux']
        # Retrieve the links
        user.permissions.append(p.site.voir.name)
        user.save()
        r = user_req.get(r.data['rendez_vous_gu']['site']['_links']['self'])
        assert r.status_code == 200, r
        for c in creneaux:
            assert '_links' in c
            r = user_req.get(c['_links']['self'])
            assert r.status_code == 200

    def test_get_recueil_da(self, user, pa_realise):
        user_req = self.make_auth_request(user, user._raw_password)
        r = user_req.get('/recueils_da')
        assert r.status_code == 403, r
        route = '/recueils_da/%s' % pa_realise.pk
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

    def test_get_links(self, user, pa_realise):
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/recueils_da/%s' % pa_realise.pk
        user.permissions = [p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_brouillon.name]
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ('self', 'parent'))
        user.permissions.append(p.recueil_da.modifier_pa_realise.name)
        user.permissions.append(p.historique.voir.name)
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ('self', 'parent', 'replace', 'annuler',
                                'identifier_demandeurs', 'history'))

    def test_cant_delete(self, user, pa_realise):
        # Only brouillons can be deleted
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/recueils_da/%s' % pa_realise.pk
        user.permissions = [p.recueil_da.modifier_brouillon.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_pa_realise.name]
        user.save()
        r = user_req.delete(route)
        assert r.status_code == 400, r

    def test_switch_to_demandeurs_identifies(self, user, demandeurs_identifies_pret, usager):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_pa_realise.name]
        user.save()
        # usager_2 already exists, but doesn't have agdref info
        usager.identifiant_agdref = None
        usager.date_enregistrement_agdref = None
        usager.save()
        demandeurs_identifies_pret.usager_2 = UsagerSecondaireRecueil(
            usager_existant=usager, demandeur=True,
            present_au_moment_de_la_demande=True,
            date_entree_en_france=datetime(1152, 1, 1),
            date_depart=datetime(1152, 1, 1),
            date_depart_approximative=False,
            date_entree_en_france_approximative=False,
            identite_approchante_select=True,
            identifiant_eurodac=generate_eurodac_ids()[0])
        demandeurs_identifies_pret.save()
        r = user_req.post('/recueils_da/%s/demandeurs_identifies' %
                          demandeurs_identifies_pret.pk)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'DEMANDEURS_IDENTIFIES'
        # usager 1&2 are demandeur, should have agdref info now
        assert r.data['usager_1']['identifiant_agdref']
        assert r.data['usager_1']['date_enregistrement_agdref']
        usager.reload()
        assert usager.identifiant_agdref
        assert usager.date_enregistrement_agdref

    def test_switch_to_demandeurs_identifies_mineur_isole(self, user, demandeurs_identifies_mineur_pret, usager, photo):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_pa_realise.name]
        user.save()
        # usager_2 already exists, but doesn't have agdref info
        usager.identifiant_agdref = None
        usager.date_enregistrement_agdref = None
        usager.save()

        r = user_req.post('/recueils_da/%s/demandeurs_identifies' %
                          demandeurs_identifies_mineur_pret.pk)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'DEMANDEURS_IDENTIFIES'
        assert r.data['usager_1']['identifiant_agdref']
        assert r.data['usager_1']['date_enregistrement_agdref']

    def test_switch_to_demandeurs_identifies_mineur_isole_representant_moral(self, user, demandeurs_identifies_mineur_pret, usager, photo):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_pa_realise.name]
        user.save()
        # usager_2 already exists, but doesn't have agdref info
        usager.identifiant_agdref = None
        usager.date_enregistrement_agdref = None
        usager.save()
        demandeurs_identifies_mineur_pret.usager_1.representant_legal_personne_morale = True
        demandeurs_identifies_mineur_pret.usager_1.representant_legal_personne_morale_designation = "Popa"
        demandeurs_identifies_mineur_pret.save()

        r = user_req.post('/recueils_da/%s/demandeurs_identifies' %
                          demandeurs_identifies_mineur_pret.pk)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'DEMANDEURS_IDENTIFIES'
        assert r.data['usager_1']['identifiant_agdref']
        assert r.data['usager_1']['date_enregistrement_agdref']

    def test_switch_to_demandeurs_identifies_mineur_isole_on_error(self, user, demandeurs_identifies_mineur_pret, usager, photo):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_pa_realise.name]
        user.save()
        # usager_2 already exists, but doesn't have agdref info
        usager.identifiant_agdref = None
        usager.date_enregistrement_agdref = None
        usager.save()

        demandeurs_identifies_mineur_pret.usager_1.representant_legal_nom = None
        demandeurs_identifies_mineur_pret.usager_1.representant_legal_prenom = None
        demandeurs_identifies_mineur_pret.save()
        r = user_req.post('/recueils_da/%s/demandeurs_identifies' %
                          demandeurs_identifies_mineur_pret.pk)
        assert r.status_code == 400, r
        assert 'representant_legal_nom' in str(r.data)
        assert 'representant_legal_prenom' in str(r.data)

    def test_switch_to_demandeurs_identifies_mineur_isole_representant_moral_on_error(self, user, demandeurs_identifies_mineur_pret, usager, photo):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_pa_realise.name]
        user.save()
        # usager_2 already exists, but doesn't have agdref info
        usager.identifiant_agdref = None
        usager.date_enregistrement_agdref = None
        usager.save()
        demandeurs_identifies_mineur_pret.usager_1.representant_legal_personne_morale = True
        demandeurs_identifies_mineur_pret.usager_1.representant_legal_personne_morale_designation = None
        demandeurs_identifies_mineur_pret.save()

        r = user_req.post('/recueils_da/%s/demandeurs_identifies' %
                          demandeurs_identifies_mineur_pret.pk)
        assert r.status_code == 400, r
        assert 'representant_legal_personne_morale_designation' in str(r.data)

    def test_invalid_switches(self, user, demandeurs_identifies_pret):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.creer_pa_realise.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_brouillon.name,
                            p.recueil_da.modifier_pa_realise.name,
                            p.recueil_da.modifier_demandeurs_identifies.name,
                            p.recueil_da.modifier_exploite.name,
                            p.recueil_da.purger.name]
        user.save()
        route = '/recueils_da/%s' % demandeurs_identifies_pret.pk
        from tests.test_rendez_vous import add_free_creneaux
        creneaux = add_free_creneaux(
            4, demandeurs_identifies_pret.structure_accueil.guichets_uniques[0])

        r = user_req.put(
            route + '/pa_realise', data={'creneaux': [creneaux[0]['id'], creneaux[1]['id']]})
        assert r.status_code == 400, r
        r = user_req.post(route + '/purge')
        assert r.status_code == 400, r

    def test_partial_error_switch(self, user, demandeurs_identifies_pret, usager):
        # Monkey patch AGDREF connector to add a mock
        from services import agdref
        origine_enregistrement_agdref = agdref.enregistrement_agdref
        trigger_error = False

        def mock(*args, **kwargs):
            nonlocal trigger_error
            if not trigger_error:
                trigger_error = True
                return origine_enregistrement_agdref(*args, **kwargs)
            else:
                raise agdref.AGDREFNumberError('Trigger error from mock')
        agdref.enregistrement_agdref = mock

        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_pa_realise.name]
        user.save()
        # usager_2 already exists, but doesn't have agdref info
        usager.identifiant_agdref = None
        usager.date_enregistrement_agdref = None
        usager.save()
        demandeurs_identifies_pret.save()
        route = '/recueils_da/%s/demandeurs_identifies' % demandeurs_identifies_pret.pk
        r = user_req.post(route)
        assert r.status_code == 400, r
        demandeurs_identifies_pret.reload()
        # usager_1 should have been successfuly altered...
        assert demandeurs_identifies_pret.usager_1.identifiant_agdref
        assert demandeurs_identifies_pret.usager_1.identifiant_portail_agdref
        assert demandeurs_identifies_pret.usager_1.date_enregistrement_agdref
        # ...while usager_2 has trigger the error and should not have changed
        assert not demandeurs_identifies_pret.usager_2.identifiant_agdref
        assert not demandeurs_identifies_pret.usager_2.identifiant_portail_agdref
        assert not demandeurs_identifies_pret.usager_2.date_enregistrement_agdref
        assert demandeurs_identifies_pret.statut == 'PA_REALISE'

        # Revert mock
        agdref.enregistrement_agdref = origine_enregistrement_agdref
        # Redo the post, usager_1 should not have changed it identifiant_agdref
        r = user_req.post(route)
        assert r.status_code == 200, r
        assert r.data['usager_1']['identifiant_agdref'] == \
            demandeurs_identifies_pret.usager_1.identifiant_agdref
        assert r.data['usager_1']['date_enregistrement_agdref']
        # usager_2 contains a new identifiant_agdref
        assert r.data['usager_2']['identifiant_agdref']
        assert r.data['usager_2']['date_enregistrement_agdref']

    def test_update_refus(self, user, pa_realise, payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.voir.name,
                            p.recueil_da.modifier_pa_realise.name]
        user.test_set_accreditation(site_affecte=pa_realise.structure_accueil)
        user.save()
        route = '/recueils_da/%s' % pa_realise.pk
        # Cannot provide a date
        r = user_req.get(route)
        assert r.status_code == 200, r
        payload = payload_pa_fini
        payload['usager_1']['refus'] = {'motif': 'I have my own reasons...',
                                        'date_notification': datetime.utcnow()}
        r = user_req.put(route, data=payload)
        assert r.status_code == 200, r
        assert 'motif' in r.data['usager_1']['refus']
        assert 'date_notification' in r.data['usager_1']['refus']

    def test_bad_update(self, user, pa_realise, payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.voir.name,
                            p.recueil_da.modifier_pa_realise.name]
        user.test_set_accreditation(site_affecte=pa_realise.structure_accueil)
        user.save()
        route = '/recueils_da/%s' % pa_realise.pk
        for key, value in (('usager_1', None), ('usager_1', common.NOT_SET),
                           ('usager_1', {}), ('usager_2', common.NOT_SET),
                           ('identifiant_famille_dna', 'cannot_update_here')):
            payload = copy.deepcopy(payload_pa_fini)
            common.update_payload(payload, key, value)
            r = user_req.put(route, data=payload)
            assert r.status_code == 400, r

    def test_bad_site_affecte(self, user, pa_realise, payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.voir.name,
                            p.recueil_da.modifier_pa_realise.name]
        user.save()
        # Cannot update without a site_affecte
        route = '/recueils_da/%s' % pa_realise.pk
        r = user_req.put(route, data=payload_pa_fini)
        assert r.status_code == 400, r
        # Same thing for the view...
        r = user_req.get('/recueils_da')
        assert r.status_code == 400, r
        r = user_req.get(route)
        assert r.status_code == 400, r
        # ...unless the specific rights are set
        user.permissions = [p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_pa_realise.name]
        user.save()
        r = user_req.get('/recueils_da')
        assert r.status_code == 200, r
        r = user_req.get(route)
        assert r.status_code == 200, r
        # Finaly retry the put with the site_affecte set
        user.test_set_accreditation(site_affecte=pa_realise.structure_accueil)
        user.save()
        r = user_req.put(route, data=payload_pa_fini)
        assert r.status_code == 200, r

    def test_cancel_rendez_vous(self, user, pa_realise):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.prefecture_rattachee.sans_limite.name]
        user.save()
        route = '/recueils_da/%s/rendez_vous' % pa_realise.pk
        r = user_req.delete(route)
        assert r.status_code == 403, r
        user.permissions.append(p.recueil_da.rendez_vous.gerer.name)
        user.save()
        creneaux_taken = pa_realise.rendez_vous_gu.creneaux
        r = user_req.delete(route)
        assert r.status_code == 200, r
        assert 'rendez_vous_gu' not in r.data
        assert 'rendez_vous_gu_anciens' in r.data
        assert len(r.data['rendez_vous_gu_anciens']) == 1
        assert r.data['rendez_vous_gu_anciens'][0]['annule'] == True
        for c in creneaux_taken:
            c.reload()
            assert c.reserve == False
        # Should not be able to re-cancel
        r = user_req.delete(route)
        assert r.status_code == 400, r

    def test_take_rendez_vous(self, user, pa_realise):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.voir.name,
                            p.recueil_da.modifier_pa_realise.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]
        user.save()
        creneaux = pa_realise.rendez_vous_gu.creneaux
        for c in creneaux:
            c.controller.liberer()
            c.save()
        pa_realise.rendez_vous_gu = None
        pa_realise.save()
        payload = {
            "motif": "DOSSIER_A_COMPLETER",
            "creneaux": [str(c.pk) for c in creneaux]
        }
        route = '/recueils_da/%s/rendez_vous' % pa_realise.pk
        r = user_req.put(route, data=payload)
        assert r.status_code == 403, r
        user.permissions.append(p.recueil_da.rendez_vous.gerer.name)
        user.save()
        r = user_req.put(route, data=payload)
        assert r.status_code == 200, r
        assert 'rendez_vous_gu' in r.data
        creneaux_got = {c['id'] for c in r.data['rendez_vous_gu']['creneaux']}
        creneaux_expected = {str(c.pk) for c in creneaux}
        assert creneaux_got == creneaux_expected
        for c in creneaux:
            c.reload()
            assert c.reserve == True
            assert c.document_lie == pa_realise
        # Should not be able to take another rendez-vous
        add_free_creneaux(2, creneaux[0].site)
        r = user_req.put(route, data=payload)
        assert r.status_code == 400, r

    def test_bad_take_rendez_vous(self, user, pa_realise):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.rendez_vous.gerer.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]
        user.save()
        creneaux = pa_realise.rendez_vous_gu.creneaux
        for c in creneaux:
            c.controller.liberer()
            c.save()
        pa_realise.rendez_vous_gu = None
        pa_realise.save()
        default_payload = {
            "motif": "DOSSIER_A_COMPLETER",
            "creneaux": [str(c.pk) for c in creneaux]
        }
        route = '/recueils_da/%s/rendez_vous' % pa_realise.pk
        for key, value in (
                ('motif', common.NOT_SET), ('motif', 'bad_motif'),
                ('creneaux', [1, 2]),
                ('creneaux', [str(creneaux[1].pk), str(user.pk)]),
                ('unknow', 'field')):
            payload = copy.deepcopy(default_payload)
            common.update_payload(payload, key, value)
            r = user_req.put(route, data=payload)
            assert r.status_code == 400, (key, value)
            for c in creneaux:
                c.reload()
                assert c.reserve == False
        # Reserve one of the creneaux to make it fail
        creneaux[1].reserve = True
        creneaux[1].linked_pk = "don't change me"
        creneaux[1].save()
        r = user_req.put(route, data=payload)
        assert r.status_code == 400
        creneaux[0].reload()
        assert creneaux[0].reserve == False
        assert creneaux[1].reserve == True
        assert creneaux[1].linked_pk == "don't change me"

    def test_cancel_recueil_cancel_rendez_vous(self, user, pa_realise):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.modifier_pa_realise.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.rendez_vous.gerer.name]
        user.save()
        creneaux_taken = pa_realise.rendez_vous_gu.creneaux
        route = '/recueils_da/%s/annule' % pa_realise.pk
        r = user_req.post(route, data={'motif': 'NON_PRESENTATION_RDV'})
        assert r.status_code == 200, r
        assert 'rendez_vous_gu' not in r.data
        assert 'rendez_vous_gu_anciens' in r.data
        assert len(r.data['rendez_vous_gu_anciens']) == 1
        assert r.data['rendez_vous_gu_anciens'][0]['annule'] == True
        for c in creneaux_taken:
            c.reload()
            assert c.reserve == False
        # Should not be able cancel
        r = user_req.delete('/recueils_da/%s/rendez_vous' % pa_realise.pk)
        assert r.status_code == 400, r

    def test_cancel_recueil_no_rendez_vous(self, user, pa_realise):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.modifier_pa_realise.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.rendez_vous.gerer.name]
        user.save()
        # First cancel the rdv...
        r = user_req.delete('/recueils_da/%s/rendez_vous' % pa_realise.pk)
        assert r.status_code == 200, r
        assert 'rendez_vous_gu' not in r.data
        assert 'rendez_vous_gu_anciens' in r.data
        assert len(r.data['rendez_vous_gu_anciens']) == 1
        assert r.data['rendez_vous_gu_anciens'][0]['annule'] == True
        creneaux_taken = pa_realise.rendez_vous_gu.creneaux
        for c in creneaux_taken:
            c.reload()
            assert c.reserve == False
        # ...then cancel the entire recueil
        route = '/recueils_da/%s/annule' % pa_realise.pk
        r = user_req.post(route, data={'motif': 'AUTRE'})
        assert r.status_code == 200, r

    def test_enregistrement_famille_ofii(self, user, pa_realise):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.voir.name]
        user.save()
        route = '/recueils_da/%s/enregistrement_famille_ofii' % pa_realise.pk
        payload = {'identifiant_famille_dna': 'dummy-id'}
        # Need right to do it...
        r = user_req.post(route, data=payload)
        assert r.status_code == 403, r
        # ...provide it
        user.permissions.append(p.recueil_da.enregistrer_famille_ofii.name)
        user.save()
        r = user_req.post(route, data=payload)
        assert r.status_code == 200, r
        assert r.data['identifiant_famille_dna'] == payload['identifiant_famille_dna']
        # Cannot do it two times
        r = user_req.post(route, data=payload)
        assert r.status_code == 400, r
        # Make sure the field is in the default dump
        r = user_req.get('/recueils_da/%s' % pa_realise.pk)
        assert r.status_code == 200
        assert r.data.get('identifiant_famille_dna', '<missing>') == payload[
            'identifiant_famille_dna']

    def test_bad_enregistrement_famille_ofii(self, user, pa_realise):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.enregistrer_famille_ofii.name]
        user.save()
        route = '/recueils_da/%s/enregistrement_famille_ofii' % pa_realise.pk
        default_payload = {'identifiant_famille_dna': 'dummy-id'}
        for key, value in (
                ('identifiant_famille_dna', ''), ('identifiant_famille_dna', None),
                ('id', '5608f8ca1d41c8553f2a2502'), ('statut', 'BROUILLON'),
                ('enfants', [])):
            payload = default_payload.copy()
            payload[key] = value
            r = user_req.post(route, data=payload)
            assert r.status_code == 400, (key, value, r)

    def test_create_in_pa_realise(self, user, site_gu, payload_post_pa_realise):
        user_req = self.make_auth_request(user, user._raw_password)
        user_site_affecte = site_gu
        user.test_set_accreditation(site_affecte=user_site_affecte)
        user.save()
        # recueil_da can be created empty
        # Need permission to do it
        r = user_req.post('/recueils_da', data=payload_post_pa_realise)
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions = [p.recueil_da.creer_pa_realise.name,
                            p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]
        user.save()
        r = user_req.post('/recueils_da', data=payload_post_pa_realise)
        assert r.status_code == 201, r
        # `structure_accueil` and `agent_accueil` should have been set
        route = '/recueils_da/%s' % r.data['id']
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert (r.data.get('structure_accueil', '<not_set>')['id'] ==
                str(user_site_affecte.pk))
        assert r.data.get('agent_accueil', '<not_set>')['id'] == str(user.pk)

    def test_gu_create_in_pa_realise(self, user, site_gu, payload_post_pa_realise):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(site_affecte=site_gu)
        payload = payload_post_pa_realise
        payload['usager_1']['type_demande'] = 'REEXAMEN'
        user.save()

        # recueil_da can be created empty
        # Need permission to do it
        r = user_req.post('/recueils_da', data=payload)

        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions = [p.recueil_da.creer_pa_realise.name,
                            p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]
        user.save()
        r = user_req.post('/recueils_da', data=payload)
        assert r.status_code == 400, r
        payload['usager_1']['numero_reexamen'] = 3
        r = user_req.post('/recueils_da', data=payload)
        assert r.status_code == 201, r
        assert r.data['usager_1']['numero_reexamen'] == payload['usager_1']['numero_reexamen'], r
        assert r.data['usager_1']['type_demande'] == payload['usager_1']['type_demande'], r

        # `structure_accueil` and `agent_accueil` should have been set
        route = '/recueils_da/%s' % r.data['id']
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert (r.data.get('structure_accueil', '<not_set>')['id'] ==
                str(user.controller.get_current_site_affecte().pk))
        assert r.data.get('agent_accueil', '<not_set>')['id'] == str(user.pk)

    def test_bad_create_in_pa_realise(self, user, site_gu, payload_post_pa_realise):
        user_req = self.make_auth_request(user, user._raw_password)
        # Make sure creer_brouillon doesn't allow use to create in PA_REALISE
        user.permissions = [p.recueil_da.creer_brouillon.name]
        user.save()
        r = user_req.post('/recueils_da', data=payload_post_pa_realise)
        assert r.status_code == 403, r
        # user must have a site_affecte to create a recueil_da
        user.permissions = [p.recueil_da.creer_pa_realise.name]
        user.save()
        r = user_req.post('/recueils_da', data=payload_post_pa_realise)
        assert r.status_code == 400, r
        user.test_set_accreditation(site_affecte=site_gu)
        user.save()
        # Can only do PA_REALISE
        payload_post_pa_realise['statut'] = 'BROUILLON'
        r = user_req.post('/recueils_da', data=payload_post_pa_realise)
        assert r.status_code == 403, r
        del payload_post_pa_realise['statut']
        r = user_req.post('/recueils_da', data=payload_post_pa_realise)
        assert r.status_code == 403, r


class TestPrefectureRattacheeRecueilDA(common.BaseTest):

    def test_prefecture_rattachee(self, user, site, pa_realise):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.voir.name]
        user.test_set_accreditation(site_affecte=site)
        user.save()
        # Sanity check on the site
        assert site != pa_realise.prefecture_rattachee

        def _test_view(size):
            r = user_req.get('/recueils_da')
            assert r.status_code == 200, r
            assert len(r.data['_items']) == size
            if len(r.data['_items']) == 1:
                route = r.data['_items'][0]['_links']['self']
                r = user_req.get(route)
                assert r.status_code == 200, r
                assert r.data['id'] == str(pa_realise.id)
        _test_view(0)
        user.test_set_accreditation(site_affecte=pa_realise.structure_accueil)
        user.save()
        _test_view(1)
        user.test_set_accreditation(site_affecte=pa_realise.structure_guichet_unique)
        user.save()
        _test_view(1)
        user.test_set_accreditation(site_affecte=None)
        user.permissions.append(p.recueil_da.prefecture_rattachee.sans_limite.name)
        user.save()
        _test_view(1)

    def test_prefecture_rattachee_route(self, user, site, pa_realise):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.voir.name]
        user.test_set_accreditation(site_affecte=site)
        user.save()
        # Sanity check
        assert site != pa_realise.prefecture_rattachee
        # Cannot see this recueil...
        r = user_req.get('/recueils_da/%s' % pa_realise.id)
        assert r.status_code == 403, r
        # ...but can ask who's it belongs to
        r = user_req.get('/recueils_da/%s/prefecture_rattachee' % pa_realise.id)
        assert r.status_code == 200, r
        assert 'prefecture_rattachee' in r.data
        assert r.data['prefecture_rattachee']['id'] == str(pa_realise.prefecture_rattachee.id)


class TestRecueilDAGenerateEurodac(common.BaseTest):

    def test_generate_eurodac(self, user, site_structure_accueil, payload_post_pa_realise):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(site_affecte=site_structure_accueil.guichets_uniques[0])

        user.permissions = [p.recueil_da.creer_pa_realise.name,
                            p.recueil_da.voir.name,
                            p.recueil_da.generer_eurodac.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]
        user.save()
        payload = payload_post_pa_realise
        r = user_req.post('/recueils_da', data=payload)
        assert r.status_code == 201, r

        # eurodac
        # `structure_accueil` and `agent_accueil` should have been set
        route = '/recueils_da/%s' % str(r.data['id'])
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert (r.data.get('structure_accueil', '<not_set>')['id'] ==
                str(user.controller.get_current_site_affecte().pk))
        assert r.data.get('agent_accueil', '<not_set>')['id'] == str(user.pk)

        # generate eurodac
        route = '/recueils_da/%s/generer_eurodac' % str(r.data['id'])
        r = user_req.post(route)

        assert r.status_code == 200, r
        assert r.data['statut'] == 'PA_REALISE'
        # pour tester la plage de l'id eurodac ulérieurement
        assert r.data['usager_1']['identifiant_eurodac']
        # pour tester la taille de l'id eurodac
        assert len(r.data['usager_1']['identifiant_eurodac']) == 10

    def test_generate_eurodac_famille(self, user, site_structure_accueil,
                                      payload_famille_post_pa_realise):

        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(site_affecte=site_structure_accueil.guichets_uniques[0])

        user.permissions = [p.recueil_da.creer_pa_realise.name,
                            p.recueil_da.voir.name,
                            p.recueil_da.generer_eurodac.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]
        user.save()
        r = user_req.post('/recueils_da', data=payload_famille_post_pa_realise)
        assert r.status_code == 201, r

        # generate eurodac
        route = '/recueils_da/%s/generer_eurodac' % str(r.data['id'])
        r = user_req.post(route)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'PA_REALISE'
        assert r.data['usager_1']['identifiant_eurodac']
        assert len(r.data['usager_1']['identifiant_eurodac']) == 10
        assert r.data['usager_2']['identifiant_eurodac']
        assert r.data['enfants'][0]['identifiant_eurodac']
        assert r.data['enfants'][1]['identifiant_eurodac']
        assert r.data['enfants'][2]['identifiant_eurodac']
