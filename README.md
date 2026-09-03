# Blood Culture Early Alert Agent (`blood-culture-early-alert-agent`)

> **Clinical Domain:** Diagnostic Microbiology, Sepsis-3 Early Intervention & Antimicrobial Stewardship  
> **Reference Guidelines:** CLSI M100 / EUCAST 2024 / IDSA Sepsis Management / CAP Laboratory Accreditation Standards

---

## 📖 Clinical Overview

The **Blood Culture Early Alert Agent** is an automated clinical microbiology decision-support system designed to minimize time-to-effective-antimicrobial-therapy and prevent unnecessary exposure to broad-spectrum antibiotics. 

Bloodstream infections (BSIs) represent medical emergencies where each hour of delayed appropriate antimicrobial administration is associated with a measurable increase in mortality under **Sepsis-3 guidelines** (an ~7.6% decrease in survival per hour of delay in septic shock). Conversely, 20–50% of positive blood cultures represent dermal contaminants (e.g., coagulase-negative Staphylococci, *Cutibacterium acnes*, *Corynebacterium* species), leading to unnecessary vancomycin exposure, acute kidney injury risk, prolonged hospitalizations, and escalated healthcare expenditures.

This agent integrates continuous blood culture incubator monitoring kinetics with Gram stain morphology to deliver:
1. **Critical Value Panic Call Escalation** within the mandatory $\le 30$-minute accreditation window.
2. **Time-to-Positivity (TTP)** interpretation correlated with bacterial burden and catheter-related bloodstream infections (CRBSI).
3. **Contamination vs. True Pathogen Arbiter** computing probabilistic likelihood based on bottle positivity ratio, TTP, and organism classification.
4. **Early Targeted Empiric Antibiotic Guidance** tailored specifically to preliminary Gram stain morphology before full MALDI-TOF or phenotypic susceptibility profiles are finalized.

---

## 🧬 Clinical Microbiology & Algorithmic Formulations

### 1. Gram Stain Morphology Classification & Targeted Empiric Selection

Upon continuous monitoring detection of microbial growth (via colorimetric or fluorometric $\text{CO}_2$ sensors), an immediate Gram stain smear is prepared and interpreted:

| Gram Stain Morphology | Differential / Likely Pathogens | Initial Targeted Empiric Regimen | Escalation / Stewardship Advisory |
|:---|:---|:---|:---|
| **GPC in clusters** | *Staphylococcus aureus* (MSSA/MRSA), CoNS (*S. epidermidis*) | **Vancomycin** (15–20 mg/kg IV q8–12h with AUC/MIC monitoring) or **Cefazolin** (2g IV q8h if low MRSA risk) | Evaluate TTP and bottle count; high risk of endocarditis/hardware seeding if *S. aureus*. |
| **GPC in pairs/chains** | *Streptococcus pneumoniae*, *Streptococcus pyogenes*, *Enterococcus faecalis / faecium* | **Ampicillin** (2g IV q4h) + **Ceftriaxone** (2g IV q12h) or Vancomycin if enterococcal ampicillin resistance suspected | Correlate with urinary/biliary/GI focus; evaluate for endocarditis if persistent. |
| **GNB (Gram-negative bacilli)** | *Escherichia coli*, *Klebsiella pneumoniae*, *Pseudomonas aeruginosa*, *Enterobacter cloacae* | **Cefepime** (2g IV q8h) or **Piperacillin-Tazobactam** (4.5g IV q6h) $\pm$ Aminoglycoside if septic shock | Severe sepsis alert; check history for ESBL or carbapenem-resistant Enterobacterales (CRE). |
| **GNC (Gram-negative cocci / diplococci)** | *Neisseria meningitidis*, *Moraxella catarrhalis* | **Ceftriaxone** (2g IV q12h) | **STAT Emergency**: Immediate droplet isolation precautions; post-exposure prophylaxis triage. |
| **Budding yeast / pseudohyphae** | *Candida albicans*, *Candida glabrata*, *Candida auris*, *Cryptococcus* | **Echinocandin** (Micafungin 100 mg IV q24h or Caspofungin 70 mg loading then 50 mg daily) | Mandatory central line removal, dilated ophthalmology fundoscopic examination, repeat cultures q24–48h. |

