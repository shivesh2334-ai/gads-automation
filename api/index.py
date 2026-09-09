"""
Vercel serverless entry point. All /api/* requests are rewritten here (see
vercel.json) and routed internally by Flask, so only one Python function is
deployed regardless of how many endpoints exist.

Endpoints:
  GET  /api/health                      liveness check, no auth
  POST /api/analyze   {customer_id, days}                returns KPI summary as JSON
  POST /api/suggest   {customer_id, days}                returns a suggestions plan as JSON
  POST /api/deploy    {customer_id, plan, live, secret}  applies a plan (dry-run unless live=true)

Every mutating call to /api/deploy requires header X-Deploy-Secret (or body
field "secret") matching the DEPLOY_SECRET environment variable. Keep that
secret private — anyone who has it can trigger real Google Ads changes when
they also pass live=true.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, request, jsonify

from lib.analyze import analyze
from lib.suggest import build_suggestions
from lib.deploy import deploy as run_deploy

app = Flask(__name__)


def _internal_error(message: str, exc: BaseException):
    app.logger.exception(message, exc_info=exc)
    return jsonify({"error": message}), 500


def _require_secret(payload: dict) -> bool:
    expected = os.environ.get("DEPLOY_SECRET")
    if not expected:
        return False  # refuse to run live/dry-run deploys if no secret is configured at all
    provided = request.headers.get("X-Deploy-Secret") or payload.get("secret")
    return provided == expected


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    payload = request.get_json(force=True, silent=True) or {}
    customer_id = payload.get("customer_id")
    days = int(payload.get("days", 30))
    if not customer_id:
        return jsonify({"error": "customer_id is required"}), 400
    try:
        result = analyze(customer_id, days)
    except SystemExit as e:
        return _internal_error("analyze request failed", e)
    campaigns = result["campaigns"]
    return jsonify({
        "summary": result["summary"],
        "campaigns": campaigns.to_dict("records") if not campaigns.empty else [],
    })


@app.route("/api/suggest", methods=["POST"])
def api_suggest():
    payload = request.get_json(force=True, silent=True) or {}
    customer_id = payload.get("customer_id")
    days = int(payload.get("days", 30))
    if not customer_id:
        return jsonify({"error": "customer_id is required"}), 400
    try:
        result = analyze(customer_id, days)
        plan = build_suggestions(result)
    except SystemExit as e:
        return _internal_error("suggest request failed", e)
    return jsonify(plan)


@app.route("/api/deploy", methods=["POST"])
def api_deploy():
    payload = request.get_json(force=True, silent=True) or {}
    customer_id = payload.get("customer_id")
    plan = payload.get("plan")
    live = bool(payload.get("live", False))

    if not customer_id or not plan:
        return jsonify({"error": "customer_id and plan are required"}), 400
    if not _require_secret(payload):
        return jsonify({"error": "invalid or missing deploy secret"}), 401

    try:
        log = run_deploy(customer_id, plan, live=live)
    except SystemExit as e:
        return _internal_error("deploy request failed", e)
    except Exception as e:
        return _internal_error("deploy request failed", e)

    return jsonify({"live": live, "actions": log})


# Vercel's Python runtime looks for a WSGI-compatible `app` object.
