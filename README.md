# 클래스카드 자동화 QA 도구

ClassCard 현재 UI를 기준으로 학습 과정을 자동화해 검증하기 위한 내부 QA용 스크립트입니다.

지원 기능:

- 세트 페이지에서 단어/뜻 목록 수집
- 암기학습 자동 진행
- 리콜학습 자동 선택
- 스펠학습 자동 입력
- 매칭 게임 자동 매칭
- 테스트 자동 입력/선택
- 학습 기록 API 요청
- CSV 내보내기와 로컬 퀴즈

## 설치

```bash
pip install -r requirements.txt
```

Chrome이 설치되어 있어야 합니다. Selenium 4의 Selenium Manager가 ChromeDriver를 자동으로 맞춥니다.

## 기본 사용법

원본처럼 메뉴로 실행:

```bash
python main.py
```

공개 세트의 단어를 CSV로 저장:

```bash
python main.py --mode export --set-url "https://www.classcard.net/set/2832708"
```

로컬 퀴즈:

```bash
python main.py --mode quiz --set-url "https://www.classcard.net/set/2832708" --shuffle
```

## 로그인 후 전체 자동화

계정 정보를 환경변수로 넣는 방식:

```powershell
$env:CLASSCARD_ID="아이디"
$env:CLASSCARD_PW="비밀번호"
python main.py --mode recall --set-url "https://www.classcard.net/set/세트ID/클래스ID" --login
```

브라우저에서 직접 로그인하는 방식:

```bash
python main.py --mode recall --set-url "https://www.classcard.net/set/세트ID/클래스ID" --manual-login
```

모드만 바꾸면 같은 방식으로 실행됩니다.

```bash
python main.py --mode memory   --set-url "https://www.classcard.net/set/세트ID/클래스ID" --manual-login
python main.py --mode recall   --set-url "https://www.classcard.net/set/세트ID/클래스ID" --manual-login
python main.py --mode spelling --set-url "https://www.classcard.net/set/세트ID/클래스ID" --manual-login
python main.py --mode matching --set-url "https://www.classcard.net/set/세트ID/클래스ID" --manual-login
python main.py --mode test     --set-url "https://www.classcard.net/set/세트ID/클래스ID" --manual-login
```

## API 기록 요청

브라우저 로그인 쿠키를 사용해 기존 ClassCard 기록 API에 요청합니다.

```bash
python main.py --mode api --activity recall --set-url "https://www.classcard.net/set/세트ID/클래스ID" --manual-login
```

URL에서 값이 자동으로 잡히지 않으면 직접 넣을 수 있습니다.

```bash
python main.py --mode api --activity spelling --set-id 123456 --class-id 7890 --api-user-id 1111 --view-cnt 50 --manual-login
```

`--activity` 값:

- `memory`
- `recall`
- `spelling`
- `test`

## 옵션

- `--max-steps 300`: 자동화 반복 횟수 제한
- `--delay 1.0`: 클릭/입력 사이 대기 시간
- `--guess-unknown`: 매칭 실패 시 임의 선택 허용
- `--headless`: Chrome 창 숨김
- `--profile-dir`: 기존 Chrome 프로필 폴더 사용
- `--html`: 저장된 세트 HTML 파일에서 카드 읽기

## 동작 방식

예전 버전처럼 고정 XPath에만 의존하지 않고, 현재 화면의 버튼 텍스트와 세트의 단어/뜻 목록을 비교해서 답을 고릅니다. ClassCard UI가 바뀌면 먼저 버튼 문구와 카드 텍스트 구조가 달라지는 지점을 확인하면 됩니다.

비밀번호는 `config.json`에 저장하지 않습니다. 환경변수, 직접 입력, 또는 수동 로그인만 사용합니다.