---

### 2. Time-to-Positivity (TTP) Interpretation & Sepsis-3 Kinetics

Time-to-positivity is defined as the elapsed time from incubation commencement in an automated continuous-monitoring system to the instrument threshold detection flag:

$$\text{TTP} = t_{\text{flag}} - t_{\text{incubation\_start}}$$

* **Rapid Growth ($\text{TTP} < 12.0 \text{ hours}$):** Strongly correlates with high initial bacterial load ($\ge 10^3 \text{ CFU/mL}$), septic shock, endovascular source, or virulent pathogens (*S. aureus*, *E. coli*). Triggers **STAT** escalation.
* **Normal Growth ($12.0 \le \text{TTP} \le 36.0 \text{ hours}$):** Typical trajectory for standard bacteremic episodes.
* **Slow Growth ($\text{TTP} > 36.0 \text{ hours}$):** Increased likelihood of indolent contaminant flora (e.g., *Cutibacterium*, *Corynebacterium*) or fastidious organisms under prior antibiotic suppression.

---

### 3. Contamination Probability Index

The agent computes the contamination probability $P(\text{Contam})$ combining prior organism distribution, TTP kinetics, and bottle positivity ratio:

$$P(\text{Contam}) = \text{clip}\left(P_{\text{base}} + \Delta_{\text{TTP}} + \Delta_{\text{Bottles}},\, 0.0,\, 1.0\right)$$

Where:
* $P_{\text{base}} = 0.85$ for classic contaminants (CoNS, *Corynebacterium*), $0.05$ for virulent pathogens (*S. aureus*, *P. aeruginosa*, Enterobacteriaceae), and $0.50$ for indeterminate species.
* $\Delta_{\text{TTP}} = +0.15$ if $\text{TTP} > 36\text{h}$ (slow growth favors contamination); $\Delta_{\text{TTP}} = -0.20$ if $\text{TTP} < 12\text{h}$ (rapid growth favors true bacteremia).
* $\Delta_{\text{Bottles}} = -0.25$ if $\frac{N_{\text{pos}}}{N_{\text{total}}} = 1.0$ ($N_{\text{total}} \ge 2$ sets); $\Delta_{\text{Bottles}} = +0.15$ if $\frac{N_{\text{pos}}}{N_{\text{total}}} \le 0.5$.

---

### 4. Critical Value Escalation & Panic Call Window ($\le 30$ min)

In compliance with College of American Pathologists (CAP) and CLSI laboratory standards, critical positive blood culture results require documented closed-loop communication:
* **STAT Level (Panic call window $\le 30$ minutes):** Rapid TTP ($<12\text{h}$), Gram-negative bacilli, budding yeast, Gram-negative diplococci, or patients in septic shock / neutropenia.
* **Urgent Level (Panic call window $\le 30$ minutes):** GPC in clusters/chains with standard growth kinetics ($12\text{h} \le \text{TTP} \le 24\text{h}$).
* **Routine Level (Call window $\le 60$ minutes):** Single-bottle CoNS or diphtheroids with delayed growth ($\text{TTP} > 36\text{h}$).

---

## 💻 CLI Quickstart & Batch Processing

The command-line interface provides both interactive analysis subcommands and high-throughput batch evaluation.

### CLI Syntax & Commands

```bash
# View available commands
python cli.py --help

# 1. Batch process blood culture alerts from CSV
python cli.py batch -i sample.csv -o alert_results.csv

# 2. Interpret Time-to-Positivity
python cli.py ttp --hours 9.5

# 3. Assess Contamination Likelihood
python cli.py contamination --organism "staphylococcus_epidermidis" --ttp 38.0 --positive-bottles 1 --total-bottles 2

# 4. Interpret Gram Stain Morphology
python cli.py gram-stain --result "gram_negative_rods"

# 5. Full End-to-End Culture Analysis
python cli.py analyze --organism "staphylococcus_aureus" --ttp 8.5 --gram-stain "gram_positive_cocci_clusters" --positive-bottles 2 --total-bottles 2
```

