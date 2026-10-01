from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    course = db.Column(db.String(100), nullable=True)
    location = db.Column(db.String(100), nullable=True)
    supervisor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_approved = db.Column(db.Boolean, default=False)
    reset_token = db.Column(db.String(100), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)

    students = db.relationship('User', backref=db.backref('supervisor', remote_side=[id]), lazy=True, foreign_keys=[supervisor_id])

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"

    @name.setter
    def name(self, value):
        if value and ' ' in value:
            parts = value.strip().split(' ', 1)
            self.first_name = parts[0]
            self.last_name = parts[1]
        else:
            self.first_name = value
            self.last_name = ''

    @property
    def student(self):
        return self

    @property
    def email_prefix(self):
        return self.email.split('@')[0] if self.email else ''

    def set_password(self, password_text):
        self.password = generate_password_hash(password_text)

    def check_password(self, password_text):
        return check_password_hash(self.password, password_text)

class HoursLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    student = db.relationship('User', foreign_keys=[student_id], backref='hour_logs')
    task_description = db.Column(db.String(200), nullable=True)
    location = db.Column(db.String(100), nullable=True)
    clock_in_time = db.Column(db.DateTime, nullable=False)
    clock_out_time = db.Column(db.DateTime, nullable=True)
    total_hours = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default='pending')
    rejection_comment = db.Column(db.String(300))