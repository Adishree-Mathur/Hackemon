from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from models import db, User, Doctor, Appointment
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
from twilio.rest import Client
from dotenv import load_dotenv
import google.generativeai as genai
from deep_translator import GoogleTranslator
import random
from flask_migrate import Migrate
from models import Doctor


load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'development-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shewell.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)

if os.getenv('TWILIO_ACCOUNT_SID') and os.getenv('TWILIO_AUTH_TOKEN'):
    twilio_client = Client(os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN'))
    twilio_phone_number = os.getenv('TWILIO_PHONE_NUMBER')
else:
    twilio_client = None
    twilio_phone_number = None

genai.configure(api_key='your_api_key_here')  # Replace with your API key
gemini_model = genai.GenerativeModel('gemini-2.0-flash')

def login_required(user_type=None):
    if 'user_id' not in session:
        flash('Please log in to access this page', 'error')
        return redirect(url_for('login'))
    if user_type and session.get('user_type') != user_type:
        flash(f'You must be logged in as a {user_type} to access this page', 'error')
        return redirect(url_for('dashboard'))
    return None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user_type = request.form.get('user_type')

        user = User.query.filter_by(email=email).first() if user_type == 'patient' else Doctor.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['user_type'] = user_type
            session['name'] = user.name  # Store name in session
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))

        flash('Invalid email or password', 'error')
    return render_template('login.html')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/periods')
def periods():
    return render_template('periods.html')

@app.route("/mental-health")
def mental_health():
    quotes = [
        "This too shall pass.", "You are stronger than you think.",
        "Breathe in courage, breathe out fear.", "One day at a time.",
        "You are enough just as you are.", "The sun will rise, and so will you."
    ]
    return render_template("mental_health.html", quote=random.choice(quotes))

