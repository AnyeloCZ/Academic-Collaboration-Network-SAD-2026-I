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

# Academic Collaboration Network - Workshop #2: System Design

## 📋 Workshop Information

| Item | Details |
|------|---------|
| **Course** | Systems Analysis & Design — Semester 2026-I |
| **Professor** | Eng. Carlos Andrés Sierra, M.Sc. |
| **Workshop** | Workshop No. 2 — Systems Design |
| **Date** | March 2026 |
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

This document presents a comprehensive system design for the Academic Collaboration Network, addressing critical collaboration barriers identified in Workshop #1's primary data analysis (n = 25, March 2026). The design employs a **microservices architecture** with seven core services, achieving scalability to **500+ concurrent users**, **<2s response times**, and **99.5% availability**. Key innovations include an intelligent skill matching engine addressing the **36% communication barrier**, seamless LMS/library integration resolving the **88% WhatsApp dependency**, and robust security protocols for high-sensitivity components. The implementation roadmap spans **7 months** across three phases: MVP foundation, integration & enhancement, and optimization & scale.

---

## 🎯 Workshop Objectives

1. **System Architecture Design:** Develop a comprehensive design blueprint that addresses challenges and opportunities from Workshop #1.
2. **Engineering Principles Integration:** Apply modularity, scalability, maintainability, and reliability.
3. **Complexity and Sensitivity Management:** Incorporate strategies to address unpredictable behaviors and sensitive parameters.
4. **Implementation Planning:** Define technical approaches, methodologies, and implementation strategies.
5. **Documentation and Communication:** Produce a professional System Design Document.

---

## 🏗️ System Architecture Overview

### Microservices Architecture

The platform is structured around **seven independently deployable microservices**:

| Service | Core Responsibility | Technology Stack |
|---------|---------------------|------------------|
| **User Profile Service** | User identity & RBAC (SSO) | Node.js / PostgreSQL |
| **Skill Matching Engine** [HIGH] | Compatibility scoring | FastAPI / Redis |
| **Group Workspace Service** | WebSockets & messaging | Socket.io / S3 |
| **Notification Engine** | Event-driven alerts | RabbitMQ / Firebase |
| **Authentication & Authorization** [HIGH] | OAuth 2.0 + JWT | Node.js / PostgreSQL |
| **Analytics Dashboard** | Real-time metrics | Python / Grafana |
| **Integration Gateway** | LMS & Library connectors | Node.js / REST |

### Key Architectural Decisions

| Decision | Justification | Trade-off |
|----------|---------------|-----------|
| **Microservices** | Independent scaling; fault isolation | Deployment complexity |
| **PostgreSQL + Redis** | ACID compliance + caching; proven reliability | Dual-database operations |
| **React + React Native** | 70% code reusability; strong ecosystem | Framework lock-in |
| **OAuth 2.0 + JWT** | Industry-standard; SSO compatibility | Token management overhead |
| **Phased Deployment** | Early feedback; risk mitigation | Extended timeline |

---

## 📊 Requirements Summary

### Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR1 | User Profile Management (<5 min creation, skills, availability, privacy) | High |
| FR2 | Intelligent Skill Matching (multi-dimensional, <3s, explainability, >80% satisfaction) | Critical |
| FR3 | Group Workspace (real-time messaging, file sharing 50MB, task boards, meeting scheduler) | Critical |
| FR4 | Multi-Channel Notifications (email, push, in-app, >95% delivery) | High |
| FR5 | LMS & Library Integration (OAuth SSO, course sync, grade import, resource search) | High |
| FR6 | Analytics Dashboard (DAU, match conversion, group formation, algorithm performance) | Medium |

### Non-Functional Requirements

| Category | Target |
|----------|--------|
| **Performance** | Page load <2s / API <500ms / Matching <3s |
| **Reliability** | 99.5% uptime / MTTR <15min / zero data loss |
| **Security** | OAuth+MFA, TLS 1.3, GDPR compliance |
| **Scalability** | 500+ concurrent users, linear to 5,000+ |
| **Usability** | Onboarding <5min, WCAG 2.1 AA, ES+EN |
| **Maintainability** | 80% code coverage, OpenAPI docs, CI/CD automated |

---

## 📈 Performance & Optimization

### Performance Targets

| Metric | Target | Tool |
|--------|--------|------|
| Page Load Time | <2s (p95) | Real User Monitoring |
| API Response Time | <500 ms (p95) | New Relic / Datadog |
| Matching Latency | <3s | Application timer |
| Database Query | <200 ms (p95) | PostgreSQL slow query log |
| Concurrent Users | 500+ | JMeter load tests |
| Cache Hit Rate | ≥90% | Redis INFO stats |

### Optimization Strategies

- **Frontend:** Code splitting, WebP images, service worker caching, React.memo(), virtual scrolling, input debouncing (300ms)
- **Backend:** Database indexing, Redis caching (profiles 15min, matches 10min, messages 5min), async RabbitMQ processing, API rate limiting (100 req/min per user)
- **Matching Algorithm:** Pre-filter before scoring, Elasticsearch for skill search, Locality-Sensitive Hashing (LSH) for >5,000 users, parallel workers

### Scalability Planning

- **Horizontal Scaling:** Stateless services, Kubernetes HPA at CPU 70%, minimum 2 replicas per service
- **Database Scaling:** Read replicas for analytics, PgBouncer connection pooling (1,000 app → 100 DB), institution-based sharding roadmap

---

## ⚠️ Risk Management

| Risk | Impact | Mitigation Strategy |
|------|--------|----------------------|
| Low Adoption | High | Gamification, Faculty Ambassadors |
| Algorithm Bias | Critical | Continuous A/B Testing, Manual Fallback |
| Security Breach | Critical | OAuth+MFA, Quarterly Penetration Testing |
| LMS API Changes | Medium | Versioned adapters, mock API testing |
| Data Privacy | Critical | GDPR compliance, encryption at rest and in transit |

---

## 🧪 Quality Assurance & Testing

### Testing Strategy

| Test Type | Tools | Coverage / Target |
|-----------|-------|-------------------|
| Unit Testing | Jest (JS), Pytest (Python) | 80% code coverage |
| Integration Testing | Supertest, Postman | All API endpoints |
| End-to-End Testing | Cypress, Selenium | Critical user paths |
| Performance Testing | JMeter, k6 | Key load scenarios |
| Security Testing | OWASP ZAP, Snyk, Burp Suite | OWASP Top 10 |
| Accessibility | axe DevTools, WAVE | WCAG 2.1 AA |
| User Acceptance | Manual + SUS/NPS surveys | 30–50 beta users |

### CI/CD Pipeline (GitHub Actions)

1. Run unit tests (Jest/Pytest)
2. Upload coverage to Codecov
3. Snyk vulnerability scan
4. Build Docker images
5. Integration tests (Supertest/Postman)
6. Deploy to staging
7. E2E tests (Cypress)
8. OWASP ZAP security scan
9. If all pass: blue-green production deploy

**Quality Gates:** All tests pass | 80% coverage | Zero high-severity vulnerabilities | SonarQube quality gate passed

---

## 🗺️ Implementation Roadmap (7 Months)

| Phase | Duration | Focus |
|-------|----------|-------|
| **Phase 1: MVP Foundation** | Months 1-3 | Auth, Profile, Basic Matcher |
| **Phase 2: Integration & Enhancement** | Months 4-5 | LMS Integration, Mobile Apps, ML v2 |
| **Phase 3: Optimization & Scale** | Months 6-7 | Analytics, UX Audit, Performance Tuning |

---

## 📁 Repository Structure
