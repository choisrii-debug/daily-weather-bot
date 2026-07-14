import os
import datetime
import time
import requests
import json

# ==========================================
# 1. 설정 정보 입력 (Firebase 연동)
# ==========================================
FIREBASE_URL = os.environ.get("FIREBASE_URL")

# 공공데이터포털(기상청) 인증키 (Decoding)
DATA_GO_KR_KEY = "ca7c28c19530e6217757ee652fa803c0686247e1bb825f9faddeeec152c3b03b"

# 송파구 기준 기상청 주소 좌표
NX = "62"
NY = "126"
LOCATION_NAME = "송파구"

# GitHub Pages 페이지 주소
PAGE_URL = "https://choisrii-debug.github.io/daily-weather-bot/"

# ==========================================
# 🔑 Firebase 메모장에서 토큰 읽고 쓰기
# ==========================================
def get_tokens_from_firebase():
    try:
        res = requests.get(FIREBASE_URL).json()
        return res
    except Exception as e:
        print("Firebase 읽기 오류:", e)
        return None

def update_tokens_to_firebase(access_token, refresh_token):
    try:
        data = {"access_token": access_token, "refresh_token": refresh_token}
        requests.put(FIREBASE_URL, json=data)
        print("💾 새로운 토큰들이 Firebase 메모장에 안전하게 저장되었습니다!")
    except Exception as e:
        print("Firebase 저장 오류:", e)

# ==========================================
# 🔄 카카오 토큰 갱신하기
# ==========================================
def refresh_kakao_token(rest_api_key, client_secret, current_refresh_token):
    url = "https://kauth.kakao.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": rest_api_key,
        "client_secret": client_secret,
        "refresh_token": current_refresh_token,
    }

    res = requests.post(url, data=payload).json()

    new_access = res.get("access_token")
    new_refresh = res.get("refresh_token", current_refresh_token)

    if new_access:
        return new_access, new_refresh
    else:
        print("카카오 서버 응답 에러:", res)
        return None, None

# ==========================================
# 2. 기상청 단기예보 데이터 가져오기 (dict로 반환)
# ==========================================
def get_kma_weather():
    url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
    now = datetime.datetime.now()
    base_date = now.strftime("%Y%m%d")
    base_time = "0500"

    params = {
        "serviceKey": DATA_GO_KR_KEY,
        "pageNo": "1",
        "numOfRows": "200",
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": NX,
        "ny": NY
    }

    data = {
        "date_str": now.strftime("%Y년 %m월 %d일"),
        "location": LOCATION_NAME,
        "temp_now": "24",
        "temp_high": "31",
        "temp_low": "22",
        "condition_text": "맑음",
        "condition_emoji": "☀️",
        "rain_chance": "10",
    }

    try:
        response = requests.get(url, params=params).json()
        items = response["response"]["body"]["items"]["item"]

        for item in items:
            category = item["category"]
            fcst_value = item["fcstValue"]
            if category == "TMP":
                data["temp_now"] = fcst_value
            elif category == "TMX":
                data["temp_high"] = int(float(fcst_value))
            elif category == "TMN":
                data["temp_low"] = int(float(fcst_value))
            elif category == "POP":
                data["rain_chance"] = fcst_value
            elif category == "SKY":
                sky_code = int(fcst_value)
                if sky_code == 1:
                    data["condition_text"] = "맑음"
                    data["condition_emoji"] = "☀️"
                elif sky_code == 3:
                    data["condition_text"] = "구름많음"
                    data["condition_emoji"] = "⛅"
                else:
                    data["condition_text"] = "흐림"
                    data["condition_emoji"] = "☁️"

        return data
    except Exception as e:
        print("기상청 API 오류 발생으로 기본 값으로 대체합니다:", e)
        return data

# ==========================================
# 3. 카카오톡용 문구 생성
# ==========================================
def build_kakao_text(w):
    return (
        f"{w['condition_emoji']} 좋은 아침입니다!\n\n📍 {w['location']}\n\n"
        f"현재 {w['temp_now']}℃\n최고 {w['temp_high']}℃\n최저 {w['temp_low']}℃\n\n"
        f"{w['condition_emoji']} {w['condition_text']}\n\n"
        f"🌂 강수확률 {w['rain_chance']}%\n\n즐거운 하루 보내세요!"
    )

