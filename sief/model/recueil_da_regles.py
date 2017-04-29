from collections import defaultdict
from datetime import datetime

from sief.model.usager import is_adult


RECUEIL_DA_TO_USAGER_FIELDS = (
    'identifiant_agdref', 'identifiant_portail_agdref', 'date_enregistrement_agdref',
    'nom', 'nom_usage', 'prenoms', 'photo', 'origine_nom', 'origine_nom_usage',
    'sexe', 'documents', 'date_naissance', 'situation_familiale',
    'date_naissance_approximative', 'pays_naissance',
    'ville_naissance', 'nationalites', 'nom_pere',
    'prenom_pere', 'nom_mere', 'prenom_mere',
    'adresse', 'telephone', 'email', 'langues',
    'langues_audition_OFPRA',
    'representant_legal_nom', 'representant_legal_prenom',
    'representant_legal_personne_morale',
    'representant_legal_personne_morale_designation',
    'vulnerabilite'
)


def _build_dict_from_path(dict_reference, path, value):
    # split my path.
    # usager_1.adresse.code_postal => usager_1 > adresse > code_postal
    all_keys = path.split(".")

    # Add to dict_reference all required keys if not exist
    # And at the end, add our value under the correct key.
    final_key = all_keys[-1]
    current_dict = dict_reference
    for local_key in all_keys[:-1]:
        if local_key not in current_dict.keys():
            current_dict[local_key] = {}
        current_dict = current_dict[local_key]
    current_dict[final_key] = value

    return dict_reference


def _merge_errors_dicts(*args):
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        # First argument is a list of errors dicts
        args = args[0]
    final_errors = defaultdict(list)
    for errors in [a for a in args if a]:
        for key, value in errors.items():
            if isinstance(value, (list, tuple)):
                final_errors[key] += value
            else:
                final_errors = _build_dict_from_path(final_errors, key, value)

    return final_errors


class RuleManager:

    def __init__(self, rules):
        self.rules = rules

    def apply(self, document, context=None):
        return _merge_errors_dicts([rule(document) for rule in self.rules])


def _check_required(document, required, route_prefix=None, forbidden=False, msg=None):
    errors = {}

    def is_missing(value):
        return (value is None or
                (isinstance(value, str) and value == '') or
                (isinstance(value, (list, tuple, dict)) and not value))

    msg = msg or ('Champ requis' if not forbidden else 'Champ non autorisé')
    for elem in required:
        value = getattr(document, elem, None)
        # Element must not be an empty list/tuple or None
        missing = is_missing(value)
        if (not forbidden and missing) or (forbidden and not missing):
            route = route_prefix + '.' + elem if route_prefix else elem
            errors[route] = msg
    return errors


def _usagers_map(fn, doc):
    # Apply fn to doc.usager_1, doc.usager_2 and each doc.enfants
    errors_dicts = []
    if doc.usager_1:
        errors_dicts.append(fn(doc.usager_1, route='usager_1'))
    if doc.usager_2:
        errors_dicts.append(fn(doc.usager_2, route='usager_2'))
    for i, usager in enumerate(doc.enfants):
        errors_dicts.append(fn(usager, route='enfants.%s' % i))
    return _merge_errors_dicts(errors_dicts)


def rgl_brouillon_champs_obligatoires(document):
    return _check_required(document, ('structure_accueil', 'agent_accueil'))


def rgl_brouillon_champs_interdits(document):
    return _check_required(document, (
        'date_transmission', 'rendez_vous_gu',  # switch to
        'rendez_vous_gu_anciens', 'structure_guichet_unique',  # DA_REALISE fields
        'motif_annulation', 'date_annulation', 'agent_annulation',  # ANNULE fields
        'agent_enregistrement', 'date_enregistrement'  # EXPLOITE fields
    ), forbidden=True)


