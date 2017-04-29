from connector.agdref.common import AGDREFProcessor, format_date, format_text, format_nombre_demande
from connector.agdref.translations import proc_trans


class RequalificationProcedure(AGDREFProcessor):

    BASE_NAME = 'requalificationProcedure'

    def _build_xml(self, msg):
        if msg.context.get('payload', {}).get('acteur', '') == 'PREFECTURE':
            return self.connector.processors['agdref_demande_numero_ou_validation']._build_xml(msg)
        context = msg.context
        xml = self.headers(self.source, '14')

        da = context['demande_asile']
        usager = context['usager']
        procedure = da['procedure']
        requalif = procedure.get('requalifications', [])
        last_requalif = requalif[-1] if requalif else {}

        xml.append('<maj:numeroRessortissantEtranger>%s</maj:numeroRessortissantEtranger>' %
                   usager.get('identifiant_agdref'))
        xml.append('<maj:identifiantSIAsile>%s</maj:identifiantSIAsile>' %
                   usager.get('identifiant_portail_agdref', ''))
        xml.append('<maj:numeroDemandeAsile>%s</maj:numeroDemandeAsile>' %
                   format_nombre_demande(usager))
        procedure_type = proc_trans.translate_out(procedure['type'])
        xml.append('<maj:typeProcedure>%s</maj:typeProcedure>' % procedure_type)
        motif = format_text(procedure.get('motif_qualification'), max=5)
        xml.append('<maj:motifRequalification>%s</maj:motifRequalification>' % motif)
        date_requalif = format_date(last_requalif['date'])
        xml.append('<maj:dateRequalification>%s</maj:dateRequalification>' % date_requalif)
        date_notification = format_date(last_requalif['date_notification'])
        xml.append('<maj:dateNotification>%s</maj:dateNotification>' % date_notification)

        xml.extend(self.footer(self.source))
        return ''.join(xml)
