from flask import current_app
from flask.ext.script import Manager, prompt_bool
from mongoengine.errors import DoesNotExist
from csv import DictWriter, QUOTE_NONE
import json

from sief.managers.dna_stock.default_resources import DefaultRessources
from sief.managers.dna_stock import csv_handler, processor

from sief.model import (Site, Usager, DemandeAsile, Droit, RecueilDA)
from connector.dna.common import proc_trans


dna_stock_manager = Manager(usage="Perform import operations on DN@ stock")


@dna_stock_manager.option('-d', '--dry', action='store_true',
                          help="Don't actualy create the elements")
def bootstrap(dry):
    """Create default user/resources needed for the import"""
    default_resources = DefaultRessources(verbose=True)
    if not default_resources.has_missing:
        print('-> No missing elements')
        return
    if not dry:
        default_resources.create_missing()


@dna_stock_manager.option('file', help="CSV file to import")
@dna_stock_manager.option('-d', '--delimiter', default=',',
                          help="delimiter for CSV fields (default: ',')")
@dna_stock_manager.option('-c', '--clean-messages', action='store_true',
                          help="Drop exploite/pa_realise/introduit_ofpra broker messages")
@dna_stock_manager.option('-f', '--force', action='store_true', default=False,
                          help="For synchronisation even if usager is already synchronized")
def load_dna(file, delimiter, clean_messages, force):
    """
    Import dn@ to sief sync csv
    """
    default_resources = DefaultRessources(verbose=True)
    if default_resources.has_missing:
        print('Required default elements are missing, please run the bootstrap command')
        return 1
    entries = csv_handler.parse_input(file, delimiter=delimiter)
    processor.process(entries, default_resources, force)
    csv_handler.write_result(file + '.output', entries, delimiter=delimiter)
    if clean_messages:
        _clean_broker_messages(entries)


@dna_stock_manager.option('file', help="CSV file to import")
@dna_stock_manager.option('-d', '--delimiter', default=',',
                          help="delimiter for CSV fields (default: ',')")
def clean_broker_messages(file, delimiter):
    """
    Drop exploite/pa_realise/introduit_ofpra broker messages linked to the
    file's users
    """
    entries = csv_handler.parse_input(file, delimiter=delimiter, full_headers=True)
    _clean_broker_messages(entries)


def _clean_broker_messages(entries):
    recueil_ids = set([e.fields['id_recueil_demande']
                       for e in entries if e.fields.get('id_recueil_demande')])
    to_cancel_msgs = []
    msg_cls = current_app.extensions['broker'].model.Message
    for msg in msg_cls.objects(
        status__in=("READY", "FAILURE", "SKIPPED", "CANCELLED"),
        handler__in=("dna-recueil_da.exploite", "dna-recueil_da.pa_realise",
                     "dna-demande_asile.introduit_ofpra")
    ):
        context = msg.context
        if context is None or context.get('recueil_da') is None:
            to_cancel_msgs.append(msg.pk)
        elif msg.handler == 'dna-demande_asile.introduit_ofpra':
            origin_id = context.get('demande_asile', {}).get('recueil_da_origine', {}).get('id', '')
            if str(origin_id) in recueil_ids:
                to_cancel_msgs.append(msg.pk)
        else:
            if context.get('recueil_da', {}).get('id') in recueil_ids:
                to_cancel_msgs.append(msg.pk)
    msg_cls.objects(id__in=to_cancel_msgs).update(status='DELETED')
    print('Canceled %s messages' % len(to_cancel_msgs))


@dna_stock_manager.option('-d', '--delimiter', help="delimiter for CSV fields",
                          default=',')
@dna_stock_manager.option('-o', '--output', default='./extract_decision_def.csv',
                          help="File to extract content to")