# ==========================================
# 4. 오늘의 상세 날씨 페이지 생성 (예쁜 디자인 버전)
# ==========================================
def generate_weather_page(w):
    html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>오늘의 날씨 - {w['location']}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@400;600;700&family=Noto+Sans+KR:wght@400;500;700&display=swap');
  :root {{
    --sky-top: #6b8cbf; --sky-bottom: #a9c4e0;
    --ink: #1c2430; --paper: #fbfaf7; --muted: #6b7280; --accent: #e8a33d;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family:'Noto Sans KR',sans-serif; background:var(--paper); color:var(--ink); display:flex; justify-content:center; }}
  .page {{ width:100%; max-width:420px; min-height:100vh; background:var(--paper); }}
  .sky {{ position:relative; padding:32px 24px 40px; background:linear-gradient(180deg,var(--sky-top) 0%,var(--sky-bottom) 100%); overflow:hidden; border-radius:0 0 32px 32px; }}
  .sky::before {{ content:""; position:absolute; top:-60px; right:-40px; width:220px; height:220px; background:radial-gradient(circle,rgba(255,255,255,0.35) 0%,rgba(255,255,255,0) 70%); border-radius:50%; }}
  .date {{ font-size:13px; letter-spacing:0.04em; color:rgba(255,255,255,0.85); font-weight:500; }}
  .location {{ font-family:'Noto Serif KR',serif; font-size:22px; font-weight:600; color:white; margin-top:4px; }}
  .temp-row {{ display:flex; align-items:flex-end; gap:14px; margin-top:28px; }}
  .temp-now {{ font-family:'Noto Serif KR',serif; font-size:76px; font-weight:700; color:white; line-height:1; letter-spacing:-0.02em; }}
  .temp-meta {{ padding-bottom:10px; }}
  .condition {{ font-size:16px; color:white; font-weight:500; }}
  .hilo {{ font-size:13px; color:rgba(255,255,255,0.8); margin-top:2px; }}
  .body-content {{ padding:24px 24px 40px; }}
  .stat-card {{ background:white; border:1px solid #eee6d8; border-radius:14px; padding:18px; text-align:center; margin-bottom:28px; }}
  .stat-label {{ font-size:12px; color:var(--muted); margin-bottom:8px; letter-spacing:0.04em; }}
  .stat-value {{ font-family:'Noto Serif KR',serif; font-size:28px; font-weight:700; color:#c96b3f; }}
  .footer-note {{ text-align:center; font-size:11px; color:#b7b0a0; margin-top:12px; }}
</style>
</head>
<body>
<div class="page">
  <div class="sky">
    <div class="date">{w['date_str']}</div>
    <div class="location">📍 {w['location']}</div>
    <div class="temp-row">
      <div class="temp-now">{w['temp_now']}°</div>
      <div class="temp-meta">
        <div class="condition">{w['condition_emoji']} {w['condition_text']}</div>
        <div class="hilo">최고 {w['temp_high']}° · 최저 {w['temp_low']}°</div>
      </div>
    </div>
  </div>
  <div class="body-content">
    <div class="stat-card">
      <div class="stat-label">오늘의 강수확률</div>
      <div class="stat-value">{w['rain_chance']}%</div>
    </div>
    <div class="footer-note">매일 아침 자동으로 업데이트되는 날씨 페이지입니다</div>
  </div>
</div>
</body>
</html>"""

    os.makedirs("docs", exist_ok=True)

    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    date_key = datetime.datetime.now().strftime("%Y-%m-%d")
    os.makedirs("docs/archive", exist_ok=True)
    with open(f"docs/archive/{date_key}.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print("📄 오늘의 날씨 페이지 생성 완료!")

# ==========================================
# 5. 카카오톡 '나에게 보내기' 함수
# ==========================================
def send_kakao_me(text, access_token):
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": f"Bearer {access_token}"}

    template_object = {
        "object_type": "text",
        "text": text,
        "link": {
            "web_url": PAGE_URL,
            "mobile_web_url": PAGE_URL
        },
        "button_title": "자세히 보기"
    }

    payload = {"template_object": json.dumps(template_object, ensure_ascii=False)}
    res = requests.post(url, headers=headers, data=payload)
    if res.status_code == 200:
        print("🎉 카카오톡 메시지 전송 성공!")
    else:
        print(f"❌ 전송 실패: {res.text}")

# ==========================================
# 🔄 실행 메인 루틴 (최초 1회 토큰 발급용 - 임시, 이번 한 번만 실행)
# ==========================================
def job():
    auth_code = "SbZDnxsCfSRV-G0LgPKGfXNHmxWFWhF5lkIdef5YnyIw3pzk1BIgCQAAAAQKDRlTAAABn1uExkHMISgqRbFCUQ"

    rest_key = os.environ.get("KAKAO_REST_KEY")
    client_secret = os.environ.get("KAKAO_CLIENT_SECRET")

    print("🔑 새 앱의 비밀 코드로 최초 토큰 세트 발급을 요청합니다...")
    url = "https://kauth.kakao.com/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": rest_key,
        "client_secret": client_secret,
        "redirect_uri": "http://localhost:3000",
        "code": auth_code
    }
    res = requests.post(url, data=payload).json()

    access_token = res.get("access_token")
    refresh_token = res.get("refresh_token")

    if access_token and refresh_token:
        update_tokens_to_firebase(access_token, refresh_token)
        print("🎉 [대성공] 최초 토큰 충전 완료!")
        weather_data = get_kma_weather()
        generate_weather_page(weather_data)
        kakao_text = build_kakao_text(weather_data)
        send_kakao_me(kakao_text, access_token)
    else:
        print("❌ 토큰 발급 실패:", res)

job()
