from flask import current_app
from pymongo.collection import ReturnDocument
from pymongo.errors import OperationFailure, CollectionInvalid


def generate_eurodac_ids(length_identifiant=10, generate_number=1):
    """
    Return a unique identifier for eurodac.

    This function will generate a unique identifier, based on the environment variable
    EURODAC_PREFIX and an inc field
    """
    # Rely directly on pymongo to avoid Mongoengine's overhead in the SequenceField
    db = current_app.db.connection.get_default_database()
    collection_name = current_app.config.get('EURODAC_PREFIX', 'XXX')
    length_identifiant = length_identifiant - len(collection_name)
    document = db[collection_name].find_one_and_update({'_id': 0}, {'$inc': {'suffix': 1 * generate_number}},
                                                       upsert=True,
                                                       return_document=ReturnDocument.AFTER)
    ids = []
    if generate_number < 0:
        return ids
    for i in range(generate_number, 0, -1):
        id_suffix = str(document['suffix'] - i)
        number_of_zero = length_identifiant - len(id_suffix)
        assert number_of_zero > 0
        ids.append(collection_name + ('0' * number_of_zero) + id_suffix)
    return ids
