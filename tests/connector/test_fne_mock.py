from tests import common
from tests.connector.common import MockFNELookup

import services


class TestFNEMock(common.BaseTest):
    def test_mock_start_stop(self):
        """Check that start() and stop() work correctly."""
        mock = MockFNELookup()
        mock.start()
        r = services.fne.lookup_fne(prenom='A', nom='B', sexe='M')
        # Check a few fields just to be sure
        assert 'identifiant_agdref' in r
        assert r['identifiant_agdref'] == 'identifiant_agdref'
        assert 'pays_naissance' in r
        assert r['pays_naissance'] == 'paysNaissance'
        assert 'referenceReglementaire' in r
        assert r['referenceReglementaire'] == 'referenceReglementaire'
        mock.stop()

    def test_mock_context_manager(self):
        """Check that the call can be used as a context manager."""
        with MockFNELookup():
            r = services.fne.lookup_fne(prenom='A', nom='B', sexe='M')
            # Check a few fields just to be sure
            assert 'identifiant_agdref' in r
            assert r['identifiant_agdref'] == 'identifiant_agdref'
            assert 'pays_naissance' in r
            assert r['pays_naissance'] == 'paysNaissance'
            assert 'referenceReglementaire' in r
            assert r['referenceReglementaire'] == 'referenceReglementaire'

    def test_call_fne_config_query(self):
        """Check that the call to fne_config.query() is also replaced."""
        with MockFNELookup():
            r = services.fne.fne_config.query(prenom='A', nom='B', sexe='M')
            # Check a few fields just to be sure
            assert 'identifiant_agdref' in r
            assert r['identifiant_agdref'] == 'identifiant_agdref'
            assert 'pays_naissance' in r
            assert r['pays_naissance'] == 'paysNaissance'
            assert 'referenceReglementaire' in r
            assert r['referenceReglementaire'] == 'referenceReglementaire'
