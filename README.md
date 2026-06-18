# 클래스카드 자동화 QA 도구

ClassCard 현재 UI를 기준으로 원본 매크로 구조를 유지하며 학습 과정을 자동화하는 내부 QA용 스크립트입니다.

지원 기능:

- 세트 페이지에서 단어/뜻 목록 수집
- 암기학습 자동 진행
- 리콜학습 자동 선택
- 스펠학습 자동 입력
- 매칭 게임 자동 매칭
- 테스트 자동 입력/선택
- 학습 기록 API 요청
- CSV 내보내기

## 설치

```bash
pip install -r requirements.txt
```

Chrome이 설치되어 있어야 합니다. Selenium 4의 Selenium Manager가 ChromeDriver를 자동으로 맞춥니다.

## VS Code에서 실행

이미 가상환경을 켠 상태라면 바로 실행합니다.

```bash
python main.py --manual-login
```

메뉴가 나오면 원하는 번호를 누릅니다.

- `1`: 암기학습 자동화
- `2`: 리콜학습 자동화
- `3`: 스펠학습 자동화
- `4`: 테스트학습 자동화
- `5`-`8`: 학습 기록 API 요청
- `9`: 매칭 게임 자동화
- `10`: CSV 내보내기

Chrome이 열리면 로그인하고, 목표 세트 페이지까지 이동한 뒤 터미널에서 Enter를 누르면 됩니다.

## 바로 모드 지정

세트 URL을 알고 있으면 메뉴 없이 바로 실행할 수 있습니다.

```bash
python main.py --mode recall --set-url "https://www.classcard.net/set/세트ID/클래스ID" --manual-login
```

모드 이름:

- `memory`
- `recall`
- `spelling`
- `matching`
- `test`
- `export`
- `api-memory`
- `api-recall`
- `api-spelling`
- `api-test`

## 원본과의 차이

원본처럼 `main.py`가 로그인/세트/메뉴를 처리하고, `handler` 폴더의 각 학습 파일이 실제 자동화를 담당합니다. 바뀐 ClassCard UI에 맞추기 위해 고정 XPath가 실패하면 버튼 텍스트, 입력칸, 선택지 텍스트를 같이 탐색합니다.
