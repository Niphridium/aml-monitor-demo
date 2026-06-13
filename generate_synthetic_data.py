"""
Generate a fully SYNTHETIC crypto-transaction dataset for the AML monitoring demo.

No real users, no real addresses, no real data of any kind. Everything here is
produced by a random generator with a fixed seed so the demo is reproducible.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)

FIRST = ["Alex", "Sam", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Jamie",
         "Avery", "Quinn", "Drew", "Skyler", "Reese", "Rowan", "Sasha", "Noor",
         "Dana", "Lena", "Marat", "Aida", "Timur", "Dilnoza", "Pavel", "Olga"]
LAST = ["Rivera", "Chen", "Patel", "Ivanov", "Kim", "Haddad", "Novak", "Silva",
        "Yusupov", "Abenov", "Petrov", "Khan", "Lopez", "Mwangi", "Sato", "Berg"]
ASSETS = ["USDT", "USDC", "BTC", "ETH", "TRX"]


def _addr(prefix="T"):
    body = "".join(RNG.choice(list("ABCDEFGHJKLMNPQRSTUVWXYZ123456789"), size=33))
    return prefix + body


def generate(n_users: int = 120, days: int = 14) -> pd.DataFrame:
    start = pd.Timestamp("2026-06-01")
    # a small pool of "hot" shared addresses to seed a CRITICAL pattern
    shared_pool = [_addr() for _ in range(3)]
    rows = []
    tx_id = 0
    for uid in range(1, n_users + 1):
        name = f"{RNG.choice(FIRST)} {RNG.choice(LAST)}"
        profile = RNG.choice(["retail", "retail", "retail", "active", "high_risk"],
                             p=[0.45, 0.25, 0.12, 0.12, 0.06])
        if profile == "retail":
            n_tx = RNG.integers(1, 8)
        elif profile == "active":
            n_tx = RNG.integers(8, 25)
        else:  # high_risk
            n_tx = RNG.integers(20, 45)

        for _ in range(int(n_tx)):
            ts = start + pd.Timedelta(
                seconds=int(RNG.integers(0, days * 24 * 3600)))
            direction = RNG.choice(["withdrawal", "deposit"], p=[0.7, 0.3])
            asset = RNG.choice(ASSETS)

            # amount distribution by profile
            if profile == "high_risk":
                amount = float(RNG.choice([
                    RNG.uniform(90_000, 99_999),     # structuring band
                    RNG.uniform(100_000, 4_000_000), # large
                    RNG.uniform(500, 50_000),
                ], p=[0.3, 0.4, 0.3]))
            elif profile == "active":
                amount = float(RNG.uniform(1_000, 250_000))
            else:
                amount = float(RNG.uniform(20, 8_000))

            to_addr = None
            if direction == "withdrawal":
                # high-risk users sometimes send to a shared pool address
                if profile == "high_risk" and RNG.random() < 0.5:
                    to_addr = RNG.choice(shared_pool)
                else:
                    to_addr = _addr()

            tx_id += 1
            rows.append({
                "tx_id": tx_id,
                "user_id": f"U{uid:04d}",
                "name": name,
                "direction": direction,
                "asset": asset,
                "amount_usd": round(amount, 2),
                "to_address": to_addr,
                "timestamp": ts,
            })

    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


if __name__ == "__main__":
    df = generate()
    df.to_csv("synthetic_transactions.csv", index=False)
    print(f"Wrote synthetic_transactions.csv  ({len(df):,} synthetic transactions, "
          f"{df['user_id'].nunique()} users)")
