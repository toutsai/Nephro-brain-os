"""上傳知識庫索引到 Firebase Storage"""
import firebase_admin
import json
import os
from firebase_admin import credentials, storage
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

cred_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "serviceAccountKey.json")
if not firebase_admin._apps:
    if cred_json.strip().startswith("{"):
        cred = credentials.Certificate(json.loads(cred_json))
    else:
        cred = credentials.Certificate(cred_json)
    firebase_admin.initialize_app(cred, {"storageBucket": "nephro-brain.firebasestorage.app"})

bucket = storage.bucket()
for f in ["knowledge_base.index", "knowledge_base_data.pkl"]:
    if os.path.exists(f):
        blob = bucket.blob(f"brain_memory/{f}")
        blob.upload_from_filename(f)
        print(f"Uploaded {f}")
    else:
        print(f"File not found: {f}")
