# Academic Collaboration Network - Final Project

This repository contains the final project package for the **Academic Collaboration Network (ACN)** developed in the Systems Analysis & Design course.

The project models and validates a skill-based academic collaboration platform designed to reduce isolated learning, improve study group formation, and support institutional resource integration.

## Repository Structure

```text
Academic_Collaboration_Network_Final_Project/
  configs/
    scenarios.json
  data/
    survey_parameters.csv
    custom_students_template.csv
  docs/
    Team8_Academic_Collaboration_Network_Final_Paper.tex
  figures/
  results/
  src/
    run_simulations.py
  .gitignore
  README.md
  requirements.txt
  run.bat
  run_my_data.bat
  run_random_data.bat
```

## Requirements

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run the Simulation

Windows:

```bat
run.bat
```

Command line:

```bash
python src/run_simulations.py
```

The script generates:

- `results/process_summary.csv`
- `results/behavior_summary.csv`
- `results/sensitivity_summary.csv`
- `figures/*.png`
- `docs/System_Simulation_Report.pdf`
- `docs/dashboard.html`

## Use Randomized Data

```bash
python src/run_simulations.py --randomize
```

or double-click:

```text
run_random_data.bat
```

## Use Your Own Student Data

1. Copy:

```text
data/custom_students_template.csv
```

2. Rename the copy as:

```text
data/custom_students.csv
```

3. Edit the values from 1 to 5:

- `skill`
- `availability`
- `performance`
- `social`
- `openness`

4. Run:

```text
run_my_data.bat
```

or:

```bash
python src/run_simulations.py --students data/custom_students.csv
```

## Final Paper

The LaTeX paper is available at:

```text
docs/Team8_Academic_Collaboration_Network_Final_Paper.tex
```

You can compile it in Overleaf using the IEEE conference template.

## Main Validation Results

The baseline reproducible simulation validates:

- 91.5% reduction in median group formation time compared with the AS-IS process.
- p95 matching latency of approximately 1.24 seconds under a 500-student stress scenario.
- Reduction of isolated students through the B1 centrality-based isolation-priority loop.
- LMS outage fallback remains operational, although with reduced performance.

