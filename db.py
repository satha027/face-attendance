import sqlite3
import os
from config import DATABASE_TYPE, SQLITE_DB_PATH, MYSQL_CONFIG

def get_connection():
    if DATABASE_TYPE == 'mysql':
        try:
            import mysql.connector
            conn = mysql.connector.connect(**MYSQL_CONFIG)
            return conn, 'mysql'
        except Exception:
            # Fallback to SQLite if MySQL is unavailable
            conn = sqlite3.connect(SQLITE_DB_PATH)
            conn.row_factory = sqlite3.Row
            return conn, 'sqlite'
    else:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn, 'sqlite'

def query_db(query, args=(), one=False, commit=False):
    conn, db_type = get_connection()
    cursor = conn.cursor()
    
    # Handle placeholder syntax: mysql uses %s, sqlite uses ?
    if db_type == 'sqlite':
        query = query.replace('%s', '?')
    else:
        query = query.replace('?', '%s')
        
    cursor.execute(query, args)
    
    if commit:
        conn.commit()
        last_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return last_id

    rv = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if rv:
        # Normalize rows to dictionaries
        if db_type == 'sqlite':
            results = [dict(ix) for ix in rv]
        else:
            # mysql with dictionary cursor or tuple
            results = [dict(ix) if isinstance(ix, dict) else ix for ix in rv]
        return results[0] if one else results
    return None if one else []

def init_db():
    conn, db_type = get_connection()
    cursor = conn.cursor()
    
    tables = [
        """
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(100) NOT NULL,
            email VARCHAR(100) DEFAULT 'admin@college.edu'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS department (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dept_name VARCHAR(150) NOT NULL,
            code VARCHAR(20) UNIQUE NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS semester (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sem_name VARCHAR(50) NOT NULL,
            dept_id INTEGER,
            year VARCHAR(20)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS syllabus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dept VARCHAR(100) NOT NULL,
            sem VARCHAR(50) NOT NULL,
            subject_code VARCHAR(30) NOT NULL,
            subject_name VARCHAR(150) NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS register (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(150) NOT NULL,
            mobile VARCHAR(30) NOT NULL,
            email VARCHAR(100) NOT NULL,
            address TEXT,
            aadhar VARCHAR(30),
            regno VARCHAR(50) UNIQUE NOT NULL,
            dept VARCHAR(100) NOT NULL,
            year VARCHAR(30) NOT NULL,
            parent_mob VARCHAR(30) NOT NULL,
            photo_path VARCHAR(255) DEFAULT '',
            is_enrolled INTEGER DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(150) NOT NULL,
            email VARCHAR(100) NOT NULL,
            mobile VARCHAR(30) NOT NULL,
            dept VARCHAR(100) NOT NULL,
            designation VARCHAR(100) DEFAULT 'Assistant Professor',
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(100) NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS hod (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hod_id VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(150) NOT NULL,
            email VARCHAR(100) NOT NULL,
            mobile VARCHAR(30) NOT NULL,
            dept VARCHAR(100) NOT NULL,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(100) NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dept VARCHAR(100) NOT NULL,
            sem VARCHAR(50) NOT NULL,
            day_name VARCHAR(30) NOT NULL,
            period VARCHAR(20) NOT NULL,
            start_time VARCHAR(20) NOT NULL,
            end_time VARCHAR(20) NOT NULL,
            subject VARCHAR(150) NOT NULL,
            staff_name VARCHAR(150) NOT NULL,
            room VARCHAR(50) DEFAULT 'LH-101'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            regno VARCHAR(50) NOT NULL,
            name VARCHAR(150) NOT NULL,
            dept VARCHAR(100) NOT NULL,
            sem VARCHAR(50) NOT NULL,
            date VARCHAR(30) NOT NULL,
            time VARCHAR(30) NOT NULL,
            status VARCHAR(30) DEFAULT 'Present',
            confidence REAL DEFAULT 98.8,
            camera_location VARCHAR(100) DEFAULT 'Classroom Camera'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS violations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            regno VARCHAR(50) NOT NULL,
            name VARCHAR(150) NOT NULL,
            dept VARCHAR(100) NOT NULL,
            sem VARCHAR(50) NOT NULL,
            date VARCHAR(30) NOT NULL,
            time VARCHAR(30) NOT NULL,
            location VARCHAR(100) NOT NULL,
            image_path VARCHAR(255) NOT NULL,
            reason VARCHAR(255) DEFAULT 'Found roaming outside classroom during class hours',
            status VARCHAR(50) DEFAULT 'Alert Sent',
            parent_notified INTEGER DEFAULT 1
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_type VARCHAR(50) NOT NULL,
            recipient VARCHAR(100) NOT NULL,
            subject VARCHAR(150) NOT NULL,
            message TEXT NOT NULL,
            channel VARCHAR(30) DEFAULT 'SMS',
            date_time VARCHAR(50) NOT NULL,
            status VARCHAR(30) DEFAULT 'Sent'
        )
        """
    ]
    
    for t in tables:
        cursor.execute(t)
        
    conn.commit()
    cursor.close()
    conn.close()
    seed_demo_data()