def rgl_pa_realise_champs_obligatoires(document):
    return _check_required(document, (
        'structure_accueil', 'agent_accueil',  # BROUILLON fields
        'date_transmission',  # PA_REALISE fields
        # PA_REALISE fields
        'usager_1', 'profil_demande', 'structure_guichet_unique', 'prefecture_rattachee'
    ))


def rgl_pa_realise_champs_interdits(document):
    return _check_required(document, (
        'motif_annulation', 'date_annulation', 'agent_annulation',  # ANNULE fields
        'agent_enregistrement', 'date_enregistrement'  # EXPLOITE fields
    ), forbidden=True)


rgl_demandeurs_identifies_champs_obligatoires = rgl_pa_realise_champs_obligatoires
rgl_demandeurs_identifies_champs_interdits = rgl_pa_realise_champs_interdits


def rgl_exploite_champs_obligatoires(document):
    return _check_required(document, (
        'structure_accueil', 'agent_accueil',  # BROUILLON fields
        'date_transmission',  # PA_REALISE fields
        # PA_REALISE fields
        'usager_1', 'profil_demande', 'structure_guichet_unique', 'prefecture_rattachee',
        'agent_enregistrement', 'date_enregistrement'  # EXPLOITE fields
    ))


def rgl_exploite_champs_interdits(document):
    return _check_required(document, (
        'motif_annulation', 'date_annulation', 'agent_annulation',  # ANNULE fields
    ), forbidden=True)


def rgl_annule_champs_obligatoires(document):
    return _check_required(document, ('motif_annulation', 'date_annulation', 'agent_annulation'))


rgl_purger_champs_obligatoires = rgl_annule_champs_obligatoires


def rgl_pays_traverses(document):
    fields = ('pays_traverses',)
    now = datetime.utcnow()

    def check_pays_traverses(usager, route):
        if not usager.demandeur:
            return _check_required(usager, fields, route_prefix=route, forbidden=True)
        elif usager.pays_traverses:
            errors = {}
            msg = 'La date ne peut pas être postérieure à la date courante.'
            for i, pt in enumerate(usager.pays_traverses):
                if pt.date_entree and pt.date_entree > now:
                    errors['%s.pays_traverses.%s.date_entree' % (route, i)] = msg
                if pt.date_sortie and pt.date_sortie > now:
                    errors['%s.pays_traverses.%s.date_sortie' % (route, i)] = msg
                if pt.date_sortie and pt.date_entree and pt.date_sortie < pt.date_entree:
                    errors['%s.pays_traverses.%s.date_entree' % (route, i)] = \
                        "La date d'arrivée en France doit être antérieure à celle de sortie"
            return errors

    return _usagers_map(check_pays_traverses, document)


def rgl_date_depart_et_entree(document):
    fields = ('date_depart', 'date_entree_en_france')
    now = datetime.utcnow()

    def check_date_depart_et_entree(usager, route):
        if not usager.demandeur:
            return _check_required(usager, fields, route_prefix=route, forbidden=True)
        errors = _check_required(usager, fields, route_prefix=route)
        if errors:
            return errors
        if usager.date_entree_en_france > now:
            return {'%s.date_entree_en_france' % route:
                    'La date ne peut pas être postérieure à la date courante.'}
        if usager.date_depart > usager.date_entree_en_france:
            return {'%s.date_depart' % route:
                    "La date de départ doit être antérieure"
                    " à celle d'arrivée en France"}

    return _usagers_map(check_date_depart_et_entree, document)


def rgl_champs_obligatoires_usagers_base(document):
    def check_usager(usager, route):
        if usager.usager_existant:
            fields = ['demandeur']
        else:
            fields = ['nom', 'prenoms', 'sexe', 'date_naissance', 'ville_naissance',
                      'pays_naissance', 'nationalites', 'adresse', 'demandeur']
            if route != 'usager_2':
                # usager_2 shares usager_1's situation_familiale field
                fields.append('situation_familiale')
        return _check_required(usager, fields, route_prefix=route)

    return _usagers_map(check_usager, document)


