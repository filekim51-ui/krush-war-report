import os
import asyncio
import datetime
import coc
from flask import Flask, render_template_string

app = Flask(__name__)

# --- Supercell Developer Portal credentials ---
COC_EMAIL = os.environ.get("COC_EMAIL") or "YOUR_EMAIL"
COC_PASSWORD = os.environ.get("COC_PASSWORD") or "YOUR_PASSWORD"

# --- your clans ---
CLANS = {
    "Krush War": "#29P2VLJP",
    "Krush Family": "#2L2UP98LU",
    "불난 집에 부채질": "#9VPPJU8Y",
}

# --- Initialize coc.py client ---
client = coc.Client(key_names="auto-refresh")

def time_diff_str(dt):
    delta = dt - datetime.datetime.now(datetime.timezone.utc)
    hrs, rem = divmod(int(delta.total_seconds()), 3600)
    mins = rem // 60
    sign = "" if delta.total_seconds() >= 0 else "-"
    return f"{sign}{abs(hrs)}h {abs(mins)}m"

def run_async(coro):
    """Allows async functions to run in Flask routes"""
    loop = asyncio.get_event_loop()
    if loop.is_running():
        return asyncio.ensure_future(coro)
    return loop.run_until_complete(coro)

async def fetch_war_summary(tag):
    try:
        war = await client.get_current_war(tag)
    except coc.PrivateWarLog:
        return {
            "state": "private",
            "stars": "?",
            "attacks_left": "?",
            "missing": ["N/A"],
            "start_time": "N/A",
            "end_time": "N/A",
            "type": "",
        }
    except coc.Maintenance:
        return {
            "state": "maintenance",
            "stars": "?",
            "attacks_left": "?",
            "missing": ["N/A"],
            "start_time": "N/A",
            "end_time": "N/A",
            "type": "",
        }

    # handle no war
    if war.state == "notInWar":
        return {"state": "notInWar", "missing": ["N/A"]}

    clan = war.clan
    attacks_per_member = 1 if war.is_cwl else 2

    if war.state == "preparation":
        missing = ["NA"]
    else:
        missing = [
            m.name for m in clan.members
            if len(m.attacks) < attacks_per_member
        ]

    start_in = time_diff_str(war.start_time) if war.start_time else "N/A"
    end_in = time_diff_str(war.end_time) if war.end_time else "N/A"

    return {
        "state": war.state,
        "stars": clan.stars,
        "attacks_left": len(missing),
        "missing": missing or ["None"],
        "start_time": start_in,
        "end_time": end_in,
        "type": "CWL War" if war.is_cwl else "Regular War",
    }

@app.route("/warsummary")
def summarize_all():
    results = []
    for name, tag in CLANS.items():
        data = run_async(fetch_war_summary(tag))
        data["clan"] = name
        results.append(data)

    html = """
    <html><body style="font-family: Menlo, monospace;">
    {% for r in results -%}
    🛡️ <b>{{ r['clan'] }}</b>: {{ r.get('stars', '?') }}⭐, {{ r.get('attacks_left', '?') }}공 남음 ({{ r.get('type', '') }})<br>
    {% if r['state'] == 'inWar' -%}
    🕒 {{ r.get('end_time', '') }} 후 종료<br>
    {% elif r['state'] == 'preparation' -%}
    🕒 {{ r.get('start_time', '') }} 후 시작<br>
    {% endif -%}
    ⚔️ 미공격: {{ ', '.join(r['missing']) }}<br><br>
    {% endfor -%}
    </body></html>
    """
    return render_template_string(html, results=results)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(client.login(COC_EMAIL, COC_PASSWORD))
    app.run(host="0.0.0.0", port=10000)