# Workshop 4 - System Simulation and Validation

This folder contains the complete Workshop 4 simulation package for the **Academic Collaboration Network**.

## Contents

- `src/run_simulations.py`: executable simulation, visualization and report-generation script.
- `configs/scenarios.json`: calibrated scenario definitions.
- `data/survey_parameters.csv`: parameters derived from Workshops 1, 2 and 3.
- `results/`: generated CSV outputs for process, behavior, sensitivity and validation results.
- `figures/`: generated visual analysis charts.
- `docs/System_Simulation_Report.md`: complete technical report in English.
- `docs/System_Simulation_Report.pdf`: PDF report for submission.

## How to Run

From this folder:

```bash
python src/run_simulations.py
```

The script uses `numpy`, `pandas`, `Pillow` and `reportlab`. It regenerates all CSV files, PNG figures and the PDF report.

## Simulation Approaches

1. **Process-oriented simulation:** models the workflow from student need recognition to group formation. It compares the current WhatsApp-based AS-IS process with the designed ACN platform, optimized B1 isolation control, LMS outage fallback and a 500-student exam peak.
2. **Behavior-oriented simulation:** models student agents as nodes in a collaboration graph over a 12-week semester. It measures density, isolated students, degree inequality, giant-component coverage and satisfaction.

## Main Validation Results

- Optimized ACN reduces group formation time compared with the WhatsApp-only process.
- The matching engine remains below the three-second latency requirement under the 500-student stress scenario.
- The B1 centrality-based re-inclusion loop reduces isolated students and degree inequality.
- Low adoption remains the main system risk and must be addressed through onboarding, faculty ambassadors and early pilot incentives.

## Submission Artifact

Use this PDF for the course platform:

`System_Simulation_Report.pdf`

Repository path recommendation:

```text
Academic-Collaboration-Network-SAD-2026-I/
  Workshop_4_Simulation/
    configs/
    data/
    docs/
    figures/
    results/
    src/
    README.md
```
