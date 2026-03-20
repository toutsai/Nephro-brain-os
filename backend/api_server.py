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
import base64
import xml.etree.ElementTree as ET
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
        return response
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    return response

# --- API Keys ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("⚠️ GOOGLE_API_KEY 未設定，核心功能無法使用")

GEMINI_MODEL = "gemini-2.5-flash"
gemini_client = None
if GOOGLE_API_KEY:
    gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
    print(f"✅ Gemini API 已啟用 ({GEMINI_MODEL})")

# OpenAI（僅用於舊端點，可選）
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = None
if OPENAI_API_KEY:
    try:
        from openai import OpenAI
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        print("✅ OpenAI API 已啟用（僅舊端點用）")
    except ImportError:
        print("⚠️ openai 套件未安裝，跳過")

# Firebase（穩健初始化，確保 Cloud Run 也能啟動）
db = None
storage_bucket_obj = None

try:
    if not firebase_admin._apps:
        firebase_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
        if firebase_json and firebase_json.strip().startswith("{"):
            cred = credentials.Certificate(json.loads(firebase_json))
        else:
            cred_path = firebase_json or "serviceAccountKey.json"
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
            else:
                print(f"⚠️ 找不到 {cred_path}，嘗試預設憑證...")
                cred = credentials.ApplicationDefault()

        storage_bucket = os.getenv("FIREBASE_STORAGE_BUCKET")
        if storage_bucket:
            firebase_admin.initialize_app(cred, {'storageBucket': storage_bucket})
        else:
            firebase_admin.initialize_app(cred)

    db = firestore.client()
    print("✅ Firebase Firestore 已連線")

    try:
        storage_bucket_obj = storage.bucket()
        print("✅ Firebase Storage 已連線")
    except Exception as e:
        print(f"⚠️ Storage bucket 未連線: {e}")

except Exception as e:
    print(f"❌ Firebase 初始化失敗: {e}")
    print("  API 會啟動但資料庫功能不可用")

# 全域變數（FAISS 向量索引）
index = None
stored_chunks = []
processed_books = set()
deep_processed_books = set()
deleted_chunks_set = set()
memory_lock = threading.Lock()
last_memory_load = 0

BASE_PUBMED_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
INDEX_FILE = "nephro_brain.index"
DATA_FILE = "nephro_data.pkl"

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

def get_abstract_and_mesh(uid):
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
    if not gemini_client:
        return None
    try:
        result = gemini_client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=768)
        )
        if hasattr(result, 'embeddings') and result.embeddings:
            return result.embeddings[0].values
        return None
    except Exception as e:
        print(f"⚠️ Embedding error: {e}")
        return None


def download_memory():
    global index, stored_chunks, processed_books, deep_processed_books, deleted_chunks_set, last_memory_load

    if not storage_bucket_obj:
        print("⚠️ Storage bucket not connected, skip memory download")
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
                    deleted_chunks_set = data.get("deleted_chunks", set())

        last_memory_load = time.time()
        print(f"✅ 記憶載入: {len(stored_chunks)} chunks")
        return True
    except Exception as e:
        print(f"⚠️ 下載記憶失敗: {e}")
        return False


def ensure_memory_loaded():
    global last_memory_load
    if index is None or time.time() - last_memory_load > 300:
        download_memory()


def fetch_content_from_firestore(doc_ids):
    if not db:
        return []
    contents = []
    for doc_id in doc_ids:
        try:
            doc_ref = db.collection("knowledge_chunks").document(doc_id).get()
            if doc_ref.exists:
                data = doc_ref.to_dict()
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
    ensure_memory_loaded()

    found_ids = []
    with memory_lock:
        if index is not None and len(stored_chunks) > 0:
            q_vec = get_embedding(question)
            if q_vec:
                D, I = index.search(np.array([q_vec]).astype('float32'), k=10)
                for idx in I[0]:
                    if idx != -1 and idx < len(stored_chunks):
                        chunk_id = stored_chunks[idx]
                        if chunk_id not in deleted_chunks_set:
                            found_ids.append(chunk_id)

    if found_ids:
        chunks_text = fetch_content_from_firestore(found_ids)
        if chunks_text:
            return "\n".join(chunks_text)

    return "無教科書相關資料。"


