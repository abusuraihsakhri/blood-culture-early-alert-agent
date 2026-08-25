#!/usr/bin/env python3
"""
Sepsis Biomarker Correlation Engine for BloodCulture Sentinel.
Correlates blood culture TTP with sepsis biomarkers (PCT, CRP, IL-6, lactate)
to improve contamination probability scoring and guide empiric therapy.
"""

import datetime
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class SepsisBiomarkers:
    """Sepsis biomarker panel."""
    procalcitonin_ng_ml: float = 0.05
    crp_mg_l: float = 5.0
    il6_pg_ml: float = 5.0
    lactate_mmol_l: float = 1.0
    wbc_x10_3: float = 7.5
    neutrophil_pct: float = 60.0
    bandemia_pct: float = 0.0
    platelet_x10_3: float = 250.0
    creatinine_mg_dl: float = 1.0
    bilirubin_mg_dl: float = 0.5


# Biomarker thresholds for sepsis likelihood scoring
BIOMARKER_THRESHOLDS = {
    "procalcitonin": {
        "normal": (0.0, 0.1),
        "localized_infection": (0.1, 0.5),
        "sepsis": (0.5, 2.0),
        "severe_sepsis": (2.0, 10.0),
        "septic_shock": (10.0, float("inf")),
    },
    "crp": {
        "normal": (0, 10),
        "mild_inflammation": (10, 50),
        "moderate_inflammation": (50, 100),
        "severe_inflammation": (100, 200),
        "critical": (200, float("inf")),
    },
    "il6": {
        "normal": (0, 7),
        "elevated": (7, 100),
        "high": (100, 1000),
        "cytokine_storm": (1000, float("inf")),
    },
    "lactate": {
        "normal": (0, 2.0),
        "borderline": (2.0, 4.0),
        "elevated": (4.0, 6.0),
        "high": (6.0, float("inf")),
    },
    "wbc": {
        "leukopenia": (0, 4.0),
        "normal": (4.0, 11.0),
        "leukocytosis": (11.0, 17.0),
        "leukocytosis_extreme": (17.0, float("inf")),
    },
}


def classify_biomarker(value: float, biomarker_name: str) -> str:
    """Classify a biomarker value into severity category."""
    thresholds = BIOMARKER_THRESHOLDS.get(biomarker_name, {})
    for category, (low, high) in thresholds.items():
        if low <= value < high:
            return category
    return "unknown"


def compute_sepsis_score(biomarkers: SepsisBiomarkers) -> Dict[str, Any]:
    """Compute composite sepsis severity score from biomarkers."""
    scores = {}
    total = 0

    pct_class = classify_biomarker(biomarkers.procalcitonin_ng_ml, "procalcitonin")
    pct_scores = {"normal": 0, "localized_infection": 1, "sepsis": 2, "severe_sepsis": 3, "septic_shock": 4}
    scores["pct_score"] = pct_scores.get(pct_class, 0)
    total += scores["pct_score"]

    crp_class = classify_biomarker(biomarkers.crp_mg_l, "crp")
    crp_scores = {"normal": 0, "mild_inflammation": 1, "moderate_inflammation": 2,
                  "severe_inflammation": 3, "critical": 4}
    scores["crp_score"] = crp_scores.get(crp_class, 0)
    total += scores["crp_score"]

    il6_class = classify_biomarker(biomarkers.il6_pg_ml, "il6")
    il6_scores = {"normal": 0, "elevated": 1, "high": 2, "cytokine_storm": 4}
    scores["il6_score"] = il6_scores.get(il6_class, 0)
    total += scores["il6_score"]

    lactate_class = classify_biomarker(biomarkers.lactate_mmol_l, "lactate")
    lactate_scores = {"normal": 0, "borderline": 1, "elevated": 2, "high": 4}
    scores["lactate_score"] = lactate_scores.get(lactate_class, 0)
    total += scores["lactate_score"]

    wbc_class = classify_biomarker(biomarkers.wbc_x10_3, "wbc")
    wbc_scores = {"leukopenia": 2, "normal": 0, "leukocytosis": 1, "leukocytosis_extreme": 3}
    scores["wbc_score"] = wbc_scores.get(wbc_class, 0)
    total += scores["wbc_score"]

    if biomarkers.bandemia_pct > 10:
        scores["bandemia_bonus"] = 2
        total += 2
    else:
        scores["bandemia_bonus"] = 0

    if biomarkers.platelet_x10_3 < 100:
        scores["thrombocytopenia_bonus"] = 2
        total += 2
    else:
        scores["thrombocytopenia_bonus"] = 0

    scores["total_sepsis_score"] = total

    if total >= 12:
        scores["severity_classification"] = "SEPTIC_SHOCK"
        scores["mortality_risk"] = "HIGH (40-60%)"
    elif total >= 8:
        scores["severity_classification"] = "SEVERE_SEPSIS"
        scores["mortality_risk"] = "MODERATE-HIGH (20-40%)"
    elif total >= 4:
        scores["severity_classification"] = "SEPSIS"
        scores["mortality_risk"] = "MODERATE (10-20%)"
    elif total >= 2:
        scores["severity_classification"] = "SIRS_LOCALIZED"
        scores["mortality_risk"] = "LOW (2-10%)"
    else:
        scores["severity_classification"] = "NO_SEPSIS"
        scores["mortality_risk"] = "MINIMAL (<2%)"

    scores["biomarker_classifications"] = {
        "pct": pct_class,
        "crp": crp_class,
        "il6": il6_class,
        "lactate": lactate_class,
        "wbc": wbc_class,
    }

    return scores


