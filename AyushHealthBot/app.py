from flask import Flask, request, jsonify, render_template, redirect, url_for, make_response
import json
import pickle
import pandas as pd
from collections import Counter
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity, create_access_token, unset_jwt_cookies
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User
from routes.users import users
from routes.doctors import doctors
from routes.chatbot import chatbot
from auth import auth
from extensions import db, migrate, bcrypt
import os

# Initialize Flask App
app = Flask(__name__, static_folder="static")
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'database.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = '165355e390430405826e55bb78d646706a6b66d9749eefd5acd06abb568ddcf7'
app.config['JWT_SECRET_KEY'] = '165355e390430405826e55bb78d646706a6b66d9749eefd5acd06abb568ddcf7'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 3600  # Token expires in 1 hour
app.config['JWT_TOKEN_LOCATION'] = ['cookies']  # Store tokens in cookies
app.config['JWT_COOKIE_CSRF_PROTECT'] = False 
app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token'

# Initialize extensions
db.init_app(app)
migrate.init_app(app, db)
bcrypt.init_app(app)
jwt = JWTManager(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Load the saved ML model and related data
try:
    with open('model.pkl', 'rb') as f:
        knn_model = pickle.load(f)
        cv = pickle.load(f)
        new_cv = pickle.load(f)
        df_idf = pickle.load(f)
        data = pickle.load(f)
        all_symptoms = pickle.load(f)
        input_symptoms = pickle.load(f)
        input_age = pickle.load(f)
        input_gender = pickle.load(f)
        top_diseases = pickle.load(f)
        indices = pickle.load(f)
        distances = pickle.load(f)
        k = pickle.load(f)
        cols = pickle.load(f)
        df = pickle.load(f)
        docs = pickle.load(f)
        word_count_vector = pickle.load(f)
        tfidf_transformer = pickle.load(f)
        new_word_count_vector = pickle.load(f)
        new_tfidf_transformer = pickle.load(f)
        input_vector = pickle.load(f)
except Exception as e:
    print(f"Error loading ML model: {e}")

# Register Blueprints
app.register_blueprint(auth, url_prefix="/auth")
app.register_blueprint(users, url_prefix="/users")
app.register_blueprint(doctors, url_prefix="/doctors")
app.register_blueprint(chatbot, url_prefix="/chatbot")

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'patient':
            return redirect(url_for('users.dashboard'))
        else:
            return redirect(url_for('doctors.dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            access_token = create_access_token(identity={'id': user.id, 'role': user.role})
            
            # Secure Token Storage (HTTP-only cookie)
            response = make_response(redirect(url_for('users.dashboard') if user.role == 'user' else url_for('doctors.doctor_dashboard')))
            response.set_cookie('access_token', access_token, httponly=True)

            return response

        return render_template('login.html', error="Invalid credentials")
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup_page():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        username = request.form['username']
        role = request.form.get('role', 'user')
        specialization = request.form.get('specialization', None) if role == "doctor" else None

        if User.query.filter_by(email=email).first():
            return render_template('signup.html', error="Email already exists")

        new_user = User(username=username, email=email, password=password, role=role, specialization=specialization)
        db.session.add(new_user)
        db.session.commit()

        access_token = create_access_token(identity={'id': new_user.id, 'role': new_user.role})
        response = make_response(redirect(url_for('login_page')))
        response.set_cookie('access_token', access_token, httponly=True)

        return response

    return render_template('signup.html')

@app.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    response = jsonify({'message': 'Logged out successfully'})
    unset_jwt_cookies(response)
    return response

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'doctor':
        return render_template('doctor_dashboard.html')
    return render_template('patient_dashboard.html')

@app.route('/users/dashboard')
@jwt_required()
def user_dashboard():
    return render_template('dashboard.html')

@app.route('/doctor-dashboard')
@jwt_required()
def doctor_dashboard():
    return render_template('doctor_dashboard.html')

@app.route('/old')
@jwt_required()
def old_project():
    return render_template('index.html')  # Renders the old project page

@app.route('/get_data', methods=['POST'])
@jwt_required()
def get_data():
    req_data = request.json
    disease = req_data['disease']
    age = req_data['age']
    gender = req_data['gender']

    try:
        with open('./static/wholeData.json') as file:
            data = json.load(file)

        filtered_data = [d for d in data if d['name'] == disease and d['ageGroup'] == age and d['gender'] == gender]

        return jsonify(filtered_data[0]) if filtered_data else jsonify({'message': 'No data found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/predict', methods=['POST'])
@jwt_required()
def predict():
    req_data = request.json
    input_age = req_data['age']
    input_gender = req_data['gender']
    input_symptoms = req_data['symptoms']
    rejected_symptoms = req_data['rejected_symptoms']

    try:
        k = 5 if len(input_symptoms) < 3 else (3 if len(input_symptoms) < 5 else (2 if len(input_symptoms) < 7 else 1))

        docs = []
        filter_df = []
        for i in range(len(df)):
            item = []
            for j in range(len(cols)):
                if df.iloc[i][j] == '1':
                    item.append(cols[j])
            if item[-1] == input_age and item[-2] == input_gender:
                docs.append(','.join(item[:-2]))
                filter_df.append(data.iloc[i]['disease'])

        input_vector = cv.transform(input_symptoms)
        input_tfidf = tfidf_transformer.transform(input_vector)
        distances, indices = knn_model.kneighbors(input_tfidf, n_neighbors=k)

        top_diseases = [filter_df[i] for i in indices[0]]

        all_symptoms = []
        for i in indices[0]:
            symp = docs[i].split(',')
            tempSymp = [s for s in symp if s not in input_symptoms and s not in rejected_symptoms]
            all_symptoms += tempSymp

        sorted_symptoms = sorted(Counter(all_symptoms), key=Counter(all_symptoms).get)

        return jsonify({'top_diseases': top_diseases, 'top_symptoms': sorted_symptoms})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        
        # Create test users if they don't exist
        if User.query.count() == 0:
            # Create a test doctor
            test_doctor = User(
                username="Dr.Sharma",
                email="doctor@example.com",
                password="password123",
                role="doctor",
                specialization="general"
            )
            
            # Create a test patient
            test_patient = User(
                username="Rahul",
                email="patient@example.com",
                password="password123",
                role="patient"
            )
            
            db.session.add(test_doctor)
            db.session.add(test_patient)
            db.session.commit()
            print("Test users created successfully!")
            
    app.run(host="0.0.0.0", port=8080, debug=True)
