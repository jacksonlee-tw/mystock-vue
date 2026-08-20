import requests
from services.exchange_rate_fetcher import BOT_CSV_URL, REQUEST_HEADERS, _decode

resp = requests.get(BOT_CSV_URL, headers=REQUEST_HEADERS, timeout=15)
print("HTTP status:", resp.status_code)
print("Content-Type:", resp.headers.get("Content-Type"))
print("Content length (bytes):", len(resp.content))
text = _decode(resp.content)
print("---- 前 800 字元 ----")
print(text[:800])
EOF
echo done
