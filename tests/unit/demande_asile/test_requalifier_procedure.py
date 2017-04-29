import pytest

from unittest import mock
from datetime import datetime
from freezegun import freeze_time
from tests import common
from tests.fixtures import *
from sief.model.demande_asile import _requalifier_procedure, RequalificationError, DemandeAsile, Procedure
from mongoengine import ValidationError


@pytest.fixture
def self_with_dublin_procedure():
    class FakeProcedure:
        type = "DUBLIN"
        acteur = "fakeActeur"
        motif_qualification = "fixtureQualification"
        date_notification = "fakeDateNotificationProcedure"
        requalifications = []

    class FakeDocument:
        procedure = FakeProcedure()
        statut = None

    class FakeSelf:
        document = FakeDocument()

    return FakeSelf()


@pytest.fixture
def self_with_dublin_procedure_en_cours():
    fake_self = self_with_dublin_procedure()
    fake_self.document.statut = "EN_COURS_PROCEDURE_DUBLIN"
    return fake_self


@pytest.fixture
def self_with_normale_procedure():
    fake_self = self_with_dublin_procedure()
    fake_self.document.procedure.type = "NORMALE"
    return fake_self


@mock.patch('sief.model.demande_asile.ProcedureRequalification')
@mock.patch('sief.model.demande_asile.Procedure')
class TestRequalifierProcedure(common.BaseTest):

    def test_fails_if_type_is_invalid(self, procedure_mock, procedure_requalification_mock):
        with pytest.raises(ValueError, message="Invalid type value"):
            _requalifier_procedure(None, "invalidType", None, None)

    def test_motif_qualification_is_mandatory_for_acteur_not_ofpra(self, procedure_mock, procedure_requalification_mock):
        with pytest.raises(RequalificationError, message="Le motif de qualification est obligatoire pour une requalification effectuée en préfecture."):
            _requalifier_procedure(None, "DUBLIN", "otherActeur", None, motif_qualification="")
        with pytest.raises(RequalificationError, message="Le motif de qualification est obligatoire pour une requalification effectuée en préfecture."):
            _requalifier_procedure(None, "DUBLIN", "invalidActeur", None, motif_qualification=None)

    def test_procedure_type_has_to_change_for_acteur_ofpra(self, procedure_mock, procedure_requalification_mock, self_with_dublin_procedure):
        with pytest.raises(RequalificationError, message="Impossible de requalifier sans changer le type de procédure"):
            _requalifier_procedure(
                self_with_dublin_procedure, "DUBLIN", "OFPRA", None, motif_qualification="")

    def test_motif_qualification_has_to_change(self, procedure_mock, procedure_requalification_mock, self_with_dublin_procedure):
        with pytest.raises(RequalificationError, message="Impossible de requalifier sans changer le motif de qualification"):
            _requalifier_procedure(
                self_with_dublin_procedure, "DUBLIN", None, None, motif_qualification="fixtureQualification")

    def test_document_statut_is_en_cours_procedure_dublin_when_type_is_dublin(self, procedure_mock, procedure_requalification_mock, self_with_normale_procedure):
        _requalifier_procedure(self_with_normale_procedure, "DUBLIN",
                               "OFPRA", None, motif_qualification="fakeMotifQualification_2")
        assert self_with_normale_procedure.document.statut == "EN_COURS_PROCEDURE_DUBLIN"

    def test_document_statut_is_en_attente_introduction_ofpra_when_document_statut_is_en_cours_procedure_dublin(self, procedure_mock, procedure_requalification_mock, self_with_dublin_procedure_en_cours):
        _requalifier_procedure(self_with_dublin_procedure_en_cours, "NORMALE",
                               "OFPRA", None, motif_qualification="fakeMotifQualification_2")
        assert self_with_dublin_procedure_en_cours.document.statut == "PRETE_EDITION_ATTESTATION"

    @freeze_time("2000-01-01")
    def test_it_creates_a_new_requalification_procedure_from_previous_procedure(self, procedure_mock, procedure_requalification_mock, self_with_dublin_procedure):
        _requalifier_procedure(self_with_dublin_procedure, "NORMALE", "OFPRA",
                               'fakeDateNotification', motif_qualification="fakeMotifQualification_2")
        procedure_requalification_mock.assert_called_once_with(
            ancien_type='DUBLIN',
            ancien_acteur='fakeActeur',
            ancien_motif_qualification='fixtureQualification',
            date_notification='fakeDateNotificationProcedure',
            date=datetime.utcnow()
        )

    @freeze_time("2000-01-01")
    def test_it_appends_the_new_requalification_procedure_to_the_requalifications_list(self, procedure_mock, procedure_requalification_mock, self_with_dublin_procedure):
        procedure_requalification_mock.return_value = 'fakeProcedureRequalification'
        _requalifier_procedure(self_with_dublin_procedure, "NORMALE", "OFPRA",
                               'fakeDateNotification', motif_qualification="fakeMotifQualification_2")
        procedure_mock.assert_called_once_with(
            type="NORMALE",
            acteur="OFPRA",
            motif_qualification="fakeMotifQualification_2",
            requalifications=['fakeProcedureRequalification'],
            date_notification='fakeDateNotification'
        )


