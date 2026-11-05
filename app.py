from flask import Flask
from models import db
from extensions import mail
from flask_login import LoginManager
from models import User
from flask_bcrypt import Bcrypt
import os

app = Flask(__name__)
bcrypt = Bcrypt(app)
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
    # AUTO-CREATE ADMIN - DO NOT DELETE YET
    try:
        admin_email = "nomcebosandisiwe5@gmail.com"
        existing = User.query.filter_by(email=admin_email).first()
        if not existing:
            admin_user = User(
                first_name="Nomcebo",
                last_name="Admin",
                email=admin_email,
                password_hash=bcrypt.generate_password_hash("Admin45").decode("utf-8"),
                role="admin",
                location="Durban",
                course="Admin"
            )
            db.session.add(admin_user)
            db.session.commit()
            print("ADMIN CREATED")
        else:
            existing.role = "admin"
            existing.password_hash = bcrypt.generate_password_hash("Admin45").decode("utf-8")
            db.session.commit()
            print("ADMIN UPDATED")
    except Exception as e:
        print("ADMIN SETUP ERROR:", e)       

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
