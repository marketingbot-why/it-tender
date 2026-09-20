"""Unit and sanity tests for IT tender classification and storage."""

import os
import unittest
from it_filter import ITFilter
from storage import TenderStorage
from scraper import EprocureScraper


class TestITScraper(unittest.TestCase):

    def setUp(self):
        self.filter = ITFilter()
        self.db_test_path = "test_tenders.db"
        if os.path.exists(self.db_test_path):
            os.remove(self.db_test_path)
        self.storage = TenderStorage(db_path=self.db_test_path)

    def tearDown(self):
        if os.path.exists(self.db_test_path):
            os.remove(self.db_test_path)
        for ext in [".csv", ".json"]:
            if os.path.exists(f"test_out{ext}"):
                os.remove(f"test_out{ext}")

    def test_it_tenders_classified_correctly(self):
        test_cases = [
            {
                "title": "Development, implementation and maintenance of web-based portal and mobile app",
                "organisation": "Ministry of Electronics and Information Technology",
                "tender_ref_no": "MeitY/2026/IT-01",
                "expected_it": True,
                "expected_category": "Software & Applications"
            },
            {
                "title": "Supply, installation and commissioning of Server, SAN Storage and Network Switches",
                "organisation": "Indian Institute of Technology Delhi",
                "tender_ref_no": "IITD/SPS/2026/102",
                "expected_it": True,
                "expected_category": "Hardware & Computing"
            },
            {
                "title": "Comprehensive Annual Maintenance Contract (AMC) for Computers, Printers and UPS",
                "organisation": "Bharat Petroleum Corporation Limited",
                "tender_ref_no": "BPCL/IT/AMC/26",
                "expected_it": True,
                "expected_category": "IT Services & Consulting"
            },
            {
                "title": "Implementation of Next-Generation Firewall and SOC Security Information and Event Management (SIEM)",
                "organisation": "Bank of Baroda",
                "tender_ref_no": "BOB/SEC/2026",
                "expected_it": True,
                "expected_category": "Networking & Cybersecurity"
            },
            {
                "title": "Cloud Service Provider (CSP) onboarding for Cloud Hosting on MeghRaj",
                "organisation": "National Informatics Centre Services Incorporated",
                "tender_ref_no": "NICSI/CLOUD/2026",
                "expected_it": True,
                "expected_category": "Cloud & Data Center"
            },
            {
                "title": "Scanning, digitization, indexing and DMS storage of official land records",
                "organisation": "Directorate of Land Records",
                "tender_ref_no": "DLR/DIGI/26",
                "expected_it": True,
                "expected_category": "Digitization & Data Processing"
            },
        ]

        for case in test_cases:
            res = self.filter.classify(case)
            self.assertTrue(res.is_it_tender, f"Failed to detect IT tender: {case['title']}")
            self.assertIn(case["expected_category"], res.categories, f"Missing category {case['expected_category']} for {case['title']}")

    def test_non_it_tenders_excluded(self):
        negative_cases = [
            {
                "title": "Permanent Restoration of road from Kalidub To Loorkote Pkg JK12-360 Rajouri",
                "organisation": "National Rural Roads Development Agency (NRRDA)",
                "tender_ref_no": "EE/PMGSY/R/32",
            },
            {
                "title": "Construction of dust bin in the premises of AHQ office at Urjagram colony under Wani Area",
                "organisation": "Western Coalfields Limited",
                "tender_ref_no": "WCL/wa4350",
            },
            {
                "title": "Catering service and supply of drinking water for staff cafeteria",
                "organisation": "Northern Coalfields Limited",
                "tender_ref_no": "NCL/CAT/2026",
            },
            {
                "title": "Hiring of 50 seated bus for local transport of school children",
                "organisation": "Airports Authority of India",
                "tender_ref_no": "AAI/BUS/26",
            },
            {
                "title": "E-Tender for execution of New OFC Development Replacement works and Laying of OFC cable in Jammu",
                "organisation": "Bharat Sanchar Nigam Limited",
                "tender_ref_no": "BSNL/OFC/2026",
            },
            {
                "title": "Trenching and laying of optical fiber cable along national highway",
                "organisation": "RailTel Corporation of India",
                "tender_ref_no": "RCIL/OFC/2026",
            }
        ]

        for case in negative_cases:
            res = self.filter.classify(case)
            self.assertFalse(res.is_it_tender, f"False positive detected: {case['title']}")

    def test_pagination_url_builder(self):
        scraper = EprocureScraper()
        url1 = scraper.build_page_url("https://eprocure.gov.in/cppp/latestactivetendersnew/cpppdata", 1)
        self.assertEqual(url1, "https://eprocure.gov.in/cppp/latestactivetendersnew/cpppdata")

        url2 = scraper.build_page_url("https://eprocure.gov.in/cppp/latestactivetendersnew/cpppdata", 2)
        self.assertIn("?url=aHR0cHM6Ly9lcHJvY3VyZS5nb3YuaW4vY3BwcC9sYXRlc3RhY3RpdmV0ZW5kZXJzbmV3L2NwcHBkYXRhP3BhZ2U9Mg==", url2)

    def test_extract_next_page_url(self):
        scraper = EprocureScraper()
        sample_html = '''
        <div class="pagination">
            <span class="page_parination">« Previous</span>
            <span class="page_parination">1</span>
            <a class="paginate_button" href="https://eprocure.gov.in/cppp/latestactivetendersnew/cpppdata?url=abc">2</a>
            <a class="paginate_button" href="https://eprocure.gov.in/cppp/latestactivetendersnew/cpppdata?url=xyz">Next »</a>
        </div>
        '''
        next_url = scraper.extract_next_page_url(sample_html)
        self.assertEqual(next_url, "https://eprocure.gov.in/cppp/latestactivetendersnew/cpppdata?url=xyz")

        last_page_html = '<div class="pagination"><span class="page_parination">1</span></div>'
        self.assertIsNone(scraper.extract_next_page_url(last_page_html))

    def test_form_metadata_extraction(self):
        scraper = EprocureScraper()
        sample_form_html = '''
        <form action="/cppp/latestactivetendersnew/cpppdata" method="post">
            <input type="hidden" name="form_build_id" value="form-ABC123XYZ" />
            <input type="hidden" name="form_id" value="latestactivetendersnew_form" />
            <input type="hidden" name="captcha_sid" value="12345" />
            <input type="hidden" name="captcha_token" value="tok987" />
            <img data-drupal-selector="edit-captcha-image" src="/captcha/image/12345" />
            <select name="s_prod_type">
                <option value="select">- Select -</option>
                <option value="Info. Tech. Services">Info. Tech. Services</option>
                <option value="Civil Works">Civil Works</option>
            </select>
        </form>
        '''
        meta = scraper.extract_form_metadata(sample_form_html, "https://eprocure.gov.in/cppp/latestactivetendersnew/cpppdata")
        self.assertIsNotNone(meta)
        self.assertEqual(meta["form_build_id"], "form-ABC123XYZ")
        self.assertEqual(meta["form_id"], "latestactivetendersnew_form")
        self.assertEqual(meta["captcha_sid"], "12345")
        self.assertEqual(meta["captcha_token"], "tok987")
        self.assertIn("/captcha/image/12345", meta["captcha_img_src"])
        self.assertIn("Info. Tech. Services", meta["product_options"])
        self.assertNotIn("select", meta["product_options"])

    def test_category_auto_filtering(self):
        from config import filter_it_categories, is_it_category
        test_cats = [
            "Civil Works",
            "Civil Works - Roads",
            "Info. Tech. Services",
            "Information Technology (IT)",
            "Information Technology/Telecom",
            "Hotel/ Catering Services",
            "Computer Software/Web Site",
            "Computer Hardware",
            "Network /Communication Equipments",
            "Air Conditioner Services",
            "OFC Laying Works"
        ]
        matched = filter_it_categories(test_cats)
        self.assertIn("Info. Tech. Services", matched)
        self.assertIn("Information Technology (IT)", matched)
        self.assertIn("Computer Software/Web Site", matched)
        self.assertNotIn("Computer Hardware", matched)
        self.assertNotIn("Network /Communication Equipments", matched)
        self.assertNotIn("Information Technology/Telecom", matched)
        self.assertNotIn("OFC Laying Works", matched)
        self.assertNotIn("Civil Works", matched)
        self.assertNotIn("Civil Works - Roads", matched)
        self.assertNotIn("Hotel/ Catering Services", matched)
        self.assertNotIn("Air Conditioner Services", matched)

    def test_storage_and_export(self):
        sample = {
            "tender_id": "TEST_TENDER_001",
            "title": "Cloud ERP Development",
            "tender_ref_no": "REF-001",
            "organisation": "National Informatics Centre",
            "published_date": "12-Sep-2026 10:00 AM",
            "closing_date": "25-Sep-2026 05:00 PM",
            "opening_date": "26-Sep-2026 11:00 AM",
            "corrigendum": "--",
            "tender_url": "https://eprocure.gov.in/test",
            "source": "central",
            "is_it_tender": True,
            "categories": ["Software & Applications", "Cloud & Data Center"],
            "matched_keywords": ["cloud", "erp"],
            "confidence": 0.85,
            "reason": "Keywords: cloud, erp"
        }

        # First insert
        is_new = self.storage.save_tender(sample)
        self.assertTrue(is_new)

        # Duplicate insert should update, not create duplicate
        is_new_again = self.storage.save_tender(sample)
        self.assertFalse(is_new_again)

        tenders = self.storage.get_tenders(only_it=True)
        self.assertEqual(len(tenders), 1)
        self.assertEqual(tenders[0]["tender_id"], "TEST_TENDER_001")

        # Test CSV export
        csv_path = "test_out.csv"
        count = self.storage.export_to_csv(csv_path)
        self.assertEqual(count, 1)
        self.assertTrue(os.path.exists(csv_path))

        # Test JSON export
        json_path = "test_out.json"
        count_json = self.storage.export_to_json(json_path)
        self.assertEqual(count_json, 1)
        self.assertTrue(os.path.exists(json_path))

    def test_refresh_tender_url(self):
        import base64
        import time

        old_ts = 1600000000
        old_b64 = base64.b64encode(str(old_ts).encode("utf-8")).decode("utf-8")
        stale_url = f"https://eprocure.gov.in/cppp/tendersfullview/seg1A13h1seg2A13h1seg3A13h1{old_b64}A13h1seg5A13h1seg6"

        refreshed = EprocureScraper.refresh_tender_url(stale_url)
        self.assertNotEqual(refreshed, stale_url)
        parts = refreshed.split("A13h1")
        self.assertEqual(len(parts), 6)
        self.assertEqual(parts[0], "https://eprocure.gov.in/cppp/tendersfullview/seg1")
        self.assertEqual(parts[1], "seg2")
        self.assertEqual(parts[2], "seg3")
        self.assertEqual(parts[4], "seg5")
        self.assertEqual(parts[5], "seg6")

        # Verify new timestamp
        new_ts_str = base64.b64decode(parts[3]).decode("utf-8")
        self.assertTrue(new_ts_str.isdigit())
        self.assertTrue(abs(time.time() - int(new_ts_str)) < 10)

        # URLs without delimiter should return unchanged
        normal_url = "https://eprocure.gov.in/cppp/latestactivetendersnew/cpppdata"
        self.assertEqual(EprocureScraper.refresh_tender_url(normal_url), normal_url)

    def test_parse_tender_details_html(self):
        import base64

        encoded_doc_url = base64.b64encode(b"https://bpcltenders.eproc.in/tender_docs/doc_123.pdf").decode("utf-8")
        sample_detail_html = f"""
        <html>
        <body>
            <table>
                <tr>
                    <td>Tender Fee in ₹</td><td>:</td><td>1,500</td>
                    <td>EMD Amount in ₹</td><td>:</td><td>50,000</td>
                </tr>
                <tr>
                    <td>Work Description</td><td>:</td><td>Implementation of Enterprise Cloud CRM</td>
                    <td>Location</td><td>:</td><td>New Delhi</td>
                </tr>
                <tr>
                    <td>Tender Type</td><td>:</td><td>Open Tender</td>
                    <td>Tender Category</td><td>:</td><td>Services</td>
                </tr>
                <tr>
                    <td>Product Category</td><td>:</td><td>Information Technology Services</td>
                    <td>Bid Submission End Date</td><td>:</td><td>15-Oct-2026 05:00 PM</td>
                </tr>
                <tr>
                    <td>Name</td><td>:</td><td>Chief Information Officer</td>
                    <td>Address</td><td>:</td><td>CGO Complex, Lodhi Road, New Delhi</td>
                </tr>
                <tr>
                    <td>Tender Document</td><td>:</td><td><a href="/cppp/tenderredirect/by/{encoded_doc_url}">Download Document</a></td>
                </tr>
            </table>
        </body>
        </html>
        """
        scraper = EprocureScraper()
        details = scraper.parse_tender_details_html(sample_detail_html)

        self.assertEqual(details["tender_fee"], "1,500")
        self.assertEqual(details["emd"], "50,000")
        self.assertEqual(details["tender_document_url"], "https://bpcltenders.eproc.in/tender_docs/doc_123.pdf")
        self.assertEqual(details["work_description"], "Implementation of Enterprise Cloud CRM")
        self.assertEqual(details["location"], "New Delhi")
        self.assertEqual(details["tender_type"], "Open Tender")
        self.assertEqual(details["tender_category"], "Services")
        self.assertEqual(details["product_category"], "Information Technology Services")
        self.assertEqual(details["bid_submission_end_date"], "15-Oct-2026 05:00 PM")
        self.assertEqual(details["authority_name"], "Chief Information Officer")
        self.assertEqual(details["authority_address"], "CGO Complex, Lodhi Road, New Delhi")
        self.assertEqual(details["details_fetched"], 1)

    def test_storage_tender_details_enrichment(self):
        sample = {
            "tender_id": "TEST_TENDER_DETAIL_001",
            "title": "Data Center Migration",
            "tender_ref_no": "NIC/DC/2026",
            "organisation": "National Informatics Centre",
            "published_date": "10-Sep-2026 10:00 AM",
            "closing_date": "30-Sep-2026 05:00 PM",
            "opening_date": "01-Oct-2026 11:00 AM",
            "corrigendum": "--",
            "tender_url": "https://eprocure.gov.in/cppp/tendersfullview/test",
            "source": "central",
            "is_it_tender": True,
            "categories": ["Cloud & Data Center"],
            "matched_keywords": ["data center"],
            "confidence": 0.9,
            "reason": "Keywords: data center"
        }
        self.storage.save_tender(sample)

        # Before enrichment: needs_details_only should return 1
        pending = self.storage.get_tenders(needs_details_only=True)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["tender_id"], "TEST_TENDER_DETAIL_001")
        self.assertIsNone(pending[0]["tender_fee"])

        # Enrich details
        details = {
            "tender_fee": "2,000",
            "emd": "1,00,000",
            "tender_document_url": "https://eprocure.gov.in/docs/rfp.pdf",
            "location": "New Delhi",
            "authority_name": "Project Director",
            "authority_address": "NIC HQ, CGO Complex",
            "bid_submission_end_date": "30-Sep-2026 05:00 PM"
        }
        updated = self.storage.update_tender_details("TEST_TENDER_DETAIL_001", details)
        self.assertTrue(updated)

        # After enrichment: needs_details_only should return 0
        pending_after = self.storage.get_tenders(needs_details_only=True)
        self.assertEqual(len(pending_after), 0)

        # Check stored fields
        tenders = self.storage.get_tenders(tender_id="TEST_TENDER_DETAIL_001")
        self.assertEqual(len(tenders), 1)
        t = tenders[0]
        self.assertEqual(t["tender_fee"], "2,000")
        self.assertEqual(t["emd"], "1,00,000")
        self.assertEqual(t["tender_document_url"], "https://eprocure.gov.in/docs/rfp.pdf")
        self.assertEqual(t["location"], "New Delhi")
        self.assertEqual(t["authority_name"], "Project Director")
        self.assertEqual(t["details_fetched"], 1)

        # Check stats
        stats = self.storage.get_stats()
        self.assertEqual(stats["details_fetched"], 1)

    def test_parse_tender_details_error_pages(self):
        scraper = EprocureScraper()

        # Error pages must return None instead of corrupt default zeroes
        self.assertIsNone(scraper.parse_tender_details_html(""), "Empty string must return None")
        self.assertIsNone(scraper.parse_tender_details_html("<h4>Invalid Url.Please Check</h4>"), "Invalid Url must return None")
        self.assertIsNone(scraper.parse_tender_details_html('<table width="100%"><tr><td><h4 align="center">Invalid parameter</h4></td></tr></table>'), "Invalid parameter must return None")
        self.assertIsNone(scraper.parse_tender_details_html("<html><body><p>Some random content</p></body></html>"), "Page without details must return None")

    def test_reset_unpopulated_details(self):
        # Insert a corrupt tender that was falsely marked details_fetched=1 with empty fields
        corrupt_tender = {
            "tender_id": "CORRUPT_001",
            "title": "Corrupt IT Tender",
            "tender_ref_no": "CORRUPT/2026",
            "organisation": "Sample Org",
            "published_date": "10-Sep-2026",
            "closing_date": "30-Sep-2026",
            "opening_date": "01-Oct-2026",
            "tender_url": "https://eprocure.gov.in/cppp/tendersfullview/corrupt",
            "source": "central",
            "is_it_tender": True,
            "tender_fee": "0",
            "emd": "0",
            "tender_document_url": "N/A",
            "work_description": "",
            "location": "",
            "details_fetched": 1
        }
        self.storage.save_tender(corrupt_tender)

        # Insert a legitimately enriched tender
        legit_tender = {
            "tender_id": "LEGIT_001",
            "title": "Legit IT Tender",
            "tender_ref_no": "LEGIT/2026",
            "organisation": "Sample Org",
            "published_date": "10-Sep-2026",
            "closing_date": "30-Sep-2026",
            "opening_date": "01-Oct-2026",
            "tender_url": "https://eprocure.gov.in/cppp/tendersfullview/legit",
            "source": "central",
            "is_it_tender": True,
            "tender_fee": "1,000",
            "emd": "50,000",
            "tender_document_url": "https://eprocure.gov.in/doc.pdf",
            "work_description": "Legitimate work description for IT project",
            "location": "New Delhi",
            "details_fetched": 1
        }
        self.storage.save_tender(legit_tender)

        # Run reset
        reset_count = self.storage.reset_unpopulated_details()
        self.assertEqual(reset_count, 1)

        # Verify corrupt record was reset
        corrupt = self.storage.get_tenders(tender_id="CORRUPT_001")[0]
        self.assertEqual(corrupt["details_fetched"], 0)
        self.assertIsNone(corrupt["tender_fee"])

        # Verify legit record was preserved
        legit = self.storage.get_tenders(tender_id="LEGIT_001")[0]
        self.assertEqual(legit["details_fetched"], 1)
        self.assertEqual(legit["tender_fee"], "1,000")
        self.assertEqual(legit["work_description"], "Legitimate work description for IT project")


if __name__ == "__main__":
    unittest.main()

