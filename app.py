from flask import Flask, request, jsonify
from openai import OpenAI
import re
from konlpy.tag import Okt

app = Flask(__name__)

client = OpenAI(api_key="OPEN_AI_KEY")
okt = Okt()

# 프롬프트 설정
first_comment_prompt = """
역할(Role):

당신은 사용자의 사진일기를 작성하기 위해 필요한 정보를 수집하는 대화형 어시스턴트입니다.
목표(Goal):

사용자가 제공한 사진을 보고 대화를 유도하여 필요한 정보를 수집합니다.

지시사항(Instructions):
- 사용자가 제공한 사진을 보고, 그 사진에 대한 첫 인사를 작성하세요.
- 사용자가 제공한 사진을 보고, 그 사진에 대해 추측하여 대화를 유도하세요.
- 배경사진이라면 주로 어떤 장소인지 음식사진이라면 어떤 음식인지에 대해 추측하고 물어보세요.

출력 형식(Output Format):
"안녕하세요! 이 사진은 [장소/음식]에서 찍힌 것 같아요. [장소/음식]에 대해 더 이야기해 주실 수 있나요?"
"""
text_prompt = """
역할(Role):
당신은 사용자의 사진일기를 작성하기 위해 필요한 정보를 수집하는 대화형 어시스턴트입니다.

목표(Goal):
사용자가 제공한 사진에 대한 일기를 작성하기 위해 필수 정보를 수집합니다.

지시사항(Instructions):

- 사용자에게 다음의 필수 정보를 질문하여 수집하세요:

    1. 사진이 촬영된 시간대(대략적으로 아침 오후 저녁 어떤 것인지)

    2. 사진이 촬영된 장소, 배경

    3. 이 때 누구와 함께 하였는지

    4. 이 때 기분은 어땠는지

    5. 어떤 일이 있었는지

- 너는 위의 6가지 정보를 얻기 위해 자연스럽게 대화를 유도하고, 필요한 정보가 빠졌다면 추가로 질문해야 해.
- 이때 너는 단도 직입적으로 묻지말고 자연스럽게 대화를 하며 위의 정보를 알아낼 수 있도록 친근하게 물어봐야해.
- 사용자의 입력이 사진과 관련이 없거나 일기 작성과 무관한 경우, 다음과 같이 정중하게 안내하세요:
"죄송하지만, 이 대화는 사진일기를 작성하기 위한 것입니다. 사진과 관련된 이야기로 다시 말씀해 주세요."

- 일기를 작성할만큼의 충분한 정보가 모인 경우, 다음과 같이 정중하게 안내하세요:
"감사합니다. 현재 정보로 이제 일기를 작성할 수 있을 것 같아요! 혹시 알려주실 정보가 더 있나요?"

- 사용자의 감정이나 기분을 네가 임의로 추측하지 마.
- 사용자의 답변을 왜곡하지마
- 사용자의 답변에 의구심을 품지마

출력 형식(Output Format):

질문 기회는 3번밖에 없으므로 너는 이 질문에 대한 답을 알아내도록 압축해서 보내야할거야.
사용자가 질문에 압박을 느끼지 않도록 한번에 너무 많은 질문을 한번에 하지마.
"""
img_prompt = """
역할(Role):
당신은 사용자의 사진일기를 대신 작성하는 어시스턴트입니다.

목표(Goal):
사용자가 제공한 사진과 대화에서 수집한 정보를 바탕으로 자연스럽고 일상적인 느낌의 일기를 작성합니다.

지시사항(Instructions):

- 수집한 정보를 기반으로 일기를 작성하되, 사용자의 감정이나 기분을 추측하지 마세요.

- 사용자가 제공하지 않은 정보를 임의로 추가하지 마세요.

- 일기는 자연스럽고 일상적인 말투로 작성하세요.

- 비속어나 검열은 하지 않아도 괜찮지만, 일기의 흐름에 맞게 자연스럽게 표현하세요.

- 일기의 내용 외에는 추가하지 마세요.(해석, 주석, 부연 설명 없이 순수한 일기 형태로 작성)

출력 형식(Output Format):
자연스럽고 일상적인 말투로 작성된 일기를 제공합니다.
일기의 내용 외에는 출력하지 마세요.(해석, 주석, 부연 설명 없이 순수한 일기 형태로 출력하세요)
"""