def decisions_definitives(delimiter, output):
    with open(output, 'w') as file:
        csv = DictWriter(file,
                         delimiter=delimiter,
                         quoting=QUOTE_NONE,
                         fieldnames=('Identifiant_usager', 'Identifant_dna', 'Identifiant_inerec',
                                     'Date_introduction', 'Type_procédure', 'Date_requalification',
                                     'Date_de_notification', 'Entité', 'Nature', 'Date_decision',
                                     'Date_notification')
                         )
        csv.writeheader()
        das = DemandeAsile.objects()
        for da in das:
            df = None
            if da.decisions_definitives:
                df = da.decisions_definitives[-1]
            proc = da.procedure

            if df or proc:
                dico = {
                    'Identifiant_usager': da.usager.id,
                    'Identifant_dna': da.usager.identifiant_dna,
                    'Identifiant_inerec': da.identifiant_inerec
                }
                if da.date_introduction_ofpra:
                    dico.update(
                        {'Date_introduction': da.date_introduction_ofpra.strftime("%Y%m%d")})
                if proc:
                    dico.update({'Type_procédure': proc_trans.translate_to_WSDL(proc.type)})
                    if proc.requalifications:
                        requal_idx = proc.requalifications[-1]
                        dico.update({
                            'Date_requalification': requal_idx.date.strftime("%Y%m%d"),
                            'Date_de_notification': requal_idx.date_notification.strftime("%Y%m%d")
                        })
                if df:
                    dico.update({
                        'Entité': df.entite,
                        'Nature': df.nature,
                        'Date_decision': df.date.strftime("%Y%m%d"),
                        'Date_notification': df.date_notification.strftime("%Y%m%d")})

                csv.writerow(dico)


@dna_stock_manager.option('-d', '--delimiter', help="delimiter for CSV fields",
                          default=',')
@dna_stock_manager.option('-o', '--output', default='./extract_id_ofpra.csv',
                          help="File to extract content to")
@dna_stock_manager.option('-l', '--prefecture_rattachee', help="Prefecture origin to find",
                          default='loader-Prefecture')
def extract_id_ofpra(delimiter, output, prefecture_rattachee):
    with open(output, 'w') as file:
        csv = DictWriter(file,
                         delimiter=delimiter,
                         quoting=QUOTE_NONE,
                         fieldnames=('Identifiant_demande_asile', 'Identifiant_inerec',
                                     'Identifiant_usager', 'Identifant_dna', 'Identifiant_agdref',)
                         )
        csv.writeheader()
        site = Site.objects(libelle=prefecture_rattachee).first()
        das = DemandeAsile.objects(prefecture_rattachee=site)
        for da in das:
            if da.usager:
                dico = {
                    'Identifiant_demande_asile': da.id,
                    'Identifiant_usager': da.usager.id,
                    'Identifant_dna': da.usager.identifiant_dna,
                    'Identifiant_agdref': da.usager.identifiant_agdref,
                    'Identifiant_inerec': da.identifiant_inerec,
                }
                csv.writerow(dico)


def _find_transferred_folders(prefecture_rattachee):
    """
        find all transferred files where the origin was prefecture_rattachee

        :param: string, prefecture_rattachee: the prefecture origin of the folder
        :return: list: lists of usager ids that has been transferred
    """
    site = Site.objects(libelle=prefecture_rattachee).first()
    if not site:
        print("Le site %s n'a pu être trouvé en base de donnée" % prefecture_rattachee)
        return
    usagers = Usager.objects(prefecture_rattachee__ne=site)
    usagers._cursor.batch_size(200)

    for usager in usagers:
        # If our usager isn't linked to our pref, check the first history
        try:
            history = usager.get_collection_history().objects(
                origin=usager.id, action="CREATE").first()
            content = json.loads(history.content)

            if str(site.id) == content.get('prefecture_rattachee', {}).get('$oid', ''):
                yield usager
        except DoesNotExist:
            continue


