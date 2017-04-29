import pytest
from connector.agdref.edition_attestation_demande_asile import _compute_duree_validite
from connector.tools import retrieve_last_demande_for_given_usager
from random import shuffle


def test_unit_duree_validitee():
    for duration, expected_code in (
            (30, '0001'),
            (28, '0001'),
            (32, '0001'),
            (90, '0003'),
            (91, '0003'),
            (104, '0003'),
            (105, '0003'),
            (106, '0004'),
            (121, '0004'),
            (180, '0006'),
            (320, '0009')
    ):
        assert _compute_duree_validite(duration) == expected_code, (duration, expected_code)


def test_retrieve_last_demande_for_given_usager():

    def _build_data_recueil(identifiant_agdref, _created):
        recueils = [{'usager_1': {'identifiant_agdref': identifiant_agdref + 1, 'demandeur': True},
                     'usager_2': {'identifiant_agdref': identifiant_agdref + 2, 'demandeur': False},
                     'enfants': [{'identifiant_agdref': identifiant_agdref + 3, 'demandeur': True},
                                 {'identifiant_agdref': identifiant_agdref + 4, 'demandeur': False}],
                     '_created': _created}]
        recueils.append({'usager_1': {'identifiant_agdref': identifiant_agdref + 1, 'demandeur': False},
                         'usager_2': {'identifiant_agdref': identifiant_agdref + 2, 'demandeur': True},
                         'enfants': [{'identifiant_agdref': identifiant_agdref + 3, 'demandeur': False},
                                     {'identifiant_agdref': identifiant_agdref + 4, 'demandeur': True}],
                         '_created': _created + 1})
        identifiant_agdref += 4
        _created += 1
        return recueils

    recueils_da = []
    identifiant_agdref = 0
    _created = 0
    for _ in range(0, 10):
        recueils_da.extend(_build_data_recueil(identifiant_agdref, _created))
        identifiant_agdref += 4
        _created += 1

    shuffle(recueils_da)
    for i in range(1, identifiant_agdref):
        usager = retrieve_last_demande_for_given_usager(recueils_da, i, None)
        assert usager['demandeur'] == True
        assert usager['identifiant_agdref'] == i


def test_retrieve_last_demande_for_given_usager_in_multiple_recueil():
    recueils_da = [{'usager_1': {'identifiant_agdref': 1, 'demandeur': True},
                    '_created': 1}]
    recueils_da.append({'usager_1': {'identifiant_agdref': 3, 'demandeur': True},
                        '_created': 2})
    recueils_da.append({'usager_1': {'identifiant_agdref': 2, 'demandeur': True},
                        '_created': 3})
    recueils_da.append({'usager_1': {'identifiant_agdref': 1, 'demandeur': True, 'this is the one': True},
                        '_created': 4})
    shuffle(recueils_da)
    usager = retrieve_last_demande_for_given_usager(recueils_da, 1, None)
    assert usager['identifiant_agdref'] == 1
    assert usager['this is the one'] == True
