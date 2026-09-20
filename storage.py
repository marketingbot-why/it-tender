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
        """Create database tables and indices if they do not exist."""
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
                    scraped_at TEXT
                )
            """)
            try:
                cursor.execute("ALTER TABLE tenders ADD COLUMN search_category TEXT")
            except sqlite3.OperationalError:
                pass

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_is_it ON tenders(is_it_tender)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_closing_date ON tenders(closing_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON tenders(source)")
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
            cursor.execute("SELECT tender_id FROM tenders WHERE tender_id = ?", (tender.get("tender_id"),))
            is_new = cursor.fetchone() is None

            cursor.execute("""
                INSERT OR REPLACE INTO tenders (
                    tender_id, title, tender_ref_no, organisation,
                    published_date, closing_date, opening_date,
                    corrigendum, tender_url, source, search_category,
                    is_it_tender, categories, matched_keywords,
                    confidence, reason, scraped_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                scraped_at
            ))
            conn.commit()
            return is_new

    def get_tenders(self, only_it: bool = True, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve tenders from SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = "SELECT * FROM tenders"
            params = []
            if only_it:
                query += " WHERE is_it_tender = 1"
            query += " ORDER BY published_date DESC"
            if limit:
                query += f" LIMIT {int(limit)}"

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> Dict[str, Any]:
        """Return counts and category breakdowns."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM tenders")
            total = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM tenders WHERE is_it_tender = 1")
            it_count = cursor.fetchone()[0]

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
                "categories": category_counts
            }

    def export_to_csv(self, filepath: str, only_it: bool = True) -> int:
        """Export stored tenders to a CSV file. Returns number of rows exported."""
        tenders = self.get_tenders(only_it=only_it)
        fields = [
            "tender_id", "title", "tender_ref_no", "organisation",
            "published_date", "closing_date", "opening_date",
            "search_category", "categories", "matched_keywords", "confidence",
            "source", "tender_url", "scraped_at"
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
