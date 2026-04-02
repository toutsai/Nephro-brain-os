# Session Log

## 最近一次更新
- **日期**：2026-04-02（第二次更新）
- **完成事項**：
  1. **Insight 新文章 badge**：側邊欄主題旁顯示紅底白字新文章數量
  2. **Insight 本日快訊**：側邊欄頂部摺疊區塊，摘要今日新增文章（點擊跳轉）
  3. **Consult 精選問答區**：新 tab，所有登入使用者可新增 Q&A（Markdown 回答、分類篩選、只能刪除自己的）
  4. **Teach PPT 選項擴充**：頁數 4 檔（精簡 5-9 / 中等 10-14 / 完整 15-20 / 自動）+ 配色新增「自動推薦」
  5. **Assist 圖片貼上**：ImageUploader 支援 Ctrl+V 剪貼簿貼上 + 拖曳圖片 + 視覺回饋
  6. （延續上次）跨模組連動優化、PWA icons、Service Worker、re-tagging 腳本
- **未完成**：
  - re-tagging 腳本尚未實際執行
  - Consult → Insight 相關文獻推薦（延後）
  - LandingPage dashboard（延後）
  - 精選問答的管理員 pin/排序功能（未來可加）
- **下次待辦**：
  - 執行 retag_articles.py
  - 精選問答初始資料填入
  - 行動版實機測試所有新功能
  - 部署 firestore.rules 更新（需手動 firebase deploy --only firestore:rules）
  - 部署 backend 更新（PPT prompt 變更）
- **重要決策**：
  - 精選問答改為「所有使用者可新增」（非僅 admin），自己只能刪除自己的
  - PPT 自動配色由 AI 在 JSON 中回傳 recommended_theme
  - ImageUploader 加入 document-level paste 監聽（在非 input 聚焦時全域生效）
  - 本日快訊預設摺疊，避免佔用太多側邊欄空間

## 歷史紀錄

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
