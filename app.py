import os
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_from_directory
)

import mysql.connector
from mysql.connector import Error
from werkzeug.utils import secure_filename
from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

app.secret_key = os.getenv(
    "SECRET_KEY",
    "tasktrack-secret-key"
)


# ============================================================
# UPLOAD FOLDERS
# ============================================================

ASSIGNMENT_UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "uploads",
    "assignments"
)

SUBMISSION_UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "uploads",
    "submissions"
)

os.makedirs(ASSIGNMENT_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SUBMISSION_UPLOAD_FOLDER, exist_ok=True)


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

DB_NAME = os.getenv(
    "DB_NAME",
    "tasktrackdb"
)


# Aiven SSL certificate
CA_FILE = os.path.join(
    BASE_DIR,
    "ca.pem"
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():

    try:

        connection_config = {
            "host": DB_HOST,
            "port": DB_PORT,
            "user": DB_USER,
            "password": DB_PASSWORD,
            "database": DB_NAME
        }

        # Use SSL for Aiven
        if os.path.exists(CA_FILE):

            connection_config["ssl_ca"] = CA_FILE
            connection_config["ssl_verify_cert"] = True
            connection_config["ssl_verify_identity"] = True

        connection = mysql.connector.connect(
            **connection_config
        )

        return connection

    except Error as e:

        print("DATABASE CONNECTION ERROR:", e)

        return None


# ============================================================
# LOGIN DECORATORS
# ============================================================

def student_required(function):

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if (
            "user_id" not in session
            or session.get("role") != "student"
        ):

            flash(
                "Please login as a student first.",
                "warning"
            )

            return redirect(
                url_for("student_login")
            )

        return function(*args, **kwargs)

    return decorated_function


def faculty_required(function):

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if (
            "user_id" not in session
            or session.get("role") != "faculty"
        ):

            flash(
                "Please login as faculty first.",
                "warning"
            )

            return redirect(
                url_for("faculty_login")
            )

        return function(*args, **kwargs)

    return decorated_function


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def index():

    return render_template("index.html")


# ============================================================
# FACULTY REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not name or not email or not password:

            flash(
                "Please fill in all fields.",
                "danger"
            )

            return render_template(
                "register.html"
            )

        connection = get_db_connection()

        if connection is None:

            flash(
                "Database connection failed.",
                "danger"
            )

            return render_template(
                "register.html"
            )

        cursor = connection.cursor(dictionary=True)

        try:

            # Check existing email
            cursor.execute(
                """
                SELECT id
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            existing_user = cursor.fetchone()

            if existing_user:

                flash(
                    "An account with this email already exists.",
                    "warning"
                )

                return render_template(
                    "register.html"
                )

            # Create faculty
            cursor.execute(
                """
                INSERT INTO users
                (
                    name,
                    email,
                    password,
                    role
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    'faculty'
                )
                """,
                (
                    name,
                    email,
                    password
                )
            )

            connection.commit()

            flash(
                "Faculty account created successfully. Please login.",
                "success"
            )

            return redirect(
                url_for("faculty_login")
            )

        except Error as e:

            connection.rollback()

            print(
                "FACULTY REGISTER ERROR:",
                e
            )

            flash(
                "Unable to create faculty account.",
                "danger"
            )

        finally:

            cursor.close()
            connection.close()

    return render_template(
        "register.html"
    )


# ============================================================
# FACULTY LOGIN
# ============================================================

@app.route("/faculty/login", methods=["GET", "POST"])
def faculty_login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

        print("\n==============================")
        print("FACULTY LOGIN ATTEMPT")
        print("EMAIL ENTERED:", email)

        connection = get_db_connection()

        if connection is None:

            flash(
                "Database connection failed.",
                "danger"
            )

            return render_template(
                "faculty_login.html"
            )

        cursor = connection.cursor(
            dictionary=True
        )

        try:

            cursor.execute(
                """
                SELECT *
                FROM users
                WHERE email = %s
                AND role = 'faculty'
                """,
                (email,)
            )

            faculty = cursor.fetchone()

            print(
                "FACULTY FOUND:",
                bool(faculty)
            )

            if faculty:

                print(
                    "FACULTY NAME:",
                    faculty["name"]
                )

                print(
                    "FACULTY EMAIL:",
                    faculty["email"]
                )

                print(
                    "FACULTY ROLE:",
                    faculty["role"]
                )

                password_match = (
                    faculty["password"] == password
                )

                print(
                    "PASSWORD MATCH:",
                    password_match
                )

            else:

                password_match = False

            if faculty and password_match:

                session.clear()

                session["user_id"] = faculty["id"]
                session["name"] = faculty["name"]
                session["email"] = faculty["email"]
                session["role"] = "faculty"

                print(
                    "LOGIN SUCCESSFUL"
                )

                return redirect(
                    url_for("faculty_dashboard")
                )

            print(
                "LOGIN FAILED"
            )

            flash(
                "Invalid email or password.",
                "danger"
            )

        except Error as e:

            print(
                "FACULTY LOGIN ERROR:",
                e
            )

            flash(
                "Unable to login.",
                "danger"
            )

        finally:

            cursor.close()
            connection.close()

    return render_template(
        "faculty_login.html"
    )


# ============================================================
# STUDENT REGISTER
# ============================================================

@app.route(
    "/student/register",
    methods=["GET", "POST"]
)
def student_register():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

        department = request.form.get(
            "department",
            ""
        ).strip()

        year_of_study = request.form.get(
            "year_of_study",
            ""
        ).strip()

        if not all([
            name,
            email,
            password,
            department,
            year_of_study
        ]):

            flash(
                "Please fill in all fields.",
                "danger"
            )

            return render_template(
                "student_register.html"
            )

        connection = get_db_connection()

        if connection is None:

            flash(
                "Database connection failed.",
                "danger"
            )

            return render_template(
                "student_register.html"
            )

        cursor = connection.cursor(
            dictionary=True
        )

        try:

            cursor.execute(
                """
                SELECT id
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            existing_user = cursor.fetchone()

            if existing_user:

                flash(
                    "An account with this email already exists.",
                    "warning"
                )

                return render_template(
                    "student_register.html"
                )

            cursor.execute(
                """
                INSERT INTO users
                (
                    name,
                    email,
                    password,
                    role,
                    department,
                    year_of_study
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    'student',
                    %s,
                    %s
                )
                """,
                (
                    name,
                    email,
                    password,
                    department,
                    year_of_study
                )
            )

            connection.commit()

            flash(
                "Student account created successfully. Please login.",
                "success"
            )

            return redirect(
                url_for("student_login")
            )

        except Error as e:

            connection.rollback()

            print(
                "STUDENT REGISTER ERROR:",
                e
            )

            flash(
                "Unable to create student account.",
                "danger"
            )

        finally:

            cursor.close()
            connection.close()

    return render_template(
        "student_register.html"
    )


# ============================================================
# STUDENT LOGIN
# ============================================================

@app.route(
    "/student/login",
    methods=["GET", "POST"]
)
def student_login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

        print("\n==============================")
        print("STUDENT LOGIN ATTEMPT")
        print("EMAIL ENTERED:", email)

        connection = get_db_connection()

        if connection is None:

            flash(
                "Database connection failed.",
                "danger"
            )

            return render_template(
                "student_login.html"
            )

        cursor = connection.cursor(
            dictionary=True
        )

        try:

            cursor.execute(
                """
                SELECT *
                FROM users
                WHERE email = %s
                AND role = 'student'
                """,
                (email,)
            )

            student = cursor.fetchone()

            print(
                "STUDENT FOUND:",
                bool(student)
            )

            if student:

                print(
                    "STUDENT NAME:",
                    student["name"]
                )

                print(
                    "STUDENT EMAIL:",
                    student["email"]
                )

                print(
                    "STUDENT ROLE:",
                    student["role"]
                )

                password_match = (
                    student["password"] == password
                )

                print(
                    "PASSWORD MATCH:",
                    password_match
                )

            else:

                password_match = False

            if student and password_match:

                session.clear()

                session["user_id"] = student["id"]
                session["name"] = student["name"]
                session["email"] = student["email"]
                session["role"] = "student"

                print(
                    "STUDENT LOGIN SUCCESSFUL"
                )

                return redirect(
                    url_for("student_dashboard")
                )

            print(
                "STUDENT LOGIN FAILED"
            )

            flash(
                "Invalid email or password.",
                "danger"
            )

        except Error as e:

            print(
                "STUDENT LOGIN ERROR:",
                e
            )

            flash(
                "Unable to login.",
                "danger"
            )

        finally:

            cursor.close()
            connection.close()

    return render_template(
        "student_login.html"
    )


# ============================================================
# STUDENT DASHBOARD
# ============================================================

@app.route("/student/dashboard")
@student_required
def student_dashboard():

    student_id = session["user_id"]

    connection = get_db_connection()

    if connection is None:

        flash(
            "Database connection failed.",
            "danger"
        )

        return redirect(
            url_for("student_login")
        )

    cursor = connection.cursor(
        dictionary=True
    )

    try:

        # ----------------------------------------------------
        # GET STUDENT DETAILS
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                name,
                email,
                department,
                year_of_study
            FROM users
            WHERE id = %s
            """,
            (student_id,)
        )

        student = cursor.fetchone()

        if not student:

            session.clear()

            return redirect(
                url_for("student_login")
            )

        # ----------------------------------------------------
        # GET ASSIGNMENTS FOR STUDENT
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT

                a.id,
                a.title,
                a.description,
                a.subject,
                a.due_date,
                a.file_name,
                a.created_at,
                a.department,
                a.year_of_study,

                u.name AS faculty_name,

                s.id AS submission_id,
                s.file_name AS submission_file_name,
                s.submitted_at,

                CASE

                    WHEN s.id IS NULL
                        THEN 'Not Submitted'

                    WHEN DATE(s.submitted_at) > a.due_date
                        THEN 'Late Submission'

                    ELSE 'Submitted'

                END AS submission_status

            FROM assignments a

            JOIN users u
                ON a.faculty_id = u.id

            LEFT JOIN submissions s
                ON a.id = s.assignment_id
                AND s.student_id = %s

            WHERE a.department = %s
            AND a.year_of_study = %s

            ORDER BY a.due_date ASC
            """,
            (
                student_id,
                student["department"],
                student["year_of_study"]
            )
        )

        assignments = cursor.fetchall()

        # ----------------------------------------------------
        # DASHBOARD STATISTICS
        # ----------------------------------------------------

        total_assignments = len(
            assignments
        )

        submitted_count = sum(
            1
            for assignment in assignments
            if assignment["submission_status"]
            != "Not Submitted"
        )

        pending_count = sum(
            1
            for assignment in assignments
            if assignment["submission_status"]
            == "Not Submitted"
        )

        # ----------------------------------------------------
        # MY SUBMISSIONS COUNT
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM submissions
            WHERE student_id = %s
            """,
            (student_id,)
        )

        submission_result = cursor.fetchone()

        my_submissions = (
            submission_result["count"]
            if submission_result
            else 0
        )

        return render_template(
            "student_dashboard.html",

            student=student,

            assignments=assignments,

            total_assignments=total_assignments,

            submitted_count=submitted_count,

            pending_count=pending_count,

            my_submissions=my_submissions
        )

    except Error as e:

        print(
            "STUDENT DASHBOARD ERROR:",
            e
        )

        flash(
            "Unable to load student dashboard.",
            "danger"
        )

        return redirect(
            url_for("student_login")
        )

    finally:

        cursor.close()
        connection.close()


# ============================================================
# STUDENT SUBMISSIONS
# ============================================================

@app.route("/student/submissions")
@student_required
def student_submissions():

    student_id = session["user_id"]

    connection = get_db_connection()

    if connection is None:

        flash(
            "Database connection failed.",
            "danger"
        )

        return redirect(
            url_for("student_dashboard")
        )

    cursor = connection.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            """
            SELECT

                s.id,
                s.file_name,
                s.submitted_at,

                a.id AS assignment_id,
                a.title,
                a.subject,
                a.due_date,

                u.name AS faculty_name,

                CASE

                    WHEN DATE(s.submitted_at) > a.due_date
                        THEN 'Late Submission'

                    ELSE 'Submitted'

                END AS submission_status

            FROM submissions s

            JOIN assignments a
                ON s.assignment_id = a.id

            JOIN users u
                ON a.faculty_id = u.id

            WHERE s.student_id = %s

            ORDER BY s.submitted_at DESC
            """,
            (student_id,)
        )

        submissions = cursor.fetchall()

        return render_template(
            "student_submissions.html",
            submissions=submissions
        )

    except Error as e:

        print(
            "STUDENT SUBMISSIONS ERROR:",
            e
        )

        flash(
            "Unable to load submissions.",
            "danger"
        )

        return redirect(
            url_for("student_dashboard")
        )

    finally:

        cursor.close()
        connection.close()


# ============================================================
# STUDENT SUBMIT ASSIGNMENT
# ============================================================

@app.route(
    "/student/submit/<int:assignment_id>",
    methods=["POST"]
)
@student_required
def student_submit(assignment_id):

    student_id = session["user_id"]

    uploaded_file = request.files.get(
        "file"
    )

    if not uploaded_file or not uploaded_file.filename:

        flash(
            "Please select a file to upload.",
            "warning"
        )

        return redirect(
            url_for("student_dashboard")
        )

    connection = get_db_connection()

    if connection is None:

        flash(
            "Database connection failed.",
            "danger"
        )

        return redirect(
            url_for("student_dashboard")
        )

    cursor = connection.cursor(
        dictionary=True
    )

    try:

        # ----------------------------------------------------
        # CHECK ASSIGNMENT
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT *
            FROM assignments
            WHERE id = %s
            """,
            (assignment_id,)
        )

        assignment = cursor.fetchone()

        if not assignment:

            flash(
                "Assignment not found.",
                "danger"
            )

            return redirect(
                url_for("student_dashboard")
            )

        # ----------------------------------------------------
        # CHECK STUDENT DETAILS
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT department, year_of_study
            FROM users
            WHERE id = %s
            AND role = 'student'
            """,
            (student_id,)
        )

        student = cursor.fetchone()

        if not student:

            flash(
                "Student account not found.",
                "danger"
            )

            return redirect(
                url_for("student_login")
            )

        # ----------------------------------------------------
        # CHECK DEPARTMENT AND YEAR
        # ----------------------------------------------------

        if (
            assignment["department"]
            != student["department"]
            or
            assignment["year_of_study"]
            != student["year_of_study"]
        ):

            flash(
                "You are not eligible to submit this assignment.",
                "danger"
            )

            return redirect(
                url_for("student_dashboard")
            )

        # ----------------------------------------------------
        # SAVE FILE
        # ----------------------------------------------------

        original_filename = secure_filename(
            uploaded_file.filename
        )

        if not original_filename:

            flash(
                "Invalid file name.",
                "danger"
            )

            return redirect(
                url_for("student_dashboard")
            )

        # Add student ID and timestamp to avoid filename conflicts
        timestamp = datetime.now().strftime(
            "%Y%m%d%H%M%S"
        )

        stored_filename = (
            f"{student_id}_{timestamp}_{original_filename}"
        )

        file_path = os.path.join(
            SUBMISSION_UPLOAD_FOLDER,
            stored_filename
        )

        uploaded_file.save(
            file_path
        )

        # ----------------------------------------------------
        # CHECK EXISTING SUBMISSION
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT id
            FROM submissions
            WHERE assignment_id = %s
            AND student_id = %s
            """,
            (
                assignment_id,
                student_id
            )
        )

        existing_submission = cursor.fetchone()

        if existing_submission:

            # Update existing submission
            cursor.execute(
                """
                UPDATE submissions
                SET
                    file_name = %s,
                    submitted_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (
                    stored_filename,
                    existing_submission["id"]
                )
            )

            message = (
                "Assignment submission updated successfully."
            )

        else:

            # Create new submission
            cursor.execute(
                """
                INSERT INTO submissions
                (
                    assignment_id,
                    student_id,
                    file_name
                )
                VALUES
                (
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    assignment_id,
                    student_id,
                    stored_filename
                )
            )

            message = (
                "Assignment submitted successfully."
            )

        connection.commit()

        flash(
            message,
            "success"
        )

        return redirect(
            url_for("student_dashboard")
        )

    except Error as e:

        connection.rollback()

        print(
            "STUDENT SUBMISSION ERROR:",
            e
        )

        flash(
            "Unable to submit assignment.",
            "danger"
        )

        return redirect(
            url_for("student_dashboard")
        )

    finally:

        cursor.close()
        connection.close()


