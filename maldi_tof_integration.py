#!/usr/bin/env python3
"""
MALDI-TOF Integration Layer for BloodCulture Sentinel.
Integrates MALDI-TOF mass spectrometry identification data with TTP analysis
for rapid organism identification and contamination probability scoring.
"""

import datetime
import uuid
from typing import Dict, Any, List, Optional


# Known contaminant organisms in blood cultures
KNOWN_CONTAMINANTS = {
    "coagulase_negative_staph": {
        "organisms": ["staphylococcus_epidermidis", "staphylococcus_haemolyticus", "staphylococcus_capitis",
                       "staphylococcus_hominis", "staphylococcus_warneri", "staphylococcus_saccharolyticus"],
        "contamination_rate": 0.85,
        "confidence_threshold": 0.95,
    },
    "diphtheroids": {
        "organisms": ["corynebacterium_striatum", "corynebacterium_jeikeium", "corynebacterium_accolens"],
        "contamination_rate": 0.70,
        "confidence_threshold": 0.90,
    },
    "micrococci": {
        "organisms": ["micrococcus_luteus", "micrococcus_lysodeikticus"],
        "contamination_rate": 0.60,
        "confidence_threshold": 0.85,
    },
    "viridans_streptococci": {
        "organisms": ["streptococcus_mitis", "streptococcus_oralis", "streptococcus_sanguinis",
                       "streptococcus_gordonii", "streptococcus_parasanguinis"],
        "contamination_rate": 0.40,
        "confidence_threshold": 0.90,
    },
    "gram_positive_rod": {
        "organisms": ["bacillus_cereus", "bacillus_subtilis", "bacillus_spp"],
        "contamination_rate": 0.55,
        "confidence_threshold": 0.88,
    },
}

# True pathogen organisms
TRUE_PATHOGENS = {
    "staphylococcus_aureus": {"severity": "HIGH", "sepsis_risk": 0.75},
    "escherichia_coli": {"severity": "HIGH", "sepsis_risk": 0.80},
    "klebsiella_pneumoniae": {"severity": "HIGH", "sepsis_risk": 0.85},
    "pseudomonas_aeruginosa": {"severity": "CRITICAL", "sepsis_risk": 0.90},
    "enterococcus_faecium": {"severity": "HIGH", "sepsis_risk": 0.70},
    "streptococcus_pneumoniae": {"severity": "HIGH", "sepsis_risk": 0.75},
    "candida_albicans": {"severity": "CRITICAL", "sepsis_risk": 0.90},
    "candida_glabrata": {"severity": "CRITICAL", "sepsis_risk": 0.85},
    "methicillin_resistant_staph_aureus": {"severity": "CRITICAL", "sepsis_risk": 0.85},
}


class MaldiTofResult:
    """Represents a MALDI-TOF identification result."""
    def __init__(self, organism_id: str, confidence: float, species: str, genus: str,
                 score: float, metadata: Optional[Dict[str, Any]] = None):
        self.organism_id = organism_id
        self.confidence = confidence
        self.species = species
        self.genus = genus
        self.score = score
        self.metadata = metadata or {}

    def is_contaminant(self) -> bool:
        """Check if identified organism is a known contaminant."""
        for category, info in KNOWN_CONTAMINANTS.items():
            if self.organism_id in info["organisms"] or self.species in info["organisms"]:
                return self.confidence >= info["confidence_threshold"]
        return False

    def is_true_pathogen(self) -> bool:
        """Check if identified organism is a known true pathogen."""
        return self.organism_id in TRUE_PATHOGENS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "organism_id": self.organism_id,
            "species": self.species,
            "genus": self.genus,
            "confidence": self.confidence,
            "score": self.score,
            "is_contaminant": self.is_contaminant(),
            "is_pathogen": self.is_true_pathogen(),
            "metadata": self.metadata,
        }


