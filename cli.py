#!/usr/bin/env python3
"""Command-line interface for eprocure IT tender scraper with interactive CAPTCHA & Product Category search."""

import sys
import argparse
import logging
from datetime import datetime

from config import SOURCES, IT_PRODUCT_CATEGORIES, GEM_IT_KEYWORDS
from scraper import EprocureScraper
from storage import TenderStorage


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        level=level
    )


def print_banner():
    banner = r"""
============================================================
      EPROCURE.GOV.IN - GOVERNMENT IT TENDER SCRAPER
         [Interactive Product Category & CAPTCHA Mode]
============================================================
"""
    print(banner)


def main():
    parser = argparse.ArgumentParser(
        description="Scrape active government tenders from eprocure.gov.in filtered by IT Product Categories."
    )
    parser.add_argument(
        "--mode",
        choices=["category", "listing"],
        default="category",
        help="Scraping mode: 'category' (search form with CAPTCHA) or 'listing' (stream open pagination)"
    )
    parser.add_argument(
        "--source",
        choices=["central", "states", "gem", "all"],
        default="central",
        help="Tender repository to scrape (default: central)"
    )
    parser.add_argument(
        "--category",
        type=str,
        help="Specific IT Product Category to search (optional; if omitted, all relevant IT categories are auto-filtered and processed sequentially)"
    )
    parser.add_argument(
        "--all-categories",
        action="store_true",
        help="Explicitly iterate through all matching IT Product Categories (default behavior when --category is omitted)"
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List all standard IT Product Categories available on eprocure and exit"
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=20,
        help="Maximum pages to scrape per category (default: 20, 10 tenders/page)"
    )
    parser.add_argument(
        "--all-pages",
        action="store_true",
        help="Scrape all available pages until completion"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between page requests (default: 1.0s)"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="it_tenders.csv",
        help="Path for CSV or JSON export (default: it_tenders.csv)"
    )
    parser.add_argument(
        "--db",
        type=str,
        default="tenders.db",
        help="Path to SQLite database file (default: tenders.db)"
    )
    parser.add_argument(
        "--keywords",
        type=str,
        help="Additional custom keyword(s) for GeM or classification"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Display current database statistics and exit"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable detailed debug logging"
    )

    args = parser.parse_args()
    setup_logging(args.verbose)
    print_banner()

    storage = TenderStorage(db_path=args.db)

    if args.list_categories:
        print("Available IT Product Categories on eprocure.gov.in:")
        for idx, cat in enumerate(IT_PRODUCT_CATEGORIES, 1):
            print(f"  [{idx:2d}] {cat}")
        print("\nGeM IT Search Keywords:")
        for idx, kw in enumerate(GEM_IT_KEYWORDS, 1):
            print(f"  [{idx:2d}] {kw}")
        return

    if args.stats:
        stats = storage.get_stats()
        print(f"Database: {args.db}")
        print(f"Total Tenders Stored: {stats['total_tenders']:,}")
        print(f"IT Tenders Stored   : {stats['it_tenders']:,}")
        print("\nBreakdown by IT Category:")
        for cat, count in stats["categories"].items():
            print(f"  - {cat:32s}: {count}")
        return

    custom_kw = [k.strip() for k in args.keywords.split(",")] if args.keywords else None
    scraper = EprocureScraper(delay=args.delay, custom_keywords=custom_kw)

    sources_to_scrape = list(SOURCES.keys()) if args.source == "all" else [args.source]
    max_pages = None if args.all_pages else args.pages

    total_scraped = 0
    total_it_found = 0
    total_new_saved = 0

    print(f"[*] Mode       : {args.mode.upper()} {'(Search Form + CAPTCHA)' if args.mode == 'category' else '(Open Feed)'}")
    print(f"[*] Sources    : {', '.join(sources_to_scrape)}")
    print(f"[*] Page Limit : {'ALL' if args.all_pages else args.pages} pages")
    print(f"[*] Delay      : {args.delay}s per request")
    print(f"[*] SQLite DB  : {args.db}")
    print(f"[*] Export File: {args.output}\n")

    start_time = datetime.now()

    try:
        if args.mode == "category":
            # Search Form with CAPTCHA Mode
            for src in sources_to_scrape:
                src_info = SOURCES[src]

                if src == "gem":
                    # GeM keyword search
                    keywords_to_run = [args.category] if args.category else (custom_kw or GEM_IT_KEYWORDS)
                    print(f"[*] GeM IT Keywords ({len(keywords_to_run)}) to search sequentially:")
                    for idx, kw in enumerate(keywords_to_run, 1):
                        print(f"    [{idx:2d}] {kw}")

                    for idx, kw in enumerate(keywords_to_run, 1):
                        print("\n" + "=" * 60)
                        print(f" [GeM Keyword {idx}/{len(keywords_to_run)}] '{kw}'")
                        print("=" * 60)
                        kw_matches = 0
                        for tender in scraper.scrape_category_interactively(source="gem", keyword=kw, max_pages=max_pages):
                            total_scraped += 1
                            if tender.get("is_it_tender"):
                                total_it_found += 1
                                kw_matches += 1
                                print(f"  [+] [MATCH] [{tender.get('search_category')}] {tender['title'][:70]}...")
                                print(f"      ID: {tender['tender_id']} | Org: {tender['organisation'][:45]} | Closes: {tender['closing_date']}")
                            is_new = storage.save_tender(tender)
                            if is_new:
                                total_new_saved += 1
                        print(f"[*] Finished GeM search for '{kw}': {kw_matches} matching bids found.")

                else:
                    # Central or States with s_prod_type dropdown
                    if args.category:
                        categories_to_run = [args.category]
                        print(f"[*] Searching specified category: '{args.category}'")
                    else:
                        print(f"[*] Auto-discovering all IT / Tech categories from {src_info['name']}...")
                        categories_to_run = scraper.discover_it_categories(source=src)
                        print(f"[*] Auto-discovered {len(categories_to_run)} relevant IT categories to process one by one:")
                        for idx, cat in enumerate(categories_to_run, 1):
                            print(f"    [{idx:2d}] {cat}")

                    for idx, cat in enumerate(categories_to_run, 1):
                        print("\n" + "=" * 60)
                        print(f" [Category {idx}/{len(categories_to_run)} on {src_info['name']}] '{cat}'")
                        print("=" * 60)
                        cat_matches = 0
                        for tender in scraper.scrape_category_interactively(source=src, category=cat, max_pages=max_pages):
                            total_scraped += 1
                            if tender.get("is_it_tender"):
                                total_it_found += 1
                                cat_matches += 1
                                print(f"  [+] [MATCH] [{tender.get('search_category')}] {tender['title'][:70]}...")
                                print(f"      ID: {tender['tender_id']} | Org: {tender['organisation'][:45]} | Closes: {tender['closing_date']}")
                            is_new = storage.save_tender(tender)
                            if is_new:
                                total_new_saved += 1
                        print(f"[*] Finished category '{cat}': {cat_matches} matching tenders found.")

        else:
            # Listing / Direct feed mode without CAPTCHA
            for src in sources_to_scrape:
                print(f"\n---> Scanning {SOURCES[src]['name']} (Listing stream)...")
                for tender in scraper.scrape_tenders(source=src, max_pages=max_pages, only_it=True):
                    total_scraped += 1
                    if tender.get("is_it_tender"):
                        total_it_found += 1
                        cats = ", ".join(tender.get("categories", [])) or "IT Project"
                        print(f"  [+] [MATCH] [{cats}] {tender['title'][:70]}...")
                        print(f"      ID: {tender['tender_id']} | Org: {tender['organisation'][:45]} | Closes: {tender['closing_date']}")
                    is_new = storage.save_tender(tender)
                    if is_new:
                        total_new_saved += 1

    except KeyboardInterrupt:
        print("\n[!] Scraping stopped by user. Generating report for saved tenders...")

    elapsed = (datetime.now() - start_time).total_seconds()

    # Perform Export
    export_path = args.output
    if export_path.endswith(".json"):
        exported_count = storage.export_to_json(export_path, only_it=True)
    else:
        if not export_path.endswith(".csv"):
            export_path += ".csv"
        exported_count = storage.export_to_csv(export_path, only_it=True)

    print("\n" + "=" * 60)
    print("                    SCRAPE SUMMARY")
    print("=" * 60)
    print(f"Duration            : {elapsed:.1f} seconds")
    print(f"Matching Tenders    : {total_it_found}")
    print(f"New Records Saved   : {total_new_saved}")
    print(f"Exported to File    : {export_path} ({exported_count} records)")
    print(f"SQLite Database     : {args.db}")

    stats = storage.get_stats()
    if stats["categories"]:
        print("\nCategory Distribution in Database:")
        for cat, count in sorted(stats["categories"].items(), key=lambda x: x[1], reverse=True):
            print(f"  - {cat:32s}: {count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
