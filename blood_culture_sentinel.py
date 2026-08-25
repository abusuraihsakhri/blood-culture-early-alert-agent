#!/usr/bin/env python3
"""
Blood Culture Early Alert Agent

Real implementation of:
- Time-to-positivity (TTP) interpretation
- Contamination assessment (true pathogen vs contaminant)
- Gram stain interpretation and expected organisms
- Antibiotic escalation triggers
- Repeat blood culture recommendations

Uses only Python stdlib.
"""

import argparse
import csv
import json
import sys
from typing import Dict, List, Optional, Any

# ─── Known Organism Databases ────────────────────────────────────────────────

COMMON_CONTAMINANTS = {
    "coagulase_negative_staphylococcus": {"common_name": "Coagulase-negative Staph (CoNS)", "contaminant_probability": 0.85},
    "staphylococcus_epidermidis": {"common_name": "S. epidermidis", "contaminant_probability": 0.85},
    "staphylococcus_haemolyticus": {"common_name": "S. haemolyticus", "contaminant_probability": 0.80},
    "staphylococcus_lugdunensis": {"common_name": "S. lugdunensis", "contaminant_probability": 0.30},  # More often pathogenic
    "corynebacterium": {"common_name": "Corynebacterium spp.", "contaminant_probability": 0.90},
    "corynebacterium_jeikeium": {"common_name": "C. jeikeium", "contaminant_probability": 0.50},
    "propionibacterium_acnes": {"common_name": "P. acnes", "contaminant_probability": 0.95},
    "cutibacterium_acnes": {"common_name": "C. acnes", "contaminant_probability": 0.95},
    "bacillus": {"common_name": "Bacillus spp. (not B. anthracis)", "contaminant_probability": 0.90},
    "bacillus_cereus": {"common_name": "B. cereus", "contaminant_probability": 0.60},
    "micrococcus": {"common_name": "Micrococcus spp.", "contaminant_probability": 0.95},
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
    "streptococcus_pyogenes": {"common_name": "S. pyogenes (Group A Strep)", "pathogen_probability": 0.98},
    "streptococcus_agalactiae": {"common_name": "S. agalactiae (Group B Strep)", "pathogen_probability": 0.95},
    "streptococcus_viridans": {"common_name": "Viridans group Streptococci", "pathogen_probability": 0.75},
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

# Gram stain mapping
GRAM_STAIN_MAP = {
    "gram_positive_cocci_clusters": [
        "staphylococcus_aureus", "coagulase_negative_staphylococcus",
        "staphylococcus_epidermidis", "staphylococcus_lugdunensis",
    ],
    "gram_positive_cocci_chains": [
        "streptococcus_pneumoniae", "streptococcus_pyogenes",
        "streptococcus_agalactiae", "streptococcus_viridans",
        "enterococcus_faecalis", "enterococcus_faecium",
    ],
    "gram_negative_rods": [
        "escherichia_coli", "klebsiella_pneumoniae", "pseudomonas_aeruginosa",
        "enterobacter_cloacae", "serratia_marcescens", "proteus_mirabilis",
        "acinetobacter_baumannii", "haemophilus_influenzae",
    ],
    "gram_negative_diplococci": [
        "neisseria_meningitidis",
    ],
    "gram_positive_rods": [
        "listeria_monocytogenes", "corynebacterium", "bacillus",
        "clostridium_perfringens", "cutibacterium_acnes",
    ],
    "yeast": [
        "candida_albicans", "candida_glabrata", "candida",
        "cryptococcus_neoformans",
    ],
}


# ─── Time-to-Positivity Interpretation ───────────────────────────────────────

def interpret_ttp(ttp_hours: float) -> Dict[str, Any]:
    """Interpret blood culture time-to-positivity.

    Args:
        ttp_hours: Time to positivity in hours

    Returns:
        Dict with interpretation, clinical significance, and recommendations
    """
    if ttp_hours < 0:
        return {"error": "TTP cannot be negative", "ttp_hours": ttp_hours}

    if ttp_hours < 12:
        return {
            "ttp_hours": ttp_hours,
            "category": "RAPID_GROWTH",
            "interpretation": "Rapid time to positivity (<12 hours)",
            "clinical_significance": "HIGH",
            "concerns": [
                "High bacterial burden in bloodstream",
                "Consider endocarditis, especially with Gram-positive cocci in clusters",
                "Consider deep-seated source: abscess, osteomyelitis, infected hardware",
                "May indicate intravascular infection source",
            ],
            "recommendations": [
                "Urgent clinical evaluation",
                "Echocardiography (TTE/TEE) if Gram-positive cocci identified",
                "Source control assessment",
                "Consider infectious disease consultation",
            ],
        }
    elif ttp_hours <= 36:
        return {
            "ttp_hours": ttp_hours,
            "category": "NORMAL_GROWTH",
            "interpretation": "Normal time to positivity (12-36 hours)",
            "clinical_significance": "MODERATE",
            "concerns": [
                "Typical bacteremia",
                "Standard clinical evaluation appropriate",
            ],
            "recommendations": [
                "Continue current management",
                "Follow standard blood culture protocols",
                "Review susceptibilities when available",
            ],
        }
    else:
        return {
            "ttp_hours": ttp_hours,
            "category": "SLOW_GROWTH",
            "interpretation": "Slow time to positivity (>36 hours)",
            "clinical_significance": "LOW_TO_MODERATE",
            "concerns": [
                "Possible contaminant organism",
                "Low-grade or intermittent bacteremia",
                "Fastidious organism (consider HACEK group, Brucella)",
                "Prior antibiotic exposure may delay growth",
            ],
            "recommendations": [
                "Correlate with Gram stain and organism identification",
                "Assess clinical context for true bacteremia vs contamination",
                "Consider repeat blood cultures if clinical suspicion remains",
                "If fastidious organism suspected, consider extended incubation",
            ],
        }


# ─── Contamination Assessment ────────────────────────────────────────────────

def assess_contamination(organism: str, ttp_hours: float,
                          num_bottles_positive: int = 1,
                          num_bottles_total: int = 2,
                          gram_stain: Optional[str] = None) -> Dict[str, Any]:
    """Assess likelihood of true bacteremia vs contamination.

    Args:
        organism: Identified organism name
        ttp_hours: Time to positivity in hours
        num_bottles_positive: Number of positive bottles
        num_bottles_total: Total number of bottles drawn
        gram_stain: Gram stain result (optional)

    Returns:
        Dict with contamination assessment, probability, and recommendations
    """
    organism_key = organism.lower().replace(" ", "_").replace(".", "")

    # Check if known contaminant
    contaminant_info = None
    for key, info in COMMON_CONTAMINANTS.items():
        if key in organism_key or organism_key in key:
            contaminant_info = info
            break

    # Check if known pathogen
    pathogen_info = None
    for key, info in TRUE_PATHOGENS.items():
        if key in organism_key or organism_key in key:
            pathogen_info = info
            break

    # Calculate contamination probability
    if contaminant_info and not pathogen_info:
        base_contamination_prob = contaminant_info.get("contaminant_probability",
                                                        contaminant_info.get("contamination_probability", 0.5))
    elif pathogen_info:
        base_contamination_prob = 1.0 - pathogen_info.get("pathogen_probability",
                                                            pathogen_info.get("contamination_probability", 0.5))
    else:
        base_contamination_prob = 0.5  # Unknown organism

    # Adjust for TTP
    ttp_adjustment = 0.0
    if ttp_hours > 36:
        ttp_adjustment += 0.15  # Slow growth increases contamination likelihood
    elif ttp_hours < 12:
        ttp_adjustment -= 0.20  # Rapid growth decreases contamination likelihood

    # Adjust for number of positive bottles
    bottle_adjustment = 0.0
    if num_bottles_total > 0:
        positivity_ratio = num_bottles_positive / num_bottles_total
        if positivity_ratio >= 1.0 and num_bottles_total >= 2:
            bottle_adjustment -= 0.25  # All bottles positive = more likely true
        elif positivity_ratio <= 0.5:
            bottle_adjustment += 0.15  # Only some bottles positive = more likely contaminant

    contamination_prob = max(0.0, min(1.0,
        base_contamination_prob + ttp_adjustment + bottle_adjustment))

    # Determine classification
    if contamination_prob >= 0.75:
        classification = "LIKELY_CONTAMINANT"
        clinical_action = "Consider not treating; discuss with clinical team"
    elif contamination_prob >= 0.40:
        classification = "INDETERMINATE"
        clinical_action = "Repeat blood cultures; correlate clinically"
    else:
        classification = "LIKELY_TRUE_PATHOGEN"
        clinical_action = "Treat as true bacteremia"

    result = {
        "organism": organism,
        "organism_display": (contaminant_info or pathogen_info or {}).get("common_name", organism),
        "ttp_hours": ttp_hours,
        "num_bottles_positive": num_bottles_positive,
        "num_bottles_total": num_bottles_total,
        "contamination_probability": round(contamination_prob, 2),
        "classification": classification,
        "clinical_action": clinical_action,
        "is_known_contaminant": contaminant_info is not None and pathogen_info is None,
        "is_known_pathogen": pathogen_info is not None,
    }

    # Add alerts
    alerts = []
    if classification == "LIKELY_CONTAMINANT":
        alerts.append({
            "severity": "ADVISORY",
            "type": "CONTAMINATION_LIKELY",
            "message": f"{result['organism_display']} is likely a contaminant "
                       f"(probability: {contamination_prob:.0%})",
            "recommendation": "Correlate with clinical presentation. Consider not initiating "
                            "antimicrobial therapy if patient is clinically well.",
        })
    elif classification == "LIKELY_TRUE_PATHOGEN":
        alerts.append({
            "severity": "WARNING",
            "type": "TRUE_PATHOGEN_LIKELY",
            "message": f"{result['organism_display']} is likely a true pathogen "
                       f"(contamination probability: {contamination_prob:.0%})",
            "recommendation": "Initiate appropriate antimicrobial therapy. "
                            "Obtain susceptibilities and de-escalate when possible.",
        })

    if ttp_hours < 12:
        alerts.append({
            "severity": "CRITICAL",
            "type": "RAPID_TTP_ALERT",
            "message": f"Rapid time to positivity ({ttp_hours:.1f}h) suggests high bacterial burden",
            "recommendation": "Evaluate for endocarditis, deep-seated abscess, or "
                            "intravascular infection source. Consider echocardiography.",
        })

    result["alerts"] = alerts
    return result


# ─── Gram Stain Interpretation ───────────────────────────────────────────────

def interpret_gram_stain(gram_stain: str) -> Dict[str, Any]:
    """Interpret a Gram stain result and provide expected organisms.

    Args:
        gram_stain: Gram stain description (e.g., 'gram_positive_cocci_clusters',
                    'gram_negative_rods', 'yeast')

    Returns:
        Dict with expected organisms, typical pathogens, and clinical guidance
    """
    gs_key = gram_stain.lower().replace(" ", "_").replace("-", "_")

    # Find matching category
    expected_organisms = []
    for category, organisms in GRAM_STAIN_MAP.items():
        if category in gs_key or gs_key in category:
            expected_organisms = organisms
            break

    if not expected_organisms:
        # Try partial matching
        if "gram_positive" in gs_key and "cocci" in gs_key:
            if "cluster" in gs_key:
                expected_organisms = GRAM_STAIN_MAP["gram_positive_cocci_clusters"]
            elif "chain" in gs_key or "pair" in gs_key:
                expected_organisms = GRAM_STAIN_MAP["gram_positive_cocci_chains"]
            else:
                expected_organisms = (GRAM_STAIN_MAP["gram_positive_cocci_clusters"] +
                                     GRAM_STAIN_MAP["gram_positive_cocci_chains"])
        elif "gram_negative" in gs_key and ("rod" in gs_key or "bacill" in gs_key):
            expected_organisms = GRAM_STAIN_MAP["gram_negative_rods"]
        elif "gram_negative" in gs_key and ("cocci" in gs_key or "diplo" in gs_key):
            expected_organisms = GRAM_STAIN_MAP["gram_negative_diplococci"]
        elif "gram_positive" in gs_key and ("rod" in gs_key or "bacill" in gs_key):
            expected_organisms = GRAM_STAIN_MAP["gram_positive_rods"]
        elif "yeast" in gs_key or "fungal" in gs_key:
            expected_organisms = GRAM_STAIN_MAP["yeast"]

    # Determine empiric therapy guidance
    empiric_guidance = _get_empiric_guidance(gs_key)

    return {
        "gram_stain": gram_stain,
        "expected_organisms": expected_organisms,
        "empiric_guidance": empiric_guidance,
        "num_expected": len(expected_organisms),
    }


def _get_empiric_guidance(gram_stain_key: str) -> Dict[str, Any]:
    """Get empiric antibiotic guidance based on Gram stain."""
    if "gram_positive" in gram_stain_key and "cocci" in gram_stain_key:
        if "cluster" in gram_stain_key:
            return {
                "likely_organisms": "Staphylococcus spp. (S. aureus or CoNS)",
                "empiric_therapy": [
                    "Vancomycin (if MRSA risk factors present)",
                    "Cefazolin or Nafcillin/Oxacillin (if MSSA likely)",
                ],
                "key_differentiation": "Coagulase test, MALDI-TOF",
            }
        else:
            return {
                "likely_organisms": "Streptococcus spp. or Enterococcus spp.",
                "empiric_therapy": [
                    "Ampicillin + Gentamicin (if Enterococcus suspected)",
                    "Penicillin or Ceftriaxone (if Streptococcus suspected)",
                ],
                "key_differentiation": "Catalase test, PYR test, bile esculin",
            }
    elif "gram_negative" in gram_stain_key and "rod" in gram_stain_key:
        return {
            "likely_organisms": "Enterobacteriaceae or Pseudomonas",
            "empiric_therapy": [
                "Ceftriaxone (standard Enterobacteriaceae coverage)",
                "Piperacillin-Tazobactam or Meropenem (if Pseudomonas risk)",
                "Add vancomycin if also covering Gram-positives",
            ],
            "key_differentiation": "Oxidase test, culture morphology",
        }
    elif "yeast" in gram_stain_key:
        return {
            "likely_organisms": "Candida spp.",
            "empiric_therapy": [
                "Echinocandin (Caspofungin, Micafungin, Anidulafungin)",
                "Fluconazole (if low azole resistance risk)",
            ],
            "key_differentiation": "MALDI-TOF, germ tube test, species ID critical",
        }
    else:
        return {
            "likely_organisms": "Various - correlate with culture",
            "empiric_therapy": ["Broad-spectrum coverage pending identification"],
            "key_differentiation": "Await final culture and susceptibilities",
        }


# ─── Antibiotic Escalation Triggers ──────────────────────────────────────────

def assess_escalation_triggers(
    organism: str,
    ttp_hours: float,
    susceptibility: Optional[Dict[str, str]] = None,
    patient_factors: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assess whether antibiotic escalation is warranted.

    Args:
        organism: Identified organism
        ttp_hours: Time to positivity
        susceptibility: Dict of antibiotic -> S/I/R (optional)
        patient_factors: Dict with clinical risk factors (optional)

    Returns:
        Dict with escalation assessment and recommendations
    """
    triggers = []
    escalation_needed = False
    organism_key = organism.lower().replace(" ", "_").replace(".", "")

    # TTP-based triggers
    if ttp_hours < 12:
        triggers.append({
            "trigger": "RAPID_TTP",
            "severity": "HIGH",
            "detail": f"TTP of {ttp_hours:.1f}h indicates high bacterial burden",
        })
        escalation_needed = True

    # Organism-based triggers
    high_risk_organisms = [
        "pseudomonas_aeruginosa", "acinetobacter_baumannii",
        "candida", "staphylococcus_aureus", "enterococcus_faecium",
    ]
    for org in high_risk_organisms:
        if org in organism_key:
            triggers.append({
                "trigger": "HIGH_RISK_ORGANISM",
                "severity": "HIGH",
                "detail": f"{organism} requires targeted therapy",
            })
            escalation_needed = True
            break

    # Resistance-based triggers
    if susceptibility:
        resistant_count = sum(1 for v in susceptibility.values() if v.upper() == "R")
        if resistant_count >= 3:
            triggers.append({
                "trigger": "MULTI_DRUG_RESISTANT",
                "severity": "CRITICAL",
                "detail": f"Resistance to {resistant_count} antibiotics detected",
            })
            escalation_needed = True

        # Check for specific resistance patterns
        if susceptibility.get("ceftriaxone", "").upper() == "R":
            triggers.append({
                "trigger": "ESBL_POSSIBLE",
                "severity": "HIGH",
                "detail": "Ceftriaxone resistance - consider ESBL-producing organism",
            })
            escalation_needed = True

        if susceptibility.get("vancomycin", "").upper() == "R":
            triggers.append({
                "trigger": "VRE_OR_VRSA",
                "severity": "CRITICAL",
                "detail": "Vancomycin resistance detected",
            })
            escalation_needed = True

    # Patient factor-based triggers
    if patient_factors:
        if patient_factors.get("immunocompromised", False):
            triggers.append({
                "trigger": "IMMUNOCOMPROMISED_HOST",
                "severity": "HIGH",
                "detail": "Immunocompromised patient - lower threshold for escalation",
            })
            escalation_needed = True

        if patient_factors.get("neutropenic", False):
            triggers.append({
                "trigger": "NEUTROPENIA",
                "severity": "CRITICAL",
                "detail": "Neutropenic patient - urgent broad-spectrum coverage needed",
            })
            escalation_needed = True

        if patient_factors.get("septic_shock", False):
            triggers.append({
                "trigger": "SEPTIC_SHOCK",
                "severity": "CRITICAL",
                "detail": "Septic shock - immediate broad-spectrum therapy required",
            })
            escalation_needed = True

    return {
        "organism": organism,
        "ttp_hours": ttp_hours,
        "escalation_needed": escalation_needed,
        "trigger_count": len(triggers),
        "triggers": triggers,
        "recommendation": (
            "Escalate antimicrobial therapy immediately"
            if escalation_needed
            else "Current therapy appears adequate; continue monitoring"
        ),
    }


# ─── Repeat Blood Culture Recommendations ────────────────────────────────────

def recommend_repeat_cultures(
    organism: str,
    ttp_hours: float,
    classification: str,
    day_of_positive_culture: int = 1,
    has_endovascular_hardware: bool = False,
    is_staphylococcus_aureus: bool = False,
    is_candida: bool = False,
) -> Dict[str, Any]:
    """Recommend repeat blood cultures based on clinical context.

    Args:
        organism: Identified organism
        ttp_hours: Time to positivity
        classification: Contamination classification
        day_of_positive_culture: Day number of positive culture
        has_endovascular_hardware: Presence of prosthetic valve, pacemaker, etc.
        is_staphylococcus_aureus: Whether organism is S. aureus
        is_candida: Whether organism is Candida spp.

    Returns:
        Dict with repeat culture recommendations
    """
    recommendations = []
    urgency = "ROUTINE"
    repeat_interval_hours = None

    # S. aureus bacteremia - always repeat
    if is_staphylococcus_aureus or "staphylococcus_aureus" in organism.lower():
        recommendations.append({
            "reason": "S. aureus bacteremia requires documentation of clearance",
            "action": "Repeat blood cultures every 24-48h until negative",
            "evidence": "IDSA guidelines for S. aureus bacteremia",
        })
        urgency = "URGENT"
        repeat_interval_hours = 24

        if has_endovascular_hardware:
            recommendations.append({
                "reason": "Endovascular hardware with S. aureus bacteremia",
                "action": "Repeat cultures q24h; minimum 4 weeks therapy; consider hardware removal",
                "evidence": "AHA/IDSA endocarditis guidelines",
            })

    # Candidemia - always repeat
    elif is_candida or "candida" in organism.lower():
        recommendations.append({
            "reason": "Candidemia requires documentation of clearance and ophthalmologic exam",
            "action": "Repeat blood cultures every 24-48h until negative; fundoscopic exam",
            "evidence": "IDSA candidiasis guidelines",
        })
        urgency = "URGENT"
        repeat_interval_hours = 24

    # Likely contaminant
    elif classification == "LIKELY_CONTAMINANT":
        recommendations.append({
            "reason": "Likely contaminant - repeat cultures may help confirm",
            "action": "Consider 1 set of repeat cultures if clinical uncertainty remains",
            "evidence": "Clinical judgment",
        })
        urgency = "LOW"
        repeat_interval_hours = None

    # Gram-negative bacteremia
    elif any(kw in organism.lower() for kw in ["e_coli", "klebsiella", "pseudomonas", "enterobacter"]):
        if day_of_positive_culture <= 1:
            recommendations.append({
                "reason": "Gram-negative bacteremia - document clearance",
                "action": "Repeat blood cultures in 48-72h if clinically indicated",
                "evidence": "Standard practice",
            })
            urgency = "MODERATE"
            repeat_interval_hours = 48

    # Endocarditis concern
    if ttp_hours < 12:
        recommendations.append({
            "reason": "Rapid TTP raises concern for endocarditis",
            "action": "Repeat blood cultures; consider echocardiography",
            "evidence": "Clinical correlation with rapid TTP",
        })
        if urgency in ("ROUTINE", "LOW"):
            urgency = "MODERATE"

    if not recommendations:
        recommendations.append({
            "reason": "Standard follow-up",
            "action": "Repeat cultures only if clinical deterioration or persistent fever",
            "evidence": "Clinical judgment",
        })

    return {
        "organism": organism,
        "urgency": urgency,
        "repeat_interval_hours": repeat_interval_hours,
        "recommendations": recommendations,
        "total_recommendations": len(recommendations),
    }


# ─── Full Blood Culture Analysis ─────────────────────────────────────────────

def analyze_blood_culture(
    organism: str,
    ttp_hours: float,
    gram_stain: Optional[str] = None,
    num_bottles_positive: int = 1,
    num_bottles_total: int = 2,
    susceptibility: Optional[Dict[str, str]] = None,
    patient_factors: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Complete blood culture analysis combining all assessments.

    Args:
        organism: Identified organism
        ttp_hours: Time to positivity in hours
        gram_stain: Gram stain result (optional)
        num_bottles_positive: Number of positive bottles
        num_bottles_total: Total bottles drawn
        susceptibility: Antibiotic susceptibility data (optional)
        patient_factors: Patient clinical factors (optional)

    Returns:
        Comprehensive analysis dict
    """
    result = {
        "organism": organism,
        "ttp_hours": ttp_hours,
        "analyses": {},
    }

    # TTP interpretation
    result["analyses"]["ttp"] = interpret_ttp(ttp_hours)

    # Contamination assessment
    result["analyses"]["contamination"] = assess_contamination(
        organism, ttp_hours, num_bottles_positive, num_bottles_total, gram_stain
    )

    # Gram stain interpretation
    if gram_stain:
        result["analyses"]["gram_stain"] = interpret_gram_stain(gram_stain)

    # Escalation triggers
    result["analyses"]["escalation"] = assess_escalation_triggers(
        organism, ttp_hours, susceptibility, patient_factors
    )

    # Repeat culture recommendations
    is_saureus = "staphylococcus_aureus" in organism.lower() or "s._aureus" in organism.lower()
    is_candida_sp = "candida" in organism.lower()
    result["analyses"]["repeat_cultures"] = recommend_repeat_cultures(
        organism, ttp_hours,
        result["analyses"]["contamination"]["classification"],
        is_staphylococcus_aureus=is_saureus,
        is_candida=is_candida_sp,
        has_endovascular_hardware=(patient_factors or {}).get("endovascular_hardware", False),
    )

    # Overall severity
    severities = []
    for analysis in result["analyses"].values():
        if isinstance(analysis, dict):
            for alert in analysis.get("alerts", []):
                severities.append(alert.get("severity", "INFO"))

    if "CRITICAL" in severities:
        result["overall_severity"] = "CRITICAL"
    elif "WARNING" in severities:
        result["overall_severity"] = "WARNING"
    elif "ADVISORY" in severities:
        result["overall_severity"] = "ADVISORY"
    else:
        result["overall_severity"] = "INFO"

    return result


# ─── CLI ──────────────────────────────────────────────────────────────────────

def build_parser():
    """Build the argument parser."""
    p = argparse.ArgumentParser(
        prog="blood-culture-sentinel",
        description="Blood Culture Early Alert Agent"
    )
    sub = p.add_subparsers(dest="cmd")

    # TTP command
    s_ttp = sub.add_parser("ttp", help="Interpret time-to-positivity")
    s_ttp.add_argument("--hours", type=float, required=True, help="TTP in hours")

    # Contamination command
    s_contam = sub.add_parser("contamination", help="Assess contamination probability")
    s_contam.add_argument("--organism", required=True, help="Organism name")
    s_contam.add_argument("--ttp", type=float, required=True, help="TTP in hours")
    s_contam.add_argument("--positive-bottles", type=int, default=1)
    s_contam.add_argument("--total-bottles", type=int, default=2)

    # Gram stain command
    s_gs = sub.add_parser("gram-stain", help="Interpret Gram stain")
    s_gs.add_argument("--result", required=True, help="Gram stain description")

    # Full analysis command
    s_full = sub.add_parser("analyze", help="Full blood culture analysis")
    s_full.add_argument("--organism", required=True, help="Organism name")
    s_full.add_argument("--ttp", type=float, required=True, help="TTP in hours")
    s_full.add_argument("--gram-stain", help="Gram stain result")
    s_full.add_argument("--positive-bottles", type=int, default=1)
    s_full.add_argument("--total-bottles", type=int, default=2)
    s_full.add_argument("--susceptibility", help="JSON of antibiotic:S/I/R pairs")
    s_full.add_argument("--immunocompromised", action="store_true")
    s_full.add_argument("--neutropenic", action="store_true")

    return p


def main(argv=None):
    """CLI entry point."""
    p = build_parser()
    args = p.parse_args(argv)

    if args.cmd == "ttp":
        result = interpret_ttp(args.hours)
        print(json.dumps(result, indent=2))
        return 0

    elif args.cmd == "contamination":
        result = assess_contamination(
            args.organism, args.ttp, args.positive_bottles, args.total_bottles
        )
        print(json.dumps(result, indent=2))
        return 0

    elif args.cmd == "gram-stain":
        result = interpret_gram_stain(args.result)
        print(json.dumps(result, indent=2))
        return 0

    elif args.cmd == "analyze":
        patient_factors = {}
        if args.immunocompromised:
            patient_factors["immunocompromised"] = True
        if args.neutropenic:
            patient_factors["neutropenic"] = True

        susceptibility = json.loads(args.susceptibility) if args.susceptibility else None

        result = analyze_blood_culture(
            organism=args.organism,
            ttp_hours=args.ttp,
            gram_stain=args.gram_stain,
            num_bottles_positive=args.positive_bottles,
            num_bottles_total=args.total_bottles,
            susceptibility=susceptibility,
            patient_factors=patient_factors if patient_factors else None,
        )
        print(json.dumps(result, indent=2))
        return 0

    else:
        p.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
