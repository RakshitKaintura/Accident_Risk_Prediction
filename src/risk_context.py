from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class RiskContext:
    city_trend_index: float
    city_trend_modifier: float
    station_scores: dict[str, float]
    station_trend_indices: dict[str, float]
    station_display_names: dict[str, str]
    station_histories: dict[str, list[dict[str, float]]]


# Mapping from blackspot names to station names present in station-wise data.
BLACKSPOT_TO_STATION = {
    "Silk Board Junction": "Madivala",
    "Hebbal Flyover": "Hebbala",
    "KR Puram Tin Factory": "K R Puram",
    "Goraguntepalya": "Yashawanthapura",
    "Electronic City Toll": "Electronic City",
    "Ibbalur Junction (ORR)": "HSR Layout",
    "Marathahalli Bridge": "Mahadevapura",
    "Dairy Circle": "Adugodi",
    "Banashankari Signal": "Banashankari",
    "Summanahalli Junction": "Kamakshipalya",
    "Koramangala Sony Signal": "Mico layout",
    "Nayandahalli Junction": "Bytarayanapura",
}


def _normalize_station_name(name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "", str(name).lower())
    return cleaned


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", "", regex=False), errors="coerce").fillna(0.0)


def _load_city_trend(path: str) -> tuple[float, float]:
    csv_path = Path(path)
    if not csv_path.exists():
        return 1.0, 0.0

    df = pd.read_csv(csv_path)
    if "Total" not in df.columns:
        return 1.0, 0.0

    totals = _to_numeric(df["Total"])
    if totals.empty or totals.median() <= 0:
        return 1.0, 0.0

    latest_total = float(totals.iloc[-1])
    baseline = float(totals.median())
    trend_index = latest_total / baseline

    modifier = max(-0.03, min(0.08, (trend_index - 1.0) * 0.08))
    return trend_index, modifier


def _column_groups(df: pd.DataFrame) -> tuple[list[str], list[str], list[str]]:
    fatal_cols: list[str] = []
    non_fatal_cols: list[str] = []
    total_cols: list[str] = []

    for col in df.columns:
        key = col.strip().lower()

        if "non-fatal" in key or "non fatal" in key:
            non_fatal_cols.append(col)
            continue

        if "total" in key:
            total_cols.append(col)
            continue

        if "fatal" in key:
            fatal_cols.append(col)

    return fatal_cols, non_fatal_cols, total_cols


def _extract_year(column_name: str) -> int | None:
    match = re.search(r"(20\d{2})", str(column_name))
    if not match:
        return None
    return int(match.group(1))


def _extract_station_rows(df: pd.DataFrame) -> pd.DataFrame:
    if "Station" not in df.columns:
        return pd.DataFrame()

    rows = df.copy()
    rows["Station"] = rows["Station"].astype(str).str.strip()
    rows = rows[rows["Station"] != ""]
    rows = rows[~rows["Station"].str.contains("total", case=False, na=False)]
    rows = rows[~rows["Station"].str.contains("grand", case=False, na=False)]
    return rows


def _station_metrics_from_file(path: str) -> tuple[
    dict[str, float],
    dict[str, float],
    dict[str, str],
    dict[str, dict[int, float]],
]:
    csv_path = Path(path)
    if not csv_path.exists():
        return {}, {}, {}, {}

    df = pd.read_csv(csv_path)
    rows = _extract_station_rows(df)
    if rows.empty:
        return {}, {}, {}, {}

    fatal_cols, non_fatal_cols, total_cols = _column_groups(rows)

    if not fatal_cols and not non_fatal_cols and not total_cols:
        return {}, {}, {}, {}

    severity_map: dict[str, float] = {}
    trend_map: dict[str, float] = {}
    display_name_map: dict[str, str] = {}
    station_history_map: dict[str, dict[int, float]] = {}

    for _, row in rows.iterrows():
        station_raw = str(row["Station"]).strip()
        station_key = _normalize_station_name(station_raw)
        if not station_key:
            continue

        fatal_total = float(_to_numeric(pd.Series([row.get(col, 0) for col in fatal_cols])).sum()) if fatal_cols else 0.0
        non_fatal_total = (
            float(_to_numeric(pd.Series([row.get(col, 0) for col in non_fatal_cols])).sum()) if non_fatal_cols else 0.0
        )
        severity = non_fatal_total + (2.0 * fatal_total)

        totals = _to_numeric(pd.Series([row.get(col, 0) for col in total_cols])) if total_cols else pd.Series([], dtype=float)
        positives = [float(v) for v in totals.tolist() if v > 0]

        if positives:
            recent_window = positives[-2:]
            historic_window = positives[:-2] if len(positives) > 2 else positives
            recent_avg = sum(recent_window) / len(recent_window)
            historic_avg = sum(historic_window) / len(historic_window) if historic_window else recent_avg
            trend_index = recent_avg / historic_avg if historic_avg > 0 else 1.0
        else:
            trend_index = 1.0

        severity_map[station_key] = severity_map.get(station_key, 0.0) + severity
        trend_map[station_key] = trend_map.get(station_key, 0.0) + trend_index
        display_name_map[station_key] = station_raw
        station_history_map.setdefault(station_key, {})
        for col in total_cols:
            year = _extract_year(col)
            if year is None:
                continue
            value = float(_to_numeric(pd.Series([row.get(col, 0)])).iloc[0])
            if value > 0:
                station_history_map[station_key][year] = value

    return severity_map, trend_map, display_name_map, station_history_map


