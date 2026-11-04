import os
import io
import cv2
import time
import json
import base64
import datetime
import functools
import numpy as np
import pandas as pd
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, jsonify, Response, flash, send_file
)

import config
from db import init_db, query_db
from vision_engine import vision_engine

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# Ensure Database and Sample Data are ready
init_db()

# ---------------------------------------------------------
# AUTHENTICATION DECORATORS
# ---------------------------------------------------------
def login_required(required_role=None):
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('username'):
                flash('Please log in to access this portal.', 'danger')
                return redirect(url_for('login_view', role=required_role or 'admin'))
            if required_role and session.get('role') != required_role:
                flash(f'Unauthorized access. {required_role.capitalize()} privileges required.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ---------------------------------------------------------
# PUBLIC & SURVEILLANCE ROUTES
# ---------------------------------------------------------
@app.route('/')
def index():
    os_has_banner = os.path.exists(os.path.join(config.BASE_DIR, 'static', 'images', 'project_banner.png'))
    return render_template('index.html', os_has_banner=os_has_banner)

@app.route('/login')
def login_view():
    role = request.args.get('role', 'staff').lower()
    if role not in ['admin', 'staff', 'hod']:
        role = 'staff'
        
    role_titles = {
        'admin': 'College Admin',
        'staff': 'Faculty Staff (ECE Department)',
        'hod': 'Head of Department (ECE)'
    }
    default_users = {
        'admin': 'admin',
        'staff': 'staff_ece',
        'hod': 'hod_ece'
    }
    default_passes = {
        'admin': 'admin123',
        'staff': 'staff123',
        'hod': 'hod123'
    }
    
    return render_template(
        'login.html',
        current_role=role,
        role_title=role_titles[role],
        default_user=default_users[role],
        default_pass=default_passes[role]
    )

@app.route('/login_submit', methods=['POST'])
def login_submit():
    role = request.form.get('role', 'admin').lower()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()

    account = None
    if role == 'admin':
        account = query_db("SELECT * FROM admin WHERE username = %s AND password = %s", (username, password), one=True)
    elif role == 'staff':
        account = query_db("SELECT * FROM staff WHERE username = %s AND password = %s", (username, password), one=True)
    elif role == 'hod':
        account = query_db("SELECT * FROM hod WHERE username = %s AND password = %s", (username, password), one=True)

    if account:
        session['username'] = account['username']
        session['role'] = role
        session['user_id'] = account['id']
        session['name'] = account.get('name', account['username'])
        session['dept'] = account.get('dept', 'All')
        flash(f'Welcome, {session["name"]}!', 'success')
        
        if role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif role == 'staff':
            return redirect(url_for('staff_dashboard'))
        else:
            return redirect(url_for('hod_dashboard'))
    else:
        flash('Invalid username or password. Please try again.', 'danger')
        return redirect(url_for('login_view', role=role))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been securely logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/monitoring')
def monitoring_view():
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    recent_attendance = query_db("SELECT * FROM attendance WHERE date = %s ORDER BY id DESC LIMIT 10", (today_str,))
    recent_violations = query_db("SELECT * FROM violations WHERE date = %s ORDER BY id DESC LIMIT 10", (today_str,))
    
    present_cnt = query_db("SELECT COUNT(*) as c FROM attendance WHERE date = %s", (today_str,), one=True)['c']
    viol_cnt = query_db("SELECT COUNT(*) as c FROM violations WHERE date = %s", (today_str,), one=True)['c']
    
    return render_template(
        'monitoring.html',
        recent_attendance=recent_attendance,
        recent_violations=recent_violations,
        present_count=present_cnt,
        violation_count=viol_cnt
    )

_hardware_cam_tested = False
_hardware_cam_available = False

def safe_open_camera():
    global _hardware_cam_tested, _hardware_cam_available
    if _hardware_cam_tested:
        if not _hardware_cam_available:
            return None
    _hardware_cam_tested = True
    try:
        # Use CAP_DSHOW with error suppression
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if cap is not None and cap.isOpened():
            _hardware_cam_available = True
            return cap
        if cap is not None:
            cap.release()
    except Exception:
        pass
    _hardware_cam_available = False
    return None

def generate_video_stream(camera_mode="classroom"):
    """
    Video streaming generator. Gracefully falls back to synthesized surveillance feed
    with steady framerate (25 FPS) without locking up DirectShow hardware camera handles.
    """
    cap = None
    try:
        cap = safe_open_camera()
    except Exception:
        cap = None

    sample_students = query_db("SELECT * FROM register WHERE is_enrolled = 1")
    tick = 0
    
    try:
        while True:
            frame = None
            if cap is not None and cap.isOpened():
                try:
                    ret, cam_frame = cap.read()
                    if ret and cam_frame is not None:
                        frame = cam_frame
                        time.sleep(0.02)
                except Exception:
                    frame = None
            
            # If no physical camera active or in use by browser, generate realistic simulation feed
            if frame is None:
                tick += 1
                frame = np.full((480, 640, 3), 246, dtype=np.uint8)
                
                # Draw realistic corridor / classroom backdrop
                cv2.rectangle(frame, (0, 0), (640, 110), (220, 235, 250), -1)
                cv2.line(frame, (0, 110), (640, 110), (200, 215, 230), 2)
                cv2.rectangle(frame, (50, 120), (200, 410), (232, 240, 252), -1)
                cv2.rectangle(frame, (50, 120), (200, 410), (195, 212, 232), 2)
                cv2.rectangle(frame, (440, 120), (590, 410), (232, 240, 252), -1)
                cv2.rectangle(frame, (440, 120), (590, 410), (195, 212, 232), 2)
                
                # Floor lines
                cv2.line(frame, (0, 410), (640, 410), (210, 222, 236), 2)
                for gx in range(0, 640, 65):
                    cv2.line(frame, (gx, 410), (int(gx * 1.25 - 60), 480), (225, 232, 242), 1)
                
                # Simulated moving student candidate face entering frame
                st_idx = (tick // 50) % len(sample_students) if sample_students else 0
                cur_st = sample_students[st_idx] if sample_students else None
                
                fx = int(270 + 35 * np.sin(tick * 0.08))
                fy = int(180 + 10 * np.cos(tick * 0.08))
                
                # Draw stylized face
                cv2.ellipse(frame, (fx+50, fy+50), (45, 55), 0, 0, 360, (215, 185, 165), -1)
                cv2.circle(frame, (fx+35, fy+40), 6, (40, 30, 30), -1)
                cv2.circle(frame, (fx+65, fy+40), 6, (40, 30, 30), -1)
                cv2.ellipse(frame, (fx+50, fy+75), (15, 6), 0, 0, 180, (40, 30, 30), 2)
                
                # Steady ~25 FPS pacing to prevent 100% CPU runaway
                time.sleep(0.04)
                
            processed_frame, _ = vision_engine.process_frame(frame, camera_mode=camera_mode)
            
            _, buffer = cv2.imencode('.jpg', processed_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    except (GeneratorExit, BrokenPipeError, ConnectionResetError):
        pass
    finally:
        if cap is not None and cap.isOpened():
            try:
                cap.release()
            except Exception:
                pass

@app.route('/video_feed/<mode>')
def video_feed(mode):
    return Response(generate_video_stream(camera_mode=mode),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/recognize_frame', methods=['POST'])
def api_recognize_frame():
    data = request.get_json() or {}
    image_data = data.get('image')
    mode = data.get('mode', 'classroom')
    
    if not image_data:
        return jsonify({'success': False, 'error': 'No image provided'}), 400
        
    try:
        frame = vision_engine.decode_base64_image(image_data)
        processed_frame, detections = vision_engine.process_frame(frame, camera_mode=mode)
        h, w = frame.shape[:2]
        
        return jsonify({
            'success': True,
            'detections': detections,
            'frame_width': int(w),
            'frame_height': int(h),
            'annotated_image': 'data:image/jpeg;base64,' + vision_engine.encode_frame_to_base64(processed_frame)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/simulate_detection', methods=['POST'])
def api_simulate_detection():
    mode = request.args.get('type', 'classroom')
    students = query_db("SELECT * FROM register WHERE is_enrolled = 1")
    if not students:
        return jsonify({'success': False, 'error': 'No enrolled students found.'})
        
    import random
    st = random.choice(students)
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    now_time = datetime.datetime.now().strftime('%I:%M %p')
    
    if mode == 'classroom':
        # Mark present
        query_db("INSERT INTO attendance (student_id, regno, name, dept, sem, date, time, status, confidence, camera_location) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                 (st['id'], st['regno'], st['name'], st['dept'], st.get('year', '3rd Year'), today_str, now_time, 'Present', 98.87, 'Classroom Camera LH-301'), commit=True)
                 
        return jsonify({
            'success': True,
            'frame_width': 640,
            'frame_height': 480,
            'detection': {
                'regno': st['regno'],
                'name': st['name'],
                'dept': st['dept'],
                'time': now_time,
                'status': 'Present',
                'confidence': 98.87,
                'camera': 'Classroom Camera LH-301',
                'color': '#10b981',
                'box': {'x': 190, 'y': 100, 'w': 260, 'h': 260}
            }
        })
    else:
        # Violation
        rel_img = "static/violations/demo_violation_1.jpg"
        reason = "Detected roaming corridor during scheduled lecture hour"
        query_db("INSERT INTO violations (student_id, regno, name, dept, sem, date, time, location, image_path, reason, status, parent_notified) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                 (st['id'], st['regno'], st['name'], st['dept'], st.get('year', '3rd Year'), today_str, now_time, 'Campus Corridor Plaza', rel_img, reason, 'Alert Sent', 1), commit=True)
                 
        msg = f"Dear Parent, your ward {st['name']} ({st['regno']}) was detected roaming outside class at {now_time}. - Principal"
        query_db("INSERT INTO notifications (recipient_type, recipient, subject, message, channel, date_time, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                 ('Parent', st['parent_mob'], 'Class Skipper Alert', msg, 'SMS', f"{today_str} {now_time}", 'Sent'), commit=True)
                 
        return jsonify({
            'success': True,
            'frame_width': 640,
            'frame_height': 480,
            'detection': {
                'regno': st['regno'],
                'name': st['name'],
                'dept': st['dept'],
                'time': now_time,
                'status': 'Class Skipper Violation',
                'confidence': 98.87,
                'camera': 'Campus Corridor Plaza',
                'color': '#ef4444',
                'box': {'x': 190, 'y': 100, 'w': 260, 'h': 260}
            }
        })

@app.route('/api/enroll_face_frames', methods=['POST'])
@login_required('admin')
def api_enroll_face_frames():
    data = request.get_json() or {}
    regno = data.get('regno')
    frames_b64 = data.get('frames', [])
    
    if not regno or not frames_b64:
        return jsonify({'success': False, 'error': 'Missing registration number or frames'}), 400
        
    try:
        decoded_frames = [vision_engine.decode_base64_image(f) for f in frames_b64]
        count = vision_engine.enroll_images(regno, decoded_frames)
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ---------------------------------------------------------
# ADMIN PORTAL CONTROLLERS
# ---------------------------------------------------------
@app.route('/admin/dashboard')
@login_required('admin')
def admin_dashboard():
    total_students = query_db("SELECT COUNT(*) as c FROM register", one=True)['c']
    total_staff = query_db("SELECT COUNT(*) as c FROM staff", one=True)['c']
    total_departments = query_db("SELECT COUNT(*) as c FROM department", one=True)['c']
    
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    today_violations = query_db("SELECT COUNT(*) as c FROM violations WHERE date = %s", (today_str,), one=True)['c']
    
    recent_attendance = query_db("SELECT * FROM attendance WHERE date = %s ORDER BY id DESC LIMIT 5", (today_str,))
    recent_violations = query_db("SELECT * FROM violations WHERE date = %s ORDER BY id DESC LIMIT 5", (today_str,))
    
    return render_template(
        'admin/dashboard.html',
        active_page='dashboard',
        total_students=total_students,
        total_staff=total_staff,
        total_departments=total_departments,
        today_violations=today_violations,
        recent_attendance=recent_attendance,
        recent_violations=recent_violations
    )

@app.route('/admin/departments', methods=['GET', 'POST'])
@login_required('admin')
def admin_departments():
    if request.method == 'POST':
        dept_name = request.form.get('dept_name', '').strip()
        code = request.form.get('code', '').strip().upper()
        if dept_name and code:
            existing = query_db("SELECT * FROM department WHERE code = %s", (code,), one=True)
            if existing:
                flash(f'Department with code {code} already exists.', 'warning')
            else:
                query_db("INSERT INTO department (dept_name, code) VALUES (%s, %s)", (dept_name, code), commit=True)
                flash(f'Department {dept_name} added successfully!', 'success')
        return redirect(url_for('admin_departments'))
        
    departments = query_db("SELECT * FROM department ORDER BY id ASC")
    return render_template('admin/departments.html', active_page='departments', departments=departments)

@app.route('/admin/delete_department/<int:id>')
@login_required('admin')
def admin_delete_department(id):
    query_db("DELETE FROM department WHERE id = %s", (id,), commit=True)
    flash('Department deleted successfully.', 'info')
    return redirect(url_for('admin_departments'))

@app.route('/admin/semesters', methods=['GET', 'POST'])
@login_required('admin')
def admin_semesters():
    if request.method == 'POST':
        sem_name = request.form.get('sem_name', '').strip()
        year = request.form.get('year', '').strip()
        if sem_name:
            query_db("INSERT INTO semester (sem_name, dept_id, year) VALUES (%s, 1, %s)", (sem_name, year), commit=True)
            flash(f'{sem_name} added successfully!', 'success')
        return redirect(url_for('admin_semesters'))
        
    semesters = query_db("SELECT * FROM semester ORDER BY id ASC")
    return render_template('admin/semesters.html', active_page='semesters', semesters=semesters)

@app.route('/admin/delete_semester/<int:id>')
@login_required('admin')
def admin_delete_semester(id):
    query_db("DELETE FROM semester WHERE id = %s", (id,), commit=True)
    flash('Semester removed.', 'info')
    return redirect(url_for('admin_semesters'))

@app.route('/admin/syllabus', methods=['GET', 'POST'])
@login_required('admin')
def admin_syllabus():
    if request.method == 'POST':
        dept = request.form.get('dept')
        sem = request.form.get('sem')
        subject_code = request.form.get('subject_code', '').strip().upper()
        subject_name = request.form.get('subject_name', '').strip()
        if subject_code and subject_name:
            query_db("INSERT INTO syllabus (dept, sem, subject_code, subject_name) VALUES (%s, %s, %s, %s)",
                     (dept, sem, subject_code, subject_name), commit=True)
            flash(f'Subject {subject_name} ({subject_code}) added to syllabus!', 'success')
        return redirect(url_for('admin_syllabus'))

    departments = query_db("SELECT * FROM department ORDER BY id ASC")
    semesters = query_db("SELECT * FROM semester ORDER BY id ASC")
    syllabus_list = query_db("SELECT * FROM syllabus ORDER BY id DESC")
    return render_template(
        'admin/syllabus.html',
        active_page='syllabus',
        departments=departments,
        semesters=semesters,
        syllabus_list=syllabus_list
    )

@app.route('/admin/delete_syllabus/<int:id>')
@login_required('admin')
def admin_delete_syllabus(id):
    query_db("DELETE FROM syllabus WHERE id = %s", (id,), commit=True)
    flash('Subject removed from syllabus.', 'info')
    return redirect(url_for('admin_syllabus'))

@app.route('/admin/students', methods=['GET', 'POST'])
@login_required('admin')
def admin_students():
    if request.method == 'POST':
        name = request.form.get('name')
        regno = request.form.get('regno')
        mobile = request.form.get('mobile')
        parent_mob = request.form.get('parent_mob')
        email = request.form.get('email')
        address = request.form.get('address')
        aadhar = request.form.get('aadhar')
        dept = request.form.get('dept')
        year = request.form.get('year')
        
        existing = query_db("SELECT * FROM register WHERE regno = %s", (regno,), one=True)
        if existing:
            flash(f'Student with Reg No {regno} is already registered.', 'warning')
        else:
            query_db("INSERT INTO register (name, mobile, email, address, aadhar, regno, dept, year, parent_mob) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                     (name, mobile, email, address, aadhar, regno, dept, year, parent_mob), commit=True)
            flash(f'Student {name} registered! Please proceed to enroll their facial biometrics.', 'success')
            return redirect(url_for('admin_enroll_face', regno=regno))
            
        return redirect(url_for('admin_students'))

    departments = query_db("SELECT * FROM department ORDER BY id ASC")
    students = query_db("SELECT * FROM register ORDER BY id DESC")
    return render_template('admin/students.html', active_page='students', departments=departments, students=students)

@app.route('/admin/delete_student/<int:id>')
@login_required('admin')
def admin_delete_student(id):
    query_db("DELETE FROM register WHERE id = %s", (id,), commit=True)
    flash('Student record deleted.', 'info')
    return redirect(url_for('admin_students'))

@app.route('/admin/enroll_face')
@login_required('admin')
def admin_enroll_face():
    selected_regno = request.args.get('regno', '')
    students = query_db("SELECT * FROM register ORDER BY id ASC")
    enrolled_count = query_db("SELECT COUNT(*) as c FROM register WHERE is_enrolled = 1", one=True)['c']
    
    return render_template(
        'admin/enroll_face.html',
        active_page='enroll_face',
        students=students,
        selected_regno=selected_regno,
        enrolled_students_count=enrolled_count
    )

@app.route('/admin/enroll_face_upload', methods=['POST'])
@login_required('admin')
def admin_enroll_face_upload():
    regno = request.form.get('regno')
    files = request.files.getlist('photos')
    
    if not regno or not files:
        flash('Please select a student and upload at least one image file.', 'warning')
        return redirect(url_for('admin_enroll_face'))
        
    student_dir = os.path.join(config.DATASET_DIR, str(regno))
    os.makedirs(student_dir, exist_ok=True)
    
    saved = 0
    for f in files:
        if f.filename:
            path = os.path.join(student_dir, f"upload_{int(datetime.datetime.now().timestamp()*1000)}_{f.filename}")
            f.save(path)
            saved += 1
            
    query_db("UPDATE register SET is_enrolled = 1 WHERE regno = %s", (regno,), commit=True)
    vision_engine.train_model()
    flash(f'Uploaded {saved} face photos for Reg No {regno}. Model retrained successfully!', 'success')
    return redirect(url_for('admin_enroll_face', regno=regno))

@app.route('/admin/retrain_model', methods=['POST'])
@login_required('admin')
def admin_retrain_model():
    success, count = vision_engine.train_model()
    if success:
        flash(f'Facial model trained successfully on {count} samples across enrolled students.', 'success')
    else:
        flash('Could not train model: dataset directory is empty.', 'warning')
    return redirect(url_for('admin_enroll_face'))

@app.route('/admin/staff', methods=['GET', 'POST'])
@login_required('admin')
def admin_staff():
    if request.method == 'POST':
        staff_id = request.form.get('staff_id')
        name = request.form.get('name')
        dept = request.form.get('dept')
        designation = request.form.get('designation')
        email = request.form.get('email')
        mobile = request.form.get('mobile')
        username = request.form.get('username')
        password = request.form.get('password')
        
        query_db("INSERT INTO staff (staff_id, name, email, mobile, dept, designation, username, password) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                 (staff_id, name, email, mobile, dept, designation, username, password), commit=True)
        flash(f'Faculty staff {name} added!', 'success')
        return redirect(url_for('admin_staff'))

    departments = query_db("SELECT * FROM department ORDER BY id ASC")
    staff_list = query_db("SELECT * FROM staff ORDER BY id DESC")
    return render_template('admin/staff.html', active_page='staff', departments=departments, staff_list=staff_list)

@app.route('/admin/delete_staff/<int:id>')
@login_required('admin')
def admin_delete_staff(id):
    query_db("DELETE FROM staff WHERE id = %s", (id,), commit=True)
    flash('Faculty staff removed.', 'info')
    return redirect(url_for('admin_staff'))

@app.route('/admin/credentials')
@login_required('admin')
def admin_credentials():
    hod_list = query_db("SELECT * FROM hod ORDER BY id ASC")
    staff_list = query_db("SELECT * FROM staff ORDER BY id ASC")
    return render_template('admin/credentials.html', active_page='credentials', hod_list=hod_list, staff_list=staff_list)

@app.route('/admin/update_credential', methods=['POST'])
@login_required('admin')
def admin_update_credential():
    user_type = request.form.get('user_type')
    user_id = request.form.get('user_id')
    new_password = request.form.get('new_password', '').strip()
    
    if new_password:
        if user_type == 'hod':
            query_db("UPDATE hod SET password = %s WHERE id = %s", (new_password, user_id), commit=True)
        else:
            query_db("UPDATE staff SET password = %s WHERE id = %s", (new_password, user_id), commit=True)
        flash('Password updated successfully.', 'success')
    return redirect(url_for('admin_credentials'))

@app.route('/admin/timetable', methods=['GET', 'POST'])
@login_required('admin')
def admin_timetable():
    if request.method == 'POST':
        day_name = request.form.get('day_name')
        period = request.form.get('period')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        dept = request.form.get('dept')
        sem = request.form.get('sem')
        subject = request.form.get('subject')
        staff_name = request.form.get('staff_name')
        room = request.form.get('room', 'LH-301')
        
        query_db("INSERT INTO timetable (dept, sem, day_name, period, start_time, end_time, subject, staff_name, room) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                 (dept, sem, day_name, period, start_time, end_time, subject, staff_name, room), commit=True)
        flash(f'Timetable schedule slot added for {day_name} ({period})!', 'success')
        return redirect(url_for('admin_timetable'))

    departments = query_db("SELECT * FROM department ORDER BY id ASC")
    semesters = query_db("SELECT * FROM semester ORDER BY id ASC")
    timetable_list = query_db("SELECT * FROM timetable ORDER BY id DESC")
    return render_template(
        'admin/timetable.html',
        active_page='timetable',
        departments=departments,
        semesters=semesters,
        timetable_list=timetable_list
    )

@app.route('/admin/delete_timetable/<int:id>')
@login_required('admin')
def admin_delete_timetable(id):
    query_db("DELETE FROM timetable WHERE id = %s", (id,), commit=True)
    flash('Timetable period deleted.', 'info')
    return redirect(url_for('admin_timetable'))

@app.route('/admin/attendance')
@login_required('admin')
def admin_attendance():
    dept = request.args.get('dept', 'All')
    sem = request.args.get('sem', 'All')
    date_val = request.args.get('date', datetime.date.today().strftime('%Y-%m-%d'))
    
    sql = "SELECT * FROM attendance WHERE 1=1"
    params = []
    
    if dept != 'All':
        sql += " AND dept = %s"
        params.append(dept)
    if sem != 'All':
        sql += " AND sem = %s"
        params.append(sem)
    if date_val:
        sql += " AND date = %s"
        params.append(date_val)
        
    sql += " ORDER BY id DESC"
    records = query_db(sql, tuple(params))
    
    departments = query_db("SELECT * FROM department ORDER BY id ASC")
    semesters = query_db("SELECT * FROM semester ORDER BY id ASC")
    
    return render_template(
        'admin/attendance.html',
        active_page='attendance',
        attendance_records=records,
        departments=departments,
        semesters=semesters,
        selected_dept=dept,
        selected_sem=sem,
        selected_date=date_val
    )

@app.route('/admin/export_attendance')
@login_required('admin')
def admin_export_attendance():
    dept = request.args.get('dept', 'All')
    sem = request.args.get('sem', 'All')
    date_val = request.args.get('date', '')
    from_date = request.args.get('from_date', '')
    to_date = request.args.get('to_date', '')
    export_format = request.args.get('format', 'excel')
    
    sql = "SELECT id, regno, name, dept, sem, date, time, status, confidence, camera_location FROM attendance WHERE 1=1"
    params = []
    
    if dept != 'All' and dept:
        sql += " AND dept = %s"
        params.append(dept)
    if sem != 'All' and sem:
        sql += " AND sem = %s"
        params.append(sem)
    if date_val:
        sql += " AND date = %s"
        params.append(date_val)
    if from_date and to_date:
        sql += " AND date BETWEEN %s AND %s"
        params.extend([from_date, to_date])
        
    sql += " ORDER BY id DESC"
    records = query_db(sql, tuple(params))
    
    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(columns=['id', 'regno', 'name', 'dept', 'sem', 'date', 'time', 'status', 'confidence', 'camera_location'])
        
    df.rename(columns={
        'id': 'Log ID',
        'regno': 'Register Number',
        'name': 'Student Name',
        'dept': 'Department',
        'sem': 'Semester',
        'date': 'Attendance Date',
        'time': 'Timestamp',
        'status': 'Status',
        'confidence': 'AI Accuracy (%)',
        'camera_location': 'Camera Source'
    }, inplace=True)
    
    output = io.BytesIO()
    if export_format == 'csv':
        df.to_csv(output, index=False)
        output.seek(0)
        return send_file(output, mimetype='text/csv', as_attachment=True, download_name=f"attendance_report_{datetime.date.today()}.csv")
    else:
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Attendance Records')
        output.seek(0)
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=f"attendance_report_{datetime.date.today()}.xlsx")

@app.route('/admin/reports')
@login_required('admin')
def admin_reports():
    dept = request.args.get('dept', 'All')
    from_date = request.args.get('from_date', (datetime.date.today() - datetime.timedelta(days=7)).strftime('%Y-%m-%d'))
    to_date = request.args.get('to_date', datetime.date.today().strftime('%Y-%m-%d'))
    
    sql_att = "SELECT COUNT(*) as c FROM attendance WHERE date BETWEEN %s AND %s"
    sql_viol = "SELECT COUNT(*) as c FROM violations WHERE date BETWEEN %s AND %s"
    params = [from_date, to_date]
    
    if dept != 'All':
        sql_att += " AND dept = %s"
        sql_viol += " AND dept = %s"
        params.append(dept)
        
    total_att = query_db(sql_att, tuple(params), one=True)['c']
    total_viol = query_db(sql_viol, tuple(params), one=True)['c']
    total_notifs = query_db("SELECT COUNT(*) as c FROM notifications", one=True)['c']
    
    departments = query_db("SELECT * FROM department ORDER BY id ASC")
    
    total_records = max(1, total_att + total_viol)
    avg_pct = round((total_att / total_records) * 100, 1)
    
    return render_template(
        'admin/reports.html',
        active_page='reports',
        departments=departments,
        selected_dept=dept,
        from_date=from_date,
        to_date=to_date,
        total_attendance_count=total_att,
        total_violations_count=total_viol,
        avg_attendance_pct=avg_pct,
        total_notifications_sent=total_notifs
    )

@app.route('/admin/notifications', methods=['GET', 'POST'])
@login_required('admin')
def admin_notifications():
    if request.method == 'POST':
        recipient_type = request.form.get('recipient_type')
        recipient = request.form.get('recipient')
        channel = request.form.get('channel')
        subject = request.form.get('subject')
        message = request.form.get('message')
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        query_db("INSERT INTO notifications (recipient_type, recipient, subject, message, channel, date_time, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                 (recipient_type, recipient, subject, message, channel, now_str, 'Sent'), commit=True)
        flash(f'Notification sent via {channel} to {recipient}!', 'success')
        return redirect(url_for('admin_notifications'))
        
    notifs = query_db("SELECT * FROM notifications ORDER BY id DESC")
    return render_template('admin/notifications.html', active_page='notifications', notifications_list=notifs)

# ---------------------------------------------------------
# STAFF PORTAL CONTROLLERS
# ---------------------------------------------------------
@app.route('/staff/dashboard')
@login_required('staff')
def staff_dashboard():
    staff_info = query_db("SELECT * FROM staff WHERE username = %s", (session['username'],), one=True)
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    
    my_timetable = query_db("SELECT * FROM timetable WHERE staff_name LIKE %s", (f"%{staff_info['name'].split()[-1]}%",))
    assigned_count = len(my_timetable)
    
    present_cnt = query_db("SELECT COUNT(*) as c FROM attendance WHERE date = %s AND dept = %s", (today_str, staff_info['dept']), one=True)['c']
    skipper_cnt = query_db("SELECT COUNT(*) as c FROM violations WHERE date = %s AND dept = %s", (today_str, staff_info['dept']), one=True)['c']
    my_skippers = query_db("SELECT * FROM violations WHERE date = %s AND dept = %s ORDER BY id DESC LIMIT 5", (today_str, staff_info['dept']))
    
    return render_template(
        'staff/dashboard.html',
        active_page='dashboard',
        staff_info=staff_info,
        assigned_classes_count=assigned_count,
        present_count=present_cnt,
        skipper_count=skipper_cnt,
        my_timetable=my_timetable,
        my_skippers=my_skippers
    )

@app.route('/staff/timetable')
@login_required('staff')
def staff_timetable():
    staff_info = query_db("SELECT * FROM staff WHERE username = %s", (session['username'],), one=True)
    my_tt = query_db("SELECT * FROM timetable WHERE staff_name LIKE %s OR dept = %s", (f"%{staff_info['name'].split()[-1]}%", staff_info['dept']))
    return render_template('staff/timetable.html', active_page='timetable', my_timetable=my_tt)

@app.route('/staff/attendance')
@login_required('staff')
def staff_attendance():
    staff_info = query_db("SELECT * FROM staff WHERE username = %s", (session['username'],), one=True)
    sem = request.args.get('sem', 'All')
    date_val = request.args.get('date', datetime.date.today().strftime('%Y-%m-%d'))
    
    sql = "SELECT * FROM attendance WHERE dept = %s"
    params = [staff_info['dept']]
    if sem != 'All':
        sql += " AND sem = %s"
        params.append(sem)
    if date_val:
        sql += " AND date = %s"
        params.append(date_val)
    sql += " ORDER BY id DESC"
    
    records = query_db(sql, tuple(params))
    semesters = query_db("SELECT * FROM semester ORDER BY id ASC")
    
    return render_template(
        'staff/attendance.html',
        active_page='attendance',
        attendance_records=records,
        semesters=semesters,
        selected_sem=sem,
        selected_date=date_val
    )

@app.route('/staff/skippers')
@login_required('staff')
def staff_skippers():
    staff_info = query_db("SELECT * FROM staff WHERE username = %s", (session['username'],), one=True)
    skippers = query_db("SELECT * FROM violations WHERE dept = %s ORDER BY id DESC", (staff_info['dept'],))
    return render_template('staff/skippers.html', active_page='skippers', skippers_list=skippers)

@app.route('/staff/roaming_images')
@login_required('staff')
def staff_roaming_images():
    staff_info = query_db("SELECT * FROM staff WHERE username = %s", (session['username'],), one=True)
    roaming = query_db("SELECT * FROM violations WHERE dept = %s ORDER BY id DESC", (staff_info['dept'],))
    return render_template('staff/roaming_images.html', active_page='roaming_images', roaming_images=roaming)

# ---------------------------------------------------------
# HOD PORTAL CONTROLLERS
# ---------------------------------------------------------
@app.route('/hod/dashboard')
@login_required('hod')
def hod_dashboard():
    hod_info = query_db("SELECT * FROM hod WHERE username = %s", (session['username'],), one=True)
    dept = hod_info['dept']
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    
    dept_students_count = query_db("SELECT COUNT(*) as c FROM register WHERE dept = %s", (dept,), one=True)['c']
    dept_present_count = query_db("SELECT COUNT(*) as c FROM attendance WHERE date = %s AND dept = %s", (today_str, dept), one=True)['c']
    dept_skipper_count = query_db("SELECT COUNT(*) as c FROM violations WHERE date = %s AND dept = %s", (today_str, dept), one=True)['c']
    alerts_sent_count = query_db("SELECT COUNT(*) as c FROM notifications WHERE recipient_type = 'Parent'", one=True)['c']
    
    recent_attendance = query_db("SELECT * FROM attendance WHERE date = %s AND dept = %s ORDER BY id DESC LIMIT 5", (today_str, dept))
    recent_violations = query_db("SELECT * FROM violations WHERE date = %s AND dept = %s ORDER BY id DESC LIMIT 5", (today_str, dept))
    
    return render_template(
        'hod/dashboard.html',
        active_page='dashboard',
        hod_info=hod_info,
        dept_students_count=dept_students_count,
        dept_present_count=dept_present_count,
        dept_skipper_count=dept_skipper_count,
        alerts_sent_count=alerts_sent_count,
        recent_attendance=recent_attendance,
        recent_violations=recent_violations
    )

@app.route('/hod/timetable')
@login_required('hod')
def hod_timetable():
    hod_info = query_db("SELECT * FROM hod WHERE username = %s", (session['username'],), one=True)
    dept_tt = query_db("SELECT * FROM timetable WHERE dept = %s ORDER BY id ASC", (hod_info['dept'],))
    return render_template('hod/timetable.html', active_page='timetable', hod_info=hod_info, dept_timetable=dept_tt)

@app.route('/hod/attendance')
@login_required('hod')
def hod_attendance():
    hod_info = query_db("SELECT * FROM hod WHERE username = %s", (session['username'],), one=True)
    sem = request.args.get('sem', 'All')
    date_val = request.args.get('date', datetime.date.today().strftime('%Y-%m-%d'))
    
    sql = "SELECT * FROM attendance WHERE dept = %s"
    params = [hod_info['dept']]
    if sem != 'All':
        sql += " AND sem = %s"
        params.append(sem)
    if date_val:
        sql += " AND date = %s"
        params.append(date_val)
    sql += " ORDER BY id DESC"
    
    records = query_db(sql, tuple(params))
    semesters = query_db("SELECT * FROM semester ORDER BY id ASC")
    
    return render_template(
        'hod/attendance.html',
        active_page='attendance',
        hod_info=hod_info,
        attendance_records=records,
        semesters=semesters,
        selected_sem=sem,
        selected_date=date_val
    )

@app.route('/hod/export_attendance')
@login_required('hod')
def hod_export_attendance():
    hod_info = query_db("SELECT * FROM hod WHERE username = %s", (session['username'],), one=True)
    records = query_db("SELECT id, regno, name, dept, sem, date, time, status, confidence, camera_location FROM attendance WHERE dept = %s ORDER BY id DESC", (hod_info['dept'],))
    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(columns=['id', 'regno', 'name', 'dept', 'sem', 'date', 'time', 'status', 'confidence', 'camera_location'])
        
    df.rename(columns={
        'id': 'Log ID',
        'regno': 'Register Number',
        'name': 'Student Name',
        'dept': 'Department',
        'sem': 'Semester',
        'date': 'Attendance Date',
        'time': 'Timestamp',
        'status': 'Status',
        'confidence': 'AI Accuracy (%)',
        'camera_location': 'Camera Source'
    }, inplace=True)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=f"{hod_info['dept']} Attendance")
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=f"{hod_info['dept']}_attendance_{datetime.date.today()}.xlsx")

@app.route('/hod/skippers')
@login_required('hod')
def hod_skippers():
    hod_info = query_db("SELECT * FROM hod WHERE username = %s", (session['username'],), one=True)
    skippers = query_db("SELECT * FROM violations WHERE dept = %s ORDER BY id DESC", (hod_info['dept'],))
    return render_template('hod/skippers.html', active_page='skippers', hod_info=hod_info, skippers_list=skippers)

@app.route('/hod/roaming_images')
@login_required('hod')
def hod_roaming_images():
    hod_info = query_db("SELECT * FROM hod WHERE username = %s", (session['username'],), one=True)
    roaming = query_db("SELECT * FROM violations WHERE dept = %s ORDER BY id DESC", (hod_info['dept'],))
    return render_template('hod/roaming_images.html', active_page='roaming_images', hod_info=hod_info, roaming_images=roaming)

@app.route('/hod/send_sms', methods=['GET', 'POST'])
@login_required('hod')
def hod_send_sms():
    hod_info = query_db("SELECT * FROM hod WHERE username = %s", (session['username'],), one=True)
    
    if request.method == 'POST':
        parent_mob = request.form.get('parent_mob')
        message = request.form.get('message')
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        query_db("INSERT INTO notifications (recipient_type, recipient, subject, message, channel, date_time, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                 ('Parent', parent_mob, f"Disciplinary Notice from HoD ({hod_info['dept']})", message, 'SMS', now_str, 'Sent'), commit=True)
        flash(f'Disciplinary SMS alert successfully dispatched to {parent_mob}!', 'success')
        return redirect(url_for('hod_skippers'))

    selected_regno = request.args.get('regno', '')
    dept_students = query_db("SELECT * FROM register WHERE dept = %s ORDER BY name ASC", (hod_info['dept'],))
    default_parent = ''
    if selected_regno:
        st = query_db("SELECT parent_mob FROM register WHERE regno = %s", (selected_regno,), one=True)
        if st:
            default_parent = st['parent_mob']

    return render_template(
        'hod/send_sms.html',
        active_page='send_sms',
        hod_info=hod_info,
        dept_students=dept_students,
        selected_regno=selected_regno,
        default_parent_mob=default_parent
    )

# ---------------------------------------------------------
# APPLICATION ENTRYPOINT
# ---------------------------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"===========================================================")
    print(f" CLASS SKIPPER - AI College Surveillance System")
    print(f" Running at http://127.0.0.1:{port}")
    print(f"===========================================================")
    app.run(host='0.0.0.0', port=port, debug=True)