# ============================================================
# 4. 核心問答引擎
# ============================================================

def generate_answer(question):
    if not gemini_client:
        return "❌ Gemini API 未設定，無法回答。"

    with ThreadPoolExecutor(max_workers=2) as executor:
        textbook_future = executor.submit(search_textbook, question)
        pubmed_future = executor.submit(search_pubmed, question)

        try:
            textbook_ctx = textbook_future.result(timeout=20)
        except:
            textbook_ctx = "無教科書資料（搜尋逾時）。"

        try:
            pubmed_ctx = pubmed_future.result(timeout=15) or "無 PubMed 結果。"
        except:
            pubmed_ctx = "無 PubMed 結果（搜尋逾時）。"

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
6. 全程使用繁體中文

【視覺化格式要求（重要）】：
- **摘要區塊**：回答最開頭用以下格式寫 3-5 點關鍵結論：
  :::summary
  - 結論一
  - 結論二
  - 結論三
  :::
- **比較表格**：凡涉及藥物比較、方案比較、優缺點對比，一律用 Markdown 表格呈現（| 欄位 | 欄位 |）
- **流程圖**：涉及診斷流程、治療決策樹、分級處理步驟時，用 mermaid 語法畫流程圖：
  ```mermaid
  graph TD
    A[起點] --> B{{決策}}
    B -->|是| C[處理A]
    B -->|否| D[處理B]
  ```
- 優先用視覺化方式呈現，減少純文字堆砌"""

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
4. 請用 Google Search 搜尋補充最新的臨床指引和實證
5. 開頭用摘要區塊列出 3-5 個最重要的臨床要點：
   :::summary
   - 要點一
   - 要點二
   :::
6. 藥物比較、劑量調整等用 Markdown 表格
7. 如有決策流程，用 mermaid 流程圖：
   ```mermaid
   graph TD
     A[起點] --> B{{決策}}
   ```"""

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
        "db_connected": db is not None,
        "storage_connected": storage_bucket_obj is not None,
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

    if db:
        try:
            books_stream = db.collection("books").stream()
            for book_doc in books_stream:
                data = book_doc.to_dict()
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


# ============================================================
# 5b. NB Teach 端點
# ============================================================

@app.route('/teach/generate', methods=['POST'])
def teach_generate():
    """NB Teach: 從文字或 PDF 生成摘要/Flashcards/大綱/心智圖"""
    data = request.get_json()
    text = data.get('text', '')
    file_url = data.get('file_url', '')
    mode = data.get('mode', 'all')

    if not text and not file_url:
        return jsonify({"error": "請提供學習素材（文字或檔案）"}), 400

    if not gemini_client:
        return jsonify({"error": "Gemini API 未設定"}), 500

    # 準備 Gemini 內容
    contents = []
    if file_url:
        try:
            print(f"🎓 下載 PDF: {file_url[:80]}...")
            pdf_resp = requests.get(file_url, timeout=60)
            pdf_resp.raise_for_status()
            pdf_bytes = pdf_resp.content
            print(f"  📄 PDF 大小：{len(pdf_bytes) / 1024:.0f} KB")

            contents.append({
                "inline_data": {
                    "mime_type": "application/pdf",
                    "data": base64.b64encode(pdf_bytes).decode("utf-8")
                }
            })
        except Exception as e:
            print(f"❌ PDF 下載失敗: {e}")
            return jsonify({"error": f"PDF 下載失敗: {e}"}), 500
    else:
        text = text[:15000]
        contents.append(text)

    print(f"🎓 /teach/generate: mode={mode}, source={'PDF' if file_url else 'text'}")

    result = {}

    try:
        if mode in ('summary', 'all'):
            result['summary'] = _teach_call(contents, TEACH_PROMPT_SUMMARY)

        if mode in ('flashcards', 'all'):
            raw = _teach_call(contents, TEACH_PROMPT_FLASHCARDS)
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()
            try:
                parsed = json.loads(cleaned)
                result['flashcards'] = json.dumps(parsed, ensure_ascii=False)
            except:
                result['flashcards'] = cleaned

        if mode in ('outline', 'all'):
            result['outline'] = _teach_call(contents, TEACH_PROMPT_OUTLINE)

        if mode in ('mindmap', 'all'):
            raw = _teach_call(contents, TEACH_PROMPT_MINDMAP)
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()
            try:
                parsed = json.loads(cleaned)
                result['mindmap'] = json.dumps(parsed, ensure_ascii=False)
            except:
                result['mindmap'] = cleaned

        return jsonify(result)

    except Exception as e:
        print(f"❌ Teach generate error: {e}")
        return jsonify({"error": str(e)}), 500


