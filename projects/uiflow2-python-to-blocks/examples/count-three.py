"""Core2 button counter with a visual and audible rule for the number 3."""

import M5
from M5 import *
import m5ui
import lvgl as lv


BLUE = 0x0050C8
DARK_BLUE = 0x003078
WHITE = 0xFFFFFF
RED = 0xFF0000

app_page = None
count_box = None
count = 0


def setup():
    global app_page, count_box, count

    M5.begin()
    Widgets.setRotation(1)
    m5ui.init()

    app_page = m5ui.M5Page(bg_c=BLUE)
    count_box = m5ui.M5TextArea(
        text="0",
        x=60,
        y=70,
        w=200,
        h=90,
        font=lv.font_montserrat_48,
        bg_c=DARK_BLUE,
        border_c=WHITE,
        text_c=WHITE,
        parent=app_page,
    )
    count_box.set_one_line(True)
    app_page.screen_load()

    Speaker.begin()
    Speaker.setVolumePercentage(0.5)
    count = 0


def loop():
    global count

    M5.update()
    if BtnA.wasPressed():
        count += 1
        count_text = str(count)
        special_number = count % 3 == 0 or "3" in count_text
        count_box.set_text(count_text)

        if special_number:
            count_box.set_text_color(
                RED, lv.OPA.COVER, lv.PART.MAIN | lv.STATE.DEFAULT
            )
            Speaker.tone(880, 150)
        else:
            count_box.set_text_color(
                WHITE, lv.OPA.COVER, lv.PART.MAIN | lv.STATE.DEFAULT
            )


if __name__ == "__main__":
    try:
        setup()
        while True:
            loop()
    except (Exception, KeyboardInterrupt) as error:
        try:
            m5ui.deinit()
            from utility import print_error_msg

            print_error_msg(error)
        except ImportError:
            print(error)
