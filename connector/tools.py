from functools import wraps
from traceback import format_exc

from connector.exceptions import (
    ProcessMessageError, ProcessMessageBadResponseError,
    ProcessMessageNoResponseError, ProcessMessageSkippedError)
import requests


def to_list(obj):
    if not isinstance(obj, list):
        lst = []
        lst.append(obj)
        obj = lst
    return obj


def check_bool(value):
    return str(value).lower() in ('1', 'o', 'true')


def strip_namespaces(raw):
    if not isinstance(raw, dict):
        return raw
    out = {}
    for key, value in raw.items():
        splitted = key.rsplit(':', 1)
        if len(splitted) == 2:
            namespace, stripped_key = splitted
            if namespace.startswith('@'):
                continue
        else:
            stripped_key = key
        stripped_key = splitted[1] if len(splitted) == 2 else key
        if isinstance(value, dict):
            out[stripped_key] = strip_namespaces(value)
        elif isinstance(value, list):
            out[stripped_key] = [strip_namespaces(sub_value) for sub_value in value]
        else:
            out[stripped_key] = value
    return out


def request_with_broker_retry(request):

    @wraps(request)
    def wrapper(*args, **kwargs):
        try:
            ret = request(*args, **kwargs)
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise ProcessMessageNoResponseError(
                'Indisponibilité du serveur\nRequête : %s %s\n\n%s' % (args, kwargs, exc))
        if ret.status_code in [502, 503, 504]:
            raise ProcessMessageNoResponseError(
                'Indisponibilité du serveur\nRequête : %s %s\n\nRéponse %s\n%s' %
                (args, kwargs, ret.status_code, ret.text))
        return ret

    return wrapper


def request_logger(func):
    """Decorator to keep trace of a request event during exception"""
    class Logger:

        def __init__(self):
            self._request_body = 'Pas de Requête envoyée'
            self._response_body = 'Pas de réponse reçue'
            self._response_status_code = ''

        def set_request(self, body):
            self._request_body = body

        def set_response(self, response):
            self._response_body = response.text
            self._response_status_code = response.status_code

    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = Logger()
        try:
            ret = func(*args, logger=logger, **kwargs)
            if not ret:
                return ('Le serveur distant a répondu avec succès\n\n'
                        'Requête %s:\n%s\n\nRéponse:\n%s' % (
                            logger._request_body, logger._response_status_code,
                            logger._response_body))
        except ProcessMessageError:
            raise
        except ProcessMessageSkippedError:
            raise
        except Exception:
            exc_dump = format_exc()
            raise ProcessMessageBadResponseError(
                '%s\nErreur dans la requête:\n%s\n\nRéponse %s:\n%s' % (
                    exc_dump, logger._request_body,
                    logger._response_status_code, logger._response_body))
        return ret

    return wrapper


def retrieve_last_demande_for_given_usager(recueils_da, identifiant_agdref, id):
    recueils_da = sorted(recueils_da, key=lambda k: k['_created'])
    usager_recueil = None
    for recueil in reversed(recueils_da):
        if 'usager_1' in recueil:
            if 'usager_existant' in recueil['usager_1'] and recueil['usager_1']['usager_existant']:
                if (recueil['usager_1']['demandeur'] and
                        recueil['usager_1']['usager_existant']['id'] == int(id)):
                    usager_recueil = recueil['usager_1']

            elif (recueil['usager_1']['demandeur'] and
                    recueil['usager_1']['identifiant_agdref'] == identifiant_agdref):
                usager_recueil = recueil['usager_1']

        if 'usager_2' in recueil and not usager_recueil:
            if 'usager_existant' in recueil['usager_2'] and recueil['usager_2']['usager_existant']:
                if (recueil['usager_2']['demandeur'] and
                        recueil['usager_2']['usager_existant']['id'] == int(id)):
                    usager_recueil = recueil['usager_2']

            elif (recueil['usager_2']['demandeur'] and
                    recueil['usager_2']['identifiant_agdref'] == identifiant_agdref):
                usager_recueil = recueil['usager_2']

        if 'enfants' in recueil and not usager_recueil:
            for enfant in recueil['enfants']:
                if 'usager_existant' in enfant and enfant['usager_existant']:
                    if (enfant['demandeur'] and
                            enfant['usager_existant']['id'] == int(id)):
                        usager_recueil = recueil['usager_2']

                elif (enfant['demandeur'] and
                        enfant['identifiant_agdref'] == identifiant_agdref):
                    usager_recueil = enfant
        if usager_recueil:
            break
    return usager_recueil
