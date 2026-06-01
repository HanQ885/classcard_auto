from __future__ import annotations

import argparse
import csv
import getpass
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


CLASSCARD_LOGIN_URL = "https://www.classcard.net/Login"
CLASSCARD_API_URL = "https://www.classcard.net/ViewSetAsync/resetAllLog"

DONE_MARKERS = ("완료", "결과", "학습 종료", "학습이 종료", "수고")
START_LABELS = ("시작", "학습 시작", "START")
MEMORY_LABELS = ("암기학습", "암기 학습", "Memory")
RECALL_LABELS = ("리콜학습", "리콜 학습", "Recall")
SPELLING_LABELS = ("스펠학습", "스펠 학습", "Spelling")
MATCHING_LABELS = ("매칭 게임", "매칭게임", "Matching")
TEST_LABELS = ("테스트", "테스트학습", "Test")
SUBMIT_LABELS = ("확인", "다음", "제출", "정답", "check", "next")
MEMORY_ADVANCE_LABELS = (
    "알고 있어요",
    "외웠어요",
    "알아요",
    "다음",
    "넘기기",
    "pass",
    "next",
)
REVEAL_LABELS = ("뒤집기", "뜻 보기", "정답 보기", "보기")
TEXT_END_MARKERS = (
    "클래스카드의 다양한 학습",
    "선생님 수업도구",
    "학생 학습도구",
    "고객센터",
    "세트 합치기",
)

NOISE_LINES = {
    "Game",
    "취소",
    "오늘 기록만 보기",
    "Class Name",
    "모든 도전기록",
    "세트공유",
    "클래스로 이동",
    "로그인",
    "무료 회원가입",
    "암기학습",
    "리콜학습",
    "스펠학습",
    "카드 이미지",
}


@dataclass(frozen=True)
class Card:
    front: str
    back: str


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def norm(value: str) -> str:
    return clean_text(value).casefold()


def visible_lines(text: str) -> list[str]:
    lines = []
    for raw_line in (text or "").splitlines():
        line = clean_text(raw_line)
        if line:
            lines.append(line)
    return lines


def is_noise_line(line: str) -> bool:
    if line in NOISE_LINES:
        return True
    if line.startswith("http://") or line.startswith("https://"):
        return True
    if re.fullmatch(r"\d+\s*카드\s*\|.*", line):
        return True
    if "로그인이 필요" in line:
        return True
    return False


def dedupe_cards(cards: list[Card]) -> list[Card]:
    deduped: list[Card] = []
    seen: set[tuple[str, str]] = set()
    for card in cards:
        front = clean_text(card.front)
        back = clean_text(card.back)
        if not front or not back or front == back:
            continue
        key = (norm(front), norm(back))
        if key not in seen:
            deduped.append(Card(front, back))
            seen.add(key)
    return deduped


def parse_cards_from_html(html: str) -> list[Card]:
    soup = BeautifulSoup(html, "html.parser")
    cards = parse_cards_from_nodes(soup)
    if cards:
        return cards
    return parse_cards_from_text(soup.get_text("\n"))


def parse_cards_from_nodes(soup: BeautifulSoup) -> list[Card]:
    cards: list[Card] = []
    selectors = (
        "#tab_set_all .flip-card",
        ".flip-card",
        ".flip-body .card",
        ".card-list .card",
        "[class*='flip-card']",
        "[class*='word-card']",
        "[data-idx][class*='card']",
    )
    for selector in selectors:
        for node in soup.select(selector):
            lines = [line for line in visible_lines(node.get_text("\n")) if not is_noise_line(line)]
            if len(lines) >= 2:
                cards.append(Card(lines[0], lines[1]))
        cards = dedupe_cards(cards)
        if cards:
            return cards
    return []


