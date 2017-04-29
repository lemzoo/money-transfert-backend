# Try to import as much fixtures as possible, order is important for
# fixtures with dependancies
for cmd in [
    """from tests.fixture_user import(
        user,
        user_with_accreditations,
        user_with_site_affecte,
        another_user,
        administrateur,
        administrateur_national,
        administrateur_prefecture,
        responsable_gu_asile_prefecture,
        gestionnaire_gu_asile_prefecture,
        administrateur_pa,
        responsable_pa,
        gestionnaire_pa,
        gestionnaire_titres,
        set_user_accreditation)""",

    """from tests.fixture_usager import (
    usager_payload,
    usager,
    usager_with_credentials)""",

    """from tests.fixture_site import (
        site,
        site_prefecture,
        site_gu,
        site_structure_accueil,
        site_ensemble_zonal,
        DEFAULT_SITE_PAYLOAD,
        DEFAULT_UNKNOWN_ADDRESS_SITE_PAYLOAD,
        DEFAULT_SITE_MODELE_PAYLOAD)""",

    "from tests.test_fichier import fichier",

    """from tests.test_referential import (
        ref_langues_ofpra,
        ref_langues_iso,
        ref_nationalites,
        ref_pays,
        ref_insee_agdref)""",

    "from tests.test_usager import usager_payload, usager",

    """from tests.recueil_da.test_brouillon import (
        brouillon,
        brouillon_payload,
        payload_pa_fini)""",

    """from tests.recueil_da.test_pa_realise import (
        pa_realise,
        demandeurs_identifies_pret,
        demandeurs_identifies_pret2,
        photo,
        payload_post_pa_realise)""",

    """from tests.recueil_da.test_solr import (
        other_structure_accueil,
        other_gu,
        other_pref,
        recueils)""",

    """from tests.recueil_da.test_demandeurs_identifies import(
        demandeurs_identifies,
        exploite_pret_reexamen,
        exploite_pret)""",

    "from tests.recueil_da.test_exploite import exploite",
    "from tests.recueil_da.test_annule import annule",
    "from tests.recueil_da.test_purge import purge",

    "from tests.demande_asile.test_orientation import da_orientation_payload, da_orientation",
    "from tests.demande_asile.test_prete_edition_attestation import da_prete_ea",
    "from tests.demande_asile.test_procedure_dublin import da_en_cours_dublin",
    "from tests.demande_asile.test_fin_procedure import da_fin_dublin",
    "from tests.demande_asile.test_attente_ofpra import da_attente_ofpra",
    "from tests.demande_asile.test_instruction_ofpra import da_instruction_ofpra",
    "from tests.demande_asile.test_decision_definitive import da_decision_def",

    "from tests.test_droit import droit"
]:
    try:
        exec(cmd)
    except ImportError as exc:
        print('FIXTURE IMPORT ERROR ==> %s' % exc)
        continue
