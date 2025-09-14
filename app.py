from flask import Flask, request, jsonify, Response, stream_with_context
import gpt_api
import json
import logging

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

@app.route('/user', methods=['POST']) # 백엔드와 소통, user 등록 
def register_user():
    data = request.json
    user_id = data.get('user_id')
    return jsonify({"message": f"user_id '{user_id}' 회원 등록 완료!"}), 200

@app.route('/image', methods=['POST'])
def upload_image_stream():
    data = request.json
    img_url = data.get('img_url')
    if not img_url:
        return jsonify({"error": "img_url is required"}), 400

    def event_stream():
        try:
            for partial in gpt_api.get_first_comment(img_url):
                logging.info(f"✅ /image yielding chunk: {partial}")
                yield f"data: {partial}\n\n"
            logging.info("✅ /image sending DONE")
            yield "event: done\ndata: [DONE]\n\n"
        except Exception as e:
            logging.error(f"❌ /image error: {str(e)}")
            yield f"event: error\ndata: {str(e)}\n\n"

    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")

@app.route('/message', methods=['POST'])  # ✅ 스트리밍
def send_message_stream():
    data = request.json
    history = data.get('history')
    user_message = data.get('message')
    logging.info(f"✅ FLASK RECEIVED history: {history}")
    logging.info(f"✅ FLASK RECEIVED user_message: {user_message}")
    
    if not history or not user_message:
        return jsonify({"error": "history and message are required"}), 400

    def event_stream():
        try:
            got_content = False  # 실질 content를 받았는지 플래그

            for chunk in gpt_api.get_user_conversation_response(history, user_message):
                content = chunk.strip()
                if content:
                    logging.info(f"✅ FLASK SENDING: {content}")
                    yield f"data: {content}\n\n"
                    got_content = True

            if not got_content:
                logging.warning("⚠️ FLASK: no meaningful content, sending fallback")
                yield f"data: 죄송합니다, 답변을 생성하지 못했습니다.\n\n"

            logging.info("✅ FLASK DONE SENDING")
            yield "event: done\ndata: [DONE]\n\n"

        except Exception as e:
            logging.error(f"❌ /message error: {str(e)}")
            yield f"event: error\ndata: {str(e)}\n\n"

    logging.info("✅ FLASK STREAMING STARTED")  # 🔥 요청 진입 로그
    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")

@app.route('/diary', methods=['POST']) # 백엔드와 소통, user가 업로드한 이미지에 대한 일기 생성
def generate_diary():
    data = request.json
    session_id = data.get('session_id')
    img_url = data.get('img_url')
    history = data.get('history')

    if not session_id or not img_url or not history:
        return jsonify({"error": "session_id, img_url and history are required"}), 400
    if not history or img_url is None:
        return jsonify({"error": "history with img_url is required"}), 400
 
    # ✅GPT API 호출
    diary_text = gpt_api.generate_diary(history, img_url)

    return jsonify({
        "diary": diary_text,
        "session_id": session_id,
    })


@app.route('/final-diary', methods=['POST'])
def receive_diary():
    data = request.json
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

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
            "session_id": session_id,
            "diary": improved_diary_list
        }), 200

    except Exception as e:
        print(f"⚠️ improve_diaries_with_gpt error: {e}")
        fallback_diary_list = [
            {"caption_id": caption_ids[i], "caption": captions[i]}
            for i in range(len(caption_ids))
        ]
        return jsonify({
            "session_id": session_id,
            "diary": fallback_diary_list,
            "warning": f"일기 개선시 오류가 발생하여 사용자의 원본 일기를 그대로 반환했습니다. Error: {str(e)}"
        }), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
