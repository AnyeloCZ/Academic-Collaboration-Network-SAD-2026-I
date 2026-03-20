# Academic Collaboration Network - Workshop #1: Systems Analysis

## 📋 Workshop Information

| Item | Details |
|------|---------|
| **Course** | Systems Analysis & Design — Semester 2026-I |
| **Professor** | Eng. Carlos Andrés Sierra, M.Sc. |
| **Workshop** | Workshop No. 1 — Systems Analysis |
| **Date** | March 6, 2026 |
| **Institution** | Universidad Distrital Francisco José de Caldas |
| **Program** | Computer Engineering |

---

## 👥 Team 8

| Name | Code |
|------|------|
| Silva Gonzalez Kevin Santiago | 20251020105 |
| Casas Zapata Anyelo Esteban | 20251020106 |
| Beltran Varela Gabriel Andrés | 20251020107 |
| Tarazona Correa Miguel David | 20251020113 |

---

## 📖 Abstract

This document presents a comprehensive systems analysis of the Academic Collaboration Network, addressing critical collaboration barriers identified through primary data collection (n = 25, March 2026). The analysis reveals that **88% of students rely exclusively on WhatsApp** with zero institutional integration, **36% identify communication as the primary obstacle** to group formation, and **96% express interest** in a dedicated platform (mean likelihood 3.88/5). The study employs systems engineering principles including stakeholder identification, process mapping, causal loop analysis, and sensitivity evaluation to characterize the current state and identify optimization opportunities.

---

## 🎯 Workshop Objectives

1. **System Identification:** Define boundaries, stakeholders, and external interfaces
2. **Process Documentation:** Map AS-IS workflows and identify structural bottlenecks
3. **Primary Data Collection:** Conduct surveys and process observation to validate findings
4. **Systems Analysis:** Apply causal loop diagrams, sensitivity analysis, and complexity evaluation
5. **Optimization Opportunities:** Identify leverage points for system improvement

---

## 📊 Key Findings

### Survey Results Summary (n = 25)

| Metric | Result |
|--------|--------|
| **WhatsApp Dependency** | 88% use WhatsApp as only coordination tool |
| **Communication Barrier** | 36% identify lack of communication as main problem |
| **Interest Barrier** | 32% identify lack of interest as main problem |
| **Platform Interest** | 96% positive or conditional interest |
| **Adoption Likelihood** | Mean = 3.88/5 (σ = 1.01) |
| **Group Formation Difficulty** | 44% neutral or difficult |

### Main Barriers to Group Formation

1. **Lack of Communication** — 36%
2. **Lack of Interest** — 32%
3. **Different Academic Levels** — 16%
4. **Unknown Classmates** — 12%
5. **Incompatible Schedules** — 4%

### Systemic Bottlenecks Identified

| Component | Bottleneck | Optimization Strategy |
|-----------|------------|----------------------|
| Skill Discovery | Social Homophily | Variance Minimization |
| Communication | Information Noise | Centralized Layer |
| Equity | Centrality Concentration | Targeted Redistribution |
| Institutional Support | Data Fragmentation | Integrated Resource Layer |

---

## 🏗️ System Architecture Overview

### System Boundaries

| Boundary | Components |
|----------|------------|
| **Internal** | Student database, optimization algorithms, collaboration graph, user interface |
| **External** | University grading system (SIA), WhatsApp, library catalogue, physical infrastructure |

### Key Stakeholders

| Stakeholder | Role in System |
|-------------|----------------|
| Students | Primary users forming study groups |
| Professors | Academic supervisors observing collaboration |
| Academic Advisors | Guidance and student support |
| University Administration | Monitor institutional academic performance |
| Library Services | Provide academic resources and support |

### Feedback Loops

- **R1 (Reinforcing) — Network Growth:** More participants → Higher skill density → Better matching accuracy → Improved satisfaction → More participants
- **B1 (Balancing) — Isolation Mitigation:** Low degree centrality triggers prioritization for inclusion

---

## 📁 Repository Structure

# Academic Collaboration Network - Workshop #2: Systems Design

## Team 8
- Silva Gonzalez Kevin Santiago
- Casas Zapata Anyelo Esteban
- Beltran Varela Gabriel Andrés
- Tarazona Correa Miguel David

## Workshop Overview
This workshop focuses on translating analytical findings from Workshop #1 into a comprehensive systems design that addresses collaboration barriers identified in the academic environment.

## Key Design Decisions
- **Architecture:** Microservices with 7 core services
- **Technologies:** React, React Native, Node.js, Python, PostgreSQL, Redis, RabbitMQ
- **Deployment:** Kubernetes with horizontal auto-scaling
- **Security:** OAuth 2.0 + JWT, TLS 1.3, GDPR compliance

## Diagrams Included
1. Microservices Architecture Overview
2. Skill Matching Engine Processing Flow
3. Sequence Diagram - SSO Authentication & LMS Integration
4. Deployment Diagram - Kubernetes Infrastructure
5. Data Flow Diagram (Level 0 and Level 1)

## Methodology
The design follows systems engineering principles including:
- Modularity and separation of concerns
- Scalability and high availability
- Security-first approach
- Continuous integration and delivery

## References
- Workshop #1 Systems Analysis (March 2026)
- IEEE 1471: Recommended Practice for Architectural Description

---
**Course:** Systems Analysis & Design — Semester 2026-I  
**Professor:** Eng. Carlos Andrés Sierra, M.Sc.  
**Universidad Distrital Francisco José de Caldas**
