"""matches.json + members.json -> leaderboard.json  (100점 배점)

판마다 양 팀 10명 안에서 각 지표의 순위(0~1)를 매겨 점수로 바꿉니다.
  팀 딜 기여도 (DS = 내 딜 / 우리 팀 딜)             25점
  킬 관여율   (KP = (킬+어시) / 우리 팀 킬)          20점
  KDA·생존력  ((킬+어시) / 데스, 데스 0이면 1로)     15점
  역할 수행도 (TS = 내가 받은 피해 / 우리 팀 받은 피해) 20점
  결정적 기여 (그 판 MVP 10점, ACE 5점)               10점
  -> 판 점수 0~90점, 이걸 판마다 구해서 평균
  경기별 안정성 (판 점수 표준편차가 작을수록)           10점
     10 * (25 - 표준편차) / 15, 0~10으로 자름 (3판 미만은 5점)
MVP = 이긴 팀에서 앞의 4개 지표 합이 가장 높은 사람, ACE = 진 팀에서 가장 높은 사람.
CC·회복·보호막·게임 시간은 전적 데이터에 없어서 빠져 있어요 (DPM도 같은 이유로 제외).
"""
import json
import math
import statistics as st
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

W_DS, W_KP, W_KDA, W_TS = 25, 20, 15, 20
MVP_PTS, ACE_PTS = 10, 5
TIER_CUTS = [(55, "S"), (47, "A"), (40, "B")]  # 그 아래는 C
FEW_GAMES = 20
REMAKE_TOTAL_KILLS = 10


def rnd(x, d=0):
    """JS의 Math.round와 같은 반올림 (사이트 계산과 결과를 맞추려고)"""
    f = 10 ** d
    v = math.floor(x * f + 0.5) / f
    return int(v) if d == 0 else v


def pct_rank(vals, v):
    below = sum(x < v for x in vals)
    equal = sum(x == v for x in vals) - 1
    return (below + equal / 2) / (len(vals) - 1)


def stability(sd):
    return max(0.0, min(10.0, 10 * (25 - sd) / 15))


def score_match(match):
    players = [(p, t) for t in match["teams"] for p in t["players"]]
    if len(players) != 10:
        return None
    team_dmg = {id(t): max(1, sum(p["damage"] for p in t["players"])) for t in match["teams"]}
    team_tkn = {id(t): max(1, sum(p["taken"] for p in t["players"])) for t in match["teams"]}
    ds = [p["damage"] / team_dmg[id(t)] for p, t in players]
    ts = [p["taken"] / team_tkn[id(t)] for p, t in players]
    kp = [(p["kills"] + p["assists"]) / max(t["kills"], 1) for p, t in players]
    kda = [(p["kills"] + p["assists"]) / max(p["deaths"], 1) for p, _ in players]
    base = [W_DS * pct_rank(ds, ds[i]) + W_KP * pct_rank(kp, kp[i]) + W_KDA * pct_rank(kda, kda[i]) + W_TS * pct_rank(ts, ts[i])
            for i in range(10)]
    win_idx = [i for i, (_, t) in enumerate(players) if t["win"]]
    lose_idx = [i for i in range(10) if i not in win_idx]
    mvp = max(win_idx, key=lambda i: base[i]) if win_idx else None
    ace = max(lose_idx, key=lambda i: base[i]) if lose_idx else None
    rows = []
    for i, (p, t) in enumerate(players):
        bonus = MVP_PTS if i == mvp else ACE_PTS if i == ace else 0
        rows.append({"p": p, "t": t, "score": base[i] + bonus, "mvp": i == mvp, "ace": i == ace,
                     "ds": ds[i], "kp": kp[i], "ts": ts[i]})
    return rows


def tier_of(score):
    for cut, t in TIER_CUTS:
        if score >= cut:
            return t
    return "C"


def load_ko():
    try:
        return json.loads((DATA / "champions_ko.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def main():
    matches = json.loads((DATA / "matches.json").read_text(encoding="utf-8"))
    members = json.loads((DATA / "members.json").read_text(encoding="utf-8"))["members"]
    ko = load_ko()
    guests = {m["name"] for m in members if m.get("guest")}
    alias = {}
    for m in members:
        for a in m.get("aliases", []) + [m["name"], m.get("riotId", "").split("#")[0]]:
            if a:
                alias[a] = m["name"]

    rec = defaultdict(lambda: {"sc": [], "wins": 0, "mvp": 0, "ace": 0, "champs": defaultdict(list), "best": None,
                               "k": 0, "d": 0, "a": 0, "dmg": 0, "tkn": 0, "ds": [], "kp": [], "ts": []})
    used = 0
    for match in matches:
        if sum(t["kills"] for t in match["teams"]) <= REMAKE_TOTAL_KILLS:
            continue
        rows = score_match(match)
        if not rows:
            continue
        used += 1
        for row in rows:
            p, t, s = row["p"], row["t"], row["score"]
            name = alias.get(p["name"])
            if not name:
                continue
            r = rec[name]
            c = ko.get(p["champion"], p["champion"])
            r["sc"].append(s)
            r["wins"] += 1 if t["win"] else 0
            r["mvp"] += row["mvp"]
            r["ace"] += row["ace"]
            r["champs"][c].append(s)
            if r["best"] is None or s > r["best"][1]:
                r["best"] = [c, rnd(s, 1)]
            r["k"] += p["kills"]; r["d"] += p["deaths"]; r["a"] += p["assists"]
            r["dmg"] += p["damage"]; r["tkn"] += p["taken"]
            r["ds"].append(row["ds"]); r["kp"].append(row["kp"]); r["ts"].append(row["ts"])

    players = []
    for name, r in rec.items():
        sc, n = r["sc"], len(r["sc"])
        game_avg = st.mean(sc)
        sd = st.stdev(sc) if n > 1 else 0.0
        stab = stability(sd) if n >= 3 else 5.0
        total = game_avg + stab
        se = sd / n ** 0.5 if n > 1 else 20.0
        champs = sorted(([c, len(v), rnd(st.mean(v), 1)] for c, v in r["champs"].items()), key=lambda x: -x[2])
        players.append({
            "name": name, "score": rnd(total, 1),
            "lo": rnd(max(0, total - 1.96 * se), 1), "hi": rnd(min(100, total + 1.96 * se), 1),
            "games": n, "wins": r["wins"], "mvp": r["mvp"], "ace": r["ace"],
            "tier": tier_of(total), "fewGames": n < FEW_GAMES,
            "best": r["best"], "champions": champs,
            "guest": name in guests, "history": [rnd(x, 1) for x in sc],
            "parts": {"game": rnd(game_avg, 1), "stability": rnd(stab, 1), "sd": rnd(sd, 1)},
            "stats": {
                "kda": rnd((r["k"] + r["a"]) / max(r["d"], 1), 2),
                "k": rnd(r["k"] / n, 1), "d": rnd(r["d"] / n, 1), "a": rnd(r["a"] / n, 1),
                "dmg": rnd(r["dmg"] / n), "taken": rnd(r["tkn"] / n),
                "kp": rnd(100 * st.mean(r["kp"]), 1), "ds": rnd(100 * st.mean(r["ds"]), 1), "ts": rnd(100 * st.mean(r["ts"]), 1),
            },
        })
    players.sort(key=lambda p: -p["score"])
    for i, p in enumerate(players):
        p["rank"] = i + 1

    out = {"updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "scale": 100,
           "matchCount": used, "players": players}
    (DATA / "leaderboard.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"leaderboard: {used} matches, {len(players)} players")


if __name__ == "__main__":
    main()
