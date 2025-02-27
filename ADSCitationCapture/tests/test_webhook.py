import unittest
import httpretty
import datetime
import json
import adsmsg
from ADSCitationCapture import app, tasks
from ADSCitationCapture import webhook
from .test_base import TestBase

now = datetime.datetime.now()

class TestWorkers(TestBase):

    def setUp(self):
        TestBase.setUp(self)
        httpretty.enable()  # enable HTTPretty so that it will monkey patch the socket module
        httpretty.register_uri(httpretty.POST, self.app.conf['ADS_WEBHOOK_URL'], status=200, body="", content_type="application/json")

    def tearDown(self):
        TestBase.tearDown(self)
        httpretty.disable()
        httpretty.reset()   # clean up registered urls and request history

    def _assert_request(self, request, expected_json_body):
        self.assertEqual(request.method, 'POST', "Incorrect request method.")
        self.assertEqual(request.headers['content-type'], 'application/json', "Incorrect request headers.")
        self.assertEqual(request.headers['authorization'], 'Bearer {}'.format(self.app.conf['ADS_WEBHOOK_AUTH_TOKEN']), "Incorrect request headers.")
        self.assertEqual(request.querystring, {}, "The request field \'queryString\' does not have the expected values.")
        json_body = json.loads(request.body)
        self.assertEqual(json_body, expected_json_body, "The request body does not have the expected values.")


    def _build_expected_json_body(self, event_type, original_relationship_name, source_bibcode, target_id, target_id_schema, target_url):
        expected_json_body = [{
            'RelationshipType': {
                'SubTypeSchema': 'DataCite',
                'SubType': original_relationship_name,
                'Name': 'References'
            },
            'Source': {
                'Identifier': {
                    'IDScheme': 'ads',
                    'IDURL': 'http://adsabs.harvard.edu/abs/{}'.format(source_bibcode),
                    'ID': source_bibcode
                },
                'Type': {
                    'Name': 'unknown'
                }
            },
            'LicenseURL': 'https://creativecommons.org/publicdomain/zero/1.0/',
            'Target': {
                'Identifier': {
                    'IDScheme': target_id_schema,
                    'IDURL': target_url,
                    'ID': target_id
                },
                'Type': {
                    'Name': 'software'
                }
            },
            'LinkPublicationDate': now.strftime("%Y-%m-%d"),
            'LinkProvider': [
                {
                    'Name': 'SAO/NASA Astrophysics Data System'
                }
            ]
        }]
        return expected_json_body

    ### DOI
    #@unittest.skip("Waiting for the concrete specification from the Zenodo team")
    def test_doi_new_citation(self):
        citation_changes = adsmsg.CitationChanges()
        citation_change = citation_changes.changes.add()
        citation_change.citing = '2005CaJES..42.1987P'
        citation_change.cited = '...................'
        citation_change.content = '10.1016/0277-3791'
        citation_change.content_type = adsmsg.CitationChangeContentType.doi
        citation_change.resolved = False
        citation_change.status = adsmsg.Status.new
        expected_event_type = "relation_created"
        expected_original_relationship_name = "Cites"
        expected_source_bibcode = citation_change.citing
        expected_target_id = citation_change.content
        expected_target_id_schema = "doi"
        expected_target_url = "https://doi.org/{}".format(expected_target_id)
        expected_json_body = self._build_expected_json_body(expected_event_type, expected_original_relationship_name, expected_source_bibcode, expected_target_id, expected_target_id_schema, expected_target_url)

        event_data = webhook.citation_change_to_event_data(citation_change)
        emitted = webhook.emit_event(self.app.conf['ADS_WEBHOOK_URL'], self.app.conf['ADS_WEBHOOK_AUTH_TOKEN'], event_data, timeout=30)
        self.assertTrue(emitted, "Agreed citation change was NOT assigned to an agreed event")
        request = httpretty.last_request()
        self._assert_request(request, expected_json_body)

    #@unittest.skip("Waiting for the concrete specification from the Zenodo team")
    def test_doi_new_citation_with_bibcode(self):
        citation_changes = adsmsg.CitationChanges()
        citation_change = citation_changes.changes.add()
        citation_change.citing = '2005CaJES..42.1881M'
        citation_change.cited = '1986JPet...27..745B'
        citation_change.content = '10.1093/petrology/27.3.745'
        citation_change.content_type = adsmsg.CitationChangeContentType.doi
        citation_change.resolved = True
        citation_change.status = adsmsg.Status.new
        expected_event_type = "relation_created"
        expected_original_relationship_name = "Cites"
        expected_source_bibcode = citation_change.citing
        expected_target_id = citation_change.content
        expected_target_id_schema = "doi"
        expected_target_url = "https://doi.org/{}".format(expected_target_id)
        expected_json_body = self._build_expected_json_body(expected_event_type, expected_original_relationship_name, expected_source_bibcode, expected_target_id, expected_target_id_schema, expected_target_url)

        event_data = webhook.citation_change_to_event_data(citation_change)
        emitted = webhook.emit_event(self.app.conf['ADS_WEBHOOK_URL'], self.app.conf['ADS_WEBHOOK_AUTH_TOKEN'], event_data, timeout=30)
        self.assertTrue(emitted, "Agreed citation change was NOT assigned to an agreed event")
        request = httpretty.last_request()
        self._assert_request(request, expected_json_body)

    #@unittest.skip("Waiting for the concrete specification from the Zenodo team")
    def test_doi_updated_citation(self):
        citation_changes = adsmsg.CitationChanges()
        citation_change = citation_changes.changes.add()
        citation_change.citing = '1999ITGRS..37..917L'
        citation_change.cited = '...................' # previous_cited 1997ASAJ..101Q3182L
        citation_change.content = '10.1121/1.419176'
        citation_change.content_type = adsmsg.CitationChangeContentType.doi
        citation_change.resolved = False
        citation_change.status = adsmsg.Status.updated

        event_data = webhook.citation_change_to_event_data(citation_change)
        emitted = webhook.emit_event(self.app.conf['ADS_WEBHOOK_URL'], self.app.conf['ADS_WEBHOOK_AUTH_TOKEN'], event_data, timeout=30)
        self.assertFalse(emitted, "Non-agreed citation change was assigned to an agreed event")


    #@unittest.skip("Waiting for the concrete specification from the Zenodo team")
    def test_doi_updated_citation_with_bibcode(self):
        citation_changes = adsmsg.CitationChanges()
        citation_change = citation_changes.changes.add()
        citation_change.citing = '1998CP....232..343L'
        citation_change.content = '1991SPIE.1361.1048S'
        citation_change.content_type = adsmsg.CitationChangeContentType.doi
        citation_change.resolved = True
        citation_change.status = adsmsg.Status.updated
        expected_event_type = "relation_created"
        expected_original_relationship_name = "IsIdenticalTo"
        expected_source_bibcode = citation_change.cited
        expected_target_id = citation_change.content
        expected_target_id_schema = "doi"
        expected_target_url = "https://doi.org/{}".format(expected_target_id)
        expected_json_body = self._build_expected_json_body(expected_event_type, expected_original_relationship_name, expected_source_bibcode, expected_target_id, expected_target_id_schema, expected_target_url)

        event_data = webhook.citation_change_to_event_data(citation_change)
        emitted = webhook.emit_event(self.app.conf['ADS_WEBHOOK_URL'], self.app.conf['ADS_WEBHOOK_AUTH_TOKEN'], event_data, timeout=30)
        self.assertFalse(emitted, "Agreed citation change was NOT assigned to an agreed event")

    @unittest.skip("Waiting for the Zenodo team to implement deletion")
    def test_doi_deleted_citation(self):
        citation_changes = adsmsg.CitationChanges()
        citation_change = citation_changes.changes.add()
        citation_change.citing = '2000JGeod..74..134G'
        citation_change.cited = '...................'
        citation_change.content = '10.1023/A:1023356803773'
        citation_change.content_type = adsmsg.CitationChangeContentType.doi
        citation_change.resolved = False
        citation_change.status = adsmsg.Status.deleted
        expected_event_type = "relation_deleted"
        expected_original_relationship_name = "Cites"
        expected_source_bibcode = citation_change.citing
        expected_target_id = citation_change.content
        expected_target_id_schema = "doi"
        expected_target_url = "https://doi.org/{}".format(expected_target_id)
        expected_json_body = self._build_expected_json_body(expected_event_type, expected_original_relationship_name, expected_source_bibcode, expected_target_id, expected_target_id_schema, expected_target_url)

        event_data = webhook.citation_change_to_event_data(citation_change)
        emitted = webhook.emit_event(self.app.conf['ADS_WEBHOOK_URL'], self.app.conf['ADS_WEBHOOK_AUTH_TOKEN'], event_data, timeout=30)
        self.assertTrue(emitted, "Agreed citation change was NOT assigned to an agreed event")
        request = httpretty.last_request()
        self._assert_request(request, expected_json_body)

    @unittest.skip("Waiting for the Zenodo team to implement deletion")
    def test_doi_deleted_citation_with_bibcode(self):
        citation_changes = adsmsg.CitationChanges()
        citation_change = citation_changes.changes.add()
        citation_change.citing = '2000JMP....41.1788O'
        citation_change.cited = '1990JMP....31..316D'
        citation_change.content = '10.1063/1.528916'
        citation_change.content_type = adsmsg.CitationChangeContentType.doi
        citation_change.resolved = True
        citation_change.status = adsmsg.Status.deleted
        expected_event_type = "relation_deleted"
        expected_original_relationship_name = "Cites"
        expected_source_bibcode = citation_change.citing
        expected_target_id = citation_change.content
        expected_target_id_schema = "doi"
        expected_target_url = "https://doi.org/{}".format(expected_target_id)
        expected_json_body = self._build_expected_json_body(expected_event_type, expected_original_relationship_name, expected_source_bibcode, expected_target_id, expected_target_id_schema, expected_target_url)

        event_data = webhook.citation_change_to_event_data(citation_change)
        emitted = webhook.emit_event(self.app.conf['ADS_WEBHOOK_URL'], self.app.conf['ADS_WEBHOOK_AUTH_TOKEN'], event_data, timeout=30)
        self.assertTrue(emitted, "Agreed citation change was NOT assigned to an agreed event")
        request = httpretty.last_request()
        self._assert_request(request, expected_json_body)

    ### ASCL
    #@unittest.skip("Waiting for the concrete specification from the Zenodo team")
    def test_ascl_new_citation(self):
        citation_changes = adsmsg.CitationChanges()
        citation_change = citation_changes.changes.add()
        citation_change.citing = '2017MNRAS.470.1687B'
        citation_change.cited = '...................'
        citation_change.content = 'ascl:1210.002'
        citation_change.content_type = adsmsg.CitationChangeContentType.pid
        citation_change.resolved = False
        citation_change.status = adsmsg.Status.new
        expected_event_type = "relation_created"
        expected_original_relationship_name = "Cites"
        expected_source_bibcode = citation_change.citing
        expected_target_id = citation_change.content
        expected_target_id_schema = "ascl"
        expected_target_url = "https://ascl.net/{}".format(expected_target_id)
        expected_json_body = self._build_expected_json_body(expected_event_type, expected_original_relationship_name, expected_source_bibcode, expected_target_id, expected_target_id_schema, expected_target_url)

        event_data = webhook.citation_change_to_event_data(citation_change)
        emitted = webhook.emit_event(self.app.conf['ADS_WEBHOOK_URL'], self.app.conf['ADS_WEBHOOK_AUTH_TOKEN'], event_data, timeout=30)
        self.assertTrue(emitted, "Agreed citation change was NOT assigned to an agreed event")
        request = httpretty.last_request()
        self._assert_request(request, expected_json_body)

    #@unittest.skip("Waiting for the concrete specification from the Zenodo team")
    def test_ascl_new_citation_with_bibcode(self):
        citation_changes = adsmsg.CitationChanges()
        citation_change = citation_changes.changes.add()
        citation_change.citing = '2017A&A...603A.117S'
        citation_change.cited = '2011ascl.soft06002P'
        citation_change.content = 'ascl:1106.002'
        citation_change.content_type = adsmsg.CitationChangeContentType.pid
        citation_change.resolved = True
        citation_change.status = adsmsg.Status.new
        expected_event_type = "relation_created"
        expected_original_relationship_name = "Cites"
        expected_source_bibcode = citation_change.citing
        expected_target_id = citation_change.content
        expected_target_id_schema = "ascl"
        expected_target_url = "https://ascl.net/{}".format(expected_target_id)
        expected_json_body = self._build_expected_json_body(expected_event_type, expected_original_relationship_name, expected_source_bibcode, expected_target_id, expected_target_id_schema, expected_target_url)

        event_data = webhook.citation_change_to_event_data(citation_change)
        emitted = webhook.emit_event(self.app.conf['ADS_WEBHOOK_URL'], self.app.conf['ADS_WEBHOOK_AUTH_TOKEN'], event_data, timeout=30)
        self.assertTrue(emitted, "Agreed citation change was NOT assigned to an agreed event")
        request = httpretty.last_request()
        self._assert_request(request, expected_json_body)

    #@unittest.skip("Waiting for the concrete specification from the Zenodo team")
    def test_ascl_updated_citation(self):
        citation_changes = adsmsg.CitationChanges()
        citation_change = citation_changes.changes.add()
        citation_change.citing = '2013MNRAS.432.1658C'
        citation_change.cited = '...................' # previous_cited 2012ascl.soft05004P
        citation_change.content = 'ascl:1205.004'
        citation_change.content_type = adsmsg.CitationChangeContentType.pid
        citation_change.resolved = False
        citation_change.status = adsmsg.Status.updated

        event_data = webhook.citation_change_to_event_data(citation_change)
        emitted = webhook.emit_event(self.app.conf['ADS_WEBHOOK_URL'], self.app.conf['ADS_WEBHOOK_AUTH_TOKEN'], event_data, timeout=30)
        self.assertFalse(emitted, "Non-agreed citation change was assigned to an agreed event")


    #@unittest.skip("Waiting for the concrete specification from the Zenodo team")
    def test_ascl_updated_citation_with_bibcode(self):
        citation_changes = adsmsg.CitationChanges()
        citation_change = citation_changes.changes.add()
        citation_change.citing = ''
        citation_change.cited = ''
        citation_change.content = ''
        citation_change.content_type = adsmsg.CitationChangeContentType.pid
        citation_change.resolved = True
        citation_change.status = adsmsg.Status.updated
        expected_event_type = "relation_created"
        expected_original_relationship_name = "IsIdenticalTo"
        expected_source_bibcode = citation_change.cited
        expected_target_id = citation_change.content
        expected_target_id_schema = "ascl"
        expected_target_url = "https://ascl.net/{}".format(expected_target_id)
        expected_json_body = self._build_expected_json_body(expected_event_type, expected_original_relationship_name, expected_source_bibcode, expected_target_id, expected_target_id_schema, expected_target_url)

        event_data = webhook.citation_change_to_event_data(citation_change)
        emitted = webhook.emit_event(self.app.conf['ADS_WEBHOOK_URL'], self.app.conf['ADS_WEBHOOK_AUTH_TOKEN'], event_data, timeout=30)
        self.assertFalse(emitted, "Agreed citation change was NOT assigned to an agreed event")

    @unittest.skip("Waiting for the Zenodo team to implement deletion")
    def test_ascl_deleted_citation(self):
        citation_changes = adsmsg.CitationChanges()
        citation_change = citation_changes.changes.add()
        citation_change.citing = ''
        citation_change.cited = '...................'
        citation_change.content = ''
        citation_change.content_type = adsmsg.CitationChangeContentType.pid
        citation_change.resolved = False
        citation_change.status = adsmsg.Status.deleted
        expected_event_type = "relation_deleted"
        expected_original_relationship_name = "Cites"
        expected_source_bibcode = citation_change.citing
        expected_target_id = citation_change.content
        expected_target_id_schema = "ascl"
        expected_target_url = "https://ascl.net/{}".format(expected_target_id)
        expected_json_body = self._build_expected_json_body(expected_event_type, expected_original_relationship_name, expected_source_bibcode, expected_target_id, expected_target_id_schema, expected_target_url)

        event_data = webhook.citation_change_to_event_data(citation_change)
        emitted = webhook.emit_event(self.app.conf['ADS_WEBHOOK_URL'], self.app.conf['ADS_WEBHOOK_AUTH_TOKEN'], event_data, timeout=30)
        self.assertFalse(emitted, "Agreed citation change was NOT assigned to an agreed event")

    @unittest.skip("Waiting for the Zenodo team to implement deletion")
    def test_ascl_deleted_citation_with_bibcode(self):
        citation_changes = adsmsg.CitationChanges()
        citation_change = citation_changes.changes.add()
        citation_change.citing = '2017AJ....153..114F'
        citation_change.cited = '2012ascl.soft03003C'
        citation_change.content = 'ascl:1203.003'
        citation_change.content_type = adsmsg.CitationChangeContentType.pid
        citation_change.resolved = True
        citation_change.status = adsmsg.Status.deleted
        expected_event_type = "relation_deleted"
        expected_original_relationship_name = "Cites"
        expected_source_bibcode = citation_change.citing
        expected_target_id = citation_change.content
        expected_target_id_schema = "ascl"
        expected_target_url = "https://ascl.net/{}".format(expected_target_id)
        expected_json_body = self._build_expected_json_body(expected_event_type, expected_original_relationship_name, expected_source_bibcode, expected_target_id, expected_target_id_schema, expected_target_url)

        event_data = webhook.citation_change_to_event_data(citation_change)
        emitted = webhook.emit_event(self.app.conf['ADS_WEBHOOK_URL'], self.app.conf['ADS_WEBHOOK_AUTH_TOKEN'], event_data, timeout=30)
        self.assertFalse(emitted, "Agreed citation change was NOT assigned to an agreed event")



    ### URL
    #@unittest.skip("Waiting for the concrete specification from the Zenodo team")
    def test_url_new_citation(self):
        citation_changes = adsmsg.CitationChanges()
        citation_change = citation_changes.changes.add()
        citation_change.citing = '2017arXiv170610086M'
        citation_change.cited = '...................'
        citation_change.content = 'https://github.com/ComputationalRadiationPhysics/graybat'
        citation_change.content_type = adsmsg.CitationChangeContentType.url
        citation_change.resolved = False
        citation_change.status = adsmsg.Status.new
        expected_event_type = "relation_created"
        expected_original_relationship_name = "Cites"
        expected_source_bibcode = citation_change.citing
        expected_target_id = citation_change.content
        expected_target_id_schema = "url"
        expected_target_url = citation_change.content
        expected_json_body = self._build_expected_json_body(expected_event_type, expected_original_relationship_name, expected_source_bibcode, expected_target_id, expected_target_id_schema, expected_target_url)

        event_data = webhook.citation_change_to_event_data(citation_change)
        emitted = webhook.emit_event(self.app.conf['ADS_WEBHOOK_URL'], self.app.conf['ADS_WEBHOOK_AUTH_TOKEN'], event_data, timeout=30)
        self.assertTrue(emitted, "Agreed citation change was NOT assigned to an agreed event")
        request = httpretty.last_request()
        self._assert_request(request, expected_json_body)

    #@unittest.skip("Waiting for the concrete specification from the Zenodo team")
    def test_url_new_citation_with_bibcode(self):
        citation_changes = adsmsg.CitationChanges()
        citation_change = citation_changes.changes.add()
        citation_change.citing = '2017arXiv170305698M'
        citation_change.cited = '2017iagt.conf.2017G'
        citation_change.content = 'http://www.github.com/capergroup/bayou'
        citation_change.content_type = adsmsg.CitationChangeContentType.url
        citation_change.resolved = True
        citation_change.status = adsmsg.Status.new
        expected_event_type = "relation_created"
        expected_original_relationship_name = "Cites"
        expected_source_bibcode = citation_change.citing
        expected_target_id = citation_change.content
        expected_target_id_schema = "url"
        expected_target_url = citation_change.content
        expected_json_body = self._build_expected_json_body(expected_event_type, expected_original_relationship_name, expected_source_bibcode, expected_target_id, expected_target_id_schema, expected_target_url)

        event_data = webhook.citation_change_to_event_data(citation_change)
        emitted = webhook.emit_event(self.app.conf['ADS_WEBHOOK_URL'], self.app.conf['ADS_WEBHOOK_AUTH_TOKEN'], event_data, timeout=30)
        self.assertTrue(emitted, "Agreed citation change was NOT assigned to an agreed event")
        request = httpretty.last_request()
        self._assert_request(request, expected_json_body)

    #@unittest.skip("Waiting for the concrete specification from the Zenodo team")
    def test_url_updated_citation(self):
        citation_changes = adsmsg.CitationChanges()
        citation_change = citation_changes.changes.add()
        citation_change.citing = '2016CMAME.305..579P'
        citation_change.cited = '...................' # previous_cited 2015LIACo...3....2T
        citation_change.content = 'https://github.com/su2code/TestCases'
        citation_change.content_type = adsmsg.CitationChangeContentType.url
        citation_change.resolved = False
        citation_change.status = adsmsg.Status.updated
        event_data = webhook.citation_change_to_event_data(citation_change)
        emitted = webhook.emit_event(self.app.conf['ADS_WEBHOOK_URL'], self.app.conf['ADS_WEBHOOK_AUTH_TOKEN'], event_data, timeout=30)
        self.assertFalse(emitted, "Non-agreed citation change was assigned to an agreed event")


    #@unittest.skip("Waiting for the concrete specification from the Zenodo team")
    def test_url_updated_citation_with_bibcode(self):
        citation_changes = adsmsg.CitationChanges()
        citation_change = citation_changes.changes.add()
        citation_change.citing = '2016NatSR...637369S'
        citation_change.cited = '2012JOSS...61..539R' # previous_cited 2012ASSL..304..539R
        citation_change.content = 'http://mrbayes.sourceforge.net/'
        citation_change.content_type = adsmsg.CitationChangeContentType.url
        citation_change.resolved = True
        citation_change.status = adsmsg.Status.updated
        expected_event_type = "relation_created"
        expected_original_relationship_name = "IsIdenticalTo"
        expected_source_bibcode = citation_change.cited
        expected_target_id = citation_change.content
        expected_target_id_schema = "url"
        expected_target_url = citation_change.content
        expected_json_body = self._build_expected_json_body(expected_event_type, expected_original_relationship_name, expected_source_bibcode, expected_target_id, expected_target_id_schema, expected_target_url)

        event_data = webhook.citation_change_to_event_data(citation_change)
        emitted = webhook.emit_event(self.app.conf['ADS_WEBHOOK_URL'], self.app.conf['ADS_WEBHOOK_AUTH_TOKEN'], event_data, timeout=30)
        self.assertFalse(emitted, "Agreed citation change was NOT assigned to an agreed event")

    #def test_url_deleted_citation(self):
        #citation_changes = adsmsg.CitationChanges()
        #citation_change = citation_changes.changes.add()
        #citation_change.citing = ''
        #citation_change.cited = '...................'
        #citation_change.content = ''
        #citation_change.content_type = adsmsg.CitationChangeContentType.url
        #citation_change.resolved = False
        #citation_change.status = adsmsg.Status.deleted
        #expected_event_type = "relation_deleted"
        #expected_original_relationship_name = "Cites"
        #expected_source_bibcode = citation_change.citing
        #expected_target_id = citation_change.content
        #expected_target_id_schema = u"url"
        #expected_target_url = citation_change.content
        #expected_json_body = self._build_expected_json_body(expected_event_type, expected_original_relationship_name, expected_source_bibcode, expected_target_id, expected_target_id_schema, expected_target_url)

        #event_data = webhook.citation_change_to_event_data(citation_change)
        #emitted = webhook.emit_event(self.app.conf['ADS_WEBHOOK_URL'], self.app.conf['ADS_WEBHOOK_AUTH_TOKEN'], event_data, timeout=30)
        #self.assertFalse(emitted, "Agreed citation change was NOT assigned to an agreed event")

    #def test_url_deleted_citation_with_bibcode(self):
        #citation_changes = adsmsg.CitationChanges()
        #citation_change = citation_changes.changes.add()
        #citation_change.citing = ''
        #citation_change.cited = ''
        #citation_change.content = ''
        #citation_change.content_type = adsmsg.CitationChangeContentType.url
        #citation_change.resolved = True
        #citation_change.status = adsmsg.Status.deleted
        #expected_event_type = "relation_deleted"
        #expected_original_relationship_name = "Cites"
        #expected_source_bibcode = citation_change.citing
        #expected_target_id = citation_change.content
        #expected_target_id_schema = u"url"
        #expected_target_url = citation_change.content
        #expected_json_body = self._build_expected_json_body(expected_event_type, expected_original_relationship_name, expected_source_bibcode, expected_target_id, expected_target_id_schema, expected_target_url)

        #event_data = webhook.citation_change_to_event_data(citation_change)
        #emitted = webhook.emit_event(self.app.conf['ADS_WEBHOOK_URL'], self.app.conf['ADS_WEBHOOK_AUTH_TOKEN'], event_data, timeout=30)
        #self.assertFalse(emitted, "Agreed citation change was NOT assigned to an agreed event")

if __name__ == '__main__':
    unittest.main()
