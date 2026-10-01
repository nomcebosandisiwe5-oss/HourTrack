from flask import render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from app import app
from models import db, User
from models import HoursLog
from werkzeug.security import generate_password_hash
from flask import make_response
import csv
import io
from datetime import datetime
from models import User
from models import HoursLog
from extensions import mail
from flask_mail import Message
import secrets
from datetime import datetime, timedelta
from flask_login import login_required, current_user
from flask_login import login_user



@app.route('/')
def home():
    return render_template('home.html',)
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form.get('email', '').strip().lower()
        course=request.form['course']
        location = request.form.get('location')
        role = request.form.get('role', 'student').lower()

        # STUDENT MUST USE UNIVERSITY EMAIL
        if role == 'student':
            if not email.endswith('@stu.unizulu.ac.za'):
                flash('Student registration requires @unizulu.ac.za email only!', 'danger')
                return redirect(url_for('register'))

        password = request.form['password']
        role = request.form['role']

        existing = User.query.filter_by(email=email).first()
        if existing:
            if not existing.password or existing.password == "":
                existing.password = generate_password_hash(password)
                existing.is_approved = True
                db.session.commit()
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Email already registered! Please login.', 'warning')
                return redirect(url_for('login'))
        else:
            hashed_password = generate_password_hash(password)
            new_user = User(
                first_name=first_name, 
                last_name=last_name,
                email=email, 
                password=hashed_password, 
                role=role,
                course=course,
                location=location,
                is_approved=False
            )
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')



@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            if not user.is_approved:
                flash('Your account is waiting for Admin approval.')
                return redirect(url_for('login'))

            if user.role == 'admin':
                user.is_approved = True
                db.session.commit()

            session['user_id'] = user.id
            session['name'] = user.first_name
            session['role'] = user.role
            login_user(user)

            if user.role == 'student':
                return redirect(url_for('student_dashboard'))
            elif user.role == 'supervisor':
                return redirect(url_for('supervisor_dashboard'))
            elif user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid email or password')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('home'))


@app.route('/student_dashboard')
def student_dashboard():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))

    logs = HoursLog.query.filter_by(student_id=session['user_id']).order_by(HoursLog.clock_in_time.desc()).all()
    currently_clocked_in = HoursLog.query.filter_by(student_id=session['user_id'], clock_out_time=None).first()
    total_approved = sum(l.total_hours for l in logs if l.status == 'approved' and l.total_hours)

    return render_template(
        'student_dashboard.html',
        name=session.get('name'),
        logs=logs,
        currently_clocked_in=currently_clocked_in,
        total_approved=total_approved
    )


@app.route('/clock_in', methods=['GET', 'POST'])
def clock_in():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))

    open_log = HoursLog.query.filter_by(student_id=session['user_id'], clock_out_time=None).first()
    if open_log:
        flash('You are already clocked in!')
        return redirect(url_for('student_dashboard'))
    task = request.form.get('task_description')
    loc = request.form.get('location')

    new_log = HoursLog(student_id=session['user_id'], task_description=task, location=loc, clock_in_time=datetime.now())
    db.session.add(new_log)
    db.session.commit()
    flash(f'Clocked in at {new_log.clock_in_time.strftime("%Y-%m-%d %H:%M:%S")}')
    return redirect(url_for('student_dashboard'))


@app.route('/clock_out')
def clock_out():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))

    open_log = HoursLog.query.filter_by(student_id=session['user_id'], clock_out_time=None).first()
    if not open_log:
        flash('You are not currently clocked in!')
        return redirect(url_for('student_dashboard'))

    open_log.clock_out_time = datetime.now()
    duration = open_log.clock_out_time - open_log.clock_in_time
    open_log.total_hours = round(duration.total_seconds() / 3600, 2)
    db.session.commit()
    flash(f'Clocked out at {open_log.clock_out_time.strftime("%Y-%m-%d %H:%M:%S")} — {open_log.total_hours} hours logged, pending approval.')
    return redirect(url_for('student_dashboard'))


@app.route('/supervisor_dashboard')
def supervisor_dashboard():
    if 'user_id' not in session or session.get('role') != 'supervisor':
        return redirect(url_for('login'))

    

    my_id = session.get('user_id')

    pending_logs = HoursLog.query.join(User, HoursLog.student_id == User.id)\
        .filter(
            User.supervisor_id == my_id,
            HoursLog.status == 'pending',
            HoursLog.clock_out_time.isnot(None)
        ).all()

    my_students = User.query.filter_by(role='student', supervisor_id=my_id).all()

    return render_template('supervisor_dashboard.html', name=session.get('name'), logs=pending_logs, students=my_students)


@app.route('/approve_log/<int:log_id>')
def approve_log(log_id):
    if 'user_id' not in session or session.get('role') != 'supervisor':
        return redirect('/login')
    log = HoursLog.query.get(log_id)
    if log:
        log.status = 'approved'
        db.session.commit()
    return redirect('/supervisor_dashboard')

