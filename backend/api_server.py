"""
Nephro Brain API Server v2 (重構版)
- 只依賴 Gemini 2.5 Flash（拿掉 Perplexity + OpenAI）
- Google Search grounding 取代 Perplexity 網路搜尋
- Embedding 原生支援中文，不再額外翻譯
- CORS 修正、timeout 保護、完整 error logging
- 保留所有舊端點（向下相容 nephro-brain-web）
"""

from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore, storage, auth as firebase_auth
from google import genai
from google.genai import types
import faiss
import numpy as np
import requests
import os
import io
import time
import pickle
import threading
import json
import base64
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from functools import wraps
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

# --- OpenEvidence Client ---
oe_client = None
oe_cookie_mgr = None

# ============================================================
# Model Routing Configuration
# ============================================================

MODEL_CONFIG = {
    "gemini-flash": {
        "model": "gemini-2.5-flash",
        "description": "快速回應，適合結構化輸出",
        "cost": "low",
    },
    "gemini-pro": {
        "model": "gemini-2.5-pro",
        "description": "深度推理，適合複雜臨床問題",
        "cost": "high",
    },
}

# 場景 → 模型映射
MODEL_ROUTING = {
    "consult_simple": "gemini-flash",
    "consult_complex": "gemini-pro",
    "assist_clinical": "gemini-pro",
    "assist_dose": "gemini-flash",
    "assist_lab": "gemini-pro",
    "assist_nhi": "gemini-flash",
    "assist_interaction": "gemini-flash",
    "assist_transplant": "gemini-pro",
    "assist_pd": "gemini-flash",
    "teach_summary": "gemini-flash",
    "teach_flashcards": "gemini-flash",
    "teach_relation": "gemini-flash",
    "teach_mindmap": "gemini-flash",
    "teach_ppt": "gemini-flash",
    "insight": "gemini-flash",
    "pathway_interactive": "gemini-flash",
    "consult_deep_research": "gemini-pro",
    "assist_evidence": "gemini-flash",
}


def get_model_for_task(task_key):
    """根據任務取得對應的模型名稱"""
    config_key = MODEL_ROUTING.get(task_key, "gemini-flash")
    return MODEL_CONFIG[config_key]["model"]


# Token 價格表（USD per million tokens）
TOKEN_PRICES = {
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.5-pro":   {"input": 1.25, "output": 10.00},
}