def rgl_champs_interdits_usagers_non_present(document):
    def check_usager(usager, route):
        if not usager.demandeur and not usager.usager_existant:
            msg = "Seuls les usagers demandeurs peuvent avoir une photo"
            return _check_required(usager, ('photo', 'photo_premier_accueil'),
                                   route_prefix=route, forbidden=True, msg=msg)

    return _usagers_map(check_usager, document)


def rgl_present_au_moment_de_la_demande(document):
    def check_present_au_moment_de_la_demande(usager, route):
        if usager.demandeur and not usager.present_au_moment_de_la_demande:
            return {route + '.present_au_moment_de_la_demande':
                    "Un usager demandeur doit être présent"}

    return _usagers_map(check_present_au_moment_de_la_demande, document)


def rgl_pa_realise_champs_obligatoires_usagers_demandeur(document):
    def check_usager(usager, route):
        if usager.demandeur:
            usager = usager if not usager.usager_existant else usager.usager_existant
            fields = ['langues', 'langues_audition_OFPRA']
            return _check_required(usager, fields,
                                   route_prefix=route,
                                   msg='Champ requis pour un usager demandeur')

    return _usagers_map(check_usager, document)


def rgl_pa_realise_champs_photo_demandeur(document):
    def check_photo(usager, route):
        if usager.demandeur and not usager.usager_existant:
            if not usager.photo_premier_accueil and not usager.photo:
                return {route + '.photo_premier_accueil': "Un demandeur doit avoir une photo renseignée"}

    return _usagers_map(check_photo, document)


def rgl_demandeurs_identifies_champs_obligatoires_usagers_demandeur(document):
    def check_usager(usager, route):
        if usager.demandeur:
            usager = usager if not usager.usager_existant else usager.usager_existant
            fields = ['photo', 'identifiant_agdref',
                      'identifiant_portail_agdref',
                      'langues', 'langues_audition_OFPRA', 'origine_nom']
            if usager.nom_usage:
                fields.append('origine_nom_usage')
            return _check_required(usager, fields,
                                   route_prefix=route,
                                   msg='Champ requis pour un usager demandeur')

    return _usagers_map(check_usager, document)


def rgl_demandeurs_identifies_numero_eurodac_demandeur(document):
    def check_numero_eurodac(usager, route):
        if usager.demandeur:
            if not usager.identifiant_eurodac:
                return _check_required(usager, ['identifiant_eurodac'],
                                   route_prefix=route,
                                   msg='Champ requis pour un usager demandeur')
    return _usagers_map(check_numero_eurodac, document)


def rgl_no_modif_usager_existant(document):
    def check_modif(usager, route):
        if usager.usager_existant:
            return _check_required(usager, RECUEIL_DA_TO_USAGER_FIELDS,
                                   route_prefix=route, forbidden=True,
                                   msg="Si l'usager a été défini comme existant, il "
                                       "ne peut pas être modifié via le recueil_da")

    return _usagers_map(check_modif, document)


def rgl_mineur_isole_representant_legal(document):
    representant_legal_fields = (
        'representant_legal_nom',
        'representant_legal_prenom',
        'representant_legal_personne_morale',
        'representant_legal_personne_morale_designation'
    )
    fields_mor = ('representant_legal_personne_morale_designation',)
    fields_phy = ('representant_legal_nom', 'representant_legal_prenom')

    def check_representant_legal(usager, route):
        if (is_adult(usager) is False and
                getattr(usager, 'demandeur', None)):
            if usager.representant_legal_personne_morale:
                # nom/prenom are allowed for a non-physical person
                return _check_required(usager, fields_mor, route_prefix=route)
            else:
                return _merge_errors_dicts(
                    _check_required(usager, fields_phy, route_prefix=route),
                    _check_required(usager, fields_mor, route_prefix=route, forbidden=True)
                )
        else:
            # Adults & non seekers are not allowed to have a representant_legal
            return _check_required(usager, representant_legal_fields,
                                   route_prefix=route, forbidden=True)

    return _usagers_map(check_representant_legal, document)


