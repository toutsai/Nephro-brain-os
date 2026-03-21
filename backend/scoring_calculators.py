"""
Nephro Brain OS — 臨床評分系統計算器
提供腎臟科常用的臨床評分與計算工具
所有計算回傳 dict: {value, unit, interpretation, reference, normal_range}
"""
import math


def calculate_egfr_ckd_epi(creatinine, age, sex, **kwargs):
    """CKD-EPI 2021 eGFR（不含種族校正）
    Reference: Inker LA et al. NEJM 2021;385:1737-1749
    """
    cr = float(creatinine)
    age = float(age)
    sex = str(sex).lower()

    if sex in ('female', 'f', '女'):
        if cr <= 0.7:
            egfr = 142 * (cr / 0.7) ** (-0.241) * (0.9938 ** age) * 1.012
        else:
            egfr = 142 * (cr / 0.7) ** (-1.200) * (0.9938 ** age) * 1.012
    else:
        if cr <= 0.9:
            egfr = 142 * (cr / 0.9) ** (-0.302) * (0.9938 ** age)
        else:
            egfr = 142 * (cr / 0.9) ** (-1.200) * (0.9938 ** age)

    egfr = round(egfr, 1)
    stage = _get_ckd_stage(egfr)

    return {
        "value": egfr,
        "unit": "mL/min/1.73m²",
        "interpretation": f"eGFR {egfr} → {stage}",
        "reference": "CKD-EPI 2021 (Inker et al. NEJM 2021)",
        "normal_range": ">90 mL/min/1.73m²",
    }


def _get_ckd_stage(egfr):
    if egfr >= 90:
        return "CKD Stage 1（腎功能正常）"
    elif egfr >= 60:
        return "CKD Stage 2（輕度下降）"
    elif egfr >= 45:
        return "CKD Stage 3a（輕至中度下降）"
    elif egfr >= 30:
        return "CKD Stage 3b（中至重度下降）"
    elif egfr >= 15:
        return "CKD Stage 4（重度下降）"
    else:
        return "CKD Stage 5（腎衰竭）"


def classify_ckd_stage(egfr, **kwargs):
    """根據 eGFR 分類 CKD stage"""
    egfr = float(egfr)
    stage = _get_ckd_stage(egfr)
    return {
        "value": stage,
        "unit": "",
        "interpretation": stage,
        "reference": "KDIGO 2024 CKD Guidelines",
        "normal_range": "eGFR >90",
    }


def classify_aki_kdigo(baseline_cr, current_cr, urine_output_ml_kg_h=None, hours=None, **kwargs):
    """KDIGO AKI Staging
    Stage 1: Cr 上升 >=0.3 mg/dL (48h) 或 1.5-1.9x baseline
    Stage 2: Cr 2.0-2.9x baseline
    Stage 3: Cr >=3.0x baseline 或 Cr >=4.0 或需要 RRT
    """
    base = float(baseline_cr)
    curr = float(current_cr)
    ratio = curr / base if base > 0 else 0
    diff = curr - base

    stage = 0
    reason = ""

    if ratio >= 3.0 or curr >= 4.0:
        stage = 3
        reason = f"Cr {curr:.1f} / baseline {base:.1f} = {ratio:.1f}x（>=3.0x）"
    elif ratio >= 2.0:
        stage = 2
        reason = f"Cr {curr:.1f} / baseline {base:.1f} = {ratio:.1f}x（2.0-2.9x）"
    elif ratio >= 1.5 or diff >= 0.3:
        stage = 1
        reason = f"Cr 上升 {diff:.1f} mg/dL（>=0.3）或 {ratio:.1f}x baseline"

    if urine_output_ml_kg_h is not None and hours is not None:
        uo = float(urine_output_ml_kg_h)
        h = float(hours)
        if uo < 0.3 and h >= 24:
            stage = max(stage, 3)
        elif uo < 0.5 and h >= 12:
            stage = max(stage, 2)
        elif uo < 0.5 and h >= 6:
            stage = max(stage, 1)

    if stage == 0:
        interp = "未達 AKI 診斷標準"
    else:
        interp = f"KDIGO AKI Stage {stage}：{reason}"

    return {
        "value": stage,
        "unit": "KDIGO Stage",
        "interpretation": interp,
        "reference": "KDIGO AKI Guidelines 2012",
        "normal_range": "Stage 0（無 AKI）",
    }


