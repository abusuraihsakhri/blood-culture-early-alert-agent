#!/usr/bin/env python3
"""Blood-culture time-to-positivity and contamination decision-support utilities.

The rules in this module are transparent heuristics intended for research,
education, workflow prototyping, and software testing. They are not calibrated
clinical prediction models and must not replace local microbiology,
antimicrobial-stewardship, or infectious-diseases guidance.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from typing import Any, Dict, List, Optional


COMMON_CONTAMINANTS = {
    "coagulase_negative_staphylococcus": {
        "common_name": "Coagulase-negative Staphylococcus (CoNS)",
        "contaminant_probability": 0.85,
    },
    "staphylococcus_epidermidis": {
        "common_name": "S. epidermidis",
        "contaminant_probability": 0.85,
    },
    "staphylococcus_haemolyticus": {
        "common_name": "S. haemolyticus",
        "contaminant_probability": 0.80,
    },
    "staphylococcus_lugdunensis": {
        "common_name": "S. lugdunensis",
        "contaminant_probability": 0.30,
    },
    "corynebacterium": {
        "common_name": "Corynebacterium spp.",
        "contaminant_probability": 0.90,
    },
    "corynebacterium_jeikeium": {
        "common_name": "C. jeikeium",
        "contaminant_probability": 0.50,
    },
    "cutibacterium_acnes": {
        "common_name": "C. acnes",
        "contaminant_probability": 0.95,
    },
    "propionibacterium_acnes": {
        "common_name": "P. acnes",
        "contaminant_probability": 0.95,
    },
    "bacillus": {
        "common_name": "Bacillus spp. (excluding B. anthracis)",
        "contaminant_probability": 0.90,
    },
    "bacillus_cereus": {
        "common_name": "B. cereus",
        "contaminant_probability": 0.60,
    },
    "micrococcus": {
        "common_name": "Micrococcus spp.",
        "contaminant_probability": 0.95,
    },
    "rothia": {"common_name": "Rothia spp.", "contaminant_probability": 0.80},
    "diphtheroids": {"common_name": "Diphtheroids", "contaminant_probability": 0.90},
}

TRUE_PATHOGENS = {
    "staphylococcus_aureus": {"common_name": "S. aureus", "pathogen_probability": 0.95},
    "escherichia_coli": {"common_name": "E. coli", "pathogen_probability": 0.98},
    "klebsiella_pneumoniae": {"common_name": "K. pneumoniae", "pathogen_probability": 0.97},
    "klebsiella_oxytoca": {"common_name": "K. oxytoca", "pathogen_probability": 0.95},
    "pseudomonas_aeruginosa": {"common_name": "P. aeruginosa", "pathogen_probability": 0.97},
    "enterococcus_faecalis": {"common_name": "E. faecalis", "pathogen_probability": 0.85},
    "enterococcus_faecium": {"common_name": "E. faecium", "pathogen_probability": 0.85},
    "candida_albicans": {"common_name": "C. albicans", "pathogen_probability": 0.98},
    "candida_glabrata": {"common_name": "C. glabrata", "pathogen_probability": 0.97},
    "candida": {"common_name": "Candida spp.", "pathogen_probability": 0.97},
    "streptococcus_pneumoniae": {"common_name": "S. pneumoniae", "pathogen_probability": 0.98},
    "streptococcus_pyogenes": {"common_name": "S. pyogenes", "pathogen_probability": 0.98},
    "streptococcus_agalactiae": {"common_name": "S. agalactiae", "pathogen_probability": 0.95},
    "streptococcus_viridans": {
        "common_name": "Viridans group streptococci",
        "pathogen_probability": 0.75,
    },
    "enterobacter_cloacae": {"common_name": "E. cloacae", "pathogen_probability": 0.95},
    "serratia_marcescens": {"common_name": "S. marcescens", "pathogen_probability": 0.95},
    "proteus_mirabilis": {"common_name": "P. mirabilis", "pathogen_probability": 0.95},
    "acinetobacter_baumannii": {"common_name": "A. baumannii", "pathogen_probability": 0.95},
    "bacteroides_fragilis": {"common_name": "B. fragilis", "pathogen_probability": 0.95},
    "clostridium_perfringens": {"common_name": "C. perfringens", "pathogen_probability": 0.90},
    "salmonella": {"common_name": "Salmonella spp.", "pathogen_probability": 0.98},
    "neisseria_meningitidis": {"common_name": "N. meningitidis", "pathogen_probability": 0.99},
    "haemophilus_influenzae": {"common_name": "H. influenzae", "pathogen_probability": 0.95},
    "listeria_monocytogenes": {"common_name": "L. monocytogenes", "pathogen_probability": 0.98},
}

GRAM_STAIN_MAP = {
    "gram_positive_cocci_clusters": [
        "staphylococcus_aureus",
        "coagulase_negative_staphylococcus",
        "staphylococcus_epidermidis",
        "staphylococcus_lugdunensis",
    ],
    "gram_positive_cocci_chains": [
        "streptococcus_pneumoniae",
        "streptococcus_pyogenes",
        "streptococcus_agalactiae",
        "streptococcus_viridans",
        "enterococcus_faecalis",
        "enterococcus_faecium",
    ],
    "gram_negative_rods": [
        "escherichia_coli",
        "klebsiella_pneumoniae",
        "pseudomonas_aeruginosa",
        "enterobacter_cloacae",
        "serratia_marcescens",
        "proteus_mirabilis",
        "acinetobacter_baumannii",
        "haemophilus_influenzae",
    ],
    "gram_negative_diplococci": ["neisseria_meningitidis"],
    "gram_positive_rods": [
        "listeria_monocytogenes",
        "corynebacterium",
        "bacillus",
        "clostridium_perfringens",
        "cutibacterium_acnes",
    ],
    "yeast": ["candida_albicans", "candida_glabrata", "candida", "cryptococcus_neoformans"],
}

GRAM_ALIASES = {
    "gpc_in_clusters": "gram_positive_cocci_clusters",
    "gpc_clusters": "gram_positive_cocci_clusters",
    "gpc_in_pairs_chains": "gram_positive_cocci_chains",
    "gpc_pairs_chains": "gram_positive_cocci_chains",
    "gpc_chains": "gram_positive_cocci_chains",
    "gnb": "gram_negative_rods",
    "gnr": "gram_negative_rods",
    "gnc": "gram_negative_diplococci",
    "gndc": "gram_negative_diplococci",
    "gpr": "gram_positive_rods",
    "budding_yeast": "yeast",
    "yeast_pseudohyphae": "yeast",
}

ORGANISM_ALIASES = {
    "s_aureus": "staphylococcus_aureus",
    "staph_aureus": "staphylococcus_aureus",
    "e_coli": "escherichia_coli",
    "p_aeruginosa": "pseudomonas_aeruginosa",
    "c_acnes": "cutibacterium_acnes",
    "cons": "coagulase_negative_staphylococcus",
}


def _slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value


def _normalise_organism(value: str) -> str:
    key = _slug(value)
    return ORGANISM_ALIASES.get(key, key)


def _normalise_gram(value: str) -> str:
    key = _slug(value)
    return GRAM_ALIASES.get(key, key)


def _require_finite_nonnegative(value: float, label: str) -> None:
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be a finite non-negative number")


def _validate_bottles(positive: int, total: int) -> None:
    if total < 1:
        raise ValueError("total bottles must be at least 1")
    if positive < 0:
        raise ValueError("positive bottles cannot be negative")
    if positive > total:
        raise ValueError("positive bottles cannot exceed total bottles")


def interpret_ttp(ttp_hours: float) -> Dict[str, Any]:
    """Categorise TTP using transparent, non-validated heuristic cut points."""
    if not math.isfinite(ttp_hours) or ttp_hours < 0:
        return {"error": "TTP must be a finite non-negative number", "ttp_hours": ttp_hours}

    if ttp_hours < 12:
        category = "RAPID_GROWTH"
        significance = "HIGH"
        interpretation = "Early instrument positivity (<12 h)"
        concerns = [
            "Higher organism burden is possible",
            "Interpret with organism identity, source, and patient context",
        ]
    elif ttp_hours <= 36:
        category = "NORMAL_GROWTH"
        significance = "MODERATE"
        interpretation = "Intermediate instrument positivity (12-36 h)"
        concerns = ["TTP alone does not establish pathogen versus contaminant status"]
    else:
        category = "SLOW_GROWTH"
        significance = "LOW_TO_MODERATE"
        interpretation = "Late instrument positivity (>36 h)"
        concerns = [
            "Some skin-flora contaminants are more common among late positives",
            "Fastidious organisms and prior antimicrobial exposure can also delay positivity",
        ]

    return {
        "ttp_hours": ttp_hours,
        "category": category,
        "interpretation": interpretation,
        "clinical_significance": significance,
        "concerns": concerns,
        "recommendations": [
            "Correlate TTP with organism identification, number of positive sets, collection site, and clinical context",
            "Use local laboratory and antimicrobial-stewardship procedures for clinical actions",
        ],
        "heuristic": True,
    }


def _lookup_organism(key: str) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    contaminant_info = COMMON_CONTAMINANTS.get(key)
    pathogen_info = TRUE_PATHOGENS.get(key)

    if contaminant_info is None:
        for candidate, info in COMMON_CONTAMINANTS.items():
            if candidate in key or key in candidate:
                contaminant_info = info
                break

    if pathogen_info is None:
        for candidate, info in TRUE_PATHOGENS.items():
            if candidate in key or key in candidate:
                pathogen_info = info
                break

    return contaminant_info, pathogen_info


def assess_contamination(
    organism: str,
    ttp_hours: float,
    num_bottles_positive: int = 1,
    num_bottles_total: int = 2,
    gram_stain: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute an interpretable heuristic contamination score.

    The returned contamination_probability key is retained for backward
    compatibility. It is a heuristic score in [0, 1], not a calibrated
    probability from a validated clinical prediction model.
    """
    _require_finite_nonnegative(ttp_hours, "TTP")
    _validate_bottles(num_bottles_positive, num_bottles_total)

    organism_key = _normalise_organism(organism)
    contaminant_info, pathogen_info = _lookup_organism(organism_key)

    if contaminant_info and not pathogen_info:
        base = contaminant_info["contaminant_probability"]
    elif pathogen_info:
        base = 1.0 - pathogen_info["pathogen_probability"]
    else:
        base = 0.50

    ttp_adjustment = 0.15 if ttp_hours > 36 else (-0.20 if ttp_hours < 12 else 0.0)
    positivity_ratio = num_bottles_positive / num_bottles_total
    bottle_adjustment = -0.25 if positivity_ratio == 1.0 and num_bottles_total >= 2 else 0.0
    if positivity_ratio <= 0.5:
        bottle_adjustment += 0.15

    score = max(0.0, min(1.0, base + ttp_adjustment + bottle_adjustment))
    if score >= 0.75:
        classification = "LIKELY_CONTAMINANT"
        action = "Review for possible contamination using clinical context and repeat sampling when indicated"
    elif score >= 0.40:
        classification = "INDETERMINATE"
        action = "Do not classify from this score alone; correlate clinically"
    else:
        classification = "LIKELY_TRUE_PATHOGEN"
        action = "Treat the isolate as clinically significant until reviewed in context"

    display = (contaminant_info or pathogen_info or {}).get("common_name", organism)
    alerts: List[Dict[str, str]] = []
    if classification == "LIKELY_CONTAMINANT":
        alerts.append(
            {
                "severity": "ADVISORY",
                "type": "CONTAMINATION_SIGNAL",
                "message": f"{display} has a high heuristic contamination score ({score:.0%})",
                "recommendation": "Confirm against collection pattern, repeat cultures, devices, and clinical findings",
            }
        )
    elif classification == "LIKELY_TRUE_PATHOGEN":
        alerts.append(
            {
                "severity": "WARNING",
                "type": "PATHOGEN_SIGNAL",
                "message": f"{display} has a low heuristic contamination score ({score:.0%})",
                "recommendation": "Use organism identification and susceptibility data with local treatment guidance",
            }
        )
    if ttp_hours < 12:
        alerts.append(
            {
                "severity": "CRITICAL",
                "type": "EARLY_POSITIVITY",
                "message": f"Early positivity at {ttp_hours:.1f} h",
                "recommendation": "Prioritise clinical review; TTP alone does not identify the source",
            }
        )

    return {
        "organism": organism,
        "organism_key": organism_key,
        "organism_display": display,
        "ttp_hours": ttp_hours,
        "num_bottles_positive": num_bottles_positive,
        "num_bottles_total": num_bottles_total,
        "contamination_probability": round(score, 2),
        "score_is_calibrated_probability": False,
        "classification": classification,
        "clinical_action": action,
        "is_known_contaminant": contaminant_info is not None and pathogen_info is None,
        "is_known_pathogen": pathogen_info is not None,
        "gram_stain": gram_stain,
        "alerts": alerts,
    }


