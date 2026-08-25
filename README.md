# Blood Culture Early Alert Agent

Clinical microbiology tool for blood culture interpretation including time-to-positivity analysis, contamination assessment, Gram stain interpretation, and antibiotic escalation guidance.

## Features

- **Time-to-Positivity (TTP) Interpretation**:
  - Rapid growth (<12h): High bacterial burden, consider endocarditis
  - Normal growth (12-36h): Standard bacteremia
  - Slow growth (>36h): Possible contaminant or low-grade bacteremia
- **Contamination Assessment**:
  - Known contaminant database (CoNS, Corynebacterium, Propionibacterium, Bacillus, Micrococcus)
  - True pathogen database (S. aureus, E. coli, Klebsiella, Pseudomonas, Enterococcus, Candida)
  - Multi-factor probability calculation (organism, TTP, bottle positivity)
- **Gram Stain Interpretation**: Expected organisms and empiric therapy guidance
- **Antibiotic Escalation Triggers**: Organism, resistance, and host factor-based
- **Repeat Blood Culture Recommendations**: Per organism-specific guidelines

## Quick Start

```bash
# Interpret time-to-positivity
python cli.py ttp --hours 8.0

# Assess contamination
python cli.py contamination --organism staphylococcus_aureus --ttp 10.0

# Full analysis
python cli.py analyze --organism escherichia_coli --ttp 14.0 --gram-stain gram_negative_rods
```

## Python API

```python
from blood_culture_sentinel import analyze_blood_culture

result = analyze_blood_culture(
    organism="staphylococcus_aureus",
    ttp_hours=6.0,
    gram_stain="gram_positive_cocci_clusters",
    num_bottles_positive=2,
    num_bottles_total=2,
)
```

## Testing

```bash
python -m pytest test_blood_culture_sentinel.py -v
```

## Standards

- CLSI M47: Principles and Procedures for Blood Cultures
- IDSA Guidelines for S. aureus Bacteremia
- CAP Microbiology Checklist

## License

MIT
