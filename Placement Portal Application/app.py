import os
import secrets
from pathlib import Path
from typing import Optional
from functools import wraps
from datetime import date, datetime

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
    send_from_directory,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from models import Application, CompanyProfile, Job, Placement, StudentProfile, User, db


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "placement_portal.db"
UPLOAD_FOLDER = BASE_DIR / "instance" / "uploads" / "resumes"
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB max upload

    db.init_app(app)

    # Ensure upload directory exists
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

    with app.app_context():
        db.create_all()
        seed_default_admin()

    @app.context_processor
    def inject_current_user():
        return {"current_user": get_current_user()}

    register_routes(app)
    return app


def seed_default_admin() -> None:
    if User.query.filter_by(role="admin").first() is None:
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com").strip().lower()
        admin_password = os.environ.get("ADMIN_PASSWORD")

        if not admin_password:
            admin_password = secrets.token_urlsafe(16)
            print("\nInitial admin account created:")
            print(f"  Email: {admin_email}")
            print(f"  Password: {admin_password}")
            print("Set ADMIN_PASSWORD in the environment for a stable credential.\n")

        admin = User(
            email=admin_email,
            password_hash=generate_password_hash(admin_password),
            role="admin",
        )
        db.session.add(admin)
        db.session.commit()


def get_current_user() -> Optional[User]:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not get_current_user():
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapper


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user or user.role not in roles:
                abort(403)
            return view_func(*args, **kwargs)

        return wrapper

    return decorator