### Batch Input CSV Format (`sample.csv`)

```csv
bottle_barcode,patient_id,gram_stain_morphology,time_to_flag_positive_hours,critical_alert_escalation_level,empiric_antibiotic_coverage_advisory
BC-882910-A,PT-10492,GPC in clusters,11.2,STAT,"Vancomycin 15-20 mg/kg IV q8-12h; consider Cefazolin/Nafcillin pending PBP2a/mecA"
BC-940212-A,PT-22819,GNB,8.4,STAT,"Cefepime 2g IV q8h or Piperacillin-Tazobactam 4.5g IV q6h; evaluate for septic shock"
BC-773419-A,PT-33041,GPC in pairs/chains,14.0,Urgent,"Ampicillin 2g IV q4h + Ceftriaxone 2g IV q12h"
BC-619283-A,PT-44810,budding yeast,22.5,STAT,"Echinocandin (Micafungin 100mg IV q24h); remove central venous catheter"
BC-552109-A,PT-55201,GNC,10.0,STAT,"Ceftriaxone 2g IV q12h; droplet precautions"
BC-441092-A,PT-67123,GPC in clusters,44.8,Routine,"Assess CoNS contamination vs line infection; obtain repeat blood cultures"
```

---

## 🐍 Python Quickstart

Use the core analytical routines directly within your Python clinical workflows:

```python
from blood_culture_sentinel import (
    interpret_ttp,
    assess_contamination,
    interpret_gram_stain,
    assess_escalation_triggers,
    recommend_repeat_cultures,
    analyze_blood_culture,
)

# 1. Evaluate Gram stain morphology and targeted empiric coverage
gram_eval = interpret_gram_stain("gram_positive_cocci_clusters")
print("Expected organisms:", gram_eval["expected_organisms"])
print("Empiric guidance:", gram_eval["empiric_guidance"]["empiric_therapy"])

# 2. Interpret Time-to-Positivity kinetics
ttp_eval = interpret_ttp(8.5)
print("TTP Category:", ttp_eval["category"])
print("Clinical Concerns:", ttp_eval["concerns"])

# 3. Differentiate True Pathogen vs. Contaminant
contam_eval = assess_contamination(
    organism="coagulase_negative_staphylococcus",
    ttp_hours=42.0,
    num_bottles_positive=1,
    num_bottles_total=2,
)
print("Classification:", contam_eval["classification"])  # LIKELY_CONTAMINANT
print("Contamination Probability:", contam_eval["contamination_probability"])

# 4. Perform comprehensive culture appraisal
full_report = analyze_blood_culture(
    organism="escherichia_coli",
    ttp_hours=7.5,
    gram_stain="gram_negative_rods",
    num_bottles_positive=2,
    num_bottles_total=2,
    patient_factors={"immunocompromised": False, "septic_shock": True},
)
print("Overall Severity:", full_report["overall_severity"])  # CRITICAL
print("Repeat Culture Protocol:", full_report["analyses"]["repeat_cultures"]["urgency"])
```

---

## 🧪 Testing & Verification

Run the comprehensive pytest suite:

```bash
python -m pytest -p no:zarr
```

Verify CLI batch execution:

```bash
python cli.py batch -i sample.csv -o out_smoke.csv
```

---

## 📜 Standards & Citations

* **CLSI M100-Ed34 (2024):** Performance Standards for Antimicrobial Susceptibility Testing.
* **EUCAST Breakpoint Tables v14.0 (2024):** Clinical breakpoints for bacteria and fungi.
* **Singer M, et al. (Sepsis-3):** The Third International Consensus Definitions for Sepsis and Septic Shock. *JAMA*, 2016.
* **Clinical and Laboratory Standards Institute (CLSI M47):** Principles and Procedures for Blood Cultures.
