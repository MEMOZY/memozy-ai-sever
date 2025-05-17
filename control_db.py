from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class UserCaption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False)
    caption_id = db.Column(db.String(100), unique=True, nullable=False)
    caption = db.Column(db.Text, nullable=False)
    rate = db.Column(db.Float, nullable=True)

def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()