@app.route('/reject/<int:log_id>', methods=['GET', 'POST'])
def reject_log(log_id):
    if 'user_id' not in session or session.get('role') != 'supervisor':
        return redirect(url_for('login'))
    log = HoursLog.query.get(log_id)
    if log:
        comment = request.form.get('comment', 'No reason given')
        log.status = 'rejected'
        log.rejection_comment = comment
        db.session.commit()
    return redirect(url_for('supervisor_dashboard'))

@app.route('/approve_user/<int:id>') 
def approve_user(id):
    print("=== APPROVE CLICKED ===")
    print("Session:", session.get('user_id'))
    if 'user_id' not in session:
        print("FAIL: No session - redirecting to login")
        return redirect(url_for('login'))
    me = User.query.get(session['user_id'])
    print("Me:", me, "Role:", me.role if me else "None")
    if not me or me.role.lower() != 'admin':
        print("FAIL: Not admin")
        return redirect(url_for('login'))
    u = User.query.get(id)
    print("Target user:", u.first_name, u.role, u.is_approved)
    if u:
        u.is_approved = True
        db.session.commit()
        print("SUCCESS: Approved")
    return redirect(url_for('admin_dashboard'))






@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    me = User.query.get(session['user_id'])
    if not me or me.role.lower() != 'admin':
        return redirect(url_for('login'))

    users = User.query.all()  # for Approve list
    # ONLY approved supervisors show in Assign dropdown
    supervisors = User.query.filter(
        User.role.ilike('supervisor'),
        User.is_approved == True
    ).all()

    return render_template('admin_dashboard.html', users=users, supervisors=supervisors)



@app.route('/generate_report')
def generate_report():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    # get all Logs with student info
    
    logs = HoursLog.query.order_by(HoursLog.clock_in_time.desc()).all()
    total_hours = sum([l.total_hours or 0 for l in logs])

    return render_template('generate_report.html', logs=logs, total_hours=total_hours, now=datetime.now())

@app.route('/download_report_csv')
def download_report_csv():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    logs = HoursLog.query.all()
    
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Student Name', 'Email', 'Clock In', 'Clock Out', 'Total Hours', 'Status'])
    
    for log in logs:
        writer.writerow([
            log.student.name if log.student else 'Unknown',
            log.student.email if log.student else '',
            log.clock_in_time,
            log.clock_out_time,
            log.total_hours,
            log.status
        ])
    
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=HourTrack_Report.csv"
    response.headers["Content-type"] = "text/csv"
    return response


@app.route('/download_report_pdf')
def download_report_pdf():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    from fpdf import FPDF
    from flask import make_response

    logs = HoursLog.query.all()
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="HourTrack - Admin Report", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", size=10)
    for log in logs:
        name = log.student.name if log.student else 'Unknown'
        pdf.cell(0, 8, txt=f"{name} | In: {log.clock_in_time} | Out: {log.clock_out_time} | {log.total_hours}h | {log.status}", ln=True, border=1)
    
    response = make_response(bytes(pdf.output()))
    response.headers['Content-Disposition'] = 'attachment; filename=HourTrack_Report.pdf'
    response.headers['Content-Type'] = 'application/pdf'
    return response


@app.route('/admin/add_student', methods=['GET', 'POST'])
def add_student():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        program = request.form['program']          # e.g. Nursing, Education
        required_hours = request.form['required_hours']

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('A user with that email already exists.')
            return redirect(url_for('add_student'))

        new_student = User(
            name=name,
            email=email,
            password=generate_password_hash(password),
            role='student',
            program=program,
            required_hours=required_hours,
            completed_hours=0
        )
        db.session.add(new_student)
        db.session.commit()

        flash(f'Student {name} added successfully.')
        return redirect(url_for('admin_dashboard'))

    return render_template('add_student.html')


@app.route('/admin/add_supervisor', methods=['GET', 'POST'])
def add_supervisor():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        department = request.form['department']   # e.g. Nursing, Education
        phone = request.form.get('phone')

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('A user with that email already exists.')
            return redirect(url_for('add_supervisor'))

        new_supervisor = User(
            name=name,
            email=email,
            password=generate_password_hash(password),
            role='supervisor',
            department=department,
            phone=phone
        )
        db.session.add(new_supervisor)
        db.session.commit()

        flash(f'Supervisor {name} added successfully.')
        return redirect(url_for('admin_dashboard'))

    return render_template('add_supervisor.html')


@app.route('/admin/assign', methods=['GET', 'POST'])
def assign_supervisor():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    students = User.query.filter_by(role='student').all()
    supervisors = User.query.filter_by(role='supervisor').all()

    if request.method == 'POST':
        student_id = request.form['student_id']
        supervisor_id = request.form['supervisor_id']

        student = User.query.get(student_id)
        if not student:
            flash('Student not found.')
            return redirect(url_for('assign_supervisor'))

        student.supervisor_id = supervisor_id
        db.session.commit()

        supervisor = User.query.get(supervisor_id)
        flash(f'{student.name} has been assigned to {supervisor.name}.')
        return redirect(url_for('assign_supervisor'))

    return redirect(url_for('admin_dashboard'))

