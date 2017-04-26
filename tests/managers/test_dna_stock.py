import pytest
import codecs
from tests import common
from tests.fixtures import *
import os
from mongoengine.errors import DoesNotExist

from sief.managers.dna_stock.commands import bootstrap, load_dna, delete_all_files, _find_usager_loader
from sief.managers.dna_stock.default_resources import DefaultRessources
from sief.managers.referentials_manager import referentials_manager
from sief.model import Usager, RecueilDA, DemandeAsile


def number_of_lines(file):
    fic = codecs.open(file, 'r', 'utf-8')
    lecture = fic.readlines()
    lignes = len(lecture)
    fic.close()
    return lignes


def check_usager_dna(prefecture_rattachee):
    usagers = [usager for usager in _find_usager_loader(
        prefecture_rattachee=prefecture_rattachee)]
    return len(usagers)


def get_list_of_recueil_demande(prefecture_rattachee):
    demande_asiles_id = []
    recueil_das_id = []

    for usager_loader in _find_usager_loader(prefecture_rattachee=prefecture_rattachee):
        for demande_asile in DemandeAsile.objects(usager=usager_loader):
            demande_asiles_id.append(demande_asile.id)
            recueil_das_id.append(demande_asile.recueil_da_origine.id)
    return demande_asiles_id, recueil_das_id


def check_delete(demande_asile_ids, recueil_das_id):
    for id in demande_asile_ids:
        assert not DemandeAsile.objects(id=id).first()
    for id in recueil_das_id:
        assert not RecueilDA.objects(id=id).first()


class TestDNAStock(common.BaseTest):

    def setup_method(self, method):
        super().setup_method(method)
        referentials_manager._commands['langue_iso6392']._commands['load'].run(
            input='./tests/managers/ressources/referential_langue.csv', delimiter=';')
        referentials_manager._commands['langue_OFPRA']._commands['load'].run(
            input='./tests/managers/ressources/referential_ofpra.csv', delimiter=';')
        referentials_manager._commands['pays']._commands['load'].run(
            input='./tests/managers/ressources/referential_pays.csv', delimiter=';')
        referentials_manager._commands['nationalites']._commands['load'].run(
            input='./tests/managers/ressources/referential_nationalite.csv', delimiter=';')

    def test_boostrap(self):
        bootstrap(dry=False)
        assert not DefaultRessources().has_missing

    def load_dna_file(self, input_file):
        output_file = input_file + ".output"
        bootstrap(dry=False)
        load_dna(input_file, delimiter=";", clean_messages=False, force=False)
        assert number_of_lines(input_file) == number_of_lines(output_file)
        if os.path.exists(output_file):
            os.remove(output_file)

    def test_load_dna_SI_ASILE_wrong_format(self):
        self.load_dna_file("./tests/managers/ressources/export_SI_ASILE.csv")
        assert check_usager_dna('loader-Prefecture') == 0

    def test_load_dna_SI_ASILE_good_format(self):
        self.load_dna_file("./tests/managers/ressources/export_SI_ASILE_v2.csv")
        assert check_usager_dna('loader-Prefecture') != 0

    def test_delete_all_files(self, usager):
        prefecture_rattachee = 'loader-Prefecture'
        input_file = "./tests/managers/ressources/export_SI_ASILE_v2.csv"
        self.load_dna_file(input_file)
        assert check_usager_dna(prefecture_rattachee) != 0
        demande_asiles_id, recueil_das_id = get_list_of_recueil_demande(prefecture_rattachee)

        output_file = input_file + ".delete.output"
        delete_all_files(
            yes=True, output=output_file, prefecture_rattachee=prefecture_rattachee, gu_rattachee='loader-GU')

        check_delete(demande_asiles_id, recueil_das_id)
        assert check_usager_dna(prefecture_rattachee) == 0
        assert Usager.objects(id=usager.id).first().id == usager.id

        if os.path.exists(output_file):
            os.remove(output_file)

    def test_delete_all_files_transfert_usagers(self, usager, site_prefecture):
        prefecture_rattachee = 'loader-Prefecture'
        input_file = "./tests/managers/ressources/export_SI_ASILE_v2.csv"

        self.load_dna_file(input_file)
        assert check_usager_dna('loader-Prefecture') != 0

        for usager_loader in _find_usager_loader(prefecture_rattachee=prefecture_rattachee):
            usager_loader.prefecture_rattachee = site_prefecture
            usager_loader.save()

        demande_asiles_id, recueil_das_id = get_list_of_recueil_demande(prefecture_rattachee)

        output_file = input_file + ".delete.output"
        delete_all_files(
            yes=True, output=output_file, prefecture_rattachee=prefecture_rattachee, gu_rattachee='loader-GU')

        check_delete(demande_asiles_id, recueil_das_id)

        assert check_usager_dna(prefecture_rattachee) == 0
        assert Usager.objects(id=usager.id).first().id == usager.id

        if os.path.exists(output_file):
            os.remove(output_file)
