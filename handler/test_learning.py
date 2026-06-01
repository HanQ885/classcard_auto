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
    open_learning_mode,
    try_submit_or_next,
    type_answer,
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
        questions = []
        for selector in ("#testForm > div", "[id='testForm'] > div", ".quiz-list > div", ".test-list > div"):
            questions.extend(driver.find_elements(By.CSS_SELECTOR, selector))

        progress = False
        for question in questions:
            if not is_visible(question):
                continue
            answer = answer_for_text(element_text(question), word_d)
            if not answer:
                continue
            if self.fill_question_input(question, answer):
                progress = True
                continue
            if self.click_question_choice(question, answer):
                progress = True

        if progress:
            click_by_text(driver, ("제출", "채점", "채점하기", "확인", "다음"), max_text_length=120)
        return progress

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
        answer_norm = answer.strip().casefold()
        for element in question.find_elements(By.CSS_SELECTOR, "button,a,[role='button'],label,div,span"):
            try:
                if not element.is_displayed() or not element.is_enabled():
                    continue
                text = element_text(element)
                if text.strip().casefold() == answer_norm:
                    click_element(self.driver, element)
                    print(f"테스트 선택: {text}")
                    return True
            except Exception:
                continue
        return False
