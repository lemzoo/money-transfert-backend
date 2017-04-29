#! /usr/bin/env python3

import os

from flask.ext.script import Manager, prompt
from sief.model import DemandeAsile, Utilisateur, Droit
from mongoengine import ValidationError
from csv import reader, QUOTE_NONE, writer


demande_asile_manager = Manager(usage="Perform operations on DemandeAsile")


def update_usager(usager):
    usager.date_depart = None
    usager.date_entree_en_france = None
    usager.representant_legal_prenom = None
    usager.representant_legal_nom = None
    usager.demandeur = False
    usager.demande_asile_resultante = None


@demande_asile_manager.option('-d', '--demande_asile_id', help="id of the \"demande d'asile\"")
def delete(demande_asile_id=None):

    demande_asile_id = demande_asile_id or prompt("id de la demande d'asile")
    demande_asile = DemandeAsile.objects(id=demande_asile_id).first()
    if not demande_asile:
        print("Impossible de charger la demande d'asile %s, cette demande d'asile est inexistante" %
              demande_asile_id)
        return
    if prompt("êtes vous sur de vouloir supprimer cette demande d'asile?(o/n)").lower() \
            not in ('y', 'o'):
        return
    id_usager = demande_asile.usager.id
    recueil_da = demande_asile.recueil_da_origine
    print("mise à jour de l'usager %s dans le recueil %s au statut demandeur = False" %
          (id_usager, recueil_da.id))
    if recueil_da.usager_1 and recueil_da.usager_1.usager_existant.id == id_usager:
        update_usager(recueil_da.usager_1)
    elif recueil_da.usager_2 and recueil_da.usager_2.usager_existant.id == id_usager:
        update_usager(recueil_da.usager_2)
    elif recueil_da.enfants:
        for e in recueil_da.enfants:
            if e.usager_existant and e.usager_existant.id == id_usager:
                update_usager(e)
    try:
        recueil_da.save()
    except ValidationError as exc:
        print("une erreur a été rencontré, arrêt de la suppression de la demande d'asile (%s)" %
              str(exc))
        return
    demande_asile.delete()
    print("suppression de la demande d'asile effectuée")


@demande_asile_manager.option('-f', '--input_file',
                              help="file containing the list of \"demande d'asile\" id to edit")
@demande_asile_manager.option('-e', '--email',
                              help="email of the user that we want to use to send the event")
def resend_event_ofpra(input_file, email):
    from sief.view.demande_asile_api import dump_da_full
    from sief.events import EVENTS as e

    if not os.path.isfile(input_file):
        print("fichier non existant vérifier le chemin du fichier")
        return
    utilisateur = Utilisateur.objects(email=email).first()
    with open(input_file, 'r') as file:
        col_demande_asile = -1
        csv = reader(file, quoting=QUOTE_NONE)
        for entry in csv:
            if col_demande_asile == -1:
                for i, col in enumerate(entry):
                    if col == 'id_demande_asile':
                        col_demande_asile = i
                if col_demande_asile == -1:
                    print(
                        "fichier aucune colone 'id_demande_asile' trouvée dans le fichier, veuillez vérifier le fichier d'entrée")
                continue
            demande_asile_id = entry[col_demande_asile]
            da = DemandeAsile.objects(id=demande_asile_id).first()
            if da:
                dump = dump_da_full(da)
                e.demande_asile.en_attente_ofpra.send(origin=utilisateur, **dump)
                print("Envoie de l'événement en attente ofpra pour la demande d'asile %s" %
                      demande_asile_id)
            else:
                print("Demande d'asile %s non trouvé en base" % (demande_asile_id))


@demande_asile_manager.option('-f', '--input_file',
                              help="file containing the list of \"demande d'asile\" id to edit")
