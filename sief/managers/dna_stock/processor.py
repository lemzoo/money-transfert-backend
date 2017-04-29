from datetime import datetime
import unicodedata

from mongoengine import ValidationError, NotUniqueError
from sief.model.recueil_da import (RecueilDA, UsagerPrincipalRecueil,
                                   UsagerSecondaireRecueil, UsagerEnfantRecueil)
from sief.model.demande_asile import DemandeAsile
from sief.model.fields import AddressEmbeddedDocument
from sief.model.usager import Usager
from sief.model.recueil_da import ExploiteError, DemandeursIdentifiesError
from connector.dna.common import format_text
from werkzeug.exceptions import BadRequest
from core.concurrency import ConcurrencyError


class AbstractProcessor:

    def __init__(self, default_resources):
        self.entries = []
        self.default_resources = default_resources

    def insert_entry(self, entry):
        self.entries.append(entry)

    def process(self, force=False):
        raise NotImplementedError()


class Family:
    DEFAULT_RESOURCES = None

    def __init__(self, family_id):
        assert self.DEFAULT_RESOURCES
        self.family_id = family_id
        self.members = []

    def insert_member(self, entry):
        assert entry.fields['identifiant_famille_dna'] == self.family_id
        self.members.append(entry)

    def process(self, force=False):
        # Make sure
        if next((True for m in self.members if m.status != 'NOT_PROCESSED'), False):
            self._set_entry_members_status('ERROR', 'Des membres de la famille sont en erreur')
            return
        success = True
        errors = []
        # Process data
        usager_1 = [m for m in self.members if m.fields['type_usager'] == 'usager_1']
        usager_2 = [m for m in self.members if m.fields['type_usager'] == 'usager_2']
        enfants = [m for m in self.members if m.fields['type_usager'] == 'enfant']
        usager_portail_1 = None
        usager_portail_2 = None
        if len(usager_1) != 1 or (len(usager_2) not in (0, 1)):
            self._set_entry_members_status(
                'ERROR',
                "La famille doit contenir un unique usager_1 et soit aucun soit un seul usager_2")
            return

        # Flux or Stock ?
        # is id_portail forced ?
        if usager_1[0].fields['identifiant_portail']:
            usager_portail_1 = Usager.objects(id=usager_1[0].fields['identifiant_portail']).first()
            if not usager_portail_1:
                errors.append("L'usager %s n'est pas connu de la pateforme" %
                              usager_1[0].fields['identifiant_portail'])
        elif usager_1[0].fields['identifiant_agdref']:
            usager_portail_1 = Usager.objects(
                identifiant_agdref=usager_1[0].fields['identifiant_agdref']).first()
        if len(usager_2) and usager_2[0].fields['identifiant_portail']:
            usager_portail_2 = Usager.objects(id=usager_2[0].fields['identifiant_portail']).first()
            if not usager_portail_2:
                errors.append("L'usager %s n'est pas connu de la pateforme" %
                              usager_2[0].fields['identifiant_portail'])
        elif len(usager_2) and usager_2[0].fields['identifiant_agdref']:
            usager_portail_2 = Usager.objects(
                identifiant_agdref=usager_2[0].fields['identifiant_agdref']).first()
        if (not usager_1[0].fields['identifiant_portail'] and
                (usager_1[0].fields['identifiant_agdref'] and usager_portail_1)):
            if len(usager_2) and usager_2[0].fields['identifiant_agdref'] and not usager_portail_2:
                errors.append("L'usager 2 de la famille n'est pas connu de la pateforme")
        if (len(usager_2) and not usager_2[0].fields['identifiant_portail'] and
                usager_2[0].fields['identifiant_agdref'] and usager_portail_2):
            if usager_1[0].fields['identifiant_agdref'] and not usager_portail_1:
                errors.append("L'usager 1 de la famille n'est pas connu de la pateforme")
        if errors:
            self._set_entry_members_status('ERROR', '|'.join(errors))
            success = False

        # Flux
        if usager_portail_1 or usager_portail_2:
            if not errors:
                self._set_entry_members_status('DONE')

            da = DemandeAsile.objects(usager=usager_portail_1).first()
            if not da and usager_portail_2:
                da = DemandeAsile.objects(usager=usager_portail_2).first()
            rda = None
            if da:
                rda = da.recueil_da_origine
            if not rda:
                self._set_entry_members_status(
                    'ERROR',
                    'Flux : Impossible de trouver le recueil associé à la demande')
                return

            def check_name(n1, n2):
                n1 = format_text(unicodedata.normalize('NFKD', n1).encode(
                    'ascii', 'ignore').decode(), max=20)
                n2 = format_text(unicodedata.normalize('NFKD', n2).encode(
                    'ascii', 'ignore').decode(), max=20)
                return n1 == n2

            def lookup_and_set(enfantDNA, enfants, rda, dry_run=True, force=False):
                for ef in enfants:
                    if not ef.usager_existant:
                        continue
                    if (check_name(ef.usager_existant.nom, enfantDNA.fields['nom']) and
                            check_name(ef.usager_existant.prenoms[0], enfantDNA.fields['prenom'])):
                        ef.usager_existant.identifiant_famille_dna = enfantDNA.fields[
                            'identifiant_famille_dna']
                        enfantDNA.identifiant_usager = ef.usager_existant.id
                        enfantDNA.id_recueil_demande = rda
                        if force or ef.usager_existant.identifiant_dna in (None, ''):
                            if not dry_run:
                                ef.usager_existant.identifiant_dna = enfantDNA.fields[
                                    'identifiant_dna']
                                try:
                                    ef.usager_existant.save()
                                except (ValidationError, NotUniqueError, ConcurrencyError) as exc:
                                    self._set_entry_members_status('ERROR', comment=exc)
                                    return False
                        else:
                            if not dry_run:
                                enfantDNA.add_comment('Usager déjà synchronisé')
                        return True
                return False

            check = [lookup_and_set(child, rda.enfants, rda.id) for child in enfants]
            if check and not all(check):
                self._set_entry_members_status(
                    'ERROR',
                    comment='Les enfants du recueil %s ne correspondent pas' % rda.id)
                success = False
            else:
                for child in enfants:
                    lookup_and_set(child, rda.enfants, rda.id, dry_run=False, force=force)
            if usager_portail_1:
                usager_1[0].identifiant_usager = usager_portail_1.id
                usager_1[0].id_recueil_demande = rda.id
                if force or usager_portail_1.identifiant_dna in (None, ''):
                    usager_portail_1.identifiant_famille_dna = usager_1[
                        0].fields['identifiant_famille_dna']
                    usager_portail_1.identifiant_dna = usager_1[0].fields['identifiant_dna']
                    try:
                        usager_portail_1.save()
                    except (ValidationError, NotUniqueError, ConcurrencyError) as exc:
                        self._set_entry_members_status('ERROR', comment=exc)
                        return
                else:
                    usager_1[0].add_comment('Usager déjà synchronisé')

            if usager_portail_2:
                usager_2[0].identifiant_usager = usager_portail_2.id
                usager_2[0].id_recueil_demande = rda.id
                if force or usager_portail_2.identifiant_dna in (None, ''):
                    usager_portail_2.identifiant_famille_dna = usager_2[
                        0].fields['identifiant_famille_dna']
                    usager_portail_2.identifiant_dna = usager_2[0].fields['identifiant_dna']
                    try:
                        usager_portail_2.save()
                    except (ValidationError, NotUniqueError, ConcurrencyError) as exc:
                        self._set_entry_members_status('ERROR', comment=exc)
                        return
                else:
                    usager_2[0].add_comment('Usager déjà synchronisé')

            return success

        else:  # Stock
            if errors:
                return
            recueil = RecueilDA(
                identifiant_famille_dna=self.family_id,
                structure_accueil=self.DEFAULT_RESOURCES.gu,
                agent_accueil=self.DEFAULT_RESOURCES.user,
                structure_guichet_unique=self.DEFAULT_RESOURCES.gu,
                prefecture_rattachee=self.DEFAULT_RESOURCES.pref,
                date_transmission=self.DEFAULT_RESOURCES.now,
                statut='PA_REALISE')

            def build_usager(fields, type='principal'):
                assert type in ('principal', 'secondaire', 'enfant')
                kwargs = {
                    'nom': fields['nom'],
                    'nom_usage': fields['nom_usage'],
                    'origine_nom': 'EUROPE',
                    'prenoms': [fields['prenom']],
                    'sexe': fields['sexe'],
                    'adresse': AddressEmbeddedDocument(adresse_inconnue=True),
                    'nationalites': [fields['nationalite']],
                    'date_naissance': fields['date_naissance'],
                    'ville_naissance': fields['ville_naissance'],
                    'pays_naissance': self.DEFAULT_RESOURCES.pays_naissance,
                    'demandeur': fields['demandeur'],
                    'present_au_moment_de_la_demande': True,
                    'conditions_exceptionnelles_accueil': False,
                    'identite_approchante_select': True
                }
                if kwargs['nom_usage'] not in ('', None):
                    kwargs.update({'origine_nom_usage': 'EUROPE'})
                if fields['demandeur']:
                    if fields['procedure_type'] == 'NORMALE':
                        qualif = 'PNOR'
                    elif fields['procedure_type'] == 'ACCELEREE':
                        qualif = '1C5'
                    else:  # DUBLIN
                        qualif = 'BDS'
                    kwargs.update({
                        'identifiant_agdref': fields['identifiant_agdref'],
                        'date_entree_en_france': fields['date_entree_en_france'],
                        'date_entree_en_france_approximative': False,
                        'date_depart': fields['date_entree_en_france'],
                        'date_depart_approximative': True,
                        'langues': [fields['langue']],
                        'langues_audition_OFPRA': [self.DEFAULT_RESOURCES.langue_OFPRA],
                        'photo': self.DEFAULT_RESOURCES.photo,
                        'type_procedure': fields['procedure_type'],
                        'condition_entree_france': 'REGULIERE',
                        'date_decision_sur_attestation': self.DEFAULT_RESOURCES.now,
                        'motif_qualification_procedure': qualif,
                        'decision_sur_attestation': False,
                        'visa': 'AUCUN',
                        'indicateur_visa_long_sejour': False,
                        'identite_approchante_select': True,
                        'identifiant_eurodac': fields['identifiant_agdref']
                    })
                if type == 'principal':
                    return UsagerPrincipalRecueil(
                        situation_familiale=fields['situation_familiale'],
                        **kwargs)
                elif type == 'secondaire':
                    return UsagerSecondaireRecueil(**kwargs)
                elif type == 'enfant':
                    return UsagerEnfantRecueil(
                        situation_familiale=fields['situation_familiale'],
                        usager_1=True, usager_2=True,
                        **kwargs)

            bind_ids = []
            if len(usager_1) == 0:
                errors.append('Un usager_1 est requis dans la famille')
            elif len(usager_1) > 1:
                errors.append("Il ne doit y avoir qu'un usager_1 dans la famille")
            else:
                recueil.usager_1 = build_usager(usager_1[0].fields, type='principal')
                bind_ids.append((usager_1[0], recueil.usager_1))
            if len(usager_2) > 1:
                errors.append("Il ne peut pas y avoir plus d'un usager_2 dans la famille")
            elif usager_2:
                if usager_1[0].fields['situation_familiale'] != \
                   usager_2[0].fields['situation_familiale']:
                    errors.append(
                        "L'usager 2 ne peut avoir un statut matrimonial différent de l'usager 1")
                recueil.usager_2 = build_usager(usager_2[0].fields, type='secondaire')
                bind_ids.append((usager_2[0], recueil.usager_2))
            elif recueil.usager_1 and recueil.usager_1.situation_familiale in \
                    ('MARIE', 'PACSE', 'CONCUBIN'):
                # Create a fake second user
                recueil.usager_2 = build_usager({
                    'nom': 'Nom inconnu',
                    'nom_usage': None,
                    'origine_nom': 'EUROPE',
                    'prenom': "Prénom inconnu",
                    'sexe': 'F' if recueil.usager_1.sexe == 'M' else 'M',
                    'adresse': AddressEmbeddedDocument(adresse_inconnue=True),
                    'nationalite': self.DEFAULT_RESOURCES.nationalite,
                    'date_naissance': datetime(1900, 1, 1),
                    'ville_naissance': 'Ville inconnue',
                    'pays_naissance': self.DEFAULT_RESOURCES.pays_naissance,
                    'demandeur': False,
                    'present_au_moment_de_la_demande': False,
                    'identite_approchante_select': True
                }, type='secondaire')
            if enfants:
                recueil.enfants = []
                for enfant in enfants:
                    # Check AGDREF and sync instead of create
                    if enfant.fields['identifiant_agdref'] not in (None, ''):
                        check = Usager.objects(
                            identifiant_agdref=enfant.fields['identifiant_agdref']).first()
                        if check:
                            check.identifiant_dna = enfant.fields['identifiant_dna']
                            enfant.fields['identifiant_usager'] = check.id
                            try:
                                check.save()
                            except (ValidationError, NotUniqueError) as exc:
                                self._set_entry_members_status('ERROR', comment=exc)
                                return
                    else:
                        usager = build_usager(enfant.fields, type='enfant')
                        recueil.enfants.append(usager)
                        bind_ids.append((enfant, usager))
            if errors:
                self._set_entry_members_status('ERROR', '\n'.join(errors))
                return
            # OFII doesn't have 'MINEUR_ISOLE' and 'MINEUR_ACCOMPAGNANT'
            if len(self.members) > 1:
                recueil.profil_demande = 'FAMILLE'
            else:
                recueil.profil_demande = 'ADULTE_ISOLE'
            try:
                recueil.controller.identifier_demandeurs()
                recueil.controller.exploiter(agent=self.DEFAULT_RESOURCES.user)
                recueil.save()
            except (ValidationError, ExploiteError, DemandeursIdentifiesError,
                    BadRequest, ConcurrencyError) as exc:
                self._set_entry_members_status('ERROR', comment=exc)
                return
            self._set_entry_members_status('DONE')

            # Check status and process
            def set_info_dna(usager, fields):
                # Get the "real usager"
                usager = usager.usager_existant
                usager.identifiant_dna = fields['identifiant_dna']
                try:
                    usager.save()
                except (ValidationError, NotUniqueError) as exc:
                    self._set_entry_members_status('ERROR', comment=exc)
                    return

            def check_status(usager, fields):
                if not usager:
                    return
                da = usager.demande_asile_resultante
                if not da:
                    return
                da.decision_sur_attestation = True
                if fields['statut'] == 'EN_ATTENTE_INTRODUCTION_OFPRA':
                    da.controller.passer_en_attente_introduction_ofpra()
                elif fields['statut'] == 'EN_COURS_INSTRUCTION_OFPRA':
                    da.controller.passer_en_attente_introduction_ofpra()
                    da.controller.introduire_ofpra(
                        fields['identifiant_inerec'], datetime.utcnow())
                elif fields['statut'] == 'EN_COURS_PROCEDURE_DUBLIN':
                    da.statut = 'EN_COURS_PROCEDURE_DUBLIN'
                try:
                    da.save()
                except ValidationError as exc:
                    self._set_entry_members_status('ERROR', comment=exc)
                    return

            # Write back the ids and check status
            for entry, usager in bind_ids:
                entry.id_recueil_demande = recueil.id
                entry.identifiant_usager = usager.usager_existant.id
                check_status(usager, entry.fields)
                set_info_dna(usager, entry.fields)

            return recueil

    def _set_entry_members_status(self, status, comment=None):
        for m in self.members:
            m.status = status
            if comment:
                m.add_comment(comment)


class StockProcessor(AbstractProcessor):

    def __init__(self, default_resources):
        super().__init__(default_resources)

        class ConfiguredFamily(Family):
            DEFAULT_RESOURCES = default_resources

        self.family_cls = ConfiguredFamily
        self.families = {}

    def insert_entry(self, entry):
        family_id = entry.fields['identifiant_famille_dna']
        if family_id not in self.families:
            self.families[family_id] = self.family_cls(family_id)
        self.families[family_id].insert_member(entry)

    def process(self, force=False):
        print('Processing STOCK elements', flush=True, end='')
        for family in self.families.values():
            if family.process(force):
                print('.', flush=True, end='')
            else:
                print('F', flush=True, end='')
        print('  Done !')


def process(entries, default_resources, force=False):
    stock_processor = StockProcessor(default_resources)
    for entry in entries:
        stock_processor.insert_entry(entry)
    stock_processor.process(force)
