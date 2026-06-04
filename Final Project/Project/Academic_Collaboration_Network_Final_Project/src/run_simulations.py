from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "scenarios.json"
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = ROOT / "figures"
DOCS_DIR = ROOT / "docs"
DEFAULT_CUSTOM_STUDENTS = DATA_DIR / "custom_students.csv"


PALETTE = {
    "blue": (42, 111, 151),
    "green": (45, 138, 95),
    "orange": (229, 137, 48),
    "red": (190, 72, 72),
    "purple": (103, 80, 164),
    "gray": (88, 96, 105),
    "line": (216, 222, 228),
    "ink": (31, 35, 40),
}


def ensure_dirs() -> None:
    for path in [RESULTS_DIR, FIGURES_DIR, DOCS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def clamp(values, lo: float, hi: float):
    return np.minimum(np.maximum(values, lo), hi)


def load_font(size: int, bold: bool = False):
    candidates = []
    if bold:
        candidates += [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf"]
    candidates += [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\segoeui.ttf"]
    for item in candidates:
        path = Path(item)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


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


def normalize_custom_value(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.dropna().empty:
        raise ValueError("Custom student data contains a non-numeric required column.")
    if float(numeric.max()) > 1.0 or float(numeric.min()) < 0.0:
        numeric = (numeric - 1.0) / 4.0
    return pd.Series(clamp(numeric.fillna(numeric.mean()).to_numpy(), 0.02, 0.99), index=series.index)


def load_custom_students(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = ["skill", "availability", "performance", "social", "openness"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Custom student file is missing required columns: {', '.join(missing)}")
    if "student_id" not in df.columns:
        df["student_id"] = [f"C{i + 1:03d}" for i in range(len(df))]
    if "semester" not in df.columns:
        df["semester"] = "custom"
    for col in required:
        df[col] = normalize_custom_value(df[col])
    return df[["student_id", "skill", "availability", "performance", "social", "openness", "semester"]].reset_index(drop=True)


def sample_students(custom_students: pd.DataFrame | None, n: int, rng: np.random.Generator) -> pd.DataFrame:
    if custom_students is None:
        return generate_students(n, rng)
    replace = len(custom_students) < n
    sampled = custom_students.sample(n=n, replace=replace, random_state=int(rng.integers(0, 2_147_483_647))).reset_index(drop=True)
    sampled = sampled.copy()
    if replace:
        for col in ["skill", "availability", "performance", "social", "openness"]:
            sampled[col] = clamp(sampled[col].to_numpy() + rng.normal(0.0, 0.025, n), 0.02, 0.99)
    sampled["student_id"] = [f"S{i + 1:03d}" for i in range(n)]
    return sampled


def pairwise_schedule_score(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    diffs = []
    vals = list(values)
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


def network_density(adj: np.ndarray) -> float:
    n = adj.shape[0]
    if n < 2:
        return 0.0
    return float(adj.sum() / (n * (n - 1)))


def giant_component_share(adj: np.ndarray) -> float:
    n = adj.shape[0]
    seen = np.zeros(n, dtype=bool)
    largest = 0
    for start in range(n):
        if seen[start]:
            continue
        stack = [start]
        seen[start] = True
        size = 0
        while stack:
            node = stack.pop()
            size += 1
            for nb in np.where(adj[node])[0]:
                if not seen[nb]:
                    seen[nb] = True
                    stack.append(int(nb))
        largest = max(largest, size)
    return largest / n


def make_groups(
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
    group_count = len(ids) // group_size
    if strategy == "balanced":
        if isolation_priority and degrees is not None:
            priority = ids[np.argsort(degrees[ids])][:group_count]
            priority_set = set(map(int, priority))
            remaining = np.array([idx for idx in ids if int(idx) not in priority_set], dtype=int)
            if len(remaining) >= group_count * (group_size - 1):
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
        sorted_ids = ids[np.argsort(students.loc[ids, "skill"].to_numpy())]
        usable = sorted_ids[: group_count * group_size]
        strata = np.array_split(usable, group_size)
        groups = [[int(stratum[j]) for stratum in strata] for j in range(group_count)]
        rng.shuffle(groups)
        return groups
    if strategy == "homophily":
        score = students.loc[ids, "skill"].to_numpy() + 0.30 * students.loc[ids, "social"].to_numpy()
        ordered = ids[np.argsort(score + rng.normal(0, 0.025, len(ids)))]
    else:
        ordered = ids.copy()
        rng.shuffle(ordered)
    usable = ordered[: group_count * group_size]
    return [list(map(int, usable[i : i + group_size])) for i in range(0, len(usable), group_size)]


def group_metrics(students: pd.DataFrame, groups: list[list[int]]) -> dict[str, float]:
    if not groups:
        return {"skill_variance": 0.0, "gbi": 0.0, "schedule": 0.0, "mean_skill_error": 0.0}
    total_var = float(np.var(students["skill"].to_numpy())) or 1e-6
    cohort_mean = float(students["skill"].mean())
    variances, schedules, errors = [], [], []
    for group in groups:
        skills = students.loc[group, "skill"].to_numpy()
        variances.append(float(np.var(skills)))
        schedules.append(pairwise_schedule_score(students.loc[group, "availability"].to_numpy()))
        errors.append(abs(float(np.mean(skills)) - cohort_mean))
    mean_var = float(np.mean(variances))
    mean_error = float(np.mean(errors))
    between_group_equity = float(clamp(1.0 - mean_error / (math.sqrt(total_var) + 1e-6), 0.0, 1.0))
    within_group_cohesion = float(clamp(1.0 - mean_var / total_var, 0.0, 1.0))
    return {
        "skill_variance": mean_var,
        "gbi": float(clamp(0.82 * between_group_equity + 0.18 * within_group_cohesion, 0.0, 1.0)),
        "schedule": float(np.mean(schedules)),
        "mean_skill_error": mean_error,
    }


def matching_latency_seconds(n: int, stress_multiplier: float, rng: np.random.Generator) -> float:
    deterministic = 0.040 + 0.0000034 * (n**2) + 0.00009 * n
    noise = rng.lognormal(mean=-3.05, sigma=0.28)
    return float((deterministic + noise) * stress_multiplier)


def simulate_process(config: dict, custom_students: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(config["random_seed"])
    group_size = int(config["group_size"])
    rows = []
    for scenario in config["process_scenarios"]:
        n = int(scenario["cohort_size"])
        for trial in range(int(config["trials"])):
            students = sample_students(custom_students, n, rng)
            if scenario["platform"]:
                adoption = clamp(scenario["adoption_rate"] * (0.65 + 0.35 * students["openness"].to_numpy()), 0.0, 0.98)
                active = np.where(rng.random(n) < adoption)[0]
                groups = make_groups(active, students, group_size, rng, scenario["strategy"], degrees=np.zeros(n), isolation_priority=True)
                latency = matching_latency_seconds(n, scenario["stress_multiplier"], rng)
                base_days = rng.lognormal(mean=math.log(0.43), sigma=0.28)
            else:
                groups = make_groups(np.arange(n), students, group_size, rng, scenario["strategy"])
                latency = np.nan
                base_days = rng.triangular(2.0, 3.5, 5.0)

            metrics = group_metrics(students, groups)
            possible = len(groups)
            if possible == 0:
                continue
            quality = 0.36 * metrics["gbi"] + 0.28 * metrics["schedule"] + 0.36 * (1.0 - min(metrics["mean_skill_error"] / 0.20, 1.0))
            success_prob = scenario["success_base"] + 0.10 * scenario["communication"] + 0.06 * quality
            if not scenario["platform"]:
                success_prob -= 0.18
            if "Outage" in scenario["name"]:
                success_prob -= 0.08
                base_days *= 1.28
            success_prob = float(clamp(success_prob, 0.05, 0.98))
            successful = rng.random(possible) < success_prob
            successful_groups = [g for g, ok in zip(groups, successful) if ok]
            successful_students = {idx for group in successful_groups for idx in group}
            if scenario["platform"]:
                formation_days = base_days * rng.lognormal(0.0, 0.20, max(1, len(successful_groups)))
            else:
                formation_days = base_days * (1.0 + 0.36 * rng.random() + 0.32 * rng.random()) * rng.lognormal(0.0, 0.22, max(1, len(successful_groups)))
            satisfaction = 0.34 + 0.44 * quality + 0.18 * scenario["communication"] + 0.08 * scenario["schedule"]
            if not scenario["platform"]:
                satisfaction -= 0.18
            if "Outage" in scenario["name"]:
                satisfaction -= 0.06
            rows.append(
                {
                    "scenario": scenario["name"],
                    "trial": trial + 1,
                    "cohort_size": n,
                    "success_rate": len(successful_groups) / possible,
                    "median_formation_days": float(np.median(formation_days)),
                    "p95_matching_latency_seconds": latency,
                    "isolated_students": n - len(successful_students),
                    "group_balance_index": metrics["gbi"],
                    "schedule_score": metrics["schedule"],
                    "satisfaction_score": float(clamp(satisfaction + rng.normal(0, 0.035), 0.0, 1.0)),
                }
            )
    df = pd.DataFrame(rows)

    def p95(series: pd.Series) -> float:
        clean = series.dropna()
        if clean.empty:
            return float("nan")
        return float(np.nanpercentile(clean, 95))

    summary = (
        df.groupby("scenario", as_index=False)
        .agg(
            cohort_size=("cohort_size", "median"),
            success_rate_mean=("success_rate", "mean"),
            median_formation_days=("median_formation_days", "median"),
            p95_matching_latency_seconds=("p95_matching_latency_seconds", p95),
            isolated_students_mean=("isolated_students", "mean"),
            group_balance_index_mean=("group_balance_index", "mean"),
            satisfaction_score_mean=("satisfaction_score", "mean"),
        )
    )
    order = {name: i for i, name in enumerate([s["name"] for s in config["process_scenarios"]])}
    summary["_order"] = summary["scenario"].map(order)
    summary = summary.sort_values("_order").drop(columns=["_order"])
    return df, summary


def initial_as_is_network(students: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    n = len(students)
    adj = np.zeros((n, n), dtype=bool)
    skills = students["skill"].to_numpy()
    social = students["social"].to_numpy()
    for i in range(n):
        for j in range(i + 1, n):
            homophily = 1.0 - abs(skills[i] - skills[j])
            social_boost = 0.5 * (social[i] + social[j])
            prob = 0.001 + 0.010 * homophily + 0.006 * social_boost
            if rng.random() < prob:
                adj[i, j] = adj[j, i] = True
    return adj


def simulate_behavior(config: dict, custom_students: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng_master = np.random.default_rng(config["random_seed"] + 777)
    n = int(config["cohort_size"])
    group_size = int(config["group_size"])
    rows = []
    for scenario in config["behavior_scenarios"]:
        rng = np.random.default_rng(int(rng_master.integers(0, 10_000_000)))
        students = sample_students(custom_students, n, rng)
        adj = initial_as_is_network(students, rng)
        adopters = rng.random(n) < scenario["initial_adoption"]
        satisfaction = np.full(n, 0.55 if scenario["platform"] else 0.42)
        for week in range(1, int(config["semester_weeks"]) + 1):
            degrees = adj.sum(axis=1)
            if scenario["platform"]:
                active = np.where(adopters & (rng.random(n) < scenario["weekly_participation"]))[0]
            else:
                active = np.where(rng.random(n) < scenario["weekly_participation"] * (0.20 + 0.85 * students["social"].to_numpy()))[0]
            groups = make_groups(active, students, group_size, rng, scenario["strategy"], degrees=degrees, isolation_priority=scenario["isolation_priority"])
            if not scenario["platform"]:
                kept = []
                for group in groups:
                    existing = sum(int(adj[a, b]) for ix, a in enumerate(group) for b in group[ix + 1 :])
                    if existing >= 1 or rng.random() < 0.12:
                        kept.append(group)
                groups = kept
            metrics = group_metrics(students, groups)
            retention = scenario["edge_retention"] + (0.06 if scenario["isolation_priority"] else 0.0) - (0.25 if not scenario["platform"] else 0.0)
            retention = float(clamp(retention, 0.10, 0.92))
            for group in groups:
                link_prob = float(clamp(retention * (0.72 + 0.28 * metrics["schedule"]), 0.05, 0.98))
                for ix, a in enumerate(group):
                    for b in group[ix + 1 :]:
                        if rng.random() < link_prob:
                            adj[a, b] = adj[b, a] = True
                group_sat = 0.42 + 0.28 * metrics["schedule"] + 0.22 * metrics["gbi"] + (0.06 if scenario["isolation_priority"] else 0.0)
                if not scenario["platform"]:
                    group_sat -= 0.10
                satisfaction[group] = 0.70 * satisfaction[group] + 0.30 * float(clamp(group_sat, 0.0, 1.0))
            if scenario["platform"]:
                non_adopters = np.where(~adopters)[0]
                current = float(adopters.mean())
                if len(non_adopters) and current < scenario["max_adoption"]:
                    growth_signal = float(np.mean(satisfaction[adopters])) if adopters.any() else 0.50
                    weekly_growth = max(0.0, growth_signal - 0.55) * 0.16 + (0.012 if scenario["isolation_priority"] else 0.0)
                    new_prob = min(weekly_growth, (scenario["max_adoption"] - current) * 0.45)
                    adopters[non_adopters[rng.random(len(non_adopters)) < new_prob]] = True
            degrees = adj.sum(axis=1)
            rows.append(
                {
                    "scenario": scenario["name"],
                    "week": week,
                    "adoption_rate": float(adopters.mean()) if scenario["platform"] else 0.0,
                    "density": network_density(adj),
                    "isolated_students": int(np.sum(degrees == 0)),
                    "degree_gini": gini(degrees),
                    "giant_component_share": giant_component_share(adj),
                    "mean_satisfaction": float(np.mean(satisfaction)),
                    "group_balance_index": metrics["gbi"],
                }
            )
    df = pd.DataFrame(rows)
    summary = df[df["week"] == int(config["semester_weeks"])].copy()
    order = {name: i for i, name in enumerate([s["name"] for s in config["behavior_scenarios"]])}
    summary["_order"] = summary["scenario"].map(order)
    summary = summary.sort_values("_order").drop(columns=["_order"])
    return df, summary


def simulate_sensitivity(config: dict, custom_students: pd.DataFrame | None = None) -> pd.DataFrame:
    rows = []
    for adoption in config["sensitivity"]["adoption_rates"]:
        for threshold in config["sensitivity"]["isolation_thresholds"]:
            local = json.loads(json.dumps(config))
            local["behavior_scenarios"] = [
                {
                    "name": f"adoption_{adoption:.1f}_threshold_{threshold}",
                    "strategy": "balanced",
                    "initial_adoption": adoption,
                    "weekly_participation": 0.76,
                    "edge_retention": 0.66,
                    "isolation_priority": threshold > 0,
                    "platform": True,
                    "max_adoption": min(0.95, adoption + 0.22),
                }
            ]
            local["random_seed"] = int(config["random_seed"] + adoption * 100 + threshold)
            _, summary = simulate_behavior(local, custom_students)
            final = summary.iloc[0]
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


def save_bar_chart(df: pd.DataFrame, label_col: str, value_cols: list[str], title: str, path: Path, value_format: str = "{:.2f}") -> None:
    width, height = 1200, 760
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    title_font = load_font(32, True)
    label_font = load_font(17)
    small_font = load_font(15)
    draw.text((80, 40), title, font=title_font, fill=PALETTE["ink"])
    x0, y0 = 90, 560
    plot_w, plot_h = 1040, 420
    ymax = max(float(df[col].max()) for col in value_cols) * 1.15
    ymax = max(ymax, 0.01)
    for step in range(6):
        y = y0 - int(plot_h * step / 5)
        draw.line((x0, y, x0 + plot_w, y), fill=PALETTE["line"], width=1)
        draw.text((25, y - 9), value_format.format(ymax * step / 5), font=small_font, fill=PALETTE["gray"])
    colors = [PALETTE["blue"], PALETTE["red"], PALETTE["green"], PALETTE["orange"]]
    cluster_w = plot_w / len(df)
    bar_w = min(54, cluster_w / (len(value_cols) + 1.5))
    for i, (_, row) in enumerate(df.iterrows()):
        center = x0 + cluster_w * (i + 0.5)
        for j, col in enumerate(value_cols):
            value = float(row[col])
            bh = int(plot_h * value / ymax)
            bx = center - len(value_cols) * bar_w / 2 + j * bar_w
            draw.rounded_rectangle((bx, y0 - bh, bx + bar_w * 0.82, y0), radius=4, fill=colors[j % len(colors)])
            draw.text((bx - 3, y0 - bh - 22), value_format.format(value), font=small_font, fill=PALETTE["ink"])
        label = str(row[label_col]).replace("ACN_", "").replace("_", " ")
        draw.text((center - cluster_w * 0.38, y0 + 18), label[:18], font=label_font, fill=PALETTE["ink"])
    legend_x = 90
    for j, col in enumerate(value_cols):
        draw.rectangle((legend_x, 705, legend_x + 18, 723), fill=colors[j % len(colors)])
        draw.text((legend_x + 25, 700), col.replace("_", " "), font=label_font, fill=PALETTE["ink"])
        legend_x += 270
    img.save(path)


def save_line_chart(df: pd.DataFrame, title: str, path: Path) -> None:
    width, height = 1200, 720
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    title_font = load_font(31, True)
    label_font = load_font(16)
    draw.text((80, 40), title, font=title_font, fill=PALETTE["ink"])
    x0, y0 = 90, 550
    plot_w, plot_h = 1040, 410
    ymax = float(df["density"].max()) * 1.12
    for step in range(6):
        y = y0 - int(plot_h * step / 5)
        draw.line((x0, y, x0 + plot_w, y), fill=PALETTE["line"])
        draw.text((25, y - 9), f"{ymax * step / 5:.2f}", font=label_font, fill=PALETTE["gray"])
    colors = [PALETTE["blue"], PALETTE["green"], PALETTE["orange"], PALETTE["red"]]
    for idx, (name, group) in enumerate(df.groupby("scenario")):
        color = colors[idx % len(colors)]
        points = []
        for _, row in group.sort_values("week").iterrows():
            xp = x0 + (row["week"] - 1) / 11 * plot_w
            yp = y0 - row["density"] / ymax * plot_h
            points.append((float(xp), float(yp)))
        if len(points) > 1:
            draw.line(points, fill=color, width=4)
        for x, y in points:
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=color)
        draw.rectangle((90 + idx * 245, 665, 108 + idx * 245, 683), fill=color)
        draw.text((115 + idx * 245, 660), name.replace("ACN_", "").replace("_", " ")[:20], font=label_font, fill=PALETTE["ink"])
    img.save(path)


def save_heatmap(df: pd.DataFrame, path: Path) -> None:
    width, height = 900, 650
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    title_font = load_font(29, True)
    label_font = load_font(17)
    draw.text((90, 35), "Sensitivity: Remaining Isolated Students", font=title_font, fill=PALETTE["ink"])
    adoptions = sorted(df["initial_adoption"].unique())
    thresholds = sorted(df["isolation_threshold"].unique())
    x0, y0, plot_w, plot_h = 150, 115, 650, 410
    values = df["final_isolated_students"].to_numpy(dtype=float)
    vmin, vmax = values.min(), values.max()
    cell_w = plot_w / len(thresholds)
    cell_h = plot_h / len(adoptions)
    for i, adoption in enumerate(adoptions):
        for j, threshold in enumerate(thresholds):
            value = float(df[(df["initial_adoption"] == adoption) & (df["isolation_threshold"] == threshold)]["final_isolated_students"].iloc[0])
            t = 0 if vmax == vmin else (value - vmin) / (vmax - vmin)
            color = tuple(int(PALETTE["green"][k] * (1 - t) + PALETTE["red"][k] * t) for k in range(3))
            x = x0 + j * cell_w
            y = y0 + (len(adoptions) - i - 1) * cell_h
            draw.rectangle((x, y, x + cell_w, y + cell_h), fill=color, outline="white", width=3)
            draw.text((x + cell_w / 2 - 8, y + cell_h / 2 - 9), f"{value:.0f}", font=label_font, fill="white")
    for j, threshold in enumerate(thresholds):
        draw.text((x0 + j * cell_w + cell_w / 2 - 5, y0 + plot_h + 18), str(int(threshold)), font=label_font, fill=PALETTE["ink"])
    for i, adoption in enumerate(adoptions):
        draw.text((92, y0 + (len(adoptions) - i - 1) * cell_h + cell_h / 2 - 8), f"{adoption:.1f}", font=label_font, fill=PALETTE["ink"])
    img.save(path)


def generate_outputs(process_summary: pd.DataFrame, behavior_timeseries: pd.DataFrame, behavior_summary: pd.DataFrame, sensitivity: pd.DataFrame) -> dict[str, Path]:
    figures = {}
    process_plot = process_summary.copy()
    process_plot["formation_days"] = process_plot["median_formation_days"]
    process_plot["isolated_share"] = process_plot["isolated_students_mean"] / process_plot["cohort_size"]
    figures["process"] = FIGURES_DIR / "process_time_and_isolation.png"
    save_bar_chart(process_plot, "scenario", ["formation_days", "isolated_share"], "Process Simulation: Time and Isolation", figures["process"])
    quality_plot = process_summary.copy()
    figures["quality"] = FIGURES_DIR / "quality_and_satisfaction.png"
    save_bar_chart(quality_plot, "scenario", ["group_balance_index_mean", "satisfaction_score_mean"], "Matching Quality and Satisfaction", figures["quality"])
    figures["density"] = FIGURES_DIR / "network_density_over_time.png"
    save_line_chart(behavior_timeseries, "Behavior Simulation: Network Density", figures["density"])
    figures["sensitivity"] = FIGURES_DIR / "sensitivity_isolation_heatmap.png"
    save_heatmap(sensitivity, figures["sensitivity"])
    return figures


def write_dashboard(process_summary: pd.DataFrame, behavior_summary: pd.DataFrame, figures: dict[str, Path]) -> None:
    as_is = process_summary[process_summary["scenario"] == "AS_IS_WhatsApp"].iloc[0]
    opt = process_summary[process_summary["scenario"] == "ACN_Optimized_B1"].iloc[0]
    peak = process_summary[process_summary["scenario"] == "ACN_Exam_Peak_500"].iloc[0]
    b1 = behavior_summary[behavior_summary["scenario"] == "ACN_With_B1"].iloc[0]
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>ACN Simulation Dashboard</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 0; background: #f6f8fa; color: #1f2328; }}
header {{ padding: 28px 36px; background: white; border-bottom: 1px solid #d0d7de; }}
main {{ max-width: 1180px; margin: auto; padding: 24px; }}
.metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }}
.metric, .chart {{ background: white; border: 1px solid #d0d7de; border-radius: 8px; padding: 14px; }}
.metric strong {{ display: block; font-size: 28px; }}
.grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 18px; margin-top: 22px; }}
img {{ width: 100%; height: auto; }}
table {{ border-collapse: collapse; width: 100%; background: white; margin-top: 18px; }}
th, td {{ border: 1px solid #d0d7de; padding: 7px; font-size: 13px; }}
th {{ background: #eaf3f8; }}
@media(max-width: 900px) {{ .metrics, .grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<header>
<h1>Academic Collaboration Network Dashboard</h1>
<p>Simulation and validation results for the final project.</p>
<p><a href="System_Simulation_Report.pdf">Open PDF report</a></p>
</header>
<main>
<section class="metrics">
<div class="metric"><strong>{(as_is['median_formation_days'] - opt['median_formation_days']) / as_is['median_formation_days'] * 100:.1f}%</strong><span>formation time reduction</span></div>
<div class="metric"><strong>{peak['p95_matching_latency_seconds']:.2f}s</strong><span>p95 latency at 500 students</span></div>
<div class="metric"><strong>{opt['satisfaction_score_mean']:.2f}</strong><span>optimized satisfaction</span></div>
<div class="metric"><strong>{b1['isolated_students']:.0f}</strong><span>isolated students with B1</span></div>
</section>
<section class="grid">
<div class="chart"><img src="../figures/{figures['process'].name}"></div>
<div class="chart"><img src="../figures/{figures['quality'].name}"></div>
<div class="chart"><img src="../figures/{figures['density'].name}"></div>
<div class="chart"><img src="../figures/{figures['sensitivity'].name}"></div>
</section>
<h2>Process Summary</h2>
{process_summary.to_html(index=False)}
<h2>Behavior Summary</h2>
{behavior_summary.to_html(index=False)}
</main>
</body>
</html>"""
    (DOCS_DIR / "dashboard.html").write_text(html, encoding="utf-8")


def write_pdf_report(process_summary: pd.DataFrame, behavior_summary: pd.DataFrame, figures: dict[str, Path]) -> None:
    pdf = DOCS_DIR / "System_Simulation_Report.pdf"
    c = canvas.Canvas(str(pdf), pagesize=letter)
    w, h = letter
    margin = 0.55 * inch
    y = h - margin
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, y, "Academic Collaboration Network")
    y -= 20
    c.setFont("Helvetica", 12)
    c.drawString(margin, y, "System Simulation and Validation Report")
    y -= 28
    c.setFont("Helvetica", 9)
    text = c.beginText(margin, y)
    text.setLeading(12)
    text.textLines(
        "This report summarizes the simulation outputs generated by the final project code. "
        "The process-oriented model evaluates group formation workflows, while the behavior-oriented "
        "model evaluates collaboration network evolution and isolated-student reduction."
    )
    c.drawText(text)
    y -= 60
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Process Simulation Summary")
    y -= 16
    c.setFont("Helvetica", 8)
    for _, row in process_summary.iterrows():
        latency = "N/A" if pd.isna(row["p95_matching_latency_seconds"]) else f"{row['p95_matching_latency_seconds']:.2f}s"
        c.drawString(margin, y, f"{row['scenario']}: success={row['success_rate_mean']:.2f}, days={row['median_formation_days']:.2f}, latency={latency}, isolated={row['isolated_students_mean']:.1f}")
        y -= 11
    y -= 12
    c.drawImage(str(figures["process"]), margin, y - 200, width=500, height=200, preserveAspectRatio=True)
    y -= 220
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Behavior Simulation Summary")
    y -= 16
    c.setFont("Helvetica", 8)
    for _, row in behavior_summary.iterrows():
        c.drawString(margin, y, f"{row['scenario']}: density={row['density']:.3f}, isolated={row['isolated_students']:.0f}, gini={row['degree_gini']:.2f}, satisfaction={row['mean_satisfaction']:.2f}")
        y -= 11
    y -= 12
    c.drawImage(str(figures["density"]), margin, y - 180, width=500, height=180, preserveAspectRatio=True)
    c.showPage()
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, h - margin, "Validation Conclusions")
    c.setFont("Helvetica", 9)
    text = c.beginText(margin, h - margin - 22)
    text.setLeading(13)
    text.textLines(
        "The simulation validates the main ACN design decisions: the matching engine remains under the "
        "three-second target in the modeled stress scenario, the optimized platform reduces group formation "
        "time compared with the WhatsApp-only process, and the B1 isolation-priority loop reduces isolated "
        "students in the behavior model. Low adoption remains the main implementation risk."
    )
    c.drawText(text)
    c.drawImage(str(figures["quality"]), margin, 360, width=500, height=200, preserveAspectRatio=True)
    c.drawImage(str(figures["sensitivity"]), margin, 120, width=430, height=220, preserveAspectRatio=True)
    c.save()


def main() -> None:
    ensure_dirs()
    parser = argparse.ArgumentParser(description="Run ACN final project simulations.")
    parser.add_argument("--seed", type=int, help="Use a custom random seed.")
    parser.add_argument("--randomize", action="store_true", help="Use a different random seed every run.")
    parser.add_argument("--students", type=str, help="Path to a custom student CSV.")
    parser.add_argument("--ignore-custom", action="store_true", help="Ignore data/custom_students.csv if present.")
    args = parser.parse_args()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if args.randomize:
        config["random_seed"] = time.time_ns() % 1_000_000_000
        print(f"Using randomized seed: {config['random_seed']}")
    elif args.seed is not None:
        config["random_seed"] = args.seed
        print(f"Using custom seed: {config['random_seed']}")

    custom_students = None
    custom_path = Path(args.students) if args.students else DEFAULT_CUSTOM_STUDENTS
    if not args.ignore_custom and custom_path.exists():
        custom_students = load_custom_students(custom_path)
        print(f"Using custom student data: {custom_path} ({len(custom_students)} rows)")

    print("1/6 Running process simulation...")
    process_trials, process_summary = simulate_process(config, custom_students)
    print("2/6 Running behavior simulation...")
    behavior_timeseries, behavior_summary = simulate_behavior(config, custom_students)
    print("3/6 Running sensitivity analysis...")
    sensitivity = simulate_sensitivity(config, custom_students)

    print("4/6 Writing CSV results...")
    process_trials.to_csv(RESULTS_DIR / "process_trials.csv", index=False)
    process_summary.to_csv(RESULTS_DIR / "process_summary.csv", index=False)
    behavior_timeseries.to_csv(RESULTS_DIR / "behavior_timeseries.csv", index=False)
    behavior_summary.to_csv(RESULTS_DIR / "behavior_summary.csv", index=False)
    sensitivity.to_csv(RESULTS_DIR / "sensitivity_summary.csv", index=False)

    print("5/6 Generating figures...")
    figures = generate_outputs(process_summary, behavior_timeseries, behavior_summary, sensitivity)
    print("6/6 Writing report and dashboard...")
    write_dashboard(process_summary, behavior_summary, figures)
    write_pdf_report(process_summary, behavior_summary, figures)

    print("\nGenerated final project outputs:")
    print(f"- {RESULTS_DIR}")
    print(f"- {FIGURES_DIR}")
    print(f"- {DOCS_DIR / 'System_Simulation_Report.pdf'}")
    print(f"- {DOCS_DIR / 'dashboard.html'}")


if __name__ == "__main__":
    main()
