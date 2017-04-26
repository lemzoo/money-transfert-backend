"""
Role&permissions management
"""
from core.auth import current_user

from sief.permissions import POLICIES


ROLE_TO_CAN_SET_ROLES = {
    None: True,  # User with no role is not limited in role creation
    'ADMINISTRATEUR': True,  # Can create any role
    'ADMINISTRATEUR_NATIONAL': (
        'ADMINISTRATEUR_NATIONAL',
        'SYSTEME_DNA',
        'SYSTEME_INEREC',
        'SYSTEME_AGDREF',
        'RESPONSABLE_NATIONAL',
        'SUPPORT_NATIONAL',
        'SUPERVISEUR_ECHANGES',
        'ADMINISTRATEUR_PA',
        'ADMINISTRATEUR_PREFECTURE',
        'ADMINISTRATEUR_DT_OFII',
        'RESPONSABLE_ZONAL',
        'GESTIONNAIRE_NATIONAL',
        'EXTRACTEUR',
    ),
    'ADMINISTRATEUR_PA': (
        'RESPONSABLE_PA',
        'GESTIONNAIRE_PA',
    ),
    'ADMINISTRATEUR_PREFECTURE': (
        'RESPONSABLE_GU_ASILE_PREFECTURE',
        'GESTIONNAIRE_GU_ASILE_PREFECTURE',
        'GESTIONNAIRE_ASILE_PREFECTURE',
        'GESTIONNAIRE_DE_TITRES',
    ),
    'ADMINISTRATEUR_DT_OFII': (
        'RESPONSABLE_GU_DT_OFII',
        'GESTIONNAIRE_GU_DT_OFII',
    )
}

ROLE_TO_TYPE_SITE = {
    'ADMINISTRATEUR_NATIONAL': None,
    'RESPONSABLE_NATIONAL': None,
    'GESTIONNAIRE_NATIONAL': None,
    'SUPPORT_NATIONAL': None,
    'SUPERVISEUR_ECHANGES': None,
    'RESPONSABLE_ZONAL': 'Site.EnsembleZonal',
    'ADMINISTRATEUR_PA': 'Site.StructureAccueil',
    'RESPONSABLE_PA': 'Site.StructureAccueil',
    'GESTIONNAIRE_PA': 'Site.StructureAccueil',
    'ADMINISTRATEUR_PREFECTURE': 'Site.Prefecture',
    'RESPONSABLE_GU_ASILE_PREFECTURE': 'Site.GU',
    'GESTIONNAIRE_GU_ASILE_PREFECTURE': 'Site.GU',
    'GESTIONNAIRE_ASILE_PREFECTURE': 'Site.Prefecture',
    'GESTIONNAIRE_DE_TITRES': 'Site.Prefecture',
    'ADMINISTRATEUR_DT_OFII': 'Site.Prefecture',
    'RESPONSABLE_GU_DT_OFII': 'Site.GU',
    'GESTIONNAIRE_GU_DT_OFII': 'Site.GU',
    'EXTRACTEUR': None
}

ROLE_WITH_SITE_INHERITANCE = (  # Those roles keep the same site than they creator
    'RESPONSABLE_PA',
    'GESTIONNAIRE_PA',
    'GESTIONNAIRE_ASILE_PREFECTURE',
    'GESTIONNAIRE_DE_TITRES'
)

ROLE_WITH_SITE_RATTACHE = (  # Those roles take the creator site's autorite_rattachement
    'RESPONSABLE_GU_ASILE_PREFECTURE',
    'GESTIONNAIRE_GU_ASILE_PREFECTURE',
    'RESPONSABLE_GU_DT_OFII',
    'GESTIONNAIRE_GU_DT_OFII'
)

ROLE_SYSTEME = (
    'SYSTEME_INEREC',
    'SYSTEME_DNA',
    'SYSTEME_AGDREF'
)

ROLE_ADMIN = (
    'ADMINISTRATEUR',
    'ADMINISTRATEUR_NATIONAL'
)


