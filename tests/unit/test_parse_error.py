from tests import common
from tests.fixtures import *

from core.model_util import parse_error_e11000


def test_e11000_good_error_syntax_qualif():
    error = "Tried to save duplicate unique keys (E11000 duplicate key error collection: sief.usager index: identifiant_agdref_1 dup key: { : \"7503002668\" })"
    treat_error = parse_error_e11000(error)
    expected = 'le champ identifiant_agdref doit être unique, valeur 7503002668 déjà existante'
    assert treat_error == expected


def test_e11000_good_error_syntax_local():
    error = 'Tried to save duplicate unique keys (E11000 duplicate key error index: sief-test.usager.$identifiant_agdref_1 dup key: { : "4923333741" })'
    treat_error = parse_error_e11000(error)
    expected = 'le champ identifiant_agdref doit être unique, valeur 4923333741 déjà existante'
    assert treat_error == expected