def _find_usager_loader(prefecture_rattachee):
    site = Site.objects(libelle=prefecture_rattachee).first()
    if not site:
        print("Le site %s n'a pu être trouvé en base de donnée" % prefecture_rattachee)
        return
    usagers = Usager.objects(prefecture_rattachee=site)
    usagers._cursor.batch_size(200)

    for usager in usagers:
        # If our usager isn't linked to our pref, check the first history
        yield usager

    _find_transferred_folders(prefecture_rattachee)


@dna_stock_manager.option('-l', '--prefecture_rattachee', help="Prefecture origin to find",
                          default='loader-Prefecture')
def find_transferred_folders(prefecture_rattachee):
    usagers_id = []
    for usager in _find_transferred_folders(prefecture_rattachee):
        usagers_id.append(usagers_id)
    print("Dossiers transférés : {}".format(usagers_id))


@dna_stock_manager.option('-y', '--yes', help="Don't ask for confirmation", action='store_true')
@dna_stock_manager.option('-o', '--output', default='./extract_id_ofpra.csv',
                          help="output file")
@dna_stock_manager.option('-l', '--prefecture_rattachee', help="Prefecture origin to find",
                          default='loader-Prefecture')
@dna_stock_manager.option('-g', '--gu_rattachee', help="Prefecture origin to find",
                          default='loader-GU')
def delete_all_files(yes, output, prefecture_rattachee, gu_rattachee):

    if not yes and not prompt_bool("êtes vous sur de vouloir supprimer tous les éléments du dna stock? (o/n)", yes_choices=['o'], no_choices=['n']):
        return

    def write_entry(csv_file, usager, demande_asile, recueil_id, droits):
        droits_str = None if not droits else '|'.join(droits_list)
        dico = {
            'Identifiant_usager': usager,
            'Identifiant_demande_asile': demande_asile,
            'Identifant_recueil': recueil_id,
            'Identifiant_droits': droits_str,
        }
        csv_file.writerow(dico)

    with open(output, 'w') as file:
        csv = DictWriter(file,
                         delimiter=',',
                         quoting=QUOTE_NONE,
                         fieldnames=('Identifiant_usager', 'Identifiant_demande_asile',
                                     'Identifant_recueil', 'Identifiant_droits',)
                         )
        csv.writeheader()
        recueil_da_loader = []

        for usager in _find_usager_loader(prefecture_rattachee):
            try:
                for demande_asile in DemandeAsile.objects(usager=usager):
                    droits_list = []
                    droits = Droit.objects(demande_origine=demande_asile)
                    for droit in droits:
                        droits_list.append(droit.id)
                        droit.delete()
                    recueil_da_loader.append(demande_asile.recueil_da_origine.id)
                    demande_asile.delete()
                    write_entry(csv, usager, demande_asile, recueil_da_loader[-1], droits_list)
                usager.delete()

            # Pokemon exception but its on purpose
            except Exception as e:
                print("An error has occured during the treatment of %s: %s" % (usager.id, e))
                continue

        recueil_da_loader = set(recueil_da_loader)
        # recueil has not been delete in the same for
        # because multiple asylum can be create from the same
        # recueil
        for recueil_id in recueil_da_loader:
            try:
                RecueilDA.objects(id=recueil_id).delete()
            except Exception as e:
                print("Unable to delete the recueil: %s" % recueil_id)
                continue
        # try to find recueil that has not been exploit
        # aka status < EXPLOITE
        gu_loader = Site.objects(libelle=gu_rattachee).first()
        if gu_loader:
            recueil_da_loader = RecueilDA.objects(structure_guichet_unique=gu_loader)
            for recueil in recueil_da_loader:
                try:
                    recueil_id = recueil.id
                    RecueilDA.objects(id=recueil_id).delete()
                    write_entry(csv, None, None, recueil_id, None)
                except Exception as e:
                    print("Unable to delete the recueil: %s" % recueil_id)
                    continue
        else:
            print("Le site %s n'a pu être trouvé en base de donnée" % gu_rattachee)

        print("Vous pouvez effectuer un rebuild solr")
