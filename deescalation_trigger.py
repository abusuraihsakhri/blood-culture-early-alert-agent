#!/usr/bin/env python3
"""
Antimicrobial De-escalation Trigger for BloodCulture Sentinel.
Analyzes culture and sensitivity results to recommend antimicrobial
de-escalation, step-down therapy, or continuation based on clinical guidelines.
"""

import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class SensitivityResult:
    """Antibiotic susceptibility result."""
    antibiotic: str
    organism: str
    mic_value: Optional[float] = None
    zone_diameter: Optional[float] = None
    interpretation: str = "SUSCEPTIBLE"  # S, I, R
    breakpoint: Optional[float] = None


@dataclass
class DeescalationContext:
    """Clinical context for de-escalation decision."""
    current_antibiotic: str
    current_duration_days: int = 0
    organism_id: str = ""
    ttp_hours: float = 15.0
    is_broad_spectrum: bool = True
    is_contaminant: bool = False
    sensitivity_results: Optional[List[SensitivityResult]] = None
    patient_allergies: Optional[List[str]] = None
    organ_function: Optional[Dict[str, Any]] = None


# Antibiotic spectrum classification
ANTIBIOTIC_SPECTRUM = {
    "broad_spectrum": [
        "piperacillin_tazobactam", "meropenem", "imipenem", "cefepime",
        "vancomycin", "linezolid", "daptomycin", "tigecycline",
    ],
    "narrow_spectrum": [
        "ampicillin", "cefazolin", "ceftriaxone", "ciprofloxacin",
        "levofloxacin", "trimethoprim_sulfamethoxazole", "doxycycline",
        "fluconazole", "amoxicillin_clavulanate",
    ],
}

# De-escalation recommendations by organism
DEESCALATION_MAP = {
    "methicillin_susceptible_staph_aureus": {
        "deescalate_to": "cefazolin",
        "duration_days": 14,
        "reason": "MSSA susceptible to first-generation cephalosporin."
    },
    "escherichia_coli_ceftriaxone_susceptible": {
        "deescalate_to": "ceftriaxone",
        "duration_days": 7,
        "reason": "E. coli susceptible to 3rd-gen cephalosporin."
    },
    "pseudomonas_aeruginosa_ambiguous": {
        "deescalate_to": "ciprofloxacin_or_ceftazidime",
        "duration_days": 10,
        "reason": "Pseudomonas requiring anti-pseudomonal narrow spectrum."
    },
    "enterococcus_faecalis_ampicillin_susceptible": {
        "deescalate_to": "ampicillin",
        "duration_days": 14,
        "reason": "E. faecalis susceptible to ampicillin."
    },
    "streptococcus_pneumoniae_penicillin_susceptible": {
        "deescalate_to": "penicillin_or_amoxicillin",
        "duration_days": 7,
        "reason": "S. pneumoniae susceptible to penicillin."
    },
}


def check_allergy_compatibility(antibiotic: str, allergies: List[str]) -> bool:
    """Check if proposed antibiotic is compatible with patient allergies."""
    allergy_map = {
        "penicillin": ["ampicillin", "amoxicillin", "piperacillin_tazobactam"],
        "cephalosporin": ["cefazolin", "ceftriaxone", "cefepime", "ceftazidime"],
        "sulfonamide": ["trimethoprim_sulfamethoxazole"],
        "fluoroquinolone": ["ciprofloxacin", "levofloxacin"],
    }
    for allergy in allergies:
        allergy_lower = allergy.lower()
        if allergy_lower in allergy_map:
            if antibiotic.lower() in allergy_map[allergy_lower]:
                return False
    return True