def _teach_call(contents, prompt_text):
    """呼叫 Gemini，contents 可以是文字或 PDF inline_data"""
    all_contents = contents + [prompt_text]
    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=all_contents,
    )
    return response.text


TEACH_PROMPT_SUMMARY = """你是一位醫學教育專家。請閱讀上面的學習素材，產生結構化摘要。

【輸出格式】（Markdown）：
# 核心摘要

## 關鍵概念
（列出 3-5 個最重要的概念，每個用 2-3 句話解釋）

## 重點整理
（條列式重點，使用 **粗體** 標示關鍵詞）

## 臨床應用
（如果是醫學內容，說明臨床意義）

## 一句話總結
（用一句話概括全文最核心的訊息）

全程使用繁體中文，醫學術語用「中文 (English)」格式。"""

TEACH_PROMPT_FLASHCARDS = """你是一位醫學教育專家。請根據上面的素材產生 10-15 張 Flashcards。

【要求】：
1. 每張卡片包含一個問題和答案
2. 問題要有臨床思考價值，不要死背型問題
3. 答案簡潔但完整（2-4 句話）
4. 涵蓋素材的核心概念
5. 全程繁體中文

【輸出格式】：純 JSON，不要 markdown 標記
[
  {"question": "問題1", "answer": "答案1"},
  {"question": "問題2", "answer": "答案2"}
]"""

TEACH_PROMPT_OUTLINE = """你是一位醫學教育專家。請為上面的素材產生一份學習大綱。

【輸出格式】（Markdown 縮排大綱）：

# 主題名稱

## 1. 第一大類
### 1.1 子項目
- 重點 a
- 重點 b
  - 細節

### 1.2 子項目
- 重點 c

## 2. 第二大類
### 2.1 子項目
- 重點 d

## 📝 學習建議
（根據內容給出 2-3 條學習建議）

## 🔗 延伸閱讀
（建議相關主題或搜尋方向）

全程使用繁體中文，醫學術語保留英文。大綱要有層次感，適合作為心智圖的基礎。"""

TEACH_PROMPT_MINDMAP = """你是一位醫學教育專家。請根據上面的素材產生一份心智圖結構。

【要求】：
1. 以 JSON 格式輸出，結構為樹狀節點
2. 根節點是主題名稱
3. 每個節點有 label（文字）和可選的 children（子節點陣列）
4. 最多 3 層深度
5. 每個大類 3-5 個子項目
6. 標籤簡潔（10 字以內）
7. 全程繁體中文，醫學術語保留英文

【輸出格式】：純 JSON，不要 markdown 標記
{
  "label": "主題名稱",
  "children": [
    {
      "label": "大類 1",
      "children": [
        {
          "label": "子項目 A",
          "children": [
            { "label": "細節 1" },
            { "label": "細節 2" }
          ]
        },
        { "label": "子項目 B" }
      ]
    },
    {
      "label": "大類 2",
      "children": [
        { "label": "子項目 C" },
        { "label": "子項目 D" }
      ]
    }
  ]
}"""


# === NB Assist 端點（加在 api_server.py 的 teach 端點後面）===

ASSIST_DISCLAIMER = "\n\n---\n> ⚠️ **免責聲明**：以上建議由 AI 根據實證醫學資料生成，僅供臨床參考。實際治療決策應由主治醫師根據完整病歷資訊做出判斷。所有藥物劑量請以最新藥典和院內處方集為準。"

