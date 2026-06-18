import time

from selenium import webdriver
from selenium.webdriver.common.by import By

from handler.common import click_answer_choice, is_done, open_learning_mode, try_submit_or_next


class RecallLearning:
    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver

    def run(self, num_d: int, word_d: list) -> None:
        driver = self.driver
        open_learning_mode(
            driver,
            ("리콜학습", "리콜 학습", "Recall"),
            entry_locators=(
                (By.XPATH, "/html/body/div[2]/div/div[2]/div[1]/div[2]"),
            ),
            start_locators=(
                (By.CSS_SELECTOR, "#wrapper-learn > div.start-opt-body > div > div > div > div.m-t > a"),
                (By.CSS_SELECTOR, "#wrapper-learn > div.start-opt-body a"),
            ),
        )

        idle_rounds = 0
        max_steps = max(40, num_d * 4)
        for _ in range(max_steps):
            if is_done(driver):
                print("완료 화면을 감지했습니다.")
                return
            if click_answer_choice(driver, word_d, guess_unknown=True):
                idle_rounds = 0
            elif try_submit_or_next(driver):
                idle_rounds = 0
            else:
                idle_rounds += 1
                print("현재 리콜 화면에서 맞는 선택지를 찾지 못했습니다.")
                if idle_rounds >= 4:
                    return
            time.sleep(0.8)
