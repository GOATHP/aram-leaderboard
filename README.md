# 칼바람 리더보드

매일 오전 9시(KST)에 playaram.gg에서 멤버들의 전날 칼바람 판을 가져와 점수와 순위를 다시 계산하는 GitHub Pages 사이트.

## 구조
- `index.html` — 페이지. `data/leaderboard.json`을 읽어서 그림
- `data/members.json` — 멤버 목록. **riotId(닉네임#태그) 채워야 함**
- `data/matches.json` — 누적 판 데이터 (현재 78판)
- `scripts/fetch_playaram.py` — playaram.gg 수집 (파서 `parse_matches()` 미완성)
- `scripts/score.py` — 점수·티어·순위 계산 → `data/leaderboard.json`
- `.github/workflows/daily.yml` — 매일 00:00 UTC(= 09:00 KST) 실행

## 설정
1. GitHub에 새 저장소 만들고 이 폴더 전체 push
2. Settings → Pages → Source: `Deploy from a branch`, Branch `main` / `(root)`
3. Settings → Actions → General → Workflow permissions: **Read and write**
4. Actions 탭 → daily → `Run workflow`로 한 번 수동 실행해 확인

## 로컬 실행
```
python scripts/score.py
python -m http.server
```

## 사이트에서 데이터 추가 (관리자)
오른쪽 아래 **데이터 추가** → 비밀번호 → 전적 상세 붙여넣기 → **미리보기**로 바뀐 순위 확인 → **사이트에 반영**.
반영에는 이 저장소의 Contents 쓰기 권한만 준 fine-grained 토큰이 필요하고, 토큰은 그 브라우저에만 저장됨.
비밀번호는 화면 잠금용이라 보안 장치가 아님 (실제 권한은 토큰).
