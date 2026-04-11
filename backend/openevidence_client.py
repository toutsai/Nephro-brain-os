"""
OpenEvidence API Client for Nephro Brain OS
- Cookie-based auth (browser session reuse)
- Firestore cookie storage for Cloud Run compatibility
- Polling-based async query with timeout
"""

import requests
import json
import time
import threading

BASE_URL = "https://www.openevidence.com"
PENDING_STATUSES = {"queued", "pending", "processing", "running", "in_progress"}
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


class OpenEvidenceCookieManager:
    """Manage OpenEvidence cookies via Firestore (Cloud Run compatible)."""

    def __init__(self, db):
        self._db = db
        self._cookies = None
        self._cache_time = 0
        self._cache_ttl = 300  # 5 min
        self._lock = threading.Lock()

    def _doc_ref(self):
        return self._db.collection("system_config").document("oe_cookies")

    def load_cookies(self):
        """Load cookies from Firestore, with in-memory cache."""
        with self._lock:
            now = time.time()
            if self._cookies and (now - self._cache_time) < self._cache_ttl:
                return self._cookies

            try:
                doc = self._doc_ref().get()
                if doc.exists:
                    data = doc.to_dict()
                    self._cookies = data.get("cookies", {})
                    self._cache_time = now
                    return self._cookies
            except Exception as e:
                print(f"⚠️ OE: Failed to load cookies from Firestore: {e}")

            return {}

    def save_cookies(self, cookies_dict, uid=None):
        """Save cookies to Firestore."""
        from google.cloud.firestore_v1 import SERVER_TIMESTAMP
        self._doc_ref().set({
            "cookies": cookies_dict,
            "updated_at": SERVER_TIMESTAMP,
            "updated_by": uid or "system",
            "valid": None,  # will be set by validate()
        }, merge=True)
        # Invalidate cache
        with self._lock:
            self._cookies = cookies_dict
            self._cache_time = time.time()

    def get_cookie_header(self):
        """Format cookies as HTTP header value."""
        cookies = self.load_cookies()
        if not cookies:
            return ""
        return "; ".join(f"{k}={v}" for k, v in cookies.items())

    def validate(self):
        """Check if cookies are valid by calling /api/auth/me."""
        cookie_header = self.get_cookie_header()
        if not cookie_header:
            return False

        try:
            resp = requests.get(
                f"{BASE_URL}/api/auth/me",
                headers=_build_headers(cookie_header),
                timeout=15,
            )
            valid = resp.status_code == 200
            # Update status in Firestore
            try:
                from google.cloud.firestore_v1 import SERVER_TIMESTAMP
                update = {"valid": valid, "last_validated": SERVER_TIMESTAMP}
                if valid:
                    data = resp.json()
                    update["user_email"] = data.get("email", "")
                self._doc_ref().set(update, merge=True)
            except Exception:
                pass
            return valid
        except Exception as e:
            print(f"⚠️ OE: Auth check failed: {e}")
            return False

    def get_status(self):
        """Return current cookie status for admin UI."""
        try:
            doc = self._doc_ref().get()
            if doc.exists:
                data = doc.to_dict()
                return {
                    "valid": data.get("valid"),
                    "user_email": data.get("user_email", ""),
                    "updated_at": str(data.get("updated_at", "")),
                    "last_validated": str(data.get("last_validated", "")),
                    "has_cookies": bool(data.get("cookies")),
                }
        except Exception:
            pass
        return {"valid": None, "has_cookies": False}


def _build_headers(cookie_header):
    """Build browser-like headers for OpenEvidence API."""
    return {
        "Cookie": cookie_header,
        "User-Agent": USER_AGENT,
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
    }


