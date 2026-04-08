"""
Download Guidelines (KDOQI + future) — Nephro Brain OS
========================================================
多來源自動下載指引 PDF：
  1. 直接 URL（kidney.org 等）
  2. Europe PMC（Open Access 全文 PDF，用 DOI 查）
  3. Unpaywall API（用 DOI 找 OA 版本）
  4. PubMed Central（PMC ID 直接下載）

使用方式：
  python crawlers/download_kdoqi.py            # 下載並上傳
  python crawlers/download_kdoqi.py --dry-run   # 只顯示，不下載
"""

import argparse
import json
import logging
import os
import tempfile
import time

import requests
import firebase_admin
from firebase_admin import credentials, firestore, storage
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

FIREBASE_SERVICE_ACCOUNT_JSON = os.getenv(
    "FIREBASE_SERVICE_ACCOUNT_JSON", "serviceAccountKey.json"
)

if not firebase_admin._apps:
    if FIREBASE_SERVICE_ACCOUNT_JSON.strip().startswith("{"):
        cred = credentials.Certificate(json.loads(FIREBASE_SERVICE_ACCOUNT_JSON))
    elif os.path.exists(FIREBASE_SERVICE_ACCOUNT_JSON):
        cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_JSON)
    else:
        raise FileNotFoundError(
            f"找不到 Firebase 憑證：{FIREBASE_SERVICE_ACCOUNT_JSON}"
        )
    firebase_admin.initialize_app(cred, {
        "storageBucket": "nephro-brain.firebasestorage.app"
    })

db = firestore.client()
bucket = storage.bucket()

# Unpaywall requires an email for API access (polite pool)
UNPAYWALL_EMAIL = os.getenv("UNPAYWALL_EMAIL", "nephro-brain@example.com")

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "NephroBrainOS/1.0 (guideline-downloader; mailto:{})".format(UNPAYWALL_EMAIL)
})

# ---------------------------------------------------------------------------
# Guideline definitions — DOI-based for multi-source resolution
# ---------------------------------------------------------------------------

GUIDELINES = [
    {
        "title": "KDOQI-Hemodialysis-Adequacy-2015",
        "doi": "10.1053/j.ajkd.2015.07.015",
        "pmcid": "PMC7685340",
        "org": "KDOQI",
        "year": 2015,
        "topic": "ESRD/HD",
    },
    {
        "title": "KDOQI-Vascular-Access-2019",
        "doi": "10.1053/j.ajkd.2019.12.001",
        "pmcid": None,
        "org": "KDOQI",
        "year": 2019,
        "topic": "ESRD/HD",
    },
    {
        "title": "KDOQI-Nutrition-in-CKD-2020",
        "doi": "10.1053/j.ajkd.2020.05.006",
        "pmcid": "PMC7659899",
        "org": "KDOQI",
        "year": 2020,
        "topic": "CKD",
    },
    {
        "title": "KDOQI-Diabetes-and-CKD-2012",
        "doi": "10.1053/j.ajkd.2012.07.005",
        "pmcid": None,
        "org": "KDOQI",
        "year": 2012,
        "topic": "CKM",
    },
    {
        "title": "KDOQI-Peritoneal-Dialysis-Adequacy-2006",
        "doi": None,
        "pmcid": None,
        "direct_url": "https://www.kidney.org/sites/default/files/docs/12-50-0210_jag_dcp_guidelines-va_oct06_sectionc_ofc.pdf",
        "org": "KDOQI",
        "year": 2006,
        "topic": "PD",
    },
    {
        "title": "KDOQI-Anemia-2006",
        "doi": "10.1053/j.ajkd.2006.03.052",
        "pmcid": None,
        "org": "KDOQI",
        "year": 2006,
        "topic": "CKD",
    },
    {
        "title": "KDOQI-Bone-Metabolism-2003",
        "doi": "10.1016/S0272-6386(03)00941-X",
        "pmcid": None,
        "org": "KDOQI",
        "year": 2003,
        "topic": "CKD-MBD",
    },
    {
        "title": "KDOQI-Hypertension-and-Antihypertensive-Agents-in-CKD-2004",
        "doi": "10.1053/j.ajkd.2004.03.003",
        "pmcid": None,
        "org": "KDOQI",
        "year": 2004,
        "topic": "HTN",
    },
]


# ---------------------------------------------------------------------------
# Multi-source PDF download strategies
# ---------------------------------------------------------------------------

