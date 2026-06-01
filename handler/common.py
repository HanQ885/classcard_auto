import random
import re
import time

from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


DONE_MARKERS = ("완료", "결과", "학습 종료", "학습이 종료", "수고")
START_LABELS = ("시작", "학습 시작", "학습 시작하기", "START")
SUBMIT_LABELS = (
    "정답 확인",
    "답 확인",
    "확인",
    "다음 문제",
    "다음",
    "제출",
    "채점",
    "채점하기",
    "계속",
    "check",
    "next",
    "submit",
)
REVEAL_LABELS = ("뒤집기", "뜻 보기", "정답 보기", "보기", "의미 보기")
MEMORY_ADVANCE_LABELS = (
    "알고 있어요",
    "외웠어요",
    "알아요",
    "다음",
    "넘기기",
    "pass",
    "next",
)
ANSWER_INPUT_SELECTOR = (
    "input:not([type]),"
    "input[type='text'],"
    "input[type='search'],"
    "input[type='tel'],"
    "textarea,"
    "[contenteditable='true']"
)
OPTION_SELECTOR = "button,a,[role='button'],label,[tabindex],div,span"
TEXT_SELECTOR = "span,div,p,h1,h2,h3,h4,strong,em,label"
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
    "테스트",
    "카드 이미지",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def norm(value: str) -> str:
    return clean_text(value).casefold()


def is_noise_line(line: str) -> bool:
    line = clean_text(line)
    if line in NOISE_LINES:
        return True
    if line.startswith("http://") or line.startswith("https://"):
        return True
    if re.fullmatch(r"\d+\s*카드\s*\|.*", line):
        return True
    if "로그인이 필요" in line:
        return True
    return False


def element_text(element) -> str:
    try:
        values = [element.text]
        if (element.tag_name or "").lower() in {"input", "textarea"}:
            values.append(element.get_attribute("value"))
        return clean_text(" ".join(value for value in values if value))
    except Exception:
        return ""


def element_search_text(element) -> str:
    try:
        values = [
            element_text(element),
            element.get_attribute("value"),
            element.get_attribute("aria-label"),
            element.get_attribute("title"),
            element.get_attribute("data-original-title"),
            element.get_attribute("href"),
            element.get_attribute("class"),
        ]
        return clean_text(" ".join(value for value in values if value))
    except Exception:
        return ""


def is_visible(element) -> bool:
    try:
        return element.is_displayed()
    except (StaleElementReferenceException, NoSuchElementException):
        return False


def rect_sort_key(element) -> tuple[int, int]:
    try:
        rect = element.rect
        return int(rect.get("y", 0)), int(rect.get("x", 0))
    except Exception:
        return 0, 0


def click_element(driver, element) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    try:
        element.click()
    except Exception:
        driver.execute_script("arguments[0].click();", element)
    time.sleep(0.35)


def try_click_locator(driver, by: By, selector: str, delay: float = 0.5) -> bool:
    try:
        element = driver.find_element(by, selector)
        if is_visible(element):
            click_element(driver, element)
            time.sleep(delay)
            return True
    except Exception:
        return False
    return False


def click_by_text(driver, labels: tuple[str, ...], max_text_length: int = 120) -> bool:
    label_norms = tuple(norm(label) for label in labels)
    for selector in ("a,button,[role='button'],input,label", "div,span"):
        for element in driver.find_elements(By.CSS_SELECTOR, selector):
            try:
                text = element_search_text(element)
                if not element.is_displayed() or not text or len(text) > max_text_length:
                    continue
                text_norm = norm(text)
                if any(label in text_norm for label in label_norms):
                    click_element(driver, element)
                    return True
            except Exception:
                continue
    return False


