from core.model_util import BaseSolrSearcher, BaseDocument
from sief.model import fields
from sief.model.utilisateur import Utilisateur


class TelemOfpraSearcher(BaseSolrSearcher):
    FIELDS = ('date_demande', 'agent', 'demande_asile', 'identifiant_inerec')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.build_and_register_converter('agent_nom', Utilisateur.nom,
                                          extractor=lambda doc: doc.agent.nom)
        self.build_and_register_converter('agent_prenom', Utilisateur.prenom,
                                          extractor=lambda doc: doc.agent.prenom)
        self.build_and_register_converter('agent_email', Utilisateur.email,
                                          extractor=lambda doc: doc.agent.email)


class TelemOfpra(BaseDocument):
    meta = {'searcher_cls': TelemOfpraSearcher}

    # date_transmission
    date_demande = fields.DateTimeField(required=True)

    agent = fields.ReferenceField("Utilisateur", required=True)
    demande_asile = fields.ReferenceField('DemandeAsile', required=True)
    identifiant_inerec = fields.StringField(max_length=9, required=True)