# 불용어 제거 
def tokenization_stopwords(user_input):

    cleaned_text = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', user_input)
    tokens = [word for word, pos in okt.pos(cleaned_text, stem=True)
              if pos not in ['Josa', 'Punctuation', 'Suffix']]

    return ' '.join(tokens)


# ✅ 첫 코멘트 (이미지 추론)
@app.route('/upload_image', methods=['POST'])
def upload_image():
    data = request.json
    history = data.get('history')
    img_url = data.get('img_url')
    iter = data.get('iter', 1)  # 기본값을 0으로 설정

    if not history or img_url is None:
        return jsonify({"error": "history with img_url is required"}), 400
    


    messages = [
        {"role": "user", "content": first_comment_prompt},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": img_url, "detail": "low"}}
            ]
        }
    ]

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages
    )

    gpt_msg = response.choices[0].message.content.strip()

    # user 응답 추가
    history["user"].append(first_comment_prompt)

    # assistant 응답만 추가
    history["assistant"].append(gpt_msg)



    # ✅ message와 img_url은 공백으로 초기화하여 반환
    return jsonify({
        "message": "",
        "iter": iter,
        "img_url": img_url,
        "history": history
    })

# ✅ 유저 대화 처리
@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.json
    user_message = data.get('message')
    history = data.get('history')
    img_url = data.get('img_url')
    iter = data.get('iter')

    if not history or img_url is None:
        return jsonify({"error": "history with img_url is required"}), 400

    if not user_message or not history:
        return jsonify({"error": "message and history are required"}), 400

    messages = [{"role": "user", "content": text_prompt}]

    for user_msg, assistant_msg in zip(history.get("user", []), history.get("assistant", [])):
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": assistant_msg})

    processed_input = tokenization_stopwords(user_message)
    messages.append({"role": "user", "content": processed_input})

    # GPT에게 응답 받기
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages
    )

    gpt_response = response.choices[0].message.content.strip()

    # user 응답 추가
    history["user"].append(processed_input)

    # assistant 응답 추가 (GPT 답변)
    history["assistant"].append(gpt_response)

    # iter 증가
    iter += 1

    # 총 3번의 대화 후 종료 메시지 추가
    if iter > 3:
        end_message = "\n 대화가 종료되었습니다. 이제 일기를 생성할게요!\n"
        history["assistant"].append(end_message)

    # ✅ message는 공백으로 초기화하여 반환
    return jsonify({
        "message": "",
        "iter": iter,
        "img_url": img_url,
        "history": history
    })

# ✅ 그림일기 생성 (이미지 url 사용)
@app.route('/generate_diary', methods=['POST'])
def generate_diary():
    data = request.json
    history = data.get('history')
    img_url = data.get('img_url')

    if not history or img_url is None:
        return jsonify({"error": "history with img_url is required"}), 400

    

    messages = [{"role": "user", "content": img_prompt}]



    for user_msg, assistant_msg in zip(history.get("user", []), history.get("assistant", [])):
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": assistant_msg})

    messages.append({
        "role": "user",
        "content": [
            {"type": "text", "text": f"{img_prompt}"},
            {"type": "image_url", "image_url": {"url": img_url, "detail": "high"}}
        ]
    })

    response = client.chat.completions.create(
        model="ft:gpt-4o-2024-08-06:personal:capstone150img:BMxNfNjK",
        messages=messages
    )

    diary_text = response.choices[0].message.content.strip()

    # 일기만 포함된 응답만 보내기
    return jsonify({"diary": diary_text})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)