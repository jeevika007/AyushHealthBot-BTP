from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, User, Question, Consultation, Appointment, MedicalReport
from sqlalchemy import desc
from datetime import datetime

doctors = Blueprint("doctors", __name__)

# -------------------------------
# 🔹 Doctor Dashboard
# -------------------------------
@doctors.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'doctor':
        flash('Access denied. Doctor privileges required.', 'danger')
        return redirect(url_for('index'))
    
    # Get ALL questions for this doctor's specialization (both answered and unanswered)
    # But order them with urgent unanswered first, then non-urgent unanswered, then answered ones
    questions = Question.query.filter_by(
        specialization=current_user.specialization
    ).order_by(
        Question.answered.asc(),  # Unanswered first
        Question.urgent.desc(),   # Urgent first
        Question.created_at.desc() # Most recent first
    ).all()
    
    # Get appointments for this doctor
    appointments = Appointment.query.filter_by(
        doctor_id=current_user.id
    ).order_by(Appointment.appointment_date.asc()).all()
    
    return render_template('doctor_dashboard.html',
                         questions=questions,
                         appointments=appointments)

# -------------------------------
# 🔹 Fetch Unanswered Questions (Sorted by Urgency)
# -------------------------------
@doctors.route('/questions')
@login_required
def get_questions():
    if current_user.role != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403

    questions = Question.query.filter_by(
        specialization=current_user.specialization,
        answered=False
    ).order_by(desc(Question.urgent), desc(Question.created_at)).all()
    
    return jsonify({'questions': [q.to_dict() for q in questions]})

# -------------------------------
# 🔹 Answer a Patient's Question
# -------------------------------
@doctors.route('/answer_question/<int:question_id>', methods=['POST'])
@login_required
def answer_question(question_id):
    if current_user.role != 'doctor':
        flash('Access denied. Doctor privileges required.', 'danger')
        return redirect(url_for('index'))
    
    question = Question.query.get_or_404(question_id)
    answer = request.form.get('answer')
    
    if not answer:
        flash('Answer cannot be empty', 'danger')
        return redirect(url_for('doctors.dashboard'))
    
    question.answer = answer
    question.answered = True
    question.answered_at = datetime.utcnow()
    question.doctor_id = current_user.id
    
    db.session.commit()
    flash('Answer submitted successfully', 'success')
    return redirect(url_for('doctors.dashboard'))

# -------------------------------
# 🔹 Fetch Assigned Patients
# -------------------------------
@doctors.route('/patients')
@login_required
def get_patients():
    if current_user.role != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403

    # Get patients who have appointments with this doctor
    patients = User.query.join(Appointment, User.id == Appointment.patient_id)\
        .filter(Appointment.doctor_id == current_user.id)\
        .distinct().all()
    
    return jsonify({
        'doctor': current_user.username,
        'assigned_patients': [p.to_dict() for p in patients]
    })

# -------------------------------
# 🔹 Fetch Patient Medical History
# -------------------------------
@doctors.route('/patient-history/<int:patient_id>')
@login_required
def get_patient_history(patient_id):
    if current_user.role != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403

    # Verify if patient has an appointment with this doctor
    appointment = Appointment.query.filter_by(
        doctor_id=current_user.id,
        patient_id=patient_id
    ).first()
    
    if not appointment:
        return jsonify({'error': 'Unauthorized access to patient history'}), 403

    history = MedicalReport.query.filter_by(user_id=patient_id).all()
    return jsonify({
        'doctor': current_user.username,
        'patient_id': patient_id,
        'history': [h.to_dict() for h in history]
    })

# -------------------------------
# 🔹 Handle Consultation
# -------------------------------
@doctors.route('/handle_consultation/<int:consultation_id>', methods=['POST'])
@login_required
def handle_consultation(consultation_id):
    if current_user.role != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403
    
    consultation = Consultation.query.get_or_404(consultation_id)
    
    if consultation.specialization != current_user.specialization:
        return jsonify({'error': 'Unauthorized'}), 403
    
    response = request.form.get('response')
    if not response:
        return jsonify({'error': 'Response is required'}), 400
    
    consultation.status = 'answered'
    consultation.doctor_id = current_user.id
    consultation.response = response
    
    db.session.commit()
    
    return redirect(url_for('doctors.dashboard'))

# -------------------------------
# 🔹 Manage Appointment
# -------------------------------
@doctors.route('/update_appointment/<int:appointment_id>', methods=['POST'])
@login_required
def update_appointment(appointment_id):
    if current_user.role != 'doctor':
        flash('Access denied. Doctor privileges required.', 'danger')
        return redirect(url_for('index'))
    
    appointment = Appointment.query.get_or_404(appointment_id)
    status = request.form.get('status')
    
    if status not in ['confirmed', 'cancelled']:
        flash('Invalid status', 'danger')
        return redirect(url_for('doctors.dashboard'))
    
    appointment.status = status
    appointment.updated_at = datetime.utcnow()
    
    db.session.commit()
    flash(f'Appointment {status} successfully', 'success')
    return redirect(url_for('doctors.dashboard'))
