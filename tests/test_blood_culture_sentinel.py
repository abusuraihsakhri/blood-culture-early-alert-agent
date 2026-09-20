"""Tests for Blood Culture Early Alert Agent."""
import json
import pytest
from blood_culture_sentinel import (
    interpret_ttp,
    assess_contamination,
    interpret_gram_stain,
    assess_escalation_triggers,
    recommend_repeat_cultures,
    analyze_blood_culture,
    COMMON_CONTAMINANTS,
    TRUE_PATHOGENS,
    main,
)


# ─── TTP Interpretation Tests ────────────────────────────────────────────────

def test_ttp_rapid_growth():
    result = interpret_ttp(8.0)
    assert result["category"] == "RAPID_GROWTH"
    assert result["clinical_significance"] == "HIGH"
    assert any("endocarditis" in c.lower() for c in result["concerns"])


def test_ttp_normal_growth():
    result = interpret_ttp(24.0)
    assert result["category"] == "NORMAL_GROWTH"
    assert result["clinical_significance"] == "MODERATE"


def test_ttp_slow_growth():
    result = interpret_ttp(48.0)
    assert result["category"] == "SLOW_GROWTH"
    assert any("contaminant" in c.lower() for c in result["concerns"])


def test_ttp_boundary_12_hours():
    result = interpret_ttp(12.0)
    assert result["category"] == "NORMAL_GROWTH"


def test_ttp_boundary_36_hours():
    result = interpret_ttp(36.0)
    assert result["category"] == "NORMAL_GROWTH"


def test_ttp_negative():
    result = interpret_ttp(-5.0)
    assert "error" in result


def test_ttp_very_rapid():
    result = interpret_ttp(4.0)
    assert result["category"] == "RAPID_GROWTH"
    assert result["clinical_significance"] == "HIGH"


# ─── Contamination Assessment Tests ──────────────────────────────────────────

def test_contamination_cons():
    result = assess_contamination("coagulase_negative_staphylococcus", 22.0,
                                   num_bottles_positive=1, num_bottles_total=2)
    assert result["classification"] == "LIKELY_CONTAMINANT"
    assert result["is_known_contaminant"] is True


def test_contamination_saureus():
    result = assess_contamination("staphylococcus_aureus", 10.0,
                                   num_bottles_positive=2, num_bottles_total=2)
    assert result["classification"] == "LIKELY_TRUE_PATHOGEN"
    assert result["is_known_pathogen"] is True


def test_contamination_ecoli():
    result = assess_contamination("escherichia_coli", 14.0,
                                   num_bottles_positive=2, num_bottles_total=2)
    assert result["classification"] == "LIKELY_TRUE_PATHOGEN"


def test_contamination_rapid_ttp_pathogen():
    """Rapid TTP with known pathogen should be classified as true pathogen."""
    result = assess_contamination("pseudomonas_aeruginosa", 6.0,
                                   num_bottles_positive=2, num_bottles_total=2)
    assert result["classification"] == "LIKELY_TRUE_PATHOGEN"


def test_contamination_single_bottle():
    """Single positive bottle increases contamination probability."""
    result = assess_contamination("coagulase_negative_staphylococcus", 24.0,
                                   num_bottles_positive=1, num_bottles_total=2)
    assert result["contamination_probability"] > 0.5


def test_contamination_all_bottles_positive():
    """All bottles positive decreases contamination probability."""
    result = assess_contamination("coagulase_negative_staphylococcus", 20.0,
                                   num_bottles_positive=2, num_bottles_total=2)
    assert result["contamination_probability"] < 0.85


def test_contamination_has_alerts():
    result = assess_contamination("staphylococcus_aureus", 8.0)
    assert len(result["alerts"]) > 0


# ─── Gram Stain Interpretation Tests ─────────────────────────────────────────

def test_gram_stain_gp_clusters():
    result = interpret_gram_stain("gram_positive_cocci_clusters")
    assert "staphylococcus_aureus" in result["expected_organisms"]
    assert result["num_expected"] > 0


def test_gram_stain_gp_chains():
    result = interpret_gram_stain("gram_positive_cocci_chains")
    assert "streptococcus_pneumoniae" in result["expected_organisms"]


def test_gram_stain_gn_rods():
    result = interpret_gram_stain("gram_negative_rods")
    assert "escherichia_coli" in result["expected_organisms"]
    assert "pseudomonas_aeruginosa" in result["expected_organisms"]


def test_gram_stain_yeast():
    result = interpret_gram_stain("yeast")
    assert "candida_albicans" in result["expected_organisms"]


def test_gram_stain_partial_match():
    result = interpret_gram_stain("gram_positive cocci in clusters")
    assert result["num_expected"] > 0


def test_gram_stain_empiric_guidance():
    result = interpret_gram_stain("gram_negative_rods")
    assert "empiric_guidance" in result
    assert len(result["empiric_guidance"]["empiric_therapy"]) > 0


# ─── Escalation Trigger Tests ────────────────────────────────────────────────

def test_escalation_rapid_ttp():
    result = assess_escalation_triggers("escherichia_coli", 8.0)
    assert result["escalation_needed"] is True
    assert any(t["trigger"] == "RAPID_TTP" for t in result["triggers"])


