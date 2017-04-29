import io
from datetime import datetime

from broker.manager import _get_cancelled_msg, _write_cancelled_msg_count, _write_cancelled_msg_error_info

from tests.broker.fixtures import *

from tests import common


class TestManager(common.BaseLegacyBrokerTest):

    def test_agdref_error(self, broker):
        msg_cls = broker.model.Message
        msg = msg_cls(
            queue="agdref",
            status='CANCELLED',
            json_context="""{"test": "test"}""",
            handler='agdref_test',
            status_comment=""" <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"><soap:Body><notificationResponse xmlns:ns2="http://www.thalesgroup.com/sbna/" xmlns="http://interieur.gouv.fr/asile/maj"><typeFlux>16</typeFlux><dateEmissionFlux>20160428</dateEmissionFlux><heureEmissionFlux>080017</heureEmissionFlux><numeroRessortissantEtranger>7503001552</numeroRessortissantEtranger><identifiantSIAsile>kV5bqS4BNvi0</identifiantSIAsile><numeroDemandeAsile>01</numeroDemandeAsile><datePriseCompteAGDREF>20160428</datePriseCompteAGDREF><heurePriseCompteAGDREF>100517</heurePriseCompteAGDREF><codeErreur>511</codeErreur></notificationResponse></soap:Body></soap:Envelope> """)
        msg.save()

        msg = msg_cls(
            queue="agdref",
            status='CANCELLED',
            json_context="""{"test": "test"}""",
            handler='agdref_test',
            status_comment=""" <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"><soap:Body><notificationResponse xmlns:ns2="http://www.thalesgroup.com/sbna/" xmlns="http://interieur.gouv.fr/asile/maj"><typeFlux>16</typeFlux><dateEmissionFlux>20160428</dateEmissionFlux><heureEmissionFlux>080017</heureEmissionFlux><numeroRessortissantEtranger>7503001552</numeroRessortissantEtranger><identifiantSIAsile>kV5bqS4BNvi0</identifiantSIAsile><numeroDemandeAsile>01</numeroDemandeAsile><datePriseCompteAGDREF>20160428</datePriseCompteAGDREF><heurePriseCompteAGDREF>100517</heurePriseCompteAGDREF><codeErreur>511</codeErreur></notificationResponse></soap:Body></soap:Envelope> """)
        msg.save()

        msgs_info = _get_cancelled_msg(queue="agdref")
        assert len(msgs_info.counts) == 1
        assert msgs_info.counts['511'] == 2
        assert '511' in msgs_info.error_info
        assert len(msgs_info.error_info['511']) == 2

        stream = io.StringIO()
        _write_cancelled_msg_count(stream, msgs_info.counts)
        assert 'Code erreur,Nombre de messages\r\n511,2\r\n' == stream.getvalue()
        stream = io.StringIO()
        _write_cancelled_msg_error_info(stream, msgs_info.error_info['511'])
        num_lines = sum(1 for line in stream.getvalue().splitlines())
        assert num_lines == 3

    def test_dna_error(self, broker):
        msg_cls = broker.model.Message
        msg = msg_cls(
            queue="dna",
            status='CANCELLED',
            json_context="""{"test": "test"}""",
            handler='dna_test',
            status_comment=""" <?xml version='1.0' encoding='UTF-8'?><S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"><SOAP-ENV:Header/><S:Body><ns2:majDonneesDAResponse xmlns:ns2="http://service.webservices.dna.anaem.social.fr/MajDonneesDAService"><REPONSES><REPONSE><CODE_ERREUR>03</CODE_ERREUR><LIBELLE_ERREUR>La valeur suivant n'est pas présente dans le référentiel : TEST-NATURE</LIBELLE_ERREUR></REPONSE></REPONSES></ns2:majDonneesDAResponse></S:Body></S:Envelope> """)
        msg.save()

        msgs_info = _get_cancelled_msg(queue="dna")
        assert len(msgs_info.counts) == 1
        assert msgs_info.counts['03'] == 1

        stream = io.StringIO()
        _write_cancelled_msg_count(stream, msgs_info.counts)
        assert 'Code erreur,Nombre de messages\r\n03,1\r\n' == stream.getvalue()

    def test_inerec_error(self, broker):
        msg_cls = broker.model.Message
        msg = msg_cls(
            queue="inerec",
            status='CANCELLED',
            json_context="""{"test": "test"}""",
            handler='inerec_test',
            status_comment="Pas de handler pour ce type de message")
        msg.save()

        msgs_info = _get_cancelled_msg(queue="inerec")
        assert len(msgs_info.counts) == 1
        assert msgs_info.counts['Pas de handler pour ce type de message'] == 1

        stream = io.StringIO()
        _write_cancelled_msg_count(stream, msgs_info.counts)
        assert 'Code erreur,Nombre de messages\r\nPas de handler pour ce type de message,1\r\n' == stream.getvalue()

    def test_agdref_error_option(self, broker):
        msg_cls = broker.model.Message
        msg = msg_cls(
            queue="agdref",
            created=datetime.strptime('2016-01-02', "%Y-%m-%d"),
            status='CANCELLED',
            json_context="""{"test": "test"}""",
            handler='agdref_test',
            status_comment=""" <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"><soap:Body><notificationResponse xmlns:ns2="http://www.thalesgroup.com/sbna/" xmlns="http://interieur.gouv.fr/asile/maj"><typeFlux>16</typeFlux><dateEmissionFlux>20160428</dateEmissionFlux><heureEmissionFlux>080017</heureEmissionFlux><numeroRessortissantEtranger>7503001552</numeroRessortissantEtranger><identifiantSIAsile>kV5bqS4BNvi0</identifiantSIAsile><numeroDemandeAsile>01</numeroDemandeAsile><datePriseCompteAGDREF>20160428</datePriseCompteAGDREF><heurePriseCompteAGDREF>100517</heurePriseCompteAGDREF><codeErreur>511</codeErreur></notificationResponse></soap:Body></soap:Envelope> """)
        msg.save()

        msg = msg_cls(
            queue="agdref",
            created=datetime.strptime('2016-01-04', "%Y-%m-%d"),
            status='CANCELLED',
            json_context="""{"test": "test"}""",
            handler='agdref_test2',
            status_comment=""" <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"><soap:Body><notificationResponse xmlns:ns2="http://www.thalesgroup.com/sbna/" xmlns="http://interieur.gouv.fr/asile/maj"><typeFlux>16</typeFlux><dateEmissionFlux>20160428</dateEmissionFlux><heureEmissionFlux>080017</heureEmissionFlux><numeroRessortissantEtranger>7503001552</numeroRessortissantEtranger><identifiantSIAsile>kV5bqS4BNvi0</identifiantSIAsile><numeroDemandeAsile>01</numeroDemandeAsile><datePriseCompteAGDREF>20160428</datePriseCompteAGDREF><heurePriseCompteAGDREF>100517</heurePriseCompteAGDREF><codeErreur>512</codeErreur></notificationResponse></soap:Body></soap:Envelope> """)
        msg.save()

        msg = msg_cls(
            queue="agdref",
            created=datetime.strptime('2016-01-02', "%Y-%m-%d"),
            status='CANCELLED',
            json_context="""{"test": "test"}""",
            handler='agdref_test2',
            status_comment=""" <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"><soap:Body><notificationResponse xmlns:ns2="http://www.thalesgroup.com/sbna/" xmlns="http://interieur.gouv.fr/asile/maj"><typeFlux>16</typeFlux><dateEmissionFlux>20160428</dateEmissionFlux><heureEmissionFlux>080017</heureEmissionFlux><numeroRessortissantEtranger>7503001552</numeroRessortissantEtranger><identifiantSIAsile>kV5bqS4BNvi0</identifiantSIAsile><numeroDemandeAsile>01</numeroDemandeAsile><datePriseCompteAGDREF>20160428</datePriseCompteAGDREF><heurePriseCompteAGDREF>100517</heurePriseCompteAGDREF><codeErreur>513</codeErreur></notificationResponse></soap:Body></soap:Envelope> """)
        msg.save()

        msgs_info = _get_cancelled_msg(queue="agdref", from_date='2016-01-01',
                                       to_date='2016-01-03', event_handler='agdref_test2')
        assert len(msgs_info.counts) == 1
        assert msgs_info.counts['513'] == 1
        assert '513' in msgs_info.error_info
        assert len(msgs_info.error_info['513']) == 1

        stream = io.StringIO()
        _write_cancelled_msg_count(stream, msgs_info.counts)
        assert 'Code erreur,Nombre de messages\r\n513,1\r\n' == stream.getvalue()
        stream = io.StringIO()
        _write_cancelled_msg_error_info(stream, msgs_info.error_info['513'])
        print(stream.getvalue())
        num_lines = sum(1 for line in stream.getvalue().splitlines())
        assert num_lines == 2