def remove_duplicate_decision_definitive(input_file):
    treat = set()

    if not os.path.isfile(input_file):
        print("fichier non existant vérifier le chemin du fichier")
        return
    with open(input_file, 'r') as file:
        header = {}
        csv = reader(file, quoting=QUOTE_NONE)
        for entry in csv:
            entry = [x or None for x in entry]
            if not header:
                for idx, col in enumerate(entry):
                    header[col] = idx
                continue
            demande_asile_id = entry[0]
            demande_asile = DemandeAsile.objects(id=demande_asile_id).first()
            s = set()
            decisions_definitives = []
            for index, decision in enumerate(demande_asile.decisions_definitives):
                if decision.date_premier_accord not in s:
                    s.add(decision.date_premier_accord)
                    decisions_definitives.append(decision)
                else:
                    for already_treat in decisions_definitives:
                        if decision.date_premier_accord == already_treat.date_premier_accord\
                                and decision != already_treat:
                            decisions_definitives.append(decision)
                if demande_asile_id not in treat:
                    treat.add(demande_asile_id)
            demande_asile.decisions_definitives = decisions_definitives
            demande_asile.save()

    output = input_file + '.output'
    with open(output, 'w') as output:
        output.write('demande_asile')
        output.write("\n")
        for i in treat:
            output.write(i)
            output.write("\n")


@demande_asile_manager.option('-f', '--input_file',
                              help="file containing the different demande d'asile to edit")
def annulation_deuxieme_renouvellement(input_file):
    class DejaAnnuleError(Exception):
        pass

    if not os.path.isfile(input_file):
        print("fichier non existant vérifier le chemin du fichier")
        return
    with open(input_file, 'r') as file,\
            open(input_file + ".err", 'w') as error_file,\
            open(input_file + ".output", 'w') as output_file:
        header = False
        csv = reader(file, quoting=QUOTE_NONE)
        output_file.write("demande_asile\n")

        for entry in csv:
            if not header:  # Just skip header
                header = True
                continue
            try:
                demande_asile_id = int(entry[0])
            except IndexError:  # empty line ?
                continue
            except ValueError:
                error_file.write("Error while parsing demande_asile id : %s\n" % entry[0])
                continue
            demande_asile = DemandeAsile.objects(id=demande_asile_id).first()
            if not demande_asile:
                continue
            droits = Droit.objects(demande_origine=demande_asile,
                                   sous_type_document='EN_RENOUVELLEMENT',
                                   ).order_by("-doc_created")
            if not droits:
                continue
            droit_not_cancel = None
            counter = 0
            for droit in droits:
                counter += 1
                try:
                    for support in droit.supports:
                        if support.motif_annulation:
                            raise DejaAnnuleError
                except DejaAnnuleError:
                    continue
                droit_not_cancel = droit
                break

            if droit_not_cancel:
                if counter == len(droits):
                    demande_asile.renouvellement_attestation -= 1
                for support in droit_not_cancel.supports:
                    support.motif_annulation = 'DEGRADATION'
                try:
                    droit_not_cancel.save()
                    demande_asile.save()
                except ValidationError:
                    error_file.write("Unable to save demande_asile : %s\n" % demande_asile_id)
                    continue
            output_file.write("%s : done\n" % demande_asile_id)


def _write_demande_asiles(demande_asiles, filename):
    with open(filename, 'w') as csvfile:
        writer_csv = writer(csvfile, delimiter=',')
        writer_csv.writerow(['Numéro étranger',
                             'Nom',
                             'Prénoms',
                             'Sexe',
                             'Date de naissance',
                             'Adresse',
                             'GU enregistrement',
                             "Date d'enregistrement"])
        for demande in demande_asiles:
            writer_csv.writerow([demande.usager.identifiant_agdref,
                                 demande.usager.nom,
                                 demande.usager.prenoms,
                                 demande.usager.sexe,
                                 "{:%d/%m/%Y}".format(demande.usager.date_naissance),
                                 str(demande.usager.localisations[-1].adresse),
                                 demande.structure_guichet_unique.libelle,
                                 "{:%d/%m/%Y}".format(demande.date_enregistrement)])


@demande_asile_manager.option('-f', '--file-name', dest='filename', default='export_reexamen_demande_asile.csv')
def export_demande_reexamen(filename):
    demande_asiles = DemandeAsile.objects(
        __raw__={'$and': [{'procedure.motif_qualification': "REEX"}, {'procedure.type': 'ACCELEREE'}]})
    _write_demande_asiles(demande_asiles, filename)


@demande_asile_manager.option('-f', '--file-name', dest='filename', default='export_refus_prise_empreinte.csv')
def export_refus_prise_empreinte(filename):
    demande_asiles = DemandeAsile.objects(
        __raw__={'$and': [{'procedure.motif_qualification': "EMPR"}, {'procedure.type': 'ACCELEREE'}]})
    _write_demande_asiles(demande_asiles, filename)

if __name__ == "__main__":
    demande_asile_manager.run()
