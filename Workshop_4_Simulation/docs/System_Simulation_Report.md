# Academic Collaboration Network: System Simulation and Validation

Workshop No. 4 - System Simulation and Validation

Team 8 - Computer Engineering Program, Universidad Distrital Francisco Jose de Caldas

Authors: Gabriel Andres Beltran Varela, Kevin Santiago Silva Gonzalez, Miguel David Tarazona Correa, Anyelo Esteban Casas Zapata

## Executive Summary

This report completes Workshop No. 4 by simulating and validating the Academic Collaboration Network developed across Workshops 1, 2 and 3. The system addresses isolated learning through skill-based study group formation, resource sharing, notification support and institutional integration.

Two complementary models were implemented. First, a process-oriented discrete-event simulation models the operational sequence from student need recognition to group formation. Second, a behavior-oriented agent-based simulation models collaboration network evolution over a 12-week semester. Both models are calibrated with Workshop 1 survey results (n = 25), Workshop 2 architecture decisions and Workshop 3 quality/risk constraints.

The optimized ACN scenario reduced median group formation time by 91.5% compared with the WhatsApp-based AS-IS process, reduced isolated students by 67.4% in the process model, and kept p95 matching latency at 1.24 seconds under the 500-student exam-peak scenario. In the behavior model, the isolation-priority balancing loop reduced isolated students by 82.8% and increased collaboration density by 883.0% compared with informal self-selection.

The simulation validates the main design decisions from previous workshops: a dedicated matching engine is feasible for the target cohort size, centralized workspaces reduce coordination friction, and centrality monitoring materially improves equity. The main challenged assumption is adoption: the low-adoption scenario still leaves 11 isolated students after 12 weeks, confirming Workshop 3's low-adoption risk as the highest operational priority.

## Model Development

### System Architecture Translated into Simulation

The model maps Workshop 2's microservices into simulation components:

- User Profile Service: generates student profiles with skill, availability, performance, social connectivity and adoption openness.
- Skill Matching Engine: forms groups through homophily, random or balanced matching strategies.
- Group Workspace Service: transforms successful matches into collaboration edges.
- Notification Engine: influences invitation acceptance and group formation time.
- Integration Gateway: increases schedule compatibility when LMS data is available.
- Analytics Dashboard: reports density, centrality inequality, isolated students, group balance and satisfaction.

### Calibration Sources

The model uses the following Workshop 1 observations: 88% WhatsApp-only coordination, 36% communication barrier, 32% lack-of-interest barrier, 96% positive or conditional platform interest, mean adoption likelihood 3.88/5 and AS-IS group formation time of two to five days. Workshop 2 contributes the target matching latency below three seconds and 500+ concurrent users. Workshop 3 contributes the isolation-priority feedback loop, LMS failure fallback and quality gates.

### Modeling Assumptions

Student skill, availability and performance are represented as normalized continuous variables. The simulation uses synthetic profiles because institutional student data is privacy-sensitive and was not available. Matching latency is modeled as a quadratic function of cohort size, consistent with the sensitivity analysis in Workshop 1, while still reflecting caching and pre-filtering improvements from Workshop 2. The agent-based model treats collaboration as an undirected graph where edges represent meaningful study interactions.

## Experimental Design

The process model runs 120 Monte Carlo trials for five scenarios: AS_IS_WhatsApp, ACN_Baseline, ACN_Optimized_B1, ACN_LMS_Outage_Fallback and ACN_Exam_Peak_500. The behavior model runs four 12-week scenarios: AS_IS_Self_Selection, ACN_No_B1, ACN_With_B1 and ACN_Low_Adoption_20. Sensitivity analysis varies initial adoption from 0.2 to 0.9 and the isolation-priority threshold from 0 to 3.

## Results and Analysis

### Process-Oriented Simulation

| Scenario | n | Success | Median days | p95 latency | Isolated | GBI | Satisfaction |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AS_IS_WhatsApp | 200 | 0.39 | 4.66 | N/A | 121.7 | 0.35 | 0.43 |
| ACN_Baseline | 200 | 0.91 | 0.38 | 0.27 | 68.8 | 0.64 | 0.87 |
| ACN_Optimized_B1 | 200 | 0.98 | 0.40 | 0.21 | 39.7 | 0.64 | 0.89 |
| ACN_LMS_Outage_Fallback | 200 | 0.74 | 0.51 | 0.32 | 93.2 | 0.64 | 0.77 |
| ACN_Exam_Peak_500 | 500 | 0.94 | 0.39 | 1.24 | 130.0 | 0.62 | 0.87 |

The AS-IS process remains slow and exclusionary because student discovery depends on existing social connections. The optimized ACN scenario compresses formation time from 4.66 days to 0.40 days and improves satisfaction to 0.89. The LMS outage scenario remains operational but suffers a measurable decline in schedule compatibility and satisfaction, validating the fallback strategy while showing that integration reliability still matters.

### Behavior-Oriented Simulation

