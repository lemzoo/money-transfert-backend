#!/usr/bin/python

import csv
import re

from bson.objectid import ObjectId

from flask import current_app
from flask.ext.script import Manager

from sief.model import GU, DemandeAsile, Usager

agdref_manager = Manager(usage="Perform operations on AGDREF message queue")


def _find_loader_gu_from_usager(json_context, loader_gu_id):
    usager_id = json_context.get('usager', {}).get('id')
    if not usager_id:
        return False
    for da in DemandeAsile.objects(usager=Usager.objects(id=usager_id).first()):
        recueil = da.recueil_da_origine
        if recueil:
            gu = recueil.structure_guichet_unique
            if gu and str(gu.id) == loader_gu_id:
                return True
    return False


def _force_find_loader_gu(json_context, loader_gu_id):
    """Find any id recursively in any context and checks whether it matches the
    loader_gu_id given as parameter.
    This is done to handle any kind of json context contained in the messages, and is
    better than trying to find the site id at a specific location (because it varies
    accross documents and will not pass the test of time).
    While mongo ObjectIds are not guaranteed to be unique, it is (very) highly unlikely
    that we will encounter a collision.

    :param json_context: any dict containing any number of sub dicts or lists
    :param loader_gu_id: id of the loader-gu Site.
    :return: True if a structure_guichet_unique id has been found and matches loader_gu_id,
             False otherwise.
    """

    for key, value in json_context.items():
        if isinstance(value, dict):
            if _comes_from_loader_gu(value, loader_gu_id):
                return True
        elif isinstance(value, list):
            for elem in value:
                if isinstance(elem, dict) and _comes_from_loader_gu(elem, loader_gu_id):
                    return True
        elif isinstance(value, str) and re.match('^[a-f0-9]{24}$', value) and value == loader_gu_id:
            return True
    return False


def _comes_from_loader_gu(json_context, loader_gu_id):
    return (_find_loader_gu_from_usager(json_context, loader_gu_id) or
      _force_find_loader_gu(json_context, loader_gu_id))


@agdref_manager.option('-l', '--libelle', help="GU loader's libelle", default='loader-GU')
@agdref_manager.option('-o', '--output', help='File to dump message ids that were marked as DELETED')
def delete_gu_loader_messages(libelle='loader-GU', output=None):
    """Change the status of messages in queue 'agdref' coming from the
    GU loader from 'CANCELLED' to 'DELETED'
    """

    msg_cls = current_app.extensions['broker'].model.Message

    # Get "loader-gu" so we can compare its id to the one in the message's context
    loader_gu = GU.objects(libelle=libelle).first()
    if not loader_gu:
        print('GU "{}" not found'.format(libelle))
        return 1

    deleted_msg = []
    for msg in msg_cls.objects(status='CANCELLED', queue='agdref'):
        # Deserializing the context to extract the any structure_guichet_unique equal to the
        # GU loader's
        json_context = msg.context
        if _comes_from_loader_gu(json_context, str(loader_gu.id)):
            deleted_msg.append(msg)
    msg_cls.objects(id__in=[msg.id for msg in deleted_msg]).update(status='DELETED')
    print("Marked {} messages as DELETED".format(len(deleted_msg)))

    if not output:
        return

    with open(output, 'w') as fd:
        writer = csv.writer(fd)
        writer.writerow(('id', 'created', 'handler', 'origin'))
        for msg in deleted_msg:
            writer.writerow((str(msg.id), msg.created.isoformat(), msg.handler, str(msg.origin)))


@agdref_manager.option('message_ids', help='Messages ids', type=ObjectId, nargs='+')
def mark_messages_as_deleted(message_ids):
    """Will mark the messages with ids given as parameter as DELETED if they are
    in the agdref queue and their status is 'CANCELLED'.
    """

    msg_cls = current_app.extensions['broker'].model.Message
    msg_cls.objects(id__in=message_ids, status='CANCELLED', queue='agdref').update(status='DELETED')