# ============================================================
# FACULTY DASHBOARD
# ============================================================

@app.route("/faculty/dashboard")
@faculty_required
def faculty_dashboard():

    faculty_id = session["user_id"]

    connection = get_db_connection()

    if connection is None:

        flash(
            "Database connection failed.",
            "danger"
        )

        return redirect(
            url_for("faculty_login")
        )

    cursor = connection.cursor(
        dictionary=True
    )

    try:

        # ----------------------------------------------------
        # GET FACULTY ASSIGNMENTS
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT

                a.id,
                a.title,
                a.description,
                a.subject,
                a.due_date,
                a.file_name,
                a.department,
                a.year_of_study,
                a.created_at,

                COUNT(s.id) AS submission_count

            FROM assignments a

            LEFT JOIN submissions s
                ON a.id = s.assignment_id

            WHERE a.faculty_id = %s

            GROUP BY

                a.id,
                a.title,
                a.description,
                a.subject,
                a.due_date,
                a.file_name,
                a.department,
                a.year_of_study,
                a.created_at

            ORDER BY a.created_at DESC
            """,
            (faculty_id,)
        )

        assignments = cursor.fetchall()

        # ----------------------------------------------------
        # ASSIGNMENT COUNT
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM assignments
            WHERE faculty_id = %s
            """,
            (faculty_id,)
        )

        assignment_result = cursor.fetchone()

        assignment_count = (
            assignment_result["count"]
            if assignment_result
            else 0
        )

        # ----------------------------------------------------
        # TOTAL SUBMISSIONS
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM submissions s

            JOIN assignments a
                ON s.assignment_id = a.id

            WHERE a.faculty_id = %s
            """,
            (faculty_id,)
        )

        submission_result = cursor.fetchone()

        submission_count = (
            submission_result["count"]
            if submission_result
            else 0
        )

        # ----------------------------------------------------
        # UNIQUE STUDENTS WHO SUBMITTED
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(
                DISTINCT s.student_id
            ) AS count

            FROM submissions s

            JOIN assignments a
                ON s.assignment_id = a.id

            WHERE a.faculty_id = %s
            """,
            (faculty_id,)
        )

        students_result = cursor.fetchone()

        students_submitted = (
            students_result["count"]
            if students_result
            else 0
        )

        return render_template(
            "faculty_dashboard.html",

            assignments=assignments,

            assignment_count=assignment_count,

            submission_count=submission_count,

            students_submitted=students_submitted
        )

    except Error as e:

        print(
            "FACULTY DASHBOARD ERROR:",
            e
        )

        flash(
            "Unable to load faculty dashboard.",
            "danger"
        )

        return redirect(
            url_for("faculty_login")
        )

    finally:

        cursor.close()
        connection.close()


