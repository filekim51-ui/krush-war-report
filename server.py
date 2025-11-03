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

# --- Initialize coc.py v3 client (no key_names now) ---
client = coc.Client()

async def login():
    """Login using the new coc.py v3 syntax."""
    await client.login(email=COC_EMAIL, password=COC_PASSWORD)
    print("✅ Logged into Clash of Clans API")

def time_diff_str(dt):
    delta = dt - datetime.datetime.now(datetime.timezone.utc)
    secs = int(delta.total_seconds())
    hrs, rem = divmod(abs(secs), 3600)
    mins = rem // 60
    sign = "" if secs >= 0 else "-"
    return f"{sign}{hrs}h {mins}m"

def run_async(coro):
    """Allows async functions to run in Flask routes."""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()

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
    except coc.NotFound:
        return {"state": "notInWar", "missing": ["N/A"], "type": ""}

    # handle no war
    if war.state == "notInWar":
        return {"state": "notInWar", "missing": ["N/A"]}

    clan = war.clan
    attacks_per_member = 1 if war.is_cwl else 2

    if war.state == "preparation":
        missing = ["NA"]
    else:
        missing = [m.name for m in clan.members if len(m.attacks) < attacks_per_member]

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
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def gather_all():
        tasks = [fetch_war_summary(tag) for tag in CLANS.values()]
        return await asyncio.gather(*tasks)

    data = loop.run_until_complete(gather_all())
    for (name, tag), d in zip(CLANS.items(), data):
        d["clan"] = name
        results.append(d)

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
    asyncio.run(login())
    app.run(host="0.0.0.0", port=10000)