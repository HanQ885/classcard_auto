import time

from selenium import webdriver
from selenium.webdriver.common.by import By

from handler.common import (
    answer_for_text,
    click_answer_choice,
    click_by_text,
    click_element,
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
            if self.answer_visible_test_form(word_d):
                idle_rounds = 0
            elif fill_current_answer(driver, word_d):
                idle_rounds = 0
            elif click_answer_choice(driver, word_d, guess_unknown=True):
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
                click_element(driver, prompt_element)
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

    def answer_active_question(self, word_d: list) -> bool:
        prompt = self.find_prompt_in_scope(self.driver.find_element(By.TAG_NAME, "body"), word_d)
        if not prompt:
            return False
        _prompt_element, prompt_text, answer = prompt
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
                    click_element(self.driver, element)
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
                    click_element(self.driver, element)
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

    def click_test_submit(self) -> bool:
        return click_by_text(
            self.driver,
            ("제출", "채점", "채점하기", "확인", "다음", "정답 확인", "답 확인"),
            max_text_length=120,
        )