@app.route('/assist/query', methods=['POST'])
def assist_query():
    """NB Assist: 臨床決策輔助（支援文字 + 圖片）"""
    data = request.get_json()
    mode = data.get('mode', '')
    images = data.get('images', [])  # [{ data: base64, mime_type: "image/jpeg" }, ...]

    if not mode:
        return jsonify({"error": "缺少 mode 參數"}), 400

    if not gemini_client:
        return jsonify({"error": "Gemini API 未設定"}), 500

    img_count = len(images) if images else 0
    print(f"🏥 /assist/query: mode={mode}, images={img_count}")

    try:
        if mode == 'clinical':
            result = _assist_clinical(data.get('scenario', ''), images)
        elif mode == 'dose':
            result = _assist_dose(data, images)
        elif mode == 'lab':
            result = _assist_lab(data.get('lab_data', ''), images)
        elif mode == 'nhi':
            result = _assist_nhi(data.get('query', ''), images)
        elif mode == 'interaction':
            result = _assist_interaction(data.get('drugs', ''), images)
        else:
            return jsonify({"error": f"不支援的模式: {mode}"}), 400

        return jsonify({"result": result})

    except Exception as e:
        print(f"❌ Assist error: {e}")
        return jsonify({"error": str(e)}), 500


def _build_image_parts(images):
    """將前端傳來的 base64 圖片轉成 Gemini 可讀的格式"""
    parts = []
    if not images:
        return parts
    for img in images:
        parts.append({
            "inline_data": {
                "mime_type": img.get("mime_type", "image/jpeg"),
                "data": img["data"]
            }
        })
    return parts


def _assist_clinical(scenario, images=None):
    """臨床情境 → 實證指引建議"""
    if not scenario and not images:
        return "❌ 請提供臨床情境描述或上傳圖片。"

    prompt = """你是一位資深腎臟科主治醫師，崇尚實證醫學 (EBM)。
請根據以下臨床情境（包含文字描述和/或圖片）提供結構化的臨床建議。
如果有圖片，請先仔細判讀圖片內容（可能是病歷、lab 報告、影像等），然後結合文字描述一起分析。

【請依照以下格式回答】（Markdown）：

## 🔍 臨床問題分析
（簡要整理關鍵問題，如果有圖片先描述圖片內容）

## 📋 鑑別診斷
（若適用，列出可能的診斷及其可能性）

## 📚 實證建議
（根據最新指引和實證，提供具體建議）
- 引用 KDIGO、KDOQI 或其他相關指引
- 附上實證等級（如果可以）

## 💊 藥物建議
（若涉及用藥，提供具體建議含劑量）

## ⚠️ 注意事項
（需要監測的指標、可能的風險）

## 🔄 後續追蹤
（建議的追蹤計劃）

全程使用繁體中文，醫學術語用「中文 (English)」格式。
請用 Google Search 搜尋補充最新的指引和實證。"""

    contents = []
    contents.extend(_build_image_parts(images))
    if scenario:
        contents.append(f"【臨床情境】\n{scenario}")
    contents.append(prompt)

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )
    )
    return response.text + ASSIST_DISCLAIMER


def _assist_dose(data, images=None):
    """藥物劑量調整"""
    drug = data.get('drug', '')
    egfr = data.get('egfr', '')
    ckd_stage = data.get('ckd_stage', '')
    weight = data.get('weight', '')
    extra = data.get('extra', '')

    if not drug and not images:
        return "❌ 請提供藥物名稱或上傳處方圖片。"

    prompt = f"""你是一位臨床藥學專家，專精腎臟病藥物劑量調整。
請提供藥物在腎功能不全時的劑量調整建議。
如果有圖片，請先判讀圖片內容（可能是處方單、藥物資訊等），提取藥物名稱和相關資訊。

【藥物】{drug if drug else '（請從圖片判讀）'}
【eGFR】{egfr if egfr else '未提供'} mL/min/1.73m²
【CKD Stage】{ckd_stage if ckd_stage else '未提供（請根據 eGFR 判斷）'}
【體重】{weight if weight else '未提供'} kg
【其他備註】{extra if extra else '無'}

【請依照以下格式回答】（Markdown）：

## 💊 藥物腎功能劑量調整

### 藥物基本資訊
| 項目 | 內容 |
|------|------|
| 學名 | |
| 藥理分類 | |
| 主要排除途徑 | |
| 蛋白結合率 | |
| 是否可透析清除 | |

### 劑量建議
| CKD Stage | eGFR 範圍 | 建議劑量 | 頻次 |
|-----------|-----------|----------|------|
| 1-2 | ≥60 | | |
| 3a-3b | 30-59 | | |
| 4 | 15-29 | | |
| 5 | <15 | | |
| 5D (HD) | 透析中 | | |
| 5D (PD) | 腹膜透析 | | |
| CRRT | | | |

### 📍 針對此病人的建議
### ⚠️ 監測項目
### 📚 參考來源

全程使用繁體中文，藥物名稱保留英文。
請用 Google Search 搜尋最新的藥物劑量調整資訊。"""

    contents = []
    contents.extend(_build_image_parts(images))
    contents.append(prompt)

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )
    )
    return response.text + ASSIST_DISCLAIMER


