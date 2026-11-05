from flask import Flask
from models import db
from extensions import mail
from flask_login import LoginManager
from models import User
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'hourtrack_unizulu_2026')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///site.db'
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'nomcebosandisiwe5@gmail.com'
app.config['MAIL_PASSWORD'] = 'cpgfrllwgsejdkez'
app.config['MAIL_DEFAULT_SENDER'] = 'nomcebosandisiwe5@gmail.com'

mail.init_app(app)
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

from routes import *

with app.app_context():
        db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)