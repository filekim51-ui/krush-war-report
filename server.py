import os, datetime, requests
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

# --- SET YOUR COC TOKEN HERE TEMPORARILY ---
# later when deploying, use Render's environment variable
TOKEN = os.environ.get("COC_TOKEN") or "YOUR_TOKEN_HERE"

API = "https://api.clashofclans.com/v1"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json",
}

# --- YOUR CLANS ---
CLANS = {
    "Krush War": "#29P2VLJP",
    "Krush Family": "#2L2UP98LU",
    "불난 집에 부채질": "#9VPPJU8Y", ##9VPPJU8Y
}

# --- HELPERS ---
def enc(tag):
    return tag.replace("#", "%23")

def get_json(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    if r.status_code == 403:
        return {"error": "403 Forbidden"}
    if r.status_code == 404:
        return {"state": "notInWar"}
    r.raise_for_status()
    return r.json()

def parse_time(s):
    # example: 20251102T153220.000Z
    return datetime.datetime.strptime(s, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=datetime.timezone.utc)

def time_diff_str(dt):
    delta = dt - datetime.datetime.now(datetime.timezone.utc)
    hrs, rem = divmod(int(delta.total_seconds()), 3600)
    mins = rem // 60
    sign = "" if delta.total_seconds() >= 0 else "-"
    return f"{sign}{abs(hrs)}h {abs(mins)}m"

# --- CWL WAR FINDER ---
def get_active_cwl_war(tag, lg):
    active_war = None
    prep_war = None

    for rnd in lg.get("rounds", []):
        for wt in rnd.get("warTags", []):
            if wt and wt != "#0":
                war_data = get_json(f"{API}/clanwarleagues/wars/{enc(wt)}")
                if "error" in war_data:
                    continue
                state = war_data.get("state")
                clan_tags = [
                    war_data.get("clan", {}).get("tag"),
                    war_data.get("opponent", {}).get("tag"),
                ]
                if tag not in clan_tags:
                    continue
                if state == "inWar":
                    return war_data  # prefer active war
                elif state == "preparation":
                    prep_war = war_data
    return prep_war

# --- REGULAR WAR SUMMARY ---
def summarize_regular_war(clan_name, tag):
    data = get_json(f"{API}/clans/{enc(tag)}/currentwar")
    if "error" in data:
        return {"clan": clan_name, "state": "error", "error": data["error"]}
    state = data.get("state", "unknown")
    if state == "notInWar":
        return {"clan": clan_name, "state": "notInWar"}

    attacks_per_member = 1 if data.get("warType") == "CWL" else 2
    team = data.get("clan", {})
    total_attacks = len(data.get("attacks", []))
    members = team.get("members", [])
    if state == "preparation":
        missing = ["NA"]
    else:
        missing = [m["name"] for m in members if len(m.get("attacks", [])) < attacks_per_member]

    start_time = data.get("startTime")
    end_time = data.get("endTime")

    if start_time:
        start = parse_time(start_time)
        end = parse_time(end_time)
        start_in = time_diff_str(start)
        end_in = time_diff_str(end)
    else:
        start_in = end_in = "N/A"

    return {
        "clan": clan_name,
        "state": state,
        "stars": team.get("stars", 0),
        "attacks_left": len(missing),
        "missing": missing or ["None"],
        "start_time": start_in,
        "end_time": end_in,
        "type": "Regular War",
    }

# --- MAIN SUMMARY ---
@app.route("/warsummary")
def summarize_all():
    results = []
    for name, tag in CLANS.items():
        # First check regular war
        data = get_json(f"{API}/clans/{enc(tag)}/currentwar")

        if data.get("state") in ["inWar", "preparation"]:
            result = summarize_regular_war(name, tag)
        elif data.get("state") == "notInWar":
            # Check if in CWL
            lg = get_json(f"{API}/clans/{enc(tag)}/currentwar/leaguegroup")
            if "error" not in lg:
                cwl_data = get_active_cwl_war(tag, lg)
                if cwl_data:
                    clan_side = (
                        cwl_data["clan"] if cwl_data["clan"]["tag"] == tag else cwl_data["opponent"]
                    )
                    state = cwl_data["state"]
                    attacks_per_member = 1
                    members = clan_side.get("members", [])
                    if cwl_data.get("state") == "preparation":
                        missing = ["NA"]
                    else:
                        missing = [m["name"] for m in members if len(m.get("attacks", [])) < attacks_per_member]

                    start_time = cwl_data.get("startTime")
                    end_time = cwl_data.get("endTime")
                    if start_time:
                        start = parse_time(start_time)
                        end = parse_time(end_time)
                        start_in = time_diff_str(start)
                        end_in = time_diff_str(end)
                    else:
                        start_in = end_in = "N/A"

                    results.append({
                        "clan": name,
                        "state": state,
                        "stars": clan_side.get("stars", 0),
                        "attacks_left": len(missing),
                        "missing": missing or ["None"],
                        "start_time": start_in,
                        "end_time": end_in,
                        "type": "CWL War",
                    })
                    continue
            result = {"clan": name, "state": "notInWar"}
        else:
            # handle private war logs or denied access
            if data.get("reason") == "accessDenied" or "403" in str(data.get("error", "")):
                result = {
                    "clan": name,
                    "state": "private",
                    "stars": "?",
                    "attacks_left": "?",
                    "missing": ["N/A"],
                    "time": "War log is private (cannot fetch data)",
                    "type": "",
                }
            else:
                result = {"clan": name, "state": "unknown"}
        results.append(result)

    # Simple web template output
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
    app.run(host="0.0.0.0", port=10000)