def _get_empiric_guidance(gram_key: str) -> Dict[str, Any]:
    """Return non-prescriptive organism/coverage prompts for local review."""
    if gram_key == "gram_positive_cocci_clusters":
        return {
            "likely_organisms": "Staphylococcus spp.",
            "empiric_therapy": ["Review local MRSA/MSSA empiric-coverage pathway"],
            "key_differentiation": "Rapid species identification and susceptibility testing",
        }
    if gram_key == "gram_positive_cocci_chains":
        return {
            "likely_organisms": "Streptococcus spp. or Enterococcus spp.",
            "empiric_therapy": ["Review local streptococcal/enterococcal empiric-coverage pathway"],
            "key_differentiation": "Species identification and susceptibility testing",
        }
    if gram_key == "gram_negative_rods":
        return {
            "likely_organisms": "Enterobacterales, non-fermenters, or other Gram-negative bacilli",
            "empiric_therapy": ["Review local Gram-negative sepsis pathway and antibiogram"],
            "key_differentiation": "Rapid identification plus resistance-risk assessment",
        }
    if gram_key == "gram_negative_diplococci":
        return {
            "likely_organisms": "Neisseria spp. and other Gram-negative cocci",
            "empiric_therapy": ["Urgently review organism-specific infection-control and treatment guidance"],
            "key_differentiation": "Rapid species confirmation",
        }
    if gram_key == "gram_positive_rods":
        return {
            "likely_organisms": "Listeria, Corynebacterium, Bacillus, Clostridium, Cutibacterium, or others",
            "empiric_therapy": ["Interpret with host factors, morphology, and species identification"],
            "key_differentiation": "Species identification is essential",
        }
    if gram_key == "yeast":
        return {
            "likely_organisms": "Candida spp., Cryptococcus spp., or other yeasts",
            "empiric_therapy": ["Urgently review local candidemia/fungemia pathway"],
            "key_differentiation": "Rapid species identification and antifungal susceptibility where indicated",
        }
    return {
        "likely_organisms": "Not resolved from the supplied morphology",
        "empiric_therapy": ["Use local blood-culture escalation guidance pending identification"],
        "key_differentiation": "Confirm morphology and organism identification",
    }


