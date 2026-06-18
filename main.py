import argparse
import sys
import time
import warnings

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from handler.matching_game import MatchingGame
from handler.recall_learning import RecallLearning
from handler.rote_learning import RoteLearning
from handler.spelling_learning import SpellingLearning
from handler.test_learning import TestLearning
from utility import (
    chd_wh,
    choice_class,
    choice_set,
    classcard_api_post,
    export_csv,
    get_account,
    parse_class_id,
    parse_set_id,
    print_word_summary,
    word_count,
    word_get,
)


warnings.filterwarnings("ignore", category=DeprecationWarning)

CLASSCARD_LOGIN_URL = "https://www.classcard.net/Login"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ClassCard automation")
    parser.add_argument(
        "--mode",
        choices=("memory", "recall", "spelling", "test", "matching", "export", "api-memory", "api-recall", "api-spelling", "api-test"),
        help="메뉴를 건너뛰고 바로 실행할 학습유형",
    )
    parser.add_argument("--manual-login", action="store_true", help="Chrome에서 직접 로그인하고 세트 페이지로 이동합니다.")
    parser.add_argument("--set-url", help="바로 열 ClassCard 세트 URL")
    parser.add_argument("--class-id", help="API 요청용 클래스 ID")
    parser.add_argument("--set-id", help="API 요청용 세트 ID")
    parser.add_argument("--user-id", help="API 요청용 사용자 ID")
    parser.add_argument("--headless", action="store_true", help="Chrome 창을 숨깁니다.")
    parser.add_argument("--profile-dir", help="Chrome 사용자 데이터 폴더")
    parser.add_argument("--export", default="classcard_cards.csv", help="CSV 저장 경로")
    return parser.parse_args()


def mode_to_menu(mode: str | None) -> int | None:
    return {
        "memory": 1,
        "recall": 2,
        "spelling": 3,
        "test": 4,
        "api-memory": 5,
        "api-recall": 6,
        "api-spelling": 7,
        "api-test": 8,
        "matching": 9,
        "export": 10,
    }.get(mode or "")


def build_driver(args: argparse.Namespace) -> webdriver.Chrome:
    chrome_options = Options()
    if args.headless:
        chrome_options.add_argument("--headless=new")
    if args.profile_dir:
        chrome_options.add_argument(f"--user-data-dir={args.profile_dir}")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument("--window-size=1280,900")
    chrome_options.add_argument("--log-level=1")
    return webdriver.Chrome(options=chrome_options)


def wait_for_body(driver: webdriver.Chrome, timeout: int = 20) -> None:
    WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.TAG_NAME, "body")))


def login_with_account(driver: webdriver.Chrome) -> None:
    account = get_account()
    driver.get(CLASSCARD_LOGIN_URL)
    wait_for_body(driver)
    id_element = driver.find_element(By.ID, "login_id")
    pw_element = driver.find_element(By.ID, "login_pwd")
    id_element.clear()
    id_element.send_keys(account["id"])
    pw_element.clear()
    pw_element.send_keys(account["pw"])
    time.sleep(0.5)

    try:
        driver.find_element(By.XPATH, "/html/body/div[1]/div/div/div/div/form/div[3]/a").click()
    except NoSuchElementException:
        pw_element.send_keys(Keys.ENTER)
    time.sleep(1)


def manual_login_and_open_set(driver: webdriver.Chrome, args: argparse.Namespace) -> str:
    driver.get(CLASSCARD_LOGIN_URL)
    wait_for_body(driver)
    input("Chrome에서 로그인한 뒤 Enter를 누르세요...")
    if args.set_url:
        driver.get(args.set_url)
        wait_for_body(driver)
        time.sleep(1)
        return driver.current_url
    input("Chrome에서 목표 ClassCard 세트 페이지로 이동한 뒤 Enter를 누르세요...")
    wait_for_body(driver)
    return driver.current_url


def read_classes(driver: webdriver.Chrome) -> dict:
    class_dict = {}
    for class_item in driver.find_elements(By.CSS_SELECTOR, ".left-class-list a, a[href*='ClassMain']"):
        class_name = class_item.text.strip()
        href = class_item.get_attribute("href") or ""
        class_id = href.rstrip("/").split("/")[-1]
        if not class_name or class_id == "joinClass":
            continue
        if class_id.isdigit() or "ClassMain" in href:
            class_dict[len(class_dict)] = {"class_name": class_name, "class_id": class_id}
    return class_dict


def read_sets(driver: webdriver.Chrome) -> dict:
    sets_dict = {}
    set_links = driver.find_elements(By.CSS_SELECTOR, ".set-items a, a[href*='/set/'], a[data-idx]")
    for link in set_links:
        title = link.text.strip()
        href = link.get_attribute("href") or ""
        set_id = link.get_attribute("data-idx") or parse_set_id(href)
        if not title or not set_id:
            continue
        card_num = ""
        try:
            card_num = link.find_element(By.TAG_NAME, "span").text
            title = title.replace(card_num, "").strip()
        except NoSuchElementException:
            pass
        if any(item.get("set_id") == set_id for item in sets_dict.values()):
            continue
        sets_dict[len(sets_dict)] = {"title": title, "card_num": card_num, "set_id": set_id}
    return sets_dict