def parse_cards_from_text(text: str) -> list[Card]:
    lines = [line for line in visible_lines(text) if not is_noise_line(line)]
    if not lines:
        return []

    start = 0
    for index, line in enumerate(lines):
        if re.search(r"\d+\s*카드", line):
            start = index + 1
            break

    end = len(lines)
    for index in range(start, len(lines)):
        if any(marker in lines[index] for marker in TEXT_END_MARKERS):
            end = index
            break

    candidates = [
        line
        for line in lines[start:end]
        if not is_noise_line(line) and not re.fullmatch(r"Image|arrow_upward", line)
    ]
    cards = []
    for index in range(0, len(candidates) - 1, 2):
        cards.append(Card(candidates[index], candidates[index + 1]))
    return dedupe_cards(cards)


def fetch_html(url: str) -> str:
    response = requests.get(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
            )
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.text


def load_cards(args: argparse.Namespace, driver: webdriver.Chrome | None = None) -> list[Card]:
    if args.html:
        html = Path(args.html).read_text(encoding="utf-8")
    elif driver is not None:
        html = driver.page_source
    elif args.set_url:
        html = fetch_html(args.set_url)
    else:
        raise ValueError("--set-url 또는 --html 이 필요합니다.")

    cards = parse_cards_from_html(html)
    if driver is not None and not cards:
        cards = parse_cards_from_text(driver.find_element(By.TAG_NAME, "body").text)
    return cards


def export_csv(cards: list[Card], output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["front", "back"])
        for card in cards:
            writer.writerow([card.front, card.back])


def run_quiz(cards: list[Card], reverse: bool, shuffle: bool, limit: int | None) -> None:
    queue = cards[:]
    if shuffle:
        random.shuffle(queue)
    if limit:
        queue = queue[:limit]

    correct = 0
    for index, card in enumerate(queue, start=1):
        prompt = card.back if reverse else card.front
        answer = card.front if reverse else card.back
        print(f"\n[{index}/{len(queue)}] {prompt}")
        typed = input("답: ").strip()
        if norm(typed) == norm(answer):
            print("정답")
            correct += 1
        else:
            print(f"오답 / 정답: {answer}")
    print(f"\n결과: {correct}/{len(queue)}")


def build_driver(args: argparse.Namespace) -> webdriver.Chrome:
    options = Options()
    if args.headless:
        options.add_argument("--headless=new")
    if args.profile_dir:
        options.add_argument(f"--user-data-dir={args.profile_dir}")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--log-level=1")
    return webdriver.Chrome(options=options)


def wait_for_body(driver: webdriver.Chrome, timeout: int = 20) -> None:
    WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.TAG_NAME, "body")))


def login(driver: webdriver.Chrome, args: argparse.Namespace) -> None:
    driver.get(CLASSCARD_LOGIN_URL)
    wait_for_body(driver)

    if args.manual_login:
        input("Chrome에서 로그인한 뒤 Enter를 누르세요...")
        return

    user_id = args.user_id or os.environ.get("CLASSCARD_ID") or input("ClassCard ID: ").strip()
    password = args.password or os.environ.get("CLASSCARD_PW") or getpass.getpass("ClassCard PW: ")

    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "login_id")))
    id_element = driver.find_element(By.ID, "login_id")
    pw_element = driver.find_element(By.ID, "login_pwd")
    id_element.clear()
    id_element.send_keys(user_id)
    pw_element.clear()
    pw_element.send_keys(password)

    if not click_by_text(driver, ("로그인",), max_text_length=30):
        pw_element.send_keys(Keys.ENTER)
    time.sleep(args.delay)


def open_target_set(driver: webdriver.Chrome, args: argparse.Namespace) -> None:
    if args.set_url:
        driver.get(args.set_url)
        wait_for_body(driver)
        time.sleep(args.delay)
        return
    input("Chrome에서 목표 ClassCard 세트 페이지로 이동한 뒤 Enter를 누르세요...")
    wait_for_body(driver)


def element_text(element: WebElement) -> str:
    try:
        return clean_text(element.text or element.get_attribute("value") or "")
    except Exception:
        return ""


