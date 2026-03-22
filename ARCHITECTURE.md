# Nephro Brain OS — 系統架構文件

> 腎臟科智慧中樞作業系統 (The Intelligence Operating System for Nephrology)

---

## 系統架構總覽

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Frontend   │────▶│    Backend API    │────▶│   Firebase      │
│   (Vercel)   │ SSE │  (Cloud Run)     │     │   (Firestore)   │
│   Vue 3      │◀────│  Flask + Gemini  │◀────│   + Storage     │
└─────────────┘     └──────────────────┘     └─────────────────┘
                           ▲
                           │ Daily cron
                    ┌──────┴───────┐
                    │   Crawler    │
                    │  (GitHub     │
                    │   Actions)   │
                    └──────────────┘
```

---

## 技術棧

| 層級 | 技術 | 說明 |
|------|------|------|
| **前端框架** | Vue 3.5 + Vite 6.3 | SPA 架構 |
| **樣式** | TailwindCSS 3.4 | Noto Sans TC + Inter 字體 |
| **資料庫** | Firebase Firestore + Storage | 聊天、文章、筆記、書籍 |
| **後端** | Python 3.12 + Flask 3.0 | Gunicorn 生產伺服器 |
| **AI 模型** | Gemini 2.5 Flash / Pro | 主要推理引擎 |
| **向量搜尋** | FAISS | 教科書 embedding 檢索 |
| **爬蟲** | Python + Groq LLaMA 3.3 | PubMed 文獻自動擷取 |
| **容器** | Docker (Python 3.12-slim) | Cloud Run 部署用 |

---

## 部署方式

### 前端 → Vercel

- **觸發**：push 到 `main` → Vercel 自動部署
- **設定檔**：`vercel.json`（所有路由 rewrite 到 `index.html`）
- **Build 指令**：`npm run build`（Vite 產出到 `dist/`）

### 後端 → Google Cloud Run

- **觸發**：push 到 `main` 且 `backend/**` 有變更 → GitHub Actions 自動部署
- **也可手動觸發**：GitHub Actions 頁面 → Run workflow
- **設定檔**：`.github/workflows/deploy.yml`
- **容器設定**：`backend/Dockerfile`（Python 3.12-slim + Gunicorn）
- **GCP Project**：`gen-lang-client-0247770936`
- **Service 名稱**：`nephro-brain-api`
- **Region**：`asia-east1`
- **API Base URL**：`https://nephro-brain-api-761804517300.asia-east1.run.app`

### 爬蟲 → GitHub Actions 排程

- **設定檔**：`.github/workflows/crawl-daily.yml`
- **排程**：每天 UTC 22:00（台灣時間 06:00）
- **腳本**：`crawlers/crawler_v2.py`
- **也可手動觸發**：GitHub Actions 頁面 → Run workflow

---

## 環境變數 / GitHub Secrets

| 變數 | 用途 | 設定位置 |
|------|------|----------|
| `GCP_SERVICE_ACCOUNT_KEY` | Cloud Run 部署認證 | GitHub Secrets |
| `GOOGLE_API_KEY` | Gemini API 呼叫 | GitHub Secrets + Cloud Run 環境變數 |
| `GROQ_API_KEY` | 爬蟲用 LLaMA 模型 | GitHub Secrets |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | 爬蟲存取 Firestore | GitHub Secrets |

---

## 四大模組

| 模組 | 路由 | 功能 |
|------|------|------|
| **NB Insight** | `/insight` | 每日文獻情報，PubMed 自動收錄與摘要 |
| **NB Consult** | `/consult` | RAG 問答引擎（教科書 + PubMed + Gemini） |
| **NB Teach** | `/teach` | 教學素材生成（投影片 / 閃卡 / 心智圖） |
| **NB Assist** | `/assist` | 臨床決策支援（計算器 / 藥物 / 路徑 / 健保規則） |

---

## 專案目錄結構

```
Nephro-brain-os/
├── src/                           ← 前端原始碼
│   ├── views/                     ← 6 個頁面
│   │   ├── LandingPage.vue           首頁
│   │   ├── InsightPage.vue           NB Insight
│   │   ├── ConsultPage.vue           NB Consult
│   │   ├── NotesPage.vue             NB Notes
│   │   ├── TeachPage.vue             NB Teach
│   │   └── AssistPage.vue            NB Assist
│   ├── components/                ← 24 個元件
│   │   ├── assist/                   10 個臨床工具元件
│   │   │   ├── AssistCalculator.vue     醫學計算器
│   │   │   ├── AssistDose.vue           藥物劑量調整
│   │   │   ├── AssistDrugSearch.vue     本地藥物查詢
│   │   │   ├── AssistLab.vue            檢驗值判讀
│   │   │   ├── AssistNhi.vue            健保規則
│   │   │   ├── AssistPathway.vue        臨床路徑
│   │   │   ├── AssistClinical.vue       臨床查詢
│   │   │   ├── AssistPD.vue             腹膜透析
│   │   │   ├── AssistTransplant.vue     腎移植
│   │   │   └── AssistInteraction.vue    藥物交互作用
│   │   ├── NavBar.vue
│   │   ├── ChatMessage.vue
│   │   ├── NoteEditor.vue / NoteCard.vue
│   │   ├── ArticleCard.vue / ArticleDetail.vue
│   │   ├── MindMap.vue
│   │   └── ...
│   ├── composables/               ← 9 個 Vue composable
│   │   ├── useConsultChat.js         RAG 對話管理
│   │   ├── useAssist.js              臨床決策支援
│   │   ├── useTeach.js               教學內容生成
│   │   ├── useArticles.js            文獻顯示
│   │   ├── useNotes.js               筆記 CRUD
│   │   ├── useBooks.js               教科書整合
│   │   ├── useCollection.js          Firestore 通用
│   │   ├── useMermaid.js             流程圖渲染
│   │   └── useUserRole.js            訪客/專業版權限
│   ├── utils/
│   │   └── renderMarkdown.js      ← Markdown 轉 HTML（含摘要卡片、表格、Mermaid）
│   ├── firebase.js                ← Firebase 設定（project: nephro-brain）
│   └── router.js                  ← 前端路由
│
├── backend/                       ← 後端原始碼
│   ├── api_server.py              ← 主 API（23 個 endpoint）
│   ├── scoring_calculators.py     ← 16 個醫學計算器
│   ├── clinical_pathways.py       ← 6 條臨床路徑
│   ├── drug_database.json         ← 20 種藥物資料庫
│   ├── Dockerfile                 ← Cloud Run 容器設定
│   └── requirements.txt           ← Python 相依套件
│
├── crawlers/                      ← PubMed 爬蟲
│   ├── crawler_v2.py              ← 多層級實證文獻爬蟲
│   └── requirements_v2.txt
│
├── .github/workflows/             ← CI/CD
│   ├── deploy.yml                 ← 後端自動部署到 Cloud Run
│   └── crawl-daily.yml            ← 每日 PubMed 爬蟲排程
│
├── index.html                     ← SPA 進入點
├── package.json                   ← 前端相依套件
├── vite.config.js                 ← Vite 設定
├── tailwind.config.js             ← TailwindCSS 設定
├── postcss.config.js              ← PostCSS 設定
├── vercel.json                    ← Vercel 部署設定
└── styles.css                     ← 全域主題樣式（深色/淺色）
```

---

## 後端 API Endpoint 一覽

### 核心問答
| Method | Path | 說明 |
|--------|------|------|
| POST | `/ask` | 同步問答 |
| POST | `/ask-stream` | 串流問答 (SSE) |
| POST | `/consult/chat-stream` | 對話式串流問答 |

### 臨床工具
| Method | Path | 說明 |
|--------|------|------|
| POST | `/assist/query` | 統一臨床查詢入口 |
| GET | `/calculators/list` | 計算器清單（16 個） |
| POST | `/calculators/compute` | 執行計算 |
| GET | `/pathways/list` | 臨床路徑清單（6 條） |
| GET | `/pathways/<id>` | 路徑詳情 |
| POST | `/pathways/<id>/interactive` | 互動式路徑導航 |

### 藥物查詢
| Method | Path | 說明 |
|--------|------|------|
| GET | `/drugs/search?q=` | 藥物搜尋 |
| GET | `/drugs/<name>` | 藥物詳情（含交互作用、劑量） |

### 教學內容
| Method | Path | 說明 |
|--------|------|------|
| POST | `/teach/generate` | 生成投影片/閃卡/心智圖 |

### 文獻管理
| Method | Path | 說明 |
|--------|------|------|
| GET | `/public-feed` | 公開文章列表 |
| POST | `/fetch-journal-issue` | 抓取期刊 |
| POST | `/generate-article-summary` | AI 文章摘要 |

### 系統
| Method | Path | 說明 |
|--------|------|------|
| GET | `/health` | 健康檢查 |
| GET | `/stats` | 伺服器統計 |

---

## 存取控制

- **訪客模式**：受限功能（GuestLock 元件控制）
- **專業版**：完整 AI 功能（驗證碼：`nephro2026`）
- **儲存位置**：Firebase + LocalStorage

---

## 本地開發

```bash
# 前端
npm install
npm run dev                        # http://localhost:5173

# 後端
cd backend
pip install -r requirements.txt
python api_server.py               # http://localhost:8080

# 爬蟲（手動執行）
cd crawlers
pip install -r requirements_v2.txt
python crawler_v2.py

# 前端 production build
npm run build
```

---

## 部署 Checklist

### 後端部署（Cloud Run）
1. 確認 `backend/Dockerfile` 有 COPY 所有需要的檔案
2. 確認 GCP 已啟用 Cloud Run Admin API
3. Push `backend/**` 變更到 `main` 分支
4. GitHub Actions 自動觸發，或手動 Run workflow
5. 驗證：`GET /health` 回傳正常

### 前端部署（Vercel）
1. Push 到 `main` 分支
2. Vercel 自動 build & deploy
3. 驗證：網站正常載入

---

*最後更新：2026-03-22*
