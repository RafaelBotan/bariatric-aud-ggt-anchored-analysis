# bariatric-aud-ggt-anchored-analysis

Reproducible analytical pipeline for the manuscript:

> **Clinical and psychometric predictors of post-bariatric alcohol use disorder, with anchored gamma-glutamyl transferase as a concurrent objective marker: a cross-sectional study**
>
> Arruda SLM, Botan RN, Galvão RO, Gonçalves MF, Melendez Araújo MS, Clark DSC, Sousa JB.
>
> Submitted to *Obesity Surgery* (Springer), 2026.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![DOI](https://img.shields.io/badge/OSF-10.17605%2FOSF.IO%2F27PSQ-blue)](https://osf.io/)

---

## Overview

This repository contains the full analytical pipeline (Python 3.13) used to:

1. Link 130 post-bariatric patients with CAGE/AUDIT screening to a single-center clinical-laboratory cohort with up to 22 years of follow-up.
2. Identify independent predictors of AUDIT-positive screening (AUDIT ≥ 8) via multivariable logistic regression with 5,000 bootstrap iterations.
3. Test gamma-glutamyl transferase (GGT) as a concurrent objective biomarker using a temporally anchored cross-sectional approach (±6, ±12, ±24 month windows).
4. Refute, via a properly specified random-slope mixed model, the hypothesis of cumulative GGT trajectory divergence between AUDIT-positive and AUDIT-negative patients.

## Key findings

- Independent predictors of AUDIT ≥ 8: **male sex** (OR 4.83, 95% CI 1.99–12.83) and **paternal alcohol use** (OR 5.17, 95% CI 2.02–14.45).
- Anchored GGT (±6 months from questionnaire): **median 31 vs 15 U/L** (AUDIT+ vs AUDIT−), p = 0.011, **AUC 0.727**.
- Monotonic temporal gradient supporting *concurrent* rather than *cumulative* signal.
- Random-slope mixed model: **slope × AUDIT interaction NS** (β = 0.016, p = 0.389) — refutes cumulative-damage interpretation.
- Hepatic family FDR-BH: only GGT survived correction (q = 0.044).

## Repository structure

```
.
├── README.md                              # this file
├── LICENSE                                # MIT
├── CITATION.cff                           # citation metadata
├── requirements.txt                       # Python dependencies
├── scripts/
│   ├── 01_linkage_e_consolidacao.py       # patient linkage (deterministic + fuzzy)
│   ├── 02_auditoria_consistencia.py       # cross-source consistency audit
│   ├── 03_replicar_descritivo_e_multivariada.py   # descriptive + multivariable
│   ├── 04_biomarcadores_sabin.py          # cross-sectional GGT/VCM/AST/ALT
│   ├── 05_texto_ia_alcool.py              # narrative text NLP (supplementary)
│   ├── 06_spline_temporal_e_firth.py      # temporal spline (rejected)
│   ├── 07_sensibilidade_e_coorte_completa.py   # sensitivity panels
│   ├── 08_robustez_consenso_dual_ia.py    # full robustness package (FDR, mixed, LOO)
│   ├── 09_anonimizar_dataset.py           # de-identification pipeline
│   ├── 10_gerar_figuras.py                # figures 300 dpi
│   ├── 11_gerar_tabelas.py                # Word tables
│   ├── 12_gerar_manuscrito.py             # full manuscript draft (Word)
│   └── 13_gerar_cover_letter_strobe.py    # cover letter + STROBE
├── data/
│   ├── DATASET_130_ANON.csv               # de-identified main dataset
│   ├── LAB_PANEL_LONG_ANON.csv            # de-identified longitudinal lab panel
│   └── README.md                          # data dictionary and ethical notice
└── results/
    ├── 08_FDR_cross_sectional.csv         # FDR-BH q-values for hepatic family
    ├── 08_FDR_mixed_models.csv            # mixed-model interaction q-values
    └── 08_robustez_log.txt                # full execution log
```

## Reproducibility

### Requirements
- Python 3.13+
- See `requirements.txt`

### Quick start

```bash
git clone https://github.com/RafaelBotan/bariatric-aud-ggt-anchored-analysis.git
cd bariatric-aud-ggt-anchored-analysis
pip install -r requirements.txt

# Reproduce the main analysis using the de-identified dataset
python scripts/08_robustez_consenso_dual_ia.py
python scripts/10_gerar_figuras.py
python scripts/11_gerar_tabelas.py
```

The de-identified dataset (`data/DATASET_130_ANON.csv`) is sufficient to reproduce **all main analyses**, **all figures**, and **all tables** in the manuscript and supplementary material. The original raw data, names, and dates are not deposited; the linkage is replaced by a study-specific sequential ID (P001–P130).

### Random seeds
- Bootstrap (5,000 iterations) — `np.random.seed(42)`
- Spline grid permutations — `np.random.seed(7)`

## Ethical statement

Approved by the Research Ethics Committee under **CAAE 34717119.4.0000.5553**. Informed consent for use of secondary data was waived under the retrospective scope of the analysis. The study followed the Declaration of Helsinki.

The deposited dataset is **de-identified**: patient names removed, dates replaced by relative offsets to anchor events, and direct identifiers (CPF, RG, hospital ID) excluded. Re-identification is operationally infeasible and any reanalysis intended to attempt re-identification is prohibited.

## License

- **Code**: MIT License (see `LICENSE`)
- **Data**: deposited under restricted ethical use — re-analysis requires (i) request to the corresponding author, (ii) institutional ethics approval at the requesting site, (iii) citation to this manuscript

## How to cite

If you use this code or data, please cite:

> Arruda SLM, Botan RN, Galvão RO, Gonçalves MF, Melendez Araújo MS, Clark DSC, Sousa JB. Clinical and psychometric predictors of post-bariatric alcohol use disorder, with anchored gamma-glutamyl transferase as a concurrent objective marker: a cross-sectional study. *Obesity Surgery* (under review). 2026.

**OSF DOI:** [10.17605/OSF.IO/27PSQ](https://doi.org/10.17605/OSF.IO/27PSQ)

## Contact

**Corresponding author:** Sergio Lincoln de Matos Arruda, MD
School of Medicine, Universidade de Brasília
sergioma3@yahoo.com.br

## Acknowledgments

We thank the patients who participated in this study and the multidisciplinary team at the bariatric service.

---

*Repository maintained as a permanent record accompanying the published manuscript.*
