from flask import Blueprint, request, jsonify, render_template, redirect, url_for, make_response, flash
from flask_jwt_extended import create_access_token, jwt_required, unset_jwt_cookies, get_jwt_identity
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, bcrypt

auth = Blueprint("auth", __name__)


@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        data = request.form
        role = data.get('role')
        specialization = data.get('specialization') if role == 'doctor' else None

        # Validate required fields
        if not all([data.get('username'), data.get('email'), data.get('password'), role]):
            return render_template('signup.html', error="All fields are required")

        # Check if email already exists
        if User.query.filter_by(email=data['email']).first():
            return render_template('signup.html', error="Email already exists")

        # Create new user
        new_user = User(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            role=role,
            specialization=specialization
        )
        db.session.add(new_user)
        db.session.commit()

        # Log in the new user
        login_user(new_user)
        
        # Also create JWT token
        access_token = create_access_token(identity={'id': new_user.id, 'role': new_user.role})
        response = make_response(redirect(url_for('users.dashboard' if role == 'patient' else 'doctors.dashboard')))
        response.set_cookie('access_token', access_token, httponly=True)
        
        return response

    return render_template('signup.html')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        data = request.form
        email = data.get('email')
        password = data.get('password')
        role = data.get('role')

        if not all([email, password, role]):
            return render_template('login.html', error="All fields are required")

        try:
            user = User.query.filter_by(email=email, role=role).first()
            
            if user and user.check_password(password):
                # Log in the user with Flask-Login
                login_user(user)
                
                # Create JWT token
                access_token = create_access_token(identity={'id': user.id, 'role': user.role})
                
                # Create response with appropriate redirect
                response = make_response(redirect(url_for('users.dashboard' if role == 'patient' else 'doctors.dashboard')))
                response.set_cookie('access_token', access_token, httponly=True)
                return response

            return render_template('login.html', error="Invalid credentials")
        except Exception as e:
            print(f"Login error: {str(e)}")
            return render_template('login.html', error="An error occurred during login. Please try again.")

    return render_template('login.html')


@auth.route('/logout', methods=['POST'])
@login_required
def logout():
    # Log out the user from Flask-Login
    logout_user()
    
    # Also remove JWT token
    response = make_response(redirect(url_for('auth.login')))
    response.delete_cookie('access_token')
    return response


@auth.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@auth.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    username = request.form.get('username')
    email = request.form.get('email')
    
    if not username or not email:
        flash('Username and email are required', 'danger')
        return redirect(url_for('auth.profile'))
    
    # Check if email already exists for another user
    existing_user = User.query.filter(User.email == email, User.id != current_user.id).first()
    if existing_user:
        flash('Email already in use by another account', 'danger')
        return redirect(url_for('auth.profile'))
    
    current_user.username = username
    current_user.email = email
    
    # Update specialization if doctor
    if current_user.role == 'doctor':
        specialization = request.form.get('specialization')
        if specialization:
            current_user.specialization = specialization
    
    db.session.commit()
    flash('Profile updated successfully', 'success')
    return redirect(url_for('auth.profile'))

@auth.route('/change_password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not current_password or not new_password or not confirm_password:
        flash('All fields are required', 'danger')
        return redirect(url_for('auth.profile'))
    
    if not current_user.check_password(current_password):
        flash('Current password is incorrect', 'danger')
        return redirect(url_for('auth.profile'))
    
    if new_password != confirm_password:
        flash('New passwords do not match', 'danger')
        return redirect(url_for('auth.profile'))
    
    if len(new_password) < 8:
        flash('Password must be at least 8 characters long', 'danger')
        return redirect(url_for('auth.profile'))
    
    current_user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
    db.session.commit()
    
    flash('Password updated successfully', 'success')
    return redirect(url_for('auth.profile'))