def calculate_fena(urine_na, plasma_na, urine_cr, plasma_cr, **kwargs):
    """FENa = (UNa × PCr) / (PNa × UCr) × 100
    <1%: Pre-renal, >2%: Intrinsic renal (ATN)
    """
    una = float(urine_na)
    pna = float(plasma_na)
    ucr = float(urine_cr)
    pcr = float(plasma_cr)

    fena = (una * pcr) / (pna * ucr) * 100
    fena = round(fena, 2)

    if fena < 1:
        interp = f"FENa {fena}% → 提示 Pre-renal azotemia（腎前性）"
    elif fena <= 2:
        interp = f"FENa {fena}% → 灰色地帶，需結合臨床判斷"
    else:
        interp = f"FENa {fena}% → 提示 Intrinsic renal disease（ATN 等）"

    return {
        "value": fena,
        "unit": "%",
        "interpretation": interp,
        "reference": "Espinel CH. JAMA 1976",
        "normal_range": "<1% (pre-renal), >2% (intrinsic)",
    }


def calculate_feurea(urine_urea, plasma_urea, urine_cr, plasma_cr, **kwargs):
    """FEUrea = (UUrea × PCr) / (PUrea × UCr) × 100
    <35%: Pre-renal（即使使用利尿劑）, >50%: Intrinsic
    """
    feu = (float(urine_urea) * float(plasma_cr)) / (float(plasma_urea) * float(urine_cr)) * 100
    feu = round(feu, 2)

    if feu < 35:
        interp = f"FEUrea {feu}% → 提示 Pre-renal（利尿劑使用時仍可靠）"
    else:
        interp = f"FEUrea {feu}% → 提示 Intrinsic renal disease"

    return {
        "value": feu, "unit": "%",
        "interpretation": interp,
        "reference": "Carvounis CP et al. Kidney Int 2002",
        "normal_range": "<35% (pre-renal), >50% (intrinsic)",
    }


def calculate_transtubular_k_gradient(urine_k, plasma_k, urine_osm, plasma_osm, **kwargs):
    """TTKG = (UK / PK) / (UOsm / POsm)
    TTKG >7: 腎臟排鉀增加, TTKG <3: 腎臟排鉀減少
    注意：UOsm 需 > POsm 才可使用此公式
    """
    uk = float(urine_k)
    pk = float(plasma_k)
    uosm = float(urine_osm)
    posm = float(plasma_osm)

    if uosm < posm:
        return {
            "value": None, "unit": "",
            "interpretation": "⚠️ UOsm < POsm，TTKG 不適用（尿液需為濃縮狀態）",
            "reference": "Ethier JH et al. Am J Nephrol 1990",
            "normal_range": "",
        }

    ttkg = (uk / pk) / (uosm / posm)
    ttkg = round(ttkg, 1)

    if ttkg > 7:
        interp = f"TTKG {ttkg} → 腎臟排鉀增加（醛固酮效應正常/過高）"
    elif ttkg < 3:
        interp = f"TTKG {ttkg} → 腎臟排鉀減少（醛固酮效應不足）"
    else:
        interp = f"TTKG {ttkg} → 中間值，需結合臨床判斷"

    return {
        "value": ttkg, "unit": "",
        "interpretation": interp,
        "reference": "Ethier JH et al. Am J Nephrol 1990",
        "normal_range": "高血鉀時 >7 為正常反應, <3 提示腎臟排鉀障礙",
    }


def calculate_urine_anion_gap(urine_na, urine_k, urine_cl, **kwargs):
    """UAG = UNa + UK - UCl
    正值 → 遠端腎小管酸中毒 (distal RTA)
    負值 → 腸道 HCO3 流失（腹瀉）或 proximal RTA
    """
    uag = float(urine_na) + float(urine_k) - float(urine_cl)
    uag = round(uag, 1)

    if uag > 0:
        interp = f"UAG {uag} mEq/L（正值）→ 提示遠端 RTA (Type 1) 或 Type 4 RTA"
    else:
        interp = f"UAG {uag} mEq/L（負值）→ 腎臟排 NH4+ 正常，提示腸道 HCO3 流失"

    return {
        "value": uag, "unit": "mEq/L",
        "interpretation": interp,
        "reference": "Battle DC et al. NEJM 1988",
        "normal_range": "負值（正常非 gap 代酸時）",
    }


