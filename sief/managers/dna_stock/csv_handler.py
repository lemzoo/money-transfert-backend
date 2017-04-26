import csv
from datetime import datetime

from sief.managers.dna_stock.exceptions import DnaImportInvalidCSVError
from connector.dna.common import nat_code_trans, lang_code_trans, matrimonial_trans
from sief.model.fields import (ReferentialLangueIso6392EmbeddedDocument,
                               ReferentialNationaliteEmbeddedDocument)


HEADERS = ('identifiant_famille_dna', 'type_usager', 'identifiant_agdref',
           'identifiant_dna', 'nom', 'nom_usage', 'prenom', 'situation_familiale',
           'sexe', 'date_naissance', 'ville_naissance', 'nationalite', 'langue',
           'demandeur', 'identifiant_inerec', 'statut', 'procedure_type',
           'type_demandeur', 'date_entree_en_france', 'identifiant_portail')


RESULT_ADDITIONAL_HEADERS = (
    'id_recueil_demande', 'identifiant_usager', 'resultat', 'commentaire')

FULL_HEADERS = HEADERS + RESULT_ADDITIONAL_HEADERS


class Entry:

    """
    Single piece of information in the source csv (i.e. a row,
    letting appart the headers)
    """

    def __init__(self, row, full_headers=False):
        if (not full_headers and (len(row) != len(HEADERS)) or
                (full_headers and (len(row) != len(FULL_HEADERS)))):
            raise DnaImportInvalidCSVError("La ligne %s ne respecte pas les en-têtes" % row)
        self.base_row = row
        self.status = 'NOT_PROCESSED'
        self._comments = []
        self.id_recueil_demande = None
        self.identifiant_usager = None
        if full_headers:
            self.fields = {h: c or None for h, c in zip(FULL_HEADERS, row)}
        else:
            self.fields = {h: c or None for h, c in zip(HEADERS, row)}
        self._convert_booleans()
        self._convert_dates()
        self._convert_referentials()
        self._check_demandeur()

    def _convert_referentials(self):
        nat = nat_code_trans._deserialize(self.fields['nationalite'])
        if nat == 'und':
            self.set_error('Code nationalites invalide')
        else:
            self.fields['nationalite'] = ReferentialNationaliteEmbeddedDocument(code=nat)
        nat = lang_code_trans._deserialize(self.fields['langue'])
        self.fields['langue'] = ReferentialLangueIso6392EmbeddedDocument(code=nat)
        statut_mat = matrimonial_trans._deserialize(self.fields['situation_familiale'])
        if statut_mat == 'und':
            self.set_error('Statut familiale invalide')
        else:
            self.fields['situation_familiale'] = statut_mat

    def _check_demandeur(self):

        def check(field, exclusive):
            if self.fields['demandeur']:
                if not self.fields[field]:
                    self.set_error('Champ `%s` obligatoire si demandeur' % field)
            elif exclusive:
                if self.fields[field]:
                    self.set_error('Champ `%s` interdit si non demandeur' % field)
            else:
                if not self.fields[field]:
                    self.fields[field] = None
        if self.fields['demandeur']:
            if self.fields['type_usager'] != 'enfant' and not self.fields['type_demandeur']:
                self.set_error('Champ `type_demandeur` obligatoire si demandeur adulte')
            if self.fields['statut'] not in ("EN_ATTENTE_INTRODUCTION_OFPRA",
                                             "EN_COURS_PROCEDURE_DUBLIN",
                                             "EN_COURS_INSTRUCTION_OFPRA"):
                self.set_error('Statut `%s` interdit' % self.fields['statut'])

            if self.fields['procedure_type'] not in ("NORMALE",
                                                     "ACCELEREE",
                                                     "DUBLIN"):
                self.set_error('Type procedure `%s` interdit' % self.fields['procedure_type'])

            if (self.fields['procedure_type'] == 'DUBLIN' and not
                    self.fields['statut'] in ('EN_COURS_PROCEDURE_DUBLIN', 'FIN_PROCEDURE_DUBLIN')):
                self.set_error('Statut `%s` interdit en procédure DUBLIN' % self.fields['statut'])

            if self.fields['statut'] == 'EN_COURS_INSTRUCTION_OFPRA' and not (
                    self.fields['identifiant_inerec']):
                self.set_error('Identifiant inerec obligatoire si statut : %s' %
                               self.fields['statut'])

        for field, exclusive in (
                ('statut', True),
                ('procedure_type', True),
                ('date_entree_en_france', True),
                ('identifiant_agdref', False),
                ('ville_naissance', False),
                ('nom', False),
                ('prenom', False)):
            check(field, exclusive)

    def _convert_dates(self):
        value = self.fields['date_naissance']
        try:
            self.fields['date_naissance'] = datetime.strptime(value, '%Y%m%d')
        except (ValueError, TypeError):
            self.set_error('Date `date_naissance` invalide')
        if not self.fields['demandeur']:
            self.fields['date_entree_en_france'] = None
        else:
            value = self.fields['date_entree_en_france']
            try:
                self.fields['date_entree_en_france'] = datetime.strptime(value, '%Y%m%d')
            except (ValueError, TypeError):
                self.set_error('Date `date_entree_en_france` invalide')
            value = self.fields['date_entree_en_france']

    def _convert_booleans(self):
        value = self.fields['demandeur'].lower()
        if value == 'true':
            self.fields['demandeur'] = True
        elif value == 'false':
            self.fields['demandeur'] = False
        else:
            self.set_error('Booléen `demandeur` invalide')

    def add_comment(self, comment):
        self._comments.append(str(comment))

    @property
    def comment(self):
        return ' | '.join(self._comments)

    def set_error(self, comment):
        self.status = 'ERROR'
        self.add_comment(comment)

    def get_field(self, field):
        return self.fields.get(field)

    @property
    def result_row(self):
        return self.base_row + [self.id_recueil_demande, self.identifiant_usager,
                                self.status, self.comment]


