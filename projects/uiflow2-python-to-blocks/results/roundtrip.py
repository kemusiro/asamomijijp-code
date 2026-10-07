import os, sys, io
import M5
from M5 import *
import m5ui
import lvgl as lv
from unit import RGBUnit
import time



page0 = None
rgb_0 = None


def setup():
  global page0, rgb_0

  M5.begin()
  Widgets.setRotation(1)
  m5ui.init()
  page0 = m5ui.M5Page(bg_c=0xffffff)

  rgb_0 = RGBUnit((36, 26), 3)
  page0.screen_load()
  rgb_0.fill_color(0xff0000)
  time.sleep(2)


def loop():
  global page0, rgb_0
  M5.update()
  rgb_0.fill_color(0x33ff33)
  time.sleep(1)
  rgb_0.fill_color(0x000000)
  time.sleep(1)


if __name__ == '__main__':
  try:
    setup()
    while True:
      loop()
  except (Exception, KeyboardInterrupt) as e:
    try:
      m5ui.deinit()
      from utility import print_error_msg
      print_error_msg(e)
    except ImportError:
      print("please update to latest firmware")
