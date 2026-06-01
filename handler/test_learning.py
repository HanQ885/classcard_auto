import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

from handler.common import (
    answer_for_text,
    click_answer_choice,
    click_by_text,
    element_text,
    fill_current_answer,
    is_done,
    is_visible,
    norm,
    open_learning_mode,
    rect_sort_key,
    side_matches,
    try_submit_or_next,
    type_answer,
    words_to_pairs,
)


class TestLearning:
    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver

    def run(self, num_d: int, word_d: list) -> None:
        driver = self.driver
        open_learning_mode(
            driver,
            ("테스트", "테스트학습", "Test"),
            entry_locators=(
                (By.XPATH, "/html/body/div[2]/div/div[2]/div[2]/div"),
            ),
            start_locators=(
                (By.CSS_SELECTOR, "#wrapper-test > div > div.quiz-start-div > div.layer.retry-layer.box > div.m-t-xl > a"),
                (By.CSS_SELECTOR, "#wrapper-test > div > div.quiz-start-div > div.layer.prepare-layer.box.bg-gray.text-white > div.text-center.m-t-md > a"),
                (By.CSS_SELECTOR, "#alertModal > div.modal-dialog > div > div.text-center.m-t-xl > a"),
            ),
        )

        idle_rounds = 0
        max_steps = max(50, num_d * 5)
        for _ in range(max_steps):
            if is_done(driver):
                print("완료 화면을 감지했습니다.")
                return
            if self.advance_after_feedback():
                idle_rounds = 0
            elif self.click_prompt_card(word_d):
                idle_rounds = 0
            elif self.answer_current_card_grid(word_d):
                idle_rounds = 0
            elif self.answer_visible_test_form(word_d):
                idle_rounds = 0
            elif fill_current_answer(driver, word_d):
                idle_rounds = 0
            elif click_answer_choice(driver, word_d, guess_unknown=False):
                idle_rounds = 0
            elif try_submit_or_next(driver):
                idle_rounds = 0
            else:
                idle_rounds += 1
                print("현재 테스트 문항에서 답을 찾지 못했습니다.")
                if idle_rounds >= 4:
                    return
            time.sleep(0.8)

    def answer_visible_test_form(self, word_d: list) -> bool:
        driver = self.driver
        questions = self.visible_question_blocks()
        if not questions:
            return self.answer_active_question(word_d)

        progress = False
        for question in questions:
            if not is_visible(question):
                continue
            prompt = self.find_prompt_in_scope(question, word_d)
            if not prompt:
                continue
            prompt_element, prompt_text, answer = prompt
            try:
                self.click_test_element(prompt_element)
                time.sleep(0.15)
            except Exception:
                pass

            if self.fill_question_input(question, answer):
                progress = True
                continue
            if self.click_question_choice(question, answer):
                print(f"테스트 문제: {prompt_text} -> 선택")
                progress = True

        if progress:
            self.click_test_submit()
        return progress

    def visible_question_blocks(self) -> list:
        selectors = (
            "#testForm > div",
            "[id='testForm'] > div",
            "#wrapper-test form > div",
            ".quiz-list > div",
            ".test-list > div",
            ".question",
            ".quiz-item",
            ".test-question",
            "[class*='question']",
            "[class*='quiz'][class*='item']",
        )
        blocks = []
        seen = set()
        for selector in selectors:
            for element in self.driver.find_elements(By.CSS_SELECTOR, selector):
                try:
                    if element.id in seen or not is_visible(element):
                        continue
                    text = element_text(element)
                    if not text or len(text) < 2:
                        continue
                    seen.add(element.id)
                    blocks.append(element)
                except Exception:
                    continue
        blocks.sort(key=rect_sort_key)
        return blocks

    def find_prompt_in_scope(self, scope, word_d: list):
        candidates = []
        for element in scope.find_elements(By.CSS_SELECTOR, "span,div,p,strong,em,h1,h2,h3,h4,a"):
            try:
                if not is_visible(element):
                    continue
                text = element_text(element)
                if not text or len(text) > 180:
                    continue
                answer = self.answer_from_prompt_text(text, word_d)
                if not answer:
                    continue
                text_norm = norm(text)
                exact = any(text_norm in {norm(front), norm(back)} for front, back in words_to_pairs(word_d))
                score = 0 if exact else 50
                y, x = rect_sort_key(element)
                candidates.append((score, y, x, len(text), element, text, answer))
            except Exception:
                continue
        if not candidates:
            return None
        _score, _y, _x, _length, element, text, answer = sorted(candidates)[0]
        return element, text, answer

    def answer_from_prompt_text(self, text: str, word_d: list) -> str | None:
        answer = answer_for_text(text, word_d)
        if answer:
            return answer
        matches = side_matches(text, word_d)
        if len(matches) == 1:
            return matches[0][2]
        return None

    def click_prompt_card(self, word_d: list) -> bool:
        if self.has_visible_answer_input():
            return False

        options = self.visible_card_options(word_d)
        if len(options) > 1:
            return False

        candidates = []
        seen = set()
        for element in self.driver.find_elements(By.CSS_SELECTOR, "#wrapper-test div,#wrapper-test span,body div,body span"):
            try:
                if element.id in seen or not element.is_displayed() or not element.is_enabled():
                    continue
                text = element_text(element)
                if not text or len(text) > 180:
                    continue
                matches = side_matches(text, word_d)
                if len(matches) != 1:
                    continue
                rect = element.rect
                if rect.get("width", 0) < 45 or rect.get("height", 0) < 20:
                    continue
                clickable = self.closest_clickable_card(element)
                seen.add(getattr(clickable, "id", element.id))
                y, x = rect_sort_key(clickable)
                candidates.append((y, x, len(text), clickable, text))
            except Exception:
                continue

        if not candidates:
            return False

        _y, _x, _length, element, text = sorted(candidates)[0]
        if self.click_test_element(element):
            print(f"test prompt card click: {text}")
            time.sleep(0.7)
            return True
        return False

    def has_visible_answer_input(self) -> bool:
        for input_element in self.driver.find_elements(
            By.CSS_SELECTOR,
            "input:not([type]),input[type='text'],input[type='search'],textarea,[contenteditable='true']",
        ):
            try:
                input_type = (input_element.get_attribute("type") or "").lower()
                if input_type in {"hidden", "submit", "button", "checkbox", "radio"}:
                    continue
                if input_element.is_displayed() and input_element.is_enabled():
                    return True
            except Exception:
                continue
        return False

    def answer_current_card_grid(self, word_d: list) -> bool:
        options = self.visible_card_options(word_d)
        if not options:
            return False

        option_values = {norm(value) for _element, _text, value, _answer in options}
        prompt = self.find_prompt_for_current_grid(word_d, option_values)
        if not prompt:
            self.print_visible_options(options)
            return False

        prompt_text, answer = prompt
        answer_norm = norm(answer)
        for element, text, value, _opposite in options:
            if norm(value) == answer_norm or self.choice_matches_answer(text, answer):
                self.click_test_element(element)
                print(f"test card: {prompt_text} -> {text}")
                time.sleep(0.5)
                self.advance_after_feedback()
                return True
        return False

    def visible_card_options(self, word_d: list) -> list:
        options = []
        seen = set()
        for element in self.driver.find_elements(By.CSS_SELECTOR, "button,a,[role='button'],label,[tabindex],div,span"):
            try:
                if element.id in seen or not element.is_displayed() or not element.is_enabled():
                    continue
                text = element_text(element)
                if not text or len(text) > 180:
                    continue
                matches = side_matches(text, word_d)
                if len(matches) != 1:
                    continue
                rect = element.rect
                if rect.get("width", 0) < 40 or rect.get("height", 0) < 20:
                    continue
                value, _side, answer = matches[0]
                clickable = self.closest_clickable_card(element)
                key = getattr(clickable, "id", element.id)
                if key in seen:
                    continue
                seen.add(key)
                options.append((clickable, text, value, answer))
            except Exception:
                continue
        options.sort(key=lambda item: (len(norm(item[1])), *rect_sort_key(item[0])))
        return options

    def closest_clickable_card(self, element):
        current = element
        for _ in range(4):
            try:
                parent = current.find_element(By.XPATH, "..")
                if not parent or not parent.is_displayed():
                    break
                current_rect = current.rect
                parent_rect = parent.rect
                parent_text = element_text(parent)
                grows_like_card = (
                    parent_rect.get("width", 0) >= current_rect.get("width", 0)
                    and parent_rect.get("height", 0) >= current_rect.get("height", 0)
                    and parent_rect.get("height", 0) <= 280
                )
                if grows_like_card and parent_text and norm(element_text(element)) in norm(parent_text):
                    current = parent
                    continue
                break
            except Exception:
                break
        return current

    def find_prompt_for_current_grid(self, word_d: list, option_values: set[str]) -> tuple[str, str] | None:
        candidates = []
        for element in self.driver.find_elements(By.CSS_SELECTOR, "body *"):
            try:
                text = self.dom_text(element)
                if not text or len(text) > 220:
                    continue
                matches = side_matches(text, word_d)
                if len(matches) != 1:
                    continue
                value, _side, answer = matches[0]
                value_norm = norm(value)
                answer_norm = norm(answer)
                if value_norm in option_values:
                    continue
                if answer_norm not in option_values:
                    continue
                visibility_score = 0 if element.is_displayed() else 30
                exact_score = 0 if norm(text) == value_norm else 50
                y, x = rect_sort_key(element)
                candidates.append((visibility_score + exact_score, y, x, len(text), value, answer))
            except Exception:
                continue
        if not candidates:
            return None
        _score, _y, _x, _length, value, answer = sorted(candidates)[0]
        return value, answer

    def dom_text(self, element) -> str:
        try:
            return " ".join((element.get_attribute("textContent") or element_text(element)).split())
        except Exception:
            return element_text(element)

    def print_visible_options(self, options: list) -> None:
        values = [text for _element, text, _value, _answer in options[:6]]
        if values:
            print("test card options:", " / ".join(values))

    def answer_active_question(self, word_d: list) -> bool:
        prompt = self.find_prompt_in_scope(self.driver.find_element(By.TAG_NAME, "body"), word_d)
        if not prompt:
            return False
        prompt_element, prompt_text, answer = prompt
        try:
            self.click_test_element(prompt_element)
            time.sleep(0.15)
        except Exception:
            pass
        if self.fill_global_input(answer):
            print(f"테스트 문제: {prompt_text} -> 입력: {answer}")
            self.click_test_submit()
            return True
        if self.click_global_choice(answer):
            print(f"테스트 문제: {prompt_text} -> 선택: {answer}")
            self.click_test_submit()
            return True
        return False

    def fill_question_input(self, question, answer: str) -> bool:
        for input_element in question.find_elements(
            By.CSS_SELECTOR,
            "input:not([type]),input[type='text'],input[type='search'],textarea,[contenteditable='true']",
        ):
            try:
                if not input_element.is_displayed() or not input_element.is_enabled():
                    continue
                current = input_element.get_attribute("value") or element_text(input_element)
                if current:
                    continue
                type_answer(input_element, answer)
                print(f"테스트 입력: {answer}")
                return True
            except Exception:
                continue
        return False

    def click_question_choice(self, question, answer: str) -> bool:
        for element in question.find_elements(By.CSS_SELECTOR, "button,a,[role='button'],label,div,span"):
            try:
                if not element.is_displayed() or not element.is_enabled():
                    continue
                text = element_text(element)
                if self.choice_matches_answer(text, answer):
                    self.click_test_element(self.closest_clickable_card(element))
                    print(f"테스트 선택: {text}")
                    return True
            except Exception:
                continue
        return False

    def fill_global_input(self, answer: str) -> bool:
        for input_element in self.driver.find_elements(
            By.CSS_SELECTOR,
            "input:not([type]),input[type='text'],input[type='search'],textarea,[contenteditable='true']",
        ):
            try:
                if not input_element.is_displayed() or not input_element.is_enabled():
                    continue
                type_answer(input_element, answer)
                return True
            except Exception:
                continue
        return False

    def click_global_choice(self, answer: str) -> bool:
        for element in self.driver.find_elements(By.CSS_SELECTOR, "button,a,[role='button'],label,div,span"):
            try:
                if not element.is_displayed() or not element.is_enabled():
                    continue
                text = element_text(element)
                if self.choice_matches_answer(text, answer):
                    self.click_test_element(self.closest_clickable_card(element))
                    return True
            except Exception:
                continue
        return False

    def choice_matches_answer(self, text: str, answer: str) -> bool:
        text_norm = norm(text)
        answer_norm = norm(answer)
        if not text_norm or not answer_norm:
            return False
        if text_norm == answer_norm:
            return True
        if len(answer_norm) >= 3 and answer_norm in text_norm and len(text_norm) <= len(answer_norm) + 80:
            return True
        return False

    def click_test_element(self, element) -> bool:
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        except Exception:
            pass

        clicked = False
        try:
            ActionChains(self.driver).move_to_element(element).pause(0.05).click().perform()
            clicked = True
        except Exception:
            try:
                element.click()
                clicked = True
            except Exception:
                try:
                    self.driver.execute_script("arguments[0].click();", element)
                    clicked = True
                except Exception:
                    pass

        try:
            self.driver.execute_script(
                """
                const el = arguments[0];
                for (const type of ['pointerdown', 'mousedown', 'mouseup', 'click']) {
                  el.dispatchEvent(new MouseEvent(type, {
                    bubbles: true,
                    cancelable: true,
                    view: window
                  }));
                }
                """,
                element,
            )
            clicked = True
        except Exception:
            pass

        if clicked:
            time.sleep(0.25)
        return clicked

    def advance_after_feedback(self) -> bool:
        try:
            body = self.driver.find_element(By.TAG_NAME, "body")
            text = body.text
        except Exception:
            return False
        if "정답" not in text and "오답" not in text:
            return False

        before = self.page_signature()
        for _ in range(6):
            if click_by_text(self.driver, ("다음", "계속", "확인", "next", "continue"), max_text_length=80):
                time.sleep(0.4)
            try:
                body.send_keys(Keys.ENTER)
                time.sleep(0.2)
                body.send_keys(Keys.SPACE)
                time.sleep(0.2)
                body.send_keys(Keys.ARROW_RIGHT)
                time.sleep(0.2)
            except Exception:
                pass
            if self.page_signature() != before:
                return True
        return True

    def page_signature(self) -> str:
        try:
            text = self.driver.find_element(By.TAG_NAME, "body").text
        except Exception:
            return ""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "|".join(lines[:14])

    def click_test_submit(self) -> bool:
        return click_by_text(
            self.driver,
            ("제출", "채점", "채점하기", "확인", "다음", "정답 확인", "답 확인"),
            max_text_length=120,
        )