@pytest.fixture
def procedure(da_orientation_payload):
    return DemandeAsile(**da_orientation_payload)


@pytest.fixture
def demande_asile(da_orientation_payload):
    return DemandeAsile(**da_orientation_payload)


@pytest.fixture
def procedure():
    procedure = Procedure(
        acteur='GUICHET_UNIQUE',
        type='NORMALE',
        motif_qualification='PNOR',
        date_notification=datetime.utcnow()
    )
    return procedure


class TestProcedureCreation():

    def test_procedure_has_a_type(self, procedure):
        assert procedure.type

    def test_procedure_has_a_motif_qualification(self, procedure):
        assert procedure.motif_qualification

    def test_procedure_has_an_acteur(self, procedure):
        assert procedure.acteur

    def test_procedure_has_a_date_notification(self, procedure):
        assert procedure.date_notification


class TestProcedureValidation():

    def test_fails_when_type_is_invalid(self):
        procedure = Procedure(type='invalidType')
        with pytest.raises(ValidationError):
            procedure.validate()

    def test_passes_when_type_is_dublin(self):
        procedure = Procedure(type='DUBLIN', motif_qualification='BDS')
        procedure.validate()

    def test_passes_when_type_is_normale(self):
        procedure = Procedure(type='NORMALE', motif_qualification='PNOR')
        procedure.validate()

    def test_passes_when_type_is_acceleree(self):
        procedure = Procedure(type='ACCELEREE', motif_qualification='1C5')
        procedure.validate()

    def test_fails_when_motif_qualification_is_invalid(self):
        procedure = Procedure(type='ACCELEREE', motif_qualification='fakeInvalidMotif')
        with pytest.raises(ValidationError):
            procedure.validate()

    def test_fails_when_type_is_dublin_and_motif_is_invalid(self):
        procedure = Procedure(type='DUBLIN', motif_qualification='fakeInvalidMotif')
        with pytest.raises(ValidationError):
            procedure.validate()

    def test_fails_when_type_is_dublin_and_motif_is_invalid(self):
        procedure = Procedure(type='NORMALE', motif_qualification='fakeInvalidMotif')
        with pytest.raises(ValidationError):
            procedure.validate()

    def test_fails_when_acteur_is_invalid(self):
        procedure = Procedure(acteur='fakeInvalidActeur')
        with pytest.raises(ValidationError):
            procedure.validate()

    def test_assigns_acteur_guichet_unique_when_not_provided(self):
        procedure = Procedure()
        assert procedure.acteur == 'GUICHET_UNIQUE'

    def test_passes_when_acteur_is_guichet_unique(self):
        procedure = Procedure(acteur='GUICHET_UNIQUE', type='NORMALE', motif_qualification='PNOR')
        procedure.validate()

    def test_passes_when_acteur_is_prefecture(self):
        procedure = Procedure(acteur='PREFECTURE', type='NORMALE', motif_qualification='PNOR')
        procedure.validate()

    def test_passes_when_acteur_is_ofpra(self):
        procedure = Procedure(acteur='OFPRA', type='NORMALE', motif_qualification='PNOR')
        procedure.validate()
