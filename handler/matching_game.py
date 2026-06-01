import time

from selenium import webdriver
from selenium.webdriver.common.by import By

from handler.common import (
    click_answer_choice,
    click_exact_card_text,
    is_done,
    open_learning_mode,
    try_submit_or_next,
    words_to_pairs,
)


class MatchingGame:
    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver

    def run(self, num_d: int, word_d: list) -> None:
        driver = self.driver
        open_learning_mode(
            driver,
            ("매칭 게임", "매칭게임", "Matching"),
            entry_locators=(),
            start_locators=(),
        )

        idle_rounds = 0
        matched = 0
        max_steps = max(60, num_d * 6)
        pairs = words_to_pairs(word_d)

        for _ in range(max_steps):
            if is_done(driver):
                print("완료 화면을 감지했습니다.")
                return

            progress = False
            for front, back in pairs:
                if click_exact_card_text(driver, front):
                    time.sleep(0.15)
                    if click_exact_card_text(driver, back):
                        matched += 1
                        print(f"매칭: {front} / {back}")
                        progress = True
                        break

            if progress:
                idle_rounds = 0
            elif click_answer_choice(driver, word_d, guess_unknown=True):
                idle_rounds = 0
            elif try_submit_or_next(driver):
                idle_rounds = 0
            else:
                idle_rounds += 1
                print("현재 매칭 화면에서 맞는 카드를 찾지 못했습니다.")
                if idle_rounds >= 5:
                    print(f"매칭 시도 종료: {matched}쌍")
                    return
            time.sleep(0.5)