def test_escalation_high_risk_organism():
    result = assess_escalation_triggers("pseudomonas_aeruginosa", 24.0)
    assert result["escalation_needed"] is True
    assert any(t["trigger"] == "HIGH_RISK_ORGANISM" for t in result["triggers"])


def test_escalation_mdr():
    result = assess_escalation_triggers("escherichia_coli", 24.0,
        susceptibility={"ceftriaxone": "R", "ciprofloxacin": "R", "gentamicin": "R"})
    assert result["escalation_needed"] is True
    assert any(t["trigger"] == "MULTI_DRUG_RESISTANT" for t in result["triggers"])


def test_escalation_neutropenic():
    result = assess_escalation_triggers("escherichia_coli", 24.0,
        patient_factors={"neutropenic": True})
    assert result["escalation_needed"] is True
    assert any(t["trigger"] == "NEUTROPENIA" for t in result["triggers"])


def test_escalation_not_needed():
    result = assess_escalation_triggers("escherichia_coli", 24.0)
    assert result["escalation_needed"] is False


# ─── Repeat Culture Recommendation Tests ─────────────────────────────────────

def test_repeat_cultures_saureus():
    result = recommend_repeat_cultures("staphylococcus_aureus", 10.0,
                                        "LIKELY_TRUE_PATHOGEN", is_staphylococcus_aureus=True)
    assert result["urgency"] == "URGENT"
    assert result["repeat_interval_hours"] == 24


def test_repeat_cultures_candida():
    result = recommend_repeat_cultures("candida_albicans", 20.0,
                                        "LIKELY_TRUE_PATHOGEN", is_candida=True)
    assert result["urgency"] == "URGENT"


def test_repeat_cultures_contaminant():
    result = recommend_repeat_cultures("coagulase_negative_staphylococcus", 40.0,
                                        "LIKELY_CONTAMINANT")
    assert result["urgency"] == "LOW"


def test_repeat_cultures_rapid_ttp():
    result = recommend_repeat_cultures("escherichia_coli", 8.0,
                                        "LIKELY_TRUE_PATHOGEN")
    assert any("endocarditis" in r["reason"].lower() for r in result["recommendations"])


# ─── Full Analysis Tests ─────────────────────────────────────────────────────

def test_full_analysis_saureus():
    result = analyze_blood_culture(
        organism="staphylococcus_aureus",
        ttp_hours=6.0,
        gram_stain="gram_positive_cocci_clusters",
        num_bottles_positive=2,
        num_bottles_total=2,
    )
    assert result["overall_severity"] in ("CRITICAL", "WARNING")
    assert "ttp" in result["analyses"]
    assert "contamination" in result["analyses"]
    assert "escalation" in result["analyses"]


def test_full_analysis_likely_contaminant():
    result = analyze_blood_culture(
        organism="coagulase_negative_staphylococcus",
        ttp_hours=40.0,
        num_bottles_positive=1,
        num_bottles_total=2,
    )
    assert result["analyses"]["contamination"]["classification"] == "LIKELY_CONTAMINANT"


# ─── CLI Tests ───────────────────────────────────────────────────────────────

def test_cli_ttp():
    assert main(["ttp", "--hours", "8.0"]) == 0


def test_cli_contamination():
    assert main(["contamination", "--organism", "staphylococcus_aureus", "--ttp", "10.0"]) == 0


def test_cli_gram_stain():
    assert main(["gram-stain", "--result", "gram_negative_rods"]) == 0


def test_cli_analyze():
    assert main(["analyze", "--organism", "escherichia_coli", "--ttp", "14.0"]) == 0


def test_cli_help():
    with pytest.raises(SystemExit) as exc:
        main(["ttp", "--help"])
    assert exc.value.code == 0


def test_cli_batch(tmp_path):
    out_file = str(tmp_path / "batch_out.csv")
    ret = main(["batch", "-i", "sample.csv", "-o", out_file])
    assert ret == 0
    with open(out_file, "r", encoding="utf-8") as f:
        content = f.read()
        assert "computed_urgency_escalation" in content
        assert "critical_panic_call_window_minutes" in content



def test_gram_stain_common_abbreviation_gnb():
    result = interpret_gram_stain("GNB")
    assert result["normalised_gram_stain"] == "gram_negative_rods"
    assert "escherichia_coli" in result["expected_organisms"]


def test_invalid_bottle_counts_are_rejected():
    with pytest.raises(ValueError):
        assess_contamination(
            "staphylococcus_epidermidis",
            24.0,
            num_bottles_positive=3,
            num_bottles_total=2,
        )


def test_batch_urgent_rows_use_30_minute_window(tmp_path):
    import csv

    out_file = str(tmp_path / "batch_out.csv")
    assert main(["batch", "-i", "sample.csv", "-o", out_file]) == 0

    with open(out_file, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    target = next(row for row in rows if row["bottle_barcode"] == "BC-773419-A")
    assert target["computed_urgency_escalation"] == "URGENT"
    assert target["critical_panic_call_window_minutes"] == "30"


def test_batch_does_not_silently_impute_missing_ttp(tmp_path):
    input_file = tmp_path / "missing_ttp.csv"
    input_file.write_text(
        "bottle_barcode,gram_stain_morphology\nBC-1,GNB\n",
        encoding="utf-8",
    )
    out_file = tmp_path / "out.csv"
    assert main(["batch", "-i", str(input_file), "-o", str(out_file)]) == 2
    assert not out_file.exists()