| Scenario | Adoption | Density | Isolated | Gini | Giant component | Satisfaction |
| --- | --- | --- | --- | --- | --- | --- |
| AS_IS_Self_Selection | 0.00 | 0.012 | 29 | 0.40 | 0.82 | 0.45 |
| ACN_No_B1 | 0.51 | 0.026 | 7 | 0.43 | 0.96 | 0.63 |
| ACN_With_B1 | 0.87 | 0.116 | 5 | 0.19 | 0.97 | 0.79 |
| ACN_Low_Adoption_20 | 0.37 | 0.026 | 11 | 0.47 | 0.94 | 0.62 |

The behavior model shows nonlinear network growth. Once platform adoption and satisfaction reinforce each other, density increases quickly and the giant component covers most of the cohort. The B1 isolation-priority loop reduces centrality inequality from 0.40 in the AS-IS scenario to 0.19, indicating a more equitable distribution of collaboration opportunities.

### Sensitivity Analysis

The best sensitivity outcome occurs at initial adoption 0.8 with threshold 1, leaving 1 isolated students. The worst outcome occurs at initial adoption 0.2 with threshold 2, leaving 18 isolated students. This confirms that adoption is not a cosmetic metric; it changes the topology of the collaboration network.

## Design Validation

The simulation validates four design decisions:

- Matching Engine: p95 latency remains below the three-second requirement, including the 500-student peak scenario.
- Integrated Workspace and Notifications: formation time and satisfaction improve substantially over the WhatsApp-only process.
- Isolation Monitoring: B1 centrality-based re-inclusion reduces isolated students and degree inequality.
- Robust Fallback: LMS outage degrades performance but does not collapse the system, aligning with Workshop 3's contingency plan.

The simulation also challenges one assumption. If adoption remains near 20%, the network cannot reach equitable connectivity even with a technically sound platform. This supports Workshop 3's mitigation strategy: faculty ambassadors, early-access pilots and gamified onboarding should be treated as core implementation work, not optional promotion.

## Complexity and Emergent Behavior

The system exhibits three complexity patterns. First, network growth is nonlinear: density improves slowly at low adoption and then accelerates when enough students participate to create useful matching diversity. Second, self-selection produces centrality concentration, where already-connected students keep receiving more collaboration opportunities. Third, centrality-based re-inclusion creates a balancing effect that reduces isolated learners without requiring manual advisor intervention in every case.

No chaotic instability appeared under the tested target loads, but the sensitivity analysis shows strong dependence on initial adoption. Small differences in adoption around the mid-range produce disproportionate changes in final isolation counts and giant-component coverage.

## Recommendations

1. Implement the B1 isolation-priority queue as a required Matching Engine feature.
2. Use cached pre-filtering and incremental recomputation to preserve sub-three-second matching at cohort scale.
3. Treat adoption as a risk-control mechanism: faculty ambassadors and guided onboarding should launch with the MVP.
4. Keep the LMS fallback path, but monitor its use because outage conditions reduce schedule compatibility.
5. Add ethical controls for consent, privacy and bias audits before using academic records in real deployments.
6. Run a real pilot with at least 50 students to replace synthetic parameters with observed usage data.

## Reproducibility

All simulation inputs, source code, generated CSV files, figures and this report are included in the Workshop_4_Simulation folder. To reproduce the experiment, run:

```bash
python src/run_simulations.py
```

The script reads configs/scenarios.json, writes CSV outputs to results/, writes PNG charts to figures/ and regenerates docs/System_Simulation_Report.pdf.

## Limitations

The simulation uses synthetic profiles calibrated from a small survey sample. Interpersonal compatibility, motivation, instructor intervention and real LMS data were approximated rather than measured directly. Results should therefore be interpreted as design validation evidence, not as a final production forecast.

## References

[1] A. M. Law, Simulation Modeling and Analysis, 5th ed. McGraw-Hill, 2015.

[2] J. Banks, J. S. Carson, B. L. Nelson and D. M. Nicol, Discrete-Event System Simulation, 5th ed. Pearson, 2010.

[3] S. F. Railsback and V. Grimm, Agent-Based and Individual-Based Modeling. Princeton University Press, 2019.

[4] S. Wasserman and K. Faust, Social Network Analysis: Methods and Applications. Cambridge University Press, 1994.

[5] D. W. Johnson, R. T. Johnson and K. A. Smith, "Cooperative learning returns to college," Change, vol. 30, no. 4, pp. 26-35, 1998.

[6] Team 8, "Workshop No. 1: Systems Analysis - Academic Collaboration Network," Universidad Distrital Francisco Jose de Caldas, 2026.

[7] Team 8, "Workshop No. 2: System Design - Academic Collaboration Network," Universidad Distrital Francisco Jose de Caldas, 2026.

[8] Team 8, "Workshop No. 3: Robust System Design and Project Management - Academic Collaboration Network," Universidad Distrital Francisco Jose de Caldas, 2026.