def interpret_gram_stain(gram_stain: str) -> Dict[str, Any]:
    """Interpret common Gram-stain descriptions and laboratory abbreviations."""
    gram_key = _normalise_gram(gram_stain)

    expected = GRAM_STAIN_MAP.get(gram_key, [])
    if not expected:
        if "gram_positive" in gram_key and "cocci" in gram_key:
            if "cluster" in gram_key:
                gram_key = "gram_positive_cocci_clusters"
            elif "chain" in gram_key or "pair" in gram_key:
                gram_key = "gram_positive_cocci_chains"
        elif "gram_negative" in gram_key and ("rod" in gram_key or "bacill" in gram_key):
            gram_key = "gram_negative_rods"
        elif "gram_negative" in gram_key and ("cocci" in gram_key or "diplo" in gram_key):
            gram_key = "gram_negative_diplococci"
        elif "gram_positive" in gram_key and ("rod" in gram_key or "bacill" in gram_key):
            gram_key = "gram_positive_rods"
        elif "yeast" in gram_key or "fungal" in gram_key:
            gram_key = "yeast"
        expected = GRAM_STAIN_MAP.get(gram_key, [])

    return {
        "gram_stain": gram_stain,
        "normalised_gram_stain": gram_key,
        "expected_organisms": expected,
        "empiric_guidance": _get_empiric_guidance(gram_key),
        "num_expected": len(expected),
    }


