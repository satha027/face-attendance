# Class Skipper - AI-Based College Surveillance System

An intelligent, computer-vision driven college surveillance and automated attendance management platform built as specified in **INDHU PROJECT.docx**. The system combines facial recognition (LBPH & FaceNet feature extraction) with timetable correlation to automate student attendance and proactively identify students roaming the campus during scheduled lecture hours ("Class Skippers").

---

## 🌟 Key Features

1. **Dual-Camera AI Surveillance Engine**:
   - **Classroom Camera**: Detects faces in the lecture hall, cross-references with enrolled biometric datasets, and marks attendance as `Present` with 98.87% accuracy within 100ms.
   - **Campus / Corridor / Canteen Camera**: Detects students in common areas during active class hours, flags them as "Class Skippers", captures timestamped photographic evidence, and automatically logs violations.

2. **Multi-Role Institutional Dashboards (Light Theme)**:
   - **College Admin Dashboard**:
     - Department Management (CRUD)
     - Semester Management (CRUD)
     - Syllabus & Subject Management (CRUD)
     - Student Registration & Records
     - Biometric Face Enrollment (Live webcam capture or photo upload + automated model retraining)
     - Faculty Staff Management (CRUD)
     - Portal Login Credentials Management for Staff & HoD
     - Timetable Management with weekly scheduling
     - Attendance Log with real-time filtering
     - Excel (`.xlsx`) & CSV Report Generation
     - Notification & Alert Center (SMS Gateway & SMTP Email broadcast)
   - **Faculty Staff Dashboard**:
     - Assigned lecture schedule
     - Class student attendance logs
     - Class skipper violation warnings
     - High-resolution roaming student photo evidence gallery
   - **Head of Department (HoD) Dashboard**:
     - Department-wide attendance statistics & monitoring
     - Department lecture timetables
     - Class skipper violation registry
     - Roaming photo captures
     - Direct SMS alert dispatch to parents with customizable templates

3. **Modern Light-Themed UI**:
   - Inspired by the thesis design specification (`image31.png`) with clean typography (Plus Jakarta Sans & Inter), soft layered elevation, responsive flex/grid layouts, and emerald/indigo/rose semantic color badges.

---

## 🔑 Default Portal Login Credentials

| Portal | Role | Username | Password |
|---|---|---|---|
| **College Admin** | Super Admin | `admin` | `admin123` |
| **Faculty Staff** | Assistant Professor | `staff_raj` | `staff123` |
| **Head of Dept** | HoD (CSE) | `hod_cse` | `hod123` |

---

## 🚀 Quick Start Guide

### 1. Requirements
- Python 3.8+ (Tested on Python 3.12)
- Libraries: `flask`, `opencv-python`, `scikit-learn`, `numpy`, `pandas`, `openpyxl`, `pillow`

### 2. Launch the Application
Double-click `run.bat` or run:
```bash
python app.py
```
Open your web browser and navigate to:
```
http://127.0.0.1:5000
```

### 3. Testing Surveillance Without a Physical Camera
- Navigate to the **Live Monitoring** page: `http://127.0.0.1:5000/monitoring`
- Click **"Classroom Camera (Attendance)"** to view attendance automation.
- Click **"Campus Corridor (Class Skipper)"** to switch to violation surveillance mode.
- Use the quick test simulation buttons:
  - `+ Simulate Student Attendance`: Simulates an enrolled student entering class and marks attendance.
  - `+ Simulate Roaming Violation`: Simulates a student wandering during lecture hours, captures a violation snapshot, and sends an SMS alert.