def check_can_see_user_by_role(user_actor_role, to_see_user_role):
    if user_actor_role == 'ADMINISTRATEUR_PREFECTURE':
        if to_see_user_role not in ('RESPONSABLE_GU_ASILE_PREFECTURE',
                                    'GESTIONNAIRE_GU_ASILE_PREFECTURE',
                                    'GESTIONNAIRE_ASILE_PREFECTURE',
                                    'GESTIONNAIRE_DE_TITRES'):
            return False
    elif user_actor_role == 'ADMINISTRATEUR_DT_OFII':
        if to_see_user_role not in ('RESPONSABLE_GU_DT_OFII', 'GESTIONNAIRE_GU_DT_OFII'):
            return False
    return True


def get_can_see_user_by_role_lookup(user_actor_role, solr=False):
    if user_actor_role == 'ADMINISTRATEUR_PREFECTURE':
        roles = ('RESPONSABLE_GU_ASILE_PREFECTURE', 'GESTIONNAIRE_GU_ASILE_PREFECTURE',
                 'GESTIONNAIRE_ASILE_PREFECTURE', 'GESTIONNAIRE_DE_TITRES')
    elif user_actor_role == 'ADMINISTRATEUR_DT_OFII':
        roles = ('RESPONSABLE_GU_DT_OFII', 'GESTIONNAIRE_GU_DT_OFII')
    else:
        return [] if solr else {}
    if solr:
        # TODO: multirole solr
        return [' OR '.join('accreditations_role:%s' % r for r in roles)]
    else:
        return {'accreditations__role__in': roles}


def check_role_on_meta_utilisateur(to_create_user):
    """
    Implement special rules on utilisateur creation according to
    the creator's own role
    """
    # If creator has no role (i.g. use a list of permissions), do nothing
    errors = {}
    # We have to run the check for each accreditation
    for i, to_create_accreditation in enumerate(to_create_user.accreditations):
        errors[i] = check_role_on_meta_utilisateur_per_accreditation(to_create_accreditation)
    return {str(k): v for k, v in errors.items() if v}


def check_role_on_meta_utilisateur_per_accreditation(to_create_accreditation):
    current_user_role = current_user.controller.get_current_role()
    current_user_site_affecte = current_user.controller.get_current_site_affecte()
    role_to_assign = to_create_accreditation.role
    site_affecte_to_assign = to_create_accreditation.site_affecte
    errors = {}

    # First make sure the creator is allowed to assigned this type of role
    role_current_user_can_assign = ROLE_TO_CAN_SET_ROLES.get(current_user_role, ())
    if (role_current_user_can_assign is not True and
            role_to_assign not in role_current_user_can_assign):
        errors['role'] = "un utilisateur %s ne peut pas assigner un role %s" %  \
            (current_user_role, role_to_assign)

    # Now check the utilisateur's type of site is compatible with the role
    type_site = ROLE_TO_TYPE_SITE.get(role_to_assign)
    if not type_site:
        if site_affecte_to_assign:
            errors['site'] = ("un utilisateur %s n'a pas de site assigné" %
                              (role_to_assign or 'sans role'))
    elif (not site_affecte_to_assign or
            site_affecte_to_assign._class_name != type_site):
        errors['site'] = ("un utilisateur %s est assigné à un site %s" %
                          (role_to_assign, type_site))

    # Finally check the site inheritance rule for some roles
    if current_user_site_affecte:
        if role_to_assign in ROLE_WITH_SITE_INHERITANCE:
            if not site_affecte_to_assign or site_affecte_to_assign != current_user_site_affecte:
                errors[
                    'site'] = "un utilisateur %s doit hériter du site de son créateur" % role_to_assign
        elif role_to_assign in ROLE_WITH_SITE_RATTACHE:
            if (not site_affecte_to_assign or
                    getattr(site_affecte_to_assign, 'autorite_rattachement', None) != current_user_site_affecte):
                errors[
                    'site'] = "un utilisateur %s doit avoir un site rattaché à la préfecture de son créateur" % role_to_assign
    return errors


def is_system_accreditation(accreditations):
    return any(accreditation.role in ROLE_SYSTEME
               for accreditation in accreditations)