def register_routes(app: Flask) -> None:
    @app.before_request
    def check_blacklisted_company():
        user = get_current_user()
        if user and user.role == "company":
            company = user.company_profile
            if company and company.blacklisted:
                if request.endpoint not in ("index", "login", "logout", "static"):
                    session.clear()
                    flash("Your company account has been blacklisted. Please contact the placement cell.", "danger")
                    return redirect(url_for("index"))

    @app.route("/")
    def index():
        return render_template("index.html")

    # Authentication
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email).first()
            if not user or not check_password_hash(user.password_hash, password):
                flash("Invalid email or password.", "danger")
                return redirect(url_for("index"))

            if user.role == "company":
                company = user.company_profile
                if not company or not company.approved or getattr(company, "blacklisted", False):
                    flash("Your company account is not approved for login. Please contact the placement cell.", "danger")
                    return render_template("auth/login.html", email=email)

            if user.role == "student":
                student = user.student_profile
                if student and getattr(student, "blacklisted", False):
                    flash("Your student account has been restricted. Please contact the placement cell.", "danger")
                    return render_template("auth/login.html", email=email)

            session["user_id"] = user.id
            session["role"] = user.role

            if user.role == "admin":
                return redirect(url_for("admin_dashboard"))
            if user.role == "company":
                return redirect(url_for("company_dashboard"))
            if user.role == "student":
                return redirect(url_for("student_dashboard"))
            return redirect(url_for("index"))

        # For GET requests, always show the main index login page
        return redirect(url_for("index"))

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.", "info")
        return redirect(url_for("index"))

    # Registration
    @app.route("/register/student", methods=["GET", "POST"])
    def register_student():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            name = request.form.get("name", "").strip()
            roll_number = request.form.get("roll_number", "").strip().upper()
            department = request.form.get("department", "").strip()
            cgpa = request.form.get("cgpa", "").strip()
            graduation_year = request.form.get("graduation_year", "").strip()
            phone = request.form.get("phone", "").strip()
            skills = request.form.get("skills", "").strip()

            if not email or not password:
                flash("Email and password are required.", "danger")
                return render_template("auth/register_student.html", form=request.form)

            if not name or not roll_number or not department or not cgpa or not graduation_year:
                flash("Please fill in all required fields.", "danger")
                return render_template("auth/register_student.html", form=request.form)

            if User.query.filter_by(email=email).first():
                flash("Email is already registered.", "danger")
                return render_template("auth/register_student.html", form=request.form)

            try:
                cgpa_val = float(cgpa)
                grad_year_val = int(graduation_year)
            except ValueError:
                flash("Please enter valid numeric values for CGPA and graduation year.", "danger")
                return render_template("auth/register_student.html", form=request.form)

            if not 0 <= cgpa_val <= 10:
                flash("CGPA must be between 0 and 10.", "danger")
                return render_template("auth/register_student.html", form=request.form)

            if not 2000 <= grad_year_val <= 2100:
                flash("Please enter a valid graduation year.", "danger")
                return render_template("auth/register_student.html", form=request.form)

            # Handle resume upload
            resume_filename = None
            resume_file = request.files.get("resume")
            if resume_file and resume_file.filename and allowed_file(resume_file.filename):
                safe_name = secure_filename(resume_file.filename)
                # Prefix with roll number for uniqueness
                resume_filename = f"{roll_number}_{safe_name}"
                resume_file.save(str(UPLOAD_FOLDER / resume_filename))

            user = User(
                email=email,
                password_hash=generate_password_hash(password),
                role="student",
            )
            db.session.add(user)
            db.session.flush()

            profile = StudentProfile(
                user_id=user.id,
                name=name,
                roll_number=roll_number,
                department=department,
                cgpa=cgpa_val,
                graduation_year=grad_year_val,
                phone=phone or None,
                skills=skills or None,
                resume_filename=resume_filename,
            )
            db.session.add(profile)
            db.session.commit()

            flash("Student registered successfully. Please log in.", "success")
            return redirect(url_for("login"))

        return render_template("auth/register_student.html", form=request.form)

    @app.route("/register/company", methods=["GET", "POST"])
    def register_company():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            name = request.form.get("name", "").strip()
            website = request.form.get("website", "").strip()
            contact_person = request.form.get("contact_person", "").strip()
            contact_email = request.form.get("contact_email", "").strip()
            industry = request.form.get("industry", "").strip()

            if not email or not password:
                flash("Email and password are required.", "danger")
                return render_template("auth/register_company.html", form=request.form)

            if not name:
                flash("Company name is required.", "danger")
                return render_template("auth/register_company.html", form=request.form)

            if User.query.filter_by(email=email).first():
                flash("Email is already registered.", "danger")
                return render_template("auth/register_company.html", form=request.form)

            if CompanyProfile.query.filter_by(name=name).first():
                flash("Company name is already registered.", "danger")
                return render_template("auth/register_company.html", form=request.form)

            user = User(
                email=email,
                password_hash=generate_password_hash(password),
                role="company",
            )
            db.session.add(user)
            db.session.flush()

            company = CompanyProfile(
                user_id=user.id,
                name=name,
                website=website,
                contact_person=contact_person,
                contact_email=contact_email,
                industry=industry or None,
                approved=False,
            )
            db.session.add(company)
            db.session.commit()

            flash("Company registered. Await admin approval before you can post jobs.", "success")
            return redirect(url_for("login"))

        return render_template("auth/register_company.html", form=request.form)

    # ──────────────────────────────────────────────
    # Admin
    # ──────────────────────────────────────────────
    @app.route("/admin/dashboard")
    @login_required
    @role_required("admin")
    def admin_dashboard():
        total_students = StudentProfile.query.count()
        total_companies = CompanyProfile.query.count()
        pending_companies = CompanyProfile.query.filter_by(approved=False).count()
        total_jobs = Job.query.count()
        total_applications = Application.query.count()

        latest_jobs = Job.query.order_by(Job.created_at.desc()).limit(5).all()
        pending_company_list = CompanyProfile.query.filter_by(approved=False, blacklisted=False).all()

        return render_template(
            "admin/dashboard.html",
            total_students=total_students,
            total_companies=total_companies,
            pending_companies=pending_companies,
            total_jobs=total_jobs,
            total_applications=total_applications,
            latest_jobs=latest_jobs,
            pending_company_list=pending_company_list,
        )

    @app.route("/admin/companies")
    @login_required
    @role_required("admin")
    def admin_companies():
        q = request.args.get("q", "").strip()
        query = CompanyProfile.query
        if q:
            like = f"%{q}%"
            query = query.filter(
                db.or_(
                    CompanyProfile.name.ilike(like),
                    CompanyProfile.contact_person.ilike(like),
                    CompanyProfile.industry.ilike(like),
                )
            )
        companies = query.order_by(CompanyProfile.approved.desc(), CompanyProfile.name).all()
        return render_template("admin/companies.html", companies=companies, q=q)

    @app.route("/admin/companies/<int:company_id>/approve", methods=["POST"])
    @login_required
    @role_required("admin")
    def approve_company(company_id: int):
        company = CompanyProfile.query.get_or_404(company_id)
        company.approved = True
        company.blacklisted = False
        db.session.commit()
        flash(f"{company.name} approved successfully.", "success")
        return redirect(url_for("admin_companies"))

    @app.route("/admin/companies/<int:company_id>/reject", methods=["POST"])
    @login_required
    @role_required("admin")
    def reject_company(company_id: int):
        company = CompanyProfile.query.get_or_404(company_id)
        company.approved = False
        company.blacklisted = False
        db.session.commit()
        flash(f"{company.name} registration has been rejected.", "warning")
        return redirect(url_for("admin_companies"))

    @app.route("/admin/companies/<int:company_id>/blacklist", methods=["POST"])
    @login_required
    @role_required("admin")
    def blacklist_company(company_id: int):
        company = CompanyProfile.query.get_or_404(company_id)
        company.blacklisted = True
        company.approved = False
        db.session.commit()
        flash(f"{company.name} has been blacklisted.", "warning")
        return redirect(url_for("admin_companies"))

    @app.route("/admin/companies/<int:company_id>/edit", methods=["GET", "POST"])
    @login_required
    @role_required("admin")
    def admin_edit_company(company_id: int):
        company = CompanyProfile.query.get_or_404(company_id)
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            website = request.form.get("website", "").strip()
            contact_person = request.form.get("contact_person", "").strip()
            contact_email = request.form.get("contact_email", "").strip()
            industry = request.form.get("industry", "").strip()

            if not name:
                flash("Company name is required.", "danger")
                return render_template("admin/edit_company.html", company=company, form=request.form)

            other = CompanyProfile.query.filter(CompanyProfile.name == name, CompanyProfile.id != company.id).first()
            if other:
                flash("Another company is already registered with this name.", "danger")
                return render_template("admin/edit_company.html", company=company, form=request.form)

            company.name = name
            company.website = website or None
            company.contact_person = contact_person or None
            company.contact_email = contact_email or None
            company.industry = industry or None
            db.session.commit()
            flash(f"{company.name} updated successfully.", "success")
            return redirect(url_for("admin_companies"))

        return render_template("admin/edit_company.html", company=company, form=request.form)

    @app.route("/admin/companies/<int:company_id>/delete", methods=["POST"])
    @login_required
    @role_required("admin")
    def delete_company(company_id: int):
        company = CompanyProfile.query.get_or_404(company_id)
        user = company.user
        # Delete all applications for all jobs of this company
        for job in company.jobs.all():
            Application.query.filter_by(job_id=job.id).delete()
            db.session.delete(job)
        db.session.delete(company)
        if user:
            db.session.delete(user)
        db.session.commit()
        flash("Company and all related data deleted.", "info")
        return redirect(url_for("admin_companies"))

    @app.route("/admin/students")
    @login_required
    @role_required("admin")
    def admin_students():
        q = request.args.get("q", "").strip()
        query = StudentProfile.query
        if q:
            like = f"%{q}%"
            query = query.filter(
                db.or_(
                    StudentProfile.name.ilike(like),
                    StudentProfile.roll_number.ilike(like),
                    StudentProfile.phone.ilike(like),
                )
            )
        students = query.order_by(StudentProfile.roll_number).all()
        return render_template("admin/students.html", students=students, q=q)

    @app.route("/admin/students/<int:student_id>/blacklist", methods=["POST"])
    @login_required
    @role_required("admin")
    def blacklist_student(student_id: int):
        student = StudentProfile.query.get_or_404(student_id)
        student.blacklisted = True
        db.session.commit()
        flash(f"Student {student.roll_number} has been blacklisted.", "warning")
        return redirect(url_for("admin_students"))

    @app.route("/admin/students/<int:student_id>/unblacklist", methods=["POST"])
    @login_required
    @role_required("admin")
    def unblacklist_student(student_id: int):
        student = StudentProfile.query.get_or_404(student_id)
        student.blacklisted = False
        db.session.commit()
        flash(f"Student {student.roll_number} has been un-blacklisted.", "success")
        return redirect(url_for("admin_students"))

    @app.route("/admin/students/<int:student_id>/edit", methods=["GET", "POST"])
    @login_required
    @role_required("admin")
    def admin_edit_student(student_id: int):
        student = StudentProfile.query.get_or_404(student_id)
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            department = request.form.get("department", "").strip()
            cgpa_raw = request.form.get("cgpa", "").strip()
            graduation_year_raw = request.form.get("graduation_year", "").strip()
            phone = request.form.get("phone", "").strip()
            skills = request.form.get("skills", "").strip()

            if not name or not department:
                flash("Name and department are required.", "danger")
                return render_template("admin/edit_student.html", student=student, form=request.form)

            try:
                cgpa_val = float(cgpa_raw)
                grad_year_val = int(graduation_year_raw)
            except ValueError:
                flash("Please enter valid numeric values for CGPA and graduation year.", "danger")
                return render_template("admin/edit_student.html", student=student, form=request.form)

            if not 0 <= cgpa_val <= 10:
                flash("CGPA must be between 0 and 10.", "danger")
                return render_template("admin/edit_student.html", student=student, form=request.form)

            if not 2000 <= grad_year_val <= 2100:
                flash("Please enter a valid graduation year.", "danger")
                return render_template("admin/edit_student.html", student=student, form=request.form)

            student.name = name
            student.department = department
            student.cgpa = cgpa_val
            student.graduation_year = grad_year_val
            student.phone = phone or None
            student.skills = skills or None
            db.session.commit()
            flash(f"Student {student.roll_number} updated successfully.", "success")
            return redirect(url_for("admin_students"))

        return render_template("admin/edit_student.html", student=student, form=request.form)

    @app.route("/admin/students/<int:student_id>/delete", methods=["POST"])
    @login_required
    @role_required("admin")
    def delete_student(student_id: int):
        student = StudentProfile.query.get_or_404(student_id)
        user = student.user
        Application.query.filter_by(student_id=student.id).delete()
        db.session.delete(student)
        if user:
            db.session.delete(user)
        db.session.commit()
        flash("Student deleted.", "info")
        return redirect(url_for("admin_students"))

    @app.route("/admin/drives")
    @login_required
    @role_required("admin")
    def admin_drives():
        jobs = Job.query.order_by(Job.created_at.desc()).all()
        return render_template("admin/drives.html", jobs=jobs)

    @app.route("/admin/drives/<int:job_id>/approve", methods=["POST"])
    @login_required
    @role_required("admin")
    def approve_drive(job_id: int):
        job = Job.query.get_or_404(job_id)
        job.status = "approved"
        db.session.commit()
        flash("Placement drive approved.", "success")
        return redirect(url_for("admin_drives"))

    @app.route("/admin/drives/<int:job_id>/reject", methods=["POST"])
    @login_required
    @role_required("admin")
    def reject_drive(job_id: int):
        job = Job.query.get_or_404(job_id)
        job.status = "rejected"
        db.session.commit()
        flash("Placement drive rejected.", "warning")
        return redirect(url_for("admin_drives"))

    @app.route("/admin/drives/<int:job_id>/close", methods=["POST"])
    @login_required
    @role_required("admin")
    def close_drive(job_id: int):
        job = Job.query.get_or_404(job_id)
        job.status = "closed"
        db.session.commit()
        flash("Placement drive closed.", "info")
        return redirect(url_for("admin_drives"))

    @app.route("/admin/applications")
    @login_required
    @role_required("admin")
    def admin_applications():
        applications = (
            Application.query
            .order_by(Application.applied_at.desc())
            .all()
        )
        return render_template("admin/applications.html", applications=applications)

    # ──────────────────────────────────────────────
    # Company
    # ──────────────────────────────────────────────
    @app.route("/company/dashboard")
    @login_required
    @role_required("company")
    def company_dashboard():
        user = get_current_user()
        company = user.company_profile
        jobs = company.jobs.order_by(Job.created_at.desc()).all()
        return render_template("company/dashboard.html", company=company, jobs=jobs)

    @app.route("/company/profile", methods=["GET", "POST"])
    @login_required
    @role_required("company")
    def company_profile():
        user = get_current_user()
        company = user.company_profile

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            website = request.form.get("website", "").strip()
            contact_person = request.form.get("contact_person", "").strip()
            contact_email = request.form.get("contact_email", "").strip()
            industry = request.form.get("industry", "").strip()

            if not name:
                flash("Company name is required.", "danger")
                return render_template("company/profile.html", company=company, form=request.form)

            other = CompanyProfile.query.filter(CompanyProfile.name == name, CompanyProfile.id != company.id).first()
            if other:
                flash("Another company is already registered with this name.", "danger")
                return render_template("company/profile.html", company=company, form=request.form)

            company.name = name
            company.website = website or None
            company.contact_person = contact_person or None
            company.contact_email = contact_email or None
            company.industry = industry or None
            db.session.commit()

            flash("Company profile updated successfully.", "success")
            return redirect(url_for("company_dashboard"))

        return render_template("company/profile.html", company=company, form=request.form)

    @app.route("/company/jobs/new", methods=["GET", "POST"])
    @login_required
    @role_required("company")
    def create_job():
        user = get_current_user()
        company = user.company_profile
        if not company.approved:
            flash("Your company is not yet approved by admin.", "warning")
            return redirect(url_for("company_dashboard"))

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            location = request.form.get("location", "").strip()
            ctc = request.form.get("ctc", "").strip()
            description = request.form.get("description", "").strip()
            min_cgpa = request.form.get("min_cgpa", "").strip()
            deadline_raw = request.form.get("application_deadline", "").strip()

            if not title:
                flash("Job title is required.", "danger")
                return render_template("company/job_form.html", form=request.form)
            if not ctc:
                flash("CTC is required.", "danger")
                return render_template("company/job_form.html", form=request.form)

            try:
                min_cgpa_val = float(min_cgpa)
            except ValueError:
                flash("Please enter a valid minimum CGPA.", "danger")
                return render_template("company/job_form.html", form=request.form)

            if not 0 <= min_cgpa_val <= 10:
                flash("Minimum CGPA must be between 0 and 10.", "danger")
                return render_template("company/job_form.html", form=request.form)

            deadline_value = None
            if deadline_raw:
                try:
                    deadline_value = datetime.strptime(deadline_raw, "%Y-%m-%d").date()
                except ValueError:
                    flash("Please enter a valid application deadline date.", "danger")
                    return render_template("company/job_form.html", form=request.form)

            job = Job(
                company_id=company.id,
                title=title,
                location=location,
                ctc=ctc,
                description=description,
                min_cgpa=min_cgpa_val,
                application_deadline=deadline_value,
                status="pending",
            )
            db.session.add(job)
            db.session.commit()

            flash("Placement drive created successfully.", "success")
            return redirect(url_for("company_dashboard"))

        return render_template("company/job_form.html", form=request.form)

    @app.route("/company/jobs/<int:job_id>/edit", methods=["GET", "POST"])
    @login_required
    @role_required("company")
    def edit_job(job_id: int):
        user = get_current_user()
        company = user.company_profile
        job = Job.query.filter_by(id=job_id, company_id=company.id).first_or_404()

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            location = request.form.get("location", "").strip()
            ctc = request.form.get("ctc", "").strip()
            description = request.form.get("description", "").strip()
            min_cgpa = request.form.get("min_cgpa", "").strip()
            deadline_raw = request.form.get("application_deadline", "").strip()

            if not title:
                flash("Job title is required.", "danger")
                return render_template("company/job_edit.html", job=job, form=request.form)
            if not ctc:
                flash("CTC is required.", "danger")
                return render_template("company/job_edit.html", job=job, form=request.form)

            try:
                min_cgpa_val = float(min_cgpa)
            except ValueError:
                flash("Please enter a valid minimum CGPA.", "danger")
                return render_template("company/job_edit.html", job=job, form=request.form)

            if not 0 <= min_cgpa_val <= 10:
                flash("Minimum CGPA must be between 0 and 10.", "danger")
                return render_template("company/job_edit.html", job=job, form=request.form)

            deadline_value = None
            if deadline_raw:
                try:
                    deadline_value = datetime.strptime(deadline_raw, "%Y-%m-%d").date()
                except ValueError:
                    flash("Please enter a valid application deadline date.", "danger")
                    return render_template("company/job_edit.html", job=job, form=request.form)

            job.title = title
            job.location = location or None
            job.ctc = ctc
            job.description = description or None
            job.min_cgpa = min_cgpa_val
            job.application_deadline = deadline_value
            db.session.commit()

            flash("Placement drive updated successfully.", "success")
            return redirect(url_for("company_dashboard"))

        return render_template("company/job_edit.html", job=job, form=request.form)

    @app.route("/company/jobs/<int:job_id>/close", methods=["POST"])
    @login_required
    @role_required("company")
    def close_job(job_id: int):
        user = get_current_user()
        company = user.company_profile
        job = Job.query.filter_by(id=job_id, company_id=company.id).first_or_404()
        job.status = "closed"
        db.session.commit()
        flash("Placement drive closed.", "info")
        return redirect(url_for("company_dashboard"))

    @app.route("/company/jobs/<int:job_id>/delete", methods=["POST"])
    @login_required
    @role_required("company")
    def delete_job(job_id: int):
        user = get_current_user()
        company = user.company_profile
        job = Job.query.filter_by(id=job_id, company_id=company.id).first_or_404()
        if job.applications.count() > 0:
            flash("You cannot delete a drive that already has applications. You can close it instead.", "warning")
            return redirect(url_for("company_dashboard"))
        db.session.delete(job)
        db.session.commit()
        flash("Placement drive deleted.", "info")
        return redirect(url_for("company_dashboard"))

    @app.route("/company/jobs/<int:job_id>/applications")
    @login_required
    @role_required("company")
    def company_job_applications(job_id: int):
        user = get_current_user()
        company = user.company_profile
        job = Job.query.filter_by(id=job_id, company_id=company.id).first_or_404()
        applications = job.applications.order_by(Application.applied_at.desc()).all()
        return render_template(
            "company/applications.html",
            job=job,
            applications=applications,
        )

    @app.route("/company/applications/<int:application_id>/status", methods=["POST"])
    @login_required
    @role_required("company")
    def update_application_status(application_id: int):
        user = get_current_user()
        company = user.company_profile
        application = Application.query.get_or_404(application_id)
        if application.job.company_id != company.id:
            abort(403)
        status = request.form.get("status", "").strip().lower()
        allowed = ("applied", "shortlisted", "interview", "selected", "rejected", "placed")
        if status not in allowed:
            flash("Invalid status.", "danger")
            return redirect(url_for("company_job_applications", job_id=application.job_id))
        application.status = status

        # Keep the Placement record synchronized with the application status.
        if status == "placed":
            if not application.placement:
                placement = Placement(application_id=application.id)
                db.session.add(placement)
        elif application.placement:
            db.session.delete(application.placement)

        db.session.commit()
        flash(f"Application status updated to {status}.", "success")
        return redirect(url_for("company_job_applications", job_id=application.job_id))

    @app.route("/company/students/<int:student_id>")
    @login_required
    @role_required("company")
    def view_student_profile(student_id: int):
        user = get_current_user()
        company = user.company_profile
        student = StudentProfile.query.get_or_404(student_id)

        has_application = (
            Application.query
            .join(Job, Application.job_id == Job.id)
            .filter(
                Application.student_id == student.id,
                Job.company_id == company.id,
            )
            .first()
        )
        if not has_application:
            abort(403)

        return render_template("company/student_profile.html", student=student)

    # ──────────────────────────────────────────────
    # Student
    # ──────────────────────────────────────────────
    @app.route("/student/dashboard")
    @login_required
    @role_required("student")
    def student_dashboard():
        user = get_current_user()
        student = user.student_profile
        applications = (
            Application.query.filter_by(student_id=student.id)
            .order_by(Application.applied_at.desc())
            .all()
        )
        # Notifications: applications whose status changed (not 'applied')
        notifications = [
            app for app in applications if app.status != "applied"
        ]
        # Approved drives the student is eligible for
        applied_job_ids = [a.job_id for a in applications]
        approved_jobs = (
            Job.query.filter(
                Job.status == "approved",
                Job.min_cgpa <= student.cgpa,
                db.or_(Job.application_deadline.is_(None), Job.application_deadline >= date.today()),
                ~Job.id.in_(applied_job_ids) if applied_job_ids else True,
            )
            .order_by(Job.created_at.desc())
            .limit(5)
            .all()
        )
        return render_template(
            "student/dashboard.html",
            student=student,
            applications=applications,
            notifications=notifications,
            approved_jobs=approved_jobs,
        )

    @app.route("/student/profile", methods=["GET", "POST"])
    @login_required
    @role_required("student")
    def student_profile():
        user = get_current_user()
        student = user.student_profile

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            department = request.form.get("department", "").strip()
            cgpa_raw = request.form.get("cgpa", "").strip()
            graduation_year_raw = request.form.get("graduation_year", "").strip()
            phone = request.form.get("phone", "").strip()
            skills = request.form.get("skills", "").strip()

            if not name or not department:
                flash("Name and department are required.", "danger")
                return render_template("student/profile.html", student=student, form=request.form)

            try:
                cgpa_val = float(cgpa_raw)
                grad_year_val = int(graduation_year_raw)
            except ValueError:
                flash("Please enter valid numeric values for CGPA and graduation year.", "danger")
                return render_template("student/profile.html", student=student, form=request.form)

            if cgpa_val < 0 or cgpa_val > 10:
                flash("CGPA must be between 0 and 10.", "danger")
                return render_template("student/profile.html", student=student, form=request.form)

            # Handle resume upload
            resume_file = request.files.get("resume")
            if resume_file and resume_file.filename and allowed_file(resume_file.filename):
                safe_name = secure_filename(resume_file.filename)
                resume_filename = f"{student.roll_number}_{safe_name}"
                resume_file.save(str(UPLOAD_FOLDER / resume_filename))
                student.resume_filename = resume_filename

            student.name = name
            student.department = department
            student.cgpa = cgpa_val
            student.graduation_year = grad_year_val
            student.phone = phone or None
            student.skills = skills or None
            db.session.commit()

            flash("Profile updated successfully.", "success")
            return redirect(url_for("student_dashboard"))

        return render_template("student/profile.html", student=student, form=request.form)

    @app.route("/jobs")
    @login_required
    @role_required("student")
    def list_jobs():
        user = get_current_user()
        student = user.student_profile
        q = request.args.get("q", "").strip()
        query = Job.query.filter(
            Job.status == "approved",
            Job.min_cgpa <= student.cgpa,
            db.or_(Job.application_deadline.is_(None), Job.application_deadline >= date.today()),
        )
        if q:
            like = f"%{q}%"
            query = query.filter(
                db.or_(
                    Job.title.ilike(like),
                    Job.description.ilike(like),
                    Job.company.has(CompanyProfile.name.ilike(like)),
                )
            )
        jobs = query.order_by(Job.created_at.desc()).all()
        return render_template("student/jobs.html", student=student, jobs=jobs, q=q)

    @app.route("/jobs/<int:job_id>/apply", methods=["POST"])
    @login_required
    @role_required("student")
    def apply_to_job(job_id: int):
        user = get_current_user()
        student = user.student_profile
        job = Job.query.get_or_404(job_id)

        if student.blacklisted:
            flash("Your account has been restricted. You cannot apply to jobs.", "danger")
            return redirect(url_for("list_jobs"))

        if job.status != "approved":
            flash("This job is not open for applications.", "warning")
            return redirect(url_for("list_jobs"))

        if job.application_deadline and job.application_deadline < date.today():
            flash("The application deadline for this job has passed.", "warning")
            return redirect(url_for("list_jobs"))

        if student.cgpa < job.min_cgpa:
            flash("You are not eligible for this job based on CGPA.", "danger")
            return redirect(url_for("list_jobs"))

        existing = Application.query.filter_by(job_id=job.id, student_id=student.id).first()
        if existing:
            flash("You have already applied for this job.", "info")
            return redirect(url_for("list_jobs"))

        application = Application(job_id=job.id, student_id=student.id, status="applied")
        db.session.add(application)
        db.session.commit()

        flash("Application submitted successfully.", "success")
        return redirect(url_for("student_dashboard"))

    # Resume download
    @app.route("/uploads/resumes/<filename>")
    @login_required
    def download_resume(filename):
        user = get_current_user()
        student = StudentProfile.query.filter_by(resume_filename=filename).first_or_404()

        if user.role == "admin":
            return send_from_directory(str(UPLOAD_FOLDER), filename)

        if user.role == "student":
            if student.user_id != user.id:
                abort(403)
        elif user.role == "company":
            company = user.company_profile
            has_application = (
                Application.query
                .join(Job, Application.job_id == Job.id)
                .filter(
                    Application.student_id == student.id,
                    Job.company_id == company.id,
                )
                .first()
            )
            if not has_application:
                abort(403)
        else:
            abort(403)

        return send_from_directory(str(UPLOAD_FOLDER), filename)


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