@app.route('/delete_user/<int:id>')
def delete_user(id):
    
    user = User.query.get_or_404(id)
    
    # 1. Delete all hours for this student
    HoursLog.query.filter_by(student_id=user.id).delete()
    
    # 2. If this user is a supervisor, un-assign his students
    students_assigned = User.query.filter_by(supervisor_id=user.id).all()
    for s in students_assigned:
        s.supervisor_id = None
    
    db.session.delete(user)
    db.session.commit()
    flash(f"Deleted {user.first_name}")
    return redirect(url_for('admin_dashboard'))

@app.route('/edit_user/<int:id>', methods=['GET', 'POST'])
def edit_user(id):
    user = User.query.get_or_404(id)
    if request.method == 'POST':
        user.first_name = request.form.get('first_name')
        user.last_name = request.form.get('last_name')
        user.email = request.form.get('email')
        user.role = request.form.get('role')
        db.session.commit()
        flash(f"User {user.first_name} updated!")
        return redirect(url_for('admin_dashboard'))
    return render_template('edit_user.html', user=user)



@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if not user:
            # to match your forgot template which uses flash version, we keep flash
            # but your reset template uses message - so we handle both
            flash('No account found with that email', 'danger')
            return redirect('/forgot-password')

        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expiry = datetime.utcnow() + timedelta(minutes=30)
        db.session.commit()

        reset_link = url_for('reset_password', token=token, _external=True)

        msg = Message("HourTrack - Reset Password", recipients=[email])
        msg.body = f"Hello,\n\nYou requested to reset your password.\nClick the link below:\n{reset_link}\n\nThis link expires in 30 minutes.\nIf you didn't request this, ignore this email."
        mail.send(msg)
        

        flash('Reset link sent! Check  email', 'success')
        return redirect('/login')

    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()

    # Invalid or expired
    if not user or not user.reset_token_expiry or user.reset_token_expiry < datetime.utcnow():
        return render_template('reset_password.html', 
                               valid=False, 
                               message='Link expired or invalid. Request a new one.',
                               success=False,
                               token=token)

    if request.method == 'POST':
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')

        if password != confirm:
            return render_template('reset_password.html',
                                   valid=True,
                                   message='Passwords do not match',
                                   success=False,
                                   token=token)

        if len(password) < 6:
            return render_template('reset_password.html',
                                   valid=True,
                                   message='Password must be at least 6 characters',
                                   success=False,
                                   token=token)

        user.password = generate_password_hash(password)
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()

        flash('Password reset successful, please login', 'success')
        return redirect('/login')

    # GET - show form
    return render_template('reset_password.html', valid=True, token=token, message=None)


from werkzeug.security import generate_password_hash



@app.route('/admin/upload', methods=['GET','POST'])
def admin_upload():
    print(f"Is Authenticated: {current_user.is_authenticated}")
    print(f"User: {current_user}")
    if not current_user.is_authenticated:
        flash('You are not logged in! Please login again', 'danger')
        return redirect(url_for('login'))
    if current_user.role!= 'admin':
        flash('Access denied! Admin only', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        file = request.files.get('file')
        if not file or file.filename == '':
            flash('No file selected!', 'danger')
            return redirect(request.url)

        if file.filename.endswith('.csv'):
            try:
                content = file.read().decode('utf-8')
                csv_reader = csv.DictReader(content.splitlines())
                count = 0
                for row in csv_reader:
                    if not User.query.filter_by(email=row['email']).first():
                        full_name = row.get('name','').strip()
                        first = row.get('first_name') or (full_name.split()[0] if full_name else 'Student')
                        last = row.get('last_name') or (' '.join(full_name.split()[1:]) if len(full_name.split()) > 1 else '')

                        new_user = User(
                            first_name=first,
                            last_name=last,
                            email=row['email'],
                            role=row.get('role','student').lower(),
                            location=row.get('location','Main Campus'), # <-- THIS FIXES YOUR PROFILE
                            course=row.get('course',''),
                            is_approved=True
                        )
                        new_user.set_password(row.get('password','Student123'))
                        db.session.add(new_user)
                        count += 1
                db.session.commit()
                flash(f'✅ Successfully uploaded {count} users!', 'success')
            except Exception as e:
                flash(f'Error: {str(e)}', 'danger')
        else:
            flash('Please upload CSV file only!', 'danger')

    return render_template('admin_upload.html')

@app.route('/my_profile')
@login_required
def my_profile():
    return render_template('my_profile.html', user=current_user)

@app.route('/dashboard')
def dashboard():
    from flask_login import current_user
    if not current_user.is_authenticated:
        return redirect('/login')
    role = current_user.role.lower()
    if role == 'student':
        return redirect('/student_dashboard')
    elif role == 'supervisor':
        return redirect('/supervisor_dashboard')
    elif role == 'admin':
        return redirect('/admin_dashboard')
    else:
        return redirect('/login')