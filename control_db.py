from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, UniqueConstraint

db = SQLAlchemy()

class UserPrompt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False, unique=True)  # 1:1 관계
    prompt_text = db.Column(db.Text, nullable=False)


class UserCaption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False)
    caption_id = db.Column(db.String(100), nullable=False)
    caption = db.Column(db.Text, nullable=False)
    rate = db.Column(db.Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint('user_id', 'caption_id', name='uc_user_caption'), # user_id와 caption_id의 조합이 유일해야 함
        CheckConstraint('rate IN (-1, 0, 1)', name='valid_rate_check'),
    )
def init_db(app): # DB 초기화
    db.init_app(app)
    with app.app_context():
        db.create_all()
