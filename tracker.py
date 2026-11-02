#!/usr/bin/env python3
"""Sleeper Fantasy Wall of Shame — standard-library-only league tracker.

Public sources:
  https://api.sleeper.app/v1 (league matchups, roster members, players, NFL state)
  https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard
No Sleeper login or API key required.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import html
import io
import json
import math
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"
SLEEPER = "https://api.sleeper.app/v1"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
USER_AGENT = "SleeperWallOfShame/1.0 (league fantasy scoreboard)"
# Preconfigured league; override using --league-id or SLEEPER_LEAGUE_ID if needed.
DEFAULT_LEAGUE_ID = "1391788553402347520"

# Different feeds occasionally use different abbreviations for the same NFL team.
ALIASES = {
    "JAX": "JAC", "JAC": "JAC", "WAS": "WAS", "WSH": "WAS",
    "LA": "LAR", "LAR": "LAR", "SD": "LAC", "LAC": "LAC",
    "OAK": "LV", "LV": "LV", "STL": "LAR",
}


def canonical_team(value):
    value = str(value or "").strip().upper()
    return ALIASES.get(value, value)


def utc_now():
    return datetime.now(timezone.utc)


def get_json(url, timeout=25):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        raise RuntimeError(f"Couldn't fetch {url}: {exc}") from exc


def post_discord(webhook, content):
    body = json.dumps({"content": content, "allowed_mentions": {"parse": []}}).encode("utf-8")
    req = urllib.request.Request(
        webhook, data=body, method="POST",
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"WARNING: Discord notification failed: {exc}", file=sys.stderr)
        return False


def load_json(path, fallback):
    if path.exists():
        try:
            with path.open(encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"Cannot read {path}: {exc}") from exc
    return fallback


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def valid_points(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
        return round(numeric, 2) if math.isfinite(numeric) else None
    except (TypeError, ValueError):
        return None


def starter_score(matchup, index, player_id):
    """Use slot-aligned score first; never use total team points or bench scores."""
    scores = matchup.get("starters_points")
    if isinstance(scores, list) and index < len(scores):
        return valid_points(scores[index])
    roster_points = matchup.get("players_points") or {}
    if isinstance(roster_points, dict) and player_id in roster_points:
        return valid_points(roster_points[player_id])
    return None  # Missing means unknown, NOT zero.


def final_teams(scoreboard):
    """Return {team: game info} only for NFL games explicitly marked final."""
    if not isinstance(scoreboard, dict) or not isinstance(scoreboard.get("events"), list):
        raise RuntimeError("ESPN returned an unrecognized scoreboard response")
    finals = {}
    for event in scoreboard["events"]:
        competition = (event.get("competitions") or [{}])[0]
        status = event.get("status") or competition.get("status") or {}
        if not (status.get("type") or {}).get("completed", False):
            continue
        competitors = competition.get("competitors") or []
        for competitor in competitors:
            team = canonical_team((competitor.get("team") or {}).get("abbreviation"))
            if team:
                finals[team] = {"game": event.get("shortName") or event.get("name") or "NFL game",
                                "game_id": str(event.get("id", ""))}
    return finals


def team_for_player(player_id, player, week_teams):
    if player_id in week_teams:
        return canonical_team(week_teams[player_id])
    team = canonical_team(player.get("team"))
    if not team and re.fullmatch(r"[A-Z]{2,3}", player_id):
        team = canonical_team(player_id)  # D/ST can be identified directly by team abbreviation.
    if team:
        week_teams[player_id] = team  # Keep weekly snapshots when NFL players change teams.
    return team


def player_name(player_id, info):
    full = info.get("full_name")
    if not full:
        full = " ".join(str(info.get(key) or "") for key in ("first_name", "last_name")).strip()
    return str(full or (f"{player_id} D/ST" if re.fullmatch(r"[A-Z]{2,3}", player_id) else f"Player {player_id}"))


def extract_week(week, matchups, player_info, roster_to_owner, finals, week_teams):
    if not isinstance(matchups, list):
        raise RuntimeError(f"Sleeper's week {week} matchup response was not a list")
    result = []
    for match in matchups:
        roster_id = match.get("roster_id")
        if roster_id is None:
            continue
        owner = roster_to_owner.get(str(roster_id), {})
        starters = match.get("starters") or []
        for index, value in enumerate(starters):
            player_id = str(value or "")
            if player_id in ("", "0", "None", "null"):
                continue
            player = player_info.get(player_id, {})
            team = team_for_player(player_id, player, week_teams)
            if not team or team not in finals:
                continue  # NFL game not completed, or bye/unknown team.
            points = starter_score(match, index, player_id)
            if points is None or points > 0:
                continue
            result.append({
                "week": week,
                "roster_id": str(roster_id),
                "manager": owner.get("manager", f"Roster {roster_id}"),
                "fantasy_team": owner.get("fantasy_team", f"Team {roster_id}"),
                "player_id": player_id,
                "player": player_name(player_id, player),
                "position": player.get("position") or ("DEF" if player_id == team else "—"),
                "nfl_team": team,
                "points": points,
                "type": "Negative" if points < 0 else "Zero",
                "nfl_game": finals[team]["game"],
            })
    return sorted(result, key=lambda x: (x["points"], x["roster_id"], x["player"]))


def event_key(event, season):
    return f"{season}:{event['week']}:{event['roster_id']}:{event['player_id']}"


def roster_names(rosters, users):
    user_map = {str(u.get("user_id")): u for u in users if u.get("user_id") is not None}
    owners = {}
    for r in rosters:
        roster_id = r.get("roster_id")
        if roster_id is None:
            continue
        user = user_map.get(str(r.get("owner_id")), {})
        manager = user.get("display_name") or user.get("username") or f"Manager {roster_id}"
        team = (user.get("metadata") or {}).get("team_name") or manager
        owners[str(roster_id)] = {"manager": str(manager), "fantasy_team": str(team)}
    return owners


def build_leaderboard(events, owners):
    counters = {
        roster_id: {"roster_id": roster_id, "manager": val["manager"],
                    "fantasy_team": val["fantasy_team"], "total": 0, "zero": 0,
                    "negative": 0, "worst": None, "weeks": set()}
        for roster_id, val in owners.items()
    }
    for entry in events:
        rid = entry["roster_id"]
        if rid not in counters:
            counters[rid] = {"roster_id": rid, "manager": entry["manager"],
                             "fantasy_team": entry["fantasy_team"], "total": 0,
                             "zero": 0, "negative": 0, "worst": None, "weeks": set()}
        row = counters[rid]
        row["total"] += 1
        row["negative" if entry["points"] < 0 else "zero"] += 1
        row["worst"] = entry["points"] if row["worst"] is None else min(row["worst"], entry["points"])
        row["weeks"].add(entry["week"])
    for row in counters.values():
        row["weeks_with_bust"] = len(row.pop("weeks"))
    return sorted(counters.values(), key=lambda x: (-x["total"], -x["negative"], x["fantasy_team"].lower()))


def safe_json_for_script(value):
    # Prevent input like '</script>' in an owner or team name closing the data script element.
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def render_dashboard(payload, demo=False):
    template = (ROOT / "dashboard_template.html").read_text(encoding="utf-8")
    output = template.replace("__DASHBOARD_DATA__", safe_json_for_script(payload))
    output = output.replace("__PAGE_TITLE__", html.escape(str(payload["league"])))
    output = output.replace("__DEMO_CLASS__", "true" if demo else "false")
    return output


def write_exports(payload, demo=False):
    DOCS.mkdir(exist_ok=True, parents=True)
    (DOCS / ("demo.html" if demo else "index.html")).write_text(render_dashboard(payload, demo), encoding="utf-8")
    if not demo:
        with (DOCS / "busts.csv").open("w", newline="", encoding="utf-8") as f:
            columns = ["week", "manager", "fantasy_team", "player", "position", "nfl_team", "points", "type", "nfl_game"]
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(sorted(payload["events"], key=lambda e: (-e["week"], e["points"])))
        write_json(DOCS / "leaderboard.json", payload)


def send_new_alerts(webhook, season, current_week, events, sent_keys, league_name):
    if not webhook:
        return []
    new = [x for x in events if x["week"] == current_week and event_key(x, season) not in sent_keys]
    if not new:
        return []
    success = []
    for offset in range(0, len(new), 10):
        batch = new[offset:offset + 10]
        lines = [f"🏈 **Wall of Shame | {league_name} | Week {current_week}**",
                 "New zero/negative starts after an NFL game finished:"]
        for x in batch:
            player = x["player"].replace("@", "@\u200b").replace("`", "'")
            team = x["fantasy_team"].replace("@", "@\u200b").replace("`", "'")
            lines.append(f"💀 **{player}** ({x['nfl_team']}): **{x['points']:.2f} pts** — {team}")
        lines.append("Leaderboard and full results: check your Wall of Shame dashboard.")
        content = "\n".join(lines)
        if len(content) > 1950:
            content = content[:1940] + "…"
        if post_discord(webhook, content):
            success += [event_key(x, season) for x in batch]
    return success


def load_player_index(required_ids, today):
    path = DATA / "player_index.json"
    cache = load_json(path, {"fetched_on": "", "players": {}})
    players = cache.get("players") or {}
    missing = [id for id in required_ids if id not in players]
    if cache.get("fetched_on") != today or missing:
        try:
            full = get_json(f"{SLEEPER}/players/nfl")
            if not isinstance(full, dict):
                raise RuntimeError("unexpected Sleeper player list")
            for pid in required_ids:
                p = full.get(pid) or {}
                if not isinstance(p, dict):
                    p = {}
                players[pid] = {"full_name": player_name(pid, p),
                                "position": p.get("position"), "team": p.get("team")}
            write_json(path, {"fetched_on": today, "players": players})
            print(f"Refreshed player index ({len(required_ids)} IDs).")
        except RuntimeError as exc:
            if missing:
                raise RuntimeError(f"Player names/teams are missing and refresh failed: {exc}") from exc
            print(f"WARNING: Using cached player data: {exc}", file=sys.stderr)
    return players


def run(league_id, force_all=False, webhook=""):
    if not re.fullmatch(r"\d{8,25}", league_id):
        raise RuntimeError("Provide the numeric Sleeper league ID (not the complete URL).")
    DATA.mkdir(parents=True, exist_ok=True)
    now = utc_now()
    today = now.date().isoformat()
    league = get_json(f"{SLEEPER}/league/{league_id}")
    if not isinstance(league, dict) or not league.get("league_id"):
        raise RuntimeError("Sleeper league not found. Check the league ID.")
    season = str(league.get("season") or "")
    if not re.fullmatch(r"20\d{2}", season):
        raise RuntimeError("Sleeper returned an invalid NFL season")
    state_path = DATA / "state.json"
    state = load_json(state_path, {})
    # Prevent mixing records if configuration changes to a different league/season.
    if state.get("identity") != f"{league_id}:{season}":
        state = {"identity": f"{league_id}:{season}", "last_full_refresh": "",
                 "week_teams": {}, "sent_alerts": []}
    stored = load_json(DATA / "events.json", {"identity": "", "events": []})
    events_by_week = {}
    if stored.get("identity") == state["identity"]:
        for e in stored.get("events", []):
            events_by_week.setdefault(int(e["week"]), []).append(e)

    nfl_state = get_json(f"{SLEEPER}/state/nfl")
    active_season = str(nfl_state.get("season") or "")
    if season == active_season:
        if str(nfl_state.get("season_type") or "").lower() in ("post", "postseason"):
            current_week = 18
        else:
            current_week = max(1, min(int(nfl_state.get("week") or 1), 18))
    elif int(season) < int(active_season or season):
        current_week = 18
    else:
        current_week = 1
    owners = roster_names(get_json(f"{SLEEPER}/league/{league_id}/rosters"),
                          get_json(f"{SLEEPER}/league/{league_id}/users"))

    is_full = force_all or state.get("last_full_refresh") != today or not events_by_week
    weeks = list(range(1, current_week + 1)) if is_full else sorted(set([max(1, current_week - 1), current_week]))
    # Fetch matchups first to know which players need to be present in the cached player map.
    matchups_by_week = {}
    for week in weeks:
        matchups = get_json(f"{SLEEPER}/league/{league_id}/matchups/{week}")
        if not isinstance(matchups, list):
            raise RuntimeError(f"Sleeper returned unexpected matchups for week {week}")
        matchups_by_week[week] = matchups
    required_ids = {
        str(pid) for games in matchups_by_week.values() for game in games
        for pid in (game.get("starters") or []) if str(pid or "") not in ("", "0", "None")
    }
    player_index = load_player_index(required_ids, today) if required_ids else {}

    scanned = 0
    for week, matchups in matchups_by_week.items():
        scoreboard_url = ESPN
        scoreboard_url += "?" + urllib.parse.urlencode({"dates": season, "seasontype": "2", "week": week, "limit": 100})
        scoreboard = get_json(scoreboard_url)
        completed = final_teams(scoreboard)
        snapshot = state["week_teams"].setdefault(str(week), {})
        events_by_week[week] = extract_week(week, matchups, player_index, owners, completed, snapshot)
        scanned += 1
    if is_full:
        state["last_full_refresh"] = today

    events = [e for w in sorted(events_by_week) for e in events_by_week[w]]
    leaderboard = build_leaderboard(events, owners)
    payload = {"league": str(league.get("name") or "Sleeper League"),
               "season": season, "current_week": current_week, "updated_at": now.isoformat(timespec="seconds"),
               "league_id": league_id, "events": events, "leaderboard": leaderboard}
    previous_publish = load_json(DOCS / "leaderboard.json", {})
    stable_fields = ("league", "season", "current_week", "league_id", "events", "leaderboard")
    if previous_publish and all(previous_publish.get(k) == payload.get(k) for k in stable_fields):
        # Don't change the dashboard every half-hour when the actual results are unchanged.
        payload["updated_at"] = previous_publish.get("updated_at", payload["updated_at"])
    write_json(DATA / "events.json", {"identity": state["identity"], "events": events})
    write_exports(payload)
    sent = set(state.get("sent_alerts") or [])
    new_sent = send_new_alerts(webhook, season, current_week, events, sent, payload["league"])
    state["sent_alerts"] = sorted(sent | set(new_sent))
    write_json(state_path, state)
    print(f"Updated {payload['league']} ({season}) | scanned {scanned} weeks | {len(events)} total busts"
          f" | {len(new_sent)} new Discord alerts")
    print(f"Dashboard: {DOCS / 'index.html'}")


def demo_payload():
    # Clearly labeled fictitious dataset, not attached to any Sleeper league.
    teams = [("1", "Bench Warmers", "Alex"), ("2", "Fourth & Regret", "Jordan"),
             ("3", "Sunday Scaries", "Taylor"), ("4", "Waiver Wire Warriors", "Morgan"),
             ("5", "Zero Dark Thirty", "Casey"), ("6", "Hail Mary", "Riley")]
    example = [
        (1, 1, "Quarterback X", "QB", "DET", -1.2), (1, 2, "Receiver Y", "WR", "BUF", 0),
        (2, 1, "Running Back Z", "RB", "CHI", 0), (2, 3, "Receiver T", "WR", "SEA", -0.6),
        (3, 4, "Tight End Q", "TE", "PHI", 0), (4, 1, "Running Back C", "RB", "KC", 0),
        (4, 2, "Defense D", "DEF", "LV", -3), (5, 5, "Receiver A", "WR", "NYJ", 0),
        (6, 3, "Quarterback E", "QB", "ATL", -0.8), (7, 2, "Tight End F", "TE", "GB", 0),
        (7, 4, "Receiver G", "WR", "SF", 0), (8, 1, "Receiver H", "WR", "MIA", -0.1),
        (8, 6, "Running Back I", "RB", "IND", 0), (9, 4, "Receiver J", "WR", "TB", 0),
        (9, 5, "Defense K", "DEF", "CAR", -2), (9, 1, "Running Back L", "RB", "LAC", 0)
    ]
    owners = {rid: {"manager": owner, "fantasy_team": name} for rid, name, owner in teams}
    events = [{"week": week, "roster_id": str(rid), "manager": owners[str(rid)]["manager"],
               "fantasy_team": owners[str(rid)]["fantasy_team"], "player_id": f"demo{i}",
               "player": player, "position": position, "nfl_team": nfl_team, "points": float(pts),
               "type": "Negative" if pts < 0 else "Zero", "nfl_game": "Sample final game"}
              for i, (week, rid, player, position, nfl_team, pts) in enumerate(example)]
    return {"league": "Sample Fantasy League", "season": "2026", "current_week": 9,
            "updated_at": utc_now().isoformat(timespec="seconds"), "league_id": "DEMO",
            "events": events, "leaderboard": build_leaderboard(events, owners)}


def main():
    parser = argparse.ArgumentParser(description="Track every Sleeper starter that scores zero or below after their NFL game ends.")
    parser.add_argument("--league-id", default=os.getenv("SLEEPER_LEAGUE_ID", DEFAULT_LEAGUE_ID), help="Numeric Sleeper league ID (defaults to your league)")
    parser.add_argument("--refresh-all", action="store_true", help="Recheck every week, even if already scanned today")
    parser.add_argument("--demo", action="store_true", help="Generate a sample webpage without accessing any APIs")
    args = parser.parse_args()
    try:
        if args.demo:
            write_exports(demo_payload(), demo=True)
            print(f"Sample dashboard created: {DOCS / 'demo.html'}")
        else:
            run(args.league_id, args.refresh_all, os.getenv("DISCORD_WEBHOOK_URL", ""))
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
