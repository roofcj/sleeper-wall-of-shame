import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import tracker


class DataRulesTests(unittest.TestCase):
    def test_team_aliases(self):
        self.assertEqual(tracker.canonical_team("JAX"), "JAC")
        self.assertEqual(tracker.canonical_team("WSH"), "WAS")
        self.assertEqual(tracker.canonical_team("LAR"), "LAR")

    def test_final_games_only(self):
        scoreboard = {"events": [
            {"id": "final1", "shortName": "JAX @ DET", "status": {"type": {"completed": True}},
             "competitions": [{"competitors": [{"team": {"abbreviation": "JAX"}},
                                               {"team": {"abbreviation": "DET"}}]}]},
            {"id": "active1", "shortName": "BUF @ NYJ", "status": {"type": {"completed": False}},
             "competitions": [{"competitors": [{"team": {"abbreviation": "BUF"}},
                                               {"team": {"abbreviation": "NYJ"}}]}]},
        ]}
        self.assertEqual(set(tracker.final_teams(scoreboard)), {"JAC", "DET"})

    def test_starters_only_no_bye_or_pending_or_empty_slots(self):
        games = [{"roster_id": 1, "starters": ["a", "b", "c", "d", "0", ""],
                  "starters_points": [0, -0.4, 0, -0.3, 0, 0],
                  "players": ["a", "b", "c", "d", "bench"],
                  "players_points": {"bench": -12}}]
        players = {"a": {"full_name": "Active Zero", "team": "DET", "position": "QB"},
                   "b": {"full_name": "Negative Starter", "team": "JAX", "position": "WR"},
                   "c": {"full_name": "Game Not Over", "team": "BUF", "position": "TE"},
                   "d": {"full_name": "Bye Player", "team": "NYJ", "position": "RB"}}
        owners = {"1": {"manager": "A", "fantasy_team": "Alpha"}}
        finals = {"DET": {"game": "JAX @ DET"}, "JAC": {"game": "JAX @ DET"}}
        events = tracker.extract_week(7, games, players, owners, finals, {})
        self.assertEqual({x["player"] for x in events}, {"Active Zero", "Negative Starter"})
        self.assertEqual([x["points"] for x in events], [-0.4, 0])
        self.assertTrue(all(x["week"] == 7 for x in events))

    def test_missing_points_not_counted_as_zero(self):
        matchups = [{"roster_id": 1, "starters": ["one", "two", "three"],
                     "starters_points": [None, 2.1], "players_points": {"two": 2.1}}]
        people = {"one": {"team": "DET"}, "two": {"team": "DET"}, "three": {"team": "DET"}}
        self.assertEqual(tracker.extract_week(3, matchups, people, {}, {"DET": {"game": "final"}}, {}), [])

    def test_dst_team_name_fallback(self):
        matchups = [{"roster_id": 2, "starters": ["DET"], "starters_points": [-2]}]
        result = tracker.extract_week(4, matchups, {}, {}, {"DET": {"game": "final"}}, {})
        self.assertEqual(result[0]["nfl_team"], "DET")

    def test_leaderboard_counts_each_occurrence(self):
        owners = {"1": {"manager": "A", "fantasy_team": "Alpha"},
                  "2": {"manager": "B", "fantasy_team": "Beta"}}
        entries = [{"roster_id": "1", "week": 1, "points": 0},
                   {"roster_id": "1", "week": 1, "points": -1},
                   {"roster_id": "1", "week": 2, "points": 0},
                   {"roster_id": "2", "week": 1, "points": 0}]
        league = tracker.build_leaderboard(entries, owners)
        self.assertEqual(league[0]["total"], 3)
        self.assertEqual(league[0]["weeks_with_bust"], 2)
        self.assertEqual(league[0]["negative"], 1)
        self.assertEqual(league[1]["total"], 1)

    def test_no_script_injection(self):
        malicious = '</script><script>alert(1)</script>'
        encoded = tracker.safe_json_for_script({"manager": malicious})
        self.assertNotIn("</script>", encoded)
        self.assertEqual(json.loads(encoded), {"manager": malicious})

    def test_integration_backfill_and_corrections(self):
        with tempfile.TemporaryDirectory() as temp:
            data, docs = Path(temp) / 'data', Path(temp) / 'docs'
            data.mkdir()
            today = datetime(2026, 11, 1, 21, tzinfo=timezone.utc)
            points = {1: [0, -1.2], 2: [0, 7.0]}
            calls = []
            def fake_api(url, timeout=25):
                calls.append(url)
                if url.endswith('/league/123456789'):
                    return {"league_id": "123456789", "season": "2026", "name": "Example League"}
                if url.endswith('/state/nfl'):
                    return {"season": "2026", "week": 2, "season_type": "regular"}
                if url.endswith('/rosters'):
                    return [{"roster_id": 1, "owner_id": "u1"}]
                if url.endswith('/users'):
                    return [{"user_id": "u1", "display_name": "Manager", "metadata": {"team_name": "Cool Team"}}]
                if '/matchups/' in url:
                    week = int(url.rsplit('/', 1)[-1])
                    return [{"roster_id": 1, "starters": ["p1", "p2"], "starters_points": points[week]}]
                if '/players/nfl' in url:
                    return {"p1": {"full_name": "Bust", "team": "DET", "position": "QB"},
                            "p2": {"full_name": "Other", "team": "JAX", "position": "WR"}}
                if 'scoreboard' in url:
                    return {"events": [{"shortName": "JAX @ DET", "id": "test",
                                        "status": {"type": {"completed": True}},
                                        "competitions": [{"competitors": [{"team": {"abbreviation": "DET"}},
                                                                          {"team": {"abbreviation": "JAX"}}]}]}]}
                raise AssertionError('Unexpected fetch: ' + url)
            with patch.object(tracker, 'DATA', data), patch.object(tracker, 'DOCS', docs), \
                 patch.object(tracker, 'utc_now', lambda: today), patch.object(tracker, 'get_json', fake_api), \
                 patch.object(tracker, 'post_discord', return_value=True) as notify:
                tracker.run('123456789', webhook='https://example.invalid/webhook')
                result = json.loads((data / 'events.json').read_text())['events']
                self.assertEqual(len(result), 3)
                self.assertTrue((docs/'index.html').exists())
                self.assertTrue((docs/'busts.csv').exists())
                self.assertEqual(notify.call_count, 1)  # Only current-week new bust, not week 1.
                calls.clear()
                tracker.run('123456789', webhook='https://example.invalid/webhook')
                self.assertEqual(notify.call_count, 1)  # No repeat alert.
                self.assertFalse(any('/players/nfl' in call for call in calls))
                points[2] = [5.0, 7.0]  # Stat correction; remove previously recorded zero.
                tracker.run('123456789', webhook='https://example.invalid/webhook')
                after = json.loads((data / 'events.json').read_text())['events']
                self.assertEqual(len(after), 2)
                self.assertEqual(json.loads((docs/'leaderboard.json').read_text())['leaderboard'][0]['total'], 2)


if __name__ == '__main__':
    unittest.main()