class MaldiTofAgent:
    """Sub-agent for MALDI-TOF identification integration with TTP analysis."""

    def __init__(self):
        self.agent_name = "MaldiTofAgent"

    def evaluate(self, maldi_result: MaldiTofResult, ttp_hours: float,
                 bottle_type: str = "peripheral") -> Dict[str, Any]:
        """Evaluate MALDI-TOF result in context of TTP and bottle type."""
        alerts = []
        contamination_adjustment = 0.0
        pathogen_boost = 0.0
        recommendation = ""

        is_contaminant = maldi_result.is_contaminant()
        is_pathogen = maldi_result.is_true_pathogen()

        if is_contaminant and ttp_hours > 18.0:
            contamination_adjustment = 0.30
            alerts.append({
                "type": "CONTAMINANT_TTP_CONCORDANT",
                "severity": "ADVISORY",
                "message": f"Organism {maldi_result.species} (confidence={maldi_result.confidence:.2f}) "
                           f"with TTP {ttp_hours:.1f}h consistent with contamination.",
                "recommendation": "Consider reculture from new peripheral sites before initiating therapy."
            })
        elif is_contaminant and ttp_hours < 8.0:
            contamination_adjustment = -0.15
            alerts.append({
                "type": "CONTAMINANT_UNUSUALLY_FAST",
                "severity": "WARNING",
                "message": f"Contaminant organism {maldi_result.species} with unusually fast TTP ({ttp_hours:.1f}h). "
                           f"May indicate high inoculum or true polymicrobial infection.",
                "recommendation": "Investigate source; consider imaging and repeat cultures."
            })

        if is_pathogen:
            pathogen_info = TRUE_PATHOGENS[maldi_result.organism_id]
            pathogen_boost = pathogen_info["sepsis_risk"] * (maldi_result.confidence / 1.0)
            alerts.append({
                "type": "TRUE_PATHOGEN_IDENTIFIED",
                "severity": pathogen_info["severity"],
                "message": f"Confirmed pathogen: {maldi_result.species} "
                           f"(sepsis risk factor: {pathogen_info['sepsis_risk']:.2f}).",
                "recommendation": f"Initiate targeted antimicrobial therapy per {pathogen_info['severity']} severity protocol."
            })

        if bottle_type == "central" and is_contaminant:
            contamination_adjustment += 0.15
            alerts.append({
                "type": "CENTRAL_BOTTLE_CONTAMINANT",
                "severity": "WARNING",
                "message": "Contaminant organism in central line blood culture requires careful evaluation.",
                "recommendation": "Assess catheter site for infection; consider catheter removal if clinical suspicion."
            })

        return {
            "alerts": alerts,
            "contamination_adjustment": contamination_adjustment,
            "pathogen_boost": pathogen_boost,
            "organism_classification": "CONTAMINANT" if is_contaminant else ("PATHOGEN" if is_pathogen else "UNCERTAIN"),
            "maldi_score": maldi_result.score,
            "confidence": maldi_result.confidence,
        }


def create_maldi_tof_api_routes(app, coordinator):
    """Add MALDI-TOF endpoints to FastAPI app."""
    try:
        from pydantic import BaseModel

        class MaldiTofRequest(BaseModel):
            organism_id: str
            species: str
            genus: str = ""
            confidence: float = 0.95
            score: float = 2.0
            ttp_hours: float = 15.0
            bottle_type: str = "peripheral"

        @app.post("/api/maldi-tof")
        def api_maldi_tof(req: MaldiTofRequest):
            agent = MaldiTofAgent()
            result = MaldiTofResult(
                organism_id=req.organism_id,
                confidence=req.confidence,
                species=req.species,
                genus=req.genus,
                score=req.score,
            )
            return agent.evaluate(result, ttp_hours=req.ttp_hours, bottle_type=req.bottle_type)

        @app.get("/api/maldi-tof/reference")
        def maldi_tof_reference():
            return {
                "contaminants": {k: v for k, v in KNOWN_CONTAMINANTS.items()},
                "pathogens": {k: v for k, v in TRUE_PATHOGENS.items()},
            }
    except ImportError:
        pass
