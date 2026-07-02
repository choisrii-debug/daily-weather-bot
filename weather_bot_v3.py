import datetime
import time
import requests
import json
import os

# ==========================================
# 1. 설정 정보 입력
# ==========================================
# ⚠️ 중요: 토큰 정보들을 코드에 직접 적지 않고, 깃허브 환경변수(Secrets)에서 안전하게 읽어옵니다.
REST_API_KEY = os.environ.get("fb2fecd4c89647d97f5a759e448d00c8")
REFRESH_TOKEN = os.environ.get("LeMfbblIL2S3wZzqIEOyRwDK4hqT6CbQAAAAAQoXIS0AAAGfIzVq6h7SOb8w2j0_")

# 공공데이터포털(기상청) 인증키 (Decoding)
DATA_GO_KR_KEY = "ca7c28c19530e6217757ee652fa803c0686247e1bb825f9faddeeec152c3b03b"

# 송파구 기준 기상청 주소 좌표
NX = "62"
NY = "126"

# ==========================================
# 🔑 카카오 Refresh Token으로 새로운 Access Token 따오기
# ==========================================
def get_new_access_token():
    url = "https://kauth.kakao.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": REST_API_KEY,
        "refresh_token": REFRESH_TOKEN,
    }
    
    try:
        res = requests.post(url, data=payload).json()
        if "access_token" in res:
            print("✅ Refresh Token을 사용하여 새로운 Access Token 발급 성공!")
            return res["access_token"]
        else:
            print(f"❌ 토큰 갱신 실패: {res}")
            return None
    except Exception as e:
        print(f"토큰 갱신 중 오류 발생: {e}")
        return None

# ==========================================
# 2. 기상청 단기예보 데이터 가져오기
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

    try:
        response = requests.get(url, params=params).json()
        items = response["response"]["body"]["items"]["item"]

        current_temp, max_temp, min_temp, pop_rain = "24", "31", "22", "10"
        sky_status = "☀️ 맑음"

        for item in items:
            category = item["category"]
            fcst_value = item["fcstValue"]
            if category == "TMP": current_temp = fcst_value
            elif category == "TMX": max_temp = int(float(fcst_value))
            elif category == "TMN": min_temp = int(float(fcst_value))
            elif category == "POP": pop_rain = fcst_value
            elif category == "SKY":
                sky_code = int(fcst_value)
                if sky_code == 1: sky_status = "☀️ 맑음"
                elif sky_code == 3: sky_status = "⛅ 구름많음"
                else: sky_status = "☁️ 흐림"

        return (
            f"🌤️ 좋은 아침입니다!\n\n📍 송파구\n\n"
            f"현재 {current_temp}℃\n최고 {max_temp}℃\n최저 {min_temp}℃\n\n"
            f"{sky_status}\n\n🌂 강수확률 {pop_rain}%\n\n즐거운 하루 보내세요!"
        )
    except Exception as e:
        print("기상청 API 호출 오류:", e)
        return "🌤️ 좋은 아침입니다!\n\n📍 송파구\n\n현재 24℃\n최고 31℃\n최저 22℃\n\n☀️ 맑음\n\n🌂 강수확률 10%\n\n즐거운 하루 보내세요!"

# ==========================================
# 3. 카카오톡 '나에게 보내기' 함수
# ==========================================
def send_kakao_me(text):
    # 카카오 테스트 도구에서 발급받은 엄청 긴 그 액세스 토큰을 여기 따옴표 안에 직접 넣으세요!
    MY_ACCESS_TOKEN = "LeMfbblIL2S3wZzqIEOyRwDK4hqT6CbQAAAAAQoXIS0AAAGfIzVq6h7SOb8w2j0_" 
    
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": f"Bearer {MY_ACCESS_TOKEN}"}

    template_object = {
        "object_type": "text",
        "text": text,
        "link": {
            "web_url": "http://localhost",
            "mobile_web_url": "http://localhost"
        },
        "button_title": " " 
    }

    payload = {"template_object": json.dumps(template_object, ensure_ascii=False)}
    res = requests.post(url, headers=headers, data=payload)
    
    if res.status_code == 200:
        print("🎉 카카오톡 메시지 전송 성공!")
    else:
        print(f"❌ 전송 실패! 에러 코드: {res.status_code}, 내용: {res.text}")

def job():
    # 1. 깃허브 실행 시마다 자동으로 신규 Access Token 받아오기
    access_token = get_new_access_token()
    if not access_token:
        print("토큰 확보 실패로 작업을 중단합니다.")
        return
        
    # 2. 날씨 정보 가져오기
    weather_info = get_kma_weather()
    
    # 3. 메시지 전송
    send_kakao_me(weather_info, access_token)

# 즉시 실행
job()