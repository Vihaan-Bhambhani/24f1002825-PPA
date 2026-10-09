# Placement Portal

A compact role-based placement management web application built with **Python, Flask, SQLAlchemy, SQLite, Jinja2, and Bootstrap 5**.

The application models a complete campus-placement workflow across three user roles:

- **Admin** — manages users, companies, placement drives, approvals, and application records
- **Company** — maintains its profile, creates placement drives, reviews applicants, and updates application status
- **Student** — maintains an academic profile, browses eligible drives, applies to jobs, and tracks application progress

## What it demonstrates

- Session-based authentication with password hashing
- Role-based access control with reusable decorators
- Relational database design with SQLAlchemy ORM
- Company and placement-drive approval workflows
- CGPA-based eligibility filtering
- Application lifecycle tracking
- Resume upload and controlled resume access
- Search across students, companies, and placement drives
- Database-level prevention of duplicate applications
- Server-side validation and business-rule enforcement
- Responsive server-rendered UI with Jinja2 and Bootstrap 5

## Application flow

```text
Company Registration
        │
        ▼
Admin Approval
        │
        ▼
Placement Drive
        │
        ▼
Admin Approval
        │
        ▼
Eligible Students
        │
        ▼
Application
        │
        ▼
Applied → Shortlisted → Interview → Selected → Placed
```

## Database design

The application uses six relational entities:

| Entity | Purpose |
|---|---|
| User | Authentication and role information |
| StudentProfile | Academic and personal student data |
| CompanyProfile | Company profile and approval state |
| Job | Placement-drive details and eligibility rules |
| Application | Student applications and status |
| Placement | Confirmed placement records |

Key relationships include company-to-job, job-to-application, student-to-application, and application-to-placement.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| ORM | Flask-SQLAlchemy / SQLAlchemy |
| Database | SQLite |
| Templates | Jinja2 |
| Frontend | Bootstrap 5, custom CSS |
| Authentication | Flask sessions + Werkzeug password hashing |

## Run locally

### 1. Create a virtual environment

```bash
python -m venv .venv
```

Activate it:

**Windows**
```bash
.venv\Scripts\activate
```

**macOS / Linux**
```bash
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r "Placement Portal Application/requirements.txt"
```

### 3. Configure the initial admin

For local development, set:

```text
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=choose-a-strong-password
```

On first launch, if `ADMIN_PASSWORD` is omitted, the application generates a random password and prints it to the console.

### 4. Start the application

```bash
cd "Placement Portal Application"
python app.py
```

The application runs locally on:

```text
http://127.0.0.1:5000
```

The SQLite database is created automatically on first run.

## Project structure

```text
Placement Portal Application/
├── app.py
├── models.py
├── requirements.txt
├── static/
│   └── css/
│       └── styles.css
└── templates/
    ├── base.html
    ├── index.html
    ├── auth/
    ├── admin/
    ├── company/
    └── student/
```

## Notes

The project is intentionally kept as a lightweight server-rendered application rather than a production-scale service. It is best viewed as a supporting software-engineering project demonstrating backend development, relational modelling, authentication, and business-rule implementation.

The SQLite database and resume files are runtime data and are excluded from version control. Resume files are stored under `instance/uploads/resumes/`, outside Flask's publicly served `static/` directory. This is a local/demo project, not a production-ready system; it does not yet include CSRF protection or content-based file inspection.

---
**Author:** Vihaan Bhambhani
