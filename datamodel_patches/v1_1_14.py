"""
Patch 1.1.13 => 1.1.14
Intégration des champs recueil_d_a et sa première valeur : PREMIERE_DEMANDE_ASILE
Intégration des champs dans demande_asile et sa première valeur : PREMIERE_DEMANDE_ASILE
Ajout d'un champs identifiant_eurodac dans le model "sief/model/usager"
"""

from mongopatcher import Patch

patch_v1114 = Patch('1.1.13', '1.1.14', patchnote=__doc__)


@patch_v1114.fix
def ajout_champ_reexamen(db):
    def update_recueil(recueil):
        delta = {'$set': {}}

        def upate_usager_recueil(usager, usager_name):
            if usager.get('demandeur'):
                delta['$set'][usager_name + '.type_demande'] = 'PREMIERE_DEMANDE_ASILE'
            if recueil['statut'] in ['DEMANDEURS_IDENTIFIES', 'EXPLOITE']:
                delta['$set'][usager_name + '.identite_approchante_select'] = True

        usager_1 = recueil.get('usager_1')
        usager_2 = recueil.get('usager_2')
        enfants = recueil.get('enfants')
        if usager_1:
            upate_usager_recueil(usager_1, 'usager_1')
        if usager_2:
            upate_usager_recueil(usager_2, 'usager_2')

        if enfants:
            for index, enfant in enumerate(enfants):
                upate_usager_recueil(enfant, 'enfants.' + str(index))
        if delta['$set'] == {}:
            return None
        return delta

    for recueil in db['recueil_d_a'].find():
        delta = update_recueil(recueil)
        if delta:
            db['recueil_d_a'].update_one({'_id': recueil['_id']}, delta)
    db['demande_asile'].update_many({}, {'$set': {'type_demande': 'PREMIERE_DEMANDE_ASILE'}})


@patch_v1114.fix
def add_idenifiants_eurodac_to_usager(db):
    usager_collection = db['usager']
    for usager in usager_collection.find():
        numero_etranger = usager.get('identifiant_agdref')
        if numero_etranger:
            usager_collection.update_one(
                {'_id': usager['_id']}, {'$set': {'identifiants_eurodac': [numero_etranger]}})


@patch_v1114.fix
def add_identifiants_eurodac_to_usager_recueil(db):
    def update_usager(usager, filter, path):
        if not usager:
            return
        numero_etranger = usager.get('identifiant_agdref')
        demandeur = usager.get('demandeur')
        if demandeur and numero_etranger:
            recueil_da.update(filter, {'$set': {path: numero_etranger}})

    recueil_da = db['recueil_d_a']
    for recueil in recueil_da.find():
        update_usager(
            recueil.get('usager_1'), {'_id': recueil['_id']}, 'usager_1.identifiant_eurodac')
        update_usager(
            recueil.get('usager_2'), {'_id': recueil['_id']}, 'usager_2.identifiant_eurodac')
        enfants = recueil.get('enfants', [])
        for enfant in enfants:
            numero_etranger = enfant.get('identifiant_agdref')
            update_usager(enfant, {'_id': recueil[
                          '_id'], 'enfants.identifiant_agdref': numero_etranger}, 'enfants.$.identifiant_eurodac')
            recueil_da.update_one({'_id': recueil['_id'], 'enfants.identifiant_agdref': numero_etranger}, {
                                  '$unset': {'enfants.$.idenfiant_eurodac': ''}})


@patch_v1114.fix
def add_identifiants_eurodac_to_demande_asile(db):
    demande_asile_collection = db['demande_asile']
    usager_collection = db['usager']
    for demande_asile in demande_asile_collection.find():
        usager = usager_collection.find_one({'_id': demande_asile['usager']})
        demande_asile_collection.update_one(
            {'_id': demande_asile['_id']}, {'$set': {'usager_identifiant_eurodac': usager['identifiant_agdref']}})
