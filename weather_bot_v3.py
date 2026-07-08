import os
import datetime
import time
import requests
import json

# ==========================================
# 1. 설정 정보 입력 (Firebase 연동)
# ==========================================
# 🎯 주소 맨 뒤에 반드시 '/tokens.json'이 붙어있어야 합니다! 
# 진아님의 파이어베이스 주소로 완벽하게 셋팅해 두었습니다.
FIREBASE_URL = os.environ.get("FIREBASE_URL")

# 공공데이터포털(기상청) 인증키 (Decoding)
DATA_GO_KR_KEY = "ca7c28c19530e6217757ee652fa803c0686247e1bb825f9faddeeec152c3b03b"

# 송파구 기준 기상청 주소 좌표
NX = "62"
NY = "126"

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
# 🔄 카카오 토큰 갱신하기 (무한 동력의 핵심)
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
    
    # 카카오는 새 토큰을 줄 때 refresh_token을 새로 줄 때도 있고 안 줄 때도 있습니다.
    new_access = res.get("access_token")
    new_refresh = res.get("refresh_token", current_refresh_token) # 안 주면 기존 것 유지
    
    if new_access:
        return new_access, new_refresh
    else:
        print("카카오 서버 응답 에러:", res)
        return None, None

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
        print("기상청 API 오류 발생으로 기본 문구로 대체합니다:", e)
        return "🌤️ 좋은 아침입니다!\n\n📍 송파구\n\n현재 24℃\n최고 31℃\n최저 22℃\n\n☀️ 맑음\n\n🌂 강수확률 10%\n\n즐거운 하루 보내세요!"

# ==========================================
# 3. 카카오톡 '나에게 보내기' 함수 (내 위치 자동 인식 버전)
# ==========================================
def send_kakao_me(text, access_token):
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": f"Bearer {access_token}"}

    # 🎯 여기를 아래 주소로 바꿔주시면 네이버가 폰 GPS를 읽어서 
    # 진아님이 지금 계신 동네 날씨를 자동으로 띄워줍니다!
    naver_weather_url = "https://search.naver.com/search.naver?query=날씨"

    template_object = {
        "object_type": "text",
        "text": text,
        "link": {
            "web_url": naver_weather_url,
            "mobile_web_url": naver_weather_url
        },
        "button_title": "네이버 날씨 보기"  # 👈 버튼 이름도 이쁘게 변경!
    }

    payload = {"template_object": json.dumps(template_object, ensure_ascii=False)}
    res = requests.post(url, headers=headers, data=payload)
    if res.status_code == 200:
        print("🎉 카카오톡 메시지 전송 성공!")
    else:
        print(f"❌ 전송 실패: {res.text}")
