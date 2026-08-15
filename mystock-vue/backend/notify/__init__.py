# 匯入即註冊：比照 strategies/__init__.py 的慣例 —— notify.channels 底下的
# email_channel.py / telegram_channel.py 用 @channel 裝飾器把類別掛進
# channels.CHANNEL_REGISTRY，必須確保該套件被 import 過一次，dispatcher.py 才找得到
# 對應的管道轉接器（ADR-14、鐵則 R2）。
from notify import channels  # noqa: F401