def choose_class_and_set(driver: webdriver.Chrome, args: argparse.Namespace) -> tuple[str | None, str | None, str]:
    if args.set_url:
        driver.get(args.set_url)
        wait_for_body(driver)
        return parse_class_id(driver.current_url), parse_set_id(driver.current_url), driver.current_url

    class_dict = read_classes(driver)
    if len(class_dict) == 0:
        raise RuntimeError("클래스가 없습니다. --manual-login 으로 직접 세트 페이지까지 이동해주세요.")
    choice_class_val = 0 if len(class_dict) == 1 else choice_class(class_dict)
    class_id = class_dict[choice_class_val].get("class_id")

    driver.get(f"https://www.classcard.net/ClassMain/{class_id}")
    wait_for_body(driver)
    time.sleep(1)

    sets_dict = read_sets(driver)
    if not sets_dict:
        raise RuntimeError("세트를 찾지 못했습니다. --manual-login 으로 직접 세트 페이지까지 이동해주세요.")
    set_choice = choice_set(sets_dict)
    set_id = sets_dict[set_choice]["set_id"]
    set_site = f"https://www.classcard.net/set/{set_id}/{class_id}"
    driver.get(set_site)
    wait_for_body(driver)
    time.sleep(1)
    return class_id, set_id, set_site


def get_js_value(driver: webdriver.Chrome, expression: str) -> str | None:
    try:
        value = driver.execute_script(f"return {expression};")
        return str(value) if value is not None else None
    except Exception:
        return None


def get_user_id(driver: webdriver.Chrome, args: argparse.Namespace) -> str | None:
    return args.user_id or get_js_value(driver, "window.c_u || (typeof c_u !== 'undefined' ? c_u : null)")


def execute_mode(
    selected: int,
    driver: webdriver.Chrome,
    word_d: list,
    class_id: str | None,
    set_id: str | None,
    args: argparse.Namespace,
) -> None:
    num_d = word_count(word_d) + 1
    if selected == 1:
        print("암기학습을 시작합니다.")
        RoteLearning(driver=driver).run(num_d=num_d, word_d=word_d)
    elif selected == 2:
        print("리콜학습을 시작합니다.")
        RecallLearning(driver=driver).run(num_d=num_d, word_d=word_d)
    elif selected == 3:
        print("스펠학습을 시작합니다.")
        SpellingLearning(driver=driver).run(num_d=num_d, word_d=word_d)
    elif selected == 4:
        print("테스트학습을 시작합니다.")
        TestLearning(driver=driver).run(num_d=num_d, word_d=word_d)
    elif selected == 9:
        print("매칭 게임을 시작합니다.")
        MatchingGame(driver=driver).run(num_d=num_d, word_d=word_d)
    elif selected == 10:
        export_csv(word_d, args.export)
        print(f"CSV 저장 완료: {args.export}")
    elif selected in {5, 6, 7, 8}:
        activity = {5: 1, 6: 2, 7: 3, 8: 4}[selected]
        user_id = get_user_id(driver, args)
        if not set_id:
            set_id = args.set_id or parse_set_id(driver.current_url)
        if not class_id:
            class_id = args.class_id or parse_class_id(driver.current_url)
        missing = [name for name, value in (("user_id", user_id), ("set_id", set_id), ("class_id", class_id)) if not value]
        if missing:
            raise RuntimeError(f"API 요청에 필요한 값이 없습니다: {', '.join(missing)}")
        print("학습 기록 API 요청을 시작합니다.")
        classcard_api_post(
            user_id=user_id,
            set_id=set_id,
            class_id=class_id,
            view_cnt=word_count(word_d),
            activity=activity,
            driver=driver,
        )
    else:
        raise RuntimeError("지원하지 않는 학습유형입니다.")


def main() -> int:
    args = parse_args()
    selected = mode_to_menu(args.mode) or chd_wh()

    print("크롬 드라이브를 불러오고 있습니다 잠시만 기다려주세요!")
    driver = build_driver(args)
    try:
        if args.manual_login:
            set_site = manual_login_and_open_set(driver, args)
            class_id = args.class_id or parse_class_id(set_site)
            set_id = args.set_id or parse_set_id(set_site)
        else:
            login_with_account(driver)
            class_id, set_id, set_site = choose_class_and_set(driver, args)

        word_d = word_get(driver)
        print_word_summary(word_d)
        execute_mode(selected, driver, word_d, class_id, set_id, args)
        print("학습이 종료되었습니다.")
        return 0
    except (NoSuchElementException, TimeoutException, RuntimeError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    finally:
        if not args.headless:
            input("Chrome을 닫으려면 Enter를 누르세요...")
        driver.quit()


if __name__ == "__main__":
    raise SystemExit(main())
