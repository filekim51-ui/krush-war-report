import os
import asyncio
import datetime
import coc
import nest_asyncio
from flask import Flask, render_template_string

app = Flask(__name__)

# --- Supercell Developer Portal credentials ---
COC_EMAIL = os.environ.get("COC_EMAIL") or "YOUR_EMAIL"
COC_PASSWORD = os.environ.get("COC_PASSWORD") or "YOUR_PASSWORD"

# --- Clans ---
CLANS = {
    "Krush War": "#29P2VLJP",
    "Krush Family": "#2L2UP98LU",
    "불난 집에 부채질": "#9VPPJU8Y",
}

# --- Init coc client ---
client = coc.Client(key_names="krush-auto")

# --- Helper functions ---
def time_diff_str(dt):
    delta = dt - datetime.datetime.now(datetime.timezone.utc)
    hrs, rem = divmod(int(delta.total_seconds()), 3600)
    mins = rem // 60
    sign = "" if delta.total_seconds() >= 0 else "-"
    return f"{sign}{abs(hrs)}h {abs(mins)}m"


async def fetch_war_summary(tag):
    try:
        war = await client.get_current_war(tag)
    except coc.PrivateWarLog:
        return {"state": "private", "missing": ["N/A"], "stars": "?", "attacks_left": "?"}
    except coc.Maintenance:
        return {"state": "maintenance", "missing": ["N/A"], "stars": "?", "attacks_left": "?"}
    except Exception as e:
        print(f"⚠️ Error fetching {tag}: {e}")
        return {"state": "error", "missing": ["N/A"], "stars": "?", "attacks_left": "?"}

    # not in war
    if war.state == "notInWar":
        return {"state": "notInWar", "missing": ["N/A"]}

    clan = war.clan
    attacks_per_member = 1 if war.is_cwl else 2
    missing = ["NA"] if war.state == "preparation" else [
        m.name for m in clan.members if len(m.attacks) < attacks_per_member
    ]

    return {
        "state": war.state,
        "stars": clan.stars,
        "attacks_left": len(missing),
        "missing": missing or ["None"],
        "start_time": time_diff_str(war.start_time) if war.start_time else "N/A",
        "end_time": time_diff_str(war.end_time) if war.end_time else "N/A",
        "type": "CWL War" if war.is_cwl else "Regular War",
    }


@app.route("/")
def home():
    return "<h3>✅ Server running. Go to <a href='/warsummary'>/warsummary</a></h3>"


@app.route("/warsummary")
def summarize_all():
    async def gather_all():
        tasks = [fetch_war_summary(tag) for tag in CLANS.values()]
        return await asyncio.gather(*tasks)

    results = asyncio.get_event_loop().run_until_complete(gather_all())

    output = []
    for i, (name, _) in enumerate(CLANS.items()):
        r = results[i]
        output.append(f"""
🛡️ <b>{name}</b>: {r.get('stars', '?')}⭐, {r.get('attacks_left', '?')}공 남음 ({r.get('type', '')})<br>
{"🕒 " + r.get('end_time', '') + " 후 종료<br>" if r.get('state') == 'inWar' else ""}
{"🕒 " + r.get('start_time', '') + " 후 시작<br>" if r.get('state') == 'preparation' else ""}
⚔️ 미공격:<br>{'<br>'.join(r['missing'])}<br><br>
""")

    return render_template_string("<html><body style='font-family: Menlo, monospace;'>"
                                  + "".join(output) + "</body></html>")


if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()

    loop = asyncio.get_event_loop()

    async def start():
        try:
            await client.login_with_tokens(
                COC_EMAIL, 
                COC_PASSWORD, 
                keys=[os.environ.get("COC_KEY")]
            )
            print("✅ Logged into Clash of Clans API successfully")
        except Exception as e:
            print("❌ Login failed:", e)

    loop.run_until_complete(start())
    app.run(host="0.0.0.0", port=10000)