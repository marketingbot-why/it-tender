"""IT Tender classifier and rule-based filter."""

import re
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field

from config import IT_CATEGORIES, IT_ORGANISATIONS, EXCLUSION_KEYWORDS


@dataclass
class ITClassificationResult:
    is_it_tender: bool
    categories: List[str] = field(default_factory=list)
    matched_keywords: List[str] = field(default_factory=list)
    matched_orgs: List[str] = field(default_factory=list)
    confidence: float = 0.0
    reason: str = ""


class ITFilter:
    """Classifies tenders to detect whether they represent Information Technology projects."""

    def __init__(self, custom_keywords: List[str] = None):
        self.categories = IT_CATEGORIES.copy()
        if custom_keywords:
            self.categories["Custom Keywords"] = [k.strip().lower() for k in custom_keywords if k.strip()]

        # Compile regex word boundary patterns for single tokens to avoid substring false positives
        self.word_patterns: Dict[str, re.Pattern] = {}
        for cat, keywords in self.categories.items():
            for kw in keywords:
                clean_kw = kw.strip().lower()
                # If short or single word, use word boundary regex
                if len(clean_kw) <= 4 or " " not in clean_kw:
                    self.word_patterns[clean_kw] = re.compile(r'\b' + re.escape(clean_kw) + r'\b', re.IGNORECASE)

    def classify(self, tender: Dict[str, Any]) -> ITClassificationResult:
        """
        Evaluate a tender dictionary.
        Expected keys: 'title', 'organisation', 'tender_ref_no', 'tender_id'
        """
        title = (tender.get("title") or "").strip().lower()
        org = (tender.get("organisation") or "").strip().lower()
        ref = (tender.get("tender_ref_no") or "").strip().lower()

        search_text = f"{title} {ref} {org}"
        matched_categories = []
        matched_keywords = []
        matched_orgs = []
        score = 0.0

        # Check for IT organisations
        for it_org in IT_ORGANISATIONS:
            if it_org in org:
                matched_orgs.append(it_org)
                score += 0.4

        # Check for standalone 'IT' or 'I.T.' (case-sensitive) or 'information technology'
        orig_text = f"{tender.get('title', '')} {tender.get('tender_ref_no', '')} {tender.get('organisation', '')}"
        if re.search(r'\b(IT|I\.T\.|ICT)\b', orig_text):
            matched_keywords.append("IT")
            if "IT Services & Consulting" not in matched_categories:
                matched_categories.append("IT Services & Consulting")
            score += 0.35

        if "information technology" in search_text:
            matched_keywords.append("information technology")
            if "IT Services & Consulting" not in matched_categories:
                matched_categories.append("IT Services & Consulting")
            score += 0.4

        # Check for Cloud acronyms (case-sensitive)
        if re.search(r'\b(PaaS|IaaS|SaaS)\b', orig_text):
            matched_keywords.append("Cloud Services")
            if "Cloud & Data Center" not in matched_categories:
                matched_categories.append("Cloud & Data Center")
            score += 0.35

        # Check for IT keywords in each category
        for cat_name, kw_list in self.categories.items():
            cat_matched = False
            for kw in kw_list:
                kw_lower = kw.strip().lower()
                pattern = self.word_patterns.get(kw_lower)
                matched = False
                if pattern:
                    if pattern.search(search_text):
                        matched = True
                else:
                    if kw_lower in search_text:
                        matched = True

                if matched:
                    matched_keywords.append(kw_lower)
                    if not cat_matched and cat_name not in matched_categories:
                        matched_categories.append(cat_name)
                        cat_matched = True
                    score += 0.35

        # If matched by an IT PSU/body without specific equipment category
        if matched_orgs and not matched_categories:
            matched_categories.append("IT & Telecom / Government Body")

        # If only generic maintenance terms matched with no other IT context, discard
        generic_terms = {"amc", "annual maintenance contract", "maintenance contract", "fms"}
        specific_it_keywords = [k for k in matched_keywords if k not in generic_terms]
        if not specific_it_keywords and not matched_orgs:
            matched_categories = []
            matched_keywords = []
            score = 0.0

        # Check exclusions (penalize if non-IT works)
        exclusion_found = []
        for exc in EXCLUSION_KEYWORDS:
            if exc in title:
                exclusion_found.append(exc)

        if exclusion_found:
            # If explicit exclusion matches and no strong technical IT project keywords (e.g. software, server, cloud)
            strong_it = [
                k for k in specific_it_keywords
                if k not in {"it", "ict", "information technology", "networking"}
            ]
            if len(strong_it) == 0:
                score = 0.0
                matched_categories = []
                matched_keywords = []
            else:
                score -= 0.6

        # Cap score between 0.0 and 1.0
        confidence = max(0.0, min(1.0, round(score, 2)))
        is_it = (confidence >= 0.35 and len(matched_keywords) > 0) or (len(matched_orgs) > 0 and confidence >= 0.3 and len(matched_categories) > 0)

        reasons = []
        if matched_keywords:
            reasons.append(f"Keywords: {', '.join(set(matched_keywords[:5]))}")
        if matched_orgs:
            reasons.append(f"IT Body: {', '.join(matched_orgs)}")
        if exclusion_found:
            reasons.append(f"Exclusion Note: {', '.join(exclusion_found[:2])}")

        return ITClassificationResult(
            is_it_tender=is_it,
            categories=matched_categories,
            matched_keywords=list(set(matched_keywords)),
            matched_orgs=matched_orgs,
            confidence=confidence,
            reason="; ".join(reasons)
        )