def _log_token_usage(response, model, feature, meta=None):
    """記錄 token 用量到 Firestore（用 update + dot-notation 做巢狀原子更新）"""
    try:
        if meta is None:
            meta = getattr(response, 'usage_metadata', None)
        if not meta:
            return
        input_tokens = getattr(meta, 'prompt_token_count', 0) or 0
        output_tokens = getattr(meta, 'candidates_token_count', 0) or 0

        prices = TOKEN_PRICES.get(model, TOKEN_PRICES["gemini-2.5-flash"])
        cost = (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000

        month_key = time.strftime("%Y-%m")
        doc_ref = db.collection("token_usage").document(month_key)

        # 模型名稱含 "." (如 gemini-2.5-flash)，會被 Firestore dot-notation 誤解析為巢狀路徑
        # 替換為 "_" 避免此問題
        safe_model = model.replace(".", "_")

        # 確保 document 存在
        doc_ref.set({"month": month_key}, merge=True)

        # update() 會正確解析 dot-notation 為巢狀路徑
        doc_ref.update({
            "total_input_tokens": firestore.Increment(input_tokens),
            "total_output_tokens": firestore.Increment(output_tokens),
            "total_cost_usd": firestore.Increment(cost),
            f"by_feature.{feature}.input": firestore.Increment(input_tokens),
            f"by_feature.{feature}.output": firestore.Increment(output_tokens),
            f"by_feature.{feature}.cost": firestore.Increment(cost),
            f"by_feature.{feature}.calls": firestore.Increment(1),
            f"by_model.{safe_model}.input": firestore.Increment(input_tokens),
            f"by_model.{safe_model}.output": firestore.Increment(output_tokens),
            f"by_model.{safe_model}.cost": firestore.Increment(cost),
            "updated_at": firestore.SERVER_TIMESTAMP,
        })
        print(f"  📊 Token usage: {input_tokens} in / {output_tokens} out → ${cost:.6f} ({feature}/{model})")
    except Exception as e:
        print(f"⚠️ Token usage log failed: {e}")


def classify_question_complexity(question):
    """判斷問題複雜度以決定使用哪個模型"""
    complex_keywords = [
        '鑑別', '比較', '選擇', '權衡', 'vs', '優缺點',
        '複雜', '困難', '罕見', '不典型', '矛盾',
        '多重', '合併', '同時', '交叉',
    ]
    score = 0
    if len(question) > 200:
        score += 1
    for kw in complex_keywords:
        if kw in question:
            score += 1
    return "consult_complex" if score >= 3 else "consult_simple"


# ---- 去識別化 (De-identification) ----
# 在將病患資料送往雲端 LLM API 前，過濾 PII（個人可識別資訊）

_PII_PATTERNS = [
    # 台灣身分證字號（A123456789）
    (re.compile(r'[A-Z][12]\d{8}'), '[身分證已隱藏]'),
    # 居留證號（舊式 AB12345678 / 新式 A800000014）
    (re.compile(r'[A-Z][A-Z89]\d{8}'), '[證號已隱藏]'),
    # 病歷號（常見格式：數字 6~10 碼，前面帶「病歷號」字樣）
    (re.compile(r'病歷號[：:\s]*[A-Za-z0-9\-]{4,15}'), '病歷號：[已隱藏]'),
    # Chart No / MRN
    (re.compile(r'(?:chart\s*no|MRN|medical\s*record)[.：:\s]*[A-Za-z0-9\-]{4,15}', re.IGNORECASE),
     '[病歷號已隱藏]'),
    # 電話號碼（台灣手機 09xx-xxx-xxx 或市話）
    (re.compile(r'09\d{2}[\-\s]?\d{3}[\-\s]?\d{3}'), '[電話已隱藏]'),
    (re.compile(r'0[2-8][\-\s]?\d{4}[\-\s]?\d{4}'), '[電話已隱藏]'),
    # Email
    (re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}'), '[Email已隱藏]'),
    # 地址（含「路/街/巷/弄/號/樓」的連續文字）
    (re.compile(r'[\u4e00-\u9fff]{2,4}[縣市][\u4e00-\u9fff]{1,4}[區鄉鎮市][\u4e00-\u9fff\d\-]+[路街][\u4e00-\u9fff\d\-巷弄號樓之]*'),
     '[地址已隱藏]'),
    # 出生年月日（民國 or 西元，常見格式）
    (re.compile(r'(?:生日|出生|DOB|birth)[：:\s]*[\d\-/\.年月日]+', re.IGNORECASE), '[出生日期已隱藏]'),
]


def anonymize_text(text):
    """移除文字中的個人可識別資訊 (PII)，保留純醫療特徵"""
    if not text:
        return text
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


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

    # Initialize OpenEvidence client (after Firestore is ready)
    try:
        from openevidence_client import OpenEvidenceClient, OpenEvidenceCookieManager
        oe_cookie_mgr = OpenEvidenceCookieManager(db)
        oe_client = OpenEvidenceClient(oe_cookie_mgr)
        print("✅ OpenEvidence client 已初始化")
    except Exception as oe_err:
        print(f"⚠️ OpenEvidence client 未啟用: {oe_err}")

    try:
        storage_bucket_obj = storage.bucket()
        print("✅ Firebase Storage 已連線")
    except Exception as e:
        print(f"⚠️ Storage bucket 未連線: {e}")

except Exception as e:
    print(f"❌ Firebase 初始化失敗: {e}")
    print("  API 會啟動但資料庫功能不可用")


# ============================================================
# Firebase Auth — Token 驗證 & 權限裝飾器
# ============================================================

def verify_token(req):
    """從 request header 取得並驗證 Firebase ID token，回傳 decoded token dict"""
    auth_header = req.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    token = auth_header[7:]
    try:
        return firebase_auth.verify_id_token(token)
    except Exception:
        return None


def require_auth(f):
    """裝飾器：要求有效的 Firebase Auth token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        decoded = verify_token(request)
        if not decoded:
            return jsonify({"error": "未授權，請先登入"}), 401
        request.uid = decoded['uid']
        request.user_email = decoded.get('email', '')
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """裝飾器：要求 admin 權限（Firestore users collection 的 role 欄位）"""
    @wraps(f)
    def decorated(*args, **kwargs):
        decoded = verify_token(request)
        if not decoded:
            return jsonify({"error": "未授權，請先登入"}), 401
        uid = decoded['uid']
        # 查 Firestore users/{uid} 的 role
        try:
            user_doc = db.collection('users').document(uid).get()
            if not user_doc.exists or user_doc.to_dict().get('role') != 'admin':
                return jsonify({"error": "需要管理員權限"}), 403
        except Exception:
            return jsonify({"error": "權限驗證失敗"}), 500
        request.uid = uid
        request.user_email = decoded.get('email', '')
        return f(*args, **kwargs)
    return decorated


# ============================================================
# Admin API 端點 — 帳號管理
# ============================================================

@app.route('/admin/users', methods=['GET'])
@require_admin
def admin_list_users():
    """列出所有使用者"""
    try:
        users = []
        page = firebase_auth.list_users()
        for u in page.users:
            user_doc = db.collection('users').document(u.uid).get()
            profile = user_doc.to_dict() if user_doc.exists else {}
            users.append({
                'uid': u.uid,
                'email': u.email,
                'displayName': profile.get('displayName', u.email.split('@')[0] if u.email else ''),
                'role': profile.get('role', 'user'),
                'disabled': u.disabled,
                'created_at': u.user_metadata.creation_timestamp,
            })
        return jsonify({"users": users})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/admin/users', methods=['POST'])
@require_admin
def admin_create_user():
    """建立新使用者"""
    data = request.get_json()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    display_name = data.get('displayName', '').strip()
    role = data.get('role', 'user')

    if not email or not password:
        return jsonify({"error": "Email 和密碼為必填"}), 400
    if len(password) < 6:
        return jsonify({"error": "密碼至少 6 碼"}), 400

    try:
        user_record = firebase_auth.create_user(email=email, password=password)
        # 在 Firestore 建立 user profile
        db.collection('users').document(user_record.uid).set({
            'email': email,
            'displayName': display_name or email.split('@')[0],
            'role': role,
            'created_at': firestore.SERVER_TIMESTAMP,
        })
        return jsonify({
            "uid": user_record.uid,
            "email": email,
            "message": f"使用者 {email} 建立成功",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/admin/users/<user_id>', methods=['DELETE'])
@require_admin
def admin_delete_user(user_id):
    """刪除使用者"""
    try:
        firebase_auth.delete_user(user_id)
        db.collection('users').document(user_id).delete()
        return jsonify({"message": "使用者已刪除"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/admin/users/<user_id>/role', methods=['PUT'])
@require_admin
def admin_update_role(user_id):
    """更新使用者角色"""
    data = request.get_json()
    role = data.get('role', 'user')
    try:
        db.collection('users').document(user_id).update({'role': role})
        return jsonify({"message": f"角色已更新為 {role}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/admin/migrate-data', methods=['POST'])
@require_admin
def admin_migrate_data():
    """將所有沒有 userId 的舊資料歸給指定使用者"""
    data = request.get_json()
    target_uid = data.get('targetUid', request.uid)

    collections_to_migrate = ['chats', 'notes', 'teach_sessions', 'assist_history', 'insight_collection']
    migrated = {}

    try:
        for col_name in collections_to_migrate:
            count = 0
            all_docs = db.collection(col_name).stream()
            for d in all_docs:
                doc_data = d.to_dict()
                if not doc_data.get('userId'):
                    db.collection(col_name).document(d.id).update({'userId': target_uid})
                    count += 1
            migrated[col_name] = count
        return jsonify({"message": "資料遷移完成", "migrated": migrated})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
# 1b. 結構化藥物資料庫（降低 AI hallucination、節省 API 成本）
# ============================================================

DRUG_DB = {}
_drug_db_path = os.path.join(os.path.dirname(__file__), "drug_database.json")
if os.path.exists(_drug_db_path):
    with open(_drug_db_path, "r", encoding="utf-8") as f:
        DRUG_DB = json.load(f)
    print(f"✅ 藥物資料庫已載入: {len(DRUG_DB)} 種藥物")
else:
    print("⚠️ drug_database.json 未找到，藥物劑量將使用 AI 生成")


def search_drug(query):
    """搜尋藥物資料庫（支援中英文模糊搜尋）"""
    query_lower = query.lower().strip()
    results = []
    for key, drug in DRUG_DB.items():
        if (query_lower in key.lower() or
            query_lower in drug.get("drug_name_en", "").lower() or
            query_lower in drug.get("drug_name_zh", "") or
            query_lower in drug.get("class_zh", "") or
            query_lower in drug.get("class_en", "").lower()):
            results.append(drug)
    return results


# ============================================================
# 1c. Prompt Template System（統一風格、節省 token）
# ============================================================

PROMPT_HEADER = """你是一位資深腎臟科主治醫師，崇尚實證醫學 (EBM)。
全程使用繁體中文，醫學術語用「中文 (English)」格式。
請用 Google Search 搜尋補充最新的指引和實證。搜尋時優先查詢學術來源（PubMed、Google Scholar、KDIGO/KDOQI 指引、UpToDate、Cochrane Library、各醫學會官方指引），避免引用 Wikipedia、Reddit、一般健康資訊網站等非學術來源。
引用文獻時，盡量以學術論文格式呈現（作者、標題、期刊、年份），並在每條文獻後附上 PubMed 連結（格式：https://pubmed.ncbi.nlm.nih.gov/PMID/）。
回答末尾的「參考文獻」列表必須依年份由新到舊排序。"""

PROMPT_CONFIDENCE = """

【信心等級標記 — 務必遵守】：
在回答的最末尾，請加入一行信心等級標記（HTML 註解格式）：
<!-- confidence: high --> 表示有明確 KDIGO/KDOQI 等指引直接支持
<!-- confidence: medium --> 表示有實證但非直接適用於此情境
<!-- confidence: low --> 表示主要基於專家意見或推論，缺乏直接實證"""

PROMPT_VISUAL_RULES = """
【視覺化格式要求 — 務必遵守，這是最重要的規則】：

■ 規則 1：摘要卡片（每次回答都必須有）
回答的「第一行」就要用以下格式，列出 3-5 個關鍵結論，不可省略：
:::summary
- 完整結論句（含藥名中英文、臨床意義，30-60 字）
- 完整結論句（含藥名中英文、臨床意義，30-60 字）
- 完整結論句（含藥名中英文、臨床意義，30-60 字）
:::
每條結論應包含具體藥物或治療名稱（中文加英文）及其臨床定位，讓讀者不看全文也能掌握重點。禁止使用「結論一」「結論二」等編號前綴。

■ 規則 2：比較表格
凡涉及以下情境，「必須」用 Markdown 表格（| 欄位 | 欄位 |），禁止用純文字條列：
  - 藥物之間的比較
  - 治療方案優缺點
  - 不同指引的對比
  - 劑量調整對照

■ 規則 3：Mermaid 流程圖
凡涉及以下情境，「必須」用 mermaid 語法畫流程圖，禁止用純文字描述流程：
  - 診斷流程或演算法
  - 治療決策樹
  - 分級處理步驟
  - 鑑別診斷路徑
Mermaid 語法限制（務必遵守，否則會渲染失敗）：
  - 第一行「只寫」 graph TD，不要在同一行加其他內容
  - 「每一個」節點連接必須獨立一行，禁止把多個節點寫在同一行
  - 節點 ID 只用英文字母和數字（A, B, C1, D2），禁止用中文當 ID
  - 節點標籤放在方括號內，可以用中文，但標籤要簡短（10字以內）
  - 連接線用 --> 或 -->|標籤|
  - 禁止在標籤中使用這些符號：# / ≥ ≤ ² （ ） 「 」 ？

■ 規則 4：參考文獻格式
回答末尾必須列出「參考文獻 (References)」專區，格式要求：
  - 依年份由新到舊排序
  - 每條文獻統一格式：文章名稱. 作者. *期刊名*. 年份;卷(期):頁碼. [PubMed](https://pubmed.ncbi.nlm.nih.gov/PMID/)
  - 若該文獻有 PMID，務必附上 PubMed 連結；若為指引或無 PMID 的來源，附上官方 URL 即可
  - 使用編號列表（1. 2. 3.）
  - 禁止只列出網站域名（如 nih.gov），每條都必須有完整的文章名稱和作者

■ 總原則：優先用視覺化方式呈現（卡片 + 表格 + 流程圖），減少純文字堆砌。如果回答中沒有摘要卡片，視為格式錯誤。"""


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


def search_textbook(question, top_k=5):
    """RAG 搜尋教科書（Phase 2 強化：取 top-20 → rerank → top-k）"""
    ensure_memory_loaded()

    found = []  # [(chunk_id, distance)]
    with memory_lock:
        if index is not None and len(stored_chunks) > 0:
            q_vec = get_embedding(question)
            if q_vec:
                q_arr = np.array([q_vec]).astype('float32')
                # 取 top-20 候選，後續 rerank
                D, I = index.search(q_arr, k=min(20, len(stored_chunks)))
                for rank, idx in enumerate(I[0]):
                    if idx != -1 and idx < len(stored_chunks):
                        chunk_id = stored_chunks[idx]
                        if chunk_id not in deleted_chunks_set:
                            found.append((chunk_id, float(D[0][rank])))

    if not found:
        return "無教科書相關資料。"

    # Reranking: 按 FAISS distance 排序（越小越相似），取 top-k
    found.sort(key=lambda x: x[1])
    top_ids = [cid for cid, _ in found[:top_k]]

    chunks_text = fetch_content_from_firestore(top_ids)
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

【問題】：{anonymize_text(question)}

【要求】：
1. 結構化回答：教科書觀點、最新實證、臨床指引、綜合建議
2. 如果教科書和 PubMed 資料不足，請用 Google Search 搜尋補充最新證據。搜尋時優先查詢學術來源：PubMed、Google Scholar、KDIGO/KDOQI 指引、UpToDate、Cochrane Library、各醫學會官方指引。避免引用 Wikipedia、Reddit、一般健康資訊網站等非學術來源。
3. 使用 Markdown 格式
4. 醫學術語用「中文 (English)」格式
5. 引用文獻時，必須以學術論文引用格式呈現，包含作者、標題、期刊、年份，並附上 PubMed 連結。格式範例：「Smith J, et al. Title of paper. *Journal Name*. 2024;Volume(Issue):Pages. [PubMed](https://pubmed.ncbi.nlm.nih.gov/PMID/)」。每個重要醫學主張都應有對應的參考來源。回答末尾的參考文獻列表必須依年份由新到舊排序。
6. 全程使用繁體中文

【視覺化格式要求 — 務必遵守，這是最重要的規則】：

■ 規則 1：摘要卡片（每次回答都必須有）
回答的「第一行」就要用以下格式，列出 3-5 個關鍵結論，不可省略：
:::summary
- 完整結論句（含藥名中英文、臨床意義，30-60 字）
- 完整結論句（含藥名中英文、臨床意義，30-60 字）
- 完整結論句（含藥名中英文、臨床意義，30-60 字）
:::
每條結論應包含具體藥物或治療名稱（中文加英文）及其臨床定位，讓讀者不看全文也能掌握重點。禁止使用「結論一」「結論二」等編號前綴。

■ 規則 2：比較表格
凡涉及以下情境，「必須」用 Markdown 表格（| 欄位 | 欄位 |），禁止用純文字條列：
  - 藥物之間的比較
  - 治療方案優缺點
  - 不同指引的對比
  - 劑量調整對照

■ 規則 3：Mermaid 流程圖
凡涉及以下情境，「必須」用 mermaid 語法畫流程圖，禁止用純文字描述流程：
  - 診斷流程或演算法
  - 治療決策樹
  - 分級處理步驟
  - 鑑別診斷路徑
Mermaid 語法限制（務必遵守，否則會渲染失敗）：
  - 第一行「只寫」 graph TD，不要在同一行加其他內容
  - 「每一個」節點連接必須獨立一行，禁止把多個節點寫在同一行
  - 節點 ID 只用英文字母和數字（A, B, C1, D2），禁止用中文當 ID
  - 節點標籤放在方括號內，可以用中文，但標籤要簡短（10字以內）
  - 連接線用 --> 或 -->|標籤|
  - 菱形決策節點用雙大括號 B{{{{是否需要透析}}}}
  - 禁止在標籤中使用這些符號：# / ≥ ≤ ² （ ） 「 」 ？ ( ) {{{{ }}}}
  - 如需表示大於等於，寫 >=；如需表示平方，寫 ^2
格式範例（注意每個連接獨立一行）：
```mermaid
graph TD
  A[評估腎功能] --> B{{{{eGFR 小於 15}}}}
  B -->|是| C[轉介腎臟科]
  B -->|否| D[門診追蹤]
  C --> E[評估透析時機]
  D --> F[每3個月追蹤]
```

■ 規則 4：參考文獻格式
回答末尾必須列出「參考文獻 (References)」專區，格式要求：
  - 依年份由新到舊排序
  - 每條文獻統一格式：文章名稱. 作者. *期刊名*. 年份;卷(期):頁碼. [PubMed](https://pubmed.ncbi.nlm.nih.gov/PMID/)
  - 若該文獻有 PMID，務必附上 PubMed 連結；若為指引或無 PMID 的來源，附上官方 URL 即可
  - 使用編號列表（1. 2. 3.）
  - 禁止只列出網站域名（如 nih.gov），每條都必須有完整的文章名稱和作者

■ 總原則：優先用視覺化方式呈現（卡片 + 表格 + 流程圖），減少純文字堆砌。如果回答中沒有摘要卡片，視為格式錯誤。"""

    task_key = classify_question_complexity(question)
    model = get_model_for_task(task_key)
    print(f"  🤖 模型路由: {task_key} → {model}")

    try:
        response = gemini_client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            )
        )
        _log_token_usage(response, model, "consult")
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
7. 如有決策流程，用 mermaid 流程圖（語法規範同下）：
   - 第一行只寫 graph TD
   - 每個節點連接獨立一行，ID 用英文
   - 方形 A[標籤]，菱形 B{{{{決策}}}}（雙大括號）
   - 標籤內禁止 ( ) [ ] {{{{ }}}} # / ; :
   範例：
   ```mermaid
   graph TD
     A[評估腎功能] --> B{{{{eGFR 小於 15}}}}
     B -->|是| C[轉介腎臟科]
     B -->|否| D[門診追蹤]
   ```"""

    try:
        model = get_model_for_task("consult_simple")
        response = gemini_client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            )
        )
        _log_token_usage(response, model, "consult")
        return response.text
    except Exception as e:
        return f"❌ 生成失敗: {e}"


# ============================================================
# 5. API 端點
# ============================================================

# --- 藥物資料庫 API（零 AI 成本，直接查表）---

@app.route('/drugs/search', methods=['GET'])
def drugs_search():
    """搜尋藥物資料庫（不呼叫 AI，零成本）"""
    q = request.args.get('q', '')
    if not q:
        return jsonify({"drugs": list(DRUG_DB.keys())})
    results = search_drug(q)
    return jsonify({"drugs": results, "count": len(results)})


@app.route('/drugs/<name>', methods=['GET'])
def drugs_detail(name):
    """取得單一藥物資料（不呼叫 AI，零成本）"""
    drug = DRUG_DB.get(name)
    if not drug:
        # 嘗試模糊搜尋
        results = search_drug(name)
        if results:
            return jsonify(results[0])
        return jsonify({"error": f"找不到藥物: {name}"}), 404
    return jsonify(drug)


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


@app.route('/usage/monthly', methods=['GET'])
def get_monthly_usage():
    """取得每月 token 用量統計"""
    month = request.args.get('month', time.strftime("%Y-%m"))
    doc_snapshot = db.collection("token_usage").document(month).get()
    if doc_snapshot.exists:
        return jsonify(doc_snapshot.to_dict())
    return jsonify({
        "month": month,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cost_usd": 0,
        "by_feature": {},
        "by_model": {},
    })


@app.route('/ask', methods=['POST'])
@require_auth
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


# ============================================================
# 5a. SSE Streaming 端點（節省 API 成本：避免重複呼叫）
# ============================================================

DEEP_RESEARCH_PROMPT = """你是一位崇尚實證醫學的腎臟科專家。我從多個來源為你蒐集了以下資訊，請整合為一篇完整的 Evidence Review。