def rgl_situation_familiale(document):
    if not document.usager_1:
        return
    usager = document.usager_1 if not document.usager_1.usager_existant else document.usager_1.usager_existant
    if usager.situation_familiale in ("MARIE", "CONCUBIN", "PACSE"):
        if not document.usager_2:
            return {'usager_2': ("Un usager secondaire est requis en cas"
                                 " de situation familiale MARIE, CONCUBIN ou PACSE")}
    elif not document.usager_1.usager_existant and document.usager_2:
        return {'usager_2': ("La situation familiale de l'usager"
                             " principal doit être MARIE, CONCUBIN ou PACSE pour avoir"
                             " un usager secondaire.")}


def rgl_exploite_champs_obligatoires_usagers_demandeur(document):
    ecv_fields = ('photo', 'identifiant_agdref', 'identifiant_portail_agdref',
                  'langues', 'langues_audition_OFPRA')
    proc_fields = ('type_procedure', 'motif_qualification_procedure',
                   'conditions_exceptionnelles_accueil', 'condition_entree_france',
                   'visa', 'indicateur_visa_long_sejour', 'decision_sur_attestation',
                   'date_decision_sur_attestation')
    cond_except_field = ('motif_conditions_exceptionnelles_accueil',)

    def check_usager(usager, route):
        if not usager.demandeur:
            return

        check_proc_fields = proc_fields
        if usager.conditions_exceptionnelles_accueil:
            check_proc_fields += cond_except_field

        if usager.usager_existant:
            return _merge_errors_dicts(
                _check_required(usager.usager_existant, ecv_fields,
                                route_prefix=route + '.usager_existant'),
                _check_required(usager, check_proc_fields, route_prefix=route),
            )
        else:
            return _check_required(usager, ecv_fields + check_proc_fields, route_prefix=route)

    return _usagers_map(check_usager, document)


def rgl_au_moins_un_demandeur_est_requis(document):
    if document.usager_1 and document.usager_1.demandeur:
        return
    if document.usager_2 and document.usager_2.demandeur:
        return
    for usager in document.enfants:
        if usager.demandeur:
            return
    return {"usager_1.demandeur": "Au moins un usager doit être demandeur"}


def rgl_aucune_demande_asile(document):
    from sief.model import DemandeAsile

    def _check_demande_asile_en_cours(usager, route):
        if usager.demandeur and usager.usager_existant:
            demande_asiles = DemandeAsile.objects(usager=usager.usager_existant)
            for demande_asile in demande_asiles:
                if len(demande_asile.decisions_definitives):
                    continue
                if demande_asile.statut in ["FIN_PROCEDURE", "FIN_PROCEDURE_DUBLIN", "DECISION_DEFINITIVE"]:
                    continue
                return {"%s.demandeur" % route: "Possède déjà une demande d'asile"}
    return _usagers_map(_check_demande_asile_en_cours, document)


def rgl_reexamen_numero_reexamen_requis(document):

    def _check_type_recueil(usager, route):
        if route in document and not usager:
            usager = document[route]
        if not usager:
            return
        if usager.demandeur:
            if usager.type_demande == 'REEXAMEN' and not usager.numero_reexamen:
                return {"%s.numero_reexamen" % route: "le numéro de réexamen doit être supérieur ou égal à 1"}

    return _usagers_map(_check_type_recueil, document)


def rgl_identite_approchante_select(document):

    def _check_identite_approchante(usager, route):
        if usager and not usager.identite_approchante_select:
            return {"%s.identite_approchante_select" % route: "L'identité approchante n'a pas été sélectionnée."}

    return _usagers_map(_check_identite_approchante, document)
