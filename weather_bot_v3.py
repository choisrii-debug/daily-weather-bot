import os
import datetime
import time
import requests
import json

# ==========================================
# 1. 설정 정보 입력 (Firebase 연동)
# ==========================================
FIREBASE_URL = os.environ.get("FIREBASE_URL")

# 공공데이터포털(기상청/환경공단) 인증키 - 계정당 공통 사용
DATA_GO_KR_KEY = "ca7c28c19530e6217757ee652fa803c0686247e1bb825f9faddeeec152c3b03b"

# 송파구 기준 좌표/지역코드 모음
NX = "62"
NY = "126"
LOCATION_NAME = "송파구"
MID_REG_ID = "11B10101"        # 중기예보(육상/기온) 지역코드 - 서울/인천/경기
UV_AREA_NO = "1171000000"      # 자외선지수 지역코드 - 송파구
DUST_STATION_NAME = "송파구"    # 미세먼지 측정소명

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
# 🕐 기상청 발표시각 계산 (공통 유틸)
# ==========================================
def get_latest_announce_time(fmt12=True):
    """기상청은 06시, 18시 하루 2번 발표. 지금 기준 가장 최근 발표시각을 계산."""
    now = datetime.datetime.now()
    if now.hour >= 18:
        base = now.replace(hour=18, minute=0, second=0, microsecond=0)
    elif now.hour >= 6:
        base = now.replace(hour=6, minute=0, second=0, microsecond=0)
    else:
        # 새벽 0~5시대는 전날 18시 발표가 최신
        base = (now - datetime.timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)

    if fmt12:
        return base.strftime("%Y%m%d%H") + "00"   # 12자리 (예: 202607141800)
    else:
        return base.strftime("%Y%m%d%H")           # 10자리 (예: 2026071418)

# ==========================================
# 2. 기상청 단기예보 데이터 가져오기 (오늘 기온/날씨/강수확률)
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
        "hourly": []   # 시간대별 예보 (아침/낮/오후3시/저녁)
    }

    try:
        response = requests.get(url, params=params).json()
        items = response["response"]["body"]["items"]["item"]

        # 시간대별 데이터를 임시로 모으기 위한 딕셔너리
        hourly_raw = {}

        for item in items:
            category = item["category"]
            fcst_time = item["fcstTime"]   # 예: "0900", "1500"
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

            # 시간대별 기온/하늘상태 모으기 (아침9시, 낮12시, 오후3시, 저녁18시)
            if fcst_time in ["0900", "1200", "1500", "1800"]:
                hourly_raw.setdefault(fcst_time, {})
                if category == "TMP":
                    hourly_raw[fcst_time]["temp"] = fcst_value
                elif category == "SKY":
                    hourly_raw[fcst_time]["sky"] = int(fcst_value)
                elif category == "PTY":
                    hourly_raw[fcst_time]["pty"] = int(fcst_value)

        label_map = {"0900": "아침", "1200": "낮", "1500": "오후 3시", "1800": "저녁"}
        for t in ["0900", "1200", "1500", "1800"]:
            if t in hourly_raw:
                h = hourly_raw[t]
                pty = h.get("pty", 0)
                sky = h.get("sky", 1)
                if pty in [1, 2, 4]:
                    emoji = "🌧️"
                elif pty == 3:
                    emoji = "🌨️"
                elif sky == 1:
                    emoji = "☀️"
                elif sky == 3:
                    emoji = "⛅"
                else:
                    emoji = "☁️"
                data["hourly"].append({
                    "label": label_map[t],
                    "emoji": emoji,
                    "temp": h.get("temp", "-")
                })

        return data
    except Exception as e:
        print("기상청 단기예보 API 오류, 기본값으로 대체합니다:", e)
        return data

# ==========================================
# 2-1. 자외선지수 조회
# ==========================================
def get_uv_index():
    url = "http://apis.data.go.kr/1360000/LivingWthrIdxServiceV5/getUVIdxV5"
    time_str = get_latest_announce_time(fmt12=False)   # 10자리 (예: 2026071418)

    params = {
        "serviceKey": DATA_GO_KR_KEY,
        "pageNo": "1",
        "numOfRows": "10",
        "dataType": "XML",
        "areaNo": UV_AREA_NO,
        "time": time_str
    }

    try:
        response = requests.get(url, params=params)
        import xml.etree.ElementTree as ET
        root = ET.fromstring(response.content)
        item = root.find(".//item")

        # 낮시간대(9~15시) 중 최댓값을 오늘의 대표 자외선지수로 사용
        candidates = []
        for tag in ["h9", "h12", "h15"]:
            el = item.find(tag)
            if el is not None and el.text is not None:
                candidates.append(int(el.text))

        if not candidates:
            return {"uv_value": None, "uv_grade": "정보없음"}

        max_uv = max(candidates)

        if max_uv <= 2:
            grade = "낮음"
        elif max_uv <= 5:
            grade = "보통"
        elif max_uv <= 7:
            grade = "높음"
        elif max_uv <= 10:
            grade = "매우높음"
        else:
            grade = "위험"

        return {"uv_value": max_uv, "uv_grade": grade}
    except Exception as e:
        print("자외선지수 API 오류:", e)
        return {"uv_value": None, "uv_grade": "정보없음"}