class OpenEvidenceClient:
    """Query OpenEvidence API with cookie auth + polling."""

    def __init__(self, cookie_manager):
        self._cm = cookie_manager

    def _headers(self):
        cookie_header = self._cm.get_cookie_header()
        if not cookie_header:
            raise RuntimeError("No OpenEvidence cookies available")
        return _build_headers(cookie_header)

    def check_auth(self):
        """Verify authentication status."""
        resp = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers=self._headers(),
            timeout=15,
        )
        return resp.status_code == 200

    def ask(self, question):
        """Submit a question, return article_id."""
        payload = {
            "article_type": "Ask OpenEvidence Light with citations",
            "inputs": {
                "variant_configuration_file": "prod",
                "attachments": [],
                "question": question,
                "use_gatekeeper": True,
            },
            "personalization_enabled": False,
            "disable_caching": False,
        }

        resp = requests.post(
            f"{BASE_URL}/api/article",
            headers=self._headers(),
            json=payload,
            timeout=30,
        )

        if resp.status_code not in (200, 201):
            raise RuntimeError(f"OE ask failed: {resp.status_code} {resp.text[:300]}")

        article = resp.json()
        article_id = article.get("id")
        if not article_id:
            raise RuntimeError("OE ask returned no article_id")
        return article_id

    def poll(self, article_id, timeout=180, interval=3):
        """Poll until article is complete or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                resp = requests.get(
                    f"{BASE_URL}/api/article/{article_id}",
                    headers=self._headers(),
                    timeout=20,
                )
                if resp.status_code != 200:
                    raise RuntimeError(f"OE poll failed: {resp.status_code}")

                article = resp.json()
                status = (article.get("status") or "").lower()

                if status not in PENDING_STATUSES:
                    return article

            except requests.RequestException as e:
                print(f"⚠️ OE poll network error: {e}")

            time.sleep(interval)

        raise TimeoutError(f"OpenEvidence polling timed out after {timeout}s")

    def extract_answer(self, article):
        """Extract main answer text from article response."""
        try:
            output = article.get("output", {})
            structured = output.get("structured_article", {})

            # Priority 1: raw_text
            raw_text = structured.get("raw_text")
            if raw_text:
                return raw_text

            # Priority 2: output.text (strip React components)
            text = output.get("text", "")
            if text:
                import re
                text = re.sub(r'<[A-Z][a-zA-Z]*[^>]*\/>', '', text)
                text = re.sub(r'<[A-Z][a-zA-Z]*[^>]*>.*?<\/[A-Z][a-zA-Z]*>', '', text, flags=re.DOTALL)
                return text.strip()

            # Priority 3: history
            inputs = article.get("inputs", {})
            history = inputs.get("history", [])
            if history:
                last = history[-1]
                if isinstance(last, dict):
                    return last.get("outputText", "")

        except Exception as e:
            print(f"⚠️ OE extract_answer error: {e}")

        return ""

    def extract_citations(self, article):
        """Extract and format citations from article."""
        citations = []
        seen_keys = set()

        try:
            output = article.get("output", {})
            structured = output.get("structured_article", {})

            def walk_sections(sections):
                if not isinstance(sections, list):
                    return
                for section in sections:
                    if not isinstance(section, dict):
                        continue
                    for cite in section.get("citations", []):
                        if not isinstance(cite, dict):
                            continue
                        meta = cite.get("metadata", {})
                        detail = meta.get("citation_detail", {})

                        title = detail.get("title", "")
                        doi = detail.get("doi", "")
                        pmid = detail.get("pmid", "")
                        authors = detail.get("authors_string", "")
                        journal = detail.get("journal_name", "")
                        year = detail.get("dt_published", "")[:4] if detail.get("dt_published") else ""
                        href = detail.get("href", "")

                        # Dedup key
                        key = (doi or pmid or title or "").lower()
                        if key and key in seen_keys:
                            continue
                        if key:
                            seen_keys.add(key)

                        if title or doi or pmid:
                            citations.append({
                                "title": title,
                                "authors": authors,
                                "journal": journal,
                                "year": year,
                                "doi": doi,
                                "pmid": pmid,
                                "href": href,
                            })

                    # Recurse
                    walk_sections(section.get("sections", []))

            walk_sections(structured.get("sections", []))

        except Exception as e:
            print(f"⚠️ OE extract_citations error: {e}")

        return citations

    def format_citations_markdown(self, citations):
        """Format citations as markdown with PubMed/DOI links."""
        if not citations:
            return ""

        lines = []
        for i, c in enumerate(citations, 1):
            parts = []
            if c.get("title"):
                parts.append(f"**{c['title']}**")
            if c.get("authors"):
                parts.append(c["authors"])
            if c.get("journal"):
                parts.append(f"*{c['journal']}*")
            if c.get("year"):
                parts.append(f"({c['year']})")

            links = []
            if c.get("pmid"):
                pmid = str(c["pmid"]).strip()
                links.append(f"[PubMed](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)")
            if c.get("doi"):
                doi = c["doi"].strip()
                links.append(f"[DOI](https://doi.org/{doi})")
            if not links and c.get("href"):
                links.append(f"[Link]({c['href']})")

            line = ". ".join(parts)
            if links:
                line += " " + " | ".join(links)

            lines.append(f"{i}. {line}")

        return "\n".join(lines)

    def get_formatted_result(self, question):
        """Full query: ask → poll → extract → format. Returns {answer, citations, citations_raw}."""
        article_id = self.ask(question)
        article = self.poll(article_id)
        answer = self.extract_answer(article)
        citations_raw = self.extract_citations(article)
        citations_md = self.format_citations_markdown(citations_raw)

        return {
            "answer": answer,
            "citations": citations_md,
            "citations_raw": citations_raw,
        }