def is_clickable_candidate(element: WebElement, max_text_length: int = 80) -> bool:
    try:
        text = element_text(element)
        return element.is_displayed() and 0 < len(text) <= max_text_length
    except Exception:
        return False


def click_by_text(
    driver: webdriver.Chrome,
    labels: tuple[str, ...],
    max_text_length: int = 80,
) -> bool:
    label_norms = tuple(norm(label) for label in labels)
    elements = driver.find_elements(By.CSS_SELECTOR, "a,button,[role='button'],input,div,span")
    for element in elements:
        if not is_clickable_candidate(element, max_text_length=max_text_length):
            continue
        text = norm(element_text(element))
        if any(label in text for label in label_norms):
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                element.click()
                time.sleep(0.4)
                return True
            except Exception:
                continue
    return False


def card_answer_maps(cards: list[Card]) -> tuple[dict[str, str], dict[str, str]]:
    front_to_back = {norm(card.front): card.back for card in cards}
    back_to_front = {norm(card.back): card.front for card in cards}
    return front_to_back, back_to_front


def find_answer_from_page_text(body_text: str, cards: list[Card]) -> str | None:
    body = norm(body_text)
    for card in cards:
        front = norm(card.front)
        back = norm(card.back)
        if back and back in body:
            return card.front
        if front and front in body:
            return card.back
    return None


def click_matching_choice(driver: webdriver.Chrome, cards: list[Card], guess_unknown: bool) -> bool:
    body_text = driver.find_element(By.TAG_NAME, "body").text
    body = norm(body_text)
    front_to_back, back_to_front = card_answer_maps(cards)
    candidates = driver.find_elements(By.CSS_SELECTOR, "button,a,[role='button'],div,span")
    fallback: list[WebElement] = []

    for element in candidates:
        if not is_clickable_candidate(element):
            continue
        text = element_text(element)
        text_norm = norm(text)
        if text_norm in front_to_back and norm(front_to_back[text_norm]) in body:
            click_element(driver, element)
            print(f"선택: {text}")
            return True
        if text_norm in back_to_front and norm(back_to_front[text_norm]) in body:
            click_element(driver, element)
            print(f"선택: {text}")
            return True
        if text_norm in front_to_back or text_norm in back_to_front:
            fallback.append(element)

    if guess_unknown and fallback:
        element = random.choice(fallback)
        print(f"임의 선택: {element_text(element)}")
        click_element(driver, element)
        return True
    return False


def click_element(driver: webdriver.Chrome, element: WebElement) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    try:
        element.click()
    except Exception:
        driver.execute_script("arguments[0].click();", element)
    time.sleep(0.5)


def click_exact_text(driver: webdriver.Chrome, target: str) -> bool:
    target_norm = norm(target)
    if not target_norm:
        return False
    elements = driver.find_elements(By.CSS_SELECTOR, "button,a,[role='button'],div,span")
    for element in elements:
        if not is_clickable_candidate(element, max_text_length=max(80, len(target) + 20)):
            continue
        if norm(element_text(element)) == target_norm:
            click_element(driver, element)
            return True
    return False


def enter_answer(driver: webdriver.Chrome, cards: list[Card]) -> bool:
    body_text = driver.find_element(By.TAG_NAME, "body").text
    answer = find_answer_from_page_text(body_text, cards)
    if not answer:
        return False

    inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], textarea")
    for input_element in inputs:
        try:
            if not input_element.is_displayed() or not input_element.is_enabled():
                continue
            input_element.click()
            input_element.clear()
            input_element.send_keys(answer)
            print(f"입력: {answer}")
            if not click_by_text(driver, SUBMIT_LABELS, max_text_length=40):
                input_element.send_keys(Keys.ENTER)
            time.sleep(0.5)
            return True
        except Exception:
            continue
    return False


def prepare_learning(driver: webdriver.Chrome, labels: tuple[str, ...], args: argparse.Namespace) -> None:
    if not click_by_text(driver, labels, max_text_length=40):
        print("학습 버튼을 자동으로 찾지 못했습니다. Chrome에서 해당 학습으로 들어간 뒤 Enter를 누르세요.")
        input()
    time.sleep(args.delay)
    click_by_text(driver, START_LABELS, max_text_length=60)
    time.sleep(args.delay)