def _assist_lab(lab_data, images=None):
    """Lab 鑑別診斷"""
    if not lab_data and not images:
        return "❌ 請提供檢驗數據或上傳 lab 報告圖片。"

    prompt = """你是一位資深腎臟科主治醫師。
請根據以下檢驗數據進行鑑別診斷分析。
如果有圖片，請先仔細判讀圖片中的所有檢驗數值，列出完整的數據，然後進行分析。

【請依照以下格式回答】（Markdown）：

## 📊 圖片判讀結果（如有圖片）
（列出從圖片中讀取到的所有檢驗數值）

## 🔬 檢驗異常摘要
（哪些數值異常？正常範圍對照）

## 📋 鑑別診斷（依可能性排序）

### 1. 最可能：[診斷名稱]
- **支持證據**：哪些 lab data 支持
- **機轉**：簡要說明病理機轉
- **需進一步檢查**：建議追加的檢驗或檢查

### 2. 次可能：[診斷名稱]
- **支持證據**：
- **機轉**：
- **需進一步檢查**：

### 3. 需排除：[診斷名稱]

## 🔍 建議追加檢查
## 💡 臨床珍珠

全程使用繁體中文，醫學術語用「中文 (English)」格式。
請用 Google Search 搜尋最新的診斷指引。"""

    contents = []
    contents.extend(_build_image_parts(images))
    if lab_data:
        contents.append(f"【檢驗數據 / 臨床資訊】\n{lab_data}")
    contents.append(prompt)

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )
    )
    return response.text + ASSIST_DISCLAIMER


def _assist_nhi(query_text, images=None):
    """台灣健保給付規則查詢"""
    if not query_text and not images:
        return "❌ 請提供要查詢的藥物或治療項目。"

    prompt = """你是一位熟悉台灣全民健康保險制度的腎臟科專家。
請根據以下查詢，提供台灣健保給付的相關規定。
如果有圖片，請先判讀圖片內容。

【重要】：請用 Google Search 搜尋「台灣健保 藥品給付規定」、「衛生福利部中央健康保險署」等關鍵字，取得最新的給付規範。

【請依照以下格式回答】（Markdown）：

## 🏛️ 健保給付查詢結果

### 藥品/項目基本資訊
| 項目 | 內容 |
|------|------|
| 健保代碼 | （如能查到）|
| 給付分類 | |
| 適應症 | |

### 📋 給付條件
（詳列健保給付的適應症、條件、限制）

### ⚠️ 事前審查 / 特殊規定
（是否需要事前審查？需要哪些文件？排除條件？）

### 💰 給付限制
（用量限制、療程限制、共同負擔等）

### 📝 申請流程
（如需事前審查，說明申請步驟）

### 📚 參考依據
（引用健保署公告文號或相關法規）

全程使用繁體中文。
如果查不到確切的健保規定，請明確說明並建議查詢管道（如健保署網站、院內藥事委員會等）。"""

    contents = []
    contents.extend(_build_image_parts(images))
    if query_text:
        contents.append(f"【查詢內容】\n{query_text}")
    contents.append(prompt)

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )
    )
    return response.text + ASSIST_DISCLAIMER


