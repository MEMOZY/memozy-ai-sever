from flask import Flask, request, jsonify
import gpt_api
import json

app = Flask(__name__)

@app.route('/user', methods=['POST']) # 백엔드와 소통, user 등록 
def register_user():
    data = request.json
    user_id = data.get('user_id')


    return jsonify({"message": f"user_id '{user_id}' 회원 등록 완료!"}), 200




@app.route('/image', methods=['POST']) # 백엔드와 소통, user가 업로드한 이미지를 gpt에게 전달하는 api
def upload_image():
    data = request.json
    user_id = data.get('user_id')
    caption_id = data.get('caption_id')
    history = data.get('history')
    img_url = data.get('img_url')
    iter = data.get('iter', 1)
    iter=1

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

@app.route('/message', methods=['POST']) # 백엔드와 소통, user가 업로드한 이미지에 대한 대화수행
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

@app.route('/diary', methods=['POST']) # 백엔드와 소통, user가 업로드한 이미지에 대한 일기 생성
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



@app.route('/improve', methods=['POST'])
def receive_diary():
    data = request.json

    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    diary_list = data.get("diary")
    if not diary_list or not isinstance(diary_list, list):
        return jsonify({"error": "diary must be a list"}), 400

    caption_ids = []
    captions = []
    for entry in diary_list:
        caption_id = entry.get("caption_id")
        caption = entry.get("caption")
        if not caption_id or not caption:
            return jsonify({"error": "Each diary entry must have caption_id and caption"}), 400
        caption_ids.append(caption_id)
        captions.append(caption)

    try:
        # ✅ GPT 개선 함수 호출
        improved_diaries = gpt_api.improve_diaries_with_gpt(captions)

        # ✅ 반환 형식 구성
        improved_diary_list = [
            {"caption_id": caption_ids[i], "caption": improved_diaries[i]}
            for i in range(len(caption_ids))
        ]

        return jsonify({
            "user_id": user_id,
            "diary": improved_diary_list
        }), 200

    except json.JSONDecodeError as e:
        return jsonify({"error": f"JSON parsing failed: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"GPT API error: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
