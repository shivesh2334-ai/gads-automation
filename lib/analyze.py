"""
Pull performance data from Google Ads and compute KPIs.
"""
import pandas as pd
from .gads_client import get_client, run_query

CAMPAIGN_QUERY = """
    SELECT
      campaign.id,
      campaign.name,
      campaign.status,
      campaign_budget.amount_micros,
      metrics.impressions,
      metrics.clicks,
      metrics.cost_micros,
      metrics.conversions,
      metrics.conversions_value,
      metrics.ctr,
      metrics.average_cpc
    FROM campaign
    WHERE segments.date DURING LAST_{days}_DAYS
    ORDER BY metrics.cost_micros DESC
"""

KEYWORD_QUERY = """
    SELECT
      campaign.name,
      ad_group.name,
      ad_group_criterion.keyword.text,
      ad_group_criterion.keyword.match_type,
      metrics.impressions,
      metrics.clicks,
      metrics.cost_micros,
      metrics.conversions,
      metrics.ctr,
      metrics.average_cpc,
      metrics.search_impression_share
    FROM keyword_view
    WHERE segments.date DURING LAST_{days}_DAYS
      AND ad_group_criterion.status = 'ENABLED'
    ORDER BY metrics.cost_micros DESC
    LIMIT 500
"""


def _days_literal(days: int) -> str:
    valid = {7: "7", 14: "14", 30: "30"}
    return valid.get(days, "30")


def fetch_campaign_data(client, customer_id: str, days: int = 30) -> pd.DataFrame:
    query = CAMPAIGN_QUERY.format(days=_days_literal(days))
    rows = run_query(client, customer_id, query)
    records = []
    for row in rows:
        cost = row.metrics.cost_micros / 1_000_000
        budget = row.campaign_budget.amount_micros / 1_000_000
        conv = row.metrics.conversions
        records.append({
            "campaign_id": row.campaign.id,
            "campaign_name": row.campaign.name,
            "status": row.campaign.status.name,
            "daily_budget": budget,
            "impressions": row.metrics.impressions,
            "clicks": row.metrics.clicks,
            "cost": cost,
            "conversions": conv,
            "conv_value": row.metrics.conversions_value,
            "ctr": row.metrics.ctr,
            "avg_cpc": row.metrics.average_cpc,
            "cpa": (cost / conv) if conv else None,
            "roas": (row.metrics.conversions_value / cost) if cost else None,
        })
    return pd.DataFrame.from_records(records)


def fetch_keyword_data(client, customer_id: str, days: int = 30) -> pd.DataFrame:
    query = KEYWORD_QUERY.format(days=_days_literal(days))
    rows = run_query(client, customer_id, query)
    records = []
    for row in rows:
        cost = row.metrics.cost_micros / 1_000_000
        records.append({
            "campaign_name": row.campaign.name,
            "ad_group_name": row.ad_group.name,
            "keyword": row.ad_group_criterion.keyword.text,
            "match_type": row.ad_group_criterion.keyword.match_type.name,
            "impressions": row.metrics.impressions,
            "clicks": row.metrics.clicks,
            "cost": cost,
            "conversions": row.metrics.conversions,
            "ctr": row.metrics.ctr,
            "avg_cpc": row.metrics.average_cpc,
            "impression_share": row.metrics.search_impression_share,
        })
    return pd.DataFrame.from_records(records)


def analyze(customer_id: str, days: int = 30) -> dict:
    client = get_client()
    campaigns = fetch_campaign_data(client, customer_id, days)
    keywords = fetch_keyword_data(client, customer_id, days)

    summary = {
        "days": days,
        "total_cost": round(campaigns["cost"].sum(), 2) if not campaigns.empty else 0,
        "total_clicks": int(campaigns["clicks"].sum()) if not campaigns.empty else 0,
        "total_conversions": round(campaigns["conversions"].sum(), 2) if not campaigns.empty else 0,
        "avg_ctr": round(campaigns["ctr"].mean(), 4) if not campaigns.empty else 0,
        "avg_cpc": round(campaigns["avg_cpc"].mean(), 2) if not campaigns.empty else 0,
        "overall_roas": (
            round(campaigns["conv_value"].sum() / campaigns["cost"].sum(), 2)
            if not campaigns.empty and campaigns["cost"].sum() else 0
        ),
        "underperforming_campaigns": campaigns[
            (campaigns["cost"] > campaigns["cost"].mean() if not campaigns.empty else False)
            & (campaigns["conversions"] < 1)
        ]["campaign_name"].tolist() if not campaigns.empty else [],
        "wasted_spend_keywords": keywords[
            (keywords["clicks"] > 10) & (keywords["conversions"] == 0)
        ].sort_values("cost", ascending=False).head(20).to_dict("records") if not keywords.empty else [],
        "low_impression_share_keywords": keywords[
            (keywords["impression_share"] < 0.5) & (keywords["conversions"] > 0)
        ].sort_values("conversions", ascending=False).head(20).to_dict("records") if not keywords.empty else [],
    }
    return {"campaigns": campaigns, "keywords": keywords, "summary": summary}