ROLES = {
    'ADMINISTRATEUR': POLICIES,
    'SYSTEME_INEREC': [
        POLICIES.demande_asile.voir,
        POLICIES.demande_asile.modifier,
        POLICIES.demande_asile.requalifier_procedure,
        POLICIES.demande_asile.modifier_ofpra,
        POLICIES.demande_asile.cloture_ofpra,
        POLICIES.demande_asile.finir_procedure,
        POLICIES.demande_asile.modifier_stock_dna,
        POLICIES.demande_asile.prefecture_rattachee.sans_limite,
        POLICIES.droit.voir,
        POLICIES.droit.prefecture_rattachee.sans_limite,
        POLICIES.usager.voir,
        POLICIES.usager.prefecture_rattachee.sans_limite,
        POLICIES.usager.modifier,
        POLICIES.usager.etat_civil.valider,
        POLICIES.usager.etat_civil.modifier,
        POLICIES.usager.modifier_ofpra
    ],
    'SYSTEME_DNA': [
        POLICIES.demande_asile.voir,
        POLICIES.demande_asile.modifier,
        POLICIES.demande_asile.orienter,
        POLICIES.demande_asile.prefecture_rattachee.sans_limite,
        POLICIES.site.voir,
        POLICIES.site.sans_limite_site_affecte,
        POLICIES.recueil_da.voir,
        POLICIES.recueil_da.prefecture_rattachee.sans_limite,
        POLICIES.droit.voir,
        POLICIES.droit.prefecture_rattachee.sans_limite,
        POLICIES.usager.voir,
        POLICIES.usager.prefecture_rattachee.sans_limite,
        POLICIES.usager.modifier,
        POLICIES.usager.etat_civil.modifier,
        POLICIES.recueil_da.enregistrer_famille_ofii,
        POLICIES.usager.modifier_ofii
    ],
    'SYSTEME_AGDREF': [
        POLICIES.demande_asile.voir,
        POLICIES.demande_asile.modifier,
        POLICIES.demande_asile.modifier_dublin,
        POLICIES.demande_asile.requalifier_procedure,
        POLICIES.demande_asile.finir_procedure,
        POLICIES.demande_asile.prefecture_rattachee.sans_limite,
        POLICIES.site.voir,
        POLICIES.site.sans_limite_site_affecte,
        # POLICIES.site.prefecture_rattachee.sans_limite,
        POLICIES.droit.voir,
        POLICIES.droit.prefecture_rattachee.sans_limite,
        POLICIES.usager.voir,
        POLICIES.usager.modifier,
        POLICIES.usager.modifier_agdref,
        POLICIES.usager.etat_civil.modifier,
        POLICIES.usager.prefecture_rattachee.sans_limite,
        POLICIES.recueil_da.voir,
        POLICIES.recueil_da.prefecture_rattachee.sans_limite,
    ],
    'ADMINISTRATEUR_NATIONAL': [
        POLICIES.utilisateur.creer,
        POLICIES.utilisateur.changer_mot_de_passe_utilisateur,
        POLICIES.utilisateur.modifier,
        POLICIES.utilisateur.voir,
        POLICIES.utilisateur.sans_limite_site_affecte,
        POLICIES.utilisateur.accreditations.gerer,
        POLICIES.site.voir,
        POLICIES.site.creer,
        POLICIES.site.modifier,
        POLICIES.site.fermer,
        POLICIES.site.sans_limite_site_affecte,
        POLICIES.broker.gerer,
        POLICIES.parametrage.gerer,
        POLICIES.telemOfpra.voir
    ],
    'RESPONSABLE_NATIONAL': [
        POLICIES.site.export,
        POLICIES.recueil_da.export,
        POLICIES.demande_asile.export,
        POLICIES.usager.export,
        POLICIES.droit.export,
        POLICIES.site.voir,
        POLICIES.site.sans_limite_site_affecte,
        POLICIES.analytics.voir
    ],
    'SUPPORT_NATIONAL': [
        POLICIES.utilisateur.voir,
        POLICIES.utilisateur.sans_limite_site_affecte,
        POLICIES.site.voir,
        POLICIES.site.sans_limite_site_affecte,
        POLICIES.site.actualite.gerer,
        POLICIES.site.export,
        POLICIES.recueil_da.voir,
        POLICIES.recueil_da.prefecture_rattachee.sans_limite,
        POLICIES.recueil_da.export,
        POLICIES.demande_asile.voir,
        POLICIES.demande_asile.prefecture_rattachee.sans_limite,
        POLICIES.demande_asile.export,
        POLICIES.droit.voir,
        POLICIES.droit.prefecture_rattachee.sans_limite,
        POLICIES.droit.export,
        POLICIES.usager.voir,
        POLICIES.usager.prefecture_rattachee.sans_limite,
        POLICIES.usager.export,
        POLICIES.fichier.voir,
        POLICIES.telemOfpra.voir
    ],
    'RESPONSABLE_ZONAL': [
        POLICIES.site.export,
        POLICIES.site.voir,
        POLICIES.recueil_da.export,
        POLICIES.recueil_da.prefecture_rattachee.sans_limite,
        POLICIES.recueil_da.voir,
        POLICIES.analytics.voir
    ],
    'SUPERVISEUR_ECHANGES': [
        POLICIES.broker.gerer
    ],
    'ADMINISTRATEUR_PA': [
        POLICIES.utilisateur.creer,
        POLICIES.utilisateur.modifier,
        POLICIES.utilisateur.voir,
        POLICIES.utilisateur.changer_mot_de_passe_utilisateur,
        POLICIES.utilisateur.accreditations.gerer,
        POLICIES.site.voir
    ],
    'RESPONSABLE_PA': [
        POLICIES.site.voir,
        POLICIES.recueil_da.voir,
        POLICIES.recueil_da.creer_brouillon,
        POLICIES.recueil_da.modifier_brouillon
    ],
    'GESTIONNAIRE_PA': [
        POLICIES.site.voir,
        POLICIES.recueil_da.voir,
        POLICIES.recueil_da.creer_brouillon,
        POLICIES.recueil_da.modifier_brouillon
    ],
    'ADMINISTRATEUR_PREFECTURE': [
        POLICIES.utilisateur.creer,
        POLICIES.utilisateur.modifier,
        POLICIES.utilisateur.voir,
        POLICIES.utilisateur.changer_mot_de_passe_utilisateur,
        POLICIES.utilisateur.accreditations.gerer,
        POLICIES.site.voir
    ],
    'GESTIONNAIRE_NATIONAL': [
        POLICIES.recueil_da.voir,
        POLICIES.recueil_da.prefecture_rattachee.sans_limite,
        POLICIES.demande_asile.voir,
        POLICIES.demande_asile.prefecture_rattachee.sans_limite,
        POLICIES.droit.voir,
        POLICIES.droit.prefecture_rattachee.sans_limite,
        POLICIES.site.voir,
        POLICIES.site.sans_limite_site_affecte,
        POLICIES.usager.voir,
        POLICIES.usager.prefecture_rattachee.sans_limite,
        POLICIES.analytics.voir
    ],
    'RESPONSABLE_GU_ASILE_PREFECTURE': [
        POLICIES.utilisateur.voir,
        POLICIES.utilisateur.creer,
        POLICIES.utilisateur.accreditations.gerer,
        POLICIES.site.voir,
        POLICIES.site.modifier,
        POLICIES.site.creneaux.gerer,
        POLICIES.site.rendez_vous.gerer,
        POLICIES.site.actualite.gerer,
        POLICIES.site.modele.gerer,
        POLICIES.recueil_da.voir,
        POLICIES.recueil_da.creer_pa_realise,
        POLICIES.recueil_da.modifier_pa_realise,
        POLICIES.recueil_da.generer_eurodac,
        POLICIES.recueil_da.modifier_demandeurs_identifies,
        POLICIES.recueil_da.rendez_vous.gerer,
        POLICIES.demande_asile.voir,
        POLICIES.demande_asile.orienter,
        POLICIES.demande_asile.editer_attestation,
        POLICIES.demande_asile.modifier,
        POLICIES.demande_asile.requalifier_procedure,
        POLICIES.demande_asile.finir_procedure,
        POLICIES.usager.voir,
        POLICIES.usager.consulter_fpr,
        POLICIES.usager.modifier,
        POLICIES.usager.etat_civil.modifier,
        POLICIES.usager.prefecture_rattachee.modifier,
        POLICIES.usager.etat_civil.modifier_photo,
        POLICIES.droit.creer,
        POLICIES.droit.voir,
        POLICIES.droit.support.creer,
        POLICIES.droit.support.annuler,
        POLICIES.telemOfpra.creer,
        POLICIES.historique.voir,
        POLICIES.analytics.voir
    ],
    'GESTIONNAIRE_GU_ASILE_PREFECTURE': [
        POLICIES.utilisateur.voir,
        POLICIES.site.voir,
        POLICIES.site.rendez_vous.gerer,
        POLICIES.recueil_da.voir,
        POLICIES.recueil_da.creer_pa_realise,
        POLICIES.recueil_da.modifier_pa_realise,
        POLICIES.recueil_da.generer_eurodac,
        POLICIES.recueil_da.modifier_demandeurs_identifies,
        POLICIES.recueil_da.rendez_vous.gerer,
        POLICIES.demande_asile.voir,
        POLICIES.demande_asile.orienter,
        POLICIES.demande_asile.editer_attestation,
        POLICIES.demande_asile.modifier,
        POLICIES.demande_asile.requalifier_procedure,
        POLICIES.demande_asile.finir_procedure,
        POLICIES.usager.voir,
        POLICIES.usager.consulter_fpr,
        POLICIES.usager.modifier,
        POLICIES.usager.etat_civil.modifier,
        POLICIES.usager.prefecture_rattachee.modifier,
        POLICIES.usager.etat_civil.modifier_photo,
        POLICIES.droit.creer,
        POLICIES.droit.voir,
        POLICIES.droit.support.creer,
        POLICIES.droit.support.annuler,
        POLICIES.telemOfpra.creer
    ],
    'GESTIONNAIRE_ASILE_PREFECTURE': [
        POLICIES.site.voir,
        POLICIES.demande_asile.voir,
        POLICIES.demande_asile.orienter,
        POLICIES.demande_asile.editer_attestation,
        POLICIES.demande_asile.modifier,
        POLICIES.demande_asile.requalifier_procedure,
        POLICIES.demande_asile.finir_procedure,
        POLICIES.droit.creer,
        POLICIES.droit.voir,
        POLICIES.droit.support.creer,
        POLICIES.droit.support.annuler,
        POLICIES.usager.voir,
        POLICIES.usager.consulter_fpr,
        POLICIES.usager.modifier,
        POLICIES.usager.etat_civil.modifier_photo,
        POLICIES.usager.etat_civil.modifier,
        POLICIES.usager.prefecture_rattachee.modifier,
        POLICIES.telemOfpra.creer,
        POLICIES.analytics.voir
    ],
    'GESTIONNAIRE_DE_TITRES': [
        POLICIES.site.voir,
        POLICIES.timbre.voir,
        POLICIES.usager.voir,
        POLICIES.timbre.consommer,
        POLICIES.usager.prefecture_rattachee.sans_limite
    ],
    'ADMINISTRATEUR_DT_OFII': [
        POLICIES.utilisateur.creer,
        POLICIES.utilisateur.modifier,
        POLICIES.utilisateur.voir,
        POLICIES.utilisateur.accreditations.gerer,
        POLICIES.utilisateur.changer_mot_de_passe_utilisateur,
        POLICIES.site.voir
    ],
    'RESPONSABLE_GU_DT_OFII': [
        POLICIES.site.voir,
        POLICIES.site.modifier,
        POLICIES.site.creneaux.gerer,
        POLICIES.site.rendez_vous.gerer,
        POLICIES.site.actualite.gerer,
        POLICIES.site.modele.gerer,
        POLICIES.recueil_da.voir,
        POLICIES.analytics.voir
    ],
    'GESTIONNAIRE_GU_DT_OFII': [
        POLICIES.site.voir,
        POLICIES.site.actualite.gerer,
        POLICIES.recueil_da.voir,
    ],
    'EXTRACTEUR': [
        POLICIES.demande_asile.condition_exceptionnelle.export,
        POLICIES.demande_asile.en_attente_introduction_ofpra.export,
    ]
}