def is_done(driver: webdriver.Chrome) -> bool:
    text = driver.find_element(By.TAG_NAME, "body").text
    return any(marker in text for marker in DONE_MARKERS)


def run_recall(driver: webdriver.Chrome, cards: list[Card], args: argparse.Namespace) -> None:
    prepare_learning(driver, RECALL_LABELS, args)
    idle_rounds = 0
    for step in range(1, args.max_steps + 1):
        if is_done(driver) and step > 1:
            print("완료 화면을 감지했습니다.")
            return
        if click_matching_choice(driver, cards, args.guess_unknown):
            idle_rounds = 0
        else:
            idle_rounds += 1
            print("현재 화면에서 일치하는 선택지를 찾지 못했습니다.")
            if idle_rounds >= 3:
                return
        time.sleep(args.delay)


def run_memory(driver: webdriver.Chrome, cards: list[Card], args: argparse.Namespace) -> None:
    prepare_learning(driver, MEMORY_LABELS, args)
    idle_rounds = 0
    for step in range(1, args.max_steps + 1):
        if is_done(driver) and step > 1:
            print("완료 화면을 감지했습니다.")
            return
        if click_by_text(driver, REVEAL_LABELS, max_text_length=40):
            idle_rounds = 0
        elif click_by_text(driver, MEMORY_ADVANCE_LABELS, max_text_length=60):
            idle_rounds = 0
        else:
            try:
                body = driver.find_element(By.TAG_NAME, "body")
                body.send_keys(Keys.ARROW_RIGHT)
                idle_rounds = 0
            except Exception:
                idle_rounds += 1
                print("암기학습 진행 버튼을 찾지 못했습니다.")
                if idle_rounds >= 3:
                    return
        time.sleep(args.delay)


def run_spelling(driver: webdriver.Chrome, cards: list[Card], args: argparse.Namespace) -> None:
    prepare_learning(driver, SPELLING_LABELS, args)
    idle_rounds = 0
    for step in range(1, args.max_steps + 1):
        if is_done(driver) and step > 1:
            print("완료 화면을 감지했습니다.")
            return
        if enter_answer(driver, cards):
            idle_rounds = 0
        else:
            idle_rounds += 1
            print("현재 화면에서 입력할 답을 찾지 못했습니다.")
            if idle_rounds >= 3:
                return
        time.sleep(args.delay)


def run_matching(driver: webdriver.Chrome, cards: list[Card], args: argparse.Namespace) -> None:
    prepare_learning(driver, MATCHING_LABELS, args)
    matched = 0
    idle_rounds = 0
    for step in range(1, args.max_steps + 1):
        if is_done(driver) and step > 1:
            print("완료 화면을 감지했습니다.")
            return

        progress = False
        for card in cards:
            if click_exact_text(driver, card.front):
                time.sleep(0.2)
                if click_exact_text(driver, card.back):
                    matched += 1
                    progress = True
                    print(f"매칭: {card.front} / {card.back}")
                    time.sleep(args.delay)
                    break
        if progress:
            idle_rounds = 0
            continue

        if click_matching_choice(driver, cards, args.guess_unknown):
            idle_rounds = 0
            continue

        idle_rounds += 1
        print("현재 화면에서 매칭 가능한 카드를 찾지 못했습니다.")
        if idle_rounds >= 3:
            print(f"매칭 시도 종료: {matched}쌍")
            return
        time.sleep(args.delay)


