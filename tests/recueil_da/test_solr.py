import pytest
from datetime import datetime

from tests import common
from tests.fixtures import *

from sief.model.fields import AddressEmbeddedDocument
from sief.model.usager import Localisation
from sief.model.recueil_da import RecueilDA, RendezVousGu
from sief.permissions import POLICIES as p

@pytest.fixture
def other_structure_accueil(request, other_gu):
    return site_structure_accueil(request, other_gu)


@pytest.fixture
def other_gu(request, other_pref):
    return site_gu(request, other_pref)


@pytest.fixture
def other_pref(request):
    return site_prefecture(request)


@pytest.fixture
def recueils(request, payload_pa_fini, site_structure_accueil, count=2):
    recueils = []
    for _ in range(count):
        recueil = pa_realise(request, payload_pa_fini, site_structure_accueil)
        recueil.save()
        recueils.append(recueil)
    return recueils


class TestRecueilDASolr(common.BaseSolrTest):

    def test_phonetic(self, user, recueils):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(site_affecte=recueils[0].structure_accueil)
        user.permissions = [p.recueil_da.voir.name]
        user.save()
        my_recueil = recueils[0]
        my_recueil.usager_1.nom = 'Duroux'
        my_recueil.usager_1.prenoms = ['Jean', 'Jonathan']
        my_recueil.save()
        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)
        for req in ['prenom_phon:jan', 'prenom_phon:Jonatan', 'nom_phon:durou']:
            r = user_req.get('/recueils_da?q=' + req)
            assert r.status_code == 200, req
            assert len(r.data['_items']) == 1
            assert r.data['_items'][0]['id'] in str(my_recueil.id)

    def test_search_limited(self, user, recueils, other_structure_accueil, other_gu):
        my_recueil, other_recueil = recueils
        # Let say we have two recueils: one from my site
        # and another not related to me
        my_recueil.structure_accueil = other_structure_accueil
        my_recueil.structure_guichet_unique = other_gu
        my_recueil.prefecture_rattachee = other_gu.autorite_rattachement
        my_recueil.usager_1.nom = 'Terrieur'
        my_recueil.usager_1.prenoms = ['Alain', 'Sorry For']
        my_recueil.save()
        # Sanity check
        assert other_structure_accueil.id != other_recueil.structure_accueil.id
        assert other_gu.id != other_recueil.structure_guichet_unique.id
        other_recueil.usager_1.nom = 'Terrieur'
        other_recueil.usager_1.prenoms = ['Alex', 'The Joke']
        other_recueil.save()
        user.test_set_accreditation(site_affecte=other_structure_accueil)
        user.permissions = [p.recueil_da.voir.name]
        user.save()
        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)
        user_req = self.make_auth_request(user, user._raw_password)
        def solr_test(results_count):
            r = user_req.get('/recueils_da')
            assert r.status_code == 200, r
            assert len(r.data['_items']) == results_count
            results_id = {i['id'] for i in r.data['_items']}
            if results_count > 0:
                r = user_req.get('/recueils_da/%s' % r.data['_items'][0]['id'])
                assert r.status_code == 200, r
            # Search for a single one
            r = user_req.get('/recueils_da?q=prenom:Alain')
            assert r.status_code == 200, r
            assert len(r.data['_items']) == 1
            assert r.data['_items'][0]['id'] in results_id
            # Solr search should be filtered as well
            for query in ('q=prenom:Al*', 'q=nom:Terrieur'):
                r = user_req.get('/recueils_da?%s' % query)
                assert r.status_code == 200, r
                assert len(r.data['_items']) == results_count
                current_results_id = {i['id'] for i in r.data['_items']}
                assert not (current_results_id ^ results_id)
        # Given the permissions, I only can see the one related to me
        solr_test(1)
        # Can see if I'm from the GU of Prefecture assigned to this recueil
        gu_affecte = other_structure_accueil.guichets_uniques[0]
        user.test_set_accreditation(site_affecte=gu_affecte)
        user.save()
        solr_test(1)
        user.test_set_accreditation(site_affecte=gu_affecte.autorite_rattachement)
        user.save()
        solr_test(1)
        # Now change the permissions to be able to see all recueils
        user.permissions.append(p.recueil_da.prefecture_rattachee.sans_limite.name)
        user.save()
        solr_test(2)

    def test_adresse_field(self, user, pa_realise, ref_pays):
        user.permissions = [p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]
        user.save()
        user_req = self.make_auth_request(user, user._raw_password)
        pa_realise.usager_1.adresse = AddressEmbeddedDocument(
            chez='M. Alain',
            identifiant_ban="ADRNIVX_0000000274134436",
            numero_voie="55",
            voie="55 Rue de la Gare",
            code_insee="67447",
            code_postal="67300",
            ville="Schiltigheim",
            pays={'code': str(ref_pays[0].pk), 'libelle': ref_pays[0].libelle}
        )
        pa_realise.save()
        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)
        for search in ('rue de la gare', '67300', 'Schiltigheim', 'Alain gare',
                       ref_pays[0]['libelle']):
            r = user_req.get('/recueils_da?q=adresse:%s' % search)
            assert r.status_code == 200, r
            assert len(r.data['_items']) == 1, search

    def test_search_usager_existant(self, user, pa_realise, usager):
        user.permissions = [p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]
        user.save()
        user_req = self.make_auth_request(user, user._raw_password)
        usager.nom = 'Newton'
        usager.prenoms = ['Isaac']
        new_loc = Localisation(
            adresse=AddressEmbeddedDocument(
                chez='M. Alain',
                numero_voie="55",
                voie="55 Rue de la Gare",
                code_insee="67447",
                code_postal="67300",
                ville="Schiltigheim",
            )
        )
        usager.localisations.append(new_loc)
        usager.save()
        pa_realise.usager_1.usager_existant = usager
        for field in ('nom', 'prenoms', 'nationalites', 'ville_naissance',
                      'situation_familiale', 'langues_audition_OFPRA',
                      'prenom_pere', 'nom_pere', 'sexe', 'prenom_mere',
                      'adresse', 'langues', 'nom_mere', 'date_naissance',
                      'pays_naissance', 'vulnerabilite'):
            setattr(pa_realise.usager_1, field, None)
        pa_realise.usager_2 = None
        pa_realise.save()
        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)
        for field, search in (('nom', 'Newton'), ('nom', 'newton'), ('nom', 'new*'),
                              ('prenom', 'Isaac'), ('prenom_phon', 'isac'),
                              ('adresse', 'Schiltigheim')):
            r = user_req.get('/recueils_da?q=%s:%s' % (field, search))
            assert r.status_code == 200, r
            assert len(r.data['_items']) == 1, search