【教科書知識庫】
{textbook_ctx}

【PubMed 文獻摘要】
{pubmed_ctx}

【OpenEvidence 實證分析】
{oe_answer}

【OpenEvidence 引用文獻】
{oe_citations}

【問題】：{question}

【整合要求】：
請將以上所有來源整合為一篇完整的 Evidence Review，格式要求如下：

■ 規則 1：摘要卡片（每次回答都必須有，放在第一行）
:::summary
- 完整結論句（含藥名中英文、臨床意義，30-60 字）
- 完整結論句（含藥名中英文、臨床意義，30-60 字）
- 完整結論句（含藥名中英文、臨床意義，30-60 字）
- 完整結論句（如適用）
- 完整結論句（如適用）
:::
每條結論應包含具體藥物或治療名稱（中文加英文）及其臨床定位。禁止使用「結論一」「結論二」等編號前綴。

■ 規則 2：主文
- 依主題分段，每段引用來源，使用編號引用如 [1], [2]
- 交叉比對不同來源（教科書、PubMed、OpenEvidence）的觀點
- 如果不同來源有矛盾，明確指出並分析哪個證據等級較高（RCT > 觀察性研究 > 專家意見）
- 如果教科書和最新實證有差異，特別標註
- 醫學術語用「中文 (English)」格式

■ 規則 3：涉及比較必須用 Markdown 表格
凡涉及藥物比較、治療方案優缺點、不同指引對比、劑量調整，必須用 Markdown 表格呈現。

■ 規則 4：Mermaid 流程圖
凡涉及診斷流程、治療決策樹、分級處理步驟，必須用 mermaid 語法畫流程圖。
Mermaid 語法限制（務必遵守）：
  - 第一行「只寫」 graph TD，不要在同一行加其他內容
  - 每一個節點連接必須獨立一行
  - 節點 ID 只用英文字母和數字（A, B, C1, D2）
  - 方形節點標籤放在方括號內 A[標籤]，標籤簡短（10字以內）
  - 菱形決策節點用雙大括號 B{{{{是否需要透析}}}}
  - 連接線用 --> 或 -->|標籤|
  - 標籤內禁止使用：( ) [ ] {{{{ }}}} # / \\\\ " ' ` ≥ ≤ ² ; :

