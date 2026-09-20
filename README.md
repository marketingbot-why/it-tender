# Government IT Tender Scraper (eprocure.gov.in / CPPP)

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Portal](https://img.shields.io/badge/source-eprocure.gov.in-orange.svg)](https://eprocure.gov.in/cppp/)
[![Storage](https://img.shields.io/badge/storage-SQLite%20%2B%20CSV%20%2B%20JSON-blueviolet.svg)](tenders.db)

An enterprise-ready, automated web scraper engineered to discover, filter, categorize, deduplicate, and export all **Information Technology (IT) tenders** published on the Government of India's Central Public Procurement Portal ([eprocure.gov.in / CPPP](https://eprocure.gov.in/cppp/)).

The scraper covers **Central Government Ministries & PSUs**, **State Government Portals (MMP)**, and **GeM (Government e-Marketplace) bids**, featuring **zero-argument automatic category discovery**, an **interactive macOS Preview CAPTCHA solver**, and an **NLP/rule-based IT sub-domain classifier** with civil works false-positive guards.

---

## Table of Contents

- [Overview & Architecture](#overview--architecture)
- [Key Features](#key-features)
- [Portal Sources Covered](#portal-sources-covered)
- [Installation & Prerequisites](#installation--prerequisites)
- [Quickstart (Zero-Argument Run)](#quickstart-zero-argument-run)
- [Operational Scraping Modes](#operational-scraping-modes)
  - [1. Automatic IT Category Discovery (Default)](#1-automatic-it-category-discovery-default)
  - [2. Interactive CAPTCHA Solver Workflow](#2-interactive-captcha-solver-workflow)
  - [3. Deep Detail Extraction (Fee, EMD & Documents)](#3-deep-detail-extraction-fee-emd--documents)
  - [4. State Government Tenders](#4-state-government-tenders)
  - [5. GeM Active Bids (Direct Detail Extraction)](#5-gem-active-bids-direct-detail-extraction)
  - [6. Single Category Override](#6-single-category-override)
  - [7. High-Throughput Open Feed (No CAPTCHA)](#7-high-throughput-open-feed-no-captcha)
- [Automatic URL Revival Mechanism](#automatic-url-revival-mechanism)
- [IT Domain Classifier & Taxonomies](#it-domain-classifier--taxonomies)
- [Database Schema & Data Fields](#database-schema--data-fields)
- [Command-Line Options Reference](#command-line-options-reference)
- [Automated Daily Scheduling (Cron)](#automated-daily-scheduling-cron)
- [Automated Test Suite](#automated-test-suite)
- [Project Directory Structure](#project-directory-structure)
- [Troubleshooting & FAQs](#troubleshooting--faqs)

---

## Overview & Architecture

`eprocure.gov.in` (CPPP) publishes tens of thousands of tenders daily. Identifying technology contracts requires traversing complex Drupal forms, multi-field search dropdowns, real-time CAPTCHAs, and base64-encoded pagination tokens.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       eprocure.gov.in / CPPP                                │
│   ┌──────────────────────┐  ┌─────────────────────┐  ┌──────────────────┐   │
│   │ Central (/cpppdata)  │  │ States (/mmpdata)   │  │ GeM (/gemtender) │   │
│   └──────────┬───────────┘  └──────────┬──────────┘  └────────┬─────────┘   │
└──────────────┼─────────────────────────┼──────────────────────┼─────────────┘
               │                         │                      │
               ▼                         ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. Dynamic Discovery: Inspects portal form & auto-filters 12+ IT categories │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. Interactive CAPTCHA: Downloads session image & opens in macOS Preview    │
│    User enters code in CLI ('r' = refresh, 's' = skip, 'q' = quit)          │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. Form Submission & Adaptive Pagination:                                   │
│    Maintains session cookies; parses <div class="pagination"> & base64 URLs │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. IT Domain Classifier & False-Positive Guard (it_filter.py):              │
│    - Classifies into 6 IT sub-domains (Software, Cloud, Network, etc.)      │
│    - Weeds out Civil / Road / Catering tenders (e.g. "cc road", "nirman")   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. Storage & Deduplication (storage.py):                                    │
│    - SQLite DB (tenders.db) with PRIMARY KEY (tender_id)                    │
│    - Formatted Export to CSV (it_tenders.csv) and JSON (it_tenders.json)    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

1. **Zero-Configuration Automatic Category Discovery**:
   - Automatically inspects the portal's `<select name="s_prod_type">` dropdown (180+ options).
   - Isolates all IT, Tech, Software, Hardware, Networking, and Digitization categories via pattern matching.
   - Runs every matching category sequentially without requiring manual input in command arguments.

2. **Native macOS Preview CAPTCHA Solver**:
   - Automatically downloads the session-bound CAPTCHA image.
   - Launches macOS **Preview** immediately via `open`.
   - Prompts in the terminal with controls: code entry, `'r'` to refresh, `'s'` to skip category, `'q'` to gracefully stop.
   - Retains the Drupal PHP session across subsequent paginated search results.

3. **Dual Scraping Modes**:
   - **Category Mode (`--mode category`, default)**: Targeted search forms filtered by Product Category with CAPTCHA verification.
   - **Listing Mode (`--mode listing`)**: Streams open live feeds across thousands of pages without CAPTCHAs.

4. **Multi-Domain IT Classification & False-Positive Elimination**:
   - Categorizes each tender into 6 discrete domains: Software, Hardware, Cloud/Hosting, Networking/Cybersecurity, IT Services/AMC, and Digitization.
   - Rejects non-IT tenders that incidentally mention technology terms (e.g., civil road repairs, catering, coal mining).

5. **Deep Tender Detail Extraction (Fee, EMD, Documents & Authority)**:
   - Traverses into individual tender pages to extract **Tender Fee in ₹**, **EMD Amount in ₹**, **Tender Document Download URLs**, **Work Description**, **Location**, **Critical Dates**, and **Tender Inviting Authority Name & Address**.
   - Resolves base64 `/cppp/tenderredirect/by/<token>` URLs to direct external e-procurement RFP / BOQ PDFs.
   - Fully automated for GeM bids without CAPTCHAs; interactive single-CAPTCHA per tender for Central and State portals.

6. **Automatic URL Revival Engine**:
   - Overcomes CPPP's short-lived URL expiry (`Invalid Url.Please Check`) by dynamically regenerating the 4th base64 timestamp nonce, allowing old and stored URLs to be enriched anytime.

7. **Deduplication & Multi-Format Storage**:
   - Stores tenders in SQLite with `tender_id` as the primary key. Re-running the scraper updates and enriches existing records (`ON CONFLICT DO UPDATE`).
   - Exports cleanly to CSV and JSON formats with all financial, date, and document columns.

## Portal Sources Covered

| Source Key | Portal Repository | Portal URL | Type | Approx. Active Records |
|---|---|---|---|---|
| `central` | Central Government Ministries, Departments & PSUs | `/cppp/latestactivetendersnew/cpppdata` | Category Dropdown (`s_prod_type`) | ~28,000+ tenders |
| `states` | State Government Portals (MMP) | `/cppp/latestactivetendersnew/mmpdata` | Category Dropdown (`s_prod_type`) | ~68,000+ tenders |
| `gem` | GeM (Government e-Marketplace) on CPPP | `/cppp/gemtender` | Multi-Field Keyword (`s_keyword`) | ~33,000+ bids |
| `all` | Combined Repositories | All of the above sequentially | Mixed | ~129,000+ bids |

---

## Installation & Prerequisites

### Prerequisites
- macOS, Linux, or Windows (macOS recommended for automatic Preview image display)
- Python 3.8 or higher
- pip package manager

### Setup Steps

1. **Clone or navigate to the repository**:
   ```bash
   cd /Users/deeps/mywork/tenders/it-tender
   ```

2. **(Optional) Create and activate a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   *Dependencies: `requests>=2.28.0`, `beautifulsoup4>=4.11.0`, `urllib3>=1.26.0`.*

---

## Quickstart (Zero-Argument Run)

To start scraping Central Government IT tenders immediately, simply run:

```bash
python3 cli.py
```

### What Happens Automatically:
1. Connects to `eprocure.gov.in` and queries the category dropdown.
2. Identifies all 8 IT product categories:
   - `Computer Data Processing`
   - `Computer Software/Web Site`
   - `Information Technology (IT)`
   - `Info. Tech. Services`
   - `IT`
   - `IT - All`
   - `IT Services`
   - `Scanning, Digitisation Services`
3. Begins with Category 1 (`Computer Data Processing`), downloads the CAPTCHA, and opens it on your screen in macOS Preview.
4. Pauses for you to type the characters shown in the terminal.
5. Once submitted, streams all matching tenders into `it_tenders.csv` and `tenders.db`.
6. Automatically advances to Category 2, downloads a fresh CAPTCHA, and continues sequentially!

---

## Operational Scraping Modes

### 1. Automatic IT Category Discovery (Default)
Scrapes all discovered IT product categories across Central Government portals:
```bash
python3 cli.py --source central --pages 20
```

### 2. Interactive CAPTCHA Solver Workflow
When running in category mode, the terminal displays:

```text
============================================================
 [!] CAPTCHA image opened on screen in Preview!
 [!] Image file location: file:///path/to/captcha.png
 [!] Controls: Enter code | 'r' refresh | 's' skip category | 'q' quit
============================================================
 Enter CAPTCHA: 
```

**Terminal Controls**:
- `<characters>`: Solves the CAPTCHA and begins scraping.
- `r` or `refresh`: Fetches a fresh CAPTCHA image if the current one is unreadable.
- `s` or `skip`: Skips the current category and proceeds to the next category in the queue.
- `q` or `quit`: Gracefully stops the scraper, writes all collected data to CSV/JSON, and exits.

### 3. Deep Detail Extraction (Fee, EMD & Documents)

To extract financial requirements (Tender Fee, EMD), official RFP / BOQ document download links, location, and inviting authority contact info:

#### A. Enrich Existing Saved Database Records (`--fetch-details`)
If you already have tenders stored in `tenders.db` and want to enrich them with full financial and document details:
```bash
# Enrich the first 5 tenders that need details
python3 cli.py --fetch-details --limit 5

# Enrich all pending IT tenders in the database
python3 cli.py --fetch-details

# Enrich a specific tender by its ID
python3 cli.py --fetch-details --tender-id "2026_TCIL_290724_1"
```
During enrichment:
- Each tender's CAPTCHA is automatically downloaded and displayed in macOS Preview.
- Enter the code in the terminal (or `'s'` to skip, `'r'` to refresh, `'q'` to quit).
- Tenders are immediately updated in SQLite and re-exported to CSV/JSON.

#### B. Live Detail Extraction During Scraping (`--details`)
To scrape categories and immediately prompt for details on each matching IT tender:
```bash
python3 cli.py --mode category --source central --category "Info. Tech. Services" --pages 1 --details
```

### 4. State Government Tenders
Search all IT categories across state government portals (MMP data):
```bash
python3 cli.py --source states --output state_it_tenders.csv
```

### 5. GeM Active Bids (Direct Detail Extraction)
GeM on CPPP uses keyword search (`s_keyword`). Running GeM mode automatically iterates through all IT keywords (`Information Technology`, `IT Services`, `Computer Software`):
```bash
python3 cli.py --source gem --output gem_it_bids.csv
```
> [!TIP]
> **No CAPTCHA on GeM Details**: GeM tender detail pages (`/cppp/gemtendersfullview/...`) do **not** require a CAPTCHA. Running with `--details` on GeM automatically fetches bid document links (`bidplus.gem.gov.in/doc_cppp/...`) with zero user interruption!

### 6. Single Category Override
If you want to target only one specific category rather than iterating through all of them:
```bash
python3 cli.py --source central --category "Info. Tech. Services" --pages 20
```

### 7. High-Throughput Open Feed (No CAPTCHA)
If you need an unattended, high-speed scraper that runs without manual CAPTCHA solving, use `--mode listing`. This mode streams live active listings directly from CPPP's public views:
```bash
python3 cli.py --mode listing --source central --pages 50 --output direct_it_tenders.csv
```

---

## Automatic URL Revival Mechanism

CPPP secures individual tender fullview URLs using a multi-segment base64 token structure:
```text
https://eprocure.gov.in/cppp/tendersfullview/<seg1>A13h1<seg2>A13h1<seg3>A13h1<seg4>A13h1<seg5>A13h1<seg6>
```

When accessed after a few minutes, stale URLs produce:
```html
<h4>Invalid Url.Please Check</h4>
```

### How the Scraper Solves This:
Through reverse engineering of the portal token layout:
1. Segments are separated by the internal delimiter `A13h1`.
2. Segment 4 is `base64(unix_timestamp)`.
3. The server checks whether `current_time - segment_4 <= token_ttl`.
4. The scraper's `EprocureScraper.refresh_tender_url(url)` dynamically decodes segment 4, re-encodes `int(time.time())` in base64, and reconstructs the URL before issuing the HTTP request.
5. Result: **Any saved or historical CPPP tender URL can be revived and loaded on demand at any time.**

---

## IT Domain Classifier & Taxonomies

Every scraped tender is analyzed by the rule-based NLP engine in [`it_filter.py`](file:///Users/deeps/mywork/tenders/it-tender/it_filter.py) and mapped into 6 distinct sub-domains:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         IT Classification Taxonomies                        │
├──────────────────────────┬──────────────────────────────────────────────────┤
│ Sub-Domain               │ Covered Areas & Keywords                         │
├──────────────────────────┼──────────────────────────────────────────────────┤
│ Software & Applications  │ ERP, CRM, Web Portals, Mobile Apps (iOS/Android) │
│                          │ Custom Software, AI / ML, APIs, Full-Stack       │
├──────────────────────────┼──────────────────────────────────────────────────┤
│ Cloud & Data Center      │ Cloud Hosting, MeghRaj, AWS, Azure, GCP, PaaS    │
│                          │ IaaS, SaaS, Data Center Migration, DR Sites      │
├──────────────────────────┼──────────────────────────────────────────────────┤
│ Networking & Security    │ Next-Gen Firewalls, SIEM, Routers, LAN / WAN     │
│                          │ Structured Cabling, SOC, CCTV Surveillance       │
├──────────────────────────┼──────────────────────────────────────────────────┤
│ Hardware & Computing     │ Enterprise Servers, SAN / NAS Storage, Laptops   │
│                          │ Desktops, Interactive Flat Panels, Workstations  │
├──────────────────────────┼──────────────────────────────────────────────────┤
│ IT Services & Consulting │ IT AMC, Facility Management (FMS), IT Staffing   │
│                          │ System Integration, Helpdesk Support, SLA        │
├──────────────────────────┼──────────────────────────────────────────────────┤
│ Digitization & Data      │ Scanning, Indexing, OCR, DMS, Document Archive   │
│                          │ Data Entry, Smart Cards, Biometric Systems       │
└──────────────────────────┴──────────────────────────────────────────────────┘
```

### False-Positive Filtering
Government portals frequently publish civil or non-IT tenders that contain incidental words (e.g., "computer room painting", "interlocking road ke paas", "catering service for IT dept"). 

The classifier implements rigorous guards:
- **Hindi civil terminology**: Excludes `cc road`, `naali nirman`, `nirman karya`, `interlocking`, `sadak`, `mitti karya`.
- **Word boundary checks**: Distinguishes cloud `PaaS` from Hindi phrase `ke paas` (near) via case-sensitive regex `\b(PaaS|IaaS|SaaS)\b`.
- **Acronym disambiguation**: Disambiguates `CMS` (Chief Medical Services vs Content Management System) and `DMS` based on organizational context.

---

## Database Schema & Data Fields

Tenders are persisted in an **SQLite 3** database ([`tenders.db`](file:///Users/deeps/mywork/tenders/it-tender/tenders.db)). 

### Table Schema: `tenders`

| Column | Type | Description |
|---|---|---|
| `tender_id` | `TEXT PRIMARY KEY` | Unique CPPP or GeM identifier (e.g. `2026_CPPP_123456_1` or `GEM/2026/B/101`) |
| `tender_ref_no` | `TEXT` | Official reference number published by the procuring agency |
| `title` | `TEXT` | Title, subject of work, or item description |
| `organisation` | `TEXT` | Department, Ministry, PSU, or Municipal Corporation |
| `published_date` | `TEXT` | Date and time published on the portal |
| `closing_date` | `TEXT` | Bid submission deadline |
| `opening_date` | `TEXT` | Technical bid opening timestamp |
| `corrigendum` | `TEXT` | Corrigendum status or latest amendment count |
| `tender_url` | `TEXT` | Direct link to tender details on CPPP / GeM |
| `source` | `TEXT` | Origin portal (`central`, `states`, or `gem`) |
| `search_category` | `TEXT` | Product Category or keyword under which it was found |
| `is_it_tender` | `INTEGER` | Boolean flag (1 = IT tender, 0 = non-IT) |
| `categories` | `TEXT` | Comma-separated IT sub-domains assigned by classifier |
| `matched_keywords`| `TEXT` | Comma-separated list of keywords that triggered the match |
| `confidence` | `REAL` | Match confidence score (0.0 to 1.0) |
| `reason` | `TEXT` | Classification explanation |
| `tender_fee` | `TEXT` | **Tender document processing fee in ₹** (e.g. `1,500` or `0`) |
| `emd` | `TEXT` | **Earnest Money Deposit (EMD) in ₹** (e.g. `50,000` or `0`) |
| `tender_document_url`| `TEXT` | **Direct URL to RFP / NIT document PDF or portal attachment** |
| `work_description`| `TEXT` | Comprehensive scope of work description |
| `location` | `TEXT` | Project site location, city, or postal pin code |
| `tender_type` | `TEXT` | Tender type (Open Tender, Limited, Expression of Interest) |
| `tender_category`| `TEXT` | Category classification (Services, Works, Goods) |
| `product_category`| `TEXT` | Product category classified on CPPP fullview |
| `doc_download_start_date`| `TEXT` | Document download start date |
| `doc_download_end_date`| `TEXT` | Document download end date |
| `bid_submission_start_date`| `TEXT`| Bid submission start date |
| `bid_submission_end_date`| `TEXT`| Final bid submission deadline |
| `authority_name` | `TEXT` | Procuring officer or buyer authority name |
| `authority_address`| `TEXT` | Official postal address of inviting authority |
| `details_fetched`| `INTEGER` | 1 if full financial and document details were fetched, 0 otherwise |
| `scraped_at` | `TEXT` | Local database insertion timestamp |

### Check Stored Database Stats
To inspect the current database inventory without scraping:
```bash
python3 cli.py --stats
```

---

## Command-Line Options Reference

| Argument | Flag | Choices / Format | Default | Description |
|---|---|---|---|---|
| Scraping Mode | `--mode` | `category`, `listing` | `category` | `category` = Form search with CAPTCHA; `listing` = Open stream |
| Source Portal | `--source` | `central`, `states`, `gem`, `all` | `central` | Repository to scrape |
| Product Category | `--category` | String | `None` *(Auto-Discover)* | Specific category; if omitted, all IT categories run sequentially |
| All Categories | `--all-categories` | Flag | `False` | Explicitly iterate all IT categories (default if `--category` omitted) |
| List Categories | `--list-categories` | Flag | `False` | Discover and display portal IT categories and exit |
| Page Limit | `--pages` | Integer | `20` | Maximum pages to scrape per category (10 tenders/page) |
| Scrape All Pages| `--all-pages` | Flag | `False` | Follow pagination until the last available page |
| Request Delay | `--delay` | Float (seconds) | `1.0` | Politeness delay between consecutive HTTP requests |
| Live Details | `--details` | Flag | `False` | Fetch full tender details (Fee, EMD, Doc URL) during live scraping |
| Enrich Details | `--fetch-details` | Flag | `False` | Standalone enrichment of existing tenders stored in `tenders.db` |
| Detail Limit | `--limit` | Integer | `None` | Max number of tenders to enrich when using `--fetch-details` |
| Target Tender | `--tender-id` | String | `None` | Enrich a specific Tender ID only with `--fetch-details` |
| Export File | `--output`, `-o` | File path | `it_tenders.csv` | Output file path (`.csv` or `.json`) |
| SQLite Database | `--db` | File path | `tenders.db` | SQLite database file path |
| Custom Keywords | `--keywords` | Comma-separated | `None` | Custom keyword(s) to add to GeM search or classifier |
| Database Stats | `--stats` | Flag | `False` | Show summary breakdown of saved tenders and exit |
| Verbose Logging | `-v`, `--verbose` | Flag | `False` | Enable detailed DEBUG-level logging |

---

## Automated Daily Scheduling (Cron)

You can automate daily scrapes on macOS or Linux using `cron`. Since the database uses `PRIMARY KEY (tender_id)`, daily runs automatically skip existing tenders and only capture new publications.

### Setting Up a Daily Cron Job (macOS)

1. Open your crontab editor:
   ```bash
   crontab -e
   ```

2. Add a daily scheduled entry (e.g., runs open listing mode every morning at 8:00 AM):
   ```bash
   0 8 * * * cd /Users/deeps/mywork/tenders/it-tender && /usr/bin/python3 cli.py --mode listing --source central --pages 50 >> scrape_cron.log 2>&1
   ```

3. For State Government tenders, add an entry at 8:30 AM:
   ```bash
   30 8 * * * cd /Users/deeps/mywork/tenders/it-tender && /usr/bin/python3 cli.py --mode listing --source states --pages 50 -o state_tenders.csv >> scrape_cron.log 2>&1
   ```

---

## Automated Test Suite

The project includes an automated test suite ([`test_filter.py`](file:///Users/deeps/mywork/tenders/it-tender/test_filter.py)) covering unit and sanity checks across all subsystems (10 automated tests):

```bash
python3 test_filter.py
```

### Verified Test Cases:
- `test_it_tenders_classified_correctly`: Validates positive detection across Software, Hardware, Networking, Cloud, AMC, and Digitization.
- `test_non_it_tenders_excluded`: Validates false-positive rejection of road restorations, coal mine civil works, catering, and bus hiring.
- `test_pagination_url_builder`: Validates base64 token generation for CPPP Drupal views.
- `test_extract_next_page_url`: Validates HTML pagination button extraction.
- `test_form_metadata_extraction`: Validates parsing of `form_build_id`, `form_id`, and `captcha_sid`.
- `test_category_auto_filtering`: Validates pattern matching of IT categories from 180+ dropdown entries.
- `test_storage_and_export`: Validates SQLite insert, duplicate prevention, and CSV/JSON export.
- `test_refresh_tender_url`: Validates dynamic base64 timestamp nonce injection to revive expired CPPP detail URLs.
- `test_parse_tender_details_html`: Validates parsing of Fee, EMD, base64 redirection tender document URLs, dates, and authority contacts.
- `test_storage_tender_details_enrichment`: Validates updating existing records, filtering by `needs_details_only`, and stats tracking.

---

## Project Directory Structure

```
/Users/deeps/mywork/tenders/it-tender/
├── cli.py                  # Main Command-Line Interface and execution orchestrator
├── config.py               # Portal URLs, IT taxonomy, regex filters, and HTTP headers
├── it_filter.py            # Rule-based NLP classifier and false-positive filter
├── scraper.py              # Core scraping engine, CAPTCHA display, and table parser
├── storage.py              # SQLite storage engine, deduplication, CSV/JSON exporters
├── test_filter.py          # Complete unit test suite (7 automated test cases)
├── requirements.txt        # Python package dependencies
├── tenders.db              # SQLite 3 persistent database (auto-generated)
├── it_tenders.csv          # Exported IT tenders in CSV format (auto-generated)
└── README.md               # Full project documentation
```

---

## Troubleshooting & FAQs

### Q1: The CAPTCHA image did not open in macOS Preview.
**A**: Ensure you are running the command in a native terminal session on macOS. You can also view the downloaded file directly:
```bash
open captcha.png
```
The exact file path is always printed in the terminal prompt: `file:///path/to/captcha.png`.

### Q2: What if the CAPTCHA is blurry or illegible?
**A**: Simply type `r` and press **Enter** at the terminal prompt. The scraper will fetch a fresh CAPTCHA without losing your position.

### Q3: How do I skip a category without stopping the entire scrape?
**A**: Type `s` and press **Enter** at the CAPTCHA prompt. The scraper will bypass that category and immediately proceed to the next one.

### Q4: The government portal is responding slowly or returning 500/502/504 errors.
**A**: The scraper includes built-in exponential backoff and retry logic (`MAX_RETRIES = 3`, `BACKOFF_FACTOR = 1.5`). You can also increase the politeness delay between requests using `--delay 2.5`.

### Q5: Can I run this in a headless server (e.g. Linux VPS / Docker)?
**A**: Yes. In a headless environment:
- Use `--mode listing` for 100% unattended scraping without CAPTCHAs.
- Or, for category mode, integrate an OCR solver (such as `tesseract`) or serve `captcha.png` via a lightweight local web interface.

---

## License

This project is licensed under the MIT License - feel free to adapt, extend, and deploy.