# ============================================================
# FACULTY UPLOAD ASSIGNMENT
# ============================================================

@app.route(
    "/faculty/upload",
    methods=["GET", "POST"],
    endpoint="faculty_upload"
)
@app.route(
    "/faculty/upload",
    methods=["GET", "POST"],
    endpoint="upload_assignments"
)
@faculty_required
def upload_assignments():

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        subject = request.form.get(
            "subject",
            ""
        ).strip()

        due_date = request.form.get(
            "due_date",
            ""
        ).strip()

        department = request.form.get(
            "department",
            ""
        ).strip()

        year_of_study = request.form.get(
            "year_of_study",
            ""
        ).strip()

        uploaded_file = request.files.get(
            "file"
        )

        if not all([
            title,
            description,
            subject,
            due_date,
            department,
            year_of_study
        ]):

            flash(
                "Please fill in all assignment details.",
                "danger"
            )

            return render_template(
                "upload_assignments.html"
            )

        if not uploaded_file or not uploaded_file.filename:

            flash(
                "Please select an assignment file.",
                "warning"
            )

            return render_template(
                "upload_assignments.html"
            )

        filename = secure_filename(
            uploaded_file.filename
        )

        if not filename:

            flash(
                "Invalid file name.",
                "danger"
            )

            return render_template(
                "upload_assignments.html"
            )

        connection = get_db_connection()

        if connection is None:

            flash(
                "Database connection failed.",
                "danger"
            )

            return render_template(
                "upload_assignments.html"
            )

        cursor = connection.cursor()

        try:

            # ------------------------------------------------
            # SAVE FILE
            # ------------------------------------------------

            timestamp = datetime.now().strftime(
                "%Y%m%d%H%M%S"
            )

            stored_filename = (
                f"{session['user_id']}_{timestamp}_{filename}"
            )

            file_path = os.path.join(
                ASSIGNMENT_UPLOAD_FOLDER,
                stored_filename
            )

            uploaded_file.save(
                file_path
            )

            # ------------------------------------------------
            # INSERT ASSIGNMENT
            # ------------------------------------------------

            cursor.execute(
                """
                INSERT INTO assignments
                (
                    title,
                    description,
                    subject,
                    due_date,
                    file_name,
                    faculty_id,
                    department,
                    year_of_study
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    title,
                    description,
                    subject,
                    due_date,
                    stored_filename,
                    session["user_id"],
                    department,
                    year_of_study
                )
            )

            connection.commit()

            flash(
                "Assignment uploaded successfully.",
                "success"
            )

            return redirect(
                url_for("faculty_dashboard")
            )

        except Error as e:

            connection.rollback()

            print(
                "ASSIGNMENT UPLOAD ERROR:",
                e
            )

            flash(
                "Unable to upload assignment.",
                "danger"
            )

        finally:

            cursor.close()
            connection.close()

    return render_template(
        "upload_assignments.html"
    )


# ============================================================
# FACULTY ALL SUBMISSIONS
# ============================================================

@app.route("/faculty/submissions")
@faculty_required
def faculty_submissions():

    faculty_id = session["user_id"]

    department = request.args.get(
        "department",
        ""
    ).strip()

    year_of_study = request.args.get(
        "year_of_study",
        ""
    ).strip()

    connection = get_db_connection()

    if connection is None:

        flash(
            "Database connection failed.",
            "danger"
        )

        return redirect(
            url_for("faculty_dashboard")
        )

    cursor = connection.cursor(
        dictionary=True
    )

    try:

        query = """
            SELECT

                s.id,
                s.file_name,
                s.submitted_at,

                a.id AS assignment_id,
                a.title AS assignment_title,
                a.subject,
                a.due_date,
                a.department,
                a.year_of_study,

                u.name AS student_name,
                u.email AS student_email,

                CASE

                    WHEN DATE(s.submitted_at) > a.due_date
                        THEN 'Late Submission'

                    ELSE 'On Time'

                END AS submission_status

            FROM submissions s

            JOIN assignments a
                ON s.assignment_id = a.id

            JOIN users u
                ON s.student_id = u.id

            WHERE a.faculty_id = %s
        """

        params = [
            faculty_id
        ]

        if department:

            query += """
                AND a.department = %s
            """

            params.append(
                department
            )

        if year_of_study:

            query += """
                AND a.year_of_study = %s
            """

            params.append(
                year_of_study
            )

        query += """
            ORDER BY s.submitted_at DESC
        """

        cursor.execute(
            query,
            tuple(params)
        )

        submissions = cursor.fetchall()

        if not submissions and (
            department or year_of_study
        ):

            flash(
                "No submissions found for the selected Department and Year of Study.",
                "info"
            )

        return render_template(
            "submissions.html",

            submissions=submissions,

            selected_department=department,

            selected_year=year_of_study
        )

    except Error as e:

        print(
            "FACULTY SUBMISSIONS ERROR:",
            e
        )

        flash(
            "Unable to load submissions.",
            "danger"
        )

        return redirect(
            url_for("faculty_dashboard")
        )

    finally:

        cursor.close()
        connection.close()


# ============================================================
# FACULTY SUBMISSIONS FOR ONE ASSIGNMENT
# ============================================================

@app.route(
    "/faculty/submissions/<int:assignment_id>"
)
@faculty_required
def faculty_assignment_submissions(
    assignment_id
):

    faculty_id = session["user_id"]

    connection = get_db_connection()

    if connection is None:

        flash(
            "Database connection failed.",
            "danger"
        )

        return redirect(
            url_for("faculty_dashboard")
        )

    cursor = connection.cursor(
        dictionary=True
    )

    try:

        # ----------------------------------------------------
        # CHECK ASSIGNMENT BELONGS TO FACULTY
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT *
            FROM assignments
            WHERE id = %s
            AND faculty_id = %s
            """,
            (
                assignment_id,
                faculty_id
            )
        )

        assignment = cursor.fetchone()

        if not assignment:

            flash(
                "Assignment not found.",
                "danger"
            )

            return redirect(
                url_for("faculty_dashboard")
            )

        # ----------------------------------------------------
        # GET SUBMISSIONS
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT

                s.id,
                s.file_name,
                s.submitted_at,

                u.name AS student_name,
                u.email AS student_email,
                u.department,
                u.year_of_study,

                CASE

                    WHEN DATE(s.submitted_at) > %s
                        THEN 'Late Submission'

                    ELSE 'On Time'

                END AS submission_status

            FROM submissions s

            JOIN users u
                ON s.student_id = u.id

            WHERE s.assignment_id = %s

            ORDER BY s.submitted_at DESC
            """,
            (
                assignment["due_date"],
                assignment_id
            )
        )

        submissions = cursor.fetchall()

        return render_template(
            "submissions.html",

            submissions=submissions,

            assignment=assignment,

            selected_department="",

            selected_year=""
        )

    except Error as e:

        print(
            "ASSIGNMENT SUBMISSIONS ERROR:",
            e
        )

        flash(
            "Unable to load assignment submissions.",
            "danger"
        )

        return redirect(
            url_for("faculty_dashboard")
        )

    finally:

        cursor.close()
        connection.close()


# ============================================================
# DOWNLOAD ASSIGNMENT
# ============================================================

@app.route(
    "/download/assignment/<filename>"
)
def download_assignment(filename):

    safe_filename = secure_filename(
        filename
    )

    return send_from_directory(
        ASSIGNMENT_UPLOAD_FOLDER,
        safe_filename,
        as_attachment=True
    )


# ============================================================
# DOWNLOAD SUBMISSION
# ============================================================

@app.route(
    "/download/submission/<filename>"
)
@faculty_required
def download_submission(filename):

    safe_filename = secure_filename(
        filename
    )

    return send_from_directory(
        SUBMISSION_UPLOAD_FOLDER,
        safe_filename,
        as_attachment=True
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out successfully.",
        "success"
    )

    return redirect(
        url_for("index")
    )


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    return render_template(
        "index.html"
    ), 404


@app.errorhandler(500)
def internal_server_error(error):

    print(
        "INTERNAL SERVER ERROR:",
        error
    )

    return """
        <h2>TaskTrack Server Error</h2>
        <p>Something went wrong. Please try again.</p>
    """, 500


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    )