@app.route('/reels')
def reels():
    return render_template("reels.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route('/register_patient', methods=['POST'])
def register_patient():
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    password = request.form.get('password')

    if User.query.filter_by(email=email).first():
        flash('Email is already registered', 'error')
        return redirect(url_for('register'))

    new_user = User(name=name, email=email, phone=phone)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    flash('Patient registered successfully! Please log in.', 'success')
    return redirect(url_for('login'))

@app.route('/register_doctor', methods=['POST'])
def register_doctor():
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    specialization = request.form.get('specialization')
    password = request.form.get('password')
    per_minute_price = request.form.get('per_minute_price', type=float)

    if Doctor.query.filter_by(email=email).first():
        flash('Email is already registered', 'error')
        return redirect(url_for('register'))

    new_doctor = Doctor(
        name=name,
        email=email,
        phone=phone,
        specialization=specialization,
        experience=request.form.get('experience', 0, type=int),
        available_days=request.form.get('available_days', 'Mon-Fri'),
        per_minute_price=per_minute_price
    )
    new_doctor.set_password(password)
    db.session.add(new_doctor)
    db.session.commit()

    flash('Doctor registered successfully! Please log in.', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session or 'user_type' not in session:
        flash('Please log in to access this page', 'error')
        return redirect(url_for('login'))
    
    if session['user_type'] == 'patient':
        return redirect(url_for('patient_dashboard'))
    elif session['user_type'] == 'doctor':
        return redirect(url_for('doctor_dashboard'))
    else:
        flash('Invalid user type', 'error')
        return redirect(url_for('login'))

@app.route('/patient_dashboard')
def patient_dashboard():
    redirect_result = login_required('patient')
    if redirect_result:
        return redirect_result

    user = User.query.get(session['user_id'])
    appointments = Appointment.query.filter_by(user_id=user.id).all()
    return render_template('patient_dashboard.html', user=user, appointments=appointments)

@app.route('/doctor_dashboard', methods=['GET', 'POST'])
def doctor_dashboard():
    try:
        # Verify user is logged in as doctor
        if 'user_id' not in session or session.get('user_type') != 'doctor':
            flash('Please login as a doctor first', 'error')
            return redirect(url_for('login'))

        # Get doctor from database
        doctor = Doctor.query.get(session['user_id'])
        if not doctor:
            flash('Doctor profile not found', 'error')
            return redirect(url_for('login'))

        # Handle price update
        if request.method == 'POST':
            new_price = request.form.get('per_minute_price', type=float)
            if new_price is not None:
                doctor.per_minute_price = new_price
                db.session.commit()
                flash('Price updated successfully!', 'success')

        # Get appointments
        appointments = Appointment.query.filter_by(doctor_id=doctor.id).all()
        
        # Render template with all required variables
        return render_template('doctor_dashboard.html',
                            doctor=doctor,
                            appointments=appointments,
                            current_time=datetime.now())  # Pass current time

    except Exception as e:
        app.logger.error(f"Dashboard error: {str(e)}")
        flash('Failed to load dashboard', 'error')
        return redirect(url_for('home'))
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('home'))

@app.route('/doctors')
def doctors():
    redirect_result = login_required('patient')
    if redirect_result:
        return redirect_result
    doctors_list = Doctor.query.all()
    return render_template('doctors.html', doctors=doctors_list)

@app.route('/book_appointment/<int:doctor_id>', methods=['GET', 'POST'])
def book_appointment(doctor_id):
    redirect_result = login_required('patient')
    if redirect_result:
        return redirect_result

    doctor = Doctor.query.get_or_404(doctor_id)

    if request.method == 'POST':
        date = request.form.get('date')
        time = request.form.get('time')

        appointment = Appointment(
            user_id=session['user_id'],
            doctor_id=doctor_id,
            date=datetime.strptime(date, '%Y-%m-%d'),
            time=time
        )
        db.session.add(appointment)
        db.session.commit()

        if twilio_client and twilio_phone_number:
            user = User.query.get(session['user_id'])
            try:
                twilio_client.messages.create(
                    body=f"Hello {user.name}, your appointment with Dr. {doctor.name} is confirmed for {date} at {time}.",
                    from_=twilio_phone_number,
                    to=user.phone
                )
            except Exception as e:
                app.logger.error(f"Failed to send SMS: {e}")

        flash('Appointment booked successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('book_appointment.html', doctor=doctor)

@app.route('/chatbot')
def chatbot():
    redirect_result = login_required('patient')
    if redirect_result:
        return redirect_result
    return render_template('chatbot.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    redirect_result = login_required('patient')
    if redirect_result:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'error': 'Message is required'}), 400

    user_message = data.get('message')
    selected_language = data.get('language', 'en')

    def translate_text(text, target_language="en"):
        try:
            return GoogleTranslator(source='auto', target=target_language).translate(text)
        except Exception as e:
            app.logger.error(f"Translation error: {e}")
            return text

    prompt = f"""
    You are a supportive AI assistant for pregnant women on the SheWell platform.
    Provide helpful, accurate information about pregnancy, but always recommend consulting with their doctor. 
    The question is: {translate_text(user_message, 'en')}
    """

    try:
        response = gemini_model.generate_content(prompt)
        ai_response = response.text.strip() if hasattr(response, 'text') else "I'm sorry, I couldn't process your request."
        return jsonify({'response': translate_text(ai_response, selected_language)})
    except Exception as e:
        app.logger.error(f"Failed to generate AI response: {e}")
        return jsonify({'response': 'Sorry, I was unable to process your request. Please try again later.'}), 500

@app.route('/admin/add_doctor', methods=['GET', 'POST'])
def add_doctor():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        specialization = request.form.get('specialization')
        experience = request.form.get('experience')
        phone = request.form.get('phone')
        available_days = request.form.get('available_days')
        per_minute_price = request.form.get('per_minute_price', type=float)

        if Doctor.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('admin_add_doctor.html')

        doctor = Doctor(
            name=name, email=email, specialization=specialization,
            experience=experience, phone=phone,
            available_days=available_days, per_minute_price=per_minute_price
        )
        doctor.set_password(password)
        db.session.add(doctor)
        db.session.commit()
        flash('Doctor added successfully!', 'success')
        return redirect(url_for('home'))

    return render_template('admin_add_doctor.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)