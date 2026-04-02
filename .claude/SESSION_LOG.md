# Session Log

## 最近一次更新
- **日期**：2026-04-02
- **完成事項**：
  1. 跨模組連動優化 — 補齊所有缺失的模組間連結：
     - Notes → Consult：筆記加「🔍 問答」按鈕
     - Insight → Teach：文章加「🎓 加到 Teach」按鈕
     - Assist → Consult + Teach：結果加「🔍 深入問答」和「🎓 加到 Teach」按鈕
     - Teach → Consult：教材加「🔍 深入問答」按鈕
  2. 抽取 `useTeachPicker.js` composable，消除 ConsultPage 和 NotesPage 中 ~80 行重複代碼
  3. 生成 PWA icon 檔案（icon-192.png、icon-512.png、apple-touch-icon.png）
  4. 設定 vite-plugin-pwa（Service Worker 離線快取 + API NetworkFirst + Google Fonts CacheFirst）
  5. 撰寫 `crawlers/retag_articles.py` 批次重新分類文章主題腳本（支援 --dry-run）
- **未完成**：
  - re-tagging 腳本尚未實際執行（需要 Firebase credentials）
  - Consult → Insight 相關文獻推薦（延後，UX 設計複雜）
  - LandingPage dashboard（延後，維護成本高）
- **下次待辦**：
  - 執行 retag_articles.py --dry-run 確認結果正確後再正式執行
  - 考慮 Consult → Insight 文獻推薦功能
  - 行動版實機測試 PWA 安裝體驗
- **重要決策**：
  - Teach picker 邏輯抽成共用 composable 而非繼續複製
  - PWA icon 用 SVG → PNG 方式自動生成（深色底 + NB 文字）
  - vite-plugin-pwa 使用 manifest: false 沿用既有 public/manifest.json
  - re-tagging 腳本複製 detect_topics() 而非 import（避免 crawler_v2.py 的副作用）

## 歷史紀錄

### 2026-03-30
- Insight 搜尋主題從 7 個擴充到 13 個
- 前端改用 30 天時間範圍 + limit(300)
- Insight 改為三欄式佈局
- 手機版改用下拉選單取代橫向 tab
- 五個頁面統一高度、統一全寬佈局
- 行動版全面優化：100dvh、觸控目標增大、文字放大、PWA manifest
- 建立 Claude Code 工作流程自動化設定