def _load_station_profiles(
    paths: list[str],
) -> tuple[dict[str, float], dict[str, float], dict[str, str], dict[str, list[dict[str, float]]]]:
    aggregate_severity: dict[str, float] = {}
    aggregate_trend_sum: dict[str, float] = {}
    aggregate_trend_count: dict[str, int] = {}
    display_names: dict[str, str] = {}
    station_histories: dict[str, dict[int, float]] = {}

    for path in paths:
        severity_map, trend_map, display_map, history_map = _station_metrics_from_file(path)

        for key, value in severity_map.items():
            aggregate_severity[key] = aggregate_severity.get(key, 0.0) + value

        for key, value in trend_map.items():
            aggregate_trend_sum[key] = aggregate_trend_sum.get(key, 0.0) + value
            aggregate_trend_count[key] = aggregate_trend_count.get(key, 0) + 1

        display_names.update(display_map)
        for station_key, yearly_map in history_map.items():
            station_histories.setdefault(station_key, {})
            station_histories[station_key].update(yearly_map)

    max_severity = max(aggregate_severity.values(), default=0.0)
    if max_severity <= 0:
        return {}, {}, {}, {}

    station_scores = {key: value / max_severity for key, value in aggregate_severity.items()}

    station_trends: dict[str, float] = {}
    for key, trend_sum in aggregate_trend_sum.items():
        count = aggregate_trend_count.get(key, 1)
        station_trends[key] = trend_sum / count

    packed_histories: dict[str, list[dict[str, float]]] = {}
    for station_key, yearly in station_histories.items():
        points = [{"year": float(year), "total_cases": float(total)} for year, total in sorted(yearly.items())]
        packed_histories[station_key] = points

    return station_scores, station_trends, display_names, packed_histories


def load_risk_context(city_yearly_path: str, station_wise_paths: list[str]) -> RiskContext:
    trend_index, trend_modifier = _load_city_trend(city_yearly_path)
    station_scores, station_trends, station_display_names, station_histories = _load_station_profiles(station_wise_paths)

    return RiskContext(
        city_trend_index=round(trend_index, 3),
        city_trend_modifier=round(trend_modifier, 3),
        station_scores=station_scores,
        station_trend_indices=station_trends,
        station_display_names=station_display_names,
        station_histories=station_histories,
    )


def station_adjustment_for_blackspot(
    blackspot_name: str,
    station_scores: dict[str, float],
    station_trends: dict[str, float],
    dist_km: float,
) -> tuple[str | None, float, float, float]:
    station = BLACKSPOT_TO_STATION.get(blackspot_name)
    if not station:
        return None, 0.0, 1.0, 0.0

    station_key = _normalize_station_name(station)
    score = float(station_scores.get(station_key, 0.0))
    trend_index = float(station_trends.get(station_key, 1.0))

    # Influence decays with distance from nearest blackspot.
    distance_weight = max(0.0, 1.0 - (dist_km / 6.0))

    severity_modifier = score * 0.10
    trend_modifier = max(-0.03, min(0.05, (trend_index - 1.0) * 0.08))

    modifier = (severity_modifier + trend_modifier) * distance_weight
    return station, score, trend_index, modifier


def station_profile_for_blackspot(
    blackspot_name: str,
    station_scores: dict[str, float],
    station_trends: dict[str, float],
) -> tuple[str | None, float, float]:
    station = BLACKSPOT_TO_STATION.get(blackspot_name)
    if not station:
        return None, 0.0, 1.0

    station_key = _normalize_station_name(station)
    score = float(station_scores.get(station_key, 0.0))
    trend_index = float(station_trends.get(station_key, 1.0))
    return station, score, trend_index
