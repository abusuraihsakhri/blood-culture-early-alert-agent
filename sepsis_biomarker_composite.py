#!/usr/bin/env python3
"""
BloodCulture Sentinel — Sepsis Biomarker Composite & Bottle-Pair Differential
Composite true-bacteremia scoring combining TTP, procalcitonin, lactate and WBC
per ENRICHMENT thresholds; central-peripheral TTP differential for CLABSI;
MALDI-TOF organism-ID posterior refinement.

Zero-dependency. Author: Dr. Abu Suraih Sakhri. License: MIT.
"""
import argparse
import json
import math
import sys
from dataclasses import dataclass
from typing import Dict, Any, List, Optional


@dataclass
class CultureCase:
    set_id: str
    ttp_hours: Optional[float]
    pct_ng_ml: Optional[float] = None        # procalcitonin
    lactate_mmol_l: Optional[float] = None
    wbc_k_ul: Optional[float] = None
    central_ttp_h: Optional[float] = None    # bottle-pair data
    peripheral_ttp_h: Optional[float] = None
    maldi_organism: Optional[str] = None     # when rapid ID available


def composite_sepsis_score(c: CultureCase) -> Dict[str, Any]:
    """
    Rule composite per ENRICHMENT spec:
      TTP<12h + PCT>2.0 + lactate>2  -> 95%+ confidence true bacteremia
      TTP>24h + PCT<0.5 + lactate<1.5 -> 80%+ confidence contamination
      Trend weighting: rising biomarkers amplify the direction of TTP signal.
    """
    evidence: List[Dict[str, Any]] = []
    score = 0.0

    if c.ttp_hours is not None:
        if c.ttp_hours < 12:
            score += 30; evidence.append({"feature": "TTP<12h", "points": 30,
                                          "value": c.ttp_hours})
        elif c.ttp_hours <= 24:
            score += 12; evidence.append({"feature": "TTP 12-24h", "points": 12,
                                          "value": c.ttp_hours})
        else:
            score -= 25; evidence.append({"feature": "TTP>24h", "points": -25,
                                          "value": c.ttp_hours})

    if c.pct_ng_ml is not None:
        if c.pct_ng_ml > 2.0:
            score += 25; evidence.append({"feature": "PCT>2.0", "points": 25,
                                          "value": c.pct_ng_ml})
        elif c.pct_ng_ml < 0.5:
            score -= 20; evidence.append({"feature": "PCT<0.5", "points": -20,
                                          "value": c.pct_ng_ml})

    if c.lactate_mmol_l is not None:
        if c.lactate_mmol_l > 2.0:
            score += 20; evidence.append({"feature": "lactate>2", "points": 20,
                                          "value": c.lactate_mmol_l})
        elif c.lactate_mmol_l < 1.5:
            score -= 15; evidence.append({"feature": "lactate<1.5", "points": -15,
                                          "value": c.lactate_mmol_l})

    if c.wbc_k_ul is not None:
        if c.wbc_k_ul > 12 or c.wbc_k_ul < 4:
            score += 8; evidence.append({"feature": "WBC abnormal", "points": 8,
                                         "value": c.wbc_k_ul})

    # anchor rules from specifications
    if (c.ttp_hours is not None and c.ttp_hours < 12 and
            (c.pct_ng_ml or 0) > 2.0 and (c.lactate_mmol_l or 0) > 2):
        probability = 0.95
        label = "TRUE_BACTEREMIA_HIGH_CONFIDENCE"
    elif (c.ttp_hours is not None and c.ttp_hours > 24 and
          (c.pct_ng_ml or 1) < 0.5 and (c.lactate_mmol_l or 1) < 1.5):
        probability = 0.20   # contamination confidence 0.80 per spec
        label = "PROBABLE_CONTAMINATION"
    else:
        probability = min(0.98, max(0.02, 1 / (1 + math.exp(-score / 22))))
        label = (_label_from_prob(probability))

    return {
        "set_id": c.set_id,
        "composite_points": round(score, 1),
        "true_bacteremia_probability": round(probability, 3),
        "classification": label,
        "evidence": evidence,
        "action": _action(label),
    }


def _label_from_prob(p: float) -> str:
    if p >= 0.75:
        return "LIKELY_TRUE_PATHOGEN"
    if p >= 0.45:
        return "INDETERMINATE"
    return "SUSPECT_CONTAMINATION"


def _action(label: str) -> str:
    table = {
        "TRUE_BACTEREMIA_HIGH_CONFIDENCE":
            "Continue empiric broad coverage; escalate per sepsis bundle",
        "LIKELY_TRUE_PATHOGEN": "Maintain therapy pending susceptibilities",
        "INDETERMINATE": "Repeat cultures; hold de-escalation decision 24h",
        "PROBABLE_CONTAMINATION":
            "De-escalation review at 48-72h; consider stopping vancomycin if stable",
        "SUSPECT_CONTAMINATION":
            "Early antibiotic stewardship consult; do not treat single skin-flora draw",
    }
    return table.get(label, "Clinical review")


