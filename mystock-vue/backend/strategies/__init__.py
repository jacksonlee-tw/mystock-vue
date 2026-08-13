# 匯入即註冊：conditions_tech.py 用 @condition 裝飾器把函式掛進 registry.CONDITION_REGISTRY，
# 必須確保模組被 import 過一次，掃描器（scanner.py）才找得到對應的條件函式。
from strategies import conditions_tech  # noqa: F401
