import os
import datetime
import requests
import json

# ==========================================
# 1. 설정 정보 입력 (Firebase 및 깃허브 주소)
# ==========================================
# Firebase Realtime DB URL (토큰 저장용 메모장)
FIREBASE_URL = os.environ.get("FIREBASE_URL")

# 깃허브 Pages에 올릴 운세 상세 페이지 주소 (상세페이지 파일명을 fortune.html로 가정)
PAGE_URL = "https://choisrii-debug.github.io/daily-weather-bot/fortune.html"

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
# 🔄 카카오 토큰 갱신하기 (하루 1번 자동 갱신)
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
# 🔮 오늘의 운세 알림 카톡 문구 제작
# ==========================================
def build_kakao_text():
    today_str = datetime.datetime.now().strftime("%Y년 %m월 %d일")
    return (
        f"🔮 {today_str} 오늘의 운세 배송 완료!\n\n"
        f"오늘 나에게 어떤 특별한 행운이 찾아올까요?\n"
        f"재물운을 높여줄 럭키 아이템과 띠별 운세를 지금 바로 확인해보세요! ✨"
    )

# ==========================================
# ✉️ 카카오톡 '나에게 보내기' 함수
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
        "button_title": "오늘의 운세 보기"
    }

    payload = {"template_object": json.dumps(template_object, ensure_ascii=False)}
    res = requests.post(url, headers=headers, data=payload)
    if res.status_code == 200:
        print("🎉 운세 카카오톡 메시지 전송 성공!")
    else:
        print(f"❌ 전송 실패: {res.text}")

# ==========================================
# 🔄 실행 메인 루틴 (매일 자동 실행용)
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

    # 1. 운세 카톡 문구 생성 ➡️ 2. 카톡 발송 (링크 포함)
    kakao_text = build_kakao_text()
    send_kakao_me(kakao_text, new_access)

job()
