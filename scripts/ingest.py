"""전적 텍스트(op.gg/playaram 상세 복사본)를 matches.json에 추가하고 순위를 다시 계산.
사용: python scripts/ingest.py 파일1.txt 파일2.txt ...
이미 있는 판은 자동으로 건너뜀."""
import re, json, sys, hashlib, subprocess, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
MATCHES = ROOT / "data" / "matches.json"
champ_re = re.compile(r"^[A-Za-z']+\d{1,2}$")
kda_re = re.compile(r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s*$")
num = lambda s: int(s.replace(",", "").replace(".", "").strip())

def parse(text):
    L = [l.rstrip("\n") for l in text.splitlines()]
    i, teams = 0, []
    while i < len(L):
        s = L[i].strip()
        if s in ("Đội Xanh", "Đội Đỏ", "ội Xanh", "ội Đỏ") and i + 2 < len(L) and L[i+1].strip() in ("Thắng", "Thua"):
            win = L[i+1].strip() == "Thắng"; tk = int(L[i+2].strip())
            j, players = i + 3, []
            while j < len(L) and len(players) < 5:
                if L[j].startswith("Người chơi"): j += 1; continue
                if champ_re.match(L[j].strip()) and j + 1 < len(L):
                    ch = re.sub(r"\d+$", "", L[j].strip()); name = L[j+1].strip()
                    k = j + 2
                    while k < len(L) and not kda_re.search(L[k]): k += 1
                    if k + 4 >= len(L): break
                    K, D, A = map(int, kda_re.search(L[k]).groups())
                    players.append(dict(name=name, champion=ch, kills=K, deaths=D, assists=A,
                        damage=num(L[k+2]), taken=num(L[k+3]), gold=num(L[k+4].split("\t")[0])))
                    j = k + 5; continue
                j += 1
            teams.append(dict(win=win, kills=tk, players=players)); i = j; continue
        i += 1
    return [[a, b] for a, b in zip(teams[0::2], teams[1::2]) if len(a["players"]) == 5 and len(b["players"]) == 5]

def key(teams):
    return tuple(sorted((p["champion"], p["kills"], p["deaths"], p["assists"], p["damage"]) for t in teams for p in t["players"]))

def main(paths):
    data = json.loads(MATCHES.read_text(encoding="utf-8"))
    seen = {key(m["teams"]) for m in data}
    added = 0
    for p in paths:
        for teams in parse(pathlib.Path(p).read_text(encoding="utf-8")):
            k = key(teams)
            if k in seen: continue
            seen.add(k); added += 1
            data.append({"id": "op-" + hashlib.sha1(repr(k).encode()).hexdigest()[:10], "date": None, "source": "paste", "teams": teams})
    MATCHES.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"새 판 {added}개 추가 (총 {len(data)}판)")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "score.py")], check=True)

if __name__ == "__main__":
    main(sys.argv[1:])
