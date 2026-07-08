# 模型調度守則（dispatch.md）

適用對象：本 repo 每一個 Claude Code session 的主對話模型（不論是 Haiku、Sonnet 還是 Opus）。
目的：主對話的 context 是最稀缺的資源，本守則規定什麼事必須派出去、怎麼派、怎麼收。

## 1. 指揮官不下場

主對話（＝你）只做：理解需求、拆解任務、派工、整合結論、與使用者對話、最終決策。

**以下工作一律派 subagent，主對話不得自己做：**

| 工作 | 派給 | 理由 |
|---|---|---|
| 探索 codebase、找「X 在哪裡實作」 | `Explore` agent | 它會讀幾十個檔案，那些內容不該進主 context |
| 掃整個 repo（找所有呼叫點、所有用到某 pattern 的地方） | `Explore` agent（prompt 註明 "very thorough"） | 同上 |
| 查網頁 / 文件 / 外部 API 規格 | `general-purpose` agent | 網頁內容又長又髒 |
| 批次修改多個檔案（同一 pattern 套用到 N 處） | 多個 `general-purpose` agents 並行 | 主對話只需要「改了哪些檔、build 過了沒」 |
| 讀超過 ~300 行的單一檔案來回答一個問題 | `Explore` agent（問題寫進 prompt） | 你要的是答案，不是檔案 |
| 設計實作方案 | `Plan` agent | 回傳 plan，不是過程 |
| 驗收別的 agent 的產出 | `verifier` agent（見第 6 節） | 驗證不自驗 |

**主對話可以自己做的**：讀單一小檔或指定行段（`Read` 帶 offset/limit）、單次精準 `Grep`/`Glob`、跑 build/測試指令、git 操作、寫少量檔案、直接改 1-2 個已經定位好的小地方。
判斷法：**動手前能說出「我要開哪個檔案的哪一段」→ 自己做；只能說出「我要去找…」→ 派工。**

## 2. 可用的 agent types 與模型

本環境的 Agent tool 可用 `subagent_type`：`Explore`（唯讀搜尋）、`Plan`（架構規劃）、`general-purpose`（可讀可寫可跑指令）、`claude`（通用）、`claude-code-guide`（問 Claude Code 本身的用法）、`verifier`（本 repo 自訂，見 `.claude/agents/verifier.md`）。
若某型號在你的 harness 不存在（工具會報錯或 system prompt 的清單裡沒有），fallback 到 `general-purpose`。

Agent tool 的 `model` 參數本環境實測可用值：`haiku`、`sonnet`、`opus`。
（`fable` 只在特定 session 存在，規則不得依賴它。）

**model 分工表：**

| model | 用在 | 具體例子 |
|---|---|---|
| `haiku` | 機械性、已有明確 pattern 可套的批次工作 | 把已驗證過的修法套到剩下 8 個檔案；格式化；改字串；照清單逐項確認檔案存在 |
| `sonnet` | 預設值。搜尋、規格明確的實作、一般審查、研究整理 | 「在 InsightPage 加一個 org 篩選 chip，比照現有 NICE chip 寫法」 |
| `opus` | 難題：跨多模組的架構設計、抓不到根因的 bug、模糊需求的方案取捨、最終仲裁 | 「三層 RAG 搜尋偶發回空結果，Sonnet 查了兩輪沒找到根因」 |

不確定用哪個 → 用 `sonnet`。省錢不是目標，**主對話 context 乾淨 + 一次做對**才是。

**關於 effort**：本環境的 Agent tool 沒有 effort 參數。控制深度的實際手段：
1. 選 model（上表）。
2. 在 prompt 裡寫明範圍："quick check"（只看最可能的 2-3 處）vs "medium"（正常）vs "very thorough"（掃多個位置與命名慣例，寧可多花時間不可漏）。
3. 自訂 agent 定義檔（`.claude/agents/*.md` frontmatter）可固定 model 與行為，如 verifier。
（Workflow 工具的 `agent()` 有 `effort` 選項，但 Workflow 需使用者明說才能用，日常不用。）

## 3. 派工三件套（每個 subagent prompt 必含）

1. **目標與動機**：要做什麼＋為什麼（上游任務是什麼）。agent 遇到邊界情況時，動機讓它做出正確取捨。
2. **驗收條件**：可機器檢查或可明確判定的完成定義。「找出所有呼叫點」不合格；「列出每個呼叫 `search_knowledge_base` 的檔案:行號，我預期至少在 api_server.py 出現」合格。
3. **回報格式**：規定回什麼、不回什麼、長度上限（見第 4 節）。

現成模板在 `templates.md`，直接填空，不要即興發揮。

## 4. 回報合約（收工標準）

subagent 的最終回覆必須是：
- **結論先行**：第一段直接回答問題／宣告結果。
- **證據用 `檔案路徑:行號`**，不貼大段程式碼（單段引用 ≤10 行）。
- **長產物落檔**：報告、清單、diff 摘要超過 ~30 行就寫到檔案（scratchpad 或 repo 內適當位置），回覆只給路徑＋3 行摘要。
- **明確標注失敗與不確定**：「沒找到」「跑不起來」「這部分是推測」要寫出來，不准含糊帶過。

主對話收到回報後：只把**結論**留在對話裡；需要細節時去讀落檔的產物，不要叫 agent 重講一遍。

## 5. 升降級路徑

- **haiku 錯一次 → 直接升 sonnet**。不要跟便宜模型糾纏。
- **sonnet 同一個子任務連錯兩次 → 升 opus**，且升級 prompt 必附完整失敗軌跡：兩次分別怎麼做、哪裡錯、錯誤訊息原文。不附軌跡的升級等於重來第三次。
- **opus 解出模式後 → 降回 haiku/sonnet 批次套用**：把 opus 找到的修法寫成明確步驟（改哪裡、改成什麼、怎麼驗證），派便宜模型套到其餘位置。
- **同一件事最多重試兩輪**。兩輪後還不行，代表方向可能錯了——停下來，走 `judgment.md` 第 4 條（換路判準），或問使用者。

## 6. 驗證不自驗

寫產出的 context 不能自己宣告合格。驗收一律派 **fresh-context agent**（沒看過實作過程的新 agent）：

- **檔案類產出**（文件、設定、資料檔）：派 `verifier` 做 read-back——實際打開檔案，逐條對照驗收條件。
- **程式碼**：能跑就跑。前端 `npm run build`；Python `python -m py_compile`；有可執行的驗證方式就實跑，沒有就派 verifier 讀 diff 對照驗收條件。
- **高風險判斷**（架構決策、會動到 production 行為、醫療內容規則）：
  - 第二意見：派另一個 agent 獨立作答同一問題（不給它第一個答案），比對結論；分歧就升 opus 仲裁或問使用者。
  - 或多答案評審：3 個 agents 各給方案，1 個 opus 評審選優並說明理由。
- verifier 回報「不合格」時，把不合格清單交回原任務（或新 agent）修，**修完再驗一次**，直到通過。

## 7. 並行與依序

- 彼此獨立（不碰同一批檔案）→ 一次派多個 agents 並行（同一則訊息裡多個 tool call）。
- 會碰同一檔案 → 依序，後一個的 prompt 附前一個改了什麼。
- 並行上限用常識：一次 2-4 個。派 10 個你自己會整合不完。
