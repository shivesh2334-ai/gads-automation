"""
Suggest optimizations and a new campaign build from an analysis dict.
Pure function — callers (CLI or API) decide whether/where to persist the result.

Tune the thresholds below to your account's norms before trusting the output.
"""

MIN_CLICKS_FOR_WASTE_FLAG = 15
TARGET_CPA = None
MIN_IMPRESSION_SHARE = 0.5
BUDGET_INCREASE_PCT = 0.20
BUDGET_DECREASE_PCT = 0.30
STRONG_ROAS = 3.0
WEAK_ROAS = 1.0


def build_suggestions(analysis: dict) -> dict:
    campaigns = analysis["campaigns"]
    keywords = analysis["keywords"]
    summary = analysis["summary"]

    plan = {
        "generated_from_days": summary["days"],
        "budget_changes": [],
        "negative_keywords": [],
        "bid_adjustments": [],
        "pause_campaigns": [],
        "new_campaign_draft": None,
    }

    if not campaigns.empty:
        for _, row in campaigns.iterrows():
            if row["roas"] and row["roas"] >= STRONG_ROAS and row["conversions"] > 0:
                plan["budget_changes"].append({
                    "campaign_id": int(row["campaign_id"]),
                    "campaign_name": row["campaign_name"],
                    "action": "increase",
                    "current_daily_budget": row["daily_budget"],
                    "suggested_daily_budget": round(row["daily_budget"] * (1 + BUDGET_INCREASE_PCT), 2),
                    "reason": f"ROAS {row['roas']:.1f}x is strong — scale spend.",
                })
            elif row["roas"] is not None and row["roas"] < WEAK_ROAS and row["cost"] > 0:
                plan["budget_changes"].append({
                    "campaign_id": int(row["campaign_id"]),
                    "campaign_name": row["campaign_name"],
                    "action": "decrease",
                    "current_daily_budget": row["daily_budget"],
                    "suggested_daily_budget": round(row["daily_budget"] * (1 - BUDGET_DECREASE_PCT), 2),
                    "reason": f"ROAS {row['roas']:.1f}x is below target — reduce spend.",
                })
            if row["cost"] > 0 and row["conversions"] == 0 and row["clicks"] > 30:
                plan["pause_campaigns"].append({
                    "campaign_id": int(row["campaign_id"]),
                    "campaign_name": row["campaign_name"],
                    "reason": "30+ clicks, zero conversions in the window — pause and review targeting/landing page.",
                })

    if not keywords.empty:
        wasted = keywords[
            (keywords["clicks"] >= MIN_CLICKS_FOR_WASTE_FLAG) & (keywords["conversions"] == 0)
        ]
        for _, row in wasted.iterrows():
            plan["negative_keywords"].append({
                "campaign_name": row["campaign_name"],
                "ad_group_name": row["ad_group_name"],
                "keyword": row["keyword"],
                "match_type": row["match_type"],
                "reason": f"{int(row['clicks'])} clicks, ${row['cost']:.2f} spent, 0 conversions "
                          "— add as negative or pause.",
            })

        rising_stars = keywords[
            (keywords["impression_share"] < MIN_IMPRESSION_SHARE) & (keywords["conversions"] > 0)
        ]
        for _, row in rising_stars.iterrows():
            plan["bid_adjustments"].append({
                "campaign_name": row["campaign_name"],
                "ad_group_name": row["ad_group_name"],
                "keyword": row["keyword"],
                "current_avg_cpc": row["avg_cpc"],
                "suggested_avg_cpc": round(row["avg_cpc"] * 1.15, 2),
                "reason": f"Converting keyword capturing only "
                          f"{row['impression_share']*100:.0f}% impression share — raise bid to capture more.",
            })

        top_converters = (
            keywords[keywords["conversions"] > 0]
            .sort_values("conversions", ascending=False)
            .head(10)
        )
        if not top_converters.empty:
            plan["new_campaign_draft"] = {
                "name": f"Auto-Suggested — Scale Top Converters ({summary['days']}d)",
                "type": "SEARCH",
                "daily_budget": round(max(summary["avg_cpc"] * 20, 20), 2),
                "bidding_strategy": "MAXIMIZE_CONVERSIONS" if not TARGET_CPA else "TARGET_CPA",
                "target_cpa": TARGET_CPA,
                "ad_groups": [
                    {"name": f"{kw} — exact", "keywords": [{"text": kw, "match_type": "EXACT"}]}
                    for kw in top_converters["keyword"].dropna().unique().tolist()
                ],
                "reason": "Consolidates proven converting search terms into a dedicated, "
                          "tightly-themed campaign for cleaner bid/budget control.",
            }

    return plan
