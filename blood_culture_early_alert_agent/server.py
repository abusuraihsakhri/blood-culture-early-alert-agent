"""Optional FastAPI interface for the blood-culture analysis utilities."""

from __future__ import annotations

from typing import Any, Dict, Optional

from blood_culture_sentinel import analyze_blood_culture


def create_app():
    """Create the FastAPI application.

    FastAPI is an optional dependency. Install the project with the "server"
    extra before calling this function.
    """
    try:
        from fastapi import FastAPI
        from pydantic import BaseModel, Field
    except ImportError:
        return None

    app = FastAPI(
        title="Blood Culture Early Alert Agent",
        description=(
            "Research/education API for time-to-positivity and contamination "
            "heuristics. Outputs are not validated clinical predictions."
        ),
        version="2.1.0",
    )

    class AnalysisRequest(BaseModel):
        organism: str
        ttp_hours: float = Field(ge=0)
        gram_stain: Optional[str] = None
        positive_bottles: int = Field(default=1, ge=0)
        total_bottles: int = Field(default=2, ge=1)
        susceptibility: Optional[Dict[str, str]] = None
        patient_factors: Dict[str, Any] = Field(default_factory=dict)

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "blood-culture-early-alert-agent",
            "version": "2.1.0",
        }

    def _analyse(req: AnalysisRequest):
        return analyze_blood_culture(
            organism=req.organism,
            ttp_hours=req.ttp_hours,
            gram_stain=req.gram_stain,
            num_bottles_positive=req.positive_bottles,
            num_bottles_total=req.total_bottles,
            susceptibility=req.susceptibility,
            patient_factors=req.patient_factors or None,
        )

    @app.post("/api/analyze")
    def api_analyze(req: AnalysisRequest):
        return _analyse(req)

    @app.post("/api/audit")
    def api_audit_compatibility(req: AnalysisRequest):
        """Compatibility alias for older integrations."""
        return _analyse(req)

    return app
