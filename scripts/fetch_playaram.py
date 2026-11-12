"""playaram.gg에서 멤버들의 전날 칼바람 판을 가져와 data/matches.json에 추가합니다.

동작 순서
1. data/members.json에서 riotId가 채워진 멤버의 프로필 페이지를 헤드리스 브라우저로 엽니다.
2. 페이지가 불러오는 JSON 응답을 모아 data/raw/<날짜>/<멤버>.json에 그대로 저장합니다.
3. parse_matches()로 판 목록을 공통 형식으로 바꾸고, 전날(한국 시간) 판만 골라 중복 없이 추가합니다.

TODO: parse_matches()는 playaram.gg의 실제 응답 구조를 확인한 뒤 채워야 합니다.
      그 전까지는 2번(원본 저장)만 하고 matches.json은 건드리지 않습니다.
"""
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
KST = timezone(timedelta(hours=9))
PROFILE_URL = "https://playaram.gg/profile/kr/{riot_id}"
WAIT_BETWEEN_PROFILES = 5  # 초. 사이트에 부담을 주지 않도록 천천히 요청합니다.


def profile_url(riot_id: str) -> str:
    return PROFILE_URL.format(riot_id=quote(riot_id, safe=""))


def capture_profile(page, riot_id: str) -> list:
    """프로필 페이지를 열고, 페이지가 받아오는 JSON 응답을 모두 모읍니다."""
    captured = []

    def on_response(resp):
        ctype = resp.headers.get("content-type", "")
        if "application/json" in ctype:
            try:
                captured.append({"url": resp.url, "body": resp.json()})
            except Exception:
                pass

    page.on("response", on_response)
    page.goto(profile_url(riot_id), wait_until="networkidle", timeout=60_000)
    page.wait_for_timeout(3000)
    html = page.content()
    page.remove_listener("response", on_response)
    return captured, html


def parse_matches(captured: list, html: str) -> list:
    """사이트 응답을 공통 형식의 판 목록으로 바꿉니다.

    반환 형식 (판 하나):
    {
      "id": "<사이트의 판 고유 ID>",
      "date": "2026-11-11T21:34:00+09:00",
      "source": "playaram",
      "teams": [
        {"win": true, "kills": 56, "players": [
          {"name": "Rstudio", "champion": "Seraphine", "kills": 4, "deaths": 8, "assists": 40,
           "damage": 16289, "taken": 17374, "gold": 12044}, ... 5명
        ]},
        {"win": false, "kills": 33, "players": [...5명]}
      ]
    }
    """
    # TODO: 실제 응답 구조 확인 후 구현
    return []


def main():
    members = json.loads((DATA / "members.json").read_text(encoding="utf-8"))["members"]
    targets = [m for m in members if m.get("riotId")]
    today = datetime.now(KST).date()
    yesterday = today - timedelta(days=1)
    raw_dir = DATA / "raw" / str(yesterday)
    raw_dir.mkdir(parents=True, exist_ok=True)

    matches_path = DATA / "matches.json"
    matches = json.loads(matches_path.read_text(encoding="utf-8"))
    known = {m["id"] for m in matches}
    added = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(locale="ko-KR")
        for i, m in enumerate(targets):
            if i:
                time.sleep(WAIT_BETWEEN_PROFILES)
            try:
                captured, html = capture_profile(page, m["riotId"])
            except Exception as e:
                print(f"[건너뜀] {m['name']}: {e}")
                continue
            safe = m["name"].replace("/", "_")
            (raw_dir / f"{safe}.json").write_text(
                json.dumps(captured, ensure_ascii=False, indent=1), encoding="utf-8")
            for match in parse_matches(captured, html):
                if match["id"] in known or not match.get("date"):
                    continue
                if datetime.fromisoformat(match["date"]).astimezone(KST).date() != yesterday:
                    continue
                matches.append(match)
                known.add(match["id"])
                added += 1
        browser.close()

    matches_path.write_text(json.dumps(matches, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{yesterday}: 새 판 {added}개 추가 (전체 {len(matches)}판)")


if __name__ == "__main__":
    main()