def calculate_serum_anion_gap(na, cl, hco3, albumin=4.0, **kwargs):
    """AG = Na - Cl - HCO3（白蛋白校正：每下降 1 g/dL，AG 下降 2.5）"""
    ag = float(na) - float(cl) - float(hco3)
    ag = round(ag, 1)
    alb = float(albumin) if albumin else 4.0
    corrected_ag = round(ag + 2.5 * (4.0 - alb), 1)

    interp = f"AG {ag} mEq/L"
    if alb < 4.0:
        interp += f"，校正後 AG {corrected_ag}（Albumin {alb}）"
    if corrected_ag > 12:
        interp += " → 高 AG 代謝性酸中毒（MUDPILES: Methanol, Uremia, DKA, Propylene glycol, INH/Iron, Lactic acidosis, Ethylene glycol, Salicylates）"
    else:
        interp += " → 正常 AG"

    return {
        "value": ag, "unit": "mEq/L",
        "interpretation": interp,
        "reference": "Emmet M. UpToDate 2024",
        "normal_range": "8-12 mEq/L",
        "corrected_ag": corrected_ag,
    }


def calculate_corrected_calcium(total_ca, albumin, **kwargs):
    """校正鈣 = Total Ca + 0.8 × (4.0 - Albumin)"""
    ca = float(total_ca)
    alb = float(albumin)
    corrected = round(ca + 0.8 * (4.0 - alb), 1)

    if corrected > 10.5:
        interp = f"校正鈣 {corrected} mg/dL → 高血鈣"
    elif corrected < 8.5:
        interp = f"校正鈣 {corrected} mg/dL → 低血鈣"
    else:
        interp = f"校正鈣 {corrected} mg/dL → 正常"

    return {
        "value": corrected, "unit": "mg/dL",
        "interpretation": interp,
        "reference": "Payne RB et al. BMJ 1973",
        "normal_range": "8.5-10.5 mg/dL",
    }


def calculate_calcium_phosphate_product(ca, phos, **kwargs):
    """Ca × P product (mg²/dL²)
    >55: 增加軟組織鈣化風險
    KDIGO 建議避免 >55
    """
    product = round(float(ca) * float(phos), 1)

    if product > 55:
        interp = f"Ca×P {product} → 偏高，軟組織鈣化風險增加"
    else:
        interp = f"Ca×P {product} → 可接受範圍"

    return {
        "value": product, "unit": "mg²/dL²",
        "interpretation": interp,
        "reference": "KDIGO CKD-MBD Guidelines 2017",
        "normal_range": "<55 mg²/dL²",
    }


def calculate_kt_v_daugirdas(pre_bun, post_bun, t_hours, uf_liters, post_weight_kg, **kwargs):
    """Daugirdas 2nd generation Kt/V
    Kt/V = -ln(R - 0.008×t) + (4-3.5×R) × UF/W
    R = post_BUN/pre_BUN, t=透析時間(hr), UF=超濾量(L), W=透析後體重(kg)
    Target: >=1.2 (HD 3x/week)
    """
    pre = float(pre_bun)
    post = float(post_bun)
    t = float(t_hours)
    uf = float(uf_liters)
    w = float(post_weight_kg)

    r = post / pre
    ktv = -math.log(r - 0.008 * t) + (4 - 3.5 * r) * uf / w
    ktv = round(ktv, 2)

    if ktv >= 1.4:
        interp = f"Kt/V {ktv} → 透析充分性良好"
    elif ktv >= 1.2:
        interp = f"Kt/V {ktv} → 達標（KDOQI 最低標準 1.2）"
    else:
        interp = f"Kt/V {ktv} → 未達標（<1.2），建議調整透析處方"

    return {
        "value": ktv, "unit": "",
        "interpretation": interp,
        "reference": "Daugirdas JT. JASN 1993; KDOQI HD Adequacy 2015",
        "normal_range": ">=1.2（目標 >=1.4）",
    }


def calculate_urr(pre_bun, post_bun, **kwargs):
    """URR = (1 - post/pre) × 100%
    Target: >=65% (KDOQI)
    """
    pre = float(pre_bun)
    post = float(post_bun)
    urr = round((1 - post / pre) * 100, 1)

    if urr >= 70:
        interp = f"URR {urr}% → 透析效率良好"
    elif urr >= 65:
        interp = f"URR {urr}% → 達標（KDOQI 最低 65%）"
    else:
        interp = f"URR {urr}% → 未達標（<65%），建議調整透析處方"

    return {
        "value": urr, "unit": "%",
        "interpretation": interp,
        "reference": "KDOQI HD Adequacy Guidelines 2015",
        "normal_range": ">=65%（目標 >=70%）",
    }


