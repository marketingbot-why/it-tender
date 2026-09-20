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
            "Hotel/ Catering Services",
            "Computer Software/Web Site",
            "Network /Communication Equipments",
            "Air Conditioner Services",
            "OFC Laying Works"
        ]
        matched = filter_it_categories(test_cats)
        self.assertIn("Info. Tech. Services", matched)
        self.assertIn("Information Technology (IT)", matched)
        self.assertIn("Computer Software/Web Site", matched)
        self.assertIn("Network /Communication Equipments", matched)
        self.assertIn("OFC Laying Works", matched)
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


if __name__ == "__main__":
    unittest.main()