def run_test(driver: webdriver.Chrome, cards: list[Card], args: argparse.Namespace) -> None:
    prepare_learning(driver, TEST_LABELS, args)
    idle_rounds = 0
    for step in range(1, args.max_steps + 1):
        if is_done(driver) and step > 1:
            print("완료 화면을 감지했습니다.")
            return
        if enter_answer(driver, cards):
            idle_rounds = 0
        elif click_matching_choice(driver, cards, args.guess_unknown):
            idle_rounds = 0
        elif click_by_text(driver, SUBMIT_LABELS, max_text_length=40):
            idle_rounds = 0
        else:
            idle_rounds += 1
            print("현재 테스트 문항에서 답을 찾지 못했습니다.")
            if idle_rounds >= 3:
                return
        time.sleep(args.delay)


def parse_set_id(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"/set/(\d+)", urlparse(url).path)
    return match.group(1) if match else None


def parse_class_id(url: str | None) -> str | None:
    if not url:
        return None
    parts = [part for part in urlparse(url).path.split("/") if part]
    if len(parts) >= 3 and parts[0].lower() == "set":
        return parts[2]
    return None


def get_js_value(driver: webdriver.Chrome, expression: str) -> str | None:
    try:
        value = driver.execute_script(f"return {expression};")
        return str(value) if value is not None else None
    except Exception:
        return None


def post_learning_api(driver: webdriver.Chrome, cards: list[Card], args: argparse.Namespace) -> None:
    current_url = args.set_url or driver.current_url
    set_id = args.set_id or parse_set_id(current_url)
    class_id = args.class_id or parse_class_id(current_url) or get_js_value(
        driver, "window.class_idx || window.c_class || null"
    )
    user_id = args.api_user_id or get_js_value(
        driver, "window.c_u || (typeof c_u !== 'undefined' ? c_u : null)"
    )
    view_cnt = args.view_cnt or len(cards)
    activity = {"memory": 1, "recall": 2, "spelling": 3, "test": 4}[args.activity]

    missing = [
        name
        for name, value in (("set_id", set_id), ("class_id", class_id), ("user_id", user_id))
        if not value
    ]
    if missing:
        raise RuntimeError(f"API 요청에 필요한 값이 없습니다: {', '.join(missing)}")

    session = requests.Session()
    for cookie in driver.get_cookies():
        session.cookies.set(cookie["name"], cookie["value"], domain=cookie.get("domain"))

    response = session.post(
        CLASSCARD_API_URL,
        data={
            "set_idx": set_id,
            "activity": activity,
            "user_idx": user_id,
            "view_cnt": view_cnt,
            "class_idx": class_id,
        },
        headers={"content-type": "application/x-www-form-urlencoded; charset=UTF-8"},
        timeout=20,
    )
    print(f"API status: {response.status_code}")
    print(response.text[:500])


def print_cards_summary(cards: list[Card]) -> None:
    print(f"카드 {len(cards)}개를 읽었습니다.")
    for card in cards[:5]:
        print(f"- {card.front} / {card.back}")
    if len(cards) > 5:
        print(f"... 외 {len(cards) - 5}개")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ClassCard QA automation")
    parser.add_argument(
        "--mode",
        choices=("quiz", "export", "memory", "recall", "spelling", "matching", "test", "api"),
        default=None,
    )
    parser.add_argument("--set-url", help="ClassCard 세트 URL")
    parser.add_argument("--html", help="저장한 ClassCard HTML 파일")
    parser.add_argument("--export", default="classcard_cards.csv", help="CSV 저장 경로")
    parser.add_argument("--reverse", action="store_true", help="뜻을 보고 단어를 맞힙니다.")
    parser.add_argument("--shuffle", action="store_true", help="카드 순서를 섞습니다.")
    parser.add_argument("--limit", type=int, help="퀴즈 카드 수 제한")
    parser.add_argument("--login", action="store_true", help="스크립트가 로그인합니다.")
    parser.add_argument("--manual-login", action="store_true", help="Chrome에서 직접 로그인합니다.")
    parser.add_argument("--user-id", help="ClassCard 로그인 ID. CLASSCARD_ID 환경변수도 지원합니다.")
    parser.add_argument("--password", help="ClassCard 로그인 비밀번호. CLASSCARD_PW 환경변수도 지원합니다.")
    parser.add_argument("--headless", action="store_true", help="Chrome 창을 숨깁니다.")
    parser.add_argument("--profile-dir", help="Chrome 사용자 데이터 폴더")
    parser.add_argument("--delay", type=float, default=1.0, help="화면 전환 대기 시간")
    parser.add_argument("--max-steps", type=int, default=300, help="자동화 최대 반복 횟수")
    parser.add_argument("--guess-unknown", action="store_true", help="매칭 실패 시 임의 선택")
    parser.add_argument("--activity", choices=("memory", "recall", "spelling", "test"), default="recall")
    parser.add_argument("--set-id", help="API용 세트 ID")
    parser.add_argument("--class-id", help="API용 클래스 ID")
    parser.add_argument("--api-user-id", help="API용 사용자 ID")
    parser.add_argument("--view-cnt", type=int, help="API용 카드 수")
    return parser.parse_args()


