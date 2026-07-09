from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# 비밀 금고에서 파이어베이스 주소 가져오기
FIREBASE_URL = os.environ.get("FIREBASE_URL")
FIREBASE_USERS_URL = FIREBASE_URL.replace("tokens.json", "users.json") if FIREBASE_URL else ""

@app.route('/api/register', methods=['POST'])
def register_user():
    # 카카오톡 챗봇이 보낸 데이터 세트 열기
    req = request.get_json()
    
    # 👤 사용자의 카카오 고유 ID와 💬 입력한 글자(동네) 추출
    user_id = req.get("userRequest", {}).get("user", {}).get("id", "unknown_user")
    utterance = req.get("userRequest", {}).get("utterance", "").strip()
    
    # 사용자가 입력한 동네 이름 (예: "송파구")
    location = utterance
    
    # 🎯 [임시 세팅] 주소에 따른 기상청 좌표 매칭 (나중에 주소 API로 자동화할 부분!)
    nx, ny = "62", "126" # 기본값 송파
    if "강남" in location: nx, ny = "61", "126"
    elif "해운대" in location or "부산" in location: nx, ny = "97", "75"
    
    # 파이어베이스 데이터베이스에 저장할 유저 정보 조립
    user_data = {
        "name": f"구독자_{user_id[:4]}", # 보안을 위해 카카오 ID 앞 4글자로 이름 임시 부여
        "location": location,
        "nx": nx,
        "ny": ny
    }
    
    try:
        # 파이어베이스의 users/카카오고유ID 자리에 저장!
        requests.put(f"{FIREBASE_USERS_URL.replace('.json', '')}/{user_id}.json", json=user_data)
        res_text = f"📍 [{location}] 등록이 완료되었습니다!\n\n내일 아침부터 매일 지정된 시간에 맞춤 날씨 정보를 배달해 드릴게요. 🤖🌤️"
    except Exception as e:
        print("파이어베이스 저장 에러:", e)
        res_text = "앗, 동네를 등록하는 중에 메모장 오류가 발생했어요. 잠시 후 다시 입력해 주세요! 😭"

    # 💬 카카오톡 챗봇 전용 답변 양식으로 포장해서 돌려보내기
    response = {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "simpleText": {
                        "text": res_text
                    }
                }
            ]
        }
    }
    return jsonify(response)

if __name__ == '__main__':
    # 외부 컴퓨터들이 접속할 수 있도록 포트 개방
    app.run(host='0.0.0.0', port=5000)
