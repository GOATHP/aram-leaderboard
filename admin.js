// 관리자: 전적 붙여넣기 → 미리보기 → 깃헙에 반영
// 주의: 비밀번호는 화면 잠금용일 뿐이에요. 실제 쓰기 권한은 깃헙 토큰이 있어야 생겨요.
(() => {
const PASS = "1234";
const REPO = "GOATHP/aram-leaderboard", BRANCH = "main";
const TIER_CUTS = [[6.2, "S"], [5.5, "A"], [5.0, "B"]], FEW = 20, REMAKE = 10;
const $ = (t, c, x) => { const e = document.createElement(t); if (c) e.className = c; if (x != null) e.textContent = x; return e; };

// ---------- 파서 (scripts/ingest.py와 같은 규칙) ----------
const champRe = /^[A-Za-z']+\d{1,2}$/, kdaRe = /(\d+)\s*\/\s*(\d+)\s*\/\s*(\d+)\s*$/;
const num = s => parseInt(String(s).replace(/[,.]/g, "").trim(), 10);
function parse(text) {
  const L = text.split(/\r?\n/), teams = []; let i = 0;
  while (i < L.length) {
    const s = L[i].trim();
    if (["Đội Xanh", "Đội Đỏ", "ội Xanh", "ội Đỏ"].includes(s) && i + 2 < L.length && ["Thắng", "Thua"].includes(L[i + 1].trim())) {
      const win = L[i + 1].trim() === "Thắng", kills = parseInt(L[i + 2].trim(), 10);
      let j = i + 3; const players = [];
      while (j < L.length && players.length < 5) {
        if (L[j].startsWith("Người chơi")) { j++; continue; }
        if (champRe.test(L[j].trim()) && j + 1 < L.length) {
          const champion = L[j].trim().replace(/\d+$/, ""), name = L[j + 1].trim();
          let k = j + 2; while (k < L.length && !kdaRe.test(L[k])) k++;
          if (k + 4 >= L.length) break;
          const [, K, D, A] = L[k].match(kdaRe);
          players.push({ name, champion, kills: +K, deaths: +D, assists: +A, damage: num(L[k + 2]), taken: num(L[k + 3]), gold: num(L[k + 4].split("\t")[0]) });
          j = k + 5; continue;
        }
        j++;
      }
      teams.push({ win, kills, players }); i = j; continue;
    }
    i++;
  }
  const out = [];
  for (let t = 0; t + 1 < teams.length; t += 2)
    if (teams[t].players.length === 5 && teams[t + 1].players.length === 5) out.push([teams[t], teams[t + 1]]);
  return out;
}
const keyOf = teams => JSON.stringify(teams.flatMap(t => t.players.map(p => [p.champion, p.kills, p.deaths, p.assists, p.damage])).sort());

// ---------- 점수 (scripts/score.py와 같은 계산) ----------
function pctRank(vals, v) { const below = vals.filter(x => x < v).length, eq = vals.filter(x => x === v).length - 1; return (below + eq / 2) / (vals.length - 1); }
function scoreMatch(m) {
  const P = m.teams.flatMap(t => t.players.map(p => [p, t])); if (P.length !== 10) return null;
  const dmg = P.map(([p]) => p.damage), tkn = P.map(([p]) => p.taken), gold = P.map(([p]) => p.gold);
  const kp = P.map(([p, t]) => (p.kills + p.assists) / Math.max(t.kills, 1)), kda = P.map(([p]) => (p.kills + p.assists) / Math.max(p.deaths, 1));
  const sc = P.map(([, t], i) => 10 * (0.30 * Math.max(pctRank(dmg, dmg[i]), pctRank(tkn, tkn[i])) + 0.25 * pctRank(kp, kp[i]) + 0.20 * pctRank(kda, kda[i]) + 0.10 * pctRank(gold, gold[i]) + 0.15 * (t.win ? 1 : 0)));
  const best = f => { let b = -1; P.forEach(([, t], i) => { if (f(t) && (b < 0 || sc[i] > sc[b])) b = i; }); return b; };
  const mvp = best(t => t.win), ace = best(t => !t.win);
  return P.map(([p, t], i) => [p, t, sc[i], i === mvp, i === ace]);
}
const r2 = (x, d) => Math.round(x * 10 ** d) / 10 ** d;
function leaderboard(matches, members, ko) {
  const guests = new Set(members.filter(m => m.guest).map(m => m.name));
  const alias = {}; members.forEach(m => [...(m.aliases || []), m.name, (m.riotId || "").split("#")[0]].forEach(a => { if (a) alias[a] = m.name; }));
  const rec = {}; let used = 0;
  for (const m of matches) {
    if (m.teams.reduce((s, t) => s + t.kills, 0) <= REMAKE) continue;
    const rows = scoreMatch(m); if (!rows) continue; used++;
    for (const [p, t, s, mv, ac] of rows) {
      const n = alias[p.name]; if (!n) continue;
      const r = rec[n] || (rec[n] = { sc: [], wins: 0, mvp: 0, ace: 0, ch: {}, best: null });
      const c = ko[p.champion] || p.champion;
      r.sc.push(s); r.wins += t.win ? 1 : 0; r.mvp += mv; r.ace += ac; (r.ch[c] = r.ch[c] || []).push(s);
      if (!r.best || s > r.best[1]) r.best = [c, r2(s, 1)];
    }
  }
  const mean = a => a.reduce((x, y) => x + y, 0) / a.length;
  const players = Object.entries(rec).map(([name, r]) => {
    const mu = mean(r.sc), n = r.sc.length;
    const se = n > 1 ? Math.sqrt(r.sc.reduce((s, x) => s + (x - mu) ** 2, 0) / (n - 1)) / Math.sqrt(n) : 2;
    const tier = (TIER_CUTS.find(([c]) => mu >= c) || [0, "C"])[1];
    return { name, score: r2(mu, 2), lo: r2(Math.max(0, mu - 1.96 * se), 1), hi: r2(Math.min(10, mu + 1.96 * se), 1), games: n, wins: r.wins, mvp: r.mvp, ace: r.ace, tier, fewGames: n < FEW, best: r.best, guest: guests.has(name), history: r.sc.map(x => r2(x, 2)),
      champions: Object.entries(r.ch).map(([c, v]) => [c, v.length, r2(mean(v), 2)]).sort((a, b) => b[2] - a[2]) };
  }).sort((a, b) => b.score - a.score);
  players.forEach((p, i) => p.rank = i + 1);
  return { updatedAt: new Date().toISOString().replace(/\.\d+Z$/, "+00:00"), matchCount: used, players };
}

// ---------- 깃헙 반영 ----------
const b64 = s => { const by = new TextEncoder().encode(s); let bin = ""; for (let i = 0; i < by.length; i += 0x8000) bin += String.fromCharCode(...by.subarray(i, i + 0x8000)); return btoa(bin); };
async function gh(path, token, opt = {}) {
  const r = await fetch(`https://api.github.com/repos/${REPO}/contents/${path}?ref=${BRANCH}`, { ...opt, headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json", ...(opt.headers || {}) } });
  if (!r.ok) throw new Error(`${path}: ${r.status} ${(await r.json().catch(() => ({}))).message || ""}`);
  return r.json();
}
async function commit(path, content, msg, token) {
  const cur = await gh(path, token);
  return gh(path, token, { method: "PUT", body: JSON.stringify({ message: msg, content: b64(content), sha: cur.sha, branch: BRANCH }) });
}

// ---------- 화면 ----------
const css = `
.adm-open{position:fixed;right:16px;bottom:16px;z-index:20;font:inherit;font-size:13px;padding:8px 14px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--muted);cursor:pointer;box-shadow:0 2px 10px rgba(0,0,0,.08)}
.adm-open:hover{color:var(--ink)}
.adm-back{position:fixed;inset:0;z-index:30;background:rgba(10,20,30,.45);display:flex;align-items:flex-start;justify-content:center;overflow:auto;padding:40px 12px}
.adm{background:var(--surface);color:var(--ink);border:1px solid var(--line);border-radius:14px;width:min(760px,100%);padding:22px}
.adm h2{margin:0 0 4px;font-size:20px}.adm p{margin:6px 0;font-size:13.5px;color:var(--muted)}
.adm input,.adm textarea{font:inherit;font-size:14px;width:100%;box-sizing:border-box;padding:9px 11px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--ink)}
.adm textarea{min-height:180px;font-family:ui-monospace,monospace;font-size:12px}
.adm .row{display:flex;gap:8px;align-items:center;margin-top:10px;flex-wrap:wrap}
.adm button{font:inherit;font-size:14px;padding:8px 14px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--ink);cursor:pointer}
.adm button.pri{background:var(--accent);border-color:var(--accent);color:#fff}
.adm button:disabled{opacity:.5;cursor:default}
.adm .msg{font-size:13.5px;margin-top:10px;min-height:1em}.adm .msg.bad{color:var(--bad)}.adm .msg.good{color:var(--good)}
.adm table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px}
.adm td,.adm th{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left}.adm th{font-size:12px;color:var(--muted);font-weight:500}
.adm .num{text-align:right;font-variant-numeric:tabular-nums}
.adm .up{color:var(--good)}.adm .down{color:var(--bad)}
.adm details{margin-top:14px;font-size:13px;color:var(--muted)}.adm summary{cursor:pointer}
`;
document.head.append(Object.assign(document.createElement("style"), { textContent: css }));
const openBtn = $("button", "adm-open", "데이터 추가"); document.body.append(openBtn);
let unlocked = false;

openBtn.onclick = () => {
  const back = $("div", "adm-back"), box = $("div", "adm"); back.append(box); document.body.append(back);
  const close = () => back.remove();
  back.addEventListener("click", e => { if (e.target === back) close(); });
  document.addEventListener("keydown", function esc(e) { if (e.key === "Escape") { close(); document.removeEventListener("keydown", esc); } });
  unlocked ? panel(box, close) : lock(box, close);
};

function lock(box, close) {
  box.textContent = "";
  const inp = $("input"); inp.type = "password"; inp.placeholder = "비밀번호"; inp.inputMode = "numeric";
  const msg = $("div", "msg"), go = $("button", "pri", "확인"), x = $("button", null, "닫기");
  const tryIt = () => { if (inp.value === PASS) { unlocked = true; panel(box, close); } else { msg.textContent = "비밀번호가 틀렸어요"; msg.className = "msg bad"; inp.select(); } };
  go.onclick = tryIt; inp.onkeydown = e => { if (e.key === "Enter") tryIt(); }; x.onclick = close;
  const row = $("div", "row"); row.append(go, x);
  box.append($("h2", null, "데이터 추가"), $("p", null, "비밀번호를 넣어 주세요."), inp, row, msg); inp.focus();
}

async function panel(box, close) {
  box.textContent = "";
  const ta = $("textarea"); ta.placeholder = "전적 상세(Chi tiết)를 펼쳐서 복사한 내용을 여기에 붙여 넣으세요. 여러 판을 한꺼번에 넣어도 되고, 이미 들어간 판은 알아서 빠져요.";
  const file = $("input"); file.type = "file"; file.accept = ".txt,.text"; file.multiple = true;
  const pv = $("button", "pri", "미리보기"), x = $("button", null, "닫기");
  const msg = $("div", "msg"), out = $("div");
  const row = $("div", "row"); row.append(pv, x);
  box.append($("h2", null, "데이터 추가"), $("p", null, "붙여 넣거나 .txt 파일을 고르면, 반영하기 전에 바뀐 순위를 먼저 보여줘요."), ta, $("div", "row"), row, msg, out);
  box.children[3].append(file);
  x.onclick = close;
  file.onchange = async () => { ta.value = (await Promise.all([...file.files].map(f => f.text()))).join("\n"); };

  let base;
  const say = (t, c = "") => { msg.textContent = t; msg.className = "msg " + c; };
  try {
    const get = p => fetch(p, { cache: "no-store" }).then(r => { if (!r.ok) throw new Error(p); return r.json(); });
    const [matches, members, ko, cur] = await Promise.all([get("data/matches.json"), get("data/members.json"), get("data/champions_ko.json").catch(() => ({})), get("data/leaderboard.json")]);
    base = { matches, members: members.members, ko, cur };
  } catch (e) { say("기존 데이터를 못 불러왔어요: " + e.message, "bad"); pv.disabled = true; return; }

  pv.onclick = () => {
    out.textContent = "";
    const parsed = parse(ta.value);
    if (!parsed.length) { say("판을 하나도 못 찾았어요. 'Đội Xanh / Thắng / 킬 수'로 시작하는 상세 내용인지 확인해 주세요.", "bad"); return; }
    const seen = new Set(base.matches.map(m => keyOf(m.teams)));
    const fresh = [];
    for (const teams of parsed) { const k = keyOf(teams); if (seen.has(k)) continue; seen.add(k); fresh.push({ id: "op-" + Math.abs([...k].reduce((h, c) => (h * 31 + c.charCodeAt(0)) | 0, 7)).toString(16), date: null, source: "paste", teams }); }
    if (!fresh.length) { say(`${parsed.length}판을 찾았는데 전부 이미 들어가 있어요.`, ""); return; }
    const matches = [...base.matches, ...fresh], next = leaderboard(matches, base.members, base.ko);
    say(`${parsed.length}판 중 새 판 ${fresh.length}개. 아래가 반영 후 순위예요.`, "good");
    renderPreview(out, base.cur, next);
    publish(out, matches, next, fresh.length);
  };
}

function renderPreview(out, cur, next) {
  const before = Object.fromEntries(cur.players.map(p => [p.name, p]));
  const t = $("table"), h = $("tr");
  ["순위", "닉네임", "점수", "변화", "판수", "티어"].forEach((x, i) => h.append($("th", i === 2 || i === 4 ? "num" : null, x)));
  t.append(h);
  next.players.forEach(p => {
    const b = before[p.name], tr = $("tr");
    const ch = $("td");
    if (!b) ch.append($("span", "up", "새로 등장"));
    else {
      const d = b.rank - p.rank, ds = r2(p.score - b.score, 2);
      ch.append($("span", d > 0 ? "up" : d < 0 ? "down" : null, d > 0 ? `▲${d}` : d < 0 ? `▼${-d}` : "–"), document.createTextNode(` (${ds >= 0 ? "+" : ""}${ds.toFixed(2)})`));
    }
    tr.append($("td", null, String(p.rank)), $("td", null, p.name), $("td", "num", p.score.toFixed(2)), ch, $("td", "num", b ? `${b.games}→${p.games}` : String(p.games)), $("td", null, b && b.tier !== p.tier ? `${b.tier}→${p.tier}` : p.tier));
    t.append(tr);
  });
  out.append(t);
}

function publish(out, matches, next, added) {
  const KEY = "aram-gh-token";
  let saved = ""; try { saved = localStorage.getItem(KEY) || ""; } catch {}
  const wrap = $("div"), tok = $("input"); tok.type = "password"; tok.placeholder = "깃헙 토큰 (처음 한 번만)"; tok.value = saved;
  const go = $("button", "pri", "사이트에 반영"), msg = $("div", "msg"), row = $("div", "row");
  row.append(go);
  const help = $("details"); help.append($("summary", null, "토큰은 어떻게 만들어요?"), $("p", null, "github.com → Settings → Developer settings → Fine-grained tokens → Generate new token. Repository access는 'Only select repositories'에서 aram-leaderboard만, Permissions는 Contents를 Read and write로 주면 돼요. 토큰은 이 브라우저에만 저장돼요."));
  wrap.append($("p", null, "괜찮으면 반영하세요. 1~2분 뒤 사이트에 보여요."), tok, row, help, msg);
  out.append(wrap);
  go.onclick = async () => {
    const token = tok.value.trim(); if (!token) { msg.textContent = "토큰을 넣어 주세요"; msg.className = "msg bad"; return; }
    go.disabled = true; msg.textContent = "올리는 중…"; msg.className = "msg";
    try {
      await commit("data/matches.json", JSON.stringify(matches, null, 1), `전적 ${added}판 추가`, token);
      await commit("data/leaderboard.json", JSON.stringify(next, null, 1), `순위 갱신 (${added}판 추가)`, token);
      try { localStorage.setItem(KEY, token); } catch {}
      msg.textContent = "반영했어요. 1~2분 뒤 새로고침하면 바뀐 순위가 보여요."; msg.className = "msg good";
    } catch (e) { msg.textContent = "실패: " + e.message + " (토큰 권한이나 만료를 확인해 주세요)"; msg.className = "msg bad"; go.disabled = false; }
  };
}
})();
