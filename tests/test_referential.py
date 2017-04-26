import pytest

from tests import common
from tests.test_auth import user

from sief.model.referentials import LangueOfpra, LangueIso6392, Pays, Nationalite, CodeInseeAGDREF


@pytest.fixture
def ref_langues_ofpra(request):
    fr_ref = LangueOfpra(code='fra', libelle="Français")
    fr_ref.save()
    en_ref = LangueOfpra(code='eng', libelle="Anglais")
    en_ref.save()
    return (fr_ref, en_ref)


@pytest.fixture
def ref_langues_iso(request):
    fr_ref = LangueIso6392(code='fra', libelle="Français")
    fr_ref.save()
    en_ref = LangueIso6392(code='eng', libelle="Anglais")
    en_ref.save()
    return (fr_ref, en_ref)


@pytest.fixture
def ref_pays(request):
    fr_ref = Pays(code='fra', libelle="France")
    fr_ref.save()
    en_ref = Pays(code='ukr', libelle="Ukraine")
    en_ref.save()
    Pays(code='CIV', libelle="COTE D'IVOIRE").save()
    Pays(code='IRL', libelle="Irlande").save()
    return (fr_ref, en_ref)


@pytest.fixture
def ref_insee_agdref(request):
    ref_01 = CodeInseeAGDREF(code='01022', libelle="ARTEMARE")
    ref_01.save()
    ref_02 = CodeInseeAGDREF(code='01029', libelle="BEAUPONT")
    ref_02.save()
    ref_03 = CodeInseeAGDREF(code='75117', libelle="PARIS17")
    ref_03.save()
    return (ref_01, ref_02)


@pytest.fixture
def ref_nationalites(request):
    fr_ref = Nationalite(code='fra', libelle="Française")
    fr_ref.save()
    en_ref = Nationalite(code='eng', libelle="Anglaise")
    en_ref.save()
    ukr_ref = Nationalite(code='ukr', libelle="Ukrainienne")
    ukr_ref.save()
    Nationalite(code='CIV', libelle="ivoirienne").save()
    Pays(code='IRL', libelle="Irlandaise").save()
    return (fr_ref, en_ref, ukr_ref)


class TestReferential(common.BaseTest):

    def test_links(self, user):
        fr_ref = LangueOfpra(code='fre', libelle="Français")
        fr_ref.save()
        user_req = self.make_auth_request(user, user._raw_password)
        r = user_req.get('/referentiels/langues_OFPRA')
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'parent'])
        r = user_req.get('/referentiels/langues_OFPRA/%s' % fr_ref.pk)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'parent'])

    def test_get(self, user):
        fr_ref = LangueOfpra(code='fre', libelle="Français")
        fr_ref.save()
        en_ref = LangueOfpra(code='eng', libelle="Anglais")
        en_ref.save()
        user_req = self.make_auth_request(user, user._raw_password)
        r = user_req.get('/referentiels/langues_OFPRA')
        assert r.status_code == 200, r
        r = user_req.get('/referentiels/langues_OFPRA/%s' % fr_ref.pk)
        assert r.status_code == 200, r
        assert r.data['id'] == fr_ref.pk
        assert r.data['libelle'] == fr_ref.libelle

    def test_root(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        r = user_req.get('/referentiels')
        assert r.status_code == 200, r
        assert '_links' in r.data


class TestPaginationReferential(common.BaseTest):

    def test_paginate_ofpra(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        for i in range(50):
            ref = LangueOfpra(code='code-%s' % i, libelle="Langue %s" % i)
            ref.save()
        # Now let's test the pagination !
        common.pagination_testbed(user_req, '/referentiels/langues_OFPRA')
