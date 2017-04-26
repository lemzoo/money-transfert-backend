import re

from flask import url_for

from core import CoreResource
from core.tools import abort
from services.ants_pftd import (stamp_service, generate_reservation_number,
                                StampServiceError)
from sief.permissions import POLICIES as p
from sief.model.droit import NUMERO_TIMBRE_FORMAT, Droit


class TimbreAPI(CoreResource):

    @p.timbre.voir.require(http_exception=403)
    def get(self, numero_timbre):

        if not is_timbre_format_correct(numero_timbre):
            abort(400, errors=[{'code_erreur': 'bad-format'}])

        droits = Droit.objects(taxe__timbre__numero=numero_timbre)
        reservation_number = get_reservation_number(droits)

        try:
            data = stamp_service.get_details(numero_timbre, reservation_number)
        except StampServiceError as e:
            abort(500, errors=[{'code_erreur': e.code}])

        links = {'self': url_for('TimbreAPI', numero_timbre=numero_timbre)}
        return {'_links': links, 'data': data}, 200


def is_timbre_format_correct(numero_timbre):
    return re.match(NUMERO_TIMBRE_FORMAT, numero_timbre)


def get_reservation_number(droits):
    has_droits = len(droits) > 0
    return droits[0].taxe.timbre.numero_reservation if has_droits else generate_reservation_number()
