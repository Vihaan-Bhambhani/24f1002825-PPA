# Placement Portal Application

A clean and modular Placement Portal System built using Flask, offering dedicated role-based dashboards for Admins, Companies, and Students.
The system manages the entire campus placement workflow — from company registration and job posting to student applications and placement tracking.

---

## Features

### Admin
- Pre-seeded admin account (no registration needed)
- Dashboard with summary statistics (students, companies, jobs, applications)
- Approve, reject, edit, blacklist, un-blacklist, and delete companies
- Edit, blacklist, un-blacklist, and delete students
- Approve, reject, and close placement drives
- View all applications across the portal
- Search students by name, roll number, or phone
- Search companies by name, contact person, or industry

### Company
- Register and await admin approval before posting jobs
- Update company profile (name, industry, website, contact details)
- Create, edit, close, and delete placement drives
- Set minimum CGPA eligibility for each drive
- View applicants for each drive
- Update application status (Applied → Shortlisted → Interview → Selected → Rejected → Placed)
- View student profiles and download resumes

### Student
- Register with academic details, skills, and resume upload
- Update profile and re-upload resume anytime
- Browse approved placement drives (auto-filtered by CGPA eligibility)
- Search jobs by company name, position, or skills/description
- Apply to eligible drives (duplicate applications prevented)
- Dashboard showing available drives, applied jobs, and status notifications
- View full application history with real-time status updates

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, Flask |
| ORM | SQLAlchemy (Flask-SQLAlchemy) |
| Database | SQLite |
| Templating | Jinja2 |
| Frontend | Bootstrap 5 |
| Auth | Session-based with Werkzeug password hashing |

---

## Installation Guide

### 1. Create Virtual Environment
```bash
python -m venv venv
```

### 2. Activate Environment

**Windows**
```bash
venv\Scripts\activate
```

**Mac/Linux**
```bash
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Application
```bash
python app.py
```

The database is automatically created on first run with a generated admin account.

The system will be available at:
**http://127.0.0.1:5000**

---

## Default Login Credentials

### Admin
The first admin account is created automatically on first run.

Set these environment variables before starting the application for a predictable
admin credential:

```text
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=choose-a-strong-password
```

If `ADMIN_PASSWORD` is not provided, the application generates a one-time random
password and prints it to the console during first-time initialization.

### Companies
- Register through the company registration page
- Login is enabled only after admin approval

### Students
- Register through the student registration page

---

## Project Structure

```
Placement-Portal/
├── app.py                          # Application entry point & all routes
├── models.py                       # SQLAlchemy models (6 tables)
├── requirements.txt                # Python dependencies
├── placement_portal.db             # SQLite database (auto-created)
├── static/
│   ├── css/
│   │   └── styles.css              # Custom Bootstrap theme
│   └── uploads/
│       └── resumes/                # Student resume uploads
├── templates/
│   ├── base.html                   # Base layout with navbar
│   ├── index.html                  # Landing page with login
│   ├── auth/
│   │   ├── login.html              # Login page
│   │   ├── register_student.html   # Student registration
│   │   └── register_company.html   # Company registration
│   ├── admin/
│   │   ├── dashboard.html          # Admin summary dashboard
│   │   ├── companies.html          # Manage companies
│   │   ├── students.html           # Manage students
│   │   ├── drives.html             # Manage placement drives
│   │   ├── applications.html       # View all applications
│   │   ├── edit_student.html       # Edit student profile
│   │   └── edit_company.html       # Edit company profile
│   ├── company/
│   │   ├── dashboard.html          # Company job listings
│   │   ├── profile.html            # Edit company profile
│   │   ├── job_form.html           # Create new drive
│   │   ├── job_edit.html           # Edit existing drive
│   │   ├── applications.html       # View applicants
│   │   └── student_profile.html    # View student details
│   └── student/
│       ├── dashboard.html          # Student dashboard
│       ├── profile.html            # Edit student profile
│       └── jobs.html               # Browse & apply to jobs
```

---

## Database Schema

| Table | Description |
|-------|-------------|
| `users` | Authentication (email, password hash, role) |
| `students` | Student profiles (name, roll number, CGPA, skills, resume) |
| `companies` | Company profiles (name, industry, approval/blacklist status) |
| `jobs` | Placement drives (title, CTC, min CGPA, status, deadline) |
| `applications` | Student job applications (status tracking) |
| `placements` | Confirmed placement records |

---

## Key Design Decisions

- **No JavaScript for core functionality** — all features work with pure server-side rendering
- **HTML5 form validation** — all forms use native browser validation
- **Backend validation** — all inputs validated server-side as well
- **Role-based access control** — custom `@login_required` and `@role_required` decorators
- **Duplicate prevention** — unique constraints at both DB and application level
- **CGPA-based filtering** — students only see drives they're eligible for
- **Resume upload** — supports PDF, DOC, DOCX (max 5 MB)

---

## Notes

- All UI pages use a consistent Bootstrap 5 theme with responsive design
- Strict role separation ensures secure access across admin, company, and student dashboards
- Flash messages provide real-time feedback for all user actions
- Blacklisted students cannot log in; blacklisted companies lose approval
- Companies must be approved by admin before they can post placement drives
- Placement records are automatically created when a company marks an application as "Placed"

---

## License

This project is intended for academic and learning purposes.
