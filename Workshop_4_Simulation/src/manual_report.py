from __future__ import annotations

from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"


def percent_delta(old: float, new: float) -> float:
    if old == 0:
        return 0.0
    return (old - new) / old * 100.0


def build_manual_two_column_pdf(
    config: dict,
    process_summary: pd.DataFrame,
    behavior_summary: pd.DataFrame,
    sensitivity: pd.DataFrame,
    figures: dict[str, Path],
) -> Path:
    pdf_path = DOCS_DIR / "System_Simulation_Report.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    page_w, page_h = letter
    margin = 0.55 * inch
    gutter = 0.18 * inch
    full_w = page_w - 2 * margin
    col_w = (full_w - gutter) / 2
    bottom = 0.52 * inch
    top = page_h - 0.55 * inch
    col_x = [margin, margin + col_w + gutter]
    page_no = 1
    col = 0
    column_top = top
    y = top

    as_is = process_summary[process_summary["scenario"] == "AS_IS_WhatsApp"].iloc[0]
    opt = process_summary[process_summary["scenario"] == "ACN_Optimized_B1"].iloc[0]
    peak = process_summary[process_summary["scenario"] == "ACN_Exam_Peak_500"].iloc[0]
    outage = process_summary[process_summary["scenario"] == "ACN_LMS_Outage_Fallback"].iloc[0]
    as_is_b = behavior_summary[behavior_summary["scenario"] == "AS_IS_Self_Selection"].iloc[0]
    b1 = behavior_summary[behavior_summary["scenario"] == "ACN_With_B1"].iloc[0]
    low = behavior_summary[behavior_summary["scenario"] == "ACN_Low_Adoption_20"].iloc[0]
    formation_reduction = percent_delta(as_is["median_formation_days"], opt["median_formation_days"])
    isolation_reduction = percent_delta(as_is["isolated_students_mean"], opt["isolated_students_mean"])
    network_isolation_reduction = percent_delta(as_is_b["isolated_students"], b1["isolated_students"])
    density_gain = (b1["density"] / as_is_b["density"] - 1.0) * 100.0 if as_is_b["density"] else 0.0

    def footer() -> None:
        c.setFont("Times-Roman", 7)
        c.drawCentredString(page_w / 2, 0.30 * inch, str(page_no))

    def new_page() -> None:
        nonlocal page_no, col, y, column_top
        footer()
        c.showPage()
        page_no += 1
        col = 0
        column_top = top
        y = column_top

    def switch_column() -> None:
        nonlocal col, y
        if col == 0:
            col = 1
            y = column_top
        else:
            new_page()

    def ensure(height: float) -> None:
        if y - height < bottom:
            switch_column()

    def draw_wrapped(
        text: str,
        font: str = "Times-Roman",
        size: float = 7.2,
        leading: float = 8.6,
        width: float | None = None,
        x: float | None = None,
        space_after: float = 3,
        center: bool = False,
    ) -> None:
        nonlocal y
        width = col_w if width is None else width
        x = col_x[col] if x is None else x
        lines = simpleSplit(text, font, size, width)
        height = len(lines) * leading + space_after
        ensure(height)
        c.setFont(font, size)
        for line in lines:
            if center:
                c.drawCentredString(x + width / 2, y, line)
            else:
                c.drawString(x, y, line)
            y -= leading
        y -= space_after

    def section(title: str) -> None:
        nonlocal y
        ensure(17)
        c.setFont("Times-Bold", 8.2)
        c.drawCentredString(col_x[col] + col_w / 2, y, title)
        y -= 12

    def subsection(title: str) -> None:
        nonlocal y
        ensure(12)
        c.setFont("Times-Bold", 7.4)
        c.drawString(col_x[col], y, title)
        y -= 9

    def table(caption: str, rows: list[list[str]], widths: list[float]) -> None:
        nonlocal y
        font_size = 5.2
        lead = 6.0
        pad = 2.0
        row_heights = []
        split_rows = []
        for row in rows:
            split_row = []
            max_lines = 1
            for cell, width in zip(row, widths):
                lines = simpleSplit(str(cell), "Times-Roman", font_size, max(width - 2 * pad, 10))
                lines = lines or [""]
                split_row.append(lines)
                max_lines = max(max_lines, len(lines))
            split_rows.append(split_row)
            row_heights.append(max_lines * lead + 2 * pad)
        height = 10 + sum(row_heights) + 6
        ensure(height)
        c.setFont("Times-Bold", 6.2)
        c.drawCentredString(col_x[col] + col_w / 2, y, caption)
        y -= 8
        x0 = col_x[col]
        table_w = sum(widths)
        current_y = y
        for r, (split_row, row_h) in enumerate(zip(split_rows, row_heights)):
            x = x0
            if r == 0:
                c.setFillColor(colors.HexColor("#F2F2F2"))
                c.rect(x0, current_y - row_h, table_w, row_h, fill=1, stroke=0)
                c.setFillColor(colors.black)
            for cell_lines, width in zip(split_row, widths):
                c.rect(x, current_y - row_h, width, row_h, fill=0, stroke=1)
                c.setFont("Times-Bold" if r == 0 else "Times-Roman", font_size)
                ty = current_y - pad - font_size
                for line in cell_lines:
                    c.drawString(x + pad, ty, line)
                    ty -= lead
                x += width
            current_y -= row_h
        y = current_y - 6

    def figure(path: Path, caption: str, height: float = 1.28 * inch) -> None:
        nonlocal y
        width = min(col_w, 3.20 * inch)
        total = height + 17
        ensure(total)
        c.drawImage(ImageReader(str(path)), col_x[col], y - height, width=width, height=height, preserveAspectRatio=True, anchor="c")
        y -= height + 7
        c.setFont("Times-Roman", 6.1)
        for line in simpleSplit(caption, "Times-Roman", 6.1, col_w):
            c.drawCentredString(col_x[col] + col_w / 2, y, line)
            y -= 6.8
        y -= 3

    def full_width_text(text: str, font: str, size: float, leading: float, y_pos: float, space: float = 0) -> float:
        c.setFont(font, size)
        for line in simpleSplit(text, font, size, full_w):
            c.drawCentredString(page_w / 2, y_pos, line)
            y_pos -= leading
        return y_pos - space

    # Full-width paper header.
    title_y = top
    title_y = full_width_text("Academic Collaboration Network:", "Times-Roman", 15, 17, title_y)
    title_y = full_width_text("System Simulation and Validation", "Times-Roman", 15, 17, title_y, 3)
    title_y = full_width_text("Workshop No. 4 - Systems Analysis & Design 2026-I", "Times-Roman", 8, 10, title_y, 7)
    author_width = full_w / 4
    author_blocks = [
        ["Gabriel Andres", "Beltran Varela", "Computer Engineering Program", "Universidad Distrital", "Bogota, Colombia", "gbeltranv@udistrital.edu.co"],
        ["Kevin Santiago", "Silva Gonzalez", "Computer Engineering Program", "Universidad Distrital", "Bogota, Colombia", "ksilvas@udistrital.edu.co"],
        ["Miguel David", "Tarazona Correa", "Computer Engineering Program", "Universidad Distrital", "Bogota, Colombia", "mtarazonac@udistrital.edu.co"],
        ["Anyelo Esteban", "Casas Zapata", "Computer Engineering Program", "Universidad Distrital", "Bogota, Colombia", "acasasz@udistrital.edu.co"],
    ]
    c.setFont("Times-Roman", 6.4)
    max_author_lines = max(len(block) for block in author_blocks)
    for i, block in enumerate(author_blocks):
        ay = title_y
        for line in block:
            c.drawCentredString(margin + author_width * i + author_width / 2, ay, line)
            ay -= 7.1
    title_y -= max_author_lines * 7.1 + 8
    abstract = (
        f"Abstract- This paper presents the computational simulation and validation phase of the Academic Collaboration Network, "
        f"a socio-technical platform designed to reduce isolated learning through skill-based group optimization and institutional resource integration. "
        f"Building on Workshops #1, #2 and #3, the study implements a process-oriented discrete-event model and a behavior-oriented agent-based network model. "
        f"Results show that the optimized ACN scenario reduces median group formation time by {formation_reduction:.1f}%, reduces process-model isolated students by {isolation_reduction:.1f}%, "
        f"and maintains p95 matching latency at {peak['p95_matching_latency_seconds']:.2f} seconds under a 500-student stress scenario. "
        f"The B1 loop reduces final isolated students by {network_isolation_reduction:.1f}% and increases density by {density_gain:.1f}%."
    )
    c.setFont("Times-Roman", 7.0)
    for line in simpleSplit(abstract, "Times-Roman", 7.0, full_w):
        c.drawString(margin, title_y, line)
        title_y -= 8.1
    keywords = "Keywords- systems engineering, discrete-event simulation, agent-based modeling, collaborative learning, social network analysis, design validation."
    for line in simpleSplit(keywords, "Times-Roman", 7.0, full_w):
        c.drawString(margin, title_y, line)
        title_y -= 8.1
    title_y -= 6

    column_top = title_y
    y = column_top

    section("I. INTRODUCTION")
    draw_wrapped("The previous workshops established the Academic Collaboration Network (ACN) as a response to isolated learning, inefficient study group formation, and uneven distribution of academic support among university students. Workshop #1 identified the current coordination process as informal and fragmented: 88% of surveyed students relied exclusively on WhatsApp, 36% reported lack of communication as the main barrier, and 96% expressed positive or conditional interest in a dedicated platform.")
    draw_wrapped("Workshop #2 transformed those findings into a microservices architecture with profile management, skill matching, workspaces, notifications, analytics, and LMS/library integration. Workshop #3 strengthened the design through fault tolerance, risk management, quality assurance, project planning, and the B1 balancing loop for isolation mitigation.")

    section("II. CONTINUITY FROM PREVIOUS WORKSHOPS")
    table(
        "TABLE I. PROJECT EVOLUTION",
        [
            ["W", "Output", "Simulation use"],
            ["#1", "Survey, AS-IS/TO-BE, loops", "Calibration and baseline"],
            ["#2", "Microservices and NFRs", "Architecture and latency targets"],
            ["#3", "Risk, QA, B1 loop", "Stress/failure scenarios"],
            ["#4", "Models and validation", "Empirical design evidence"],
        ],
        [0.24 * inch, 1.05 * inch, 1.80 * inch],
    )

    section("III. SIMULATION METHODOLOGY")
    subsection("A. Process-Oriented Simulation")
    draw_wrapped("The process model represents the sequence from student need recognition to successful group formation. It compares the current WhatsApp-based process with platform-supported matching, notification, schedule integration, LMS fallback, and exam-period stress scenarios. Each scenario is evaluated through Monte Carlo trials using synthetic profiles calibrated from Workshop #1.")
    subsection("B. Behavior-Oriented Simulation")
    draw_wrapped("The behavior model represents students as agents in an undirected collaboration graph. Weekly interactions create or reinforce edges, while adoption and satisfaction influence participation. Metrics include density, isolated students, centrality inequality, giant-component coverage, and satisfaction across a 12-week semester.")
    subsection("C. Assumptions")
    draw_wrapped("Student skill, availability, performance, social connectivity, and platform openness are normalized synthetic variables. Institutional academic records are not used, preserving privacy while allowing design-level validation.")

    section("IV. EXPERIMENTAL DESIGN")
    table(
        "TABLE II. SIMULATION SCENARIOS",
        [
            ["Scenario", "Purpose", "Change"],
            ["AS-IS", "Current coordination", "No platform"],
            ["Baseline", "Workshop #2 design", "80% adoption"],
            ["Opt. B1", "Isolation control", "B1 priority"],
            ["LMS Out.", "Risk fallback", "LMS unavailable"],
            ["Peak 500", "Capacity test", "500 students"],
        ],
        [0.72 * inch, 1.20 * inch, 1.18 * inch],
    )

    section("V. PROCESS SIMULATION RESULTS")
    process_label = {
        "AS_IS_WhatsApp": "AS-IS",
        "ACN_Baseline": "Base",
        "ACN_Optimized_B1": "Opt.",
        "ACN_LMS_Outage_Fallback": "Out.",
        "ACN_Exam_Peak_500": "Peak",
    }
    process_rows = [["Sc.", "n", "Succ.", "Days", "p95", "Iso.", "GBI", "Sat."]]
    for _, row in process_summary.iterrows():
        latency = "N/A" if pd.isna(row["p95_matching_latency_seconds"]) else f"{row['p95_matching_latency_seconds']:.2f}"
        process_rows.append(
            [
                process_label.get(row["scenario"], row["scenario"]),
                f"{row['cohort_size']:.0f}",
                f"{row['success_rate_mean']:.2f}",
                f"{row['median_formation_days']:.2f}",
                latency,
                f"{row['isolated_students_mean']:.0f}",
                f"{row['group_balance_index_mean']:.2f}",
                f"{row['satisfaction_score_mean']:.2f}",
            ]
        )
    table(
        "TABLE III. PROCESS RESULTS",
        process_rows,
        [0.33 * inch, 0.22 * inch, 0.33 * inch, 0.32 * inch, 0.30 * inch, 0.30 * inch, 0.28 * inch, 0.28 * inch],
    )
    draw_wrapped(f"The optimized ACN scenario compresses group formation from {as_is['median_formation_days']:.2f} days to {opt['median_formation_days']:.2f} days and improves satisfaction from {as_is['satisfaction_score_mean']:.2f} to {opt['satisfaction_score_mean']:.2f}. The LMS outage case remains operational with success rate {outage['success_rate_mean']:.2f}, validating the fallback but showing integration reliability still matters.")
    figure(figures["process"], "Fig. 1. Formation time and isolated-student share.", 1.30 * inch)
    figure(figures["quality"], "Fig. 2. Matching quality and satisfaction.", 1.30 * inch)

    section("VI. BEHAVIOR SIMULATION")
    behavior_label = {
        "AS_IS_Self_Selection": "AS-IS",
        "ACN_No_B1": "No B1",
        "ACN_With_B1": "B1",
        "ACN_Low_Adoption_20": "Low",
    }
    behavior_rows = [["Sc.", "Ad.", "Den.", "Iso.", "Gini", "Giant", "Sat."]]
    for _, row in behavior_summary.iterrows():
        behavior_rows.append(
            [
                behavior_label.get(row["scenario"], row["scenario"]),
                f"{row['adoption_rate']:.2f}",
                f"{row['density']:.3f}",
                f"{row['isolated_students']:.0f}",
                f"{row['degree_gini']:.2f}",
                f"{row['giant_component_share']:.2f}",
                f"{row['mean_satisfaction']:.2f}",
            ]
        )
    table(
        "TABLE IV. BEHAVIOR RESULTS",
        behavior_rows,
        [0.40 * inch, 0.34 * inch, 0.37 * inch, 0.28 * inch, 0.34 * inch, 0.38 * inch, 0.34 * inch],
    )
    draw_wrapped(f"The behavior model shows nonlinear network growth. Informal self-selection ends with {as_is_b['isolated_students']:.0f} isolated students and density {as_is_b['density']:.3f}. With B1, final isolation falls to {b1['isolated_students']:.0f}, density rises to {b1['density']:.3f}, and degree inequality decreases to {b1['degree_gini']:.2f}.")
    figure(figures["density"], "Fig. 3. Collaboration density over 12 weeks.", 1.22 * inch)
    figure(figures["fairness"], "Fig. 4. Isolation and centrality inequality.", 1.30 * inch)

    section("VII. COMPLEXITY AND SENSITIVITY")
    draw_wrapped("The system exhibits nonlinear adoption effects, centrality concentration in informal groups, and balancing behavior when low-degree students are prioritized. Sensitivity tests confirm that adoption is structural: below a mid-range threshold, the graph does not accumulate enough active participants to eliminate isolation.")
    figure(figures["sensitivity"], "Fig. 5. Sensitivity of remaining isolated students.", 1.48 * inch)

    section("VIII. DESIGN VALIDATION")
    table(
        "TABLE V. VALIDATION SUMMARY",
        [
            ["Decision", "Evidence", "Result"],
            ["Matcher", f"p95 {peak['p95_matching_latency_seconds']:.2f}s at 500", "Valid"],
            ["Workspace", f"Time -{formation_reduction:.1f}%", "Valid"],
            ["B1 loop", f"Isolation {as_is_b['isolated_students']:.0f}->{b1['isolated_students']:.0f}", "Valid"],
            ["LMS fallback", f"Success {outage['success_rate_mean']:.2f}", "Partial"],
            ["Adoption", f"Low case leaves {low['isolated_students']:.0f}", "Mitigate"],
        ],
        [0.80 * inch, 1.55 * inch, 0.60 * inch],
    )

    section("IX. RECOMMENDATIONS")
    for item in [
        "Implement B1 isolation-priority as a mandatory Matching Engine component.",
        "Use cached pre-filtering and incremental recomputation for sub-three-second matching.",
        "Launch faculty ambassadors, guided onboarding, and pilot incentives with the MVP.",
        "Maintain LMS fallback mechanisms and monitor schedule compatibility during outages.",
        "Apply consent, data minimization, access control, explainability, and bias audits.",
        "Run a 50-student pilot to replace synthetic assumptions with observed data.",
    ]:
        draw_wrapped("- " + item)

    section("X. LIMITATIONS AND ETHICS")
    draw_wrapped("The model uses synthetic profiles calibrated from a limited survey sample. It approximates interpersonal compatibility, motivation, instructor intervention, and LMS behavior. Results should be interpreted as design validation evidence rather than a production forecast. Any implementation must protect student privacy and avoid biased academic recommendations.")

    section("XI. CONCLUSION")
    draw_wrapped("The simulation phase validates the ACN design trajectory across the four-workshop sequence. The architecture can reduce coordination time, improve satisfaction, preserve latency targets under modeled stress, and reduce isolation when centrality-based re-inclusion is active. The strongest remaining risk is sustained adoption, making change management a technical success factor.")

    section("ACKNOWLEDGMENT")
    draw_wrapped("The authors thank Eng. Carlos Andres Sierra, M.Sc., for guidance throughout the Systems Analysis & Design course, and the survey participants who contributed primary data for this project.")

    section("GITHUB REPOSITORY")
    draw_wrapped("Workshop 4 materials should be placed under Workshop_4_Simulation in the course repository, including source code, input data, figures, results, README documentation, and this report. Repository: https://github.com/AnyeloCZ/Academic-Collaboration-Network-SAD-2026-I")

    section("REFERENCES")
    refs = [
        "[1] A. M. Law, Simulation Modeling and Analysis, 5th ed. McGraw-Hill, 2015.",
        "[2] J. Banks, J. S. Carson, B. L. Nelson and D. M. Nicol, Discrete-Event System Simulation, 5th ed. Pearson, 2010.",
        "[3] S. F. Railsback and V. Grimm, Agent-Based and Individual-Based Modeling. Princeton University Press, 2019.",
        "[4] S. Wasserman and K. Faust, Social Network Analysis: Methods and Applications. Cambridge University Press, 1994.",
        "[5] D. W. Johnson, R. T. Johnson and K. A. Smith, Cooperative learning returns to college, Change, vol. 30, no. 4, pp. 26-35, 1998.",
        "[6] Team 8, Workshop No. 1: Systems Analysis - Academic Collaboration Network, Universidad Distrital Francisco Jose de Caldas, 2026.",
        "[7] Team 8, Workshop No. 2: System Design - Academic Collaboration Network, Universidad Distrital Francisco Jose de Caldas, 2026.",
        "[8] Team 8, Workshop No. 3: Robust System Design and Project Management - Academic Collaboration Network, Universidad Distrital Francisco Jose de Caldas, 2026.",
    ]
    for ref in refs:
        draw_wrapped(ref, size=6.8, leading=8.0, space_after=1)

    footer()
    c.save()
    return pdf_path
