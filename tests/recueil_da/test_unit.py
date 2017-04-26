import pytest
from mongoengine import ValidationError

from tests import common
from tests.fixtures import *

from sief.model.recueil_da import RecueilDA


class TestUnitRecueilDA(common.BaseTest):

    def test_bad_save(self, user, site_structure_accueil):
        # Cannot save without structure_accueil, agent_accueil fields
        recueil = RecueilDA()
        with pytest.raises(ValidationError):
            recueil.save()
        recueil.structure_accueil = site_structure_accueil
        with pytest.raises(ValidationError):
            recueil.save()
        recueil.structure_accueil = None
        recueil.agent_accueil = user
        with pytest.raises(ValidationError):
            recueil.save()
        recueil.structure_accueil = site_structure_accueil
        recueil.agent_accueil = user
        recueil.save()
