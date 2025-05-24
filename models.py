from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime
from sqlalchemy import Enum  # Add this line
from flask_login import UserMixin
from extensions import db, bcrypt
import json


# -------------------------------
# 🔹 DOCTOR-PATIENT RELATIONSHIP (Many-to-Many)
# -------------------------------
doctor_patient = db.Table(
    'doctor_patient',
    db.Column('doctor_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('patient_id', db.Integer, db.ForeignKey('users.id'))
)

# -------------------------------
# 🔹 USER MODEL (Patients & Doctors)
# -------------------------------
# models.py
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), nullable=False, default='patient')  # 'patient' or 'doctor'
    specialization = db.Column(db.String(50))  # Only for doctors
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    
    # Relationships
    questions_asked = db.relationship('Question', backref='patient', lazy=True, foreign_keys='Question.patient_id')
    questions_answered = db.relationship('Question', backref='doctor', lazy=True, foreign_keys='Question.doctor_id')
    appointments_patient = db.relationship('Appointment', backref='patient', lazy=True, foreign_keys='Appointment.patient_id')
    appointments_doctor = db.relationship('Appointment', backref='doctor', lazy=True, foreign_keys='Appointment.doctor_id')

    def __init__(self, username, email, password, role='patient', specialization=None):
        self.username = username
        self.email = email
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        self.role = role
        self.specialization = specialization

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    # ✅ Convert User Object to Dictionary (for JSON responses)
    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "specialization": self.specialization,
            "created_at": self.created_at
        }

    @property
    def is_active(self):
        return True

    def get_id(self):
        return str(self.id)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

#---------------------------
#   Consult to a doctor
#---------------------------

class Consultation(db.Model):
    __tablename__ = 'consultations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    problem_description = db.Column(db.Text, nullable=False)
    specialization = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='pending')  # pending, answered
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, user_id, problem_description, specialization, status='pending'):
        self.user_id = user_id
        self.problem_description = problem_description
        self.specialization = specialization
        self.status = status


# -------------------------------
# 🔹 CHAT HISTORY MODEL (User Conversations)
# -------------------------------
class ChatHistory(db.Model):
    __tablename__ = "chat_history"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ✅ Convert ChatHistory Object to Dictionary
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "message": self.message,
            "response": self.response,
            "created_at": self.created_at
        }

# -------------------------------
# 🔹 MEDICAL REPORT MODEL (User Health Reports)
# -------------------------------
class MedicalReport(db.Model):
    __tablename__ = "medical_reports"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    report_name = db.Column(db.String(100), nullable=False)
    diagnosis = db.Column(db.Text, nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="SET NULL"), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # ✅ Convert MedicalReport Object to Dictionary
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "report_name": self.report_name,
            "diagnosis": self.diagnosis,
            "doctor_id": self.doctor_id,
            "timestamp": self.timestamp
        }

# -------------------------------
# 🔹 QUESTION MODEL (User Queries for Doctors)
# -------------------------------
class Question(db.Model):
    __tablename__ = 'questions'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    specialization = db.Column(db.String(50), nullable=False)
    urgent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    answered = db.Column(db.Boolean, default=False)
    answered_at = db.Column(db.DateTime)
    answer = db.Column(db.Text)
    
    # Foreign Keys
    patient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # ✅ Convert Question Object to Dictionary
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "specialization": self.specialization,
            "urgent": self.urgent,
            "created_at": self.created_at,
            "answered": self.answered,
            "answered_at": self.answered_at,
            "answer": self.answer
        }

# -------------------------------
# 🔹 APPOINTMENT MODEL (Patient-Doctor Meeting)
# -------------------------------
class Appointment(db.Model):
    __tablename__ = 'appointments'
    
    id = db.Column(db.Integer, primary_key=True)
    appointment_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign Keys
    patient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # ✅ Convert Appointment Object to Dictionary
    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "appointment_date": self.appointment_date,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class Conversation(db.Model):
    __tablename__ = 'conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    language = db.Column(db.String(20), default='en')  # Language of conversation (en, hi, etc.)
    context_data = db.Column(db.Text)  # JSON-encoded context data
    
    # Relationships
    user = db.relationship('User', backref=db.backref('conversations', lazy=True))
    messages = db.relationship('ChatMessage', backref='conversation', lazy=True,
                             cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "language": self.language,
            "context_data": self.context_data
        }
    
    def get_context(self):
        """Get the parsed context data"""
        if not self.context_data:
            return {}
        try:
            return json.loads(self.context_data)
        except:
            return {}
    
    def update_context(self, new_data):
        """Update the context data with new information"""
        context = self.get_context()
        context.update(new_data)
        self.context_data = json.dumps(context)
        self.last_updated = datetime.utcnow()
        return context

class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.String(50), db.ForeignKey('conversations.conversation_id', ondelete='CASCADE'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_bot = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # For user messages
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Message metadata
    language = db.Column(db.String(20), nullable=True)  # Language detected in message
    intent = db.Column(db.String(100), nullable=True)   # Detected intent
    entities = db.Column(db.Text, nullable=True)        # JSON string of detected entities
    
    # Relationships
    user = db.relationship('User', backref=db.backref('chat_messages', lazy=True))
    
    def to_dict(self):
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "content": self.content,
            "is_bot": self.is_bot,
            "created_at": self.created_at.isoformat(),
            "user_id": self.user_id,
            "language": self.language,
            "intent": self.intent,
            "entities": self.entities
        }
        
    def get_entities(self):
        """Get the parsed entities from the message"""
        if not self.entities:
            return []
        try:
            return json.loads(self.entities)
        except:
            return []
