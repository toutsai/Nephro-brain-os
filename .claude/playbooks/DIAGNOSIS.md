# Harness 快速診斷（2026-07-06，Fable 5 制度設計 session）

本檔是這套制度的「為什麼」。後面所有 playbook 的規則都源自這三個問題。
改動任何 playbook 前先讀本檔，確認你的改動不會讓這三個問題復發。

## 問題 1：SESSION_LOG.md 全文注入每個 session，且無限增長

**症狀**：`.claude/settings.json` 的 SessionStart hook 會 `cat` 整份 SESSION_LOG.md。
制度改革前已達 159 行（約 4k tokens），且格式是 append-only（「最近一次更新」＋「上一次更新」＋歷史紀錄全部保留）。
每個 session 開場就固定燒掉這筆 token，而且逐月變胖——半年後可能是 500 行。

**修法（已實施）**：
- SESSION_LOG.md 只保留「目前狀態」：上限 **80 行**，超過就把舊內容搬走。
- 歷史搬到 `.claude/SESSION_ARCHIVE.md`（不會自動載入，需要時才讀）。
- Hook 不變（仍 cat SESSION_LOG.md），靠檔案本身瘦身。
- 容量規則與搬運格式寫在 `maintenance.md`。

## 問題 2：規則重複且互相衝突，弱模型會停擺或做危險動作

**症狀**：
- CLAUDE.md 的「工作流程」與 `.claude/rules/workflow.md` 內容約 80% 重複，且兩者都自動載入＝同一套規則付兩次 token。
- 「使用者確認 plan 前絕對不得實作」在遠端自主 session（使用者不在線）會讓整個 session 停擺等一個永遠不會來的確認。
- 「完成後自動 commit、push、建 PR、merge 到 main」——main 就是 production（Vercel 自動部署），這個 repo 又**沒有測試套件**，自動 merge 等於無防護上線。遠端 harness 的 draft PR 流程與它直接衝突，弱模型會二選一亂猜。

**修法（已實施）**：
- 單一事實來源＝CLAUDE.md。`.claude/rules/workflow.md` 已刪除（備份在 `.claude/archive/2026-07-06-pre-fable5/`）。
- 衝突規則按「使用者是否在線」分流，具體判準寫在 CLAUDE.md 工作流程一節與 `judgment.md` 第 3 條。
- 品質底線（build 驗證）從「建議」升格為 merge 前的硬性條件，見 `judgment.md` 第 5 條。

## 問題 3：沒有派工合約，主對話被原始資料淹死

**症狀**：舊規則說「用 2-3 個 Explore agents 並行探索」，但沒規定：
- 派工時要給什麼（目標？驗收條件？回報格式？）→ agent 自由發揮，常整包檔案內容回傳主對話。
- 主對話自己能不能下場讀檔？→ 沒禁止，弱模型傾向自己 grep 全 repo、開十幾個大檔，context 塞滿原始碼後開始失焦、忘記原始任務。
- 誰驗收？→ 沒人。寫完的 code 由寫的那個 context 自己說「完成了」，自驗等於沒驗。

**修法（已實施）**：
- `dispatch.md`：指揮官不下場原則＋派工三件套（目標與動機、驗收條件、回報格式）＋回報合約（只回結論與檔案:行號，長產物落檔傳路徑）。
- `templates.md`：五種任務型態的填空模板，把合約變成 copy-paste 就能用。
- `.claude/agents/verifier.md`：獨立的 fresh-context 驗收 agent，驗證不自驗。

## 次要發現（未列前三，但要知道）

- **無測試套件**：前端唯一可機器驗證的是 `npm run build`（vite），後端只有 `python -m py_compile`。這是結構性風險，見 letter 第 3 點。
- **雙環境**：這個 repo 同時在本機 Windows（settings.local.json 有 `gh.exe`、`/c/Users/` 路徑）與遠端 cloud session 使用。規則寫法必須兩邊都能執行——遠端沒有 `gh` CLI，要用 GitHub MCP tools。
- **部署斷層**：backend merge 到 main ≠ 部署。Cloud Run 要手動 `gcloud run deploy`，這步只有使用者本機能做，session 結束前必須明確提醒。
