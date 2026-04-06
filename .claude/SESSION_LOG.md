# Session Log

## 最近一次更新
- **日期**：2026-04-06
- **完成事項**：
  1. **Consult → Insight 相關文獻推薦**：問答完成後自動推薦相關 Insight 文章（純前端 keyword→topic 匹配，零後端修改）
  2. **LandingPage Dashboard**：首頁改寫為即時統計儀表板（今日/30日文獻數、知識庫、AI 用量、模組入口 grid）
  3. **Insight 臨床指引區（KDIGO & KDOQI）**：
     - 新增 `guidelines` Firestore collection + `useGuidelines` composable
     - GuidelineCard / GuidelineDetail 元件
     - InsightPage 側邊欄新增「臨床指引」tab（含 KDIGO/KDOQI 篩選）
     - 手機版完整支援（下拉選單 + 底部彈出詳情）
  4. **種子資料腳本**：`crawlers/seed_guidelines.py`（18 KDIGO + 8 KDOQI = 26 部指引）
  5. **Firestore rules 更新**：guidelines collection 公開讀取
- **未完成**：
  - 需手動執行 `python crawlers/seed_guidelines.py` 填入指引資料到 Firestore
  - 需手動執行 `firebase deploy --only firestore:rules` 部署規則
  - 指引區 Phase 2：版本更新差異分析（延後）
  - 指引區 Phase 3：解析指引內容存入 Firestore 供 RAG 查詢（延後）
  - 精選問答初始資料填入（延後自上次）
  - 行動版實機測試所有新功能
- **下次待辦**：
  - 執行 seed_guidelines.py 寫入 26 部指引到 Firestore
  - 部署 firestore.rules（firebase deploy --only firestore:rules）
  - 部署 backend（如有需要）
  - Phase 2：KDIGO/KDOQI 版本追蹤與更新差異分析
  - Phase 3：指引內容解析 → RAG 整合
- **重要決策**：
  - 相關文獻推薦採純前端方案（用一次性 getDocs 載入 articles_v2，避免重複 real-time listener）
  - 指引區放在 InsightPage 側邊欄 specialTabs 中（而非獨立頁面），保持統一瀏覽體驗
  - selectedGuideline 與 selectedArticle 分開管理，避免型別衝突
  - LandingPage 統一呼叫所有 composables（不條件性呼叫），用 v-if 控制顯示
  - KDIGO 指引 URL 使用 kdigo.org/guidelines/，KDOQI 使用 ajkd.org 或 kidney.org

## 歷史紀錄

### 2026-04-02（第二次更新）
- Insight 新文章 badge、本日快訊
- Consult 精選問答區
- Teach PPT 選項擴充（頁數 4 檔 + 自動配色）
- Assist 圖片貼上（Ctrl+V + 拖曳）
- 跨模組連動優化、PWA icons、Service Worker、re-tagging 腳本

### 2026-04-02（第一次更新）
- 跨模組連動優化（Notes→Consult、Insight→Teach、Assist→Consult/Teach、Teach→Consult）
- 抽取 useTeachPicker composable
- PWA icon 生成 + vite-plugin-pwa 設定
- 文章 re-tagging 腳本

### 2026-03-30
- Insight 搜尋主題從 7 個擴充到 13 個
- 前端改用 30 天時間範圍 + limit(300)
- Insight 改為三欄式佈局
- 手機版改用下拉選單取代橫向 tab
- 五個頁面統一高度、統一全寬佈局
- 行動版全面優化
- 建立 Claude Code 工作流程自動化設定
