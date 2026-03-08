from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import os
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour timeout
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ssc_registration.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)


# Database Models
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    student_type = db.Column(db.String(50), nullable=False)  # Government, Private, Staff
    age = db.Column(db.Integer, nullable=True)
    exam_score = db.Column(db.Float, nullable=True)
    grade_level = db.Column(db.String(20), nullable=True)
    application_status = db.Column(db.String(20), default='Pending')  # Pending, Approved, Rejected
    
    # File paths
    birth_certificate_path = db.Column(db.String(200), nullable=True)
    national_id_path = db.Column(db.String(200), nullable=True)
    parent_id_path = db.Column(db.String(200), nullable=True)
    photo_path = db.Column(db.String(200), nullable=True)
    staff_proof_path = db.Column(db.String(200), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Admin(db.Model):
    __tablename__ = 'admins'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)  # In production, use hashed passwords
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SystemSettings(db.Model):
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    registration_open_date = db.Column(db.Date, nullable=True)
    registration_close_date = db.Column(db.Date, nullable=True)
    exam_date = db.Column(db.String(50), default='June 15, 2026')
    exam_location = db.Column(db.String(200), default='National Examination Center, Addis Ababa')
    bank_name = db.Column(db.String(100), default='Commercial Bank of Ethiopia')
    bank_account_number = db.Column(db.String(50), default='1000123456789')
    bank_account_holder = db.Column(db.String(100), default='SSC Examination Board')
    telebirr_merchant_code = db.Column(db.String(20), default='123456')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Admin authentication decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            flash('Please login to access admin panel', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


def is_registration_open():
    """Check if registration is currently open based on settings"""
    settings = SystemSettings.query.first()
    if not settings:
        return True  # Default to open if no settings
    
    today = date.today()
    
    if settings.registration_open_date and today < settings.registration_open_date:
        return False
    
    if settings.registration_close_date and today > settings.registration_close_date:
        return False
    
    return True


def get_settings():
    """Get or create system settings"""
    settings = SystemSettings.query.first()
    if not settings:
        settings = SystemSettings()
        db.session.add(settings)
        db.session.commit()
    return settings


# Helper functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file, prefix):
    if file and allowed_file(file.filename):
        filename = f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return filepath
    return None


# Routes
@app.route('/')
def home():
    return render_template('home.html')


@app.route('/register')
def register_options():
    if not is_registration_open():
        settings = get_settings()
        flash(f'Registration is currently closed. Registration closes on {settings.registration_close_date.strftime("%B %d, %Y") if settings.registration_close_date else "N/A"}.', 'error')
        return redirect(url_for('home'))
    return render_template('register.html')


@app.route('/register/new', methods=['GET', 'POST'])
def new_user():
    if not is_registration_open():
        flash('Registration is currently closed.', 'error')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        # Get form data
        full_name = request.form.get('full_name')
        student_type = request.form.get('student_type')
        age = request.form.get('age')
        exam_score = request.form.get('exam_score')
        grade_level = request.form.get('grade_level')
        
        # Convert age and exam_score to appropriate types
        age_int = None
        exam_score_float = None
        
        try:
            if age:
                age_int = int(age)
        except ValueError:
            flash('Age must be a valid number!', 'error')
            return render_template('new_user.html')
        
        try:
            if exam_score:
                exam_score_float = float(exam_score)
        except ValueError:
            flash('Exam score must be a valid number!', 'error')
            return render_template('new_user.html')
        
        # Validation
        if not full_name or not student_type:
            flash('Full Name and Student Type are required!', 'error')
            return render_template('new_user.html')
        
        if age_int is None:
            flash('Age is required!', 'error')
            return render_template('new_user.html')
        
        # Validation - Age must be between 13-16
        if age_int < 13 or age_int > 16:
            flash('Age must be between 13 and 16 years old to be eligible for the SSC examination.', 'error')
            return render_template('new_user.html')
        
        # Validation - Exam Score must be at least 85%
        if exam_score_float is not None and exam_score_float < 85:
            flash('Your Ministry/Entrance Exam Score must be at least 85% to be eligible for the SSC examination.', 'error')
            return render_template('new_user.html')
        
        # Handle file uploads
        birth_cert = request.files.get('birth_certificate')
        national_id = request.files.get('national_id')
        photo = request.files.get('photo')
        parent_id = request.files.get('parent_id')
        staff_proof = request.files.get('staff_proof')
        
        # Validate required files
        if not birth_cert or not national_id or not photo or not parent_id:
            flash('All required documents must be uploaded!', 'error')
            return render_template('new_user.html')
        
        # Save files
        birth_cert_path = save_uploaded_file(birth_cert, 'birth')
        national_id_path = save_uploaded_file(national_id, 'national')
        photo_path = save_uploaded_file(photo, 'photo')
        parent_id_path = save_uploaded_file(parent_id, 'parent')
        
        # Staff proof only required for Staff type
        staff_proof_path = None
        if student_type == 'Staff':
            if not staff_proof:
                flash('Staff ID / Employment Proof is required for Staff type!', 'error')
                return render_template('new_user.html')
            staff_proof_path = save_uploaded_file(staff_proof, 'staff')
        
        # Create new user
        new_user = User(
            full_name=full_name,
            student_type=student_type,
            age=age_int,
            exam_score=exam_score_float,
            grade_level=grade_level,
            birth_certificate_path=birth_cert_path,
            national_id_path=national_id_path,
            parent_id_path=parent_id_path,
            photo_path=photo_path,
            staff_proof_path=staff_proof_path
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful!', 'success')
        return redirect(url_for('payment_info'))
    
    return render_template('new_user.html')


@app.route('/register/existing', methods=['GET', 'POST'])
def existing_user():
    if not is_registration_open():
        flash('Registration is currently closed.', 'error')
        return redirect(url_for('home'))
    
    user = None
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'search':
            # Search by uploaded National ID file
            national_id_file = request.files.get('national_id_search')
            if national_id_file:
                # In a real system, you'd extract ID info from the file
                # For this demo, we'll flash a message
                flash('Searching for user... Please verify your information below.', 'info')
            
            # Get grade level
            grade_level = request.form.get('grade_level_search')
            
            # For demo purposes, get the most recent user or search by name
            search_name = request.form.get('search_name', '').strip()
            if search_name:
                user = User.query.filter(User.full_name.ilike(f'%{search_name}%')).first()
            else:
                user = User.query.order_by(User.created_at.desc()).first()
            
            if not user:
                flash('No existing user found. Please register as a new user.', 'error')
                return render_template('existing_user.html', user=None)
        
        elif action == 'update':
            user_id = request.form.get('user_id')
            user = User.query.get(user_id)
            
            if user:
                user.grade_level = request.form.get('grade_level')
                
                # Handle new National ID upload
                new_national_id = request.files.get('national_id_update')
                if new_national_id:
                    national_id_path = save_uploaded_file(new_national_id, 'national_update')
                    user.national_id_path = national_id_path
                
                db.session.commit()
                flash('Information updated successfully!', 'success')
                return redirect(url_for('payment_info'))
    
    return render_template('existing_user.html', user=user)


@app.route('/payment')
def payment_info():
    settings = get_settings()
    return render_template('payment.html', settings=settings)


# Admin Routes
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    # Always show login form first - credentials required every time for security
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin = Admin.query.filter_by(username=username, password=password).first()
        
        if admin:
            session.clear()  # Clear any old session first
            session['admin_logged_in'] = True
            session['admin_username'] = username
            flash('Welcome to Admin Dashboard', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('admin/login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('admin_login'))


@app.route('/admin')
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    # Get statistics
    total_users = User.query.count()
    pending_count = User.query.filter_by(application_status='Pending').count()
    approved_count = User.query.filter_by(application_status='Approved').count()
    rejected_count = User.query.filter_by(application_status='Rejected').count()
    staff_count = User.query.filter_by(student_type='Staff').count()
    student_count = User.query.filter(User.student_type != 'Staff').count()
    
    # Get recent applications
    recent_applications = User.query.order_by(User.created_at.desc()).limit(10).all()
    
    # Check registration status
    registration_open = is_registration_open()
    settings = get_settings()
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         pending_count=pending_count,
                         approved_count=approved_count,
                         rejected_count=rejected_count,
                         staff_count=staff_count,
                         student_count=student_count,
                         recent_applications=recent_applications,
                         registration_open=registration_open,
                         settings=settings)


@app.route('/admin/applications')
@admin_required
def admin_applications():
    status_filter = request.args.get('status', 'all')
    search_query = request.args.get('search', '')
    
    query = User.query
    
    if status_filter != 'all':
        query = query.filter_by(application_status=status_filter)
    
    if search_query:
        query = query.filter(User.full_name.ilike(f'%{search_query}%'))
    
    applications = query.order_by(User.created_at.desc()).all()
    
    return render_template('admin/applications.html',
                         applications=applications,
                         status_filter=status_filter,
                         search_query=search_query)


@app.route('/admin/applications/<int:user_id>')
@admin_required
def admin_application_detail(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('admin/application_detail.html', user=user)


@app.route('/admin/applications/<int:user_id>/approve', methods=['POST'])
@admin_required
def admin_approve_application(user_id):
    user = User.query.get_or_404(user_id)
    user.application_status = 'Approved'
    db.session.commit()
    flash(f'Application for {user.full_name} has been approved.', 'success')
    return redirect(url_for('admin_applications'))


@app.route('/admin/applications/<int:user_id>/reject', methods=['POST'])
@admin_required
def admin_reject_application(user_id):
    user = User.query.get_or_404(user_id)
    user.application_status = 'Rejected'
    db.session.commit()
    flash(f'Application for {user.full_name} has been rejected.', 'info')
    return redirect(url_for('admin_applications'))


@app.route('/admin/users')
@admin_required
def admin_users():
    search_query = request.args.get('search', '')
    type_filter = request.args.get('type', 'all')
    
    query = User.query
    
    if search_query:
        query = query.filter(User.full_name.ilike(f'%{search_query}%'))
    
    if type_filter != 'all':
        query = query.filter_by(student_type=type_filter)
    
    users = query.order_by(User.created_at.desc()).all()
    
    return render_template('admin/users.html',
                         users=users,
                         search_query=search_query,
                         type_filter=type_filter)


@app.route('/admin/users/<int:user_id>')
@admin_required
def admin_user_detail(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('admin/user_detail.html', user=user)


@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    settings = get_settings()
    
    if request.method == 'POST':
        # Registration dates
        reg_open_date = request.form.get('registration_open_date')
        reg_close_date = request.form.get('registration_close_date')
        
        if reg_open_date:
            settings.registration_open_date = datetime.strptime(reg_open_date, '%Y-%m-%d').date()
        if reg_close_date:
            settings.registration_close_date = datetime.strptime(reg_close_date, '%Y-%m-%d').date()
        
        # Exam information
        settings.exam_date = request.form.get('exam_date', settings.exam_date)
        settings.exam_location = request.form.get('exam_location', settings.exam_location)
        
        # Payment information
        settings.bank_name = request.form.get('bank_name', settings.bank_name)
        settings.bank_account_number = request.form.get('bank_account_number', settings.bank_account_number)
        settings.bank_account_holder = request.form.get('bank_account_holder', settings.bank_account_holder)
        settings.telebirr_merchant_code = request.form.get('telebirr_merchant_code', settings.telebirr_merchant_code)
        
        db.session.commit()
        flash('Settings updated successfully', 'success')
        return redirect(url_for('admin_settings'))
    
    return render_template('admin/settings.html', settings=settings)


@app.route('/admin/documents/<int:user_id>')
@admin_required
def admin_view_documents(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('admin/documents.html', user=user)


# Initialize database
@app.before_request
def create_tables():
    db.create_all()


def create_default_admin():
    """Create default admin if none exists"""
    with app.app_context():
        db.create_all()
        # Create default admin if none exists
        if not Admin.query.first():
            default_admin = Admin(username='admin', password='admin123')
            db.session.add(default_admin)
            db.session.commit()
            print("Default admin created: username='admin', password='admin123'")


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_default_admin()
    app.run(debug=True)
