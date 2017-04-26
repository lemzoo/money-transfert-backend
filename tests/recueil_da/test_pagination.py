import pytest

from tests import common
from tests.fixtures import *

from sief.model.recueil_da import RecueilDA
from sief.permissions import POLICIES as p


@pytest.fixture
def another_site_structure_accueil(request, site_gu):
    return site_structure_accueil(request, site_gu)


class TestPaginationRecueilDA_site_associe(common.BaseTest):

    def test_paginate_recueil_da_site_associe(self, user, another_user,
                                              site_structure_accueil,
                                              another_site_structure_accueil):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.voir.name]
        user.test_set_accreditation(site_affecte=site_structure_accueil)
        user.save()
        # Those recueils are not part of my site, cannot see them
        for i in range(50):
            new_recueil = RecueilDA(structure_accueil=another_site_structure_accueil,
                                    agent_accueil=another_user)
            new_recueil.save()
        # Those recueils are ok to be seen
        for i in range(50):
            new_recueil = RecueilDA(structure_accueil=site_structure_accueil,
                                    agent_accueil=user)
            new_recueil.save()
        # Now let's test the pagination !
        common.pagination_testbed(user_req, '/recueils_da')


class TestPaginationRecueilDA_all(common.BaseTest):

    def test_paginate_recueil_da_site_associe(self, user, another_user,
                                              site_structure_accueil,
                                              another_site_structure_accueil):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]
        user.test_set_accreditation(site_affecte=site_structure_accueil)
        user.save()
        # This time, part of my site or not, I can see everything !
        for i in range(25):
            new_recueil = RecueilDA(structure_accueil=another_site_structure_accueil,
                                    agent_accueil=another_user)
            new_recueil.save()
        for i in range(25):
            new_recueil = RecueilDA(structure_accueil=site_structure_accueil,
                                    agent_accueil=user)
            new_recueil.save()
        common.pagination_testbed(user_req, '/recueils_da')


class TestPaginationViewLimited(common.BaseTest):

    def test_search_limited(self, user, recueils, other_structure_accueil, other_gu):
        my_recueil, other_recueil = recueils
        # Let say we have two recueils: one from my site
        # and another not related to me
        my_recueil.structure_accueil = other_structure_accueil
        my_recueil.structure_guichet_unique = other_gu
        my_recueil.prefecture_rattachee = other_gu.autorite_rattachement
        my_recueil.save()
        # Sanity check
        assert other_structure_accueil.id != other_recueil.structure_accueil.id
        assert other_gu.id != other_recueil.structure_guichet_unique.id
        user.test_set_accreditation(site_affecte=other_structure_accueil)
        user.permissions = [p.recueil_da.voir.name]
        user.save()
        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)
        user_req = self.make_auth_request(user, user._raw_password)
        def view_test(results_count):
            r = user_req.get('/recueils_da')
            assert r.status_code == 200, r
            assert len(r.data['_items']) == results_count
            results_id = {i['id'] for i in r.data['_items']}
            if results_count > 0:
                r = user_req.get('/recueils_da/%s' % r.data['_items'][0]['id'])
                assert r.status_code == 200, r
        # Given the permissions, I only can see the one related to me
        view_test(1)
        # Can see if I'm from the GU of Prefecture assigned to this recueil
        gu_affecte = other_structure_accueil.guichets_uniques[0]
        user.test_set_accreditation(site_affecte=gu_affecte)
        user.save()
        view_test(1)
        user.test_set_accreditation(site_affecte=gu_affecte.autorite_rattachement)
        user.save()
        view_test(1)
        # Now change the permissions to be able to see all recueils
        user.permissions.append(p.recueil_da.prefecture_rattachee.sans_limite.name)
        user.save()
        view_test(2)
