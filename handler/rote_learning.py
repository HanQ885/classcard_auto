import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from handler.common import (
    MEMORY_ADVANCE_LABELS,
    REVEAL_LABELS,
    click_by_text,
    is_done,
    open_learning_mode,
    try_click_locator,
)


class RoteLearning:
    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver

    def run(self, num_d: int, word_d: list | None = None) -> None:
        driver = self.driver
        open_learning_mode(
            driver,
            ("암기학습", "암기 학습", "Memory"),
            entry_locators=(
                (By.XPATH, "/html/body/div[2]/div/div[2]/div[1]/div[1]"),
            ),
            start_locators=(
                (By.XPATH, "/html/body/div[2]/div[2]/div/div/div/div[4]/a"),
                (By.CSS_SELECTOR, "#wrapper-learn > div.start-opt-body a"),
            ),
        )

        idle_rounds = 0
        max_steps = max(30, num_d * 3)
        for _ in range(max_steps):
            if is_done(driver):
                print("완료 화면을 감지했습니다.")
                return

            if self.flip_or_advance():
                idle_rounds = 0
            else:
                idle_rounds += 1
                if idle_rounds >= 5:
                    print("암기학습 진행 버튼을 찾지 못해 종료합니다.")
                    return
            time.sleep(0.7)

    def flip_or_advance(self) -> bool:
        driver = self.driver
        if try_click_locator(
            driver,
            By.CSS_SELECTOR,
            "#wrapper-learn > div > div > div.study-bottom > div.btn-text.btn-down-cover-box",
            delay=0.2,
        ):
            return True
        if try_click_locator(
            driver,
            By.CSS_SELECTOR,
            "#wrapper-learn > div > div > div.study-bottom.down > div.btn-text.btn-know-box",
            delay=0.2,
        ):
            return True
        if click_by_text(driver, REVEAL_LABELS, max_text_length=80):
            return True
        if click_by_text(driver, MEMORY_ADVANCE_LABELS, max_text_length=80):
            return True
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ARROW_RIGHT)
            return True
        except Exception:
            return False
