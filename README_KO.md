# GitHub Pages 업로드 구조

아래 구조 그대로 저장소 루트에 업로드하세요.

```
/
├─ index.html
└─ data/
   ├─ manifest.json
   ├─ gems_001.xml\n   ├─ gems_002.xml\n   ├─ gems_003.xml\n   ├─ gems_004.xml\n   ├─ gems_005.xml\n   ├─ gems_006.xml\n   ├─ gems_007.xml\n   ├─ gems_008.xml\n   ├─ gems_009.xml\n   └─ gems_010.xml
```

- 원본 XML: 77.89 MiB
- 분할 파일 수: 10
- 최대 분할 파일: 8.00 MiB
- 전체 젬 수: 1014

`index.html`은 먼저 `data/manifest.json`만 읽습니다.
젬을 선택할 때 해당 젬이 들어 있는 XML 조각만 다운로드합니다.