# ==========================================
# 2-2. 미세먼지 조회
# ==========================================
def get_dust_info():
    url = "http://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"

    params = {
        "serviceKey": DATA_GO_KR_KEY,
        "sidoName": "서울",
        "pageNo": "1",
        "numOfRows": "100",
        "dataTerm": "DAILY",
        "ver": "1.3",
        "returnType": "json"
    }

    grade_map = {"1": "좋음", "2": "보통", "3": "나쁨", "4": "매우나쁨"}

    try:
        response = requests.get(url, params=params).json()
        items = response["response"]["body"]["items"]

        for item in items:
            if item.get("stationName") == DUST_STATION_NAME:
                return {
                    "pm10_value": item.get("pm10Value", "-"),
                    "pm10_grade": grade_map.get(item.get("pm10Grade"), "정보없음")
                }

        return {"pm10_value": "-", "pm10_grade": "정보없음"}
    except Exception as e:
        print("미세먼지 API 오류:", e)
        return {"pm10_value": "-", "pm10_grade": "정보없음"}

# ==========================================
# 2-3. 중기예보(이번 주) 조회
# ==========================================
def get_weekly_forecast():
    tm_fc = get_latest_announce_time(fmt12=True)   # 12자리 (예: 202607141800)
    weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
    result = []

    try:
        # 육상예보(하늘상태/강수확률)
        land_url = "http://apis.data.go.kr/1360000/MidFcstInfoService/getMidLandFcst"
        land_params = {
            "serviceKey": DATA_GO_KR_KEY, "pageNo": "1", "numOfRows": "10",
            "dataType": "JSON", "regId": MID_REG_ID, "tmFc": tm_fc
        }
        land_res = requests.get(land_url, params=land_params).json()
        land_item = land_res["response"]["body"]["items"]["item"][0]

        # 기온(최고/최저)
        ta_url = "http://apis.data.go.kr/1360000/MidFcstInfoService/getMidTa"
        ta_params = {
            "serviceKey": DATA_GO_KR_KEY, "pageNo": "1", "numOfRows": "10",
            "dataType": "JSON", "regId": MID_REG_ID, "tmFc": tm_fc
        }
        ta_res = requests.get(ta_url, params=ta_params).json()
        ta_item = ta_res["response"]["body"]["items"]["item"][0]

        today = datetime.datetime.now()

        # 3일 후 ~ 7일 후까지 5일치 (당일 포함 최대 10일치 중 앞부분만 사용)
        for day_offset in range(3, 8):
            target_date = today + datetime.timedelta(days=day_offset)
            weekday = weekday_names[target_date.weekday()]

            rain_am = land_item.get(f"rnSt{day_offset}Am")
            rain_pm = land_item.get(f"rnSt{day_offset}Pm")
            rain = rain_am if rain_am is not None else rain_pm

            wf_am = land_item.get(f"wf{day_offset}Am")
            wf_pm = land_item.get(f"wf{day_offset}Pm")
            wf_text = wf_am if wf_am else wf_pm

            if wf_text and "비" in wf_text:
                emoji = "🌧️"
            elif wf_text and "눈" in wf_text:
                emoji = "🌨️"
            elif wf_text and "구름많음" in wf_text:
                emoji = "⛅"
            elif wf_text and "흐림" in wf_text:
                emoji = "☁️"
            else:
                emoji = "☀️"

            temp_max = ta_item.get(f"taMax{day_offset}", "-")

            result.append({
                "weekday": weekday,
                "emoji": emoji,
                "temp": temp_max,
                "rain_chance": rain if rain is not None else "-"
            })

        return result
    except Exception as e:
        print("중기예보 API 오류:", e)
        return []

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
# 4. 오늘의 상세 날씨 페이지 생성
# ==========================================
def generate_weather_page(w, uv, dust, weekly):

    # 시간대별 예보 HTML 조각
    hourly_html = ""
    for h in w.get("hourly", []):
        hourly_html += f"""
        <div class="timeline-item">
          <div class="t-label">{h['label']}</div>
          <div class="t-icon">{h['emoji']}</div>
          <div class="t-temp">{h['temp']}°</div>
        </div>"""

    # 주간예보 HTML 조각
    week_html = ""
    for d in weekly:
        week_html += f"""
        <div class="week-day">
          <div>{d['weekday']}</div>
          <div class="w-icon">{d['emoji']}</div>
          <div class="w-temp">{d['temp']}°</div>
        </div>"""

    # 오늘의 준비물 멘트 (강수확률 기반, 링크 없이 텍스트만)
    try:
        rain_val = int(w['rain_chance'])
    except (ValueError, TypeError):
        rain_val = 0

    if rain_val >= 50:
        tip_title = "☔ 오늘의 준비물"
        tip_text = "오후에 비 소식이 있어요. 외출 전에 우산 하나 챙겨두면 마음이 편할 거예요."
    elif dust.get("pm10_grade") in ["나쁨", "매우나쁨"]:
        tip_title = "😷 오늘의 준비물"
        tip_text = "미세먼지가 평소보다 안 좋아요. 마스크를 챙기고 환기는 짧게 하는 게 좋아요."
    elif uv.get("uv_grade") in ["높음", "매우높음", "위험"]:
        tip_title = "🧴 오늘의 준비물"
        tip_text = "자외선이 강한 날이에요. 선크림을 바르고 나가면 좋겠어요."
    else:
        tip_title = "🌤️ 오늘의 한마디"
        tip_text = "날씨가 무난해요. 편안한 하루 보내세요!"

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
  .stat-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:28px; }}
  .stat-card {{ background:white; border:1px solid #eee6d8; border-radius:14px; padding:14px 10px; text-align:center; }}
  .stat-label {{ font-size:11px; color:var(--muted); margin-bottom:6px; }}
  .stat-value {{ font-family:'Noto Serif KR',serif; font-size:18px; font-weight:600; }}
  .stat-value.warn {{ color:#c96b3f; }}
  .stat-value.good {{ color:#3f8f5f; }}
  .section-title {{ font-size:12px; letter-spacing:0.08em; color:var(--muted); text-transform:uppercase; margin-bottom:10px; font-weight:700; }}
  .timeline {{ display:flex; justify-content:space-between; background:white; border:1px solid #eee6d8; border-radius:14px; padding:18px 14px; margin-bottom:28px; }}
  .timeline-item {{ text-align:center; flex:1; }}
  .timeline-item .t-label {{ font-size:11px; color:var(--muted); margin-bottom:8px; }}
  .timeline-item .t-icon {{ font-size:20px; margin-bottom:6px; }}
  .timeline-item .t-temp {{ font-size:14px; font-weight:600; }}
  .week-strip {{ display:flex; justify-content:space-between; margin-bottom:28px; }}
  .week-day {{ text-align:center; font-size:11px; color:var(--muted); }}
  .week-day .w-icon {{ font-size:16px; margin:6px 0; }}
  .week-day .w-temp {{ font-size:12px; color:var(--ink); font-weight:500; }}
  .rec-card {{ background:linear-gradient(135deg,#fff8ec 0%,#fdf1de 100%); border:1px solid #f0dfc0; border-radius:16px; padding:20px; margin-bottom:20px; }}
  .rec-title {{ font-size:14px; font-weight:700; margin-bottom:6px; }}
  .rec-text {{ font-size:13px; color:#5c4a2f; line-height:1.6; }}
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

    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-label">강수확률</div>
        <div class="stat-value warn">{w['rain_chance']}%</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">미세먼지</div>
        <div class="stat-value good">{dust.get('pm10_grade', '정보없음')}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">자외선</div>
        <div class="stat-value warn">{uv.get('uv_grade', '정보없음')}</div>
      </div>
    </div>

    <div class="section-title">시간대별 예보</div>
    <div class="timeline">{hourly_html}
    </div>

    <div class="section-title">이번 주</div>
    <div class="week-strip">{week_html}
    </div>

    <div class="rec-card">
      <div class="rec-title">{tip_title}</div>
      <div class="rec-text">{tip_text}</div>
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
# 🔄 실행 메인 루틴 (매일 자동 갱신용)
# ==========================================
def job():
    db_tokens = get_tokens_from_firebase()
    if not db_tokens:
        print("❌ Firebase 메모장이 비어있거나 주소가 잘못되어 읽을 수 없습니다.")
        return

    rest_key = os.environ.get("KAKAO_REST_KEY")
    client_secret = os.environ.get("KAKAO_CLIENT_SECRET")

    print("🔄 Firebase 토큰을 사용해 카카오 토큰 갱신을 시도합니다...")
    new_access, new_refresh = refresh_kakao_token(rest_key, client_secret, db_tokens["refresh_token"])

    if not new_access:
        print("❌ 토큰 확보 실패로 작업을 중단합니다. 파이어베이스에 싱싱한 토큰이 들어있는지 확인해 주세요.")
        return

    update_tokens_to_firebase(new_access, new_refresh)

    # 데이터 조회 (오늘 날씨 → 자외선 → 미세먼지 → 주간예보) → 페이지 생성 → 카톡 발송
    weather_data = get_kma_weather()
    uv_data = get_uv_index()
    dust_data = get_dust_info()
    weekly_data = get_weekly_forecast()

    generate_weather_page(weather_data, uv_data, dust_data, weekly_data)
    kakao_text = build_kakao_text(weather_data)
    send_kakao_me(kakao_text, new_access)

job()
