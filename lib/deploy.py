"""
Apply suggested changes via Google Ads mutate operations.

SAFE BY DEFAULT: dry run (validate_only) unless live=True is explicitly passed.
Returns a list of log entries describing every action attempted; the caller
(CLI or API route) decides where to persist that log.
"""
from datetime import datetime, timezone
from .gads_client import get_client


def _entry(action: str, live: bool, detail: dict, note: str | None = None) -> dict:
    e = {"action": action, "live": live, "detail": detail,
         "timestamp": datetime.now(timezone.utc).isoformat()}
    if note:
        e["note"] = note
    return e


def apply_budget_changes(client, customer_id: str, changes: list, live: bool, log: list):
    if not changes:
        return
    service = client.get_service("CampaignBudgetService")
    ops = []
    for change in changes:
        op = client.get_type("CampaignBudgetOperation")
        op.update.resource_name = f"customers/{customer_id}/campaignBudgets/{change['campaign_id']}"
        op.update.amount_micros = int(change["suggested_daily_budget"] * 1_000_000)
        op.update_mask.paths.append("amount_micros")
        ops.append(op)
        log.append(_entry("budget_change", live, change))
    service.mutate_campaign_budgets(customer_id=customer_id, operations=ops, validate_only=not live)


def apply_pause_campaigns(client, customer_id: str, pauses: list, live: bool, log: list):
    if not pauses:
        return
    service = client.get_service("CampaignService")
    ops = []
    for p in pauses:
        op = client.get_type("CampaignOperation")
        op.update.resource_name = f"customers/{customer_id}/campaigns/{p['campaign_id']}"
        op.update.status = client.enums.CampaignStatusEnum.PAUSED
        op.update_mask.paths.append("status")
        ops.append(op)
        log.append(_entry("pause_campaign", live, p))
    service.mutate_campaigns(customer_id=customer_id, operations=ops, validate_only=not live)


def apply_negative_keywords(negatives: list, live: bool, log: list):
    # Needs ad_group resource-name resolution via GAQL before it can mutate directly;
    # logged as a reviewed suggestion rather than auto-applied to avoid guessing IDs.
    for n in negatives:
        log.append(_entry(
            "negative_keyword_suggestion_only", live, n,
            note="Resolve ad_group resource_name via GAQL before mutating; not auto-applied.",
        ))


def deploy(customer_id: str, plan: dict, live: bool = False) -> list:
    """Apply a suggestions plan (as produced by lib.suggest.build_suggestions).
    Returns the audit log as a list of dicts."""
    customer_id = customer_id.replace("-", "")
    client = get_client()
    log: list = []

    apply_budget_changes(client, customer_id, plan.get("budget_changes", []), live, log)
    apply_pause_campaigns(client, customer_id, plan.get("pause_campaigns", []), live, log)
    apply_negative_keywords(plan.get("negative_keywords", []), live, log)

    if plan.get("new_campaign_draft"):
        log.append(_entry(
            "new_campaign_draft_reviewed", live, plan["new_campaign_draft"],
            note="Building a brand-new campaign (budget + campaign + ad groups + "
                 "keywords + ads) is a multi-step mutate chain. Review the draft, "
                 "then extend apply_* to create each resource in order before going live.",
        ))

    return log
