from flask import Flask, request, jsonify
from control_db import db, UserCaption, init_db
import gpt_api

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///user_diary.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
init_db(app)

@app.route('/add_caption', methods=['POST'])
def add_caption():
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

@app.route('/rate_caption', methods=['POST'])
def rate_caption():
    data = request.json
    user_id = data.get('user_id')
    caption_id = data.get('caption_id')
    rate = data.get('rate')

    if not user_id or not caption_id or rate is None:
        return jsonify({"error": "user_id, caption_id, and rate are required"}), 400

    caption_entry = UserCaption.query.filter_by(user_id=user_id, caption_id=caption_id).first()
    if not caption_entry:
        return jsonify({"error": "Caption not found for given user_id and caption_id"}), 404

    caption_entry.rate = rate
    db.session.commit()
    return jsonify({"message": "Rate updated successfully"})

@app.route('/get_user_captions', methods=['GET'])
def get_user_captions():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "user_id is required as query param"}), 400

    captions = UserCaption.query.filter_by(user_id=user_id).all()
    result = [{"caption_id": c.caption_id, "caption": c.caption, "rate": c.rate} for c in captions]
    return jsonify({"captions": result})

@app.route('/upload_image', methods=['POST'])
def upload_image():
    data = request.json
    history = data.get('history')
    img_url = data.get('img_url')
    iter = data.get('iter', 1)

    if not history or img_url is None:
        return jsonify({"error": "history with img_url is required"}), 400

    gpt_msg = gpt_api.get_first_comment(img_url)
    history["user"].append(gpt_api.first_comment_prompt)
    history["assistant"].append(gpt_msg)

    return jsonify({
        "message": "",
        "iter": iter,
        "img_url": img_url,
        "history": history
    })

@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.json
    user_message = data.get('message')
    history = data.get('history')
    img_url = data.get('img_url')
    iter = data.get('iter')

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
        "history": history
    })

@app.route('/generate_diary', methods=['POST'])
def generate_diary():
    data = request.json
    history = data.get('history')
    img_url = data.get('img_url')

    if not history or img_url is None:
        return jsonify({"error": "history with img_url is required"}), 400

    diary_text = gpt_api.generate_diary(history, img_url)
    return jsonify({"diary": diary_text})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
