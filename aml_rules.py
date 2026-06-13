"""
Explainable AML transaction-monitoring rules.

Each rule returns a list of flags. A flag is a small, auditable record:
    {user_id, rule, severity, detail, evidence}

Design goal: every alert must be explainable to an auditor/regulator.
No black boxes — rules are transparent and parameterised.

NOTE: operates on fully synthetic data only (see generate_synthetic_data.py).
"""
from __future__ import annotations
import pandas as pd

# --- Tunable thresholds (a real programme calibrates these to its risk appetite) ---
LARGE_TX_USD = 100_000          # single-transaction reporting threshold
STRUCTURING_BAND = (90_000, 100_000)  # amounts that sit just under the threshold
RAPID_FIRE_PER_DAY = 5          # withdrawals/day that look like layering
VELOCITY_24H_USD = 1_000_000    # aggregate outflow over 24h
SHARED_ADDRESS_MIN_USERS = 5    # distinct users paying into one address


def _flag(uid, rule, severity, detail, evidence):
    return {"user_id": uid, "rule": rule, "severity": severity,
            "detail": detail, "evidence": evidence}


def large_transactions(df: pd.DataFrame) -> list[dict]:
    flags = []
    big = df[df["amount_usd"] >= LARGE_TX_USD]
    for uid, g in big.groupby("user_id"):
        flags.append(_flag(
            uid, "LARGE_TRANSACTION", "MEDIUM",
            f"{len(g)} transaction(s) >= ${LARGE_TX_USD:,.0f}",
            f"max ${g['amount_usd'].max():,.0f}, total ${g['amount_usd'].sum():,.0f}"))
    return flags


def structuring(df: pd.DataFrame) -> list[dict]:
    """Amounts deliberately parked just below the reporting threshold."""
    flags = []
    lo, hi = STRUCTURING_BAND
    band = df[(df["amount_usd"] >= lo) & (df["amount_usd"] < hi)]
    for uid, g in band.groupby("user_id"):
        if len(g) >= 2:
            flags.append(_flag(
                uid, "STRUCTURING", "HIGH",
                f"{len(g)} transactions in the ${lo:,.0f}-${hi:,.0f} band (just below threshold)",
                f"amounts: {', '.join(f'${a:,.0f}' for a in g['amount_usd'].head(5))}"))
    return flags


def rapid_fire(df: pd.DataFrame) -> list[dict]:
    """Many withdrawals in a single day == possible layering."""
    flags = []
    wd = df[df["direction"] == "withdrawal"].copy()
    wd["day"] = wd["timestamp"].dt.date
    counts = wd.groupby(["user_id", "day"]).size().reset_index(name="n")
    hot = counts[counts["n"] > RAPID_FIRE_PER_DAY]
    for uid, g in hot.groupby("user_id"):
        peak = int(g["n"].max())
        flags.append(_flag(
            uid, "RAPID_FIRE", "HIGH",
            f"up to {peak} withdrawals in a single day (> {RAPID_FIRE_PER_DAY})",
            f"busiest day: {g.loc[g['n'].idxmax(), 'day']}"))
    return flags


def velocity(df: pd.DataFrame) -> list[dict]:
    """Aggregate outflow over any rolling 24h window exceeds the velocity limit."""
    flags = []
    wd = df[df["direction"] == "withdrawal"].sort_values("timestamp")
    for uid, g in wd.groupby("user_id"):
        s = g.set_index("timestamp")["amount_usd"].rolling("24h").sum()
        if not s.empty and s.max() >= VELOCITY_24H_USD:
            flags.append(_flag(
                uid, "HIGH_VELOCITY", "HIGH",
                f"24h outflow reached ${s.max():,.0f} (>= ${VELOCITY_24H_USD:,.0f})",
                f"total period outflow ${g['amount_usd'].sum():,.0f}"))
    return flags


def shared_addresses(df: pd.DataFrame) -> list[dict]:
    """One destination address funded by many distinct users -> mixer / P2P exchanger."""
    flags = []
    wd = df[(df["direction"] == "withdrawal") & df["to_address"].notna()]
    by_addr = wd.groupby("to_address")["user_id"].nunique()
    for addr, n in by_addr[by_addr >= SHARED_ADDRESS_MIN_USERS].items():
        users = sorted(wd[wd["to_address"] == addr]["user_id"].unique().tolist())
        for uid in users:
            flags.append(_flag(
                uid, "SHARED_ADDRESS", "CRITICAL",
                f"withdrew to address used by {n} distinct users (possible mixer/P2P exchanger)",
                f"address {addr[:10]}… shared by {n} users"))
    return flags


RULES = [large_transactions, structuring, rapid_fire, velocity, shared_addresses]
SEVERITY_WEIGHT = {"LOW": 1, "MEDIUM": 2, "HIGH": 4, "CRITICAL": 8}


def run_all(df: pd.DataFrame) -> pd.DataFrame:
    flags = []
    for rule in RULES:
        flags.extend(rule(df))
    return pd.DataFrame(flags, columns=["user_id", "rule", "severity", "detail", "evidence"])


def risk_scores(flags: pd.DataFrame) -> pd.DataFrame:
    """Transparent additive score: sum of severity weights per user. Fully explainable."""
    if flags.empty:
        return pd.DataFrame(columns=["user_id", "risk_score", "n_flags", "top_rule"])
    f = flags.copy()
    f["w"] = f["severity"].map(SEVERITY_WEIGHT)
    out = (f.groupby("user_id")
             .agg(risk_score=("w", "sum"), n_flags=("rule", "count"),
                  top_rule=("severity", lambda s: f.loc[s.index].sort_values("w").iloc[-1]["rule"]))
             .reset_index()
             .sort_values("risk_score", ascending=False))
    return out
