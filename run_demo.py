"""
End-to-end demo: generate synthetic data -> run explainable AML rules ->
print an alert summary, write flags to CSV, and render a dashboard PNG.

Usage:
    python run_demo.py
"""
from __future__ import annotations
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

import generate_synthetic_data as gen
import aml_rules as rules

NAVY, BLUE, GREY = "#1F3A5F", "#2E75B6", "#666666"
SEV_COLOR = {"CRITICAL": "#C0392B", "HIGH": "#E67E22", "MEDIUM": "#B8860B", "LOW": "#2E7D32"}
RULE_LABEL = {
    "SHARED_ADDRESS": "Shared address", "LARGE_TRANSACTION": "Large transaction",
    "STRUCTURING": "Structuring", "HIGH_VELOCITY": "High velocity",
    "RAPID_FIRE": "Rapid-fire", "PASS_THROUGH": "Pass-through",
}


def main():
    df = gen.generate()
    df.to_csv("synthetic_transactions.csv", index=False)

    flags = rules.run_all(df)
    scores = rules.risk_scores(flags)
    flags.to_csv("flags.csv", index=False)
    scores.to_csv("risk_scores.csv", index=False)

    # ---- console summary ----
    print("=" * 64)
    print(" AML MONITORING DEMO — synthetic data, explainable rules")
    print("=" * 64)
    print(f" Transactions analysed : {len(df):,}")
    print(f" Users                 : {df['user_id'].nunique()}")
    print(f" Alerts raised         : {len(flags)}")
    print(f" Users flagged         : {flags['user_id'].nunique()}")
    print("-" * 64)
    print(" Alerts by rule:")
    for rule, n in flags["rule"].value_counts().items():
        print(f"   {rule:<18} {n}")
    print("-" * 64)
    print(" Top 5 users by risk score:")
    for _, r in scores.head(5).iterrows():
        print(f"   {r['user_id']}  score={int(r['risk_score']):>3}  "
              f"flags={int(r['n_flags'])}  top={r['top_rule']}")
    print("=" * 64)

    render_dashboard(df, flags, scores)
    print("Wrote: flags.csv, risk_scores.csv, dashboard.png")


def render_dashboard(df, flags, scores):
    fig = plt.figure(figsize=(11, 5.6), dpi=130)
    fig.patch.set_facecolor("white")
    gs = GridSpec(1, 2, figure=fig,
                  wspace=0.30, left=0.16, right=0.97, top=0.58, bottom=0.13)

    fig.suptitle("AML Transaction-Monitoring Dashboard", x=0.045, y=0.95,
                 ha="left", fontsize=17, fontweight="bold", color=NAVY)
    fig.text(0.045, 0.875, "Synthetic data · explainable rule-based detection · demo only",
             ha="left", fontsize=9.5, color=GREY)

    # KPI strip
    kpis = [("Transactions", f"{len(df):,}"), ("Users", f"{df['user_id'].nunique()}"),
            ("Alerts", f"{len(flags)}"), ("Users flagged", f"{flags['user_id'].nunique()}")]
    for i, (label, val) in enumerate(kpis):
        x = 0.045 + i * 0.235
        fig.text(x, 0.74, val, fontsize=19, fontweight="bold", color=BLUE, ha="left")
        fig.text(x, 0.695, label, fontsize=9, color=GREY, ha="left")

    # Alerts by rule
    ax1 = fig.add_subplot(gs[0, 0])
    vc = flags["rule"].value_counts()
    # color by the (max) severity associated with each rule
    rule_sev = flags.groupby("rule")["severity"].agg(
        lambda s: max(s, key=lambda x: rules.SEVERITY_WEIGHT[x]))
    bar_colors = [SEV_COLOR[rule_sev[r]] for r in vc.index]
    labels = [RULE_LABEL.get(r, r) for r in vc.index]
    ax1.barh(labels[::-1], vc.values[::-1], color=bar_colors[::-1])
    ax1.set_title("Alerts by rule", fontsize=11, color=NAVY, loc="left", fontweight="bold")
    ax1.tick_params(labelsize=9)
    ax1.margins(x=0.12)
    for s in ("top", "right"):
        ax1.spines[s].set_visible(False)

    # Top users by risk score
    ax2 = fig.add_subplot(gs[0, 1])
    top = scores.head(8)[::-1]
    ax2.barh(top["user_id"], top["risk_score"], color=NAVY)
    ax2.set_title("Top users by risk score (additive, explainable)",
                  fontsize=11, color=NAVY, loc="left", fontweight="bold")
    ax2.tick_params(labelsize=8.5)
    for s in ("top", "right"):
        ax2.spines[s].set_visible(False)

    fig.text(0.07, 0.03,
             "Prepared by Merey Nurkaliyev — AML Team Lead | linkedin.com/in/merey-nurkaliyev",
             fontsize=8, color=GREY, ha="left")
    fig.savefig("dashboard.png", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
