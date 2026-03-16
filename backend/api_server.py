"""
Nephro Brain API Server v2 (重構版)
- 只依賴 Gemini 2.5 Flash（拿掉 Perplexity + OpenAI）
- Google Search grounding 取代 Perplexity 網路搜尋
- Embedding 原生支援中文，不再額外翻譯
- CORS 修正、timeout 保護、完整 error logging
- 保留所有舊端點（向下相容 nephro-brain-web）
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore, storage
from google import genai
from google.genai import types
import faiss
import numpy as np
import requests
import os
import time
import pickle
import threading
import json
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import gc
from datetime import datetime

# ============================================================
# 1. 設定區
# ============================================================
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization"]}})

@app.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Headers'] = request.headers.get(
            'Access-Control-Request-Headers', 'Content-Type,Authorization'
        )
        response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
        return response

@app.after_request
def after_request(response):
    if request.method == 'OPTIONS':
        return response  # 已在 handle_preflight 處理，避免重複 header
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    return response

# --- API Keys ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("⚠️ GOOGLE_API_KEY 未設定，核心功能無法使用")

# Gemini 2.5 Flash — 唯一的 AI 依賴
GEMINI_MODEL = "gemini-2.5-flash"
gemini_client = None
if GOOGLE_API_KEY:
    gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
    print(f"✅ Gemini API 已啟用 ({GEMINI_MODEL})")

# OpenAI（僅用於舊端點 /generate-article-summary，可選）
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = None
if OPENAI_API_KEY:
    from openai import OpenAI
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    print("✅ OpenAI API 已啟用（僅舊端點用）")

# Firebase
if not firebase_admin._apps:
    firebase_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if firebase_json and firebase_json.strip().startswith("{"):
        cred = credentials.Certificate(json.loads(firebase_json))
    else:
        cred_path = firebase_json or "serviceAccountKey.json"
        if not os.path.exists(cred_path):
            print(f"⚠️ 找不到 {cred_path}，嘗試預設憑證...")
            cred = credentials.ApplicationDefault()
        else:
            cred = credentials.Certificate(cred_path)

    storage_bucket = os.getenv("FIREBASE_STORAGE_BUCKET")
    if storage_bucket:
        firebase_admin.initialize_app(cred, {'storageBucket': storage_bucket})
    else:
        firebase_admin.initialize_app(cred)

db = firestore.client()
storage_bucket_obj = None
try:
    storage_bucket_obj = storage.bucket()
except:
    pass

# 全域變數（FAISS 向量索引）
index = None
stored_chunks = []
processed_books = set()
deep_processed_books = set()
memory_lock = threading.Lock()
last_memory_load = 0

BASE_PUBMED_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
INDEX_FILE = "nephro_brain.index"
DATA_FILE = "nephro_data.pkl"

# 期刊設定
TARGET_JOURNALS = {
    "JASN": '"J Am Soc Nephrol"[Journal]',
    "CJASN": '"Clin J Am Soc Nephrol"[Journal]',
    "Kidney Int": '"Kidney Int"[Journal]',
    "Nat Rev Nephrol": '"Nat Rev Nephrol"[Journal]',
    "NEJM": '"N Engl J Med"[Journal] AND (Kidney OR Renal OR Dialysis)',
    "Lancet": '"Lancet"[Journal] AND (Kidney OR Renal OR Dialysis)',
    "JAMA": '"JAMA"[Journal] AND (Kidney OR Renal OR Dialysis)'
}


# ============================================================
# 2. 工具函式
# ============================================================

import xml.etree.ElementTree as ET

def get_abstract_and_mesh(uid):
    """從 PubMed 取得摘要和 MeSH 標籤"""
    try:
        fetch_url = f"{BASE_PUBMED_URL}efetch.fcgi?db=pubmed&id={uid}&rettype=xml"
        resp = requests.get(fetch_url, timeout=10)
        root = ET.fromstring(resp.content)
        article = root.find('.//PubmedArticle')
        if article is None:
            return None, []

        abstract_el = article.find('.//AbstractText')
        abstract_text = abstract_el.text if abstract_el is not None else ""

        mesh_terms = []
        for mesh in article.findall('.//MeshHeading/DescriptorName'):
            if mesh.text:
                mesh_terms.append(mesh.text)

        return abstract_text, mesh_terms
    except Exception as e:
        print(f"⚠️ PubMed fetch error for {uid}: {e}")
        return None, []


def get_embedding(text):
    """Gemini text-embedding-004（原生支援中文，不需翻譯）"""
    if not gemini_client:
        return None
    try:
        result = gemini_client.models.embed_content(
            model="text-embedding-004",
            contents=text
        )
        if hasattr(result, 'embeddings') and result.embeddings:
            return result.embeddings[0].values
        return None
    except Exception as e:
        print(f"⚠️ Embedding error: {e}")
        return None


def download_memory():
    """從 Firebase Storage 下載 FAISS 索引"""
    global index, stored_chunks, processed_books, deep_processed_books, last_memory_load

    if not storage_bucket_obj:
        print("⚠️ Storage bucket not connected")
        return False

    try:
        blob_index = storage_bucket_obj.blob(f"brain_memory/{INDEX_FILE}")
        if not blob_index.exists():
            print("⚠️ Index file not found in storage")
            return False
        blob_index.download_to_filename(INDEX_FILE)

        blob_data = storage_bucket_obj.blob(f"brain_memory/{DATA_FILE}")
        if blob_data.exists():
            blob_data.download_to_filename(DATA_FILE)

        with memory_lock:
            if os.path.exists(INDEX_FILE):
                index = faiss.read_index(INDEX_FILE)

            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, "rb") as f:
                    data = pickle.load(f)
                    stored_chunks = data.get("chunks", [])
                    processed_books = data.get("books", set())
                    deep_processed_books = data.get("deep_books", set())

        last_memory_load = time.time()
        print(f"✅ 記憶載入: {len(stored_chunks)} chunks")
        return True
    except Exception as e:
        print(f"⚠️ 下載記憶失敗: {e}")
        return False


def ensure_memory_loaded():
    """每 5 分鐘重整一次記憶"""
    global last_memory_load
    if index is None or time.time() - last_memory_load > 300:
        download_memory()


def fetch_content_from_firestore(doc_ids):
    """從 Firestore 抓取知識片段文字"""
    contents = []
    for doc_id in doc_ids:
        try:
            doc = db.collection("knowledge_chunks").document(doc_id).get()
            if doc.exists:
                data = doc.to_dict()
                text = data.get('text', '')
                source = data.get('source', 'Unknown')
                if text:
                    contents.append(f"[來源: {source}] {text[:500]}...")
        except Exception as e:
            print(f"⚠️ Firestore fetch error for {doc_id}: {e}")
    return contents


# ============================================================
# 3. 搜尋功能
# ============================================================

def search_pubmed(query):
    """PubMed 文獻搜尋（免費）"""
    try:
        search_url = f"{BASE_PUBMED_URL}esearch.fcgi?db=pubmed&term={query}&retmode=json&retmax=5&sort=date"
        resp = requests.get(search_url, timeout=10).json()
        id_list = resp.get('esearchresult', {}).get('idlist', [])
        if not id_list:
            return ""

        ids_str = ",".join(id_list)
        summary_url = f"{BASE_PUBMED_URL}esummary.fcgi?db=pubmed&id={ids_str}&retmode=json"
        summary_data = requests.get(summary_url, timeout=10).json()

        ctx = ""
        for uid in id_list:
            if uid in summary_data.get('result', {}):
                p = summary_data['result'][uid]
                ctx += f"[標題]: {p.get('title','')}\n[來源]: {p.get('source','')} ({p.get('pubdate','')})\n[連結]: https://pubmed.ncbi.nlm.nih.gov/{uid}/\n---\n"
        return ctx
    except Exception as e:
        print(f"⚠️ PubMed 搜尋失敗: {e}")
        return ""


def search_textbook(question):
    """FAISS 向量搜尋教科書（直接用中文，不需翻譯）"""
    ensure_memory_loaded()

    found_ids = []
    with memory_lock:
        if index is not None and len(stored_chunks) > 0:
            q_vec = get_embedding(question)
            if q_vec:
                D, I = index.search(np.array([q_vec]).astype('float32'), k=10)
                for idx in I[0]:
                    if idx != -1 and idx < len(stored_chunks):
                        found_ids.append(stored_chunks[idx])

    if found_ids:
        chunks_text = fetch_content_from_firestore(found_ids)
        if chunks_text:
            return "\n".join(chunks_text)

    return "無教科書相關資料。"


# ============================================================
# 4. 核心問答引擎（重構版）
# ============================================================

def generate_answer(question):
    """
    重構版問答流程（2 次 Gemini API）：
    1. Embedding 搜尋教科書 + PubMed（平行）
    2. Gemini 2.5 Flash + Google Search grounding 生成回答

    舊版需要 4-5 次 API：翻譯 + embedding×2 + Perplexity + 生成
    """
    if not gemini_client:
        return "❌ Gemini API 未設定，無法回答。"

    # Step 1: 平行搜尋（教科書 + PubMed）
    with ThreadPoolExecutor(max_workers=2) as executor:
        textbook_future = executor.submit(search_textbook, question)
        pubmed_future = executor.submit(search_pubmed, question)

        try:
            textbook_ctx = textbook_future.result(timeout=20)
        except Exception as e:
            print(f"⚠️ 教科書搜尋逾時: {e}")
            textbook_ctx = "無教科書資料（搜尋逾時）。"

        try:
            pubmed_ctx = pubmed_future.result(timeout=15) or "無 PubMed 結果。"
        except Exception as e:
            print(f"⚠️ PubMed 搜尋逾時: {e}")
            pubmed_ctx = "無 PubMed 結果（搜尋逾時）。"

    # Step 2: Gemini 2.5 Flash + Google Search（一次搞定生成+網路搜尋）
    prompt = f"""你是一位崇尚「實證醫學 (EBM)」的腎臟科專家。

