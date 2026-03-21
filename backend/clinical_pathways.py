"""
Nephro Brain OS — Clinical Pathway Engine
結構化臨床路徑系統，可輸出 Mermaid 流程圖
"""

PATHWAYS = {
    "aki_workup": {
        "title": "AKI Workup Pathway",
        "title_zh": "急性腎損傷評估流程",
        "version": "KDIGO 2024",
        "steps": [
            {
                "id": "A",
                "label": "確認 AKI",
                "detail": "Cr 上升 >=0.3 mg/dL (48h) 或 >=1.5x baseline (7d) 或尿量 <0.5 mL/kg/h x6h",
                "next": ["B"],
            },
            {
                "id": "B",
                "label": "初步評估",
                "detail": "生命徵象、體液狀態、用藥審視（NSAIDs, ACEi/ARB, aminoglycoside）、尿液分析",
                "next": ["C", "D", "E"],
            },
            {
                "id": "C",
                "label": "Pre-renal 評估",
                "detail": "FENa <1%, BUN/Cr >20, 尿比重 >1.020, 尿 Na <20 mEq/L",
                "next": ["C1"],
            },
            {
                "id": "C1",
                "label": "體液復甦",
                "detail": "晶體液 bolus, 停用腎毒性藥物, 監測 urine output 及 Cr 變化",
                "next": ["C2"],
            },
            {
                "id": "C2",
                "label": "48h 內追蹤 Cr",
                "detail": "若 Cr 改善 → 持續治療; 若未改善 → 考慮 intrinsic cause",
                "next": [],
            },
            {
                "id": "D",
                "label": "Intrinsic renal 評估",
                "detail": "尿液沉渣（RBC cast, WBC cast, muddy brown cast）, 蛋白尿定量, 補體, ANCA, anti-GBM",
                "next": ["D1", "D2", "D3"],
            },
            {
                "id": "D1",
                "label": "ATN (急性腎小管壞死)",
                "detail": "Muddy brown casts, FENa >2%, 常見原因：缺血、腎毒素",
                "next": ["D4"],
            },
            {
                "id": "D2",
                "label": "AIN (急性間質性腎炎)",
                "detail": "WBC casts, 嗜酸性球尿, 常見藥物：PPI, antibiotics, NSAIDs",
                "next": ["D4"],
            },
            {
                "id": "D3",
                "label": "GN (腎絲球腎炎)",
                "detail": "RBC casts, dysmorphic RBC, 蛋白尿, 需緊急腎臟切片",
                "next": ["D4"],
            },
            {
                "id": "D4",
                "label": "考慮腎臟切片",
                "detail": "適應症：不明原因 AKI, 快速進行性 GN (RPGN), AIN 疑似但未改善",
                "next": [],
            },
            {
                "id": "E",
                "label": "Post-renal 評估",
                "detail": "腎臟超音波檢查水腎 (hydronephrosis), Foley catheter 評估膀胱出口阻塞",
                "next": ["E1"],
            },
            {
                "id": "E1",
                "label": "解除阻塞",
                "detail": "Foley catheter, 泌尿科會診, PCN (percutaneous nephrostomy) 若需要",
                "next": [],
            },
        ],
        "mermaid": """graph TD
  A[確認AKI] --> B[初步評估]
  B --> C{Pre-renal}
  B --> D{Intrinsic renal}
  B --> E{Post-renal}
  C --> C1[體液復甦]
  C1 --> C2[48h追蹤Cr]
  D --> D1[ATN]
  D --> D2[AIN]
  D --> D3[GN]
  D1 --> D4[考慮腎臟切片]
  D2 --> D4
  D3 --> D4
  E --> E1[解除阻塞]""",
        "references": [
            "KDIGO AKI Guideline 2012 (updated 2024)",
            "UpToDate: Diagnostic approach to adult patients with subacute kidney injury",
        ],
    },
    "hyperkalemia": {
        "title": "Hyperkalemia Management",
        "title_zh": "高血鉀處置流程",
        "version": "AHA/ACC 2024",
        "steps": [
            {
                "id": "A",
                "label": "確認高血鉀",
                "detail": "排除溶血假性高血鉀, 重覆抽血確認, 同時做 12-lead ECG",
                "next": ["B"],
            },
            {
                "id": "B",
                "label": "檢查 ECG 變化",
                "detail": "Peaked T waves, QRS widening, PR prolongation, sine wave pattern",
                "next": ["C", "D", "E"],
            },
            {
                "id": "C",
                "label": "K > 6.5 或 ECG 異常",
                "detail": "緊急處置 (Emergent)",
                "next": ["C1", "C2", "C3", "C4"],
            },
            {
                "id": "C1",
                "label": "Calcium gluconate",
                "detail": "10% CaGluconate 10 mL IV over 2-3 min, 可重複, 膜穩定劑",
                "next": [],
            },
            {
                "id": "C2",
                "label": "Insulin + Glucose",
                "detail": "Regular insulin 10U IV + D50W 50mL, 監測血糖 1-2h, onset 15-30 min",
                "next": [],
            },
            {
                "id": "C3",
                "label": "Sodium bicarbonate",
                "detail": "若合併代謝性酸中毒 (pH <7.2), NaHCO3 50-100 mEq IV",
                "next": [],
            },
            {
                "id": "C4",
                "label": "緊急透析",
                "detail": "若藥物治療無效或 K 持續上升, 緊急 hemodialysis",
                "next": [],
            },
            {
                "id": "D",
                "label": "K 5.5-6.5 無 ECG 變化",
                "detail": "積極處置 (Urgent)",
                "next": ["D1", "D2"],
            },
            {
                "id": "D1",
                "label": "Insulin + Glucose",
                "detail": "同緊急處置劑量",
                "next": [],
            },
            {
                "id": "D2",
                "label": "K binder",
                "detail": "SPS (Kayexalate) 15-30g PO 或 Patiromer 8.4g PO 或 SZC 10g PO",
                "next": [],
            },
            {
                "id": "E",
                "label": "K 5.0-5.5",
                "detail": "非緊急處置 (Non-urgent)",
                "next": ["E1", "E2", "E3"],
            },
            {
                "id": "E1",
                "label": "飲食衛教",
                "detail": "限制高鉀食物：香蕉、柳橙、番茄、馬鈴薯、堅果",
                "next": [],
            },
            {
                "id": "E2",
                "label": "審視用藥",
                "detail": "ACEi/ARB, spironolactone, K-sparing diuretics, TMP/SMX",
                "next": [],
            },
            {
                "id": "E3",
                "label": "考慮 K binder 長期使用",
                "detail": "Patiromer 或 SZC 若需長期使用 RAASi",
                "next": [],
            },
        ],
        "mermaid": """graph TD
  A[確認高血鉀] --> B[檢查ECG]
  B --> C{K > 6.5 或 ECG異常}
  B --> D{K 5.5-6.5}
  B --> E{K 5.0-5.5}
  C --> C1[Calcium gluconate IV]
  C --> C2[Insulin + Glucose]
  C --> C3[NaHCO3]
  C --> C4[緊急透析]
  D --> D1[Insulin + Glucose]
  D --> D2[K binder]
  E --> E1[飲食衛教]
  E --> E2[審視用藥]
  E --> E3[長期K binder]""",
        "references": [
            "AHA/ACC 2024 Hyperkalemia Management",
            "KDIGO CKD Guideline: Potassium Management",
            "UpToDate: Treatment and prevention of hyperkalemia in adults",
        ],
    },
    "hyponatremia": {
        "title": "Hyponatremia Workup",
        "title_zh": "低血鈉鑑別診斷流程",
        "version": "European Clinical Practice Guideline 2024",
        "steps": [
            {
                "id": "A",
                "label": "確認低血鈉",
                "detail": "Serum Na <135 mEq/L, 確認非抽血誤差",
                "next": ["B"],
            },
            {
                "id": "B",
                "label": "檢查 Serum Osmolality",
                "detail": "區分 hypo-osmolar, iso-osmolar, hyper-osmolar",
                "next": ["C", "D", "E"],
            },
            {
                "id": "C",
                "label": "Serum Osm > 295",
                "detail": "Hypertonic hyponatremia: 高血糖 (每 glucose 上升 100, Na 下降 1.6-2.4), mannitol",
                "next": ["C1"],
            },
            {
                "id": "C1",
                "label": "矯正 glucose",
                "detail": "計算 corrected Na, 治療根本原因 (DKA, HHS)",
                "next": [],
            },
            {
                "id": "D",
                "label": "Serum Osm 280-295",
                "detail": "Isotonic hyponatremia (pseudohyponatremia): 高脂血症, 高蛋白血症",
                "next": ["D1"],
            },
            {
                "id": "D1",
                "label": "排除假性低血鈉",
                "detail": "使用 direct ISE 測量 Na, 檢查 TG 和 protein",
                "next": [],
            },
            {
                "id": "E",
                "label": "Serum Osm < 280",
                "detail": "True hypotonic hyponatremia, 進一步評估 volume status",
                "next": ["F"],
            },
            {
                "id": "F",
                "label": "評估 Urine Osmolality",
                "detail": "Urine Osm <100: 多飲水 (primary polydipsia), beer potomania",
                "next": ["G"],
            },
            {
                "id": "G",
                "label": "Urine Osm >= 100",
                "detail": "進一步評估體液狀態和 Urine Na",
                "next": ["H", "I", "J"],
            },
            {
                "id": "H",
                "label": "Hypovolemic",
                "detail": "Urine Na <20: 腸胃道流失, 皮膚流失; Urine Na >20: 利尿劑, 腎上腺不足, cerebral salt wasting",
                "next": ["H1"],
            },
            {
                "id": "H1",
                "label": "Normal saline 補充",
                "detail": "0.9% NaCl IV, 治療根本原因, 停利尿劑",
                "next": [],
            },
            {
                "id": "I",
                "label": "Euvolemic",
                "detail": "最常見：SIADH. 其他：hypothyroidism, adrenal insufficiency",
                "next": ["I1"],
            },
            {
                "id": "I1",
                "label": "SIADH 處置",
                "detail": "限水 (1-1.5 L/day), salt tablets, 考慮 tolvaptan (限住院使用)",
                "next": [],
            },
            {
                "id": "J",
                "label": "Hypervolemic",
                "detail": "CHF, cirrhosis, nephrotic syndrome. Urine Na 通常 <20",
                "next": ["J1"],
            },
            {
                "id": "J1",
                "label": "限水 + 利尿劑",
                "detail": "限水, loop diuretics, 治療根本疾病, 考慮 tolvaptan (限 CHF/cirrhosis)",
                "next": [],
            },
        ],
        "mermaid": """graph TD
  A[確認低血鈉 Na<135] --> B{Serum Osmolality}
  B -->|>295| C[Hypertonic]
  B -->|280-295| D[Isotonic]
  B -->|<280| E[Hypotonic]
  C --> C1[矯正glucose]
  D --> D1[排除假性低血鈉]
  E --> F{Urine Osm}
  F -->|<100| F1[多飲水]
  F -->|>=100| G[評估體液狀態]
  G --> H[Hypovolemic]
  G --> I[Euvolemic]
  G --> J[Hypervolemic]
  H --> H1[NS補充]
  I --> I1[SIADH處置]
  J --> J1[限水加利尿劑]""",
        "references": [
            "European Clinical Practice Guideline on Hyponatraemia 2014 (updated 2024)",
            "AJKD: Diagnosis and Treatment of Hyponatremia",
            "UpToDate: Diagnostic evaluation and treatment of hyponatremia in adults",
        ],
    },
    "ckd_progression": {
        "title": "CKD Progression Management",
        "title_zh": "CKD 延緩惡化策略",
        "version": "KDIGO 2024",
        "steps": [
            {
                "id": "A",
                "label": "確認 CKD 分期",
                "detail": "eGFR 和 UACR 確認 CKD 分期和風險分級 (KDIGO heat map)",
                "next": ["B"],
            },
            {
                "id": "B",
                "label": "基礎治療",
                "detail": "所有 CKD 患者：血壓控制 <130/80, 減鹽 (<2g Na/day), 戒菸, 運動",
                "next": ["C"],
            },
            {
                "id": "C",
                "label": "評估蛋白尿",
                "detail": "UACR >=30 mg/g 或 UPCR >=150 mg/g",
                "next": ["D", "E"],
            },
            {
                "id": "D",
                "label": "有蛋白尿",
                "detail": "ACEi 或 ARB 最大耐受劑量, 目標 UACR 下降 >=30%",
                "next": ["F"],
            },
            {
                "id": "E",
                "label": "無顯著蛋白尿",
                "detail": "ACEi/ARB 非必須, 血壓控制為主",
                "next": ["G"],
            },
            {
                "id": "F",
                "label": "加上 SGLT2 抑制劑",
                "detail": "Dapagliflozin 10mg 或 Empagliflozin 10mg (eGFR >=20 可啟用), 不論是否有糖尿病",
                "next": ["H"],
            },
            {
                "id": "G",
                "label": "考慮 SGLT2i",
                "detail": "即使無蛋白尿, eGFR 20-45 仍可考慮 SGLT2i (EMPA-KIDNEY trial)",
                "next": ["I"],
            },
            {
                "id": "H",
                "label": "評估 Finerenone",
                "detail": "若為 T2DM + CKD + UACR >=30, 加上 Finerenone 10-20mg (FIDELIO/FIGARO trials), 監測 K",
                "next": ["I"],
            },
            {
                "id": "I",
                "label": "額外措施",
                "detail": "代謝性酸中毒矯正 (NaHCO3 目標 bicarb >=22), 避免腎毒素, 管理 CKD-MBD",
                "next": ["J"],
            },
            {
                "id": "J",
                "label": "定期追蹤",
                "detail": "高風險 (G4-5 或 A3): 每 1-3 月; 中風險: 每 3-6 月; 低風險: 每 6-12 月",
                "next": [],
            },
        ],
        "mermaid": """graph TD
  A[確認CKD分期] --> B[基礎治療]
  B --> C{評估蛋白尿}
  C -->|UACR>=30| D[ACEi或ARB]
  C -->|UACR<30| E[血壓控制為主]
  D --> F[加SGLT2i]
  E --> G[考慮SGLT2i]
  F --> H{T2DM加CKD}
  H -->|是| H1[加Finerenone]
  H -->|否| I[額外措施]
  H1 --> I
  G --> I
  I --> J[定期追蹤]""",
        "references": [
            "KDIGO 2024 CKD Guideline",
            "DAPA-CKD Trial (NEJM 2020)",
            "EMPA-KIDNEY Trial (NEJM 2023)",
            "FIDELIO-DKD / FIGARO-DKD Trials",
        ],
    },
    "proteinuria_workup": {
        "title": "Proteinuria Workup",
        "title_zh": "蛋白尿評估流程",
        "version": "KDIGO 2024 / ACR 2023",
        "steps": [
            {
                "id": "A",
                "label": "發現蛋白尿",
                "detail": "Dipstick positive 或 UACR >=30 mg/g 或 UPCR >=150 mg/g",
                "next": ["B"],
            },
            {
                "id": "B",
                "label": "排除暫時性蛋白尿",
                "detail": "發燒, 劇烈運動, UTI, CHF 急性期. 重複檢查 2 次以上確認持續性",
                "next": ["C"],
            },
            {
                "id": "C",
                "label": "定量蛋白尿",
                "detail": "UACR (首選) 或 UPCR 或 24hr urine protein",
                "next": ["D"],
            },
            {
                "id": "D",
                "label": "蛋白尿分級",
                "detail": "A1 (<30 mg/g), A2 (30-300 mg/g), A3 (>300 mg/g), Nephrotic range (>3.5g/day)",
                "next": ["E", "F"],
            },
            {
                "id": "E",
                "label": "A2 微量白蛋白尿",
                "detail": "評估 DM, HTN, 早期 GN",
                "next": ["E1"],
            },
            {
                "id": "E1",
                "label": "ACEi/ARB + SGLT2i",
                "detail": "啟動腎臟保護治療, 每 3-6 月追蹤 UACR",
                "next": [],
            },
            {
                "id": "F",
                "label": "A3 或 Nephrotic range",
                "detail": "全面檢查：SPEP/UPEP, complement C3/C4, ANA, ANCA, anti-GBM, anti-PLA2R, HBV/HCV/HIV",
                "next": ["G"],
            },
            {
                "id": "G",
                "label": "評估腎臟切片適應症",
                "detail": "Nephrotic syndrome, 不明原因蛋白尿持續惡化, 合併血尿/腎功能惡化",
                "next": ["G1", "G2"],
            },
            {
                "id": "G1",
                "label": "執行腎臟切片",
                "detail": "Light microscopy, IF, EM. 排除出血風險 (INR, platelet, BP control)",
                "next": ["G3"],
            },
            {
                "id": "G2",
                "label": "暫緩切片",
                "detail": "明確 DKD (糖尿病 >10y + retinopathy + 漸進蛋白尿) 可先試治療",
                "next": [],
            },
            {
                "id": "G3",
                "label": "根據病理結果治療",
                "detail": "MN, IgAN, FSGS, MCD, lupus nephritis 等各有專屬治療",
                "next": [],
            },
        ],
        "mermaid": """graph TD
  A[發現蛋白尿] --> B[排除暫時性原因]
  B --> C[定量蛋白尿]
  C --> D{蛋白尿分級}
  D -->|A2 30-300| E[微量白蛋白尿]
  D -->|A3 >300| F[大量蛋白尿]
  E --> E1[ACEi或ARB加SGLT2i]
  F --> G{評估腎臟切片適應症}
  G -->|符合| G1[執行腎臟切片]
  G -->|暫緩| G2[先試治療]
  G1 --> G3[根據病理結果治療]""",
        "references": [
            "KDIGO 2024 Glomerular Diseases Guideline",
            "KDIGO 2024 CKD Guideline",
            "UpToDate: Evaluation of proteinuria in adults",
        ],
    },
    "dialysis_initiation": {
        "title": "Dialysis Initiation Decision",
        "title_zh": "透析起始時機評估",
        "version": "KDIGO 2024 / Taiwan NHI 2024",
        "steps": [
            {
                "id": "A",
                "label": "CKD Stage 5",
                "detail": "eGFR <15 mL/min/1.73m2, 開始透析準備評估",
                "next": ["B"],
            },
            {
                "id": "B",
                "label": "評估緊急透析指征",
                "detail": "致命性高血鉀, 嚴重肺水腫, 尿毒性腦病變, 尿毒性心包膜炎, 嚴重代謝性酸中毒",
                "next": ["C", "D"],
            },
            {
                "id": "C",
                "label": "有緊急指征",
                "detail": "立即啟動透析 (通常 emergent HD via temporary catheter)",
                "next": ["C1"],
            },
            {
                "id": "C1",
                "label": "緊急血管通路",
                "detail": "Non-tunneled dialysis catheter (IJV preferred), 同時安排永久通路",
                "next": [],
            },
            {
                "id": "D",
                "label": "無緊急指征",
                "detail": "評估尿毒症狀和營養狀態",
                "next": ["E"],
            },
            {
                "id": "E",
                "label": "評估尿毒症狀",
                "detail": "噁心嘔吐, 食慾不振, 疲倦, 注意力不集中, 搔癢, restless legs",
                "next": ["F", "G"],
            },
            {
                "id": "F",
                "label": "有症狀或營養惡化",
                "detail": "計劃性啟動透析, 選擇透析模式",
                "next": ["H"],
            },
            {
                "id": "G",
                "label": "無症狀",
                "detail": "密切追蹤 (每 1-2 月), 透析衛教, 準備血管通路/PD catheter",
                "next": ["G1"],
            },
            {
                "id": "G1",
                "label": "提前建立通路",
                "detail": "AVF: 提前 6 個月; AVG: 提前 3-6 週; PD catheter: 提前 2-4 週",
                "next": [],
            },
            {
                "id": "H",
                "label": "選擇透析模式",
                "detail": "病人偏好, 生活型態, 合併症, 家庭支持, 殘餘腎功能",
                "next": ["H1", "H2", "H3"],
            },
            {
                "id": "H1",
                "label": "血液透析 (HD)",
                "detail": "In-center HD 3x/week 或 Home HD. 需 AVF/AVG/catheter",
                "next": [],
            },
            {
                "id": "H2",
                "label": "腹膜透析 (PD)",
                "detail": "CAPD 或 APD. 優勢：保留殘餘腎功能, 生活彈性, 居家執行",
                "next": [],
            },
            {
                "id": "H3",
                "label": "保守治療",
                "detail": "高齡或多重合併症患者可考慮, 著重症狀控制和生活品質",
                "next": [],
            },
        ],
        "mermaid": """graph TD
  A[CKD Stage 5] --> B{緊急透析指征}
  B -->|有| C[立即透析]
  B -->|無| D[評估症狀]
  C --> C1[緊急血管通路]
  D --> E{尿毒症狀}
  E -->|有症狀| F[計劃啟動透析]
  E -->|無症狀| G[密切追蹤]
  G --> G1[提前建立通路]
  F --> H{選擇透析模式}
  H --> H1[血液透析HD]
  H --> H2[腹膜透析PD]
  H --> H3[保守治療]""",
        "references": [
            "KDIGO 2024: Timing of Dialysis Initiation",
            "Taiwan NHI Dialysis Guidelines 2024",
            "IDEAL Study (NEJM 2010): Early vs Late Initiation",
            "UpToDate: Indications for initiation of dialysis in CKD",
        ],
    },
}


def get_pathway_list():
    """取得所有 pathway 的摘要清單"""
    return [
        {
            "id": pid,
            "title": p["title"],
            "title_zh": p["title_zh"],
            "version": p["version"],
            "steps_count": len(p["steps"]),
        }
        for pid, p in PATHWAYS.items()
    ]


def get_pathway_detail(pathway_id):
    """取得特定 pathway 的完整內容"""
    pathway = PATHWAYS.get(pathway_id)
    if not pathway:
        return None
    return {
        "id": pathway_id,
        **pathway,
    }


def get_step_by_id(pathway_id, step_id):
    """取得 pathway 中特定步驟的詳細資訊"""
    pathway = PATHWAYS.get(pathway_id)
    if not pathway:
        return None
    for step in pathway["steps"]:
        if step["id"] == step_id:
            return step
    return None
