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
    
    # ✅ 먼저 GPT로 user_message가 '일기 관련 내용인지' 확인 아니라면 거절
    try:
        is_diary_related = gpt_api.check_diary_related(user_message)
        logging.info(f"✅ diary relevance: {is_diary_related}")
    except Exception as e:
        logging.error(f"❌ GPT relevance check error: {str(e)}")
        return jsonify({"error": "GPT relevance check failed"}), 500


    def event_stream():
        try:
            if not is_diary_related:
                # 🔴 일기 관련 내용이 아닌 경우: 사용자에게 경고 문구를 한 글자씩 스트리밍
                warning = "죄송합니다. 일기 작성과 관련된 내용만 도와드릴 수 있어요. 일기와 관련된 내용을 입력해 주세요."
   
                logging.info("⚠️ Non-diary message. Sending warning via stream (char by char).")
                for char in warning:
                    yield f"data: {char}\n\n"
                yield "event: done\ndata: [DONE]\n\n"
                return

            got_content = False

            for chunk in gpt_api.get_user_conversation_response(history, user_message):
                content = chunk
                if content:
                    logging.info(f"✅ FLASK SENDING: {content}")
                    yield f"data: {content}\n\n"
                    got_content = True

            if not got_content:
                logging.warning("⚠️ FLASK: no meaningful content, sending fallback")
                fallback = "죄송합니다, 답변을 생성하지 못했습니다."
                for char in fallback:
                    yield f"data: {char}\n\n"

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
    # print(data)###### 디버깅용, data가 잘 넘어오는지 확인
    session_id = data.get('session_id')
    img_url = data.get('img_url')
    history = data.get('history')
    past_diary = data.get('past_diary', [])  # 과거 일기 리스트. 없으면 빈 리스트로 처리

    if not session_id or not img_url or not history:
        return jsonify({"error": "session_id, img_url and history are required"}), 400
    if not history or img_url is None:
        return jsonify({"error": "history with img_url is required"}), 400
 
   # ✅ 과거 일기가 존재할 경우: 프롬프트로 구성
    past_diary_prompt = ""
    if past_diary and isinstance(past_diary, list) and any(past_diary):
        past_diary_prompt = "\n\n".join(
            f"- {diary}" for diary in past_diary if diary.strip()
        )
        past_diary_prompt = (
            "\n다음은 사용자가 과거에 작성한 일기들 입니다. 다음 일기들의 스타일, 말투, 형식 문체를 참고하여 작성하여 주세요. :\n\n"
            + past_diary_prompt
        )
    else:
        past_diary_prompt =None

    # ✅ GPT API 호출 (프롬프트 추가된 버전으로)
    diary_text= gpt_api.generate_diary(history=history, img_url=img_url, past_diary_prompt=past_diary_prompt)

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