def assess_narrow_spectrum_options(sensitivity_results: List[SensitivityResult],
                                    patient_allergies: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Find narrow-spectrum alternatives based on susceptibility."""
    options = []
    patient_allergies = patient_allergies or []

    for sr in sensitivity_results:
        if sr.interpretation == "SUSCEPTIBLE":
            for category, abx_list in ANTIBIOTIC_SPECTRUM.items():
                if category == "narrow_spectrum" and sr.antibiotic.lower().replace(" ", "_") in abx_list:
                    compatible = check_allergy_compatibility(sr.antibiotic, patient_allergies)
                    options.append({
                        "antibiotic": sr.antibiotic,
                        "organism": sr.organism,
                        "interpretation": sr.interpretation,
                        "allergy_compatible": compatible,
                        "mic": sr.mic_value,
                        "zone_diameter": sr.zone_diameter,
                    })

    options.sort(key=lambda x: (not x["allergy_compatible"], x.get("mic") or 0))
    return options


class DeescalationTriggerAgent:
    """Sub-agent for antimicrobial de-escalation decision support."""

    def __init__(self):
        self.agent_name = "DeescalationTriggerAgent"

    def evaluate(self, context: DeescalationContext) -> Dict[str, Any]:
        """Evaluate de-escalation opportunity."""
        alerts = []
        recommendation = ""
        deescalation_possible = False

        if context.is_contaminant:
            return {
                "alerts": [{
                    "type": "CONTAMINATION_NO_THERAPY",
                    "severity": "ADVISORY",
                    "message": "Organism identified as probable contamination. Consider discontinuing antibiotics.",
                    "recommendation": "If patient clinically stable, discontinue antibiotics and observe.",
                }],
                "deescalation_possible": False,
                "recommendation": "Discontinue antibiotics; contamination likely.",
                "broad_to_narrow_candidates": [],
            }

        if context.sensitivity_results:
            narrow_options = assess_narrow_spectrum_options(
                context.sensitivity_results, context.patient_allergies
            )
            compatible_options = [o for o in narrow_options if o["allergy_compatible"]]

            if compatible_options and context.is_broad_spectrum:
                deescalation_possible = True
                best_option = compatible_options[0]

                alerts.append({
                    "type": "DEESCALATION_OPPORTUNITY",
                    "severity": "ADVISORY",
                    "message": f"Narrow-spectrum option available: {best_option['antibiotic']} "
                               f"(MIC: {best_option.get('mic', 'N/A')}).",
                    "recommendation": f"Consider de-escalating from broad-spectrum to {best_option['antibiotic']}."
                })

                deescalation_key = f"{context.organism_id}_{best_option['antibiotic'].lower().replace(' ', '_')}"
                if deescalation_key in DEESCALATION_MAP:
                    rec = DEESCALATION_MAP[deescalation_key]
                    recommendation = (f"De-escalate to {rec['deescalate_to']} for {rec['duration_days']} days. "
                                      f"{rec['reason']}")

        if context.current_duration_days > 7 and context.ttp_hours > 18.0:
            alerts.append({
                "type": "PROLONGED_THERAPY_REVIEW",
                "severity": "ADVISORY",
                "message": f"Current therapy duration: {context.current_duration_days} days "
                           f"with prolonged TTP ({context.ttp_hours:.1f}h).",
                "recommendation": "Review necessity of continued therapy. Consider oral step-down if clinically stable."
            })

        if not context.is_broad_spectrum and deescalation_possible is False:
            alerts.append({
                "type": "ALREADY_NARROW_SPECTRUM",
                "severity": "INFO",
                "message": "Patient already on narrow-spectrum agent. No de-escalation needed.",
                "recommendation": "Continue current regimen."
            })

        return {
            "alerts": alerts,
            "deescalation_possible": deescalation_possible,
            "recommendation": recommendation,
            "broad_to_narrow_candidates": [o for o in (narrow_options if context.sensitivity_results else [])
                                           if o["allergy_compatible"]],
        }


def create_deescalation_api_routes(app, coordinator):
    """Add de-escalation endpoints to FastAPI app."""
    try:
        from pydantic import BaseModel

        class DeescalationRequest(BaseModel):
            current_antibiotic: str = "piperacillin_tazobactam"
            current_duration_days: int = 3
            organism_id: str = ""
            ttp_hours: float = 15.0
            is_broad_spectrum: bool = True
            is_contaminant: bool = False
            antibiotic: str = ""
            susceptibility: str = "SUSCEPTIBLE"
            mic_value: Optional[float] = None
            allergies: List[str] = []

        @app.post("/api/deescalation")
        def api_deescalation(req: DeescalationRequest):
            agent = DeescalationTriggerAgent()
            context = DeescalationContext(
                current_antibiotic=req.current_antibiotic,
                current_duration_days=req.current_duration_days,
                organism_id=req.organism_id,
                ttp_hours=req.ttp_hours,
                is_broad_spectrum=req.is_broad_spectrum,
                is_contaminant=req.is_contaminant,
                sensitivity_results=[
                    SensitivityResult(
                        antibiotic=req.antibiotic,
                        organism=req.organism_id,
                        mic_value=req.mic_value,
                        interpretation=req.susceptibility,
                    )
                ] if req.antibiotic else None,
                patient_allergies=req.allergies,
            )
            return agent.evaluate(context)

        @app.get("/api/deescalation/spectrum")
        def antibiotic_spectrum():
            return ANTIBIOTIC_SPECTRUM
    except ImportError:
        pass
