# PoE1 스킬젬 밸런스 시각화: 설치 안내

## 설치

기존 GitHub Pages 저장소의 **루트**에 이 압축파일 속 `balance/` 폴더를 그대로 추가합니다.
**기존 `index.html`, `data/manifest.json`, XML, Secondary, GitHub Actions는 수정하거나 삭제하지 마세요.**

```text
<저장소 루트>/
├── index.html                      [기존, 변경 없음]
├── data/                           [기존, 변경 없음]
│   ├── manifest.json
│   ├── secondary_effects.json
│   └── gems_001.xml ...
└── balance/                        [신규 폴더]
    ├── index.html                  신규 밸런스 페이지
    ├── style.css                   별도 모바일 디자인
    ├── app.js                      검색/필터/정렬/상세 모달
    ├── README.md                   데이터 갱신 안내
    ├── data/
    │   ├── 3.29.json               선별된 3.29 시험 데이터
    │   └── 3.30.template.json      3.30용 빈 템플릿
    ├── icons/
    │   └── README.txt              실제 아이콘 설치 안내
    └── scripts/
        ├── parse_patchnotes.py      공식 HTML → JSON 파서
        ├── aliases.json            영어 젬 이름 → effectId 매핑
        └── requirements.txt        Python 패키지
```

페이지 주소:
- 기존 뷰어: `https://<사용자>.github.io/<저장소>/`
- 새 밸런스 화면: `https://<사용자>.github.io/<저장소>/balance/`

로컬에서 동작 확인: 저장소 루트에서 `python -m http.server 8000` 실행한 뒤
`http://localhost:8000/balance/`를 엽니다. (파일을 직접 더블클릭하면 `fetch`가 차단될 수 있습니다.)

## 구현된 기능

- 다크 테마, 반응형 카드형 목록, 화면 가로 넘침 없는 모바일 UI
- 젬 색상 및 보조젬 구분을 위한 CSS 아이콘 (실제 이미지 파일은 아직 미수록)
- 전체/상향/하향/복합/조정/신규 상태 필터
- 스킬/보조/변형/바알 필터, 한글·영어 이름 검색
- 주요 변화폭/피해량/피해 효율/보조 피해 배율/속도/쿨다운/비용/치명타/반경/지속시간/투사체 수/변경 개수 정렬
- 상향순·하향순 전환, 정렬 기준 변경 시 카드의 대표 숫자도 연동
- 목록 누르면 **페이지 이동 없이** 데스크톱 중앙 모달, 모바일 하단 시트 표시
- 변경 전→후 숫자·상대 변화율·색상·비교 막대, 효과 추가·제거 표시
- 검색/필터 상태는 sessionStorage에 저장
- `?patch=3.29`로 시험 자료를 강제 표시할 수 있음

## 현재 3.29 데이터의 범위 — 중요

`balance/data/3.29.json`에는 **48개 젬의 선별된 수치 변경 및 신규 항목**이 들어 있습니다.
이 데이터는 디자인과 동작을 확인하기 위한 **미리보기**로, 3.29 전체 젬 변경을 포함하지 않습니다.
변경 내용은 공식 3.29 New and Changed Gems 페이지 및 공식 3.29 패치 내용을 참고했습니다.
공식 원문 HTML 전체는 압축파일에 보관하지 않았습니다.

- 스킬·보조 스탯: 선별된 변경 전/후 숫자로 구성
- 신규 젬: 맹약/보조/변형 등 12개
- 수치로 판정하기 어려운 일부 변화는 중립 처리
- 종합 상향/하향 분류는 **정해진 규칙에 따른 보수적인 임시 판정**입니다. 실제 빌드 효율과 동일하지 않습니다.

## 공식 HTML 원문에서 전체 변경 데이터 재생성

`balance/scripts/parse_patchnotes.py`는 파서입니다. 사용자 PC 또는 인터넷이 허용된 CI에서 실행합니다.
브라우저 GitHub Pages 환경에서 Python이 실행되는 것은 아닙니다.

```bash
pip install -r balance/scripts/requirements.txt
python balance/scripts/parse_patchnotes.py \
  --url https://www.pathofexile.com/forum/view-thread/3987254 \
  --patch 3.29 --previous 3.28 \
  --manifest data/manifest.json \
  --output balance/data/3.29.json
```

또는 HTML 파일을 직접 저장한 경우:

```bash
python balance/scripts/parse_patchnotes.py \
  --html downloads/3.29.html \
  --patch 3.29 --previous 3.28 \
  --manifest data/manifest.json \
  --output balance/data/3.29.json
```

실행하면 같은 `data/` 폴더에 `3.29.review.json`이 추가로 만들어집니다.
**반드시 확인할 항목**: 미매칭 영문명, 미인식 스탯, 잘못된 New/Old 쌍, 신규 젬, 변경 누락.
공식 사이트 구조가 바뀌면 파서를 조정해야 할 수 있습니다. 특히 신규 젬 카드/이미지의 원문 텍스트는 별도 검증이 필요합니다.

실제 데이터가 공개되기 전에 자동 추출 결과를 검토 없이 `verified`로 표시하지 마세요.

## 3.30으로 전환

공식 젬 변경 HTML을 받았을 때:

```bash
python balance/scripts/parse_patchnotes.py \
  --html downloads/3.30.html \
  --patch 3.30 --previous 3.29 \
  --manifest data/manifest.json \
  --output balance/data/3.30.json
```

`3.30.review.json`을 검토한 뒤 **`balance/data/3.30.json`을 업로드하면**, 앱이 기본적으로 3.30을 자동 표시합니다.
3.29 시험 데이터는 `?patch=3.29`로 계속 볼 수 있습니다.
새 젬은 현재 `manifest.json`에 없을 수 있으므로, 그런 항목은 `unmatched`로 남습니다.
수동 매칭은 `aliases.json`에 추가하거나 JSON의 ID/한글 이름을 직접 검증하세요.

> 3.30이 동일한 'New and Changed Gems' HTML 구조로 제공된다는 보장은 없습니다.
> 일반 패치노트 형식만 나오는 경우 파서의 수집 단계를 추가 개발해야 합니다.

## 아이콘

실제 GGG 아이콘 이미지 자체는 이 파일에 포함하지 않았습니다. 현재 CSS로 보석 모양을 표시합니다.
아이콘의 출처/사용 조건을 확인해 정적 파일을 넣고 각 젬에
`"icon":"icons/Fireball.webp"` 식으로 지정하면 자동으로 이미지가 대신 표시됩니다.

## 계산과 판정 원칙

- `deltaPct`: **숫자 자체의** 변화율. 예: 마나 비용 20→25 = +25%.
- `impactPct`: 효과 방향을 반영한 **비교 정렬용** 상대값. 양수는 개선, 음수는 악화.
- 시전 시간/쿨다운: 사용 빈도 기준으로 효과 변화율 계산. 화면에는 시전 속도 환산 여부 명시.
- `less Damage`: 40% less→50% less를 +25% 상향으로 오판하지 않고 실효 배율 0.60→0.50, 즉 -16.7%로 처리.
- 범위 피해: 최소/최대의 평균을 기반으로 상대 변화율 계산.
- 조건부 수치·효과 추가/제거는 확인되지 않은 경우 변화율 및 버프/너프를 강제하지 않음.
- 여러 서로 다른 변화율을 **한 개의 젬 성능 점수로 합산하지 않음**.

공식 3.29 젬 자료: https://www.pathofexile.com/forum/view-thread/3987254