def apply_interactive_defaults(args: argparse.Namespace) -> argparse.Namespace:
    if args.mode:
        return args

    print("학습유형을 선택해주세요.")
    print("Ctrl + C 를 눌러 종료")
    print("[1] 암기학습(매크로)")
    print("[2] 리콜학습(매크로)")
    print("[3] 스펠학습(매크로)")
    print("[4] 테스트학습(매크로)")
    print("[5] 암기학습(API 요청)")
    print("[6] 리콜학습(API 요청)")
    print("[7] 스펠학습(API 요청)")
    print("[8] 테스트학습(API 요청)")
    print("[9] 매칭 게임(매크로)")
    print("[10] CSV 내보내기")
    print("[11] 로컬 퀴즈")

    menu = {
        1: ("memory", None),
        2: ("recall", None),
        3: ("spelling", None),
        4: ("test", None),
        5: ("api", "memory"),
        6: ("api", "recall"),
        7: ("api", "spelling"),
        8: ("api", "test"),
        9: ("matching", None),
        10: ("export", None),
        11: ("quiz", None),
    }

    while True:
        try:
            selected = int(input(">>> ").strip())
            if selected in menu:
                break
            raise ValueError
        except ValueError:
            print("학습유형을 다시 입력해주세요.")

    args.mode, activity = menu[selected]
    if activity:
        args.activity = activity

    if not args.set_url and not args.html:
        set_url = input("세트 URL을 입력하세요. 직접 이동하려면 비워두고 Enter: ").strip()
        if set_url:
            args.set_url = set_url

    if args.mode not in {"quiz", "export"} and not args.login and not args.manual_login:
        args.login = True

    return args


def main() -> int:
    args = apply_interactive_defaults(parse_args())

    if args.mode in {"quiz", "export"}:
        cards = load_cards(args)
        print_cards_summary(cards)
        if args.mode == "export":
            export_csv(cards, args.export)
            print(f"CSV 저장 완료: {args.export}")
        else:
            run_quiz(cards, reverse=args.reverse, shuffle=args.shuffle, limit=args.limit)
        return 0

    driver = build_driver(args)
    try:
        if args.login or args.manual_login:
            login(driver, args)
        open_target_set(driver, args)
        cards = load_cards(args, driver=driver)
        if not cards:
            raise RuntimeError("카드를 찾지 못했습니다. 세트 페이지가 맞는지 확인해주세요.")
        print_cards_summary(cards)

        if args.mode == "memory":
            run_memory(driver, cards, args)
        elif args.mode == "recall":
            run_recall(driver, cards, args)
        elif args.mode == "spelling":
            run_spelling(driver, cards, args)
        elif args.mode == "matching":
            run_matching(driver, cards, args)
        elif args.mode == "test":
            run_test(driver, cards, args)
        elif args.mode == "api":
            post_learning_api(driver, cards, args)
        return 0
    except (NoSuchElementException, TimeoutException, RuntimeError, requests.RequestException) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    finally:
        if not args.headless:
            input("Chrome을 닫으려면 Enter를 누르세요...")
        driver.quit()


if __name__ == "__main__":
    raise SystemExit(main())