def open_learning_mode(
    driver,
    mode_labels: tuple[str, ...],
    entry_locators: tuple[tuple[By, str], ...] = (),
    start_locators: tuple[tuple[By, str], ...] = (),
    delay: float = 1.0,
) -> None:
    opened = False
    for by, selector in entry_locators:
        if try_click_locator(driver, by, selector, delay=delay):
            opened = True
            break
    if not opened:
        opened = click_by_text(driver, mode_labels, max_text_length=260)
    if not opened:
        print("학습 버튼을 자동으로 찾지 못했습니다. Chrome에서 해당 학습으로 들어간 뒤 Enter를 누르세요.")
        input()

    time.sleep(delay)
    clicked_start = False
    for by, selector in start_locators:
        if try_click_locator(driver, by, selector, delay=delay):
            clicked_start = True
            time.sleep(delay)
    if not clicked_start:
        click_by_text(driver, START_LABELS, max_text_length=120)
    time.sleep(delay)


def words_to_pairs(word_d: list) -> list[tuple[str, str]]:
    da_e, da_k = word_d[0], word_d[1]
    pairs: list[tuple[str, str]] = []
    for front, back in zip(da_e, da_k):
        if not front or not back or front == 0 or back == 0:
            continue
        front = clean_text(str(front))
        back = clean_text(str(back))
        if front and back and front != back:
            pairs.append((front, back))
    return pairs


def side_matches(text: str, word_d: list) -> list[tuple[str, str, str]]:
    text_norm = norm(text)
    matches: list[tuple[str, str, str]] = []
    if not text_norm:
        return matches
    for front, back in words_to_pairs(word_d):
        front_norm = norm(front)
        back_norm = norm(back)
        if text_norm == front_norm or (len(front_norm) >= 3 and front_norm in text_norm):
            matches.append((front, "front", back))
        if text_norm == back_norm or (len(back_norm) >= 3 and back_norm in text_norm):
            matches.append((back, "back", front))
    return matches


def answer_for_text(text: str, word_d: list) -> str | None:
    exact = []
    contains = []
    text_norm = norm(text)
    for front, back in words_to_pairs(word_d):
        front_norm = norm(front)
        back_norm = norm(back)
        if text_norm == front_norm:
            exact.append(back)
        elif text_norm == back_norm:
            exact.append(front)
        elif len(front_norm) >= 3 and front_norm in text_norm:
            contains.append(back)
        elif len(back_norm) >= 3 and back_norm in text_norm:
            contains.append(front)
    if len(exact) == 1:
        return exact[0]
    if len(contains) == 1:
        return contains[0]
    return None


def current_scopes(driver):
    scopes = []
    for selector in ("#wrapper-learn", "#wrapper-test", "#testForm", "form", "body"):
        try:
            for element in driver.find_elements(By.CSS_SELECTOR, selector):
                if is_visible(element):
                    scopes.append(element)
        except Exception:
            continue
    return scopes or [driver.find_element(By.TAG_NAME, "body")]


def visible_text_nodes(driver):
    seen = set()
    for scope in current_scopes(driver):
        for element in scope.find_elements(By.CSS_SELECTOR, TEXT_SELECTOR):
            try:
                element_id = element.id
                if element_id in seen or not element.is_displayed():
                    continue
                seen.add(element_id)
                text = element_text(element)
                if not text or len(text) > 180 or is_noise_line(text):
                    continue
                yield element, text
            except Exception:
                continue


def infer_prompt_answer(
    driver,
    word_d: list,
    allowed_answers: set[str] | None = None,
) -> tuple[str, str] | None:
    candidates: list[tuple[int, int, str, str]] = []
    for element, text in visible_text_nodes(driver):
        answer = answer_for_text(text, word_d)
        if not answer:
            continue
        if allowed_answers is not None and norm(answer) not in allowed_answers:
            continue
        y, _ = rect_sort_key(element)
        exact_bonus = 0 if any(norm(text) in {norm(f), norm(b)} for f, b in words_to_pairs(word_d)) else 50
        candidates.append((y + exact_bonus, len(text), text, answer))
    if not candidates:
        return None
    _, _, prompt, answer = sorted(candidates)[0]
    return prompt, answer


