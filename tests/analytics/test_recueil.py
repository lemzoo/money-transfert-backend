from tests import common
from tests.fixtures import *
from tests.test_rendez_vous import add_free_creneaux
from sief.model import RecueilDA
from analytics.manager import bootstrap
from datetime import datetime
from sief.permissions import POLICIES as p

from sief.model.site import creneaux_multi_reserver

PA_REALISE_USERS_COUNT = 0


def _pa_realise(request, payload_pa_fini, site_gu, site_structure_accueil, statut):
    global PA_REALISE_USERS_COUNT
    u = user(request, nom='Parealise', prenom='Setter',
             email='parealise-%s@test.com' % PA_REALISE_USERS_COUNT)
    u.test_set_accreditation(site_affecte=site_structure_accueil)
    u.save()
    PA_REALISE_USERS_COUNT += 1
    if statut == 'PA_REALISE':
        recueil = RecueilDA(agent_accueil=u,
                            structure_accueil=site_structure_accueil,
                            structure_guichet_unique=site_gu,
                            statut=statut,
                            prefecture_rattachee=site_gu.autorite_rattachement,
                            date_transmission=datetime.utcnow(),
                            **payload_pa_fini)
        recueil.save()
    else:
        recueil = RecueilDA(structure_accueil=site_structure_accueil,
                            agent_accueil=u, **payload_pa_fini)
        recueil.save()
        creneaux = add_free_creneaux(4, site_gu)

        creneaux_multi_reserver([creneaux[0], creneaux[1]], recueil)

        recueil.controller.pa_realiser(creneaux=[creneaux[0], creneaux[1]])
        recueil.save()
    return recueil


def create_pa_realise_spa(count, request, payload_pa_fini, site_structure_accueil):
    recueil = []
    for _ in range(count):
        recueil.append(_pa_realise(request, payload_pa_fini, site_structure_accueil.guichets_uniques[
            0], site_structure_accueil, 'BROUILLON'))
    return recueil


def create_pa_realise_gu(count, request, payload_pa_fini, site_structure_accueil):
    recueil = []
    for _ in range(count):
        recueil.append(_pa_realise(request, payload_pa_fini, site_structure_accueil.guichets_uniques[
            0], site_structure_accueil.guichets_uniques[
            0], 'PA_REALISE'))
    return recueil


def reprise_rendez_vous(user_req, recueils, motif, site_gu):
    for r in recueils:
        route = '/recueils_da/%s/rendez_vous' % r.pk
        if 'rendez_vous_gu' in r:
            r = user_req.delete(route)
        creneaux = add_free_creneaux(2, site_gu)
        payload = {
            "motif": motif,
            "creneaux": [str(c.pk) for c in creneaux]
        }
        r = user_req.put(route, data=payload)


class TestCreneau(common.BaseSolrTest):

    def test_creneau_pris(self, request, user, payload_pa_fini, site_structure_accueil):
        user.permissions.append(p.recueil_da.rendez_vous.gerer.name)
        user.permissions.append(p.analytics.voir.name)
        user.save()
        user_req = self.make_auth_request(user, user._raw_password)
        bootstrap()
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_pris_gu')
        assert r.data['hits'] == 0
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_pris_spa')
        assert r.data['hits'] == 0
        r = user_req.get('/analytics?fq=doc_type:on_pa_realise')
        assert r.data['hits'] == 0
        recueil_spa = create_pa_realise_spa(15, request, payload_pa_fini, site_structure_accueil)
        recueil_gu = create_pa_realise_gu(15, request, payload_pa_fini, site_structure_accueil)
        bootstrap()
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_pris_gu')
        assert r.data['hits'] == 0
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_pris_spa')
        assert r.data['hits'] == 30
        r = user_req.get('/analytics?fq=doc_type:on_pa_realise')
        assert r.data['hits'] == 15
        user.test_set_accreditation(site_affecte=site_structure_accueil)
        user.save()
        reprise_rendez_vous(
            user_req, recueil_spa, 'DOSSIER_A_COMPLETER', site_structure_accueil.guichets_uniques[0])
        user.test_set_accreditation(site_affecte=site_structure_accueil.guichets_uniques[0])
        user.save()
        reprise_rendez_vous(
            user_req, recueil_gu, 'DOSSIER_A_COMPLETER', site_structure_accueil.guichets_uniques[0])
        bootstrap()
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_pris_gu')
        assert r.data['hits'] == 30
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_pris_spa')
        assert r.data['hits'] == 60
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_annule')
        assert r.data['hits'] == 30
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_honore')
        assert r.data['hits'] == 30
        r = user_req.get('/analytics?fq=doc_type:on_pa_realise')
        assert r.data['hits'] == 15
        user.test_set_accreditation(site_affecte=site_structure_accueil)
        user.save()
        reprise_rendez_vous(
            user_req, recueil_spa, 'ECHEC_PRISE_EMPREINTES', site_structure_accueil.guichets_uniques[0])
        bootstrap()
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_pris_gu')
        assert r.data['hits'] == 30
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_pris_spa')
        assert r.data['hits'] == 90
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_annule')
        assert r.data['hits'] == 60
        r = user_req.get(
            '/analytics?fq=doc_type:rendez_vous_annule&fq=motif_s:ECHEC_PRISE_EMPREINTES')
        assert r.data['hits'] == 30
        r = user_req.get('/analytics?fq=doc_type:rendez_vous_honore')
        assert r.data['hits'] == 60
        r = user_req.get('/analytics?fq=doc_type:on_pa_realise')
        assert r.data['hits'] == 15
