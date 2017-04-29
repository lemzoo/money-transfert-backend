import pytest
from datetime import datetime

from tests import common
from tests.test_auth import user

from sief.permissions import POLICIES as p
from sief.model.site import Prefecture
from sief.model.utilisateur import Utilisateur
from core.model_util import fields, BaseSolrSearcher, BaseDocument


@pytest.fixture
def query_base(request):
    u = user(request, nom='Mérovingiens', prenom='Clovis', email='clovis@mero.fr')
    u.doc_created = datetime(466, 1, 1)
    u.save()
    u = user(request, nom='Carolingiens', prenom='Charles Martel', email='charles.martel@caro.fr')
    u.doc_created = datetime(690, 1, 1)
    u.save()
    user(request, nom='Carolingiens', prenom='Charlemagne', email='charlemagne@caro.fr')
    user(request, nom='Carolingiens', prenom='Pépin le Bref', email='plb@caro.fr')
    user(request, nom='Capétiens', prenom='Hugues', email='hugues@capet.fr')
    user(request, nom='Capétiens', prenom='Robert II', email='robert2@capet.fr')


def _assert_results(r, total, msg=None, page=1, per_page=None):
    msg = msg or r.data
    assert r.status_code == 200, msg
    assert '_items' in r.data, msg
    assert '_meta' in r.data, msg
    assert r.data['_meta']['page'] == page, msg
    assert r.data['_meta']['total'] == total, msg
    if per_page:
        assert r.data['_meta']['per_page'] == per_page, msg
    else:
        assert 'per_page' in r.data['_meta'], msg
        per_page = r.data['_meta']['per_page']
    if per_page >= total:
        assert len(r.data['_items']) == total, msg
    elif page * per_page > total:
        assert len(r.data['_items']) == total - (page - 1) * per_page, msg
    else:
        assert len(r.data['_items']) == per_page, msg


class TestSolr(common.BaseSolrTest):

    def test_q(self, user, query_base):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.voir.name,
                            p.utilisateur.sans_limite_site_affecte.name]
        user.save()
        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)
        r = user_req.get('/utilisateurs?q=')
        _assert_results(r, 7)
        r = user_req.get('/utilisateurs?q=nom:Capétiens AND prenom:Hugues')
        _assert_results(r, 1)
        for req, results in [('prenom:Hugues', 1),
                             ('nom:Ca*', 5),
                             ('nom:ca*', 5),  # TODO: fix casesensitive
                             ('nom:Cape*', 2),
                             ('nom:capetiens', 2),
                             ('nom:Capétiens OR nom:Carolingiens', 5),
                             ('nom:Carolingiens AND prenom:Charl*', 2),
                             ('email:*@caro.fr', 3),
                             ('NOT Charle*', 5),
                             ('_created:[1995-12-31T23:59:59Z TO NOW]', 5)
                             ]:
            r = user_req.get('/utilisateurs?q=' + req)
            _assert_results(r, results, (req, results))

    def test_fq(self, user, query_base):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.voir.name,
                            p.utilisateur.sans_limite_site_affecte.name]
        user.save()
        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)
        r = user_req.get('/utilisateurs?fq=prenom:Hugues&fqnom:Capétiens')
        _assert_results(r, 1)
        r = user_req.get('/utilisateurs?q=&fq=prenom:Hugues&fqnom:Capétiens')
        _assert_results(r, 1)

    def test_sort(self, user, query_base):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.voir.name,
                            p.utilisateur.sans_limite_site_affecte.name]
        user.save()
        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)
        r = user_req.get('/utilisateurs?sort=nom asc,prenom asc')
        list_asc = r.data['_items']
        r = user_req.get('/utilisateurs?sort=nom desc&sort=prenom desc')
        list_desc = r.data['_items']
        assert len(list_desc) == len(list_asc)
        size = len(list_asc)
        for i in range(size):
            assert list_asc[i] == list_desc[size - 1 - i]

    def test_dont_mix_collections(self, user, query_base):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.voir.name,
                            p.utilisateur.sans_limite_site_affecte.name]
        user.save()

        class FamilySearcher(BaseSolrSearcher):
            FIELDS = ('nom',)

        class Family(BaseDocument):
            meta = {'searcher_cls': FamilySearcher}
            nom = fields.StringField()
        caro_family = Family(nom='Carolingiens').save()
        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)
        # If we search for the utilisateurs, we should not find this document
        r = user_req.get('/utilisateurs?fq=nom:Carolingiens')
        _assert_results(r, 3)
        # Same thing for the Family document
        result = caro_family.search_or_abort(fq=['nom:Carolingiens'])
        assert len(result.items) == 1

    def test_pagination(self, user, query_base):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.voir.name,
                            p.utilisateur.sans_limite_site_affecte.name]
        user.save()
        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)
        r = user_req.get('/utilisateurs?fq=nom:Carolingiens')
        _assert_results(r, 3)
        for page, per_page in ((1, 1), (2, 1), (1, 2), (2, 2)):
            r = user_req.get('/utilisateurs?fq=nom:Carolingiens&page=%s&per_page=%s' %
                             (page, per_page))
            _assert_results(r, 3, per_page=per_page, page=page,
                            msg={'page': page, 'per_page': per_page})

    def test_phon(self, user, query_base):
        # Patronyme field provides phonetic search
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.voir.name,
                            p.utilisateur.sans_limite_site_affecte.name]
        user.save()
        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)
        for req, results in [('prenom_phon:hugues', 1),
                             ('prenom_phon:charles', 1),
                             ('nom_phon:capetien', 2),
                             ('nom_phon:kapetiens', 2),
                             ('nom_phon:Karolingien', 3),
                             ]:
            r = user_req.get('/utilisateurs?q=' + req)
            _assert_results(r, results, (req, results))

    def test_base_text(self, user, query_base):
        # Test search without field
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.voir.name,
                            p.utilisateur.sans_limite_site_affecte.name]
        user.save()
        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)
        for req, results in [('hugues', 1), ('HUGUES', 1),
                             ('capetiens', 2)]:
            r = user_req.get('/utilisateurs?q=' + req)
            _assert_results(r, results, (req, results))
