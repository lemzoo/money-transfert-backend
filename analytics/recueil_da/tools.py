from sief.model import GU
from analytics.tools import logger


def load_spa(document):
    if 'structure_accueil' not in document:
        msg = "[RecueilDA Load spa] Structure d'accueil: not define in recueil " + \
            str(document['_id'])
        logger.log(msg, 'WARNING')
        return None
    return document['structure_accueil']['$oid']


def load_gu(document):
    if 'structure_guichet_unique' in document:
        return document['structure_guichet_unique']['$oid']
    return None


def load_sites(document):
    gu_id = load_gu(document)
    if gu_id:
        gu = GU.objects(id=gu_id).first()
        if gu:
            if not gu.autorite_rattachement:
                msg = "[RecueilDA Load sites] Guichet Unique: prefecture not define for " + \
                    str(gu.id)
                logger.log(msg, 'WARNING')
                return None, None
            prefecture = str(gu.autorite_rattachement.id)
            return gu_id, prefecture
        else:
            msg = "[RecueilDA Load sites] GU: " + gu_id + " not found in database"
            logger.log(msg, 'ERROR')
    return None, None
