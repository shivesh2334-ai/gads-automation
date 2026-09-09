"""
Build a full HTML report (with a chart) + CSV exports, for local CLI use.
Not used by the lightweight Vercel API (see api/index.py), which returns JSON
instead so the serverless bundle doesn't need matplotlib.
"""
from pathlib import Path
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from jinja2 import Template

OUT_DIR = Path("output")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Google Ads Report — {{ generated }}</title>
<style>
  body { font-family: -apple-system, Arial, sans-serif; max-width: 900px; margin: 40px auto; color: #222; }
  h1 { border-bottom: 2px solid #4285F4; padding-bottom: 8px; }
  .kpi-grid { display: flex; flex-wrap: wrap; gap: 16px; margin: 24px 0; }
  .kpi { background: #f4f6fa; border-radius: 8px; padding: 16px 20px; min-width: 140px; }
  .kpi .label { font-size: 12px; color: #666; text-transform: uppercase; }
  .kpi .value { font-size: 22px; font-weight: 600; color: #1a73e8; }
  table { border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 13px; }
  th, td { border: 1px solid #ddd; padding: 6px 10px; text-align: left; }
  th { background: #f4f6fa; }
  .flag { color: #d93025; font-weight: 600; }
  img { max-width: 100%; margin: 16px 0; }
</style>
</head>
<body>
  <h1>Google Ads Performance Report</h1>
  <p>Generated {{ generated }} · Last {{ summary.days }} days</p>

  <div class="kpi-grid">
    <div class="kpi"><div class="label">Spend</div><div class="value">${{ summary.total_cost }}</div></div>
    <div class="kpi"><div class="label">Clicks</div><div class="value">{{ summary.total_clicks }}</div></div>
    <div class="kpi"><div class="label">Conversions</div><div class="value">{{ summary.total_conversions }}</div></div>
    <div class="kpi"><div class="label">Avg CTR</div><div class="value">{{ (summary.avg_ctr * 100) | round(2) }}%</div></div>
    <div class="kpi"><div class="label">Avg CPC</div><div class="value">${{ summary.avg_cpc }}</div></div>
    <div class="kpi"><div class="label">ROAS</div><div class="value">{{ summary.overall_roas }}x</div></div>
  </div>

  {% if chart_path %}<img src="{{ chart_path }}" alt="Spend by campaign">{% endif %}

  <h2>Underperforming campaigns <span class="flag">(spend, no conversions)</span></h2>
  {% if summary.underperforming_campaigns %}
    <ul>{% for c in summary.underperforming_campaigns %}<li>{{ c }}</li>{% endfor %}</ul>
  {% else %}<p>None flagged.</p>{% endif %}

  <h2>Top wasted-spend keywords <span class="flag">(clicks, zero conversions)</span></h2>
  <table>
    <tr><th>Keyword</th><th>Match type</th><th>Campaign</th><th>Clicks</th><th>Cost</th></tr>
    {% for k in summary.wasted_spend_keywords %}
    <tr><td>{{ k.keyword }}</td><td>{{ k.match_type }}</td><td>{{ k.campaign_name }}</td>
        <td>{{ k.clicks }}</td><td>${{ "%.2f"|format(k.cost) }}</td></tr>
    {% endfor %}
  </table>

  <h2>Converting keywords losing traffic to low impression share</h2>
  <table>
    <tr><th>Keyword</th><th>Campaign</th><th>Conversions</th><th>Impression share</th></tr>
    {% for k in summary.low_impression_share_keywords %}
    <tr><td>{{ k.keyword }}</td><td>{{ k.campaign_name }}</td><td>{{ k.conversions }}</td>
        <td>{{ (k.impression_share * 100) | round(1) }}%</td></tr>
    {% endfor %}
  </table>

  <h2>Full campaign data</h2>
  {{ campaigns_table | safe }}
</body>
</html>
"""


def build_chart(campaigns_df, out_path: Path):
    if campaigns_df.empty:
        return None
    top = campaigns_df.nlargest(10, "cost")
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(top["campaign_name"], top["cost"], color="#4285F4")
    ax.set_xlabel("Spend ($)")
    ax.set_title("Spend by campaign (top 10)")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path.name


def generate_report(analysis: dict) -> Path:
    OUT_DIR.mkdir(exist_ok=True)
    campaigns, keywords, summary = analysis["campaigns"], analysis["keywords"], analysis["summary"]

    campaigns.to_csv(OUT_DIR / "campaigns.csv", index=False)
    keywords.to_csv(OUT_DIR / "keywords.csv", index=False)

    chart_name = build_chart(campaigns, OUT_DIR / "spend_by_campaign.png")

    campaigns_table = (
        campaigns[["campaign_name", "status", "cost", "clicks", "conversions", "ctr", "avg_cpc", "roas"]]
        .to_html(index=False, float_format=lambda x: f"{x:,.2f}")
        if not campaigns.empty else "<p>No campaign data.</p>"
    )

    html = Template(HTML_TEMPLATE).render(
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        summary=summary,
        chart_path=chart_name,
        campaigns_table=campaigns_table,
    )
    report_path = OUT_DIR / "report.html"
    report_path.write_text(html)
    print(f"Report written to {report_path}")
    return report_path
