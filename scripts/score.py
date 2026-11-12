"""matches.json + members.json -> leaderboard.json

판마다 양 팀 10명을 비교해 0~10점을 매깁니다 (op.gg OP 스코어 근사).
  딜량·받은 피해 중 높은 순위 30%, 킬 관여 25%, KDA 20%, 골드 10%, 승리 15%
이긴 팀 최고점은 MVP, 진 팀 최고점은 ACE.
"""
import json
import statistics as st
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

TIER_CUTS = [(6.2, "S"), (5.5, "A"), (5.0, "B")]  # 그 아래는 C
FEW_GAMES = 20  # 이보다 적으면 "판수 적음"
REMAKE_TOTAL_KILLS = 10  # 양 팀 킬 합이 이 이하면 다시하기로 보고 제외


def pct_rank(vals, v):
    below = sum(x < v for x in vals)
    equal = sum(x == v for x in vals) - 1
    return (below + equal / 2) / (len(vals) - 1)


def score_match(match):
    players = []
    for team in match["teams"]:
        for p in team["players"]:
            players.append((p, team))
    if len(players) != 10:
        return None
    dmg = [p["damage"] for p, _ in players]
    tkn = [p["taken"] for p, _ in players]
    gold = [p["gold"] for p, _ in players]
    kp = [(p["kills"] + p["assists"]) / max(t["kills"], 1) for p, t in players]
    kda = [(p["kills"] + p["assists"]) / max(p["deaths"], 1) for p, _ in players]
    scores = []
    for i, (p, t) in enumerate(players):
        contrib = max(pct_rank(dmg, dmg[i]), pct_rank(tkn, tkn[i]))
        s = 10 * (0.30 * contrib + 0.25 * pct_rank(kp, kp[i]) + 0.20 * pct_rank(kda, kda[i])
                  + 0.10 * pct_rank(gold, gold[i]) + 0.15 * (1 if t["win"] else 0))
        scores.append(s)
    win_idx = [i for i, (_, t) in enumerate(players) if t["win"]]
    lose_idx = [i for i in range(10) if i not in win_idx]
    mvp = max(win_idx, key=lambda i: scores[i]) if win_idx else None
    ace = max(lose_idx, key=lambda i: scores[i]) if lose_idx else None
    return [(p, t, scores[i], i == mvp, i == ace) for i, (p, t) in enumerate(players)]


def tier_of(score):
    for cut, t in TIER_CUTS:
        if score >= cut:
            return t
    return "C"


def ko(name):
    try:
        m = json.loads((DATA / "champions_ko.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return name
    return m.get(name, name)


def main():
    matches = json.loads((DATA / "matches.json").read_text(encoding="utf-8"))
    members = json.loads((DATA / "members.json").read_text(encoding="utf-8"))["members"]
    alias = {}
    for m in members:
        for a in m.get("aliases", []) + [m["name"], m.get("riotId", "").split("#")[0]]:
            if a:
                alias[a] = m["name"]

    rec = defaultdict(lambda: {"scores": [], "wins": 0, "mvp": 0, "ace": 0, "champs": defaultdict(list), "best": None})
    used = 0
    for match in matches:
        total = sum(t["kills"] for t in match["teams"])
        if total <= REMAKE_TOTAL_KILLS:
            continue
        rows = score_match(match)
        if not rows:
            continue
        used += 1
        for p, t, s, is_mvp, is_ace in rows:
            name = alias.get(p["name"])
            if not name:
                continue
            r = rec[name]
            r["scores"].append(s)
            r["wins"] += 1 if t["win"] else 0
            r["mvp"] += is_mvp
            r["ace"] += is_ace
            r["champs"][ko(p["champion"])].append(s)
            if r["best"] is None or s > r["best"][1]:
                r["best"] = [ko(p["champion"]), round(s, 1)]

    players = []
    for name, r in rec.items():
        sc = r["scores"]
        mean = st.mean(sc)
        se = st.stdev(sc) / len(sc) ** 0.5 if len(sc) > 1 else 2.0
        champs = sorted(([c, len(v), round(st.mean(v), 2)] for c, v in r["champs"].items()), key=lambda x: -x[2])
        players.append({
            "name": name, "score": round(mean, 2),
            "lo": round(max(0, mean - 1.96 * se), 1), "hi": round(min(10, mean + 1.96 * se), 1),
            "games": len(sc), "wins": r["wins"], "mvp": r["mvp"], "ace": r["ace"],
            "tier": tier_of(mean), "fewGames": len(sc) < FEW_GAMES,
            "best": r["best"], "champions": champs,
        })
    players.sort(key=lambda p: -p["score"])
    for i, p in enumerate(players):
        p["rank"] = i + 1

    out = {
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "matchCount": used,
        "players": players,
    }
    (DATA / "leaderboard.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"leaderboard: {used} matches, {len(players)} players")


if __name__ == "__main__":
    main()