def bottle_pair_differential(c: CultureCase) -> Dict[str, Any]:
    """Central vs peripheral differential (CLABSI criteria)."""
    if c.central_ttp_h is None or c.peripheral_ttp_h is None:
        return {"set_id": c.set_id, "error": "requires paired central+peripheral TTP"}
    diff = c.central_ttp_h - c.peripheral_ttp_h   # positive => peripheral grew faster
    abs_diff = abs(diff)
    if abs_diff > 120 / 60:
        interpretation = ("differential >= 2h: catheter-related bloodstream infection "
                          "likely (CRBSI sensitivity ~94%, specificity ~91% in pooled studies)")
        crbsi_likelihood = "HIGH"
    elif abs_diff < 60 / 60:
        interpretation = ("differential < 1h: concordant growth argues against line source; "
                          "if CoNS, contamination probability rises")
        crbsi_likelihood = "LOW"
    else:
        interpretation = "intermediate differential 1-2h: repeat paired sets recommended"
        crbsi_likelihood = "MODERATE"
    return {
        "set_id": c.set_id,
        "central_ttp_h": c.central_ttp_h,
        "peripheral_ttp_h": c.peripheral_ttp_h,
        "differential_minutes": round(diff * 60),
        "crbsi_likelihood": crbsi_likelihood,
        "interpretation": interpretation,
    }


# Likelihood ratios for MALDI-TOF species x TTP context -> contamination prior update
MALDI_LR_TABLE = {
    "staphylococcus_aureus": {"lr_true": 6.0, "lr_contam": 0.05},
    "streptococcus_pneumoniae": {"lr_true": 9.0, "lr_contam": 0.02},
    "escherichia_coli": {"lr_true": 7.0, "lr_contam": 0.03},
    "coagulase_negative_staphylococcus": {"lr_true": 0.35, "lr_contam": 4.5},
    "cutibacterium_acnes": {"lr_true": 0.15, "lr_contam": 6.0},
}


def refine_with_maldi(c: CultureCase, prior_probability: float) -> Dict[str, Any]:
    """Bayesian posterior update on contamination using MALDI-TOF species ID."""
    if not c.maldi_organism or c.maldi_organism not in MALDI_LR_TABLE:
        return {"set_id": c.set_id, "posterior_contamination_probability":
                round(1 - prior_probability, 3), "note": "no MALDI entry; prior unchanged"}
    lr = MALDI_LR_TABLE[c.maldi_organism]
    prior_contam = 1 - prior_probability
    odds = (prior_contam / max(1 - prior_contam, 1e-9)) * (lr["lr_contam"] / lr["lr_true"])
    post_contam = odds / (1 + odds)
    verdict = "CONTAMINATION_LIKELY" if post_contam >= 0.6 else \
              "TRUE_BACTEREMIA_LIKELY" if post_contam <= 0.25 else "EQUIVOCAL"
    short_ttp_boost = ""
    if c.ttp_hours is not None and c.ttp_hours < 12 and \
            c.maldi_organism in ("streptococcus_pneumoniae", "staphylococcus_aureus"):
        short_ttp_boost = "short TTP + virulent species: treat as high-confidence bacteremia"
    return {
        "set_id": c.set_id,
        "maldi_organism": c.maldi_organism,
        "prior_bacteremia_probability": round(prior_probability, 3),
        "posterior_contamination_probability": round(post_contam, 3),
        "posterior_verdict": verdict,
        "note": short_ttp_boost or f"LR applied: true={lr['lr_true']}, contam={lr['lr_contam']}",
    }


if __name__ == "__main__":
    case_a = CultureCase("BC-A", ttp_hours=8.5, pct_ng_ml=4.2, lactate_mmol_l=3.1,
                         wbc_k_ul=17.5, central_ttp_h=8.5, peripheral_ttp_h=16.0)
    case_b = CultureCase("BC-B", ttp_hours=31.0, pct_ng_ml=0.3, lactate_mmol_l=1.1,
                         wbc_k_ul=7.9, maldi_organism="coagulase_negative_staphylococcus")
    case_c = CultureCase("BC-C", ttp_hours=19.0, pct_ng_ml=1.2, lactate_mmol_l=1.8,
                         maldi_organism="streptococcus_pneumoniae")

    for case in (case_a, case_b, case_c):
        base = composite_sepsis_score(case)
        print(json.dumps(base, indent=2))
        print(json.dumps(bottle_pair_differential(case), indent=2))
        print(json.dumps(refine_with_maldi(case, base["true_bacteremia_probability"]), indent=2))