【教科書知識庫】
{textbook_ctx}

【PubMed 文獻】
{pubmed_ctx}

【問題】：{question}

【要求】：
1. 結構化回答：教科書觀點、最新實證、臨床指引、綜合建議
2. 如果教科書和 PubMed 資料不足，請用 Google Search 搜尋補充最新證據
3. 使用 Markdown 格式
4. 醫學術語用「中文 (English)」格式
5. 引用文獻時附上連結
6. 全程使用繁體中文"""

    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            )
        )
        return response.text
    except Exception as e:
        print(f"❌ Gemini 生成失敗: {e}")
        return f"❌ 生成失敗: {e}"


def generate_cheat_sheet(topic):
    """懶人包生成（同樣用 Google Search grounding）"""
    if not gemini_client:
        return "❌ Gemini API 未設定。"

    textbook_ctx = search_textbook(topic)

    prompt = f"""請為 "{topic}" 製作一份 **單頁臨床懶人包**。

【教科書資料】
{textbook_ctx}

【格式要求】：
1. 使用 Markdown，大量使用 **粗體** 和表格
2. 包含：🩺 適應症與機制、💊 劑量調整、⚠️ 禁忌症與副作用、📚 最新實證、💡 臨床珍珠
3. 繁體中文，術語用「中文 (English)」格式
4. 請用 Google Search 搜尋補充最新的臨床指引和實證"""

    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            )
        )
        return response.text
    except Exception as e:
        return f"❌ 生成失敗: {e}"


# ============================================================
# 5. API 端點
# ============================================================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "version": "v2",
        "model": GEMINI_MODEL,
        "chunks_count": len(stored_chunks),
    })


@app.route('/ask', methods=['POST'])
def ask():
    data = request.get_json()
    question = data.get('question', '')

    if not question:
        return jsonify({"error": "請提供問題"}), 400

    print(f"💬 /ask: {question[:60]}...")

    if question.startswith("懶人包") or question.lower().startswith("cheat sheet"):
        topic = question.replace("懶人包", "").replace("cheat sheet", "").replace(":", "").replace("：", "").strip()
        if topic:
            answer = generate_cheat_sheet(topic)
        else:
            answer = "❌ 請提供懶人包主題，例如：「懶人包：SGLT2 inhibitor」"
    else:
        answer = generate_answer(question)

    return jsonify({"answer": answer})


@app.route('/stats', methods=['GET'])
def stats():
    ensure_memory_loaded()

    total_books = 0
    ready_books = 0
    pending_books = 0
    error_books = 0

    try:
        books = db.collection("books").stream()
        for doc in books:
            data = doc.to_dict()
            total_books += 1
            status = data.get("status", "pending")
            if status == "ready":
                ready_books += 1
            elif status in ("pending", "processing"):
                pending_books += 1
            elif status == "error":
                error_books += 1
    except Exception as e:
        print(f"⚠️ Stats error: {e}")

    return jsonify({
        "memory_chunks_ids": len(stored_chunks),
        "books_quick": len(processed_books),
        "books_deep": len(deep_processed_books),
        "total_books": total_books,
        "ready_books": ready_books,
        "pending_books": pending_books,
        "error_books": error_books,
        "total_chunks": len(stored_chunks),
    })


@app.route('/process-book', methods=['POST'])
def process_book_endpoint():
    return jsonify({
        "error": "雲端 PDF 處理已停用。",
        "message": "請使用 'python local_pdf_processor.py' 在本地處理。"
    }), 403


@app.route('/process-all-pending', methods=['POST'])
def process_all_pending():
    return jsonify({
        "error": "雲端 PDF 處理已停用。",
        "message": "請使用 'python local_pdf_processor.py --all' 在本地處理。"
    }), 403


# ============================================================
# 6. 舊端點（向下相容 nephro-brain-web）
# ============================================================

def serialize_value(value):
    """序列化 Firestore 值"""
    try:
        from google.cloud.firestore_v1._helpers import DatetimeWithNanoseconds
        if isinstance(value, DatetimeWithNanoseconds):
            return value.isoformat()
    except:
        pass
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [serialize_value(v) for v in value]
    if isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}
    return value


def serialize_doc(doc_id, data):
    return {**{k: serialize_value(v) for k, v in data.items()}, "id": doc_id}


@app.route('/public-feed', methods=['GET'])
def public_feed():
    """舊前端公開資料（nephro-brain-web 用）"""
    articles = []
    topic_articles = []
    journal_articles = []
    hd_selected = []
    crawler_status = None
    last_update = None

    try:
        # 統一集合
        unified_ref = db.collection("articles_unified")
        unified_docs = unified_ref.order_by("crawled_at", direction=firestore.Query.DESCENDING).limit(200).stream()
        for doc in unified_docs:
            data = doc.to_dict()
            item = serialize_doc(doc.id, data)
            source = data.get("source", "")
            if source in ("daily_crawler", "general"):
                articles.append(item)
            elif source == "topic_crawler":
                topic_articles.append(item)
            elif source == "journal_issue_crawler":
                journal_articles.append(item)
            elif source == "hd_selected":
                hd_selected.append(item)

        # 爬蟲狀態
        runs = db.collection("crawler_runs").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(1).stream()
        for doc in runs:
            data = doc.to_dict()
            crawler_status = serialize_doc(doc.id, data)
            ts = data.get("timestamp")
            if ts:
                last_update = ts.isoformat() if hasattr(ts, 'isoformat') else str(ts)
    except Exception as e:
        print(f"⚠️ public-feed error: {e}")

    return jsonify({
        "articles": articles,
        "topic_articles": topic_articles,
        "journal_articles": journal_articles,
        "hd_selected": hd_selected,
        "crawler_status": crawler_status,
        "last_update": last_update,
    })


@app.route('/debug', methods=['GET'])
def debug():
    return jsonify({
        "gemini_model": GEMINI_MODEL,
        "memory_chunks": len(stored_chunks),
        "books_quick": len(processed_books),
        "books_deep": len(deep_processed_books),
        "has_index": index is not None,
        "has_gemini": gemini_client is not None,
        "has_openai": openai_client is not None,
    })


@app.route('/journals', methods=['GET'])
def get_journals():
    return jsonify({"journals": list(TARGET_JOURNALS.keys())})


def ask_gemini_journal_summary(title, abstract_text, max_retries=3):
    """期刊文章摘要（舊端點用）"""
    if not gemini_client:
        return None

    prompt = f"""請用繁體中文摘要以下醫學文章：