def _assist_interaction(drugs_text, images=None):
    """藥物交互作用檢查"""
    if not drugs_text and not images:
        return "❌ 請提供藥物列表或上傳處方圖片。"

    prompt = """你是一位臨床藥學專家，專精腎臟病患者的用藥安全。
請檢查以下藥物之間的交互作用。
如果有圖片，請先從圖片中判讀所有藥物名稱和劑量。

【請依照以下格式回答】（Markdown）：

## ⚡ 藥物交互作用檢查報告

### 📋 藥物清單
（列出所有要檢查的藥物及劑量）

### 🔴 嚴重交互作用（需立即處理）
（如有，列出每一對有嚴重交互作用的藥物）
- **藥物 A + 藥物 B**
  - 交互作用機轉
  - 臨床後果
  - 建議處置

### 🟡 中度交互作用（需注意監測）
- **藥物 C + 藥物 D**
  - 交互作用機轉
  - 監測建議

### 🟢 輕度交互作用（知道就好）

### 🔬 腎功能相關注意事項
（針對腎臟病患者的特殊考量：腎排除藥物、腎毒性疊加等）

### 💡 用藥建議
（整體用藥安全建議、時間間隔建議等）

### 📚 參考來源

全程使用繁體中文，藥物名稱保留英文。
請用 Google Search 搜尋最新的藥物交互作用資訊。"""

    contents = []
    contents.extend(_build_image_parts(images))
    if drugs_text:
        contents.append(f"【藥物列表】\n{drugs_text}")
    contents.append(prompt)

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )
    )
    return response.text + ASSIST_DISCLAIMER


# ============================================================
# 6. 舊端點（向下相容 nephro-brain-web）
# ============================================================

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


def serialize_value(value):
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
    if not db:
        return jsonify({"articles": [], "error": "DB not connected"})

    articles = []
    topic_articles = []
    journal_articles = []
    hd_selected = []
    crawler_status = None
    last_update = None

    try:
        unified_ref = db.collection("articles_unified")
        unified_docs = unified_ref.order_by("crawled_at", direction=firestore.Query.DESCENDING).limit(200).stream()
        for unified_doc in unified_docs:
            data = unified_doc.to_dict()
            item = serialize_doc(unified_doc.id, data)
            source = data.get("source", "")
            if source in ("daily_crawler", "general"):
                articles.append(item)
            elif source == "topic_crawler":
                topic_articles.append(item)
            elif source == "journal_issue_crawler":
                journal_articles.append(item)
            elif source == "hd_selected":
                hd_selected.append(item)

        runs = db.collection("crawler_runs").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(1).stream()
        for run_doc in runs:
            data = run_doc.to_dict()
            crawler_status = serialize_doc(run_doc.id, data)
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
        "has_db": db is not None,
        "has_storage": storage_bucket_obj is not None,
    })


@app.route('/journals', methods=['GET'])
def get_journals():
    return jsonify({"journals": list(TARGET_JOURNALS.keys())})


def ask_gemini_journal_summary(title, abstract_text, max_retries=3):
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


def search_pubmed_articles(query_text, years=5, max_results=5):
    try:
        search_url = f"{BASE_PUBMED_URL}esearch.fcgi?db=pubmed&term={query_text}&retmode=json&retmax={max_results}&sort=relevance"
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
    if not db:
        return jsonify({"error": "DB not connected"}), 500
    cleaned = 0
    try:
        cache_docs = db.collection("abstract_cache").stream()
        for cache_doc in cache_docs:
            data = cache_doc.to_dict()
            content = data.get("content", "")
            if not content or len(content) < 20 or "```json" in content:
                cache_doc.reference.delete()
                cleaned += 1
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"cleaned": cleaned})


@app.route('/clean-bad-articles', methods=['POST'])
def clean_bad_articles():
    if not db:
        return jsonify({"error": "DB not connected"}), 500
    cleaned = 0
    try:
        for coll_name in ["articles_unified"]:
            article_docs = db.collection(coll_name).stream()
            for article_doc in article_docs:
                data = article_doc.to_dict()
                title_zh = data.get("title_zh", "")
                if not title_zh or "```" in title_zh or len(title_zh) < 5:
                    article_doc.reference.delete()
                    cleaned += 1
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"cleaned": cleaned})


@app.route('/generate-article-summary', methods=['POST'])
def generate_article_summary():
    data = request.get_json()
    pmid = data.get('pmid', '')
    title = data.get('title', '')

    if not pmid and not title:
        return jsonify({"error": "缺少 pmid 或 title"}), 400

    if not gemini_client:
        return jsonify({"error": "Gemini API 未設定"}), 500

    try:
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

        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        result_text = response.text.strip()

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

# Gunicorn 啟動時也載入記憶（不只 __main__）
print("🚀 Nephro Brain API Server v2 初始化中...")
print(f"🤖 模型：{GEMINI_MODEL}")
download_memory()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)