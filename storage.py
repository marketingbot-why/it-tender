"""Database and file storage manager for eprocure tenders."""

import os
import csv
import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional


class TenderStorage:
    """Handles SQLite persistence and CSV / JSON exports for scraped tenders."""

    def __init__(self, db_path: str = "tenders.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Create database tables, indices, and auto-migrate new columns."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tenders (
                    tender_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    tender_ref_no TEXT,
                    organisation TEXT,
                    published_date TEXT,
                    closing_date TEXT,
                    opening_date TEXT,
                    corrigendum TEXT,
                    tender_url TEXT,
                    source TEXT,
                    search_category TEXT,
                    is_it_tender INTEGER,
                    categories TEXT,
                    matched_keywords TEXT,
                    confidence REAL,
                    reason TEXT,
                    scraped_at TEXT,
                    tender_fee TEXT,
                    emd TEXT,
                    tender_document_url TEXT,
                    work_description TEXT,
                    location TEXT,
                    tender_type TEXT,
                    tender_category TEXT,
                    product_category TEXT,
                    doc_download_start_date TEXT,
                    doc_download_end_date TEXT,
                    bid_submission_start_date TEXT,
                    bid_submission_end_date TEXT,
                    authority_name TEXT,
                    authority_address TEXT,
                    details_fetched INTEGER DEFAULT 0
                )
            """)

            # Auto-migrate existing database tables
            new_columns = [
                ("search_category", "TEXT"),
                ("tender_fee", "TEXT"),
                ("emd", "TEXT"),
                ("tender_document_url", "TEXT"),
                ("work_description", "TEXT"),
                ("location", "TEXT"),
                ("tender_type", "TEXT"),
                ("tender_category", "TEXT"),
                ("product_category", "TEXT"),
                ("doc_download_start_date", "TEXT"),
                ("doc_download_end_date", "TEXT"),
                ("bid_submission_start_date", "TEXT"),
                ("bid_submission_end_date", "TEXT"),
                ("authority_name", "TEXT"),
                ("authority_address", "TEXT"),
                ("details_fetched", "INTEGER DEFAULT 0"),
            ]
            for col_name, col_type in new_columns:
                try:
                    cursor.execute(f"ALTER TABLE tenders ADD COLUMN {col_name} {col_type}")
                except sqlite3.OperationalError:
                    pass

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_is_it ON tenders(is_it_tender)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_closing_date ON tenders(closing_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON tenders(source)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_details_fetched ON tenders(details_fetched)")
            conn.commit()

    def save_tender(self, tender: Dict[str, Any]) -> bool:
        """
        Save or update a tender record.
        Returns True if inserted as a new record, False if updated.
        """
        scraped_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        categories_str = ", ".join(tender.get("categories", [])) if isinstance(tender.get("categories"), list) else tender.get("categories", "")
        keywords_str = ", ".join(tender.get("matched_keywords", [])) if isinstance(tender.get("matched_keywords"), list) else tender.get("matched_keywords", "")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tender_id, details_fetched FROM tenders WHERE tender_id = ?", (tender.get("tender_id"),))
            existing = cursor.fetchone()
            is_new = existing is None

            cursor.execute("""
                INSERT INTO tenders (
                    tender_id, title, tender_ref_no, organisation,
                    published_date, closing_date, opening_date,
                    corrigendum, tender_url, source, search_category,
                    is_it_tender, categories, matched_keywords,
                    confidence, reason, scraped_at,
                    tender_fee, emd, tender_document_url,
                    work_description, location, tender_type, tender_category, product_category,
                    doc_download_start_date, doc_download_end_date,
                    bid_submission_start_date, bid_submission_end_date,
                    authority_name, authority_address, details_fetched
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tender_id) DO UPDATE SET
                    title = excluded.title,
                    tender_ref_no = excluded.tender_ref_no,
                    organisation = excluded.organisation,
                    closing_date = excluded.closing_date,
                    opening_date = excluded.opening_date,
                    corrigendum = excluded.corrigendum,
                    tender_url = excluded.tender_url,
                    search_category = COALESCE(excluded.search_category, tenders.search_category),
                    is_it_tender = excluded.is_it_tender,
                    categories = excluded.categories,
                    matched_keywords = excluded.matched_keywords,
                    confidence = excluded.confidence,
                    reason = excluded.reason,
                    tender_fee = COALESCE(excluded.tender_fee, tenders.tender_fee),
                    emd = COALESCE(excluded.emd, tenders.emd),
                    tender_document_url = COALESCE(excluded.tender_document_url, tenders.tender_document_url),
                    work_description = COALESCE(excluded.work_description, tenders.work_description),
                    location = COALESCE(excluded.location, tenders.location),
                    tender_type = COALESCE(excluded.tender_type, tenders.tender_type),
                    tender_category = COALESCE(excluded.tender_category, tenders.tender_category),
                    product_category = COALESCE(excluded.product_category, tenders.product_category),
                    doc_download_start_date = COALESCE(excluded.doc_download_start_date, tenders.doc_download_start_date),
                    doc_download_end_date = COALESCE(excluded.doc_download_end_date, tenders.doc_download_end_date),
                    bid_submission_start_date = COALESCE(excluded.bid_submission_start_date, tenders.bid_submission_start_date),
                    bid_submission_end_date = COALESCE(excluded.bid_submission_end_date, tenders.bid_submission_end_date),
                    authority_name = COALESCE(excluded.authority_name, tenders.authority_name),
                    authority_address = COALESCE(excluded.authority_address, tenders.authority_address),
                    details_fetched = CASE WHEN excluded.details_fetched = 1 THEN 1 ELSE tenders.details_fetched END
            """, (
                tender.get("tender_id", ""),
                tender.get("title", ""),
                tender.get("tender_ref_no", ""),
                tender.get("organisation", ""),
                tender.get("published_date", ""),
                tender.get("closing_date", ""),
                tender.get("opening_date", ""),
                tender.get("corrigendum", ""),
                tender.get("tender_url", ""),
                tender.get("source", "central"),
                tender.get("search_category", ""),
                1 if tender.get("is_it_tender") else 0,
                categories_str,
                keywords_str,
                tender.get("confidence", 0.0),
                tender.get("reason", ""),
                scraped_at,
                tender.get("tender_fee"),
                tender.get("emd"),
                tender.get("tender_document_url"),
                tender.get("work_description"),
                tender.get("location"),
                tender.get("tender_type"),
                tender.get("tender_category"),
                tender.get("product_category"),
                tender.get("doc_download_start_date"),
                tender.get("doc_download_end_date"),
                tender.get("bid_submission_start_date"),
                tender.get("bid_submission_end_date"),
                tender.get("authority_name"),
                tender.get("authority_address"),
                1 if tender.get("details_fetched") else 0
            ))
            conn.commit()
            return is_new

    def update_tender_details(self, tender_id: str, details: Optional[Dict[str, Any]]) -> bool:
        """Update financial, document, and authority details for an existing tender."""
        if not details:
            return False

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE tenders SET
                    tender_fee = COALESCE(?, tender_fee),
                    emd = COALESCE(?, emd),
                    tender_document_url = COALESCE(?, tender_document_url),
                    work_description = COALESCE(?, work_description),
                    location = COALESCE(?, location),
                    tender_type = COALESCE(?, tender_type),
                    tender_category = COALESCE(?, tender_category),
                    product_category = COALESCE(?, product_category),
                    doc_download_start_date = COALESCE(?, doc_download_start_date),
                    doc_download_end_date = COALESCE(?, doc_download_end_date),
                    bid_submission_start_date = COALESCE(?, bid_submission_start_date),
                    bid_submission_end_date = COALESCE(?, bid_submission_end_date),
                    authority_name = COALESCE(?, authority_name),
                    authority_address = COALESCE(?, authority_address),
                    details_fetched = 1
                WHERE tender_id = ?
            """, (
                details.get("tender_fee"),
                details.get("emd"),
                details.get("tender_document_url"),
                details.get("work_description"),
                details.get("location"),
                details.get("tender_type"),
                details.get("tender_category"),
                details.get("product_category"),
                details.get("doc_download_start_date"),
                details.get("doc_download_end_date"),
                details.get("bid_submission_start_date"),
                details.get("bid_submission_end_date"),
                details.get("authority_name"),
                details.get("authority_address"),
                tender_id
            ))
            conn.commit()
            return cursor.rowcount > 0

    def reset_unpopulated_details(self) -> int:
        """
        Reset details_fetched to 0 for any tenders that were falsely marked as enriched
        but have no actual work description or location data.
        Returns number of rows reset.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE tenders SET
                    details_fetched = 0,
                    tender_fee = NULL,
                    emd = NULL,
                    tender_document_url = NULL,
                    work_description = NULL,
                    location = NULL
                WHERE details_fetched = 1 
                  AND (work_description IS NULL OR work_description = '')
                  AND (location IS NULL OR location = '')
            """)
            conn.commit()
            return cursor.rowcount

    def get_tenders(
        self,
        only_it: bool = True,
        needs_details_only: bool = False,
        tender_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve tenders from SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = "SELECT * FROM tenders WHERE 1=1"
            params = []
            if only_it:
                query += " AND is_it_tender = 1"
            if needs_details_only:
                query += " AND (details_fetched IS NULL OR details_fetched = 0)"
            if tender_id:
                query += " AND tender_id = ?"
                params.append(tender_id)
            query += " ORDER BY published_date DESC"
            if limit:
                query += f" LIMIT {int(limit)}"

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> Dict[str, Any]:
        """Return counts, category breakdowns, and details coverage."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM tenders")
            total = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM tenders WHERE is_it_tender = 1")
            it_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM tenders WHERE details_fetched = 1")
            details_count = cursor.fetchone()[0]

            cursor.execute("SELECT categories FROM tenders WHERE is_it_tender = 1 AND categories != ''")
            category_counts: Dict[str, int] = {}
            for (cats,) in cursor.fetchall():
                for cat in cats.split(", "):
                    cat = cat.strip()
                    if cat:
                        category_counts[cat] = category_counts.get(cat, 0) + 1

            return {
                "total_tenders": total,
                "it_tenders": it_count,
                "details_fetched": details_count,
                "categories": category_counts
            }

    def export_to_csv(self, filepath: str, only_it: bool = True) -> int:
        """Export stored tenders to a CSV file. Returns number of rows exported."""
        tenders = self.get_tenders(only_it=only_it)
        fields = [
            "tender_id", "title", "tender_ref_no", "organisation",
            "tender_fee", "emd", "tender_document_url", "work_description",
            "location", "tender_type", "tender_category",
            "published_date", "closing_date", "opening_date",
            "doc_download_start_date", "doc_download_end_date",
            "bid_submission_start_date", "bid_submission_end_date",
            "authority_name", "authority_address",
            "search_category", "categories", "matched_keywords", "confidence",
            "source", "tender_url", "details_fetched", "scraped_at"
        ]
        if not tenders:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
            return 0

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for t in tenders:
                writer.writerow(t)

        return len(tenders)

    def export_to_json(self, filepath: str, only_it: bool = True) -> int:
        """Export stored tenders to a JSON file."""
        tenders = self.get_tenders(only_it=only_it)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(tenders, f, indent=2, ensure_ascii=False)
        return len(tenders)