class SepsisBiomarkerAgent:
    """Sub-agent for sepsis biomarker correlation with TTP analysis."""

    def __init__(self):
        self.agent_name = "SepsisBiomarkerAgent"

    def evaluate(self, biomarkers: SepsisBiomarkers, ttp_hours: float,
                 organism_id: Optional[str] = None) -> Dict[str, Any]:
        """Correlate biomarkers with TTP to assess sepsis probability."""
        sepsis_scores = compute_sepsis_score(biomarkers)
        alerts = []

        if sepsis_scores["severity_classification"] in ("SEVERE_SEPSIS", "SEPTIC_SHOCK"):
            alerts.append({
                "type": "SEPSIS_BIOMARKER_CRITICAL",
                "severity": "CRITICAL" if sepsis_scores["severity_classification"] == "SEPTIC_SHOCK" else "WARNING",
                "message": f"Biomarker profile indicates {sepsis_scores['severity_classification']} "
                           f"(score: {sepsis_scores['total_sepsis_score']}/18).",
                "recommendation": "Immediate broad-spectrum antibiotics. Consider ICU transfer. "
                                  "Monitor for organ dysfunction."
            })

        if ttp_hours < 12.0 and sepsis_scores["total_sepsis_score"] >= 4:
            alerts.append({
                "type": "FAST_TTP_HIGH_BIOMARKERS",
                "severity": "CRITICAL",
                "message": f"Rapid TTP ({ttp_hours:.1f}h) with elevated sepsis biomarkers "
                           f"(score: {sepsis_scores['total_sepsis_score']}). High bacterial burden suspected.",
                "recommendation": "High-confidence true bacteremia. Initiate source-directed therapy."
            })

        if ttp_hours > 24.0 and sepsis_scores["total_sepsis_score"] < 2:
            alerts.append({
                "type": "SLOW_TTP_LOW_BIOMARKERS",
                "severity": "ADVISORY",
                "message": f"Prolonged TTP ({ttp_hours:.1f}h) with low biomarker score "
                           f"({sepsis_scores['total_sepsis_score']}). Contamination more likely.",
                "recommendation": "Consider repeating cultures before committing to long-term therapy."
            })

        contamination_adjustment = 0.0
        if sepsis_scores["total_sepsis_score"] >= 6:
            contamination_adjustment = -0.25
        elif sepsis_scores["total_sepsis_score"] >= 3:
            contamination_adjustment = -0.10

        return {
            "alerts": alerts,
            "sepsis_scores": sepsis_scores,
            "contamination_adjustment": contamination_adjustment,
            "severity": sepsis_scores["severity_classification"],
            "mortality_risk": sepsis_scores["mortality_risk"],
            "total_score": sepsis_scores["total_sepsis_score"],
        }


def create_biomarker_api_routes(app, coordinator):
    """Add sepsis biomarker endpoints to FastAPI app."""
    try:
        from pydantic import BaseModel

        class BiomarkerRequest(BaseModel):
            procalcitonin: float = 0.05
            crp: float = 5.0
            il6: float = 5.0
            lactate: float = 1.0
            wbc: float = 7.5
            neutrophil_pct: float = 60.0
            bandemia_pct: float = 0.0
            platelet: float = 250.0
            creatinine: float = 1.0
            bilirubin: float = 0.5
            ttp_hours: float = 15.0
            organism_id: str = ""

        @app.post("/api/sepsis-biomarkers")
        def api_sepsis_biomarkers(req: BiomarkerRequest):
            agent = SepsisBiomarkerAgent()
            biomarkers = SepsisBiomarkers(
                procalcitonin_ng_ml=req.procalcitonin,
                crp_mg_l=req.crp,
                il6_pg_ml=req.il6,
                lactate_mmol_l=req.lactate,
                wbc_x10_3=req.wbc,
                neutrophil_pct=req.neutrophil_pct,
                bandemia_pct=req.bandemia_pct,
                platelet_x10_3=req.platelet,
                creatinine_mg_dl=req.creatinine,
                bilirubin_mg_dl=req.bilirubin,
            )
            return agent.evaluate(biomarkers, ttp_hours=req.ttp_hours,
                                  organism_id=req.organism_id or None)

        @app.get("/api/sepsis-biomarkers/thresholds")
        def biomarker_thresholds():
            return BIOMARKER_THRESHOLDS
    except ImportError:
        pass