def calculate_corrected_sodium(measured_na, glucose_mg_dl, **kwargs):
    """校正鈉 = Measured Na + 1.6 × (Glucose - 100) / 100
    (Hillier modification for glucose >400: use 2.4)
    """
    na = float(measured_na)
    glu = float(glucose_mg_dl)
    factor = 2.4 if glu > 400 else 1.6
    corrected = round(na + factor * (glu - 100) / 100, 1)

    return {
        "value": corrected, "unit": "mEq/L",
        "interpretation": f"校正鈉 {corrected} mEq/L（Glucose {glu} mg/dL, factor={factor}）",
        "reference": "Hillier TA et al. Am J Med 1999",
        "normal_range": "135-145 mEq/L",
    }


def calculate_plasma_osmolality(na, bun_mg_dl, glucose_mg_dl, **kwargs):
    """計算血漿滲透壓 = 2×Na + BUN/2.8 + Glucose/18"""
    osm = 2 * float(na) + float(bun_mg_dl) / 2.8 + float(glucose_mg_dl) / 18
    osm = round(osm, 1)

    return {
        "value": osm, "unit": "mOsm/kg",
        "interpretation": f"計算滲透壓 {osm} mOsm/kg",
        "reference": "Standard formula",
        "normal_range": "275-295 mOsm/kg",
    }


def calculate_osmolal_gap(measured_osm, na, bun_mg_dl, glucose_mg_dl, **kwargs):
    """Osmolal gap = Measured Osm - Calculated Osm
    >10: 考慮 toxic alcohol (methanol, ethylene glycol, isopropanol)
    """
    calc = 2 * float(na) + float(bun_mg_dl) / 2.8 + float(glucose_mg_dl) / 18
    gap = round(float(measured_osm) - calc, 1)

    if gap > 10:
        interp = f"Osmolal gap {gap} → 偏高，考慮 toxic alcohol（methanol, ethylene glycol）"
    else:
        interp = f"Osmolal gap {gap} → 正常範圍"

    return {
        "value": gap, "unit": "mOsm/kg",
        "interpretation": interp,
        "reference": "Kraut JA, Kurtz I. Clin J Am Soc Nephrol 2008",
        "normal_range": "<10 mOsm/kg",
    }


def winter_formula(hco3, **kwargs):
    """Winter's Formula: Expected pCO2 = 1.5 × HCO3 + 8 ± 2
    用於判斷代謝性酸中毒是否合併呼吸性酸鹼異常
    """
    h = float(hco3)
    expected = 1.5 * h + 8
    low = round(expected - 2, 1)
    high = round(expected + 2, 1)
    expected = round(expected, 1)

    return {
        "value": expected, "unit": "mmHg",
        "interpretation": f"預期 pCO2 = {low}-{high} mmHg。若實際 pCO2 高於此範圍 → 合併呼吸性酸中毒；低於 → 合併呼吸性鹼中毒",
        "reference": "Winter's Formula (Albert MS et al. Ann Intern Med 1967)",
        "normal_range": f"{low}-{high} mmHg",
    }


def classify_mest_c(m, e, s, t, c, **kwargs):
    """IgA Nephropathy Oxford/MEST-C Classification
    M: Mesangial hypercellularity (0/1)
    E: Endocapillary hypercellularity (0/1)
    S: Segmental sclerosis (0/1)
    T: Tubular atrophy/interstitial fibrosis (0/1/2)
    C: Crescents (0/1/2)
    """
    m, e, s, t, c = int(m), int(e), int(s), int(t), int(c)
    score = f"M{m}E{e}S{s}T{t}C{c}"

    risk_factors = []
    if m == 1:
        risk_factors.append("M1（系膜增生 >50%，預後較差）")
    if e == 1:
        risk_factors.append("E1（內皮增生，可能對免疫抑制治療有反應）")
    if s == 1:
        risk_factors.append("S1（節段性硬化，不良預後因子）")
    if t >= 1:
        risk_factors.append(f"T{t}（腎小管萎縮/間質纖維化 {'25-50%' if t == 1 else '>50%'}，最強預後因子）")
    if c >= 1:
        risk_factors.append(f"C{c}（新月體 {'<25%' if c == 1 else '>=25%'}，提示活動性病變）")

    if not risk_factors:
        interp = f"{score} — 低風險，所有指標均為 0"
    else:
        interp = f"{score} — 風險因子：" + "；".join(risk_factors)

    return {
        "value": score, "unit": "MEST-C",
        "interpretation": interp,
        "reference": "Oxford Classification (Cattran DC et al. Kidney Int 2009; Haas M et al. Kidney Int 2017)",
        "normal_range": "M0E0S0T0C0（最低風險）",
    }