■ 規則 5：參考文獻列表
回答末尾必須列出「參考文獻 (References)」，依序編號：
  - 教科書來源標示 [教科書]
  - PubMed 文獻：作者. 標題. *期刊*. 年份;卷(期):頁碼. [PubMed](https://pubmed.ncbi.nlm.nih.gov/PMID/)
  - OpenEvidence 引用文獻附 DOI 或 PMID 連結
  - Google Search 補充附 URL
  依年份由新到舊排序。

■ 規則 6：如果以上資料不足，使用 Google Search 搜尋補充。優先查詢 PubMed、Google Scholar、KDIGO/KDOQI 指引、UpToDate、Cochrane Library。

■ 總原則：全程繁體中文。優先用視覺化方式呈現。這是一篇綜合多來源的深度分析，品質要求高於一般問答。"""


def _generate_deep_research(question):
    """Deep Research mode: gather from RAG + PubMed + OpenEvidence, then synthesize."""

    def _sse(type_, content):
        return f"data: {json.dumps({'type': type_, 'content': content}, ensure_ascii=False)}\n\n"

    try:
        yield _sse('status', '正在搜尋教科書知識庫...')

        # Phase 1: Parallel gathering
        oe_result_holder = [None]
        oe_error_holder = [None]

        def run_openevidence():
            try:
                if oe_client:
                    oe_result_holder[0] = oe_client.get_formatted_result(question)
            except Exception as e:
                oe_error_holder[0] = e
                print(f"⚠️ OE Deep Research error: {e}")

        # Start OE in separate thread (long polling)
        oe_thread = None
        if oe_client:
            oe_thread = threading.Thread(target=run_openevidence, daemon=True)
            oe_thread.start()
            yield _sse('status', '正在查詢 OpenEvidence 實證資料庫...')

        # RAG + PubMed in ThreadPool
        with ThreadPoolExecutor(max_workers=2) as executor:
            textbook_future = executor.submit(search_textbook, question)
            pubmed_future = executor.submit(search_pubmed, question)

            try:
                textbook_ctx = textbook_future.result(timeout=20)
            except Exception:
                textbook_ctx = "無教科書資料（搜尋逾時）。"
            yield _sse('status', '教科書搜尋完成')

            try:
                pubmed_ctx = pubmed_future.result(timeout=15) or "無 PubMed 結果。"
            except Exception:
                pubmed_ctx = "無 PubMed 結果（搜尋逾時）。"
            yield _sse('status', 'PubMed 搜尋完成')

        # Wait for OpenEvidence
        oe_answer = ""
        oe_citations = ""
        if oe_thread:
            yield _sse('status', '等待 OpenEvidence 分析完成（約需 1-2 分鐘）...')
            oe_thread.join(timeout=180)
            if oe_result_holder[0]:
                oe_answer = oe_result_holder[0].get("answer", "")
                oe_citations = oe_result_holder[0].get("citations", "")
                yield _sse('status', 'OpenEvidence 分析已收到')
            elif oe_error_holder[0]:
                yield _sse('status', f'OpenEvidence 查詢失敗，將以其他來源繼續分析')
            else:
                yield _sse('status', 'OpenEvidence 逾時，將以其他來源繼續分析')

        yield _sse('status', '所有來源收集完成，正在生成深度分析...')

        # Phase 2: Synthesis with Gemini Pro
        model = get_model_for_task("consult_deep_research")

        prompt = DEEP_RESEARCH_PROMPT.format(
            textbook_ctx=textbook_ctx,
            pubmed_ctx=pubmed_ctx,
            oe_answer=oe_answer or "（OpenEvidence 未回傳資料）",
            oe_citations=oe_citations or "（無引用文獻）",
            question=anonymize_text(question),
        )

        response = gemini_client.models.generate_content_stream(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            )
        )

        # Phase 3: Stream the synthesized article
        last_usage = None
        grounding_meta = None
        for chunk in response:
            if chunk.text:
                yield f"data: {json.dumps({'type': 'content', 'content': chunk.text}, ensure_ascii=False)}\n\n"
            if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                last_usage = chunk.usage_metadata
            if hasattr(chunk, 'candidates') and chunk.candidates:
                candidate = chunk.candidates[0]
                if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                    grounding_meta = candidate.grounding_metadata

        # Send grounding sources (reuse existing logic)
        if grounding_meta and hasattr(grounding_meta, 'grounding_chunks') and grounding_meta.grounding_chunks:
            from urllib.parse import urlparse
            ACADEMIC_DOMAINS = {
                'pubmed.ncbi.nlm.nih.gov', 'ncbi.nlm.nih.gov', 'scholar.google.com',
                'doi.org', 'nejm.org', 'thelancet.com', 'bmj.com', 'jamanetwork.com',
                'nature.com', 'springer.com', 'wiley.com', 'elsevier.com', 'sciencedirect.com',
                'cochranelibrary.com', 'uptodate.com', 'kidney-international.org',
                'kdigo.org', 'kidney.org', 'asn-online.org', 'era-online.org',
                'jasn.asnjournals.org', 'cjasn.asnjournals.org',
                'academic.oup.com', 'journals.lww.com', 'karger.com',
                'mdpi.com', 'frontiersin.org', 'hindawi.com', 'plos.org',
                'annals.org', 'acpjournals.org', 'ahajournals.org',
                'nih.gov', 'who.int', 'cdc.gov', 'tsn.org.tw', 'nephrology.org',
            }
            NON_ACADEMIC_DOMAINS = {
                'wikipedia.org', 'reddit.com', 'quora.com', 'facebook.com',
                'twitter.com', 'x.com', 'youtube.com', 'tiktok.com',
                'healthline.com', 'webmd.com', 'mayoclinic.org',
                'medicalnewstoday.com', 'verywellhealth.com',
                'droracle.ai', 'zy91.com', 'dxy.cn',
                'revivemobileivs.com', 'criticalcaretime.com',
            }
            sources = []
            seen = set()
            for gc in grounding_meta.grounding_chunks:
                if hasattr(gc, 'web') and gc.web and gc.web.uri and gc.web.uri not in seen:
                    seen.add(gc.web.uri)
                    uri = gc.web.uri
                    try:
                        domain = urlparse(uri).hostname or ''
                        domain_parts = domain.replace('www.', '').split('.')
                        main_domain = '.'.join(domain_parts[-2:]) if len(domain_parts) >= 2 else domain
                    except Exception:
                        main_domain = ''
                    if main_domain in NON_ACADEMIC_DOMAINS:
                        continue
                    sources.append({'title': gc.web.title or '', 'url': uri})

            def _academic_priority(s):
                try:
                    d = urlparse(s['url']).hostname or ''
                    d = d.replace('www.', '')
                    for ad in ACADEMIC_DOMAINS:
                        if d.endswith(ad):
                            return 0
                    return 1
                except Exception:
                    return 1
            sources.sort(key=_academic_priority)
            if sources:
                yield f"data: {json.dumps({'type': 'sources', 'sources': sources}, ensure_ascii=False)}\n\n"

        _log_token_usage(response, model, "deep_research", meta=last_usage)
        yield "data: [DONE]\n\n"

    except Exception as e:
        print(f"❌ Deep Research error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"


@app.route('/ask-stream', methods=['POST'])
@require_auth
def ask_stream():
    """SSE streaming endpoint for NB Consult — 即時串流回答"""
    data = request.get_json()
    question = data.get('question', '')
    deep_research = data.get('deep_research', False)

    if not question:
        return jsonify({"error": "請提供問題"}), 400

    if not gemini_client:
        return jsonify({"error": "Gemini API 未設定"}), 500

    mode_label = "🔬 Deep Research" if deep_research else "💬"
    print(f"{mode_label} /ask-stream: {question[:60]}...")

    def generate():
        try:
            # === Deep Research Mode ===
            if deep_research:
                yield from _generate_deep_research(question)
                return

            # === Normal Mode (unchanged) ===
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

            yield f"data: {json.dumps({'type': 'status', 'content': '搜尋完成，開始生成回答...'}, ensure_ascii=False)}\n\n"

            task_key = classify_question_complexity(question)
            model = get_model_for_task(task_key)

            prompt = f"""你是一位崇尚「實證醫學 (EBM)」的腎臟科專家。

【教科書知識庫】
{textbook_ctx}

【PubMed 文獻】
{pubmed_ctx}

【問題】：{anonymize_text(question)}

【要求】：
1. 結構化回答：教科書觀點、最新實證、臨床指引、綜合建議
2. 如果教科書和 PubMed 資料不足，請用 Google Search 搜尋補充最新證據。搜尋時優先查詢學術來源：PubMed、Google Scholar、KDIGO/KDOQI 指引、UpToDate、Cochrane Library、各醫學會官方指引。避免引用 Wikipedia、Reddit、一般健康資訊網站等非學術來源。
3. 使用 Markdown 格式
4. 醫學術語用「中文 (English)」格式
5. 引用文獻時，必須以學術論文引用格式呈現，包含作者、標題、期刊、年份，並附上 PubMed 連結。格式範例：「Smith J, et al. Title of paper. *Journal Name*. 2024;Volume(Issue):Pages. [PubMed](https://pubmed.ncbi.nlm.nih.gov/PMID/)」。每個重要醫學主張都應有對應的參考來源。回答末尾的參考文獻列表必須依年份由新到舊排序。
6. 全程使用繁體中文

【視覺化格式要求】：
■ 規則 1：摘要卡片（每次回答都必須有）
回答的「第一行」就要用以下格式，列出 3-5 個關鍵結論，不可省略：
:::summary
- 完整結論句（含藥名中英文、臨床意義，30-60 字）
- 完整結論句（含藥名中英文、臨床意義，30-60 字）
- 完整結論句（含藥名中英文、臨床意義，30-60 字）
:::
每條結論應包含具體藥物或治療名稱（中文加英文）及其臨床定位，讓讀者不看全文也能掌握重點。禁止使用「結論一」「結論二」等編號前綴。

■ 規則 2：涉及比較必須用 Markdown 表格

■ 規則 3：Mermaid 流程圖
凡涉及診斷流程、治療決策樹、分級處理步驟，必須用 mermaid 語法畫流程圖。
Mermaid 語法限制（務必遵守，否則會渲染失敗）：
  - 第一行「只寫」 graph TD，不要在同一行加其他內容
  - 「每一個」節點連接必須獨立一行，禁止把多個節點寫在同一行
  - 節點 ID 只用英文字母和數字（A, B, C1, D2），禁止用中文當 ID
  - 方形節點標籤放在方括號內 A[標籤]，可以用中文，但標籤要簡短（10字以內）
  - 菱形決策節點用雙大括號 B{{{{是否需要透析}}}}
  - 連接線用 --> 或 -->|標籤|
  - 標籤內禁止使用：( ) [ ] {{{{ }}}} # / \\ " ' ` ≥ ≤ ² ; :
  - 大於等於寫 >=，小於等於寫 <=；範圍用破折號如 eGFR 30-59
正確範例：
```mermaid
graph TD
  A[評估腎功能] --> B{{{{eGFR 是否小於 15}}}}
  B -->|是| C[轉介腎臟科]
  B -->|否| D[門診追蹤]
  C --> E[評估透析時機]
  D --> F[每3個月追蹤]
```
常見錯誤（絕對不要這樣寫）：
  - 錯：A[CKD Stage 3 (eGFR 30-59)] → 括號會被解析為節點語法
  - 對：A[CKD Stage 3 eGFR 30-59]
  - 錯：B{{是否需要透析}} → 單大括號會解析失敗
  - 對：B{{{{是否需要透析}}}}
  - 錯：graph TD A[起點] --> B[終點] → 宣告和節點同一行
  - 對：graph TD 獨立一行

■ 規則 4：參考文獻格式
回答末尾必須列出「參考文獻 (References)」專區，格式要求：
  - 依年份由新到舊排序
  - 每條文獻統一格式：文章名稱. 作者. *期刊名*. 年份;卷(期):頁碼. [PubMed](https://pubmed.ncbi.nlm.nih.gov/PMID/)
  - 若該文獻有 PMID，務必附上 PubMed 連結；若為指引或無 PMID 的來源，附上官方 URL 即可
  - 使用編號列表（1. 2. 3.）
  - 禁止只列出網站域名（如 nih.gov），每條都必須有完整的文章名稱和作者

■ 總原則：優先用視覺化方式呈現。"""

            response = gemini_client.models.generate_content_stream(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                )
            )

            last_usage = None
            grounding_meta = None
            for chunk in response:
                if chunk.text:
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk.text}, ensure_ascii=False)}\n\n"
                # streaming 的 usage_metadata 通常在最後一個 chunk
                if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                    last_usage = chunk.usage_metadata
                # 收集 grounding metadata（Google Search 來源）
                if hasattr(chunk, 'candidates') and chunk.candidates:
                    candidate = chunk.candidates[0]
                    if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                        grounding_meta = candidate.grounding_metadata

            # 發送網路搜尋來源（優先學術來源，過濾非學術網站）
            if grounding_meta and hasattr(grounding_meta, 'grounding_chunks') and grounding_meta.grounding_chunks:
                # 學術來源域名白名單
                ACADEMIC_DOMAINS = {
                    'pubmed.ncbi.nlm.nih.gov', 'ncbi.nlm.nih.gov', 'scholar.google.com',
                    'doi.org', 'nejm.org', 'thelancet.com', 'bmj.com', 'jamanetwork.com',
                    'nature.com', 'springer.com', 'wiley.com', 'elsevier.com', 'sciencedirect.com',
                    'cochranelibrary.com', 'uptodate.com', 'kidney-international.org',
                    'kdigo.org', 'kidney.org', 'asn-online.org', 'era-online.org',
                    'jasn.asnjournals.org', 'cjasn.asnjournals.org',
                    'academic.oup.com', 'journals.lww.com', 'karger.com',
                    'mdpi.com', 'frontiersin.org', 'hindawi.com', 'plos.org',
                    'annals.org', 'acpjournals.org', 'ahajournals.org',
                    'nih.gov', 'who.int', 'cdc.gov',
                    'tsn.org.tw', 'nephrology.org',
                }
                # 非學術來源黑名單
                NON_ACADEMIC_DOMAINS = {
                    'wikipedia.org', 'reddit.com', 'quora.com', 'facebook.com',
                    'twitter.com', 'x.com', 'youtube.com', 'tiktok.com',
                    'healthline.com', 'webmd.com', 'mayoclinic.org',
                    'medicalnewstoday.com', 'verywellhealth.com',
                    'droracle.ai', 'zy91.com', 'dxy.cn',
                    'revivemobileivs.com', 'criticalcaretime.com',
                }
                sources = []
                seen = set()
                for gc in grounding_meta.grounding_chunks:
                    if hasattr(gc, 'web') and gc.web and gc.web.uri and gc.web.uri not in seen:
                        seen.add(gc.web.uri)
                        uri = gc.web.uri
                        # 解析域名，過濾非學術來源
                        try:
                            from urllib.parse import urlparse
                            domain = urlparse(uri).hostname or ''
                            # 取主域名（去掉 www.）
                            domain_parts = domain.replace('www.', '').split('.')
                            main_domain = '.'.join(domain_parts[-2:]) if len(domain_parts) >= 2 else domain
                        except Exception:
                            main_domain = ''
                        # 跳過黑名單域名
                        if main_domain in NON_ACADEMIC_DOMAINS:
                            continue
                        sources.append({'title': gc.web.title or '', 'url': uri})
                # 排序：學術來源優先
                def _academic_priority(s):
                    try:
                        from urllib.parse import urlparse
                        d = urlparse(s['url']).hostname or ''
                        d = d.replace('www.', '')
                        for ad in ACADEMIC_DOMAINS:
                            if d.endswith(ad):
                                return 0
                        return 1
                    except Exception:
                        return 1
                sources.sort(key=_academic_priority)
                if sources:
                    yield f"data: {json.dumps({'type': 'sources', 'sources': sources}, ensure_ascii=False)}\n\n"

            _log_token_usage(response, model, "consult", meta=last_usage)
            yield "data: [DONE]\n\n"

        except Exception as e:
            print(f"❌ Streaming error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'X-Accel-Buffering': 'no',
        }
    )


@app.route('/consult/chat-stream', methods=['POST'])
@require_auth
def consult_chat_stream():
    """SSE streaming alias"""
    return ask_stream()


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
@require_auth
def teach_generate():
    """NB Teach: 從文字或 PDF 生成摘要/Flashcards/關聯分析/心智圖"""
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
    uploaded_file = None  # Track for cleanup
    if file_url:
        try:
            print(f"🎓 下載 PDF: {file_url[:80]}...")
            pdf_resp = requests.get(file_url, timeout=60)
            pdf_resp.raise_for_status()
            pdf_bytes = pdf_resp.content
            print(f"  📄 PDF 大小：{len(pdf_bytes) / 1024:.0f} KB")

            # 使用 Gemini File API 上傳（比 inline_data 更穩定，不限大小）
            uploaded_file = gemini_client.files.upload(
                file=io.BytesIO(pdf_bytes),
                config=types.UploadFileConfig(
                    mime_type="application/pdf",
                    display_name="teach_upload.pdf"
                )
            )
            print(f"  ☁️ 已上傳至 Gemini File API: {uploaded_file.name}")
            contents.append(uploaded_file)
        except Exception as e:
            print(f"❌ PDF 處理失敗: {e}")
            return jsonify({"error": f"PDF 處理失敗: {e}"}), 500
    else:
        text = text[:15000]
        contents.append(text)

    print(f"🎓 /teach/generate: mode={mode}, source={'PDF' if file_url else 'text'}")

    result = {}

    try:
        # If PDF, extract text so user can view/edit later
        if file_url and contents:
            try:
                extract_prompt = "請完整提取這份 PDF 的所有文字內容，保持原始結構和段落格式。只輸出文字內容，不要加任何說明或標記。"
                extracted = _teach_call(contents, extract_prompt, "teach_extract_text")
                if extracted and len(extracted.strip()) > 50:
                    result['extracted_text'] = extracted.strip()
                    print(f"  📝 提取文字：{len(result['extracted_text'])} 字")
            except Exception as e:
                print(f"⚠️ PDF 文字提取失敗（不影響生成）: {e}")

        if mode in ('summary', 'all'):
            result['summary'] = _teach_call(contents, TEACH_PROMPT_SUMMARY, "teach_summary")

        if mode in ('flashcards', 'all'):
            raw = _teach_call(contents, TEACH_PROMPT_FLASHCARDS, "teach_flashcards")
            parsed = _extract_json(raw)
            result['flashcards'] = json.dumps(parsed, ensure_ascii=False)

        if mode in ('relation', 'all'):
            result['relation'] = _teach_call(contents, TEACH_PROMPT_RELATION, "teach_relation")

        if mode in ('mindmap', 'all'):
            raw = _teach_call(contents, TEACH_PROMPT_MINDMAP, "teach_mindmap")
            parsed = _extract_json(raw)
            result['mindmap'] = json.dumps(parsed, ensure_ascii=False)

        if mode == 'ppt':
            ppt_options = data.get('ppt_options', {})
            theme = ppt_options.get('theme', 'orange')
            if theme == 'auto':
                ppt_options['_auto_theme'] = True
            prompt = build_ppt_prompt(ppt_options)
            raw = _teach_call(contents, prompt, "teach_ppt")
            parsed = _extract_json(raw)
            result['ppt'] = json.dumps(parsed, ensure_ascii=False)
            # Resolve auto theme from AI response
            if theme == 'auto':
                theme = parsed.get('recommended_theme', 'blue')
                if theme not in ('orange', 'blue', 'green', 'bw'):
                    theme = 'blue'
            result['ppt_theme'] = theme

        return jsonify(result)

    except Exception as e:
        print(f"❌ Teach generate error: {e}")
        return jsonify({"error": str(e)}), 500

    finally:
        # 清理 Gemini File API 上傳的暫存檔
        if uploaded_file:
            try:
                gemini_client.files.delete(name=uploaded_file.name)
                print(f"  🗑️ 已清理 Gemini 暫存檔: {uploaded_file.name}")
            except Exception:
                pass


def _extract_json(raw):
    """從 LLM 回傳的文字中擷取 JSON，處理 code fence 和額外文字"""
    text = raw.strip()
    # 1. 嘗試從 code fence 中擷取
    m = re.search(r'```(?:json)?\s*\n([\s\S]*?)\n```', text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    # 2. 嘗試找第一個 { 到最後一個 } 之間的內容
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    # 3. 嘗試找 [ 到 ] (陣列格式)
    start = text.find('[')
    end = text.rfind(']')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    raise ValueError(f"無法從回應中擷取有效 JSON（前 200 字元：{text[:200]}）")


def _teach_call(contents, prompt_text, task_key="teach_summary"):
    """呼叫 Gemini，contents 可以是文字或 PDF inline_data"""
    all_contents = contents + [prompt_text]
    model = get_model_for_task(task_key)
    response = gemini_client.models.generate_content(
        model=model,
        contents=all_contents,
    )
    _log_token_usage(response, model, "teach")
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

TEACH_PROMPT_RELATION = """你是一位醫學教育專家，擅長分析知識之間的關聯性。
請閱讀上面的學習素材，進行深度關聯分析。

【輸出格式】（Markdown）：

## 🔗 核心知識定位
（這份素材屬於哪個知識領域？在腎臟醫學知識體系中的位置）

## 🧩 先備知識（Prerequisites）
（要理解這份素材，需要先具備哪些知識？列出 3-5 個）
- **知識點 A**：為什麼需要、簡述關係
- **知識點 B**：為什麼需要、簡述關係

## 🔀 橫向關聯（Cross-links）
（這份素材和哪些其他主題有密切關聯？）
- **相關主題 1** → 關聯方式（例如：共同機轉、鑑別診斷、合併治療）
- **相關主題 2** → 關聯方式
- **相關主題 3** → 關聯方式

## ⬆️ 進階延伸（Next Steps）
（學完這份素材後，建議接下來學什麼？）
1. **延伸主題 A** — 為什麼值得學
2. **延伸主題 B** — 為什麼值得學

## 🏥 臨床情境連結
（這份素材的知識會在哪些臨床情境用到？）
- 情境 1：簡述如何應用
- 情境 2：簡述如何應用
- 情境 3：簡述如何應用

## 💡 學習策略建議
（根據這份素材的特性，建議用什麼方式學習最有效？）

全程使用繁體中文，醫學術語用「中文 (English)」格式。
請用 Google Search 搜尋補充最新的相關知識和指引。"""

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


def build_ppt_prompt(options):
    """根據使用者選項動態組合 PPT 生成 prompt"""
    language = options.get('language', 'zh-TW')
    audience = options.get('audience', 'doctor')
    length = options.get('length', 'standard')
    style = options.get('style', 'balanced')

    # 語言設定
    lang_map = {
        'zh-TW': '全程使用繁體中文，醫學術語用「中文 (English)」格式。',
        'en': '全程使用英文 (English)。',
        'zh-mixed': '全程使用繁體中文，但疾病名稱、藥物名稱、檢驗項目使用英文。',
    }
    lang_instruction = lang_map.get(language, lang_map['zh-TW'])

    # 對象設定
    audience_map = {
        'public': '對象是一般民眾（衛教用途）。用簡單易懂的語言，避免過多專業術語，多用比喻和生活化的說明。每頁重點不超過 3 個。',
        'staff': '對象是醫院專師、護理師、住院醫師（教育用途）。可使用專業術語但需解釋關鍵概念，著重臨床實務應用和操作流程。',
        'doctor': '對象是主治醫師（學術報告用）。可使用完整專業術語，強調實證醫學證據、最新指引、臨床決策重點。',
    }
    audience_instruction = audience_map.get(audience, audience_map['doctor'])

    # 頁數設定
    length_map = {
        'brief': '投影片總數 5-9 頁（精簡版）。',
        'medium': '投影片總數 10-14 頁（中等版）。',
        'standard': '投影片總數 10-14 頁（中等版）。',  # backward compat
        'full': '投影片總數 15-20 頁（完整版）。',
        'auto': '根據素材的豐富程度與複雜度，自行決定最適合的投影片頁數（5-20 頁範圍內）。',
    }
    length_instruction = length_map.get(length, length_map['standard'])

    # 風格設定
    style_map = {
        'chart-heavy': '盡量多使用圖表（chart）和表格（table）呈現資料，至少 40% 的頁面使用視覺化呈現。文字精簡，讓數據說話。',
        'text-heavy': '以文字內容為主，使用條列式重點。僅在有明確數據時才使用圖表。',
        'balanced': '均衡使用文字和圖表。有數據比較時用圖表，概念說明用文字條列。',
    }
    style_instruction = style_map.get(style, style_map['balanced'])

    prompt = f"""你是一位醫學簡報設計專家。請根據上面的學習素材，製作一份專業的投影片簡報。

【簡報設定】
- {lang_instruction}
- {audience_instruction}
- {length_instruction}
- {style_instruction}

【輸出格式】：純 JSON，不要 markdown 標記。嚴格遵守以下結構：

{{
  "title": "簡報主題",
  "slides": [
    {{
      "layout": "title",
      "title": "簡報標題",
      "subtitle": "副標題或講者資訊"
    }},
    {{
      "layout": "content",
      "title": "投影片標題",
      "bullets": ["重點 1", "重點 2", "重點 3"],
      "notes": "講者備註（口頭補充說明）"
    }},
    {{
      "layout": "two_column",
      "title": "比較標題",
      "left": {{ "heading": "左欄標題", "bullets": ["項目 A", "項目 B"] }},
      "right": {{ "heading": "右欄標題", "bullets": ["項目 C", "項目 D"] }},
      "notes": "講者備註"
    }},
    {{
      "layout": "chart",
      "title": "圖表標題",
      "chart_type": "bar",
      "chart_data": {{
        "labels": ["A", "B", "C"],
        "datasets": [{{ "name": "系列1", "values": [10, 20, 30] }}]
      }},
      "notes": "講者備註"
    }},
    {{
      "layout": "table",
      "title": "表格標題",
      "headers": ["欄位1", "欄位2", "欄位3"],
      "rows": [["值A", "值B", "值C"], ["值D", "值E", "值F"]],
      "notes": "講者備註"
    }},
    {{
      "layout": "summary",
      "title": "總結與重點回顧",
      "bullets": ["重點回顧 1", "重點回顧 2"],
      "notes": "講者備註"
    }}
  ]
}}

【規則】：
1. 第一頁必須是 layout: "title"，最後一頁必須是 layout: "summary"
2. 可用的 layout 類型：title, content, two_column, chart, table, summary
3. 可用的 chart_type：bar, pie, line, doughnut
4. 僅在素材中有明確數據時才使用 chart layout，絕對不要捏造數字
5. 每個 content 頁的 bullets 不超過 5 個
6. notes 欄位提供講者的口頭補充說明，比投影片內容更詳細
7. 根據素材內容選擇最適合的 layout 類型組合
8. 表格用於比較、分類、藥物劑量等結構化資訊
9. **重要文字高亮**：在 bullets 文字中，對關鍵術語、重要數值、藥物名稱、診斷標準、關鍵結論等使用 **粗體** markdown 標記（用 **雙星號** 包起來）。例如："eGFR **< 60 mL/min** 持續 **3 個月**以上即可診斷為 **CKD**"。每條 bullet 中標記 1-3 個最重要的詞彙或數值即可，不要過度標記。"""

    # Auto theme instruction
    auto_theme = options.get('_auto_theme', False)
    theme_instruction = ''
    if auto_theme:
        theme_instruction = '\n10. 在 JSON 最外層加入 "recommended_theme" 欄位，根據簡報內容主題推薦最適合的配色（只能選 "orange"、"blue"、"green"、"bw" 其中一個）。學術/嚴謹主題推薦 blue 或 bw，臨床/衛教主題推薦 orange 或 green。'

    return prompt + theme_instruction


# === NB Assist 端點（加在 api_server.py 的 teach 端點後面）===

ASSIST_DISCLAIMER = "\n\n---\n> ⚠️ **免責聲明**：以上建議由 AI 根據實證醫學資料生成，僅供臨床參考。實際治療決策應由主治醫師根據完整病歷資訊做出判斷。所有藥物劑量請以最新藥典和院內處方集為準。"

@app.route('/assist/query', methods=['POST'])
@require_auth
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
        elif mode == 'transplant':
            result = _assist_transplant(data, images)
        elif mode == 'pd':
            result = _assist_pd(data, images)
        elif mode == 'evidence':
            result = _assist_evidence(data.get('question', ''))
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
        contents.append(f"【臨床情境】\n{anonymize_text(scenario)}")
    contents.append(prompt)

    model = get_model_for_task("assist_clinical")
    response = gemini_client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )
    )
    _log_token_usage(response, model, "assist")
    return response.text + ASSIST_DISCLAIMER


def _assist_dose(data, images=None):
    """藥物劑量調整 — 優先使用結構化資料庫（節省 API 成本、降低 hallucination）"""
    drug = data.get('drug', '')
    egfr = data.get('egfr', '')
    ckd_stage = data.get('ckd_stage', '')
    weight = data.get('weight', '')
    extra = anonymize_text(data.get('extra', ''))

    if not drug and not images:
        return "❌ 請提供藥物名稱或上傳處方圖片。"

    # 先查結構化藥物資料庫（零 AI 成本）
    db_context = ""
    db_found = False
    if drug:
        db_results = search_drug(drug)
        if db_results:
            db_found = True
            d = db_results[0]
            dose_adj = d.get("dose_adjustments", {})
            db_context = f"""
【⚠️ 結構化藥物資料庫資料 — 以此為主要依據，不可自行編造劑量】
藥名: {d.get('drug_name_en')} ({d.get('drug_name_zh')})
分類: {d.get('class_zh')} ({d.get('class_en')})
排除途徑: {d.get('elimination')}
蛋白結合率: {d.get('protein_binding')}
可透析清除: {'是' if d.get('dialyzable') else '否'} {d.get('dialysis_supplement', '')}
腎毒性: {'是' if d.get('nephrotoxic') else '否'}
劑量調整:
  正常腎功能: {dose_adj.get('normal', {}).get('dose', '')} {dose_adj.get('normal', {}).get('frequency', '')}
  CKD 3: {dose_adj.get('ckd_3', {}).get('dose', '')} {dose_adj.get('ckd_3', {}).get('frequency', '')}
  CKD 4: {dose_adj.get('ckd_4', {}).get('dose', '')} {dose_adj.get('ckd_4', {}).get('frequency', '')}
  CKD 5: {dose_adj.get('ckd_5', {}).get('dose', '')} {dose_adj.get('ckd_5', {}).get('frequency', '')}
  HD: {dose_adj.get('hd', {}).get('dose', '')} {dose_adj.get('hd', {}).get('frequency', '')}
  PD: {dose_adj.get('pd', {}).get('dose', '')} {dose_adj.get('pd', {}).get('frequency', '')}
  CRRT: {dose_adj.get('crrt', {}).get('dose', '')} {dose_adj.get('crrt', {}).get('frequency', '')}
監測項目: {', '.join(d.get('monitoring', []))}
主要交互作用: {', '.join(d.get('interactions_major', []))}
禁忌症: {', '.join(d.get('contraindications', []))}
"""

    db_warning = ""
    if not db_found:
        db_warning = "\n⚠️ 此藥物不在結構化資料庫中，以下劑量由 AI 生成，請務必與藥典交叉驗證。\n"

    prompt = f"""{PROMPT_HEADER}
你同時具備臨床藥學專長，專精腎臟病藥物劑量調整。
如果有圖片，請先判讀圖片內容。
{db_context}

【藥物】{drug if drug else '（請從圖片判讀）'}
【eGFR】{egfr if egfr else '未提供'} mL/min/1.73m²
【CKD Stage】{ckd_stage if ckd_stage else '未提供（請根據 eGFR 判斷）'}
【體重】{weight if weight else '未提供'} kg
【其他備註】{extra if extra else '無'}

【請依照以下格式回答】（Markdown）：
{db_warning}
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
| 1-2 | >=60 | | |
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
{'如果結構化資料庫有提供資料，以資料庫為主，不要自行編造不同的劑量。' if db_found else '請用 Google Search 搜尋最新的藥物劑量調整資訊。'}
{PROMPT_CONFIDENCE}"""

    contents = []
    contents.extend(_build_image_parts(images))
    contents.append(prompt)

    model = get_model_for_task("assist_dose")
    response = gemini_client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )
    )
    _log_token_usage(response, model, "assist")
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
        contents.append(f"【檢驗數據 / 臨床資訊】\n{anonymize_text(lab_data)}")
    contents.append(prompt)

    model = get_model_for_task("assist_lab")
    response = gemini_client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )
    )
    _log_token_usage(response, model, "assist")
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
        contents.append(f"【查詢內容】\n{anonymize_text(query_text)}")
    contents.append(prompt)

    model = get_model_for_task("assist_nhi")
    response = gemini_client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )
    )
    _log_token_usage(response, model, "assist")
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
        contents.append(f"【藥物列表】\n{anonymize_text(drugs_text)}")
    contents.append(prompt)

    model = get_model_for_task("assist_interaction")
    response = gemini_client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )
    )
    _log_token_usage(response, model, "assist")
    return response.text + ASSIST_DISCLAIMER


def _assist_transplant(data, images=None):
    """腎臟移植相關諮詢"""
    question = data.get('query', '') or data.get('scenario', '')
    if not question and not images:
        return "❌ 請提供移植相關問題或上傳圖片。"

    prompt = """你是一位腎臟移植專科醫師，崇尚實證醫學。
請根據以下移植相關問題提供建議。

【請依照以下格式回答】（Markdown）：

## 🏥 移植問題分析
（整理關鍵問題，如有圖片先描述圖片內容）

## 💊 免疫抑制劑建議
（含 Tacrolimus/Cyclosporine 目標濃度、MMF/AZA 劑量）
| 藥物 | 建議劑量 | 目標濃度 | 監測頻率 |
|------|----------|----------|----------|

## 🦠 感染風險評估
（BK virus, CMV, PJP prophylaxis timeline）
- **移植後 0-1 月**：
- **移植後 1-6 月**：
- **移植後 6-12 月**：
- **移植後 >12 月**：

## 📋 排斥反應鑑別
（T-cell mediated vs antibody-mediated, Banff classification）
| 特徵 | T-cell mediated | Antibody-mediated |
|------|----------------|-------------------|

## 🔬 建議檢查
（根據臨床情境建議的檢查項目）

## 📚 參考指引
（KDIGO Transplant Guidelines, Banff 2022）

全程使用繁體中文，醫學術語用「中文 (English)」格式。
請用 Google Search 搜尋補充最新的移植相關指引和實證。"""

    contents = []
    contents.extend(_build_image_parts(images))
    if question:
        contents.append(f"【移植相關問題】\n{anonymize_text(question)}")
    contents.append(prompt)

    model = get_model_for_task("assist_transplant")
    response = gemini_client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )
    )
    _log_token_usage(response, model, "assist")
    return response.text + ASSIST_DISCLAIMER


def _assist_pd(data, images=None):
    """腹膜透析相關諮詢"""
    question = data.get('query', '') or data.get('scenario', '')
    if not question and not images:
        return "❌ 請提供腹膜透析相關問題或上傳圖片。"

    prompt = """你是一位腹膜透析專科醫師，崇尚實證醫學。
請根據以下腹膜透析相關問題提供建議。

【請依照以下格式回答】（Markdown）：

## 🏥 PD 問題分析
（整理關鍵問題，如有圖片先描述圖片內容）

## 💧 PD 處方建議
（CAPD vs APD, 透析液選擇, dwell time）
| 處方模式 | 適應症 | 透析液濃度 | Dwell time | 交換次數 |
|----------|--------|-----------|------------|----------|

## 📊 Adequacy 評估
（Kt/V, Weekly CrCl, PET test 解讀）
| 指標 | 目標值 | 評估頻率 |
|------|--------|----------|
| Weekly Kt/V | >= 1.7 | 每 6 個月 |
| Weekly CrCl | >= 50 L/week/1.73m2 | 每 6 個月 |

### PET Test 分類
| PET 類型 | D/P Cr (4h) | 超濾量 | 建議處方 |
|----------|-------------|--------|----------|
| High | > 0.81 | 低 | Short dwell (APD) |
| High-average | 0.65-0.81 | 中等 | CAPD 或 APD |
| Low-average | 0.50-0.64 | 良好 | CAPD |
| Low | < 0.50 | 最佳 | Long dwell CAPD |

## 🦠 腹膜炎處置
（ISPD 2022 guidelines, 經驗性抗生素, 培養結果調整）

### 經驗性治療
- **Gram-positive coverage**：Cefazolin 或 Vancomycin (IP)
- **Gram-negative coverage**：Ceftazidime 或 Gentamicin (IP)

### 培養結果調整原則
| 培養結果 | 建議抗生素 | 療程 |
|----------|-----------|------|

## ⚠️ 併發症管理
（exit site infection, tunnel infection, hernias, hydrothorax）

## 📚 參考指引
（ISPD 2022 Peritonitis Guidelines, KDOQI PD Adequacy Guidelines）

全程使用繁體中文，醫學術語用「中文 (English)」格式。
請用 Google Search 搜尋補充最新的 PD 相關指引和實證。"""

    contents = []
    contents.extend(_build_image_parts(images))
    if question:
        contents.append(f"【腹膜透析相關問題】\n{anonymize_text(question)}")
    contents.append(prompt)

    model = get_model_for_task("assist_pd")
    response = gemini_client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )
    )
    _log_token_usage(response, model, "assist")
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
            _log_token_usage(response, GEMINI_MODEL, "other")
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
        _log_token_usage(response, GEMINI_MODEL, "other")
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
@require_auth
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
@require_auth
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
@require_auth
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
        _log_token_usage(response, GEMINI_MODEL, "other")
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
# 6b. 臨床計算器端點（純計算，零 AI 成本）
# ============================================================

try:
    from scoring_calculators import (
        calculate_egfr_ckd_epi, classify_ckd_stage, classify_aki_kdigo,
        calculate_fena, calculate_feurea, calculate_transtubular_k_gradient,
        calculate_urine_anion_gap, calculate_serum_anion_gap,
        calculate_corrected_calcium, calculate_calcium_phosphate_product,
        calculate_kt_v_daugirdas, calculate_urr, calculate_corrected_sodium,
        calculate_plasma_osmolality, calculate_osmolal_gap, winter_formula,
        classify_mest_c
    )
    print("✅ 臨床計算器模組已載入")
except ImportError:
    print("⚠️ scoring_calculators.py 未找到，計算器功能不可用")


CALCULATOR_REGISTRY = {
    "egfr": {"fn": "calculate_egfr_ckd_epi", "name": "eGFR (CKD-EPI 2021)", "params": ["creatinine", "age", "sex"]},
    "ckd_stage": {"fn": "classify_ckd_stage", "name": "CKD 分期", "params": ["egfr"]},
    "aki_staging": {"fn": "classify_aki_kdigo", "name": "AKI 分期 (KDIGO)", "params": ["baseline_cr", "current_cr"]},
    "fena": {"fn": "calculate_fena", "name": "FENa", "params": ["urine_na", "plasma_na", "urine_cr", "plasma_cr"]},
    "feurea": {"fn": "calculate_feurea", "name": "FEUrea", "params": ["urine_urea", "plasma_urea", "urine_cr", "plasma_cr"]},
    "ttkg": {"fn": "calculate_transtubular_k_gradient", "name": "TTKG", "params": ["urine_k", "plasma_k", "urine_osm", "plasma_osm"]},
    "urine_ag": {"fn": "calculate_urine_anion_gap", "name": "Urine Anion Gap", "params": ["urine_na", "urine_k", "urine_cl"]},
    "serum_ag": {"fn": "calculate_serum_anion_gap", "name": "Serum Anion Gap", "params": ["na", "cl", "hco3"]},
    "corrected_ca": {"fn": "calculate_corrected_calcium", "name": "校正鈣", "params": ["total_ca", "albumin"]},
    "ca_p_product": {"fn": "calculate_calcium_phosphate_product", "name": "鈣磷乘積", "params": ["ca", "phos"]},
    "kt_v": {"fn": "calculate_kt_v_daugirdas", "name": "Kt/V (Daugirdas)", "params": ["pre_bun", "post_bun", "t_hours", "uf_liters", "post_weight_kg"]},
    "urr": {"fn": "calculate_urr", "name": "URR", "params": ["pre_bun", "post_bun"]},
    "corrected_na": {"fn": "calculate_corrected_sodium", "name": "校正鈉", "params": ["measured_na", "glucose_mg_dl"]},
    "plasma_osm": {"fn": "calculate_plasma_osmolality", "name": "血漿滲透壓", "params": ["na", "bun_mg_dl", "glucose_mg_dl"]},
    "osm_gap": {"fn": "calculate_osmolal_gap", "name": "滲透壓差距", "params": ["measured_osm", "na", "bun_mg_dl", "glucose_mg_dl"]},
    "winter": {"fn": "winter_formula", "name": "Winter's Formula", "params": ["hco3"]},
    "mest_c": {"fn": "classify_mest_c", "name": "MEST-C (IgA 腎病)", "params": ["m", "e", "s", "t", "c"]},
}


@app.route('/calculators/list', methods=['GET'])
def calculators_list():
    """取得所有計算器清單（零 AI 成本）"""
    return jsonify({
        "calculators": {k: {"name": v["name"], "params": v["params"]} for k, v in CALCULATOR_REGISTRY.items()}
    })


@app.route('/calculators/compute', methods=['POST'])
def calculators_compute():
    """臨床計算器統一端點（零 AI 成本，純數學計算）"""
    data = request.get_json()
    calculator = data.get('calculator', '')
    params = data.get('params', {})

    if calculator not in CALCULATOR_REGISTRY:
        return jsonify({"error": f"不支援的計算器: {calculator}", "available": list(CALCULATOR_REGISTRY.keys())}), 400

    reg = CALCULATOR_REGISTRY[calculator]
    fn_name = reg["fn"]
    fn = globals().get(fn_name)
    if not fn:
        return jsonify({"error": f"計算器函數未載入: {fn_name}"}), 500

    try:
        # 將參數轉為數值
        numeric_params = {}
        for k, v in params.items():
            try:
                numeric_params[k] = float(v) if v != '' else None
            except (ValueError, TypeError):
                numeric_params[k] = v

        result = fn(**numeric_params)
        return jsonify({"calculator": calculator, "name": reg["name"], "result": result})
    except Exception as e:
        return jsonify({"error": f"計算錯誤: {str(e)}"}), 400


# ============================================================
# 6c. Clinical Pathway 端點
# ============================================================

from clinical_pathways import get_pathway_list, get_pathway_detail, get_step_by_id


@app.route('/pathways/list', methods=['GET'])
def pathways_list():
    """取得所有 clinical pathway 清單"""
    return jsonify({"pathways": get_pathway_list()})


@app.route('/pathways/<pathway_id>', methods=['GET'])
def pathway_detail(pathway_id):
    """取得特定 pathway 的完整內容和 mermaid"""
    detail = get_pathway_detail(pathway_id)
    if not detail:
        return jsonify({"error": f"找不到 pathway: {pathway_id}"}), 404
    return jsonify(detail)


@app.route('/pathways/<pathway_id>/interactive', methods=['POST'])
@require_auth
def pathway_interactive(pathway_id):
    """互動式 pathway — 根據使用者輸入的參數，AI 解讀在 pathway 中的位置"""
    detail = get_pathway_detail(pathway_id)
    if not detail:
        return jsonify({"error": f"找不到 pathway: {pathway_id}"}), 404

    if not gemini_client:
        return jsonify({"error": "Gemini API 未設定"}), 500

    data = request.get_json()
    patient_data = data.get('patient_data', '')

    if not patient_data:
        return jsonify({"error": "請提供病人資料 (patient_data)"}), 400

    # 建構 pathway 的文字描述
    steps_desc = ""
    for step in detail["steps"]:
        steps_desc += f"- [{step['id']}] {step['label']}: {step['detail']}\n"

    prompt = f"""你是一位腎臟科主治醫師。以下是一個臨床路徑：

【Clinical Pathway】: {detail['title_zh']} ({detail['title']})
【版本】: {detail['version']}
【步驟】:
{steps_desc}

【病人資料】:
{anonymize_text(patient_data)}

請根據病人資料，判斷此病人在這個 clinical pathway 中的位置，並提供建議：

【回答格式】（Markdown）：

## 📍 目前位置
（病人目前在 pathway 的哪個步驟，用步驟 ID 標示）

## 🔍 判斷依據
（為什麼判斷在這個位置）

## ➡️ 下一步建議
（根據 pathway，接下來應該做什麼）

## ⚠️ 注意事項
（此病人的特殊考量）

## 📚 參考指引

全程使用繁體中文，醫學術語用「中文 (English)」格式。
請用 Google Search 搜尋補充最新指引。"""

    try:
        model = get_model_for_task("pathway_interactive")
        response = gemini_client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            )
        )
        _log_token_usage(response, model, "assist")
        return jsonify({
            "result": response.text + ASSIST_DISCLAIMER,
            "pathway_id": pathway_id,
            "pathway_title": detail["title_zh"],
        })
    except Exception as e:
        print(f"❌ Pathway interactive error: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================
# 6b. OpenEvidence — Assist 模式 & Admin 端點
# ============================================================

def _assist_evidence(question):
    """OpenEvidence 實證查詢 — 直接回傳 OE 答案 + 引用文獻"""
    if not question:
        return "❌ 請提供醫學問題。"

    if not oe_client:
        return "❌ OpenEvidence 尚未設定。請先在 Settings 頁面上傳 cookie。"

    try:
        result = oe_client.get_formatted_result(question)

        # Track usage
        if db:
            month_key = time.strftime("%Y-%m")
            doc_ref = db.collection("token_usage").document(month_key)
            doc_ref.set({"month": month_key}, merge=True)
            doc_ref.update({
                "by_feature.openevidence.calls": firestore.Increment(1),
                "updated_at": firestore.SERVER_TIMESTAMP,
            })

        md = f"""## OpenEvidence 實證回答

{result.get('answer', '（無回答）')}

---

## 參考文獻 (OpenEvidence Citations)

{result.get('citations', '（無引用文獻）')}
"""
        return md + ASSIST_DISCLAIMER

    except Exception as e:
        print(f"❌ OE assist error: {e}")
        return f"❌ OpenEvidence 查詢失敗：{str(e)}"


@app.route('/admin/oe-status', methods=['GET'])
@require_admin
def get_oe_status():
    """取得 OpenEvidence cookie 狀態"""
    if not oe_cookie_mgr:
        return jsonify({"valid": None, "has_cookies": False, "message": "OE client not initialized"})
    return jsonify(oe_cookie_mgr.get_status())


@app.route('/admin/oe-cookies', methods=['POST'])
@require_admin
def update_oe_cookies():
    """上傳 OpenEvidence cookies"""
    data = request.get_json()
    token_info = verify_token(request)
    uid = token_info['uid'] if token_info else 'admin'

    if not oe_cookie_mgr:
        return jsonify({"error": "OE client not initialized"}), 500

    # Support both JSON object and raw string format
    cookies_dict = data.get('cookies')
    cookies_raw = data.get('cookies_raw', '')

    if not cookies_dict and cookies_raw:
        # Parse "name1=val1; name2=val2" format
        cookies_dict = {}
        for pair in cookies_raw.split(';'):
            pair = pair.strip()
            if '=' in pair:
                k, v = pair.split('=', 1)
                cookies_dict[k.strip()] = v.strip()

    if not cookies_dict:
        # Try parsing as JSON array (browser export format)
        cookies_json = data.get('cookies_json')
        if cookies_json:
            if isinstance(cookies_json, list):
                cookies_dict = {c['name']: c['value'] for c in cookies_json if 'name' in c and 'value' in c}
            elif isinstance(cookies_json, str):
                try:
                    parsed = json.loads(cookies_json)
                    if isinstance(parsed, list):
                        cookies_dict = {c['name']: c['value'] for c in parsed if 'name' in c and 'value' in c}
                    elif isinstance(parsed, dict) and 'cookies' in parsed:
                        cookies_dict = {c['name']: c['value'] for c in parsed['cookies'] if 'name' in c and 'value' in c}
                except json.JSONDecodeError:
                    pass

    if not cookies_dict:
        return jsonify({"error": "無法解析 cookies，請提供 JSON object 或 name=value; 格式"}), 400

    oe_cookie_mgr.save_cookies(cookies_dict, uid)

    # Validate
    valid = oe_cookie_mgr.validate()
    return jsonify({"success": True, "valid": valid, "cookie_count": len(cookies_dict)})


@app.route('/admin/oe-validate', methods=['POST'])
@require_admin
def validate_oe_cookies():
    """驗證 OpenEvidence cookies 是否有效"""
    if not oe_cookie_mgr:
        return jsonify({"valid": False, "message": "OE client not initialized"})
    valid = oe_cookie_mgr.validate()
    return jsonify({"valid": valid})


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