def answer_inputs(driver):
    inputs = []
    for element in driver.find_elements(By.CSS_SELECTOR, ANSWER_INPUT_SELECTOR):
        try:
            input_type = (element.get_attribute("type") or "").lower()
            if input_type in {"hidden", "submit", "button", "checkbox", "radio"}:
                continue
            if element.is_displayed() and element.is_enabled():
                inputs.append(element)
        except Exception:
            continue
    inputs.sort(key=rect_sort_key)
    return inputs


def type_answer(element, answer: str) -> None:
    element.click()
    try:
        element.clear()
    except Exception:
        element.send_keys(Keys.CONTROL + "a")
    element.send_keys(answer)


def fill_current_answer(driver, word_d: list) -> bool:
    inferred = infer_prompt_answer(driver, word_d)
    if not inferred:
        return False
    prompt, answer = inferred
    for input_element in answer_inputs(driver):
        try:
            type_answer(input_element, answer)
            print(f"문제: {prompt} -> 입력: {answer}")
            if not click_by_text(driver, SUBMIT_LABELS, max_text_length=120):
                input_element.send_keys(Keys.ENTER)
            time.sleep(0.5)
            return True
        except Exception:
            continue
    return False


def clickable_card_options(driver, word_d: list, max_text_length: int = 140):
    options = []
    for element in driver.find_elements(By.CSS_SELECTOR, OPTION_SELECTOR):
        try:
            if not element.is_displayed() or not element.is_enabled():
                continue
            text = element_text(element)
            if not text or len(text) > max_text_length:
                continue
            matches = side_matches(text, word_d)
            if len(matches) != 1:
                continue
            value, _side, answer = matches[0]
            options.append((element, text, value, answer))
        except Exception:
            continue
    options.sort(key=lambda item: (len(norm(item[1])), *rect_sort_key(item[0])))
    return options


def click_answer_choice(driver, word_d: list, guess_unknown: bool = False) -> bool:
    options = clickable_card_options(driver, word_d)
    option_values = {norm(value) for _, _, value, _ in options}
    inferred = infer_prompt_answer(driver, word_d, allowed_answers=option_values)

    if inferred:
        prompt, answer = inferred
        answer_norm = norm(answer)
        for element, text, value, _ in options:
            if norm(value) == answer_norm:
                click_element(driver, element)
                print(f"문제: {prompt} -> 선택: {text}")
                return True

    body = norm(driver.find_element(By.TAG_NAME, "body").text)
    for element, text, _value, answer in options:
        if norm(answer) in body:
            click_element(driver, element)
            print(f"선택: {text}")
            return True

    if guess_unknown and options:
        element, text, _value, _answer = random.choice(options)
        click_element(driver, element)
        print(f"임의 선택: {text}")
        return True
    return False


def click_exact_card_text(driver, target: str) -> bool:
    target_norm = norm(target)
    candidates = []
    for element in driver.find_elements(By.CSS_SELECTOR, OPTION_SELECTOR):
        try:
            if not element.is_displayed() or not element.is_enabled():
                continue
            text = element_text(element)
            if norm(text) == target_norm:
                candidates.append(element)
        except Exception:
            continue
    candidates.sort(key=lambda element: (len(element_text(element)), *rect_sort_key(element)))
    if not candidates:
        return False
    click_element(driver, candidates[0])
    return True


def try_submit_or_next(driver) -> bool:
    if click_by_text(driver, SUBMIT_LABELS, max_text_length=120):
        return True
    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ENTER)
        time.sleep(0.3)
        return True
    except Exception:
        return False


def is_done(driver) -> bool:
    try:
        text = driver.find_element(By.TAG_NAME, "body").text
    except Exception:
        return False
    return any(marker in text for marker in DONE_MARKERS)
