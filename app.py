from flask import Flask, request, jsonify
import gpt_api
from difflib import SequenceMatcher

app = Flask(__name__)





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


 
    # ✅GPT API 호출
    diary_text = gpt_api.generate_diary(history, img_url)



    return jsonify({
        "diary": diary_text,
        "user_id": user_id,
        "caption_id": caption_id
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
