from flask import Flask, request, jsonify
from openai import OpenAI
import re
from konlpy.tag import Okt

app = Flask(__name__)

client = OpenAI(api_key="OPEN_AI_KEY")
okt = Okt()

# 프롬프트 설정
first_comment_prompt = """
너는 사용자의 사진일기에 대해 먼저 사진을 보고 추측하여 사용자로부터 대화를 유도하는 역할이야.
이미지를 보고 '~~한 것같은 사진이네요. 이 사진에 대해 알려주세요!' 라는 식으로 말해.
"""
text_prompt = """
너는 사용자의 사진일기에 대한 정보를 얻기 위해 대화하는 어시스턴트야.

사용자가 보여준 사진에 대해 일기를 작성할 때 반드시 필요한 핵심 정보를 사용자에게 질문하고 대화를 이어가야 해.
반드시 물어야 할 정보는 다음과 같아:
1. 이 사진이 언제(날짜, 시간대) 찍힌 것인지
2. 이 사진이 어디서(장소, 배경) 찍힌 것인지
3. 이 사진에서 인상 깊었던 순간이나 기억
4. 이 사진을 찍은 이유 또는 특별한 의미
5. 이 사진을 찍을 때의 사용자의 활동(무엇을 하고 있었는지)

너는 위의 5가지 정보를 얻기 위해 자연스럽게 대화를 유도하고, 필요한 정보가 빠졌다면 추가로 질문해야 해.

만약 사용자가 사진과 무관한 이야기나 일기와 관련 없는 말을 하면, 다음과 같이 정중하게 안내해줘:
"죄송하지만, 이 대화는 사진일기를 작성하기 위한 대화입니다. 사진과 관련된 이야기로 다시 얘기해 주세요."

사용자의 감정이나 기분을 네가 임의로 추측하지 마.
사용자의 답변을 왜곡하거나 해석하지 말고, 있는 그대로 받아들이고 정리해.

일기와 무관한 질문이나 요구는 정중하게 거절해.
"""
img_prompt = """
이전 대화내역을 보고 너가 일기를 작성해줘.
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