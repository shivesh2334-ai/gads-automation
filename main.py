"""
Local CLI. Uses google-ads.yaml (see auth.py) rather than env vars.

    python main.py analyze --customer-id 123-456-7890 --days 30
    python main.py suggest --customer-id 123-456-7890
    python main.py deploy  --customer-id 123-456-7890 --plan output/suggestions.json
    python main.py deploy  --customer-id 123-456-7890 --plan output/suggestions.json --live
    python main.py run-all --customer-id 123-456-7890 --days 30
"""
import argparse
import json
import pickle
from pathlib import Path

from lib.analyze import analyze
from lib.report import generate_report
from lib.suggest import build_suggestions
from lib.deploy import deploy as run_deploy

OUT_DIR = Path("output")
CACHE_PATH = OUT_DIR / "analysis.pkl"


def cmd_analyze(args):
    result = analyze(args.customer_id, args.days)
    generate_report(result)
    OUT_DIR.mkdir(exist_ok=True)
    with open(CACHE_PATH, "wb") as f:
        pickle.dump(result, f)


def cmd_suggest(args):
    if not CACHE_PATH.exists():
        raise SystemExit("Run `analyze` first — no cached analysis found.")
    with open(CACHE_PATH, "rb") as f:
        result = pickle.load(f)
    plan = build_suggestions(result)
    OUT_DIR.mkdir(exist_ok=True)
    plan_path = OUT_DIR / "suggestions.json"
    plan_path.write_text(json.dumps(plan, indent=2, default=str))
    print(f"Suggestions written to {plan_path}")


def cmd_deploy(args):
    plan = json.loads(Path(args.plan).read_text())
    if not args.live:
        print("=== DRY RUN — no changes will be made to your account ===\n")
    log = run_deploy(args.customer_id, plan, live=args.live)
    OUT_DIR.mkdir(exist_ok=True)
    log_path = OUT_DIR / "deploy_log.jsonl"
    with open(log_path, "a") as f:
        for entry in log:
            f.write(json.dumps(entry, default=str) + "\n")
    print(f"{len(log)} action(s) {'applied' if args.live else 'validated (dry run)'}. Logged to {log_path}")


def cmd_run_all(args):
    result = analyze(args.customer_id, args.days)
    generate_report(result)
    plan = build_suggestions(result)
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "suggestions.json").write_text(json.dumps(plan, indent=2, default=str))
    print("\nReview output/report.html and output/suggestions.json.")
    print("Then run: python main.py deploy --customer-id "
          f"{args.customer_id} --plan output/suggestions.json  (add --live when ready)")


def main():
    parser = argparse.ArgumentParser(description="Google Ads automation pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_analyze = sub.add_parser("analyze", help="Pull performance data and build a report")
    p_analyze.add_argument("--customer-id", required=True)
    p_analyze.add_argument("--days", type=int, default=30, choices=[7, 14, 30])
    p_analyze.set_defaults(func=cmd_analyze)

    p_suggest = sub.add_parser("suggest", help="Generate optimization + new campaign suggestions")
    p_suggest.add_argument("--customer-id", required=True)
    p_suggest.set_defaults(func=cmd_suggest)

    p_deploy = sub.add_parser("deploy", help="Apply suggestions (dry run unless --live)")
    p_deploy.add_argument("--customer-id", required=True)
    p_deploy.add_argument("--plan", default="output/suggestions.json")
    p_deploy.add_argument("--live", action="store_true", help="Actually apply changes (default: dry run)")
    p_deploy.set_defaults(func=cmd_deploy)

    p_all = sub.add_parser("run-all", help="analyze + suggest in one pass (deploy stays manual)")
    p_all.add_argument("--customer-id", required=True)
    p_all.add_argument("--days", type=int, default=30, choices=[7, 14, 30])
    p_all.set_defaults(func=cmd_run_all)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