def assess_escalation_triggers(
    organism: str,
    ttp_hours: float,
    susceptibility: Optional[Dict[str, str]] = None,
    patient_factors: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Flag review triggers without prescribing a regimen."""
    _require_finite_nonnegative(ttp_hours, "TTP")
    organism_key = _normalise_organism(organism)
    triggers: List[Dict[str, str]] = []

    if ttp_hours < 12:
        triggers.append(
            {"trigger": "EARLY_POSITIVITY", "severity": "HIGH", "detail": f"TTP {ttp_hours:.1f} h"}
        )

    high_priority = {
        "pseudomonas_aeruginosa",
        "acinetobacter_baumannii",
        "candida",
        "candida_albicans",
        "candida_glabrata",
        "staphylococcus_aureus",
        "enterococcus_faecium",
        "neisseria_meningitidis",
    }
    if organism_key in high_priority:
        triggers.append(
            {
                "trigger": "HIGH_RISK_ORGANISM",
                "severity": "HIGH",
                "detail": f"{organism} warrants prompt organism-specific review",
            }
        )

    if susceptibility:
        normalised = {str(k).lower(): str(v).upper() for k, v in susceptibility.items()}
        resistant_count = sum(1 for value in normalised.values() if value == "R")
        if resistant_count >= 3:
            triggers.append(
                {
                    "trigger": "MULTI_DRUG_RESISTANT",
                    "severity": "CRITICAL",
                    "detail": f"{resistant_count} reported resistant results",
                }
            )
        if normalised.get("vancomycin") == "R":
            triggers.append(
                {
                    "trigger": "VANCOMYCIN_RESISTANCE_REPORTED",
                    "severity": "CRITICAL",
                    "detail": "Verify organism, method, MIC/breakpoint, and local reporting rules",
                }
            )

    factors = patient_factors or {}
    for key, label in (
        ("immunocompromised", "IMMUNOCOMPROMISED_HOST"),
        ("neutropenic", "NEUTROPENIA"),
        ("septic_shock", "SEPTIC_SHOCK"),
    ):
        if factors.get(key):
            triggers.append(
                {
                    "trigger": label,
                    "severity": "CRITICAL" if key != "immunocompromised" else "HIGH",
                    "detail": label.replace("_", " ").title(),
                }
            )

    escalation_needed = bool(triggers)
    return {
        "organism": organism,
        "ttp_hours": ttp_hours,
        "escalation_needed": escalation_needed,
        "trigger_count": len(triggers),
        "triggers": triggers,
        "recommendation": (
            "Prompt clinical and microbiology review is indicated"
            if escalation_needed
            else "No heuristic escalation trigger detected; continue standard review"
        ),
    }


def recommend_repeat_cultures(
    organism: str,
    ttp_hours: float,
    classification: str,
    day_of_positive_culture: int = 1,
    has_endovascular_hardware: bool = False,
    is_staphylococcus_aureus: bool = False,
    is_candida: bool = False,
) -> Dict[str, Any]:
    """Return selective follow-up-culture prompts."""
    _require_finite_nonnegative(ttp_hours, "TTP")
    organism_key = _normalise_organism(organism)
    recs: List[Dict[str, str]] = []
    urgency = "ROUTINE"
    repeat_interval_hours: Optional[int] = None

    if is_staphylococcus_aureus or organism_key == "staphylococcus_aureus":
        recs.append(
            {
                "reason": "S. aureus bloodstream infection",
                "action": "Follow local S. aureus bacteremia clearance-culture protocol",
                "evidence": "Organism-specific management practice",
            }
        )
        urgency, repeat_interval_hours = "URGENT", 24
        if has_endovascular_hardware:
            recs.append(
                {
                    "reason": "Endovascular hardware present",
                    "action": "Escalate endovascular-source assessment",
                    "evidence": "Clinical risk factor",
                }
            )
    elif is_candida or organism_key.startswith("candida"):
        recs.append(
            {
                "reason": "Candidemia/fungemia",
                "action": "Follow local candidemia clearance-culture and source-control protocol",
                "evidence": "Organism-specific management practice",
            }
        )
        urgency, repeat_interval_hours = "URGENT", 24
    elif classification == "LIKELY_CONTAMINANT":
        recs.append(
            {
                "reason": "High heuristic contamination score",
                "action": "Consider repeat peripheral cultures when clinical uncertainty remains",
                "evidence": "Context-dependent confirmation",
            }
        )
        urgency = "LOW"
    elif organism_key in {
        "escherichia_coli",
        "klebsiella_pneumoniae",
        "pseudomonas_aeruginosa",
        "enterobacter_cloacae",
    }:
        recs.append(
            {
                "reason": "Gram-negative bloodstream infection",
                "action": "Use selective follow-up cultures for persistence risk, poor response, endovascular source, or resistant organisms",
                "evidence": "Follow-up culture utility is context dependent",
            }
        )
        urgency = "MODERATE"

    if ttp_hours < 12:
        recs.append(
            {
                "reason": "Early positivity",
                "action": "Prioritise source assessment; TTP alone does not diagnose endocarditis",
                "evidence": "TTP is supportive rather than diagnostic",
            }
        )
        if urgency in {"ROUTINE", "LOW"}:
            urgency = "MODERATE"

    if not recs:
        recs.append(
            {
                "reason": "No organism-specific repeat-culture rule encoded",
                "action": "Use local guidance and clinical course",
                "evidence": "Clinical judgement",
            }
        )

    return {
        "organism": organism,
        "urgency": urgency,
        "repeat_interval_hours": repeat_interval_hours,
        "recommendations": recs,
        "total_recommendations": len(recs),
    }


def analyze_blood_culture(
    organism: str,
    ttp_hours: float,
    gram_stain: Optional[str] = None,
    num_bottles_positive: int = 1,
    num_bottles_total: int = 2,
    susceptibility: Optional[Dict[str, str]] = None,
    patient_factors: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run the combined heuristic analysis."""
    _require_finite_nonnegative(ttp_hours, "TTP")
    _validate_bottles(num_bottles_positive, num_bottles_total)

    contamination = assess_contamination(
        organism,
        ttp_hours,
        num_bottles_positive,
        num_bottles_total,
        gram_stain,
    )
    escalation = assess_escalation_triggers(organism, ttp_hours, susceptibility, patient_factors)
    organism_key = _normalise_organism(organism)

    result: Dict[str, Any] = {
        "organism": organism,
        "ttp_hours": ttp_hours,
        "analyses": {
            "ttp": interpret_ttp(ttp_hours),
            "contamination": contamination,
            "escalation": escalation,
            "repeat_cultures": recommend_repeat_cultures(
                organism,
                ttp_hours,
                contamination["classification"],
                is_staphylococcus_aureus=organism_key == "staphylococcus_aureus",
                is_candida=organism_key.startswith("candida"),
                has_endovascular_hardware=(patient_factors or {}).get("endovascular_hardware", False),
            ),
        },
        "disclaimer": "Research/education heuristic; not a validated clinical prediction model.",
    }
    if gram_stain:
        result["analyses"]["gram_stain"] = interpret_gram_stain(gram_stain)

    severities = [alert.get("severity", "INFO") for alert in contamination.get("alerts", [])]
    severities += [trigger.get("severity", "INFO") for trigger in escalation.get("triggers", [])]
    if "CRITICAL" in severities:
        result["overall_severity"] = "CRITICAL"
    elif "HIGH" in severities or "WARNING" in severities:
        result["overall_severity"] = "WARNING"
    elif "ADVISORY" in severities:
        result["overall_severity"] = "ADVISORY"
    else:
        result["overall_severity"] = "INFO"
    return result


def _extract_ttp(row: Dict[str, str], row_number: int) -> float:
    keys = (
        "time_to_flag_positive_hours",
        "time_to_flag_positive",
        "ttp_hours",
        "ttp",
        "metric_primary",
    )
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            try:
                parsed = float(value)
            except ValueError as exc:
                raise ValueError(f"row {row_number}: invalid {key}={value!r}") from exc
            _require_finite_nonnegative(parsed, f"row {row_number} TTP")
            return parsed
    raise ValueError(f"row {row_number}: no TTP field found")


def _computed_urgency(gram_stain: str, ttp_hours: float) -> str:
    gram_key = _normalise_gram(gram_stain)
    if ttp_hours < 12 or gram_key in {"gram_negative_rods", "gram_negative_diplococci", "yeast"}:
        return "STAT"
    if ttp_hours <= 24 or gram_key in {"gram_positive_cocci_clusters", "gram_positive_cocci_chains"}:
        return "URGENT"
    return "ROUTINE"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="blood-culture-early-alert-agent",
        description="Blood-culture TTP and contamination heuristic utilities",
    )
    sub = parser.add_subparsers(dest="cmd")

    p_ttp = sub.add_parser("ttp", help="Interpret time-to-positivity")
    p_ttp.add_argument("--hours", type=float, required=True)

    p_contam = sub.add_parser("contamination", help="Assess heuristic contamination score")
    p_contam.add_argument("--organism", required=True)
    p_contam.add_argument("--ttp", type=float, required=True)
    p_contam.add_argument("--positive-bottles", type=int, default=1)
    p_contam.add_argument("--total-bottles", type=int, default=2)

    p_gram = sub.add_parser("gram-stain", help="Interpret Gram-stain morphology")
    p_gram.add_argument("--result", required=True)

    p_analyse = sub.add_parser("analyze", help="Run combined analysis")
    p_analyse.add_argument("--organism", required=True)
    p_analyse.add_argument("--ttp", type=float, required=True)
    p_analyse.add_argument("--gram-stain")
    p_analyse.add_argument("--positive-bottles", type=int, default=1)
    p_analyse.add_argument("--total-bottles", type=int, default=2)
    p_analyse.add_argument("--susceptibility", help="JSON object of antibiotic: S/I/R values")
    p_analyse.add_argument("--immunocompromised", action="store_true")
    p_analyse.add_argument("--neutropenic", action="store_true")
    p_analyse.add_argument("--septic-shock", action="store_true")
    p_analyse.add_argument("--endovascular-hardware", action="store_true")

    p_batch = sub.add_parser("batch", help="Process CSV records")
    p_batch.add_argument("-i", "--input", required=True)
    p_batch.add_argument("-o", "--output", default="results.csv")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.cmd == "ttp":
            print(json.dumps(interpret_ttp(args.hours), indent=2))
            return 0

        if args.cmd == "contamination":
            result = assess_contamination(
                args.organism,
                args.ttp,
                args.positive_bottles,
                args.total_bottles,
            )
            print(json.dumps(result, indent=2))
            return 0

        if args.cmd == "gram-stain":
            print(json.dumps(interpret_gram_stain(args.result), indent=2))
            return 0

        if args.cmd == "analyze":
            factors = {
                key: True
                for key in ("immunocompromised", "neutropenic", "septic_shock", "endovascular_hardware")
                if getattr(args, key)
            }
            susceptibility = json.loads(args.susceptibility) if args.susceptibility else None
            result = analyze_blood_culture(
                organism=args.organism,
                ttp_hours=args.ttp,
                gram_stain=args.gram_stain,
                num_bottles_positive=args.positive_bottles,
                num_bottles_total=args.total_bottles,
                susceptibility=susceptibility,
                patient_factors=factors or None,
            )
            print(json.dumps(result, indent=2))
            return 0

        if args.cmd == "batch":
            with open(args.input, encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = list(reader.fieldnames or [])
                rows = list(reader)

            extra = [
                "computed_urgency_escalation",
                "time_to_positivity_category",
                "empiric_antibiotic_advisory",
                "likely_pathogens",
                "critical_panic_call_window_minutes",
            ]
            output_fields = list(dict.fromkeys(fieldnames + extra))
            output_rows: List[Dict[str, Any]] = []

            for index, row in enumerate(rows, start=2):
                gram_raw = (
                    row.get("gram_stain_morphology")
                    or row.get("gram_stain")
                    or row.get("status_flag")
                    or ""
                )
                ttp = _extract_ttp(row, index)
                gram_analysis = interpret_gram_stain(gram_raw)
                ttp_analysis = interpret_ttp(ttp)
                urgency = _computed_urgency(gram_raw, ttp)

                output = dict(row)
                output["computed_urgency_escalation"] = urgency
                output["time_to_positivity_category"] = ttp_analysis["category"]
                output["empiric_antibiotic_advisory"] = "; ".join(
                    gram_analysis["empiric_guidance"]["empiric_therapy"]
                )
                output["likely_pathogens"] = gram_analysis["empiric_guidance"]["likely_organisms"]
                output["critical_panic_call_window_minutes"] = 30 if urgency in {"STAT", "URGENT"} else 60
                output_rows.append(output)

            with open(args.output, "w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=output_fields)
                writer.writeheader()
                writer.writerows(output_rows)

            print(f"Batch processed {len(output_rows)} blood culture records -> {args.output}")
            return 0

        parser.print_help()
        return 1

    except (ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