def try_direct_url(url: str, title: str) -> str | None:
    """Strategy 1: Direct URL download."""
    try:
        resp = SESSION.get(url, timeout=60, allow_redirects=True)
        resp.raise_for_status()
        if resp.content[:5] == b"%PDF-":
            return _save_temp(resp.content, title, "direct_url")
        ct = resp.headers.get("Content-Type", "")
        if "pdf" in ct:
            return _save_temp(resp.content, title, "direct_url")
        logger.warning("    direct_url: 回應不是 PDF (Content-Type: %s)", ct)
        return None
    except Exception as e:
        logger.debug("    direct_url 失敗: %s", e)
        return None


def try_europepmc(doi: str, title: str) -> str | None:
    """Strategy 2: Europe PMC — search by DOI, get OA full-text PDF."""
    try:
        # Search for the article
        search_url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:{doi}&format=json&resultType=core"
        resp = SESSION.get(search_url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("resultList", {}).get("result", [])

        for result in results:
            pmcid = result.get("pmcid")
            if pmcid:
                # Try to get PDF from PMC
                pdf_url = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf"
                pdf_resp = SESSION.get(pdf_url, timeout=60, allow_redirects=True)
                if pdf_resp.status_code == 200 and (pdf_resp.content[:5] == b"%PDF-" or "pdf" in pdf_resp.headers.get("Content-Type", "")):
                    return _save_temp(pdf_resp.content, title, f"europepmc/{pmcid}")
            # Check for OA full-text URLs
            ftx_list = result.get("fullTextUrlList", {}).get("fullTextUrl", [])
            for ftx in ftx_list:
                if ftx.get("documentStyle") == "pdf" and ftx.get("availabilityCode") == "OA":
                    pdf_resp = SESSION.get(ftx["url"], timeout=60, allow_redirects=True)
                    if pdf_resp.status_code == 200 and pdf_resp.content[:5] == b"%PDF-":
                        return _save_temp(pdf_resp.content, title, f"europepmc/oa")

        logger.debug("    europepmc: 找不到 OA PDF for DOI %s", doi)
        return None
    except Exception as e:
        logger.debug("    europepmc 失敗: %s", e)
        return None


def try_pmc_direct(pmcid: str, title: str) -> str | None:
    """Strategy 3: PubMed Central direct PDF download."""
    if not pmcid:
        return None
    try:
        pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
        resp = SESSION.get(pdf_url, timeout=60, allow_redirects=True)
        if resp.status_code == 200 and (resp.content[:5] == b"%PDF-" or "pdf" in resp.headers.get("Content-Type", "")):
            return _save_temp(resp.content, title, f"pmc/{pmcid}")
        logger.debug("    pmc_direct: 無法下載 %s", pmcid)
        return None
    except Exception as e:
        logger.debug("    pmc_direct 失敗: %s", e)
        return None


def try_unpaywall(doi: str, title: str) -> str | None:
    """Strategy 4: Unpaywall API — find OA version by DOI."""
    try:
        api_url = f"https://api.unpaywall.org/v2/{doi}?email={UNPAYWALL_EMAIL}"
        resp = SESSION.get(api_url, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # Try best_oa_location first
        best = data.get("best_oa_location")
        if best:
            pdf_url = best.get("url_for_pdf")
            if pdf_url:
                pdf_resp = SESSION.get(pdf_url, timeout=60, allow_redirects=True)
                if pdf_resp.status_code == 200 and pdf_resp.content[:5] == b"%PDF-":
                    return _save_temp(pdf_resp.content, title, "unpaywall/best_oa")

        # Try all OA locations
        for loc in data.get("oa_locations", []):
            pdf_url = loc.get("url_for_pdf")
            if pdf_url:
                pdf_resp = SESSION.get(pdf_url, timeout=60, allow_redirects=True)
                if pdf_resp.status_code == 200 and pdf_resp.content[:5] == b"%PDF-":
                    return _save_temp(pdf_resp.content, title, "unpaywall/oa_location")

        logger.debug("    unpaywall: 無 OA PDF for DOI %s", doi)
        return None
    except Exception as e:
        logger.debug("    unpaywall 失敗: %s", e)
        return None


def try_scihub_style_doi_redirect(doi: str, title: str) -> str | None:
    """Strategy 5: Try Elsevier's open access redirect (some DOIs resolve to free PDF)."""
    try:
        # Some Elsevier articles have open access PDFs via content redirect
        url = f"https://doi.org/{doi}"
        resp = SESSION.get(url, timeout=30, allow_redirects=True)
        # Check if we landed on a page with a PDF link
        if resp.status_code == 200 and resp.content[:5] == b"%PDF-":
            return _save_temp(resp.content, title, "doi_redirect")
        return None
    except Exception as e:
        logger.debug("    doi_redirect 失敗: %s", e)
        return None


def _save_temp(content: bytes, title: str, source: str) -> str:
    """Save PDF content to temp file."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, prefix=f"{title}_") as f:
        f.write(content)
        size_mb = len(content) / 1024 / 1024
        logger.info("    已下載: %s (%.1f MB) [來源: %s]", title, size_mb, source)
        return f.name


def download_pdf(guideline: dict) -> str | None:
    """Try multiple sources to download a guideline PDF."""
    title = guideline["title"]
    doi = guideline.get("doi")
    pmcid = guideline.get("pmcid")
    direct_url = guideline.get("direct_url")

    strategies = []

    # 1. Direct URL (if provided)
    if direct_url:
        strategies.append(("direct_url", lambda: try_direct_url(direct_url, title)))

    if doi:
        # 2. PMC direct (if PMCID known)
        if pmcid:
            strategies.append(("pmc_direct", lambda p=pmcid: try_pmc_direct(p, title)))

        # 3. Europe PMC (search by DOI, often has OA versions)
        strategies.append(("europepmc", lambda d=doi: try_europepmc(d, title)))

        # 4. Unpaywall (comprehensive OA finder)
        strategies.append(("unpaywall", lambda d=doi: try_unpaywall(d, title)))

        # 5. DOI redirect (sometimes leads to free PDF)
        strategies.append(("doi_redirect", lambda d=doi: try_scihub_style_doi_redirect(d, title)))

    for name, strategy_fn in strategies:
        logger.info("    嘗試 %s...", name)
        result = strategy_fn()
        if result:
            return result
        time.sleep(1)  # polite delay between attempts

    logger.error("    所有來源都無法下載 %s", title)
    return None


# ---------------------------------------------------------------------------
# Firebase Storage + Firestore
# ---------------------------------------------------------------------------

def upload_to_storage(local_path: str, title: str) -> str | None:
    """Upload PDF to Firebase Storage, return download URL."""
    try:
        blob_path = f"guideline_pdfs/{title}.pdf"
        blob = bucket.blob(blob_path)
        blob.upload_from_filename(local_path, content_type="application/pdf")
        blob.make_public()
        logger.info("    已上傳到 Storage: %s", blob_path)
        return blob.public_url
    except Exception as exc:
        logger.error("    上傳 Storage 失敗: %s", exc)
        return None


def create_book_doc(title: str, storage_url: str, meta: dict) -> str | None:
    """Create a document in the books collection."""
    try:
        doc_data = {
            "title": title,
            "url": storage_url,
            "type": "guideline",
            "status": "pending",
            "guideline_id": title,
            "version": str(meta.get("year", "")),
            "uploadedAt": firestore.SERVER_TIMESTAMP,
        }
        _, doc_ref = db.collection("books").add(doc_data)
        logger.info("    已建立 books doc: %s", doc_ref.id)
        return doc_ref.id
    except Exception as exc:
        logger.error("    建立 books doc 失敗: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(dry_run: bool = False) -> None:
    logger.info("=== 開始下載指引 (%d 部) ===", len(GUIDELINES))

    success = 0
    failed = 0

    for i, gl in enumerate(GUIDELINES, 1):
        title = gl["title"]
        doi = gl.get("doi", "無")
        logger.info("[%d/%d] %s (DOI: %s)", i, len(GUIDELINES), title, doi)

        # Check if already exists in books
        existing = list(
            db.collection("books")
            .where("title", "==", title)
            .limit(1)
            .stream()
        )
        if existing:
            logger.info("    已存在於 books collection，跳過")
            success += 1
            continue

        if dry_run:
            logger.info("    [DRY-RUN] 會嘗試下載")
            continue

        # Download with multi-source fallback
        local_path = download_pdf(gl)
        if not local_path:
            failed += 1
            continue

        try:
            storage_url = upload_to_storage(local_path, title)
            if not storage_url:
                failed += 1
                continue

            create_book_doc(title, storage_url, gl)
            success += 1
        finally:
            if os.path.exists(local_path):
                os.unlink(local_path)

    logger.info("=== 完成！成功 %d，失敗 %d ===", success, failed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="多來源自動下載指引 PDF 並上傳到 Firebase")
    parser.add_argument("--dry-run", action="store_true", help="只顯示，不下載")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