def seed_demo_data():
    # Admin
    existing_admin = query_db("SELECT * FROM admin WHERE username = %s", ('admin',), one=True)
    if not existing_admin:
        query_db("INSERT INTO admin (username, password, email) VALUES (%s, %s, %s)",
                 ('admin', 'admin123', 'admin@collegesurveillance.edu'), commit=True)
                 
    # Departments
    depts = [
        ('Computer Science and Engineering', 'CSE'),
        ('Information Technology', 'IT'),
        ('Electronics and Communication Engineering', 'ECE'),
        ('Mechanical Engineering', 'MECH')
    ]
    for name, code in depts:
        if not query_db("SELECT * FROM department WHERE code = %s", (code,), one=True):
            query_db("INSERT INTO department (dept_name, code) VALUES (%s, %s)", (name, code), commit=True)
            
    # Semesters
    for i in range(1, 9):
        sem_name = f"Semester {i}"
        if not query_db("SELECT * FROM semester WHERE sem_name = %s", (sem_name,), one=True):
            query_db("INSERT INTO semester (sem_name, dept_id, year) VALUES (%s, %s, %s)", 
                     (sem_name, 1, f"Year {(i+1)//2}"), commit=True)
                     
    # Syllabus / Subjects
    sample_subjects = [
        ('CSE', 'Semester 6', 'CS8601', 'Artificial Intelligence & Deep Learning'),
        ('CSE', 'Semester 6', 'CS8602', 'Compiler Design'),
        ('CSE', 'Semester 6', 'CS8603', 'Distributed Systems & Cloud Computing'),
        ('IT', 'Semester 6', 'IT8601', 'Computer Vision and Biometrics'),
        ('ECE', 'Semester 6', 'EC8601', 'Digital Signal Processing')
    ]
    for dept, sem, code, sname in sample_subjects:
        if not query_db("SELECT * FROM syllabus WHERE subject_code = %s", (code,), one=True):
            query_db("INSERT INTO syllabus (dept, sem, subject_code, subject_name) VALUES (%s, %s, %s, %s)",
                     (dept, sem, code, sname), commit=True)
                     
    # HoD
    if not query_db("SELECT * FROM hod WHERE username = %s", ('hod_ece',), one=True):
        query_db("INSERT INTO hod (hod_id, name, email, mobile, dept, username, password) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                 ('HOD-ECE-01', 'Dr. S. K. Narayanan (ECE)', 'hod.ece@college.edu', '+91 9845012345', 'ECE', 'hod_ece', 'hod123'), commit=True)
                 
    # Staff
    if not query_db("SELECT * FROM staff WHERE username = %s", ('staff_ece',), one=True):
        query_db("INSERT INTO staff (staff_id, name, email, mobile, dept, designation, username, password) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                 ('STF-ECE-101', 'Prof. Rajesh Kumar (ECE)', 'rajesh.ece@college.edu', '+91 9845023456', 'ECE', 'Assistant Professor - ECE', 'staff_ece', 'staff123'), commit=True)
    if not query_db("SELECT * FROM staff WHERE username = %s", ('staff_raj',), one=True):
        query_db("INSERT INTO staff (staff_id, name, email, mobile, dept, designation, username, password) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                 ('STF-101', 'Prof. Rajesh Kumar', 'rajesh.k@college.edu', '+91 9845023456', 'ECE', 'Assistant Professor', 'staff_raj', 'staff123'), commit=True)
    if not query_db("SELECT * FROM staff WHERE username = %s", ('staff_priya',), one=True):
        query_db("INSERT INTO staff (staff_id, name, email, mobile, dept, designation, username, password) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                 ('STF-102', 'Dr. Priya Varma', 'priya.v@college.edu', '+91 9845034567', 'ECE', 'Associate Professor', 'staff_priya', 'staff123'), commit=True)

    # Students (Register) - All assigned to ECE Department
    sample_students = [
        ('Indhumathi R', '+91 9876543210', 'indhu.ece@college.edu', '24, Rose Garden, Chennai', '4521-7890-1234', '91001', 'ECE', '3rd Year', '+91 9444123450'),
        ('Aravind Swamy', '+91 9876543211', 'aravind.ece@college.edu', '12, Anna Nagar, Chennai', '4521-7890-1235', '91002', 'ECE', '3rd Year', '+91 9444123451'),
        ('Deepika Mohan', '+91 9876543212', 'deepika.ece@college.edu', '88, Gandhi Road, Salem', '4521-7890-1236', '91003', 'ECE', '3rd Year', '+91 9444123452'),
        ('Karthik Raja', '+91 9876543213', 'karthik.ece@college.edu', '15, Temple Street, Madurai', '4521-7890-1237', '91004', 'ECE', '3rd Year', '+91 9444123453'),
        ('Sneha Balaji', '+91 9876543214', 'sneha.ece@college.edu', '05, Lake View, Coimbatore', '4521-7890-1238', '91005', 'ECE', '3rd Year', '+91 9444123454')
    ]
    for name, mob, email, addr, aadhar, regno, dept, yr, pmob in sample_students:
        if not query_db("SELECT * FROM register WHERE regno = %s", (regno,), one=True):
            query_db("INSERT INTO register (name, mobile, email, address, aadhar, regno, dept, year, parent_mob, is_enrolled) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1)",
                     (name, mob, email, addr, aadhar, regno, dept, yr, pmob), commit=True)

    # Timetable
    sample_tt = [
        ('CSE', 'Semester 6', 'Monday', 'Period 1', '09:00 AM', '10:00 AM', 'Artificial Intelligence & Deep Learning', 'Prof. Rajesh Kumar', 'LH-301'),
        ('ECE', 'Semester 6', 'Monday', 'Period 1', '09:00 AM', '10:00 AM', 'Digital Signal Processing', 'Prof. Rajesh Kumar (ECE)', 'LH-301'),
        ('ECE', 'Semester 6', 'Monday', 'Period 2', '10:00 AM', '11:00 AM', 'VLSI Design & Microelectronics', 'Prof. Rajesh Kumar (ECE)', 'LH-301'),
        ('ECE', 'Semester 6', 'Monday', 'Period 3', '11:15 AM', '12:15 PM', 'Embedded Systems & IoT', 'Dr. Priya Varma', 'LH-301'),
        ('ECE', 'Semester 6', 'Tuesday', 'Period 1', '09:00 AM', '10:00 AM', 'Embedded Systems & IoT', 'Dr. Priya Varma', 'LH-301'),
        ('ECE', 'Semester 6', 'Tuesday', 'Period 2', '10:00 AM', '11:00 AM', 'Digital Signal Processing', 'Prof. Rajesh Kumar (ECE)', 'LH-301'),
        ('ECE', 'Semester 6', 'Wednesday', 'Period 1', '09:00 AM', '10:00 AM', 'AI & Computer Vision for ECE', 'Prof. Rajesh Kumar (ECE)', 'LH-301')
    ]
    for dept, sem, day, per, st, et, sub, stf, rm in sample_tt:
        if not query_db("SELECT * FROM timetable WHERE dept = %s AND day_name = %s AND period = %s", (dept, day, per), one=True):
            query_db("INSERT INTO timetable (dept, sem, day_name, period, start_time, end_time, subject, staff_name, room) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                     (dept, sem, day, per, st, et, sub, stf, rm), commit=True)

    # Initial Attendance records
    if not query_db("SELECT * FROM attendance LIMIT 1"):
        import datetime
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        now_time = "09:05 AM"
        query_db("INSERT INTO attendance (student_id, regno, name, dept, sem, date, time, status, confidence, camera_location) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                 (1, '91001', 'Indhumathi R', 'ECE', 'Semester 6', today_str, now_time, 'Present', 99.2, 'Classroom Camera LH-301'), commit=True)
        query_db("INSERT INTO attendance (student_id, regno, name, dept, sem, date, time, status, confidence, camera_location) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                 (3, '91003', 'Deepika Mohan', 'ECE', 'Semester 6', today_str, now_time, 'Present', 98.7, 'Classroom Camera LH-301'), commit=True)
        query_db("INSERT INTO attendance (student_id, regno, name, dept, sem, date, time, status, confidence, camera_location) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                 (5, '91005', 'Sneha Balaji', 'ECE', 'Semester 6', today_str, now_time, 'Present', 98.4, 'Classroom Camera LH-301'), commit=True)

    # Initial Violations (Class Skipper)
    if not query_db("SELECT * FROM violations LIMIT 1"):
        import datetime
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        query_db("INSERT INTO violations (student_id, regno, name, dept, sem, date, time, location, image_path, reason, status, parent_notified) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                 (4, '91004', 'Karthik Raja', 'ECE', 'Semester 6', today_str, '09:22 AM', 'College Canteen Corridor', 'static/violations/demo_violation_1.jpg', 'Found roaming during DSP class hour', 'Alert Sent', 1), commit=True)
        query_db("INSERT INTO violations (student_id, regno, name, dept, sem, date, time, location, image_path, reason, status, parent_notified) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                 (2, '91002', 'Aravind Swamy', 'ECE', 'Semester 6', today_str, '10:15 AM', 'Campus Ground Plaza', 'static/violations/demo_violation_2.jpg', 'Skipped Period 2 VLSI class', 'Alert Sent', 1), commit=True)

    # Initial Notifications
    if not query_db("SELECT * FROM notifications LIMIT 1"):
        import datetime
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query_db("INSERT INTO notifications (recipient_type, recipient, subject, message, channel, date_time, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                 ('Parent', '+91 9444123453', 'Class Absence & Campus Violation Notice', 'Dear Parent, your ward Karthik Raja (91004) was detected roaming outside the classroom during class hours at 09:22 AM. - Principal', 'SMS', now_str, 'Sent'), commit=True)
        query_db("INSERT INTO notifications (recipient_type, recipient, subject, message, channel, date_time, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                 ('HoD', 'hod.cse@college.edu', 'Violation Alert: Student Roaming Campus', 'Student Aravind Swamy (91002) detected by Campus Ground Camera at 10:15 AM during Period 2.', 'Email', now_str, 'Sent'), commit=True)