def check_unicity(entries=None):
    if entries is None:
        return
    agdref = {}
    dna = {}
    for entry in entries:
        if entry.fields['identifiant_agdref']:
            if not agdref.get(entry.fields['identifiant_agdref']):
                agdref[entry.fields['identifiant_agdref']] = []
            agdref[entry.fields['identifiant_agdref']].append(entry)
        if entry.fields['identifiant_dna']:
            if not dna.get(entry.fields['identifiant_dna']):
                dna[entry.fields['identifiant_dna']] = []
            dna[entry.fields['identifiant_dna']].append(entry)

    for id, entries in agdref.items():
        if len(entries) > 1 and id:
            for entry in entries:
                entry.set_error("Doublon de l'identifiant AGDREF %s" % id)
    for id, entries in dna.items():
        if len(entries) > 1 and id:
            for entry in entries:
                entry.set_error("Doublon de l'identifiant DNA %s" % id)


def parse_input(csv_path, delimiter=',', full_headers=False):
    """
    Check input csv validity and convert it into a list of Entry objects
    """
    with open(csv_path, 'r') as fd:
        reader = csv.reader(fd, delimiter=delimiter, quoting=csv.QUOTE_NONE)
        # First check the headers
        headers = next(reader, None)
        if full_headers:
            if list(headers) != list(FULL_HEADERS):
                raise DnaImportInvalidCSVError(
                    'Invalid headers, was {} | should be {}'.format(headers, FULL_HEADERS))
        else:
            if list(headers) != list(HEADERS):
                raise DnaImportInvalidCSVError(
                    'Invalid headers, was {} | should be {}'.format(headers, HEADERS))

        # Then load the data rows
        entries = [Entry(r, full_headers) for r in reader]
        check_unicity(entries)
        return entries


def write_result(output_path, entries, delimiter=','):
    """
    Create a result csv file from the given Entry objects
    """
    with open(output_path, 'w') as fd:
        writer = csv.writer(fd, delimiter=delimiter)
        writer.writerow(HEADERS + RESULT_ADDITIONAL_HEADERS)
        writer.writerows(e.result_row for e in entries)
