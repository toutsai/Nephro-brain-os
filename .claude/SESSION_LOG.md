# Session Log

## 最近一次更新
- **日期**：2026-03-30
- **完成事項**：
  1. Insight 搜尋主題從 7 個擴充到 13 個（新增 CKM、HTN、PKD、CKD-MBD、Stone、Onco-Nephro）
  2. 前端改用 30 天時間範圍 + limit(300)，收藏庫不受限制
  3. Insight 改為三欄式佈局（左側 sidebar + 文章列表 + 文章詳情）
  4. 手機版改用下拉選單取代橫向 tab
  5. 五個頁面統一高度（扣除 NavBar）、統一全寬佈局
  6. NavBar 導航靠左排列、sub-header 格式統一
  7. 行動版全面優化：100dvh、觸控目標增大、文字放大、PWA manifest
  8. TeachPage 手機版新增返回按鈕
  9. 建立 Claude Code 工作流程自動化設定
- **未完成**：
  - PWA icon 檔案（icon-192.png、icon-512.png、apple-touch-icon.png）需要設計提供
  - Service Worker 離線支援（vite-plugin-pwa）
  - 現有文章的 topic 重新分類（新主題只對新文章生效）
- **下次待辦**：
  - 提供 PWA icon 圖片
  - 考慮是否需要 re-tagging script 為現有文章重新分類
  - 行動版實機測試與微調
- **重要決策**：
  - 主題分類採用寫死方式（非 AI 動態生成），因為 PubMed 查詢需要精確語法
  - MAX_ARTICLES_PER_RUN 從 60 提高到 80
  - 前端顯示改用 30 天 + 300 篇雙重限制
  - 頁面佈局全部改為全寬（移除 max-w-7xl）
