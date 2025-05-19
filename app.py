from flask import Flask, request, jsonify
from control_db import db, UserPrompt, UserCaption, init_db
import gpt_api
from difflib import SequenceMatcher

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///user_diary.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
init_db(app)

@app.route('/add_caption', methods=['POST'])
def add_caption(): # db에 gpt가 생성한 caption을 저장(user의 일기 x)하는 api
    data = request.json
    user_id = data.get('user_id')
    caption_id = data.get('caption_id')
    caption = data.get('caption')

    if not user_id or not caption_id or not caption:
        return jsonify({"error": "user_id, caption_id, caption are required"}), 400

    if UserCaption.query.filter_by(caption_id=caption_id).first():
        return jsonify({"error": "caption_id already exists"}), 400

    new_entry = UserCaption(user_id=user_id, caption_id=caption_id, caption=caption)
    db.session.add(new_entry)
    db.session.commit()
    return jsonify({"message": "Caption added successfully"})


@app.route('/get_user_captions', methods=['GET']) # 강화학습시 user db에 저장된 caption을 가져오는 api
def get_user_captions():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "user_id is required as query param"}), 400

    captions = UserCaption.query.filter_by(user_id=user_id).all()
    result = [{"caption_id": c.caption_id, "caption": c.caption, "rate": c.rate} for c in captions]
    return jsonify({"captions": result})

@app.route('/register_user', methods=['POST']) # 백엔드와 소통, user 등록 
def register_user():
    data = request.json
    user_id = data.get('user_id')
    init_prompt = """
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
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    # 이미 등록된 유저인지 확인
    existing_user = UserPrompt.query.filter_by(user_id=user_id).first()
    if existing_user:
        return jsonify({"error": f"user_id '{user_id}' is already registered"}), 400

    # 새 유저 등록
    new_prompt = UserPrompt(user_id=user_id, prompt_text=init_prompt)
    db.session.add(new_prompt)
    db.session.commit()

    return jsonify({"message": f"user_id '{user_id}' registered successfully with default prompt"}), 200

@app.route('/upload_image', methods=['POST']) # 백엔드와 소통, user가 업로드한 이미지를 gpt에게 전달하는 api
def upload_image():
    data = request.json
    user_id = data.get('user_id')
    caption_id = data.get('caption_id')
    history = data.get('history')
    img_url = data.get('img_url')
    iter = data.get('iter', 1)

    if not user_id or not caption_id or not img_url:
        return jsonify({"error": "user_id, caption_id, and img_url are required"}), 400
    if not history or img_url is None:
        return jsonify({"error": "history with img_url is required"}), 400

    gpt_msg = gpt_api.get_first_comment(img_url)
    history["user"].append(gpt_api.first_comment_prompt)
    history["assistant"].append(gpt_msg)

    return jsonify({
        "message": "",
        "iter": iter,
        "img_url": img_url,
        "user_id": user_id,
        "caption_id": caption_id,
        "history": history
    })

@app.route('/send_message', methods=['POST']) # 백엔드와 소통, user가 업로드한 이미지에 대한 대화수행
def send_message():
    data = request.json
    user_id = data.get('user_id')
    caption_id = data.get('caption_id')
    user_message = data.get('message')
    history = data.get('history')
    img_url = data.get('img_url')
    iter = data.get('iter')

    if not user_id or not caption_id or not img_url or not user_message:
        return jsonify({"error": "user_id, caption_id, img_url, and message are required"}), 400
    if not history or img_url is None or not user_message:
        return jsonify({"error": "history, img_url and message are required"}), 400

    gpt_response = gpt_api.get_user_conversation_response(history, user_message)
    history["user"].append(gpt_api.tokenization_stopwords(user_message))
    history["assistant"].append(gpt_response)

    iter += 1

    if iter > 3:
        history["assistant"].append("\n 대화가 종료되었습니다. 이제 일기를 생성할게요!\n")

    return jsonify({
        "message": "",
        "iter": iter,
        "img_url": img_url,
        "user_id": user_id,
        "caption_id": caption_id,
        "history": history
    })

@app.route('/generate_diary', methods=['POST']) # 백엔드와 소통, user가 업로드한 이미지에 대한 일기 생성
def generate_diary():
    data = request.json
    user_id = data.get('user_id')
    caption_id = data.get('caption_id')
    img_url = data.get('img_url')
    history = data.get('history')

    if not user_id or not caption_id or not img_url or not history:
        return jsonify({"error": "user_id, caption_id, img_url and history are required"}), 400
    if not history or img_url is None:
        return jsonify({"error": "history with img_url is required"}), 400


    # ✅ 1. prompt_text 불러오기
    prompt_entry = UserPrompt.query.filter_by(user_id=user_id).first()
    if not prompt_entry:
        return jsonify({"error": "Prompt not found for this user"}), 404
    user_prompt = prompt_entry.prompt_text  # 사용자의 프롬프트
    # ✅ 2. GPT API 호출
    diary_text = gpt_api.generate_diary(history, img_url, user_prompt)




    new_entry = UserCaption( # user caption 테이블에 diary_text 저장
        user_id=user_id,
        caption_id=caption_id,
        caption=diary_text
    )
    db.session.add(new_entry)
    db.session.commit()
    return jsonify({
        "diary": diary_text,
        "user_id": user_id,
        "caption_id": caption_id
    })


@app.route('/rate_caption', methods=['POST'])  # 백엔드와 소통 user가 작성한 caption과 GPT caption을 비교하여 평가
def rate_caption():
    data = request.json
    user_id = data.get('user_id')
    caption_id = data.get('caption_id')
    user_caption = data.get('caption')

    if not user_id or not caption_id or not user_caption:
        return jsonify({"error": "user_id, caption_id, and caption are required"}), 400

    # DB에서 origin_caption 조회
    caption_entry = UserCaption.query.filter_by(user_id=user_id, caption_id=caption_id).first()
    if not caption_entry:
        return jsonify({"error": "Caption not found for given user_id and caption_id"}), 404

    origin_caption = caption_entry.caption

    # 유사도 계산 (SequenceMatcher)
    similarity = SequenceMatcher(None, user_caption.strip(), origin_caption.strip()).ratio()

    # 평가 기준
    if similarity > 0.8:
        rate = 1
    elif similarity > 0.5:
        rate = 0
    else:
        rate = -1

    # rate 저장
    caption_entry.rate = rate
    db.session.commit()

    return jsonify({
        "message": "Rate updated successfully based on similarity",
        "similarity": round(similarity, 3),
        "rate": rate
    })



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
