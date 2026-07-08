# Session Log（目前狀態）

> 容量上限 80 行。超過時把最舊的 session 摘要搬到 `.claude/SESSION_ARCHIVE.md` 最上方。
> 格式規則見 `.claude/playbooks/maintenance.md`。本檔每次 session 開場會全文自動載入——只放「下個 session 需要知道的事」，不放歷史。

## 最近一次 session：2026-07-08（成本審視 + 兩份 plan 實作）

- **制度**：PR #94/#95 已 merge，`.claude/playbooks/` 制度生效。
- **止血包 PR #96 已 merge（⚠️ 未部署）**：修 study_quality 丟棄、Dockerfile 補 nhi_database.json、rebuild 索引改每月、前端顯示文章優劣。**Dockerfile 改動需重新部署 backend 才生效**。
- **PR #97 已 merge（⚠️ 未部署）**：①grounding 按需第一階段（環境變數 `GROUNDING_OPTIMIZE` 預設 false＝只加 log 零行為改變，未來看 `grounding_logs` 數據後設 true 才省錢）②新價值功能：`kg_generate_insights.py`→`kg_insights`、`kg_check_guideline_updates.py`→`kg_guideline_flags`，backend review API + 前端待審核區 + rules/indexes + 週三/週五排程。全部 pending、強制引用來源。

## 待部署（#96/#97 都在 main 未部署，使用者本機執行）

1. `gcloud run deploy nephro-brain-api --source ./backend --region asia-east1 --clear-base-image`（#96 的 nhi + #97 的 backend）。
2. `firebase deploy --only firestore`（#97 的 rules + indexes）。
3. grounding 省錢：先觀察 `grounding_logs`，有信心才在 Cloud Run 設 `GROUNDING_OPTIMIZE=true`。
4. 新爬蟲先 `--dry-run --limit 5` 試跑看產出品質，再靠排程自動化。

## 系統目前狀態（截至 2026-04-14，之後未再變動）

- Knowledge Graph Phase 1 + 2 已 merge 到 main 並部署（434 concepts、66,768 links）。
- Cloud Run 後端、Firestore rules/indexes 皆已部署。
- 每月自動化：PubMed backfill（每月 1 日）、guideline PDF 處理（每月 15 日）；每週：Cochrane / SR / ClinicalTrials 爬蟲。

## 待辦（依優先序）

1. 手動觸發 GitHub Actions「PubMed Monthly Backfill」（months_back=12）做首次全量回溯。
2. 跑 `crawlers/kg_generate_synthesis.py` 為 top 概念產生整合摘要。
3. KG Phase 3：Review tab + approve/reject 流程；`kg_gap_analysis.py` 缺口週報；排程（kg_process_consults 每日、kg_auto_link + synthesis 每週）。
4. 觀察每週 GitHub Actions 排程是否正常觸發。

## 重要架構決策（不可輕易推翻，推翻前先問使用者）

- **KG 是 overlay，不替換三層搜尋**：RAG pipeline 不動，KG 只做瀏覽/審核/缺口偵測。
- **Consult 三層搜尋**：結構化查表（drug/NHI JSON）→ 本地 FAISS 向量搜尋 → 外部搜尋（PubMed/Google/OpenEvidence）。
- **雙 FAISS 索引**：教科書（nephro_brain.index）與知識庫（knowledge_base.index）分開，互不影響。
- **AI 產出預設 pending、批次而非即時**：醫療內容需人工審核。
- **Firestore 而非 Neo4j**：規模 ~500 concepts / ~10K links 用現有 stack 即可。
- **藥物名稱一律英文**（也寫在 CLAUDE.md 硬規則）。
- **NHI 結構化優先**：`_assist_nhi()` 先查 JSON，找不到才 AI + Google Search。
- **Cochrane 走 PubMed 搜尋**（免付費 API）；**ClinicalTrials 獨立 collection**（schema 差異大，Groq 翻譯）。
