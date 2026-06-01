import csv
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By


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


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def visible_lines(text: str) -> list[str]:
    return [clean_text(line) for line in (text or "").splitlines() if clean_text(line)]


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


def dedupe_cards(cards: list[tuple[str, str]]) -> list[tuple[str, str]]:
    deduped = []
    seen = set()
    for front, back in cards:
        front = clean_text(front)
        back = clean_text(back)
        if not front or not back or front == back:
            continue
        key = (front.casefold(), back.casefold())
        if key not in seen:
            deduped.append((front, back))
            seen.add(key)
    return deduped


def parse_cards_from_nodes(soup: BeautifulSoup) -> list[tuple[str, str]]:
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
        cards = []
        for node in soup.select(selector):
            lines = [line for line in visible_lines(node.get_text("\n")) if not is_noise_line(line)]
            if len(lines) >= 2:
                cards.append((lines[0], lines[1]))
        cards = dedupe_cards(cards)
        if cards:
            return cards
    return []


def parse_cards_from_text(text: str) -> list[tuple[str, str]]:
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
    return dedupe_cards(
        [(candidates[index], candidates[index + 1]) for index in range(0, len(candidates) - 1, 2)]
    )


def parse_cards_from_html(html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    return parse_cards_from_nodes(soup) or parse_cards_from_text(soup.get_text("\n"))


def word_get(driver: webdriver.Chrome, num_d: int | None = None) -> list:
    cards = parse_cards_from_html(driver.page_source)
    if not cards:
        cards = parse_cards_from_text(driver.find_element(By.TAG_NAME, "body").text)
    if not cards:
        raise RuntimeError("카드를 찾지 못했습니다. 세트 페이지가 맞는지 확인해주세요.")

    da_e = [0]
    da_k = [0]
    da_kyn = [0]
    for front, back in cards:
        da_e.append(front)
        da_k.append(back.split("\n")[0])
        da_kyn.append(back)
    return [da_e, da_k, da_kyn]


def word_count(word_d: list) -> int:
    return max(0, len(word_d[0]) - 1)


def print_word_summary(word_d: list) -> None:
    count = word_count(word_d)
    print(f"카드 {count}개를 읽었습니다.")
    for front, back in zip(word_d[0][1:6], word_d[1][1:6]):
        print(f"- {front} / {back}")
    if count > 5:
        print(f"... 외 {count - 5}개")


def export_csv(word_d: list, output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["front", "back"])
        for front, back in zip(word_d[0][1:], word_d[1][1:]):
            writer.writerow([front, back])


def chd_wh() -> int:
    os.system("cls" if os.name == "nt" else "clear")
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
    while True:
        try:
            ch_d = int(input(">>> "))
            if 1 <= ch_d <= 10:
                return ch_d
            raise ValueError
        except ValueError:
            print("학습유형을 다시 입력해주세요.")
        except KeyboardInterrupt:
            raise SystemExit


def choice_set(sets: dict) -> int:
    os.system("cls" if os.name == "nt" else "clear")
    print("학습할 세트를 선택해주세요.")
    print("Ctrl + C 를 눌러 종료")
    for set_item in sets:
        print(f"[{set_item + 1}] {sets[set_item].get('title')} | {sets[set_item].get('card_num')}")
    while True:
        try:
            ch_s = int(input(">>> "))
            if 1 <= ch_s <= len(sets):
                return ch_s - 1
            raise ValueError
        except ValueError:
            print("세트를 다시 입력해주세요.")
        except KeyboardInterrupt:
            raise SystemExit


def choice_class(class_dict: dict) -> int:
    os.system("cls" if os.name == "nt" else "clear")
    print("학습할 클래스를 선택해주세요.")
    print("Ctrl + C 를 눌러 종료")
    for class_item in class_dict:
        print(f"[{class_item + 1}] {class_dict[class_item].get('class_name')}")
    while True:
        try:
            ch_c = int(input(">>> "))
            if 1 <= ch_c <= len(class_dict):
                return ch_c - 1
            raise ValueError
        except ValueError:
            print("클래스를 다시 입력해주세요.")
        except KeyboardInterrupt:
            raise SystemExit


def check_id(user_id: str, password: str) -> bool:
    print("계정 정보를 확인하고 있습니다 잠시만 기다려주세요!")
    headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
    data = {"login_id": user_id, "login_pwd": password}
    res = requests.post("https://www.classcard.net/LoginProc", headers=headers, data=data, timeout=20)
    try:
        return res.json().get("result") == "ok"
    except ValueError:
        return False


def save_id() -> dict:
    while True:
        user_id = input("아이디를 입력하세요 : ")
        password = input("비밀번호를 입력하세요 : ")
        if check_id(user_id, password):
            data = {"id": user_id, "pw": password}
            Path("config.json").write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
            print("아이디 비밀번호가 저장되었습니다.\n")
            return data
        print("아이디 또는 비밀번호가 잘못되었습니다.\n")


def get_account() -> dict:
    try:
        json_data = json.loads(Path("config.json").read_text(encoding="utf-8"))
        if json_data["id"] and json_data["pw"]:
            return json_data
    except Exception:
        pass
    return save_id()


def classcard_api_post(
    user_id: int | str,
    set_id: int | str,
    class_id: int | str,
    view_cnt: int,
    activity: int,
    driver: webdriver.Chrome | None = None,
) -> None:
    url = "https://www.classcard.net/ViewSetAsync/resetAllLog"
    data = {
        "set_idx": set_id,
        "activity": activity,
        "user_idx": user_id,
        "view_cnt": view_cnt,
        "class_idx": class_id,
    }
    headers = {"content-type": "application/x-www-form-urlencoded; charset=UTF-8"}
    session = requests.Session()
    if driver is not None:
        for cookie in driver.get_cookies():
            session.cookies.set(cookie["name"], cookie["value"], domain=cookie.get("domain"))
    response = session.post(url, data=data, headers=headers, timeout=20)
    print(f"API status: {response.status_code}")
    print(response.text[:500])


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
