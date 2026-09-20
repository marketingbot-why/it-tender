"""Scraping engine for eprocure.gov.in CPPP tenders with interactive CAPTCHA & category filtering."""

import os
import re
import math
import time
import base64
import logging
import subprocess
from typing import Generator, Dict, Any, Optional, List, Tuple
import requests
from bs4 import BeautifulSoup

from config import (
    BASE_URL,
    CPPP_CENTRAL_URL,
    CPPP_STATES_URL,
    SOURCES,
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT,
    DEFAULT_DELAY,
    MAX_RETRIES,
    BACKOFF_FACTOR,
    IT_PRODUCT_CATEGORIES,
    GEM_IT_KEYWORDS,
    filter_it_categories,
)
from it_filter import ITFilter, ITClassificationResult

logger = logging.getLogger(__name__)


class EprocureScraper:
    """Scrapes active tenders from eprocure.gov.in (CPPP) with interactive category search and CAPTCHA support."""

    def __init__(
        self,
        delay: float = DEFAULT_DELAY,
        timeout: int = DEFAULT_TIMEOUT,
        custom_keywords: Optional[List[str]] = None,
    ):
        self.delay = delay
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.it_filter = ITFilter(custom_keywords=custom_keywords)
        self._active_sessions = set()

    def ensure_session(self, portal: str = "central") -> bool:
        """
        Ensure the session has established the necessary Drupal session cookie (SSESS...)
        by visiting the corresponding portal listing page.
        """
        if portal in self._active_sessions and any(k.startswith("SSESS") for k in self.session.cookies.keys()):
            return True

        url = CPPP_STATES_URL if portal == "states" else CPPP_CENTRAL_URL
        headers = dict(DEFAULT_HEADERS)
        headers["Referer"] = url
        try:
            resp = self.session.get(url, headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                self._active_sessions.add(portal)
                logger.debug(f"Established portal session for {portal}: {dict(self.session.cookies)}")
                return True
        except Exception as e:
            logger.warning(f"Unable to establish {portal} portal session: {e}")
        return False

    def build_page_url(self, source_url: str, page: int) -> str:
        """Generate base64 obfuscated page URL used by CPPP Drupal views."""
        if page <= 1:
            return source_url

        target_url = f"{source_url}?page={page}"
        token = base64.b64encode(target_url.encode("utf-8")).decode("utf-8")
        return f"{source_url}?url={token}"

    def extract_next_page_url(self, html: str, base_url: str = BASE_URL) -> Optional[str]:
        """Extract the next page URL directly from the pagination controls in the HTML."""
        soup = BeautifulSoup(html, "html.parser")
        pagination = soup.find("div", class_="pagination") or soup.find("ul", class_="pager")
        if pagination:
            for a in pagination.find_all("a"):
                text = a.get_text(strip=True)
                if "Next" in text or "»" in text:
                    href = a.get("href")
                    if href:
                        if href.startswith("/"):
                            return f"{base_url}{href}"
                        return href
        return None

    @staticmethod
    def refresh_tender_url(url: str) -> str:
        """
        Refresh the timestamp nonce in a CPPP detail URL so it never expires.
        CPPP uses 6 base64 segments separated by 'A13h1', where the 4th segment is the unix timestamp.
        """
        if not url or "tendersfullview" not in url or "A13h1" not in url:
            return url
        try:
            prefix, slug = url.rsplit("/", 1)
            parts = slug.split("A13h1")
            if len(parts) >= 4:
                current_ts_b64 = base64.b64encode(str(int(time.time())).encode("utf-8")).decode("utf-8")
                parts[3] = current_ts_b64
                return f"{prefix}/{'A13h1'.join(parts)}"
        except Exception as err:
            logger.debug(f"Unable to refresh timestamp nonce on {url}: {err}")
        return url

    def fetch_page_html(self, url: str) -> Optional[str]:
        """Fetch raw HTML with retry backoff."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code == 200:
                    return response.text
                elif response.status_code in (429, 500, 502, 503, 504):
                    wait = BACKOFF_FACTOR ** attempt
                    logger.warning(f"HTTP {response.status_code} for {url}. Retrying in {wait:.1f}s...")
                    time.sleep(wait)
                else:
                    logger.error(f"HTTP {response.status_code} for {url}. Aborting page fetch.")
                    return None
            except (requests.RequestException, Exception) as err:
                wait = BACKOFF_FACTOR ** attempt
                logger.warning(f"Connection error on attempt {attempt}/{MAX_RETRIES}: {err}. Retrying in {wait:.1f}s...")
                time.sleep(wait)
        return None

    def extract_form_metadata(self, html: str, base_page_url: str) -> Optional[Dict[str, Any]]:
        """
        Extract form hidden inputs, action URL, captcha image URL, and available dropdown categories.
        """
        soup = BeautifulSoup(html, "html.parser")
        form = soup.find("form")
        if not form:
            logger.error("Could not find search form on page.")
            return None

        action = form.get("action", "")
        if action.startswith("/"):
            action_url = f"{BASE_URL}{action}"
        elif action.startswith("http"):
            action_url = action
        else:
            action_url = base_page_url

        form_build_id = ""
        elem_bid = form.find("input", {"name": "form_build_id"})
        if elem_bid:
            form_build_id = elem_bid.get("value", "")

        form_id = ""
        elem_fid = form.find("input", {"name": "form_id"})
        if elem_fid:
            form_id = elem_fid.get("value", "")

        captcha_sid = ""
        elem_csid = form.find("input", {"name": "captcha_sid"})
        if elem_csid:
            captcha_sid = elem_csid.get("value", "")

        captcha_token = ""
        elem_ctok = form.find("input", {"name": "captcha_token"})
        if elem_ctok:
            captcha_token = elem_ctok.get("value", "")

        captcha_img_src = ""
        captcha_img = form.find("img", {"data-drupal-selector": "edit-captcha-image"}) or form.find("img", {"title": "Image CAPTCHA"})
        if captcha_img:
            captcha_img_src = captcha_img.get("src", "")
            if captcha_img_src.startswith("/"):
                captcha_img_src = f"{BASE_URL}{captcha_img_src}"

        # Collect available options in s_prod_type
        prod_options = []
        select_prod = form.find("select", {"name": "s_prod_type"})
        if select_prod:
            for opt in select_prod.find_all("option"):
                val = opt.get("value", "").strip()
                if val and val != "select":
                    prod_options.append(val)

        return {
            "action_url": action_url,
            "form_build_id": form_build_id,
            "form_id": form_id,
            "captcha_sid": captcha_sid,
            "captcha_token": captcha_token,
            "captcha_img_src": captcha_img_src,
            "product_options": prod_options,
        }

    def discover_it_categories(self, source: str = "central") -> List[str]:
        """
        Dynamically fetch the portal search form, parse available product categories,
        and filter for all relevant IT / Tech categories.
        Falls back to IT_PRODUCT_CATEGORIES if portal cannot be reached.
        """
        source_info = SOURCES.get(source)
        if not source_info or source_info.get("type") != "category_dropdown":
            return []

        html = self.fetch_page_html(source_info["url"])
        if html:
            meta = self.extract_form_metadata(html, source_info["url"])
            if meta and meta.get("product_options"):
                matched = filter_it_categories(meta["product_options"])
                if matched:
                    return matched

        return IT_PRODUCT_CATEGORIES

    def download_captcha_image(self, img_url: str, dest_path: str = "captcha.png") -> str:
        """Download real-time CAPTCHA image using the active session."""
        abs_path = os.path.abspath(dest_path)
        res = self.session.get(img_url, timeout=self.timeout)
        res.raise_for_status()
        with open(abs_path, "wb") as f:
            f.write(res.content)
        return abs_path

    def open_image_in_viewer(self, file_path: str):
        """Trigger native image viewer (Preview on macOS)."""
        try:
            subprocess.Popen(["open", file_path])
        except Exception as e:
            logger.debug(f"Unable to launch native viewer: {e}")

    def prompt_captcha_input(self, img_url: str, temp_file: str = "captcha.png") -> Optional[str]:
        """
        Download CAPTCHA, open it in macOS Preview, and prompt user in terminal.
        Returns:
            - string: User entered CAPTCHA
            - None: Refresh requested ('r')
            - '__SKIP__': Skip current category ('s')
            - '__QUIT__': Stop scraping ('q')
        """
        abs_path = self.download_captcha_image(img_url, dest_path=temp_file)
        self.open_image_in_viewer(abs_path)

        print("\n" + "=" * 60)
        print(" [!] CAPTCHA image opened on screen in Preview!")
        print(f" [!] Image file location: file://{abs_path}")
        print(" [!] Controls: Enter code | 'r' refresh | 's' skip category | 'q' quit")
        print("=" * 60)

        user_input = input(" Enter CAPTCHA: ").strip()
        if user_input.lower() in ("r", "refresh"):
            print("[*] Refreshing CAPTCHA...")
            return None
        if user_input.lower() in ("s", "skip"):
            return "__SKIP__"
        if user_input.lower() in ("q", "quit", "exit"):
            return "__QUIT__"
        return user_input

    def submit_category_search(
        self,
        form_meta: Dict[str, Any],
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        captcha_response: str = "",
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Submit the search form via POST with the selected category or keyword and solved CAPTCHA.
        Returns (success, response_html, error_message).
        """
        payload = {
            "s_state": "select",
            "s_short": "published_date",
            "captcha_sid": form_meta["captcha_sid"],
            "captcha_token": form_meta["captcha_token"],
            "captcha_response": captcha_response,
            "op": "Search",
            "form_build_id": form_meta["form_build_id"],
            "form_id": form_meta["form_id"],
        }

        if category is not None:
            payload["s_prod_type"] = category
            payload["s_keyword"] = ""
        elif keyword is not None:
            payload["s_keyword"] = keyword

        action_url = form_meta["action_url"]
        logger.debug(f"Submitting POST to {action_url} with category='{category}' keyword='{keyword}'")

        res = self.session.post(action_url, data=payload, timeout=self.timeout)
        html = res.text

        # Detect CAPTCHA error
        if "CAPTCHA was not correct" in html or "messages error" in html:
            soup = BeautifulSoup(html, "html.parser")
            err_box = soup.find("div", {"class": "messages error"}) or soup.find("div", {"class": "alert-danger"})
            err_text = err_box.get_text(strip=True) if err_box else "Incorrect CAPTCHA code entered."
            return False, html, err_text

        return True, html, None

    def parse_tender_details_html(self, html: str) -> Optional[Dict[str, Any]]:
        """
        Parse structured tender details (Tender Fee, EMD, Document URL, Work Description,
        Critical Dates, Authority info) from CPPP or GeM fullview HTML.
        Returns None if no details tables or valid tender metadata were found.
        """
        if not html:
            return None

        # Check for immediate failure markers
        if "Invalid parameter" in html or "Invalid Url" in html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        raw_pairs = {}
        doc_links = []

        # Parse all table rows for key-value pairs and document links
        for tr in soup.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if not cells:
                continue

            # Look for document/attachment links in row
            for a in tr.find_all("a"):
                href = a.get("href", "").strip()
                text = a.get_text(strip=True)
                if href and not href.startswith("javascript:"):
                    resolved_href = href
                    if "/cppp/tenderredirect/by/" in href:
                        token = href.split("/cppp/tenderredirect/by/")[-1].strip()
                        try:
                            resolved_href = base64.b64decode(token).decode("utf-8", errors="ignore")
                        except Exception:
                            pass
                    doc_links.append({"text": text, "url": resolved_href})

            i = 0
            while i < len(cells):
                # Pattern: [Key, ':', Value] or [Key1, ':', Val1, Key2, ':', Val2]
                if i + 2 < len(cells) and cells[i+1].get_text(strip=True) == ":":
                    k = cells[i].get_text(strip=True).rstrip("*").strip()
                    v = cells[i+2].get_text(strip=True)
                    link = cells[i+2].find("a")
                    if link and link.get("href"):
                        raw_pairs[k + "_link"] = link.get("href")
                    raw_pairs[k] = v
                    i += 3
                elif i + 1 < len(cells):
                    # Pattern: [Key, Value]
                    k = cells[i].get_text(strip=True).rstrip(":").rstrip("*").strip()
                    v = cells[i+1].get_text(strip=True)
                    link = cells[i+1].find("a")
                    if link and link.get("href"):
                        raw_pairs[k + "_link"] = link.get("href")
                    raw_pairs[k] = v
                    i += 2
                else:
                    i += 1

        # Extract and resolve tender document URL
        tender_doc_url = None
        doc_val = raw_pairs.get("Tender Document_link") or raw_pairs.get("Bid Document_link")
        if doc_val:
            if "/cppp/tenderredirect/by/" in doc_val:
                token = doc_val.split("/cppp/tenderredirect/by/")[-1].strip()
                try:
                    tender_doc_url = base64.b64decode(token).decode("utf-8", errors="ignore")
                except Exception:
                    tender_doc_url = doc_val
            else:
                tender_doc_url = doc_val
        elif raw_pairs.get("Tender Document"):
            tender_doc_url = raw_pairs.get("Tender Document")
        elif raw_pairs.get("Bid Document"):
            tender_doc_url = raw_pairs.get("Bid Document")

        if not tender_doc_url and doc_links:
            for dl in doc_links:
                u = dl["url"]
                if any(ext in u.lower() for ext in [".pdf", ".zip", ".xls", "doc_cppp", "eproc", "tender", "redirect", "bidplus"]):
                    tender_doc_url = u
                    break

        # If no key-value pairs and no doc links were found, it's not a detail page
        if not raw_pairs and not doc_links:
            return None

        # Ensure at least one substantive field was captured
        substantive_keys = [
            "Tender Fee", "Tender Fee in ₹", "EMD", "EMD Amount in ₹",
            "Work Description", "Tender Title", "Product Category",
            "Name", "Buyer Name", "Organisation Name", "Location", "Pin Code"
        ]
        if not any(k in raw_pairs for k in substantive_keys) and not tender_doc_url:
            return None

        work_desc = (
            raw_pairs.get("Work Description")
            or raw_pairs.get("Tender Title")
            or raw_pairs.get("Product Category")
            or ""
        )

        return {
            "tender_fee": raw_pairs.get("Tender Fee") or raw_pairs.get("Tender Fee in ₹") or "0",
            "emd": raw_pairs.get("EMD") or raw_pairs.get("EMD Amount in ₹") or "0",
            "tender_document_url": tender_doc_url or "N/A",
            "work_description": work_desc,
            "location": raw_pairs.get("Location") or raw_pairs.get("Pin Code") or "",
            "tender_type": raw_pairs.get("Tender Type") or "",
            "tender_category": raw_pairs.get("Tender Category") or "",
            "product_category": raw_pairs.get("Product Category") or "",
            "doc_download_start_date": raw_pairs.get("Document Download Start Date") or "",
            "doc_download_end_date": raw_pairs.get("Document Download End Date") or "",
            "bid_submission_start_date": raw_pairs.get("Bid Submission Start Date") or raw_pairs.get("Bid Start Date") or "",
            "bid_submission_end_date": raw_pairs.get("Bid Submission End Date") or raw_pairs.get("Bid End Date") or "",
            "bid_opening_date": raw_pairs.get("Bid Opening Date") or "",
            "authority_name": raw_pairs.get("Name") or raw_pairs.get("Buyer Name") or "",
            "authority_address": raw_pairs.get("Address") or "",
            "details_fetched": 1,
        }

    def fetch_tender_details_interactively(
        self,
        tender_url: str,
        tender_id: str = "",
        tender_title: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch and parse full tender details from CPPP or GeM.
        Prompts for CAPTCHA if needed (Central/State), or fetches directly without CAPTCHA (GeM).
        Returns None on skip or failure, raises KeyboardInterrupt on quit.
        """
        if not tender_url:
            return None

        disp_title = (tender_title[:65] + "...") if len(tender_title) > 65 else tender_title
        print(f"\n---> Fetching Details for Tender ID: {tender_id}")
        if disp_title:
            print(f"     Title: {disp_title}")

        # Case A: GeM Bid details - no CAPTCHA needed
        if "gemtendersfullview" in tender_url:
            logger.debug(f"Fetching GeM details directly: {tender_url}")
            resp = self.fetch_page_html(tender_url)
            if resp:
                details = self.parse_tender_details_html(resp)
                if details:
                    print("[✓] GeM Bid details successfully retrieved.")
                    return details
            print(f"  [!] Unable to load GeM bid details for {tender_id}.")
            return None

        # Case B: Central / State tender details - requires solving CAPTCHA
        portal = "states" if "tendersfullviewmmp" in tender_url else "central"
        self.ensure_session(portal)

        portal_referer = CPPP_STATES_URL if portal == "states" else CPPP_CENTRAL_URL
        refreshed_url = self.refresh_tender_url(tender_url)

        headers = dict(DEFAULT_HEADERS)
        headers["Referer"] = portal_referer

        while True:
            resp = self.session.get(refreshed_url, headers=headers, timeout=self.timeout)
            if resp.status_code != 200:
                logger.error(f"HTTP {resp.status_code} loading tender detail: {refreshed_url}")
                return None

            # Check if CPPP rejected refreshed URL (e.g. Invalid Url)
            if "Invalid Url" in resp.text:
                logger.debug(f"Refreshed URL returned Invalid Url. Trying original URL: {tender_url}")
                resp_orig = self.session.get(tender_url, headers=headers, timeout=self.timeout)
                if "Invalid Url" not in resp_orig.text and ("form" in resp_orig.text or "Tender Details" in resp_orig.text):
                    resp = resp_orig
                    refreshed_url = tender_url
                else:
                    print(f"  [!] Tender {tender_id} detail page is no longer active on CPPP (tender may be closed/archived).")
                    return None

            soup = BeautifulSoup(resp.text, "html.parser")
            form = soup.find("form")
            if not form:
                # If detail tables already exist without form, parse directly
                if any(m in resp.text for m in ["Organisation Details", "Tender Details", "Critical Dates", "Work Details"]):
                    parsed = self.parse_tender_details_html(resp.text)
                    if parsed:
                        print("[✓] Details successfully retrieved directly.")
                        return parsed
                print(f"  [!] No detail form found on page for {tender_id}.")
                return None

            captcha_input = form.find("input", {"name": "captcha_response"})
            if not captcha_input:
                # Rendered directly without captcha
                parsed = self.parse_tender_details_html(resp.text)
                if parsed:
                    print("[✓] Details successfully retrieved directly.")
                    return parsed
                print(f"  [!] Tender form without CAPTCHA contained no detail data for {tender_id}.")
                return None

            form_inputs = {i.get("name"): i.get("value", "") for i in form.find_all("input") if i.get("name")}
            img = form.find("img")
            if not img or not img.get("src"):
                logger.error("No CAPTCHA image found on tender page.")
                return None

            img_src = img["src"]
            if img_src.startswith("/"):
                img_src = f"{BASE_URL}{img_src}"

            captcha_val = self.prompt_captcha_input(img_src, temp_file="detail_captcha.png")
            if not captcha_val:
                # Refresh
                refreshed_url = self.refresh_tender_url(tender_url)
                continue

            if captcha_val == "__SKIP__":
                print(f"[*] Skipping detail extraction for {tender_id}.")
                return None

            if captcha_val == "__QUIT__":
                print("[*] Quitting detail extraction as requested.")
                raise KeyboardInterrupt

            action = form.get("action", "")
            action_url = f"{BASE_URL}{action}" if action.startswith("/") else (action or refreshed_url)
            payload = dict(form_inputs)
            payload["captcha_response"] = captcha_val
            payload["op"] = "Submit"

            post_headers = dict(headers)
            post_headers["Referer"] = refreshed_url

            post_resp = self.session.post(action_url, data=payload, headers=post_headers, timeout=self.timeout)

            # Check 1: Incorrect CAPTCHA code
            if "CAPTCHA was not correct" in post_resp.text or "messages error" in post_resp.text:
                print("[!] Incorrect CAPTCHA code entered. Retrying with fresh code...")
                refreshed_url = self.refresh_tender_url(tender_url)
                continue

            # Check 2: Invalid parameter or URL error
            if "Invalid parameter" in post_resp.text or "Invalid Url" in post_resp.text:
                print("[!] CPPP rejected request (Invalid parameter/URL). Re-establishing session and retrying...")
                self._active_sessions.discard(portal)
                self.ensure_session(portal)
                refreshed_url = self.refresh_tender_url(tender_url)
                continue

            # Check 3: Form was re-rendered (still asking for CAPTCHA)
            if '<input name="captcha_response"' in post_resp.text:
                print("[!] Server re-rendered CAPTCHA form. Retrying...")
                refreshed_url = self.refresh_tender_url(tender_url)
                continue

            # Check 4: Must contain actual detail markers
            if not any(m in post_resp.text for m in ["Organisation Details", "Tender Details", "Critical Dates", "Work Details"]):
                print(f"  [!] Detail tables not found in server response for {tender_id}.")
                return None

            details = self.parse_tender_details_html(post_resp.text)
            if not details:
                print(f"  [!] Failed to parse detail tables for {tender_id}.")
                return None

            print("[✓] CAPTCHA accepted! Details successfully retrieved.")
            return details

    def extract_total_tenders(self, html: str) -> int:
        """Parse total tenders or bids count displayed on CPPP."""
        match = re.search(r"Total\s+(?:Tenders|Bid\(s\))\s*:\s*(\d+)", html, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 0

    def parse_table_rows(self, html: str, source_key: str, search_category: str = "") -> List[Dict[str, Any]]:
        """
        Parse structured tender/bid entries from the HTML table.
        Supports standard Central/State tables and GeM bids tables.
        """
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", {"id": "table"}) or soup.find("table", {"class": "list_table"})
        if not table:
            return []

        rows = table.find_all("tr")
        tenders = []

        is_gem = source_key == "gem" or "Bid Number" in (table.find("thead").get_text() if table.find("thead") else "")

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 6:
                continue

            sl_no = cells[0].get_text(strip=True)
            if not sl_no or not any(char.isdigit() for char in sl_no):
                continue

            if is_gem:
                # GeM Table layout:
                # Cell 0: Sl.No
                # Cell 1: Bid Start Date
                # Cell 2: Bid End Date
                # Cell 3: Bid Number / Total Quantity (contains <a>)
                # Cell 4: Product Category (Item Description)
                # Cell 5: Organisation Name
                # Cell 6: Department Name
                pub_date = cells[1].get_text(strip=True)
                close_date = cells[2].get_text(strip=True)
                open_date = "--"

                cell3 = cells[3]
                link = cell3.find("a")
                bid_text = cell3.get_text(strip=True)
                tender_url = link.get("href", "") if link else ""
                if tender_url.startswith("/"):
                    tender_url = f"{BASE_URL}{tender_url}"

                parts = bid_text.split("/")
                tender_id = parts[0].strip() if parts else bid_text
                tender_ref_no = tender_id

                # Product Category is the item description/title in GeM
                title = cells[4].get_text(strip=True)
                org = cells[5].get_text(strip=True)
                dept = cells[6].get_text(strip=True) if len(cells) > 6 else ""
                organisation = f"{org} ({dept})" if org != "N/A" and dept else (dept or org)
                corrigendum = "--"

            else:
                # Standard Central/State Table layout:
                # Cell 0: Sl.No
                # Cell 1: Published Date
                # Cell 2: Closing Date
                # Cell 3: Opening Date
                # Cell 4: Title / Ref No / Tender ID
                # Cell 5: Organisation / State Name
                # Cell 6: Corrigendum
                pub_date = cells[1].get_text(strip=True)
                close_date = cells[2].get_text(strip=True)
                open_date = cells[3].get_text(strip=True)

                cell4 = cells[4]
                link = cell4.find("a")
                if link:
                    title = link.get_text(strip=True)
                    tender_url = link.get("href", "")
                    if tender_url.startswith("/"):
                        tender_url = f"{BASE_URL}{tender_url}"
                else:
                    title = cell4.get_text(strip=True)
                    tender_url = ""

                cell4_text = cell4.get_text(strip=True)
                remainder = cell4_text[len(title):].strip().lstrip("/")
                tender_ref_no = ""
                tender_id = ""

                if "/" in remainder:
                    parts = remainder.rsplit("/", 1)
                    tender_ref_no = parts[0].strip()
                    tender_id = parts[1].strip()
                elif remainder:
                    tender_id = remainder.strip()
                else:
                    match_id = re.search(r"(202\d_[A-Z0-9]+_\d+_\d+)", tender_url)
                    tender_id = match_id.group(1) if match_id else f"TENDER_{hash(title)}"

                organisation = cells[5].get_text(strip=True)
                corrigendum = cells[6].get_text(strip=True) if len(cells) > 6 else "--"

            tender_dict = {
                "sl_no": sl_no,
                "title": title,
                "tender_id": tender_id,
                "tender_ref_no": tender_ref_no,
                "organisation": organisation,
                "published_date": pub_date,
                "closing_date": close_date,
                "opening_date": open_date,
                "corrigendum": corrigendum,
                "tender_url": tender_url,
                "source": source_key,
                "search_category": search_category,
            }

            # Augment with IT classification
            classification = self.it_filter.classify(tender_dict)
            if search_category:
                # If explicitly retrieved from an IT product category search, mark as IT
                tender_dict["is_it_tender"] = True
                cats = classification.categories
                if search_category not in cats:
                    cats.append(search_category)
                tender_dict["categories"] = cats
                tender_dict["matched_keywords"] = classification.matched_keywords
                tender_dict["confidence"] = max(0.95, classification.confidence)
                tender_dict["reason"] = f"Product Category: {search_category}; {classification.reason}"
            else:
                tender_dict["is_it_tender"] = classification.is_it_tender
                tender_dict["categories"] = classification.categories
                tender_dict["matched_keywords"] = classification.matched_keywords
                tender_dict["confidence"] = classification.confidence
                tender_dict["reason"] = classification.reason

            tenders.append(tender_dict)

        return tenders

    def scrape_category_interactively(
        self,
        source: str = "central",
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        max_pages: Optional[int] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Interactively search by Product Category (or keyword for GeM), prompting for CAPTCHA,
        and yield all resulting tenders across pages.
        """
        source_info = SOURCES.get(source)
        if not source_info:
            raise ValueError(f"Unknown source '{source}'. Available: {list(SOURCES.keys())}")

        source_url = source_info["url"]
        label = category or keyword or "All IT"
        print(f"\n[*] Initiating search for '{label}' on {source_info['name']}...")

        # Step 1: Fetch form and solve CAPTCHA
        form_html = None
        form_meta = None
        solved_html = None

        while True:
            # Fetch fresh form if needed
            if not form_html:
                form_html = self.fetch_page_html(source_url)
                if not form_html:
                    logger.error("Failed to load search form.")
                    return

            form_meta = self.extract_form_metadata(form_html, source_url)
            if not form_meta or not form_meta.get("captcha_img_src"):
                logger.error("Failed to parse CAPTCHA image details.")
                return

            # Display CAPTCHA and get user solution
            captcha_val = self.prompt_captcha_input(form_meta["captcha_img_src"])
            if not captcha_val:
                # User typed 'r' to refresh
                form_html = None
                continue

            if captcha_val == "__SKIP__":
                print(f"[*] Skipping category: '{label}' as requested.")
                return

            if captcha_val == "__QUIT__":
                print("[*] Stopping category loop as requested.")
                raise KeyboardInterrupt

            # Submit the form
            success, resp_html, err_msg = self.submit_category_search(
                form_meta=form_meta,
                category=category,
                keyword=keyword,
                captcha_response=captcha_val,
            )

            if success:
                print(f"[✓] CAPTCHA accepted! Search query successfully executed.")
                solved_html = resp_html
                break
            else:
                print(f"[!] {err_msg or 'CAPTCHA validation failed.'} Retrying with a new CAPTCHA...")
                form_html = resp_html

        # Step 2: Extract results & follow pagination
        total_found = self.extract_total_tenders(solved_html)
        total_pages = math.ceil(total_found / 10) if total_found > 0 else 1
        print(f"[*] Found {total_found:,} matching tenders across {total_pages:,} page(s).")

        limit_pages = min(max_pages, total_pages) if max_pages else total_pages

        current_html = solved_html
        for page in range(1, limit_pages + 1):
            if page > 1:
                next_url = self.extract_next_page_url(current_html)
                if not next_url:
                    next_url = self.build_page_url(source_url, page)
                logger.debug(f"Fetching filtered page {page}/{limit_pages}: {next_url}")
                current_html = self.fetch_page_html(next_url)
                if not current_html:
                    logger.warning(f"Could not load page {page}. Skipping...")
                    break

            page_tenders = self.parse_table_rows(current_html, source_key=source, search_category=label)
            for tender in page_tenders:
                yield tender

            if self.delay > 0 and page < limit_pages:
                time.sleep(self.delay)

    def scrape_tenders(
        self,
        source: str = "central",
        max_pages: Optional[int] = None,
        only_it: bool = True,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Legacy/Direct stream across open pagination without CAPTCHA.
        """
        source_info = SOURCES.get(source)
        if not source_info:
            raise ValueError(f"Unknown source '{source}'. Available: {list(SOURCES.keys())}")

        source_url = source_info["url"]
        page1_html = self.fetch_page_html(source_url)
        if not page1_html:
            return

        total_tenders = self.extract_total_tenders(page1_html)
        total_pages = math.ceil(total_tenders / 10) if total_tenders > 0 else 1
        limit_pages = min(max_pages, total_pages) if max_pages else total_pages

        current_html = page1_html
        for page in range(1, limit_pages + 1):
            if page > 1:
                next_url = self.extract_next_page_url(current_html)
                if not next_url:
                    next_url = self.build_page_url(source_url, page)
                current_html = self.fetch_page_html(next_url)
                if not current_html:
                    break

            raw_tenders = self.parse_table_rows(current_html, source_key=source)
            for tender in raw_tenders:
                if only_it and not tender.get("is_it_tender"):
                    continue
                yield tender

            if self.delay > 0 and page < limit_pages:
                time.sleep(self.delay)
