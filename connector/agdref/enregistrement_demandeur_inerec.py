from connector.agdref.common import (AGDREFProcessor, format_date,
                                     format_nombre_demande, format_demande)
from flask import current_app


class EnregistrementDemandeurINEREC(AGDREFProcessor):

    BASE_NAME = 'enregistrementDemandeurINEREC'

    def _build_xml(self, msg):
        xml = self.headers(self.source, '12')
        context = msg.context
        usager = context['usager']
        da = context['demande_asile']
        xml.append('<maj:numeroRessortissantEtranger>%s</maj:numeroRessortissantEtranger>' %
                   usager.get('identifiant_agdref'))
        xml.append('<maj:identifiantSIAsile>%s</maj:identifiantSIAsile>' %
                   usager.get('identifiant_portail_agdref', ''))
        xml.append('<maj:numeroDemandeAsile>%s</maj:numeroDemandeAsile>' %
                   format_nombre_demande(usager))
        xml.append('<maj:numeroINEREC>%s</maj:numeroINEREC>' % da.get('identifiant_inerec', ''))
        xml.append('<maj:dateEnregistrement>%s</maj:dateEnregistrement>' %
                   format_date(da.get('date_introduction_ofpra')))
        # uncomment this when agdref is ready to receive the information on reexamen in flow 12
        # xml.extend(format_demande(da, complement_reexamen=True))
        xml.extend(self.footer(self.source))
        return ''.join(xml)
