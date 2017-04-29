from flask import Blueprint

from core import CoreApi
from core import CoreResource

from . import usager_vlsts_api


vlsts_blueprint = Blueprint('vlsts', __name__, url_prefix='/vlsts')

api = CoreApi(vlsts_blueprint)

# Usagers
api.add_resource(usager_vlsts_api.UsagerVLSTSAPI, '/moi')
api.add_resource(usager_vlsts_api.UsagerVLSTSVerifierNumeroVisa, '/moi/verifier_numero_visa')
api.add_resource(usager_vlsts_api.UsagerVLSTSDeclarerDateEntreeEnFrance, '/moi/declarer_date_entree_en_france')
api.add_resource(usager_vlsts_api.UsagerVLSTSCoordonnees, '/moi/coordonnees')


class RootVLSTSAPI(CoreResource):

    """Root endpoint for VLS-TS api discovering"""

    def get(self):
        return {
            '_links': {
                'usagers': '/usagers',
            }
        }
api.add_resource(RootVLSTSAPI, '/')
