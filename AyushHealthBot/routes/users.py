from flask import Blueprint, jsonify, render_template, request, send_file, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, User, Question, Consultation, Appointment, ChatHistory, MedicalReport
import io
from reportlab.pdfgen import canvas
from datetime import datetime

users = Blueprint("users", __name__)

# ==============================
# 🔹 User Dashboard
# ==============================
@users.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'patient':
        flash('Access denied. Patient privileges required.', 'danger')
        return redirect(url_for('index'))
    
    # Get user's questions
    questions = Question.query.filter_by(
        patient_id=current_user.id
    ).order_by(Question.created_at.desc()).all()
    
    # Get user's appointments
    appointments = Appointment.query.filter_by(
        patient_id=current_user.id
    ).order_by(Appointment.appointment_date.asc()).all()
    
    # Get all doctors for appointment booking
    doctors = User.query.filter_by(role='doctor').all()
    
    return render_template('patient_dashboard.html',
                         user=current_user,
                         questions=questions,
                         appointments=appointments,
                         doctors=doctors)

@users.route('/consult-doctor', methods=['GET'])
@login_required
def consult_doctor():
    return render_template("consult_doctor.html", username=current_user.username)

# ==============================
# 🔹 Fetch User's Chat History
# ==============================
@users.route('/chat-history')
@login_required
def chat_history():
    chats = ChatHistory.query.filter_by(user_id=current_user.id).order_by(ChatHistory.created_at.desc()).all()
    return jsonify({
        'username': current_user.username,
        'chat_history': [chat.to_dict() for chat in chats]
    })

# ==============================
# 🔹 View Medical Reports
# ==============================
@users.route('/medical-reports')
@login_required
def medical_reports():
    reports = MedicalReport.query.filter_by(user_id=current_user.id).order_by(MedicalReport.timestamp.desc()).all()
    return jsonify({
        'username': current_user.username,
        'reports': [report.to_dict() for report in reports]
    })

# ==============================
# 🔹 Download Medical Report as PDF
# ==============================
@users.route("/download-report/<int:report_id>")
@login_required
def download_report(report_id):
    report = MedicalReport.query.get_or_404(report_id)
    
    if report.user_id != current_user.id:
        return jsonify({"error": "Unauthorized access"}), 403

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    p.drawString(100, 750, f"Report: {report.report_name}")
    p.drawString(100, 730, f"Diagnosis: {report.diagnosis}")
    p.drawString(100, 710, f"Doctor: {report.doctor_id if report.doctor_id else 'N/A'}")
    p.showPage()
    p.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name=f"report_{report_id}.pdf", mimetype="application/pdf")

# ==============================
# 🔹 Redirect to Old Project UI
# ==============================
@users.route('/old')
@login_required
def old_ui():
    return render_template("new.html")


@users.route('/submit-consultation', methods=['POST'])
@login_required
def submit_consultation():
    problem_description = request.form.get('problemDescription')
    doctor_specialization = request.form.get('doctorSpecialization')

    # Save consultation request to the database
    new_consultation = Consultation(
        user_id=current_user.id,
        problem_description=problem_description,
        specialization=doctor_specialization,
        status='pending'  # Initial status
    )
    db.session.add(new_consultation)
    db.session.commit()

    return jsonify({'message': 'Consultation request submitted successfully!'})

@users.route('/ask_question', methods=['POST'])
@login_required
def ask_question():
    if current_user.role != 'patient':
        flash('Access denied. Patient privileges required.', 'danger')
        return redirect(url_for('index'))
    
    title = request.form.get('title')
    description = request.form.get('description')
    specialization = request.form.get('specialization')
    urgent = 'urgent' in request.form
    
    if not all([title, description, specialization]):
        flash('All fields are required', 'danger')
        return redirect(url_for('users.dashboard'))
    
    question = Question(
        title=title,
        description=description,
        specialization=specialization,
        urgent=urgent,
        patient_id=current_user.id
    )
    
    db.session.add(question)
    db.session.commit()
    
    flash('Question submitted successfully', 'success')
    return redirect(url_for('users.dashboard'))

@users.route('/book_consultation', methods=['POST'])
@login_required
def book_consultation():
    data = request.form
    
    new_consultation = Consultation(
        user_id=current_user.id,
        problem_description=data['problem_description'],
        specialization=data['specialization']
    )
    
    db.session.add(new_consultation)
    db.session.commit()
    
    return redirect(url_for('users.dashboard'))

@users.route('/book_appointment', methods=['POST'])
@login_required
def book_appointment():
    if current_user.role != 'patient':
        flash('Access denied. Patient privileges required.', 'danger')
        return redirect(url_for('index'))
    
    doctor_id = request.form.get('doctor_id')
    appointment_date = request.form.get('appointment_date')
    
    if not all([doctor_id, appointment_date]):
        flash('All fields are required', 'danger')
        return redirect(url_for('users.dashboard'))
    
    try:
        appointment_date = datetime.strptime(appointment_date, '%Y-%m-%dT%H:%M')
        if appointment_date < datetime.now():
            flash('Cannot book appointments in the past', 'danger')
            return redirect(url_for('users.dashboard'))
    except ValueError:
        flash('Invalid date format', 'danger')
        return redirect(url_for('users.dashboard'))
    
    # Check if doctor exists and is actually a doctor
    doctor = User.query.filter_by(id=doctor_id, role='doctor').first()
    if not doctor:
        flash('Invalid doctor selected', 'danger')
        return redirect(url_for('users.dashboard'))
    
    # Check for conflicting appointments
    existing_appointment = Appointment.query.filter_by(
        doctor_id=doctor_id,
        appointment_date=appointment_date,
        status='confirmed'
    ).first()
    
    if existing_appointment:
        flash('This time slot is already booked', 'danger')
        return redirect(url_for('users.dashboard'))
    
    appointment = Appointment(
        patient_id=current_user.id,
        doctor_id=doctor_id,
        appointment_date=appointment_date
    )
    
    db.session.add(appointment)
    db.session.commit()
    
    flash('Appointment booked successfully. Waiting for doctor confirmation.', 'success')
    return redirect(url_for('users.dashboard'))