標題：{title}
摘要：{abstract_text or '無摘要'}

請提供：
1. title_zh: 中文標題
2. abstract_zh: 中文摘要（2-3 句）
3. pearl: 臨床珍珠（1 句重點）"""

    for attempt in range(max_retries):
        try:
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt
            )
            return response.text
        except Exception as e:
            print(f"⚠️ 期刊摘要失敗 (attempt {attempt+1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
    return None


def extract_search_keywords(title):
    """從標題提取搜尋關鍵字"""
    if not gemini_client:
        return title[:100]
    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=f"Extract 3-5 key medical search terms from this title. Return only the terms separated by spaces, no explanation:\n{title}"
        )
        return response.text.strip()
    except:
        return title[:100]


def search_pubmed_articles(query, years=5, max_results=5):
    """PubMed 搜尋文章（舊端點用）"""
    try:
        search_url = f"{BASE_PUBMED_URL}esearch.fcgi?db=pubmed&term={query}&retmode=json&retmax={max_results}&sort=relevance"
        resp = requests.get(search_url, timeout=10).json()
        id_list = resp.get('esearchresult', {}).get('idlist', [])
        if not id_list:
            return []

        ids_str = ",".join(id_list)
        summary_url = f"{BASE_PUBMED_URL}esummary.fcgi?db=pubmed&id={ids_str}&retmode=json"
        summary_data = requests.get(summary_url, timeout=10).json()

        results = []
        for uid in id_list:
            if uid in summary_data.get('result', {}):
                p = summary_data['result'][uid]
                results.append({
                    "pmid": uid,
                    "title": p.get("title", ""),
                    "source": p.get("source", ""),
                    "pubdate": p.get("pubdate", ""),
                    "link": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/"
                })
        return results
    except:
        return []


@app.route('/fetch-journal-issue', methods=['POST'])
def fetch_journal_issue():
    data = request.get_json()
    journal_tag = data.get('journal', '')
    if not journal_tag or journal_tag not in TARGET_JOURNALS:
        return jsonify({"error": f"不支援的期刊: {journal_tag}"}), 400

    try:
        search_query = TARGET_JOURNALS[journal_tag]
        search_url = f"{BASE_PUBMED_URL}esearch.fcgi?db=pubmed&term={search_query}&retmode=json&retmax=10&sort=date"
        resp = requests.get(search_url, timeout=10).json()
        id_list = resp.get('esearchresult', {}).get('idlist', [])

        if not id_list:
            return jsonify({"articles": [], "message": "無最新文章"})

        ids_str = ",".join(id_list)
        summary_url = f"{BASE_PUBMED_URL}esummary.fcgi?db=pubmed&id={ids_str}&retmode=json"
        summary_data = requests.get(summary_url, timeout=10).json()

        articles = []
        for uid in id_list:
            if uid in summary_data.get('result', {}):
                p = summary_data['result'][uid]
                articles.append({
                    "pmid": uid,
                    "title": p.get("title", ""),
                    "source": p.get("source", ""),
                    "pubdate": p.get("pubdate", ""),
                    "link": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                })

        return jsonify({"articles": articles, "journal": journal_tag})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/search-related', methods=['POST'])
def search_related():
    data = request.get_json()
    title = data.get('title', '')
    if not title:
        return jsonify({"error": "缺少 title"}), 400

    keywords = extract_search_keywords(title)
    results = search_pubmed_articles(keywords, max_results=10)
    return jsonify({"articles": results, "keywords": keywords})


@app.route('/clean-bad-cache', methods=['POST'])
def clean_bad_cache():
    """清除格式錯誤的快取"""
    cleaned = 0
    try:
        docs = db.collection("abstract_cache").stream()
        for doc in docs:
            data = doc.to_dict()
            content = data.get("content", "")
            if not content or len(content) < 20 or "```json" in content:
                doc.reference.delete()
                cleaned += 1
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"cleaned": cleaned})


@app.route('/clean-bad-articles', methods=['POST'])
def clean_bad_articles():
    """清除格式錯誤的文章"""
    cleaned = 0
    try:
        for coll_name in ["articles_unified"]:
            docs = db.collection(coll_name).stream()
            for doc in docs:
                data = doc.to_dict()
                title_zh = data.get("title_zh", "")
                if not title_zh or "```" in title_zh or len(title_zh) < 5:
                    doc.reference.delete()
                    cleaned += 1
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"cleaned": cleaned})


@app.route('/generate-article-summary', methods=['POST'])
def generate_article_summary():
    """文章詳細摘要（舊端點，優先用 Gemini，fallback OpenAI）"""
    data = request.get_json()
    pmid = data.get('pmid', '')
    title = data.get('title', '')

    if not pmid and not title:
        return jsonify({"error": "缺少 pmid 或 title"}), 400

    try:
        # 取得摘要
        abstract_text = ""
        if pmid:
            abstract_text, mesh_terms = get_abstract_and_mesh(pmid)

        prompt = f"""請分析以下醫學文章並以 JSON 格式回覆：

標題：{title}
摘要：{abstract_text or '無摘要'}
PMID：{pmid}

回覆格式（純 JSON，不要 markdown）：
{{
  "title_zh": "中文標題",
  "summary": "2-3 句中文摘要",
  "pico": {{
    "population": "族群",
    "intervention": "介入",
    "comparison": "對照",
    "outcome": "結局"
  }},
  "key_results": "主要結果（含數字）",
  "clinical_pearl": "臨床珍珠",
  "limitations": "主要限制",
  "tags": ["標籤1", "標籤2"]
}}"""

        # 優先用 Gemini
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        result_text = response.text.strip()

        # 清理 markdown 標記
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[1] if "\n" in result_text else result_text
        if result_text.endswith("```"):
            result_text = result_text[:-3]
        result_text = result_text.strip()

        result = json.loads(result_text)
        return jsonify({"success": True, "data": result})

    except Exception as e:
        print(f"❌ generate-article-summary error: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================
# 7. 啟動
# ============================================================

if __name__ == "__main__":
    print("🚀 啟動 Nephro Brain API Server v2...")
    print(f"🤖 模型：{GEMINI_MODEL}")
    print(f"🔧 Google Search grounding 已啟用")
    download_memory()

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
