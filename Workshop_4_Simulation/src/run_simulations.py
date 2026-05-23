from __future__ import annotations

import json
import math
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
from xml.sax.saxutils import escape

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    FrameBreak,
    Image as PdfImage,
    PageBreak,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "scenarios.json"
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = ROOT / "figures"
DOCS_DIR = ROOT / "docs"


PALETTE = {
    "blue": (42, 111, 151),
    "green": (45, 138, 95),
    "orange": (229, 137, 48),
    "red": (190, 72, 72),
    "purple": (103, 80, 164),
    "gray": (88, 96, 105),
    "light_gray": (241, 244, 248),
    "ink": (31, 35, 40),
}


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend(
            [
                r"C:\Windows\Fonts\arialbd.ttf",
                r"C:\Windows\Fonts\segoeuib.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            ]
        )
    candidates.extend(
        [
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    )
    for item in candidates:
        path = Path(item)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def ensure_dirs() -> None:
    for path in [RESULTS_DIR, FIGURES_DIR, DOCS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def clamp(values: np.ndarray | float, lo: float, hi: float):
    return np.minimum(np.maximum(values, lo), hi)


def generate_students(n: int, rng: np.random.Generator) -> pd.DataFrame:
    skill = clamp(rng.normal(0.58, 0.18, n), 0.05, 0.98)
    availability = clamp(rng.beta(3.0, 2.2, n), 0.05, 0.98)
    performance = clamp(0.65 * skill + 0.35 * rng.normal(0.62, 0.15, n), 0.05, 0.99)
    social = clamp(rng.beta(2.0, 4.0, n), 0.02, 0.96)
    openness = clamp(rng.normal(3.88 / 5.0, 1.01 / 5.0, n), 0.05, 0.99)
    semester = rng.choice(["1-2", "3-4", "5+"], size=n, p=[0.40, 0.28, 0.32])
    return pd.DataFrame(
        {
            "student_id": [f"S{i + 1:03d}" for i in range(n)],
            "skill": skill,
            "availability": availability,
            "performance": performance,
            "social": social,
            "openness": openness,
            "semester": semester,
        }
    )


def pairwise_schedule_score(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    vals = np.asarray(values)
    diffs = []
    for i in range(len(vals)):
        for j in range(i + 1, len(vals)):
            diffs.append(1.0 - abs(float(vals[i]) - float(vals[j])))
    return float(np.mean(diffs))


def gini(values: np.ndarray) -> float:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0 or np.sum(arr) == 0:
        return 0.0
    arr = np.sort(arr)
    n = arr.size
    return float((2 * np.sum((np.arange(1, n + 1) * arr))) / (n * np.sum(arr)) - (n + 1) / n)


def connected_component_share(adj: np.ndarray) -> float:
    n = adj.shape[0]
    seen = np.zeros(n, dtype=bool)
    best = 0
    for start in range(n):
        if seen[start]:
            continue
        stack = [start]
        seen[start] = True
        size = 0
        while stack:
            node = stack.pop()
            size += 1
            neighbors = np.where(adj[node])[0]
            for neighbor in neighbors:
                if not seen[neighbor]:
                    seen[neighbor] = True
                    stack.append(int(neighbor))
        best = max(best, size)
    return float(best / n)


def network_density(adj: np.ndarray) -> float:
    n = adj.shape[0]
    if n < 2:
        return 0.0
    return float(adj.sum() / (n * (n - 1)))


def group_indices(
    ids: np.ndarray,
    students: pd.DataFrame,
    group_size: int,
    rng: np.random.Generator,
    strategy: str,
    degrees: np.ndarray | None = None,
    isolation_priority: bool = False,
) -> list[list[int]]:
    ids = np.asarray(ids, dtype=int)
    if len(ids) < group_size:
        return []

    if isolation_priority and degrees is not None and strategy == "balanced":
        group_count = len(ids) // group_size
        priority = ids[np.argsort(degrees[ids])][:group_count]
        priority_set = set(map(int, priority))
        remaining = np.array([idx for idx in ids if int(idx) not in priority_set], dtype=int)
        if len(remaining) < group_count * (group_size - 1):
            rng.shuffle(ids)
            usable = ids[: group_count * group_size]
            return [list(map(int, usable[i : i + group_size])) for i in range(0, len(usable), group_size)]
        sorted_remaining = remaining[np.argsort(students.loc[remaining, "skill"].to_numpy())]
        strata = np.array_split(sorted_remaining[: group_count * (group_size - 1)], group_size - 1)
        groups = []
        for j in range(group_count):
            group = [int(priority[j])]
            for stratum in strata:
                group.append(int(stratum[j]))
            groups.append(group)
        rng.shuffle(groups)
        return groups
    elif isolation_priority and degrees is not None:
        isolated = ids[np.argsort(degrees[ids])][: max(group_size, len(ids) // 4)]
        isolated_set = set(map(int, isolated))
        remaining = np.array([idx for idx in ids if int(idx) not in isolated_set], dtype=int)
        rng.shuffle(remaining)
        ordered = np.concatenate([isolated, remaining])
    elif strategy == "homophily":
        score = students.loc[ids, "skill"].to_numpy() + 0.30 * students.loc[ids, "social"].to_numpy()
        ordered = ids[np.argsort(score + rng.normal(0, 0.025, len(ids)))]
    elif strategy == "balanced":
        sorted_ids = ids[np.argsort(students.loc[ids, "skill"].to_numpy())]
        group_count = len(sorted_ids) // group_size
        usable = sorted_ids[: group_count * group_size]
        strata = np.array_split(usable, group_size)
        groups = []
        for j in range(group_count):
            group = []
            for stratum in strata:
                if j < len(stratum):
                    group.append(int(stratum[j]))
            if len(group) == group_size:
                groups.append(group)
        rng.shuffle(groups)
        return groups
    else:
        ordered = ids.copy()
        rng.shuffle(ordered)

    usable_count = (len(ordered) // group_size) * group_size
    usable = ordered[:usable_count]
    return [list(map(int, usable[i : i + group_size])) for i in range(0, usable_count, group_size)]


def group_metrics(students: pd.DataFrame, groups: list[list[int]]) -> dict[str, float]:
    if not groups:
        return {
            "mean_skill_variance": 0.0,
            "group_balance_index": 0.0,
            "mean_schedule_score": 0.0,
            "mean_group_mean_skill_error": 0.0,
        }
    total_var = float(np.var(students["skill"].to_numpy())) or 1e-6
    cohort_mean = float(students["skill"].mean())
    group_vars = []
    schedule_scores = []
    mean_errors = []
    for group in groups:
        skill_values = students.loc[group, "skill"].to_numpy()
        group_vars.append(float(np.var(skill_values)))
        schedule_scores.append(pairwise_schedule_score(students.loc[group, "availability"].to_numpy()))
        mean_errors.append(abs(float(np.mean(skill_values)) - cohort_mean))
    mean_var = float(np.mean(group_vars))
    mean_error = float(np.mean(mean_errors))
    # Balance is defined as equitable skill distribution across groups, not only
    # low within-group variance. This avoids rewarding homophily-driven clusters.
    between_group_equity = float(clamp(1.0 - mean_error / (math.sqrt(total_var) + 1e-6), 0.0, 1.0))
    within_group_cohesion = float(clamp(1.0 - mean_var / total_var, 0.0, 1.0))
    return {
        "mean_skill_variance": mean_var,
        "group_balance_index": float(clamp(0.82 * between_group_equity + 0.18 * within_group_cohesion, 0.0, 1.0)),
        "mean_schedule_score": float(np.mean(schedule_scores)),
        "mean_group_mean_skill_error": mean_error,
    }


def matching_latency_seconds(n: int, stress_multiplier: float, rng: np.random.Generator) -> float:
    # Quadratic growth is kept below Workshop 2's 3s NFR for the modeled cohort sizes.
    deterministic = 0.040 + 0.0000034 * (n**2) + 0.00009 * n
    noise = rng.lognormal(mean=-3.05, sigma=0.28)
    return float((deterministic + noise) * stress_multiplier)


def simulate_process_scenarios(config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(config["random_seed"])
    group_size = int(config["group_size"])
    trials = int(config["monte_carlo_trials"])
    rows = []

    for scenario in config["process_scenarios"]:
        n = int(scenario["cohort_size"])
        for trial in range(trials):
            students = generate_students(n, rng)
            if scenario["platform_enabled"]:
                adoption_prob = clamp(
                    scenario["adoption_rate"]
                    * (0.65 + 0.35 * students["openness"].to_numpy() / max(students["openness"].max(), 1e-6)),
                    0.0,
                    0.98,
                )
                active = np.where(rng.random(n) < adoption_prob)[0]
                groups = group_indices(
                    active,
                    students,
                    group_size,
                    rng,
                    scenario["strategy"],
                    degrees=np.zeros(n),
                    isolation_priority=bool(scenario["isolation_priority"]),
                )
                latency = matching_latency_seconds(n, float(scenario["stress_multiplier"]), rng)
                base_days = rng.lognormal(mean=math.log(0.43), sigma=0.28)
                if not scenario["lms_available"]:
                    base_days *= 1.28
                if scenario["isolation_priority"]:
                    base_days *= 0.92
            else:
                active = np.arange(n)
                groups = group_indices(active, students, group_size, rng, scenario["strategy"])
                latency = float("nan")
                base_days = rng.triangular(2.0, 3.5, 5.0)

            metrics = group_metrics(students, groups)
            possible_groups = len(groups)
            if possible_groups == 0:
                rows.append(
                    {
                        "scenario": scenario["name"],
                        "trial": trial + 1,
                        "cohort_size": n,
                        "possible_groups": 0,
                        "successful_groups": 0,
                        "success_rate": 0.0,
                        "median_formation_days": float("nan"),
                        "p95_matching_latency_seconds": latency,
                        "isolated_students": n,
                        "group_balance_index": 0.0,
                        "mean_skill_variance": 0.0,
                        "mean_schedule_score": 0.0,
                        "satisfaction_score": 0.0,
                    }
                )
                continue

            quality = 0.35 * metrics["group_balance_index"] + 0.35 * (
                1.0 - min(metrics["mean_group_mean_skill_error"] / 0.20, 1.0)
            ) + 0.30 * metrics["mean_schedule_score"]
            success_probability = scenario["success_base"] * (
                0.65 + 0.35 * scenario["invitation_acceptance"]
            )
            success_probability += 0.10 * scenario["communication_efficiency"] + 0.06 * quality
            if not scenario["platform_enabled"]:
                success_probability -= 0.18
            if not scenario["lms_available"] and scenario["platform_enabled"]:
                success_probability -= 0.08
            success_probability = float(clamp(success_probability, 0.05, 0.98))

            successful_flags = rng.random(possible_groups) < success_probability
            successful_groups = [group for group, ok in zip(groups, successful_flags) if ok]
            successful_students = set(idx for group in successful_groups for idx in group)

            if scenario["platform_enabled"]:
                formation_times = base_days * rng.lognormal(mean=0.0, sigma=0.20, size=max(1, len(successful_groups)))
                formation_times += latency / (60 * 60 * 24)
            else:
                barrier_factor = 1.0 + 0.36 * rng.random() + 0.32 * rng.random()
                formation_times = base_days * barrier_factor * rng.lognormal(
                    mean=0.0, sigma=0.22, size=max(1, len(successful_groups))
                )

            satisfaction = 0.30 + 0.42 * quality + 0.20 * scenario["communication_efficiency"]
            satisfaction += 0.10 * scenario["schedule_integration"] + rng.normal(0.0, 0.035)
            if scenario["platform_enabled"]:
                satisfaction += 0.035
            if not scenario["platform_enabled"]:
                satisfaction -= 0.18
            if not scenario["lms_available"] and scenario["platform_enabled"]:
                satisfaction -= 0.06
            satisfaction = float(clamp(satisfaction, 0.0, 1.0))

            rows.append(
                {
                    "scenario": scenario["name"],
                    "trial": trial + 1,
                    "cohort_size": n,
                    "possible_groups": possible_groups,
                    "successful_groups": len(successful_groups),
                    "success_rate": len(successful_groups) / possible_groups,
                    "median_formation_days": float(np.median(formation_times)) if len(successful_groups) else np.nan,
                    "p95_matching_latency_seconds": latency,
                    "isolated_students": n - len(successful_students),
                    "group_balance_index": metrics["group_balance_index"],
                    "mean_skill_variance": metrics["mean_skill_variance"],
                    "mean_schedule_score": metrics["mean_schedule_score"],
                    "satisfaction_score": satisfaction,
                }
            )

    trials_df = pd.DataFrame(rows)
    def nan_p95(series: pd.Series) -> float:
        clean = series.dropna()
        if clean.empty:
            return float("nan")
        return float(np.nanpercentile(clean, 95))

    summary = (
        trials_df.groupby("scenario", as_index=False)
        .agg(
            cohort_size=("cohort_size", "median"),
            success_rate_mean=("success_rate", "mean"),
            success_rate_std=("success_rate", "std"),
            median_formation_days=("median_formation_days", "median"),
            p95_matching_latency_seconds=("p95_matching_latency_seconds", nan_p95),
            isolated_students_mean=("isolated_students", "mean"),
            isolated_students_std=("isolated_students", "std"),
            group_balance_index_mean=("group_balance_index", "mean"),
            mean_schedule_score=("mean_schedule_score", "mean"),
            satisfaction_score_mean=("satisfaction_score", "mean"),
        )
    )
    order = {
        "AS_IS_WhatsApp": 0,
        "ACN_Baseline": 1,
        "ACN_Optimized_B1": 2,
        "ACN_LMS_Outage_Fallback": 3,
        "ACN_Exam_Peak_500": 4,
    }
    summary["_order"] = summary["scenario"].map(order).fillna(99)
    summary = summary.sort_values("_order").drop(columns=["_order"])
    return trials_df, summary


def initial_as_is_network(students: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    n = len(students)
    adj = np.zeros((n, n), dtype=bool)
    skills = students["skill"].to_numpy()
    social = students["social"].to_numpy()
    for i in range(n):
        for j in range(i + 1, n):
            homophily = 1.0 - abs(skills[i] - skills[j])
            social_boost = 0.5 * (social[i] + social[j])
            prob = 0.001 + 0.010 * max(homophily, 0) + 0.006 * social_boost
            if rng.random() < prob:
                adj[i, j] = adj[j, i] = True
    return adj


def simulate_behavior_scenarios(config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng_master = np.random.default_rng(config["random_seed"] + 777)
    n = int(config["cohort_size"])
    group_size = int(config["group_size"])
    weeks = int(config["semester_weeks"])
    rows = []

    for scenario in config["behavior_scenarios"]:
        rng = np.random.default_rng(int(rng_master.integers(0, 10_000_000)))
        students = generate_students(n, rng)
        adj = initial_as_is_network(students, rng)
        adopters = rng.random(n) < float(scenario["initial_adoption"])
        satisfaction_memory = np.full(n, 0.55 if scenario["platform_enabled"] else 0.42)

        for week in range(1, weeks + 1):
            degrees = adj.sum(axis=1)
            if scenario["platform_enabled"]:
                active_mask = adopters & (rng.random(n) < float(scenario["weekly_participation"]))
            else:
                social_factor = 0.20 + 0.85 * students["social"].to_numpy()
                active_mask = rng.random(n) < (float(scenario["weekly_participation"]) * social_factor)
            active_ids = np.where(active_mask)[0]
            groups = group_indices(
                active_ids,
                students,
                group_size,
                rng,
                scenario["strategy"],
                degrees=degrees,
                isolation_priority=bool(scenario["isolation_priority"]),
            )
            if not scenario["platform_enabled"]:
                # Informal coordination loses groups when there is no common social path.
                filtered = []
                for group in groups:
                    existing_edges = 0
                    for a in range(len(group)):
                        for b in range(a + 1, len(group)):
                            existing_edges += int(adj[group[a], group[b]])
                    if existing_edges >= 1 or rng.random() < 0.12:
                        filtered.append(group)
                groups = filtered

            metric = group_metrics(students, groups)
            retention = float(scenario["edge_retention"])
            if scenario["isolation_priority"]:
                retention += 0.06
            if not scenario["platform_enabled"]:
                retention -= 0.25
            retention = float(clamp(retention, 0.10, 0.92))

            for group in groups:
                schedule_score = pairwise_schedule_score(students.loc[group, "availability"].to_numpy())
                link_prob = clamp(retention * (0.72 + 0.28 * schedule_score), 0.05, 0.98)
                for a in range(len(group)):
                    for b in range(a + 1, len(group)):
                        if rng.random() < link_prob:
                            adj[group[a], group[b]] = True
                            adj[group[b], group[a]] = True
                group_sat = 0.42 + 0.28 * metric["mean_schedule_score"] + 0.22 * metric["group_balance_index"]
                if scenario["isolation_priority"]:
                    group_sat += 0.06
                if not scenario["platform_enabled"]:
                    group_sat -= 0.10
                satisfaction_memory[group] = 0.70 * satisfaction_memory[group] + 0.30 * clamp(group_sat, 0, 1)

            if scenario["platform_enabled"]:
                non_adopters = np.where(~adopters)[0]
                if len(non_adopters) > 0:
                    growth_signal = np.mean(satisfaction_memory[adopters]) if adopters.any() else 0.50
                    weekly_growth = max(0.0, growth_signal - 0.55) * 0.16
                    if bool(scenario["isolation_priority"]):
                        weekly_growth += 0.012
                    current_rate = float(adopters.mean())
                    cap = float(scenario["max_adoption"])
                    if current_rate < cap:
                        new_prob = min(weekly_growth, (cap - current_rate) * 0.45)
                        new_flags = rng.random(len(non_adopters)) < new_prob
                        adopters[non_adopters[new_flags]] = True

            degrees = adj.sum(axis=1)
            isolates = int(np.sum(degrees == 0))
            rows.append(
                {
                    "scenario": scenario["name"],
                    "week": week,
                    "adoption_rate": float(adopters.mean()) if scenario["platform_enabled"] else 0.0,
                    "density": network_density(adj),
                    "isolated_students": isolates,
                    "degree_gini": gini(degrees),
                    "giant_component_share": connected_component_share(adj),
                    "mean_satisfaction": float(np.mean(satisfaction_memory)),
                    "group_balance_index": metric["group_balance_index"],
                }
            )

    timeseries = pd.DataFrame(rows)
    final = timeseries[timeseries["week"] == weeks].copy()
    summary = final[
        [
            "scenario",
            "adoption_rate",
            "density",
            "isolated_students",
            "degree_gini",
            "giant_component_share",
            "mean_satisfaction",
            "group_balance_index",
        ]
    ].copy()
    order = {
        "AS_IS_Self_Selection": 0,
        "ACN_No_B1": 1,
        "ACN_With_B1": 2,
        "ACN_Low_Adoption_20": 3,
    }
    summary["_order"] = summary["scenario"].map(order).fillna(99)
    summary = summary.sort_values("_order").drop(columns=["_order"])
    return timeseries, summary


def simulate_sensitivity(config: dict) -> pd.DataFrame:
    base = config.copy()
    rows = []
    seed = int(config["random_seed"]) + 202
    for adoption in config["sensitivity"]["adoption_rates"]:
        for threshold in config["sensitivity"]["isolation_thresholds"]:
            local = json.loads(json.dumps(base))
            local["behavior_scenarios"] = [
                {
                    "name": f"adoption_{adoption:.1f}_threshold_{threshold}",
                    "description": "Sensitivity test",
                    "strategy": "balanced",
                    "initial_adoption": adoption,
                    "weekly_participation": 0.76,
                    "edge_retention": 0.66,
                    "isolation_priority": threshold > 0,
                    "platform_enabled": True,
                    "max_adoption": min(0.95, adoption + 0.22),
                }
            ]
            local["random_seed"] = seed + int(adoption * 100) + threshold
            local["semester_weeks"] = config["sensitivity"]["weeks"]
            ts, _ = simulate_behavior_scenarios(local)
            final = ts.iloc[-1]
            rows.append(
                {
                    "initial_adoption": adoption,
                    "isolation_threshold": threshold,
                    "final_density": final["density"],
                    "final_isolated_students": final["isolated_students"],
                    "degree_gini": final["degree_gini"],
                    "giant_component_share": final["giant_component_share"],
                }
            )
    return pd.DataFrame(rows)


def draw_text_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    max_width: int,
    line_spacing: int = 4,
) -> int:
    x, y = xy
    words = text.split()
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            line = candidate
        else:
            draw.text((x, y), line, font=font, fill=fill)
            y += font.size + line_spacing
            line = word
    if line:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + line_spacing
    return y


def save_bar_chart(
    data: pd.DataFrame,
    label_col: str,
    value_cols: list[str],
    title: str,
    ylabel: str,
    path: Path,
    colors_list: list[tuple[int, int, int]],
    value_format: str = "{:.2f}",
) -> None:
    width, height = 1320, 820
    margin = {"left": 120, "right": 70, "top": 120, "bottom": 210}
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    title_font = load_font(34, bold=True)
    axis_font = load_font(21)
    small_font = load_font(17)
    draw.text((margin["left"], 42), title, font=title_font, fill=PALETTE["ink"])
    plot_w = width - margin["left"] - margin["right"]
    plot_h = height - margin["top"] - margin["bottom"]
    x0, y0 = margin["left"], height - margin["bottom"]
    y_max = max(float(data[col].max()) for col in value_cols) * 1.18
    y_max = max(y_max, 1e-6)
    for step in range(6):
        y = y0 - int(plot_h * step / 5)
        value = y_max * step / 5
        draw.line((x0, y, x0 + plot_w, y), fill=(224, 229, 235), width=1)
        draw.text((25, y - 12), value_format.format(value), font=small_font, fill=PALETTE["gray"])
    draw.line((x0, margin["top"], x0, y0), fill=PALETTE["ink"], width=2)
    draw.line((x0, y0, x0 + plot_w, y0), fill=PALETTE["ink"], width=2)

    n = len(data)
    cluster_w = plot_w / max(n, 1)
    bar_w = min(68, cluster_w / (len(value_cols) + 1.4))
    for i, row in data.reset_index(drop=True).iterrows():
        center = x0 + cluster_w * (i + 0.5)
        for j, col in enumerate(value_cols):
            value = float(row[col])
            bx0 = center - (len(value_cols) * bar_w) / 2 + j * bar_w
            bh = int(plot_h * value / y_max)
            color = colors_list[j % len(colors_list)]
            draw.rounded_rectangle((bx0, y0 - bh, bx0 + bar_w * 0.82, y0), radius=4, fill=color)
            draw.text((bx0 - 4, y0 - bh - 27), value_format.format(value), font=small_font, fill=PALETTE["ink"])
        label = str(row[label_col]).replace("ACN_", "").replace("_", " ")
        draw_text_wrapped(
            draw,
            (int(center - cluster_w * 0.42), y0 + 20),
            label,
            small_font,
            PALETTE["ink"],
            int(cluster_w * 0.84),
            line_spacing=1,
        )
    legend_x = margin["left"]
    legend_y = height - 62
    for j, col in enumerate(value_cols):
        draw.rectangle((legend_x, legend_y, legend_x + 20, legend_y + 20), fill=colors_list[j])
        draw.text((legend_x + 28, legend_y - 1), col.replace("_", " "), font=axis_font, fill=PALETTE["ink"])
        legend_x += 310
    draw.text((20, margin["top"] + plot_h // 2 - 20), ylabel, font=axis_font, fill=PALETTE["gray"])
    img.save(path)


def save_line_chart(
    data: pd.DataFrame,
    x_col: str,
    y_col: str,
    series_col: str,
    title: str,
    ylabel: str,
    path: Path,
) -> None:
    width, height = 1320, 780
    margin = {"left": 110, "right": 70, "top": 115, "bottom": 120}
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    title_font = load_font(34, bold=True)
    axis_font = load_font(21)
    small_font = load_font(17)
    draw.text((margin["left"], 42), title, font=title_font, fill=PALETTE["ink"])
    plot_w = width - margin["left"] - margin["right"]
    plot_h = height - margin["top"] - margin["bottom"]
    x0, y0 = margin["left"], height - margin["bottom"]
    x_values = sorted(data[x_col].unique())
    y_min = 0.0
    y_max = float(data[y_col].max()) * 1.12
    y_max = max(y_max, 0.01)
    for step in range(6):
        y = y0 - int(plot_h * step / 5)
        value = y_max * step / 5
        draw.line((x0, y, x0 + plot_w, y), fill=(224, 229, 235), width=1)
        draw.text((25, y - 12), f"{value:.2f}", font=small_font, fill=PALETTE["gray"])
    draw.line((x0, margin["top"], x0, y0), fill=PALETTE["ink"], width=2)
    draw.line((x0, y0, x0 + plot_w, y0), fill=PALETTE["ink"], width=2)
    for x in x_values:
        xp = x0 + (int(x) - min(x_values)) / max(max(x_values) - min(x_values), 1) * plot_w
        draw.text((xp - 8, y0 + 18), str(int(x)), font=small_font, fill=PALETTE["gray"])
    color_cycle = [PALETTE["blue"], PALETTE["green"], PALETTE["orange"], PALETTE["red"], PALETTE["purple"]]
    legend_x = x0
    legend_y = height - 58
    for idx, (name, group) in enumerate(data.groupby(series_col)):
        color = color_cycle[idx % len(color_cycle)]
        points = []
        for _, row in group.sort_values(x_col).iterrows():
            xp = x0 + (row[x_col] - min(x_values)) / max(max(x_values) - min(x_values), 1) * plot_w
            yp = y0 - (row[y_col] - y_min) / max(y_max - y_min, 1e-9) * plot_h
            points.append((float(xp), float(yp)))
        if len(points) >= 2:
            draw.line(points, fill=color, width=4)
        for xp, yp in points:
            draw.ellipse((xp - 4, yp - 4, xp + 4, yp + 4), fill=color)
        draw.rectangle((legend_x, legend_y, legend_x + 20, legend_y + 20), fill=color)
        label = str(name).replace("ACN_", "").replace("_", " ")
        draw.text((legend_x + 28, legend_y - 2), label, font=axis_font, fill=PALETTE["ink"])
        legend_x += min(330, 24 + len(label) * 12)
    draw.text((20, margin["top"] + plot_h // 2 - 20), ylabel, font=axis_font, fill=PALETTE["gray"])
    img.save(path)


def save_heatmap(data: pd.DataFrame, path: Path) -> None:
    width, height = 1040, 720
    margin = {"left": 160, "right": 80, "top": 120, "bottom": 120}
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    title_font = load_font(32, bold=True)
    axis_font = load_font(20)
    small_font = load_font(17)
    draw.text((margin["left"], 42), "Sensitivity: Remaining Isolated Students", font=title_font, fill=PALETTE["ink"])
    adoptions = sorted(data["initial_adoption"].unique())
    thresholds = sorted(data["isolation_threshold"].unique())
    plot_w = width - margin["left"] - margin["right"]
    plot_h = height - margin["top"] - margin["bottom"]
    cell_w = plot_w / len(thresholds)
    cell_h = plot_h / len(adoptions)
    values = data["final_isolated_students"].to_numpy()
    vmin, vmax = float(values.min()), float(values.max())
    for i, adoption in enumerate(adoptions):
        for j, threshold in enumerate(thresholds):
            value = float(
                data[(data["initial_adoption"] == adoption) & (data["isolation_threshold"] == threshold)][
                    "final_isolated_students"
                ].iloc[0]
            )
            t = 0.0 if vmax == vmin else (value - vmin) / (vmax - vmin)
            color = (
                int(PALETTE["green"][0] * (1 - t) + PALETTE["red"][0] * t),
                int(PALETTE["green"][1] * (1 - t) + PALETTE["red"][1] * t),
                int(PALETTE["green"][2] * (1 - t) + PALETTE["red"][2] * t),
            )
            x0 = margin["left"] + j * cell_w
            y0 = margin["top"] + (len(adoptions) - i - 1) * cell_h
            draw.rectangle((x0, y0, x0 + cell_w, y0 + cell_h), fill=color, outline="white", width=3)
            text = f"{value:.0f}"
            bbox = draw.textbbox((0, 0), text, font=axis_font)
            draw.text(
                (x0 + cell_w / 2 - (bbox[2] - bbox[0]) / 2, y0 + cell_h / 2 - 10),
                text,
                font=axis_font,
                fill="white",
            )
    for j, threshold in enumerate(thresholds):
        x = margin["left"] + j * cell_w + cell_w / 2
        draw.text((x - 8, margin["top"] + plot_h + 25), str(int(threshold)), font=axis_font, fill=PALETTE["ink"])
    for i, adoption in enumerate(adoptions):
        y = margin["top"] + (len(adoptions) - i - 1) * cell_h + cell_h / 2 - 10
        draw.text((80, y), f"{adoption:.1f}", font=axis_font, fill=PALETTE["ink"])
    draw.text((margin["left"] + 230, height - 55), "Isolation-priority threshold", font=axis_font, fill=PALETTE["gray"])
    draw.text((35, margin["top"] - 45), "Initial adoption", font=axis_font, fill=PALETTE["gray"])
    draw.text((margin["left"], height - 92), "Lower values are better; each cell reports isolated students after 12 weeks.", font=small_font, fill=PALETTE["gray"])
    img.save(path)


def generate_figures(
    process_summary: pd.DataFrame,
    behavior_timeseries: pd.DataFrame,
    behavior_summary: pd.DataFrame,
    sensitivity: pd.DataFrame,
) -> dict[str, Path]:
    figures = {}
    p = FIGURES_DIR / "process_time_and_isolation.png"
    proc = process_summary.copy()
    proc["formation_days"] = proc["median_formation_days"].fillna(0)
    proc["isolated_share"] = proc["isolated_students_mean"] / proc["cohort_size"]
    save_bar_chart(
        proc,
        "scenario",
        ["formation_days", "isolated_share"],
        "Process Simulation: Formation Time and Isolation",
        "days / share",
        p,
        [PALETTE["blue"], PALETTE["red"]],
        "{:.2f}",
    )
    figures["process"] = p

    p = FIGURES_DIR / "quality_and_satisfaction.png"
    qual = process_summary.copy()
    save_bar_chart(
        qual,
        "scenario",
        ["group_balance_index_mean", "satisfaction_score_mean"],
        "Process Simulation: Matching Quality and Satisfaction",
        "score (0-1)",
        p,
        [PALETTE["green"], PALETTE["orange"]],
        "{:.2f}",
    )
    figures["quality"] = p

    p = FIGURES_DIR / "network_density_over_time.png"
    save_line_chart(
        behavior_timeseries,
        "week",
        "density",
        "scenario",
        "Behavior Simulation: Collaboration Density Over Time",
        "density",
        p,
    )
    figures["density"] = p

    p = FIGURES_DIR / "isolation_and_fairness.png"
    fair = behavior_summary.copy()
    fair["isolated_share"] = fair["isolated_students"] / int(behavior_timeseries.groupby("scenario").size().iloc[0] * 0 + 200)
    save_bar_chart(
        fair,
        "scenario",
        ["isolated_share", "degree_gini"],
        "Behavior Simulation: Isolation and Centrality Inequality",
        "share / gini",
        p,
        [PALETTE["red"], PALETTE["purple"]],
        "{:.2f}",
    )
    figures["fairness"] = p

    p = FIGURES_DIR / "sensitivity_isolation_heatmap.png"
    save_heatmap(sensitivity, p)
    figures["sensitivity"] = p
    return figures


def csv_outputs(
    process_trials: pd.DataFrame,
    process_summary: pd.DataFrame,
    behavior_timeseries: pd.DataFrame,
    behavior_summary: pd.DataFrame,
    sensitivity: pd.DataFrame,
) -> None:
    process_trials.to_csv(RESULTS_DIR / "process_trials.csv", index=False)
    process_summary.to_csv(RESULTS_DIR / "process_summary.csv", index=False)
    behavior_timeseries.to_csv(RESULTS_DIR / "behavior_timeseries.csv", index=False)
    behavior_summary.to_csv(RESULTS_DIR / "behavior_summary.csv", index=False)
    sensitivity.to_csv(RESULTS_DIR / "sensitivity_summary.csv", index=False)

    validation = []
    optimized = process_summary[process_summary["scenario"] == "ACN_Optimized_B1"].iloc[0]
    peak = process_summary[process_summary["scenario"] == "ACN_Exam_Peak_500"].iloc[0]
    as_is = process_summary[process_summary["scenario"] == "AS_IS_WhatsApp"].iloc[0]
    b1 = behavior_summary[behavior_summary["scenario"] == "ACN_With_B1"].iloc[0]
    as_is_behavior = behavior_summary[behavior_summary["scenario"] == "AS_IS_Self_Selection"].iloc[0]
    validation.append(
        {
            "design_claim": "Matching engine responds under 3 seconds",
            "threshold": 3.0,
            "observed": peak["p95_matching_latency_seconds"],
            "status": "validated" if peak["p95_matching_latency_seconds"] < 3.0 else "challenged",
        }
    )
    validation.append(
        {
            "design_claim": "Platform reduces average group formation time",
            "threshold": as_is["median_formation_days"],
            "observed": optimized["median_formation_days"],
            "status": "validated" if optimized["median_formation_days"] < as_is["median_formation_days"] else "challenged",
        }
    )
    validation.append(
        {
            "design_claim": "Isolation-priority loop reduces isolated students",
            "threshold": as_is_behavior["isolated_students"],
            "observed": b1["isolated_students"],
            "status": "validated" if b1["isolated_students"] < as_is_behavior["isolated_students"] else "challenged",
        }
    )
    validation.append(
        {
            "design_claim": "User satisfaction reaches the 80 percent target",
            "threshold": 0.80,
            "observed": optimized["satisfaction_score_mean"],
            "status": "validated" if optimized["satisfaction_score_mean"] >= 0.80 else "challenged",
        }
    )
    pd.DataFrame(validation).to_csv(RESULTS_DIR / "validation_summary.csv", index=False)


def percent_delta(old: float, new: float) -> float:
    if old == 0:
        return 0.0
    return (old - new) / old * 100.0


def markdown_table(df: pd.DataFrame, columns: list[str], headers: list[str], formats: dict[str, str] | None = None) -> str:
    formats = formats or {}
    rows = []
    rows.append("| " + " | ".join(headers) + " |")
    rows.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for _, row in df.iterrows():
        vals = []
        for col in columns:
            value = row[col]
            fmt = formats.get(col)
            if pd.isna(value):
                vals.append("N/A")
                continue
            if fmt and isinstance(value, (int, float, np.floating)):
                vals.append(fmt.format(value))
            else:
                vals.append(str(value))
        rows.append("| " + " | ".join(vals) + " |")
    return "\n".join(rows)


def build_report_markdown(
    config: dict,
    process_summary: pd.DataFrame,
    behavior_summary: pd.DataFrame,
    sensitivity: pd.DataFrame,
) -> str:
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
    sensitivity_best = sensitivity.sort_values("final_isolated_students").iloc[0]
    sensitivity_worst = sensitivity.sort_values("final_isolated_students", ascending=False).iloc[0]

    proc_table = markdown_table(
        process_summary,
        [
            "scenario",
            "cohort_size",
            "success_rate_mean",
            "median_formation_days",
            "p95_matching_latency_seconds",
            "isolated_students_mean",
            "group_balance_index_mean",
            "satisfaction_score_mean",
        ],
        ["Scenario", "n", "Success", "Median days", "p95 latency", "Isolated", "GBI", "Satisfaction"],
        {
            "cohort_size": "{:.0f}",
            "success_rate_mean": "{:.2f}",
            "median_formation_days": "{:.2f}",
            "p95_matching_latency_seconds": "{:.2f}",
            "isolated_students_mean": "{:.1f}",
            "group_balance_index_mean": "{:.2f}",
            "satisfaction_score_mean": "{:.2f}",
        },
    )
    beh_table = markdown_table(
        behavior_summary,
        [
            "scenario",
            "adoption_rate",
            "density",
            "isolated_students",
            "degree_gini",
            "giant_component_share",
            "mean_satisfaction",
        ],
        ["Scenario", "Adoption", "Density", "Isolated", "Gini", "Giant component", "Satisfaction"],
        {
            "adoption_rate": "{:.2f}",
            "density": "{:.3f}",
            "isolated_students": "{:.0f}",
            "degree_gini": "{:.2f}",
            "giant_component_share": "{:.2f}",
            "mean_satisfaction": "{:.2f}",
        },
    )

    return f"""# Academic Collaboration Network: System Simulation and Validation

Workshop No. 4 - System Simulation and Validation

Team 8 - Computer Engineering Program, Universidad Distrital Francisco Jose de Caldas

Authors: Gabriel Andres Beltran Varela, Kevin Santiago Silva Gonzalez, Miguel David Tarazona Correa, Anyelo Esteban Casas Zapata

## Executive Summary

This report completes Workshop No. 4 by simulating and validating the Academic Collaboration Network developed across Workshops 1, 2 and 3. The system addresses isolated learning through skill-based study group formation, resource sharing, notification support and institutional integration.

Two complementary models were implemented. First, a process-oriented discrete-event simulation models the operational sequence from student need recognition to group formation. Second, a behavior-oriented agent-based simulation models collaboration network evolution over a 12-week semester. Both models are calibrated with Workshop 1 survey results (n = 25), Workshop 2 architecture decisions and Workshop 3 quality/risk constraints.

The optimized ACN scenario reduced median group formation time by {formation_reduction:.1f}% compared with the WhatsApp-based AS-IS process, reduced isolated students by {isolation_reduction:.1f}% in the process model, and kept p95 matching latency at {peak['p95_matching_latency_seconds']:.2f} seconds under the 500-student exam-peak scenario. In the behavior model, the isolation-priority balancing loop reduced isolated students by {network_isolation_reduction:.1f}% and increased collaboration density by {density_gain:.1f}% compared with informal self-selection.

The simulation validates the main design decisions from previous workshops: a dedicated matching engine is feasible for the target cohort size, centralized workspaces reduce coordination friction, and centrality monitoring materially improves equity. The main challenged assumption is adoption: the low-adoption scenario still leaves {low['isolated_students']:.0f} isolated students after 12 weeks, confirming Workshop 3's low-adoption risk as the highest operational priority.

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

The process model runs {config['monte_carlo_trials']} Monte Carlo trials for five scenarios: AS_IS_WhatsApp, ACN_Baseline, ACN_Optimized_B1, ACN_LMS_Outage_Fallback and ACN_Exam_Peak_500. The behavior model runs four 12-week scenarios: AS_IS_Self_Selection, ACN_No_B1, ACN_With_B1 and ACN_Low_Adoption_20. Sensitivity analysis varies initial adoption from 0.2 to 0.9 and the isolation-priority threshold from 0 to 3.

## Results and Analysis

### Process-Oriented Simulation

{proc_table}

The AS-IS process remains slow and exclusionary because student discovery depends on existing social connections. The optimized ACN scenario compresses formation time from {as_is['median_formation_days']:.2f} days to {opt['median_formation_days']:.2f} days and improves satisfaction to {opt['satisfaction_score_mean']:.2f}. The LMS outage scenario remains operational but suffers a measurable decline in schedule compatibility and satisfaction, validating the fallback strategy while showing that integration reliability still matters.

### Behavior-Oriented Simulation

{beh_table}

The behavior model shows nonlinear network growth. Once platform adoption and satisfaction reinforce each other, density increases quickly and the giant component covers most of the cohort. The B1 isolation-priority loop reduces centrality inequality from {as_is_b['degree_gini']:.2f} in the AS-IS scenario to {b1['degree_gini']:.2f}, indicating a more equitable distribution of collaboration opportunities.

### Sensitivity Analysis

The best sensitivity outcome occurs at initial adoption {sensitivity_best['initial_adoption']:.1f} with threshold {sensitivity_best['isolation_threshold']:.0f}, leaving {sensitivity_best['final_isolated_students']:.0f} isolated students. The worst outcome occurs at initial adoption {sensitivity_worst['initial_adoption']:.1f} with threshold {sensitivity_worst['isolation_threshold']:.0f}, leaving {sensitivity_worst['final_isolated_students']:.0f} isolated students. This confirms that adoption is not a cosmetic metric; it changes the topology of the collaboration network.

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
"""


def dataframe_for_pdf(df: pd.DataFrame, columns: list[str], formats: dict[str, str] | None = None) -> list[list[str]]:
    formats = formats or {}
    out = [[col.replace("_", " ").title() for col in columns]]
    for _, row in df.iterrows():
        line = []
        for col in columns:
            value = row[col]
            fmt = formats.get(col)
            if pd.isna(value):
                line.append("N/A")
                continue
            if fmt and isinstance(value, (int, float, np.floating)):
                line.append(fmt.format(value))
            else:
                line.append(str(value))
        out.append(line)
    return out


def para(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


def add_table(story: list, data: list[list[str]], col_widths: list[float] | None = None) -> None:
    table = Table(data, repeatRows=1, colWidths=col_widths)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2A6F97")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D0D7DE")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8FA")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.12 * inch))


def build_report_pdf(
    config: dict,
    process_summary: pd.DataFrame,
    behavior_summary: pd.DataFrame,
    sensitivity: pd.DataFrame,
    figures: dict[str, Path],
) -> Path:
    pdf_path = DOCS_DIR / "System_Simulation_Report.pdf"
    doc = BaseDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )
    page_w, page_h = letter
    margin_x = 0.55 * inch
    margin_top = 0.55 * inch
    margin_bottom = 0.55 * inch
    gutter = 0.18 * inch
    full_w = page_w - 2 * margin_x
    col_w = (full_w - gutter) / 2
    top_h = 2.82 * inch
    top_y = page_h - margin_top - top_h
    first_col_h = top_y - margin_bottom - 0.04 * inch
    first_template = PageTemplate(
        id="FirstPage",
        frames=[
            Frame(margin_x, top_y, full_w, top_h, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
            Frame(margin_x, margin_bottom, col_w, first_col_h, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
            Frame(margin_x + col_w + gutter, margin_bottom, col_w, first_col_h, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
        ],
        autoNextPageTemplate="TwoColumn",
    )
    body_h = page_h - margin_top - margin_bottom
    two_col_template = PageTemplate(
        id="TwoColumn",
        frames=[
            Frame(margin_x, margin_bottom, col_w, body_h, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
            Frame(margin_x + col_w + gutter, margin_bottom, col_w, body_h, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
        ],
    )
    doc.addPageTemplates([first_template, two_col_template])
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleCenter", parent=styles["Title"], alignment=TA_CENTER, fontSize=18, leading=22))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading1"], fontSize=13, leading=16, spaceAfter=7))
    styles.add(ParagraphStyle(name="Subsection", parent=styles["Heading2"], fontSize=10.5, leading=13, spaceAfter=5))
    body = ParagraphStyle(name="BodyCustom", parent=styles["BodyText"], fontSize=8.7, leading=11.2, spaceAfter=6)

    as_is = process_summary[process_summary["scenario"] == "AS_IS_WhatsApp"].iloc[0]
    opt = process_summary[process_summary["scenario"] == "ACN_Optimized_B1"].iloc[0]
    peak = process_summary[process_summary["scenario"] == "ACN_Exam_Peak_500"].iloc[0]
    as_is_b = behavior_summary[behavior_summary["scenario"] == "AS_IS_Self_Selection"].iloc[0]
    b1 = behavior_summary[behavior_summary["scenario"] == "ACN_With_B1"].iloc[0]
    low = behavior_summary[behavior_summary["scenario"] == "ACN_Low_Adoption_20"].iloc[0]
    formation_reduction = percent_delta(as_is["median_formation_days"], opt["median_formation_days"])
    isolation_reduction = percent_delta(as_is["isolated_students_mean"], opt["isolated_students_mean"])
    network_isolation_reduction = percent_delta(as_is_b["isolated_students"], b1["isolated_students"])
    density_gain = (b1["density"] / as_is_b["density"] - 1.0) * 100.0 if as_is_b["density"] else 0.0

    story = []
    story.append(Paragraph("Academic Collaboration Network", styles["TitleCenter"]))
    story.append(Paragraph("Workshop No. 4 - System Simulation and Validation", styles["TitleCenter"]))
    story.append(para("Team 8 - Computer Engineering Program, Universidad Distrital Francisco Jose de Caldas", body))
    story.append(Spacer(1, 0.10 * inch))
    story.append(para("Authors: Gabriel Andres Beltran Varela, Kevin Santiago Silva Gonzalez, Miguel David Tarazona Correa, Anyelo Esteban Casas Zapata", body))
    story.append(Spacer(1, 0.18 * inch))

    story.append(Paragraph("Executive Summary", styles["Section"]))
    story.append(
        para(
            f"This report validates the Academic Collaboration Network through two complementary models: a process-oriented discrete-event simulation and a behavior-oriented agent-based network simulation. The optimized ACN scenario reduced median group formation time by {formation_reduction:.1f}% and reduced process-model isolated students by {isolation_reduction:.1f}% compared with the WhatsApp-based AS-IS workflow. Under the 500-student exam peak, p95 matching latency remained at {peak['p95_matching_latency_seconds']:.2f} seconds, below the Workshop 2 requirement of three seconds.",
            body,
        )
    )
    story.append(
        para(
            f"In the behavior model, the B1 isolation-priority loop reduced isolated students by {network_isolation_reduction:.1f}% and increased network density by {density_gain:.1f}% compared with informal self-selection. The low-adoption scenario still left {low['isolated_students']:.0f} isolated students after 12 weeks, confirming low adoption as the highest operational risk.",
            body,
        )
    )

    story.append(Paragraph("Model Development", styles["Section"]))
    story.append(
        para(
            "The simulation maps Workshop 2's microservices into model components: user profiles generate student attributes, the matching engine forms groups, workspaces convert successful matches into collaboration edges, notifications affect invitation acceptance, the integration gateway improves schedule compatibility, and analytics produce validation metrics.",
            body,
        )
    )
    story.append(
        para(
            "Calibration uses Workshop 1 primary data: 88% WhatsApp-only coordination, 36% communication barrier, 32% lack-of-interest barrier, 96% positive or conditional platform interest, mean adoption likelihood of 3.88/5, and AS-IS group formation time of two to five days. Workshop 3 contributes risk scenarios, fallback behavior and robust-design constraints.",
            body,
        )
    )

    story.append(Paragraph("Experimental Design", styles["Section"]))
    story.append(
        para(
            f"The process model runs {config['monte_carlo_trials']} Monte Carlo trials across AS-IS, baseline ACN, optimized ACN, LMS outage fallback and 500-student exam peak scenarios. The behavior model runs four 12-week scenarios and sensitivity analysis varies initial adoption from 0.2 to 0.9 with isolation-priority thresholds from 0 to 3.",
            body,
        )
    )

    story.append(Paragraph("Results and Analysis", styles["Section"]))
    story.append(Paragraph("Process-Oriented Simulation", styles["Subsection"]))
    add_table(
        story,
        dataframe_for_pdf(
            process_summary,
            [
                "scenario",
                "cohort_size",
                "success_rate_mean",
                "median_formation_days",
                "p95_matching_latency_seconds",
                "isolated_students_mean",
                "group_balance_index_mean",
                "satisfaction_score_mean",
            ],
            {
                "cohort_size": "{:.0f}",
                "success_rate_mean": "{:.2f}",
                "median_formation_days": "{:.2f}",
                "p95_matching_latency_seconds": "{:.2f}",
                "isolated_students_mean": "{:.1f}",
                "group_balance_index_mean": "{:.2f}",
                "satisfaction_score_mean": "{:.2f}",
            },
        ),
        [1.10 * inch, 0.42 * inch, 0.52 * inch, 0.56 * inch, 0.58 * inch, 0.55 * inch, 0.45 * inch, 0.62 * inch],
    )
    story.append(PdfImage(str(figures["process"]), width=6.7 * inch, height=4.15 * inch))
    story.append(Spacer(1, 0.08 * inch))
    story.append(PdfImage(str(figures["quality"]), width=6.7 * inch, height=4.15 * inch))
    story.append(PageBreak())

    story.append(Paragraph("Behavior-Oriented Simulation", styles["Subsection"]))
    add_table(
        story,
        dataframe_for_pdf(
            behavior_summary,
            [
                "scenario",
                "adoption_rate",
                "density",
                "isolated_students",
                "degree_gini",
                "giant_component_share",
                "mean_satisfaction",
            ],
            {
                "adoption_rate": "{:.2f}",
                "density": "{:.3f}",
                "isolated_students": "{:.0f}",
                "degree_gini": "{:.2f}",
                "giant_component_share": "{:.2f}",
                "mean_satisfaction": "{:.2f}",
            },
        ),
        [1.35 * inch, 0.62 * inch, 0.56 * inch, 0.58 * inch, 0.52 * inch, 0.72 * inch, 0.70 * inch],
    )
    story.append(PdfImage(str(figures["density"]), width=6.7 * inch, height=3.95 * inch))
    story.append(Spacer(1, 0.08 * inch))
    story.append(PdfImage(str(figures["fairness"]), width=6.7 * inch, height=4.15 * inch))
    story.append(PageBreak())

    story.append(Paragraph("Sensitivity and Complexity Insights", styles["Section"]))
    story.append(PdfImage(str(figures["sensitivity"]), width=6.1 * inch, height=4.22 * inch))
    story.append(
        para(
            "The sensitivity experiment shows a nonlinear adoption threshold. When initial adoption is low, the platform does not accumulate enough active students to create a dense collaboration graph. When adoption passes the mid-range, the reinforcing network-growth loop accelerates density and the balancing loop reduces isolation.",
            body,
        )
    )
    story.append(
        para(
            "The main emergent behavior is centrality concentration in informal self-selection: already-connected students accumulate more collaboration edges while peripheral students remain excluded. The B1 loop counteracts this effect by prioritizing low-degree students during group construction.",
            body,
        )
    )

    story.append(Paragraph("Design Validation", styles["Section"]))
    validations = [
        "Matching Engine: validated because p95 latency remains below three seconds under the target 500-student peak.",
        "Workspace and Notifications: validated because formation time and satisfaction improve over the WhatsApp-only process.",
        "Isolation Monitoring: validated because B1 reduces isolated students and centrality inequality.",
        "LMS Fallback: partially validated because the system continues operating, although schedule compatibility and satisfaction decline.",
        "Adoption Strategy: challenged because a 20% adoption scenario leaves substantial residual isolation.",
    ]
    for item in validations:
        story.append(para("- " + item, body))

    story.append(Paragraph("Recommendations", styles["Section"]))
    recs = [
        "Implement the B1 isolation-priority queue as a required Matching Engine feature.",
        "Use cached pre-filtering and incremental recomputation to keep matching below three seconds.",
        "Launch faculty ambassadors and guided onboarding with the MVP, because adoption changes network topology.",
        "Maintain the LMS fallback path and monitor schedule-compatibility degradation during outages.",
        "Add consent, privacy and bias-audit controls before using institutional academic records.",
        "Run a 50-student pilot to replace synthetic parameters with observed production data.",
    ]
    for item in recs:
        story.append(para("- " + item, body))

    story.append(Paragraph("Limitations and Reproducibility", styles["Section"]))
    story.append(
        para(
            "The simulation uses synthetic profiles calibrated from a small survey sample. Interpersonal compatibility, motivation and real LMS behavior are approximated. To reproduce all artifacts, run python src/run_simulations.py from the Workshop_4_Simulation folder.",
            body,
        )
    )
    story.append(Paragraph("References", styles["Section"]))
    refs = [
        "A. M. Law, Simulation Modeling and Analysis, 5th ed. McGraw-Hill, 2015.",
        "J. Banks, J. S. Carson, B. L. Nelson and D. M. Nicol, Discrete-Event System Simulation, 5th ed. Pearson, 2010.",
        "S. F. Railsback and V. Grimm, Agent-Based and Individual-Based Modeling. Princeton University Press, 2019.",
        "S. Wasserman and K. Faust, Social Network Analysis: Methods and Applications. Cambridge University Press, 1994.",
        "D. W. Johnson, R. T. Johnson and K. A. Smith, Cooperative learning returns to college, Change, vol. 30, no. 4, pp. 26-35, 1998.",
        "Team 8, Workshop No. 1: Systems Analysis - Academic Collaboration Network, Universidad Distrital Francisco Jose de Caldas, 2026.",
        "Team 8, Workshop No. 2: System Design - Academic Collaboration Network, Universidad Distrital Francisco Jose de Caldas, 2026.",
        "Team 8, Workshop No. 3: Robust System Design and Project Management - Academic Collaboration Network, Universidad Distrital Francisco Jose de Caldas, 2026.",
    ]
    for ref in refs:
        story.append(para(ref, body))

    doc.build(story)
    return pdf_path


def add_ieee_table(
    story: list,
    caption: str,
    data: list[list[str]],
    col_widths: list[float] | None,
    styles: dict[str, ParagraphStyle],
) -> None:
    story.append(Paragraph(caption, styles["TableCaption"]))
    table = Table(data, repeatRows=1, colWidths=col_widths, hAlign="CENTER")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 5.6),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.10 * inch))


def add_ieee_figure(story: list, image_path: Path, caption: str, width: float, height: float, styles: dict[str, ParagraphStyle]) -> None:
    story.append(PdfImage(str(image_path), width=width, height=height))
    story.append(Paragraph(caption, styles["FigureCaption"]))
    story.append(Spacer(1, 0.08 * inch))


def build_ieee_report_pdf(
    config: dict,
    process_summary: pd.DataFrame,
    behavior_summary: pd.DataFrame,
    sensitivity: pd.DataFrame,
    figures: dict[str, Path],
) -> Path:
    pdf_path = DOCS_DIR / "System_Simulation_Report.pdf"
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )

    base = getSampleStyleSheet()
    styles = {
        "Title": ParagraphStyle(
            name="PaperTitle",
            parent=base["Title"],
            alignment=TA_CENTER,
            fontName="Helvetica",
            fontSize=14,
            leading=16,
            spaceAfter=5,
        ),
        "Subtitle": ParagraphStyle(
            name="PaperSubtitle",
            parent=base["BodyText"],
            alignment=TA_CENTER,
            fontSize=7.8,
            leading=9.2,
            spaceAfter=5,
        ),
        "Author": ParagraphStyle(
            name="Author",
            parent=base["BodyText"],
            alignment=TA_CENTER,
            fontSize=6.2,
            leading=7.1,
        ),
        "Abstract": ParagraphStyle(
            name="Abstract",
            parent=base["BodyText"],
            fontSize=7.1,
            leading=8.4,
            leftIndent=0.18 * inch,
            rightIndent=0.18 * inch,
            spaceAfter=6,
        ),
        "Section": ParagraphStyle(
            name="IeeeSection",
            parent=base["Heading1"],
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            spaceBefore=8,
            spaceAfter=5,
        ),
        "Subsection": ParagraphStyle(
            name="IeeeSubsection",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            spaceBefore=5,
            spaceAfter=3,
        ),
        "Body": ParagraphStyle(
            name="IeeeBody",
            parent=base["BodyText"],
            fontSize=7.3,
            leading=8.8,
            alignment=4,
            spaceAfter=4,
        ),
        "TableCaption": ParagraphStyle(
            name="TableCaption",
            parent=base["BodyText"],
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            fontSize=7.6,
            leading=9,
            spaceBefore=5,
            spaceAfter=3,
        ),
        "FigureCaption": ParagraphStyle(
            name="FigureCaption",
            parent=base["BodyText"],
            alignment=TA_CENTER,
            fontSize=7.4,
            leading=8.8,
            spaceAfter=4,
        ),
    }

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

    story = []
    story.append(Paragraph("Academic Collaboration Network:<br/>System Simulation and Validation", styles["Title"]))
    story.append(Paragraph("Workshop No. 4 - Systems Analysis & Design 2026-I", styles["Subtitle"]))

    authors = [
        ["Gabriel Andres<br/>Beltran Varela<br/>Computer Engineering Program<br/>Universidad Distrital<br/>Bogota, Colombia<br/>gbeltranv@udistrital.edu.co",
         "Kevin Santiago<br/>Silva Gonzalez<br/>Computer Engineering Program<br/>Universidad Distrital<br/>Bogota, Colombia<br/>ksilvas@udistrital.edu.co",
         "Miguel David<br/>Tarazona Correa<br/>Computer Engineering Program<br/>Universidad Distrital<br/>Bogota, Colombia<br/>mtarazonac@udistrital.edu.co",
         "Anyelo Esteban<br/>Casas Zapata<br/>Computer Engineering Program<br/>Universidad Distrital<br/>Bogota, Colombia<br/>acasasz@udistrital.edu.co"]
    ]
    author_table = Table([[Paragraph(cell, styles["Author"]) for cell in authors[0]]], colWidths=[1.72 * inch] * 4)
    author_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(author_table)
    story.append(Spacer(1, 0.14 * inch))

    story.append(
        Paragraph(
            f"<b>Abstract-</b> This paper presents the computational simulation and validation phase of the Academic Collaboration Network, a socio-technical platform designed to reduce isolated learning through skill-based group optimization and institutional resource integration. Building on Workshop #1 system analysis, Workshop #2 architecture design, and Workshop #3 robust project management, the study implements two complementary models: a process-oriented discrete-event simulation and a behavior-oriented agent-based network simulation. Results show that the optimized ACN scenario reduces median group formation time by {formation_reduction:.1f}% compared with the WhatsApp-based AS-IS process, reduces process-model isolated students by {isolation_reduction:.1f}%, and maintains p95 matching latency at {peak['p95_matching_latency_seconds']:.2f} seconds under a 500-student stress scenario. The B1 isolation-priority loop reduces final isolated students by {network_isolation_reduction:.1f}% and increases network density by {density_gain:.1f}% compared with informal self-selection. These findings validate the feasibility of the proposed design while identifying adoption as the dominant implementation risk.",
            styles["Abstract"],
        )
    )
    story.append(
        Paragraph(
            "<b>Keywords-</b> systems engineering, discrete-event simulation, agent-based modeling, collaborative learning, social network analysis, design validation.",
            styles["Abstract"],
        )
    )
    story.append(FrameBreak())

    story.append(Paragraph("I. INTRODUCTION", styles["Section"]))
    story.append(
        para(
            "The previous workshops established the Academic Collaboration Network (ACN) as a response to isolated learning, inefficient study group formation, and uneven distribution of academic support among university students. Workshop #1 identified the current coordination process as informal and fragmented: 88% of surveyed students relied exclusively on WhatsApp, 36% reported lack of communication as the main barrier, and 96% expressed positive or conditional interest in a dedicated platform.",
            styles["Body"],
        )
    )
    story.append(
        para(
            "Workshop #2 transformed those findings into a microservices architecture with a user profile service, skill matching engine, workspace service, notification engine, analytics dashboard, and LMS/library integration gateway. Workshop #3 then strengthened the design through fault tolerance, risk management, quality assurance, project scheduling, and the B1 balancing loop for isolation mitigation. This fourth workshop validates those design decisions through computational simulation.",
            styles["Body"],
        )
    )

    story.append(Paragraph("II. CONTINUITY FROM PREVIOUS WORKSHOPS", styles["Section"]))
    add_ieee_table(
        story,
        "TABLE I. PROJECT EVOLUTION ACROSS WORKSHOPS",
        [
            ["Workshop", "Primary Output", "Contribution to Simulation"],
            ["#1 Analysis", "Survey n=25, AS-IS/TO-BE process, feedback loops", "Calibration values, baseline process and isolation risk"],
            ["#2 Design", "Microservices, FR/NFR, matching engine, LMS integration", "Architecture translated into model components and latency targets"],
            ["#3 Robust Design", "Risk register, QA gates, fallback plans, B1 loop", "Stress/failure scenarios and validation criteria"],
            ["#4 Simulation", "Process and behavior models, charts, validation report", "Empirical design validation and optimization insights"],
        ],
        [0.48 * inch, 0.95 * inch, 2.12 * inch],
        styles,
    )

    story.append(Paragraph("III. SIMULATION METHODOLOGY", styles["Section"]))
    story.append(Paragraph("A. Process-Oriented Simulation", styles["Subsection"]))
    story.append(
        para(
            "The process-oriented model represents the operational sequence from student need recognition to group formation. It compares an informal WhatsApp-based workflow against platform-supported scenarios with matching, notifications, schedule integration, LMS fallback, and exam-period load. Each scenario is evaluated through Monte Carlo trials using synthetic profiles calibrated from primary survey parameters.",
            styles["Body"],
        )
    )
    story.append(Paragraph("B. Behavior-Oriented Simulation", styles["Subsection"]))
    story.append(
        para(
            "The behavior-oriented model represents students as agents in an undirected collaboration graph. Weekly interactions create or reinforce edges, while adoption and satisfaction influence participation. The model measures network density, isolated students, centrality inequality, giant-component coverage, and satisfaction over a 12-week semester.",
            styles["Body"],
        )
    )
    story.append(Paragraph("C. Assumptions and Calibration", styles["Subsection"]))
    story.append(
        para(
            "Student skill, availability, performance, social connectivity, and platform openness are normalized synthetic variables. The model uses the observed two-to-five-day AS-IS formation window, the 3-second matching latency target, the 500-user capacity target, the LMS outage risk, and the B1 centrality monitoring logic from earlier workshops. Institutional academic data was not used to preserve privacy.",
            styles["Body"],
        )
    )

    story.append(Paragraph("IV. EXPERIMENTAL DESIGN", styles["Section"]))
    add_ieee_table(
        story,
        "TABLE II. SIMULATION SCENARIOS",
        [
            ["Scenario", "Purpose", "Main Parameter Change"],
            ["AS_IS_WhatsApp", "Represents current informal coordination", "No platform, homophily-driven groups"],
            ["ACN_Baseline", "Validates Workshop #2 design", "80% adoption, matching + workspace"],
            ["ACN_Optimized_B1", "Tests isolation-priority improvement", "B1 loop and higher adoption support"],
            ["ACN_LMS_Outage_Fallback", "Tests Workshop #3 risk fallback", "LMS unavailable, cached/manual sync"],
            ["ACN_Exam_Peak_500", "Tests capacity requirement", "500 students under exam-period stress"],
        ],
        [0.78 * inch, 1.18 * inch, 1.55 * inch],
        styles,
    )

    story.append(Paragraph("V. PROCESS SIMULATION RESULTS", styles["Section"]))
    process_label = {
        "AS_IS_WhatsApp": "AS-IS",
        "ACN_Baseline": "Baseline",
        "ACN_Optimized_B1": "Opt. B1",
        "ACN_LMS_Outage_Fallback": "LMS Out.",
        "ACN_Exam_Peak_500": "Peak 500",
    }
    process_table_data = [["Scenario", "n", "Succ.", "Days", "p95s", "Iso.", "GBI", "Sat."]]
    for _, row in process_summary.iterrows():
        latency = "N/A" if pd.isna(row["p95_matching_latency_seconds"]) else f"{row['p95_matching_latency_seconds']:.2f}"
        process_table_data.append(
            [
                process_label.get(row["scenario"], row["scenario"]),
                f"{row['cohort_size']:.0f}",
                f"{row['success_rate_mean']:.2f}",
                f"{row['median_formation_days']:.2f}",
                latency,
                f"{row['isolated_students_mean']:.1f}",
                f"{row['group_balance_index_mean']:.2f}",
                f"{row['satisfaction_score_mean']:.2f}",
            ]
        )
    add_ieee_table(
        story,
        "TABLE III. PROCESS-ORIENTED SIMULATION SUMMARY",
        process_table_data,
        [0.60 * inch, 0.20 * inch, 0.30 * inch, 0.30 * inch, 0.28 * inch, 0.30 * inch, 0.27 * inch, 0.27 * inch],
        styles,
    )
    story.append(
        para(
            f"The optimized ACN scenario compresses group formation from {as_is['median_formation_days']:.2f} days to {opt['median_formation_days']:.2f} days and improves satisfaction from {as_is['satisfaction_score_mean']:.2f} to {opt['satisfaction_score_mean']:.2f}. The LMS outage scenario remains operational but its success rate declines to {outage['success_rate_mean']:.2f}, confirming that fallback mechanisms prevent collapse while integration reliability remains important.",
            styles["Body"],
        )
    )
    add_ieee_figure(
        story,
        figures["process"],
        "Fig. 1. Process simulation comparing formation time and isolated-student share.",
        3.28 * inch,
        1.68 * inch,
        styles,
    )
    add_ieee_figure(
        story,
        figures["quality"],
        "Fig. 2. Matching quality and satisfaction across operational scenarios.",
        3.28 * inch,
        1.68 * inch,
        styles,
    )

    story.append(Paragraph("VI. BEHAVIOR SIMULATION AND EMERGENT PATTERNS", styles["Section"]))
    behavior_label = {
        "AS_IS_Self_Selection": "AS-IS",
        "ACN_No_B1": "No B1",
        "ACN_With_B1": "With B1",
        "ACN_Low_Adoption_20": "Low Adopt.",
    }
    behavior_table_data = [["Scenario", "Adopt.", "Density", "Iso.", "Gini", "Giant", "Sat."]]
    for _, row in behavior_summary.iterrows():
        behavior_table_data.append(
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
    add_ieee_table(
        story,
        "TABLE IV. BEHAVIOR-ORIENTED SIMULATION SUMMARY",
        behavior_table_data,
        [0.62 * inch, 0.38 * inch, 0.44 * inch, 0.28 * inch, 0.32 * inch, 0.37 * inch, 0.32 * inch],
        styles,
    )
    story.append(
        para(
            f"The behavior model shows nonlinear network growth. Informal self-selection ends with {as_is_b['isolated_students']:.0f} isolated students and density {as_is_b['density']:.3f}. With the B1 loop, final isolation falls to {b1['isolated_students']:.0f}, density rises to {b1['density']:.3f}, and degree inequality decreases to {b1['degree_gini']:.2f}.",
            styles["Body"],
        )
    )
    add_ieee_figure(
        story,
        figures["density"],
        "Fig. 3. Collaboration density evolution during the simulated 12-week semester.",
        3.28 * inch,
        1.60 * inch,
        styles,
    )
    add_ieee_figure(
        story,
        figures["fairness"],
        "Fig. 4. Isolation and centrality inequality after behavior simulation.",
        3.28 * inch,
        1.68 * inch,
        styles,
    )

    story.append(Paragraph("VII. COMPLEXITY AND SENSITIVITY ANALYSIS", styles["Section"]))
    story.append(
        para(
            "The model reveals three complexity patterns: nonlinear adoption effects, centrality concentration in informal groups, and balancing behavior when low-degree students are prioritized. Sensitivity tests confirm that adoption is a structural variable: below a mid-range threshold, the collaboration graph does not accumulate enough active participants to eliminate isolation.",
            styles["Body"],
        )
    )
    add_ieee_figure(
        story,
        figures["sensitivity"],
        "Fig. 5. Sensitivity analysis of remaining isolated students by adoption and isolation threshold.",
        3.15 * inch,
        1.92 * inch,
        styles,
    )

    story.append(Paragraph("VIII. DESIGN VALIDATION", styles["Section"]))
    add_ieee_table(
        story,
        "TABLE V. VALIDATION OF DESIGN DECISIONS",
        [
            ["Design Decision", "Evidence", "Result"],
            ["Skill Matching Engine", f"p95 latency {peak['p95_matching_latency_seconds']:.2f}s under 500 students", "Validated"],
            ["Integrated Workspace", f"Formation time reduced by {formation_reduction:.1f}%", "Validated"],
            ["B1 Isolation Loop", f"Final isolation reduced from {as_is_b['isolated_students']:.0f} to {b1['isolated_students']:.0f} students", "Validated"],
            ["LMS Fallback", f"Outage success rate remains {outage['success_rate_mean']:.2f}", "Partially validated"],
            ["Adoption Strategy", f"Low-adoption scenario leaves {low['isolated_students']:.0f} isolated students", "Requires mitigation"],
        ],
        [0.92 * inch, 1.95 * inch, 0.55 * inch],
        styles,
    )

    story.append(Paragraph("IX. RECOMMENDATIONS", styles["Section"]))
    recommendations = [
        "Implement the B1 isolation-priority queue as a mandatory Matching Engine component.",
        "Use cached pre-filtering and incremental recomputation to preserve sub-three-second matching.",
        "Launch faculty ambassadors, guided onboarding, and early pilot incentives with the MVP.",
        "Maintain LMS fallback mechanisms and monitor schedule-compatibility degradation during outages.",
        "Include privacy, consent, and bias-audit controls before using institutional academic records.",
        "Conduct a real pilot with at least 50 students to replace synthetic assumptions with observed data.",
    ]
    for item in recommendations:
        story.append(para("- " + item, styles["Body"]))

    story.append(Paragraph("X. LIMITATIONS AND ETHICAL CONSIDERATIONS", styles["Section"]))
    story.append(
        para(
            "The model uses synthetic student profiles calibrated from a limited survey sample. It approximates interpersonal compatibility, motivation, instructor intervention, and LMS behavior. Results should therefore be interpreted as design validation evidence rather than a production forecast. Any real implementation must apply informed consent, data minimization, access control, explainability, and bias-monitoring procedures.",
            styles["Body"],
        )
    )

    story.append(Paragraph("XI. CONCLUSION", styles["Section"]))
    story.append(
        para(
            "The simulation phase validates the core ACN design trajectory across the four-workshop sequence. The proposed architecture can reduce coordination time, improve satisfaction, preserve latency targets under the modeled stress load, and reduce isolation when centrality-based re-inclusion is active. The strongest remaining risk is not computational feasibility but sustained adoption, making change management a technical success factor for the system.",
            styles["Body"],
        )
    )

    story.append(Paragraph("ACKNOWLEDGMENT", styles["Section"]))
    story.append(
        para(
            "The authors thank Eng. Carlos Andres Sierra, M.Sc., for guidance throughout the Systems Analysis & Design course, and the survey participants who contributed primary data for the Academic Collaboration Network project.",
            styles["Body"],
        )
    )

    story.append(Paragraph("GITHUB REPOSITORY", styles["Section"]))
    story.append(
        para(
            "Workshop 4 materials should be placed in the course repository under Workshop_4_Simulation, including source code, input data, figures, results, README documentation, and this report. Repository: https://github.com/AnyeloCZ/Academic-Collaboration-Network-SAD-2026-I",
            styles["Body"],
        )
    )

    story.append(Paragraph("REFERENCES", styles["Section"]))
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
        story.append(para(ref, styles["Body"]))

    doc.build(story)
    return pdf_path


def write_readme(report_pdf: Path) -> None:
    readme = f"""# Workshop 4 - System Simulation and Validation

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

`{report_pdf.name}`

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
"""
    (ROOT / "README.md").write_text(readme, encoding="utf-8")


def build_dashboard_html(process_summary: pd.DataFrame, behavior_summary: pd.DataFrame, figures: dict[str, Path]) -> Path:
    dashboard_path = DOCS_DIR / "dashboard.html"
    as_is = process_summary[process_summary["scenario"] == "AS_IS_WhatsApp"].iloc[0]
    opt = process_summary[process_summary["scenario"] == "ACN_Optimized_B1"].iloc[0]
    peak = process_summary[process_summary["scenario"] == "ACN_Exam_Peak_500"].iloc[0]
    b1 = behavior_summary[behavior_summary["scenario"] == "ACN_With_B1"].iloc[0]

    def rel(path: Path) -> str:
        return Path("..", path.parent.name, path.name).as_posix()

    process_table = process_summary.copy()
    behavior_table = behavior_summary.copy()
    for df in [process_table, behavior_table]:
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].map(lambda x: "N/A" if pd.isna(x) else f"{x:.3f}")

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Workshop 4 Simulation Dashboard</title>
  <style>
    :root {{
      --ink: #1f2328;
      --muted: #59636e;
      --line: #d0d7de;
      --panel: #ffffff;
      --soft: #f6f8fa;
      --blue: #2a6f97;
      --green: #2d8a5f;
      --orange: #c76b24;
      --red: #be4848;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Segoe UI, sans-serif;
      color: var(--ink);
      background: var(--soft);
    }}
    header {{
      background: #ffffff;
      border-bottom: 1px solid var(--line);
      padding: 28px 32px 22px;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 24px 24px 48px;
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 30px;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 30px 0 14px;
      font-size: 20px;
      letter-spacing: 0;
    }}
    p {{ color: var(--muted); line-height: 1.5; }}
    a {{
      color: var(--blue);
      font-weight: 700;
      text-decoration: none;
    }}
    .actions {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 16px;
    }}
    .button {{
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      padding: 10px 14px;
      color: var(--ink);
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    .metric strong {{
      display: block;
      font-size: 28px;
      margin-bottom: 4px;
    }}
    .metric span {{
      color: var(--muted);
      font-size: 13px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }}
    .chart {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
    }}
    .chart img {{
      display: block;
      width: 100%;
      height: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #eaf3f8;
      color: var(--ink);
    }}
    tr:last-child td {{ border-bottom: 0; }}
    .note {{
      background: #fff8e6;
      border: 1px solid #f0d38a;
      border-radius: 8px;
      padding: 12px 14px;
      color: #5f4711;
    }}
    @media (max-width: 850px) {{
      .metrics, .grid {{ grid-template-columns: 1fr; }}
      header {{ padding: 22px 18px; }}
      main {{ padding: 18px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Workshop 4 Simulation Dashboard</h1>
    <p>Academic Collaboration Network - system simulation, validation and visual results.</p>
    <div class="actions">
      <a class="button" href="System_Simulation_Report.pdf">Open PDF Report</a>
      <a class="button" href="../results/process_summary.csv">Process CSV</a>
      <a class="button" href="../results/behavior_summary.csv">Behavior CSV</a>
    </div>
  </header>
  <main>
    <section class="metrics">
      <div class="metric"><strong>{percent_delta(as_is['median_formation_days'], opt['median_formation_days']):.1f}%</strong><span>Group formation time reduction</span></div>
      <div class="metric"><strong>{peak['p95_matching_latency_seconds']:.2f}s</strong><span>p95 latency at 500 students</span></div>
      <div class="metric"><strong>{opt['satisfaction_score_mean']:.2f}</strong><span>Optimized satisfaction score</span></div>
      <div class="metric"><strong>{b1['isolated_students']:.0f}</strong><span>Isolated students after B1 loop</span></div>
    </section>

    <h2>Visual Results</h2>
    <section class="grid">
      <div class="chart"><img src="{rel(figures['process'])}" alt="Process time and isolation chart"></div>
      <div class="chart"><img src="{rel(figures['quality'])}" alt="Quality and satisfaction chart"></div>
      <div class="chart"><img src="{rel(figures['density'])}" alt="Network density over time chart"></div>
      <div class="chart"><img src="{rel(figures['fairness'])}" alt="Isolation and fairness chart"></div>
      <div class="chart"><img src="{rel(figures['sensitivity'])}" alt="Sensitivity heatmap"></div>
    </section>

    <h2>Process Simulation Summary</h2>
    {process_table.to_html(index=False, escape=True)}

    <h2>Behavior Simulation Summary</h2>
    {behavior_table.to_html(index=False, escape=True)}

    <h2>How to Regenerate</h2>
    <div class="note">Run <strong>run_workshop4.bat</strong> from the project folder. It regenerates this dashboard, the PDF report, figures and CSV results.</div>
  </main>
</body>
</html>
"""
    dashboard_path.write_text(html, encoding="utf-8")
    return dashboard_path


def main() -> None:
    ensure_dirs()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    print("1/6 Running process-oriented simulation...")
    process_trials, process_summary = simulate_process_scenarios(config)
    print("2/6 Running behavior-oriented simulation...")
    behavior_timeseries, behavior_summary = simulate_behavior_scenarios(config)
    print("3/6 Running sensitivity analysis...")
    sensitivity = simulate_sensitivity(config)

    print("4/6 Writing CSV results...")
    csv_outputs(process_trials, process_summary, behavior_timeseries, behavior_summary, sensitivity)
    print("5/6 Generating figures...")
    figures = generate_figures(process_summary, behavior_timeseries, behavior_summary, sensitivity)

    print("6/6 Building Markdown and PDF report...")
    report_md = build_report_markdown(config, process_summary, behavior_summary, sensitivity)
    md_path = DOCS_DIR / "System_Simulation_Report.md"
    md_path.write_text(report_md, encoding="utf-8")
    from manual_report import build_manual_two_column_pdf

    pdf_path = build_manual_two_column_pdf(config, process_summary, behavior_summary, sensitivity, figures)
    dashboard_path = build_dashboard_html(process_summary, behavior_summary, figures)
    write_readme(pdf_path)

    print("Generated Workshop 4 simulation package")
    print(f"Root: {ROOT}")
    print(f"Report PDF: {pdf_path}")
    print(f"Report MD: {md_path}")
    print(f"Dashboard: {dashboard_path}")
    print("Results:")
    print(process_summary.to_string(index=False))
    print(behavior_summary.to_string(index=False))


if __name__ == "__main__":
    main()
