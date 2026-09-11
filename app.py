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
import os

from werkzeug.utils import secure_filename
from functools import wraps
from dotenv import load_dotenv


# ==========================================================
# APP CONFIGURATION
# ==========================================================

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))

app.secret_key = os.getenv("SECRET_KEY", "tasktrack-secret-key")


# ==========================================================
# DATABASE CONFIGURATION
# ==========================================================

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME", "tasktrackdb"),
}

SSL_CA = os.path.join(BASE_DIR, "ca.pem")


def get_db_connection():

    try:

        connection = mysql.connector.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"],
            ssl_ca=SSL_CA,
            ssl_verify_cert=True
        )

        return connection

    except mysql.connector.Error as error:

        print("DATABASE CONNECTION ERROR:", error)

        return None


# ==========================================================
# FILE UPLOAD CONFIGURATION
# ==========================================================

ASSIGNMENT_FOLDER = os.path.join(
    BASE_DIR,
    "uploads",
    "assignments"
)

SUBMISSION_FOLDER = os.path.join(
    BASE_DIR,
    "uploads",
    "submissions"
)

os.makedirs(ASSIGNMENT_FOLDER, exist_ok=True)
os.makedirs(SUBMISSION_FOLDER, exist_ok=True)


ALLOWED_EXTENSIONS = {
    "pdf",
    "doc",
    "docx",
    "txt",
    "zip",
    "rar",
    "ppt",
    "pptx",
    "xls",
    "xlsx",
    "jpg",
    "jpeg",
    "png"
}


def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# ==========================================================
# LOGIN DECORATORS
# ==========================================================

def student_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session or session.get("role") != "student":

            flash("Please login as a student first.", "danger")

            return redirect(url_for("student_login"))

        return function(*args, **kwargs)

    return wrapper


def faculty_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session or session.get("role") != "faculty":

            flash("Please login as faculty first.", "danger")

            return redirect(url_for("faculty_login"))

        return function(*args, **kwargs)

    return wrapper


# ==========================================================
# HOME PAGE
# ==========================================================

@app.route("/")
def index():

    return render_template("index.html")


# ==========================================================
# FACULTY REGISTER
# ==========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not name or not email or not password:

            flash("Please fill in all fields.", "danger")

            return render_template("register.html")

        connection = get_db_connection()

        if not connection:

            flash("Unable to connect to database.", "danger")

            return render_template("register.html")

        cursor = connection.cursor(dictionary=True)

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

                flash("An account with this email already exists.", "warning")

                return render_template("register.html")

            cursor.execute(
                """
                INSERT INTO users
                (name, email, password, role)
                VALUES (%s, %s, %s, 'faculty')
                """,
                (name, email, password)
            )

            connection.commit()

            flash(
                "Faculty account created successfully. Please login.",
                "success"
            )

            return redirect(url_for("faculty_login"))

        except mysql.connector.Error as error:

            connection.rollback()

            print("FACULTY REGISTER ERROR:", error)

            flash("Unable to create account.", "danger")

            return render_template("register.html")

        finally:

            cursor.close()
            connection.close()

    return render_template("register.html")


# ==========================================================
# STUDENT REGISTER
# ==========================================================

@app.route("/student/register", methods=["GET", "POST"])
def student_register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        department = request.form.get(
            "department",
            ""
        ).strip()

        year_of_study = request.form.get(
            "year_of_study",
            ""
        ).strip()

        if not name or not email or not password:

            flash("Please fill in all required fields.", "danger")

            return render_template("student_register.html")

        if not department or not year_of_study:

            flash(
                "Please select Department and Year of Study.",
                "danger"
            )

            return render_template("student_register.html")

        connection = get_db_connection()

        if not connection:

            flash("Unable to connect to database.", "danger")

            return render_template("student_register.html")

        cursor = connection.cursor(dictionary=True)

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

                return render_template("student_register.html")

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
                VALUES (%s, %s, %s, 'student', %s, %s)
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

            return redirect(url_for("student_login"))

        except mysql.connector.Error as error:

            connection.rollback()

            print("STUDENT REGISTER ERROR:", error)

            flash("Unable to create student account.", "danger")

            return render_template("student_register.html")

        finally:

            cursor.close()
            connection.close()

    return render_template("student_register.html")


# ==========================================================
# STUDENT LOGIN
# ==========================================================

@app.route("/student/login", methods=["GET", "POST"])
def student_login():

    if request.method == "POST":

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        connection = get_db_connection()

        if not connection:

            flash("Unable to connect to database.", "danger")

            return render_template("student_login.html")

        cursor = connection.cursor(dictionary=True)

        try:

            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    email,
                    password,
                    role,
                    department,
                    year_of_study
                FROM users
                WHERE email = %s
                AND role = 'student'
                """,
                (email,)
            )

            student = cursor.fetchone()

            if student and student["password"] == password:

                session.clear()

                session["user_id"] = student["id"]
                session["name"] = student["name"]
                session["email"] = student["email"]
                session["role"] = "student"
                session["department"] = student["department"]
                session["year_of_study"] = student["year_of_study"]

                return redirect(
                    url_for("student_dashboard")
                )

            flash(
                "Invalid email or password.",
                "danger"
            )

        except mysql.connector.Error as error:

            print("STUDENT LOGIN ERROR:", error)

            flash(
                "Unable to login.",
                "danger"
            )

        finally:

            cursor.close()
            connection.close()

    return render_template("student_login.html")


# ==========================================================
# FACULTY LOGIN
# ==========================================================

@app.route("/faculty/login", methods=["GET", "POST"])
def faculty_login():

    if request.method == "POST":

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        print("================================")
        print("FACULTY LOGIN ATTEMPT")
        print("EMAIL ENTERED:", email)

        connection = get_db_connection()

        if not connection:

            print("DATABASE CONNECTION FAILED")

            flash(
                "Unable to connect to database.",
                "danger"
            )

            return render_template("faculty_login.html")

        cursor = connection.cursor(dictionary=True)

        try:

            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    email,
                    password,
                    role
                FROM users
                WHERE email = %s
                AND role = 'faculty'
                """,
                (email,)
            )

            faculty = cursor.fetchone()

            print(
                "FACULTY FOUND:",
                faculty is not None
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

                print(
                    "PASSWORD MATCH:",
                    faculty["password"] == password
                )

            if faculty and faculty["password"] == password:

                session.clear()

                session["user_id"] = faculty["id"]
                session["name"] = faculty["name"]
                session["email"] = faculty["email"]
                session["role"] = "faculty"

                print("LOGIN SUCCESSFUL")
                print("================================")

                return redirect(
                    url_for("faculty_dashboard")
                )

            print("LOGIN FAILED")
            print("================================")

            flash(
                "Invalid email or password.",
                "danger"
            )

        except mysql.connector.Error as error:

            print(
                "FACULTY LOGIN ERROR:",
                error
            )

            flash(
                "Unable to login.",
                "danger"
            )

        finally:

            cursor.close()
            connection.close()

    return render_template("faculty_login.html")


# ==========================================================
# LOGOUT
# ==========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out successfully.",
        "success"
    )

    return redirect(url_for("index"))


# ==========================================================
# STUDENT DASHBOARD
# ==========================================================

@app.route("/student/dashboard")
@student_required
def student_dashboard():

    connection = get_db_connection()

    if not connection:

        flash(
            "Unable to connect to database.",
            "danger"
        )

        return redirect(url_for("student_login"))

    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                a.id,
                a.title,
                a.description,
                a.subject,
                a.due_date,
                a.file_name,
                a.faculty_id,
                a.department,
                a.year_of_study,
                a.created_at,

                u.name AS faculty_name,

                s.id AS submission_id,
                s.file_name AS submission_file,
                s.submitted_at,

                CASE
                    WHEN s.id IS NULL
                        THEN 'Not Submitted'

                    WHEN DATE(s.submitted_at) > a.due_date
                        THEN 'Late Submission'

                    ELSE 'Submitted'
                END AS submission_status

            FROM assignments a

            LEFT JOIN users u
                ON a.faculty_id = u.id

            LEFT JOIN submissions s
                ON a.id = s.assignment_id
                AND s.student_id = %s

            WHERE a.department = %s
            AND a.year_of_study = %s

            ORDER BY a.due_date ASC
            """,
            (
                session["user_id"],
                session.get("department"),
                session.get("year_of_study")
            )
        )

        assignments = cursor.fetchall()

        total_assignments = len(assignments)

        submitted_count = sum(
            1
            for assignment in assignments
            if assignment["submission_status"]
            in ["Submitted", "Late Submission"]
        )

        pending_count = total_assignments - submitted_count

        late_count = sum(
            1
            for assignment in assignments
            if assignment["submission_status"]
            == "Late Submission"
        )

        return render_template(
            "student_dashboard.html",
            assignments=assignments,
            total_assignments=total_assignments,
            submitted_count=submitted_count,
            pending_count=pending_count,
            late_count=late_count
        )

    except mysql.connector.Error as error:

        print(
            "STUDENT DASHBOARD ERROR:",
            error
        )

        flash(
            "Unable to load assignments.",
            "danger"
        )

        return render_template(
            "student_dashboard.html",
            assignments=[],
            total_assignments=0,
            submitted_count=0,
            pending_count=0,
            late_count=0
        )

    finally:

        cursor.close()
        connection.close()


# ==========================================================
# STUDENT SUBMIT ASSIGNMENT
# ==========================================================

@app.route(
    "/student/submit/<int:assignment_id>",
    methods=["POST"]
)
@student_required
def student_submit(assignment_id):

    uploaded_file = request.files.get("file")

    if not uploaded_file or uploaded_file.filename == "":

        flash(
            "Please select a file to upload.",
            "danger"
        )

        return redirect(
            url_for("student_dashboard")
        )

    if not allowed_file(uploaded_file.filename):

        flash(
            "This file type is not allowed.",
            "danger"
        )

        return redirect(
            url_for("student_dashboard")
        )

    connection = get_db_connection()

    if not connection:

        flash(
            "Unable to connect to database.",
            "danger"
        )

        return redirect(
            url_for("student_dashboard")
        )

    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id,
                title,
                due_date,
                department,
                year_of_study
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

        if (
            assignment["department"]
            != session.get("department")
            or
            assignment["year_of_study"]
            != session.get("year_of_study")
        ):

            flash(
                "You are not allowed to submit this assignment.",
                "danger"
            )

            return redirect(
                url_for("student_dashboard")
            )

        filename = secure_filename(
            uploaded_file.filename
        )

        filename = (
            str(session["user_id"])
            + "_"
            + str(assignment_id)
            + "_"
            + filename
        )

        file_path = os.path.join(
            SUBMISSION_FOLDER,
            filename
        )

        uploaded_file.save(file_path)

        cursor.execute(
            """
            SELECT id
            FROM submissions
            WHERE assignment_id = %s
            AND student_id = %s
            """,
            (
                assignment_id,
                session["user_id"]
            )
        )

        existing_submission = cursor.fetchone()

        if existing_submission:

            cursor.execute(
                """
                UPDATE submissions
                SET
                    file_name = %s,
                    submitted_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (
                    filename,
                    existing_submission["id"]
                )
            )

            message = "Assignment resubmitted successfully."

        else:

            cursor.execute(
                """
                INSERT INTO submissions
                (
                    assignment_id,
                    student_id,
                    file_name
                )
                VALUES (%s, %s, %s)
                """,
                (
                    assignment_id,
                    session["user_id"],
                    filename
                )
            )

            message = "Assignment submitted successfully."

        connection.commit()

        cursor.execute(
            """
            SELECT
                submitted_at,
                %s AS due_date
            FROM submissions
            WHERE assignment_id = %s
            AND student_id = %s
            """,
            (
                assignment["due_date"],
                assignment_id,
                session["user_id"]
            )
        )

        submission_info = cursor.fetchone()

        if submission_info:

            submitted_at = submission_info["submitted_at"]
            due_date = submission_info["due_date"]

            if submitted_at and due_date:

                if submitted_at.date() > due_date:

                    flash(
                        "Assignment submitted, but it was submitted late.",
                        "warning"
                    )

                    return redirect(
                        url_for("student_dashboard")
                    )

        flash(
            message,
            "success"
        )

        return redirect(
            url_for("student_dashboard")
        )

    except mysql.connector.Error as error:

        connection.rollback()

        print(
            "STUDENT SUBMISSION ERROR:",
            error
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


# ==========================================================
# STUDENT SUBMISSIONS
# ==========================================================

@app.route("/student/submissions")
@student_required
def student_submissions():

    connection = get_db_connection()

    if not connection:

        flash(
            "Unable to connect to database.",
            "danger"
        )

        return redirect(
            url_for("student_login")
        )

    cursor = connection.cursor(dictionary=True)

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
                a.department,
                a.year_of_study,

                u.name AS faculty_name,

                CASE
                    WHEN DATE(s.submitted_at) > a.due_date
                        THEN 'Late Submission'
                    ELSE 'Submitted'
                END AS submission_status

            FROM submissions s

            INNER JOIN assignments a
                ON s.assignment_id = a.id

            LEFT JOIN users u
                ON a.faculty_id = u.id

            WHERE s.student_id = %s

            ORDER BY s.submitted_at DESC
            """,
            (session["user_id"],)
        )

        submissions = cursor.fetchall()

        return render_template(
            "student_submissions.html",
            submissions=submissions
        )

    except mysql.connector.Error as error:

        print(
            "STUDENT SUBMISSIONS ERROR:",
            error
        )

        flash(
            "Unable to load submissions.",
            "danger"
        )

        return render_template(
            "student_submissions.html",
            submissions=[]
        )

    finally:

        cursor.close()
        connection.close()


# ==========================================================
# FACULTY DASHBOARD
# ==========================================================

@app.route("/faculty/dashboard")
@faculty_required
def faculty_dashboard():

    connection = get_db_connection()

    if not connection:
        flash("Unable to connect to database.", "danger")
        return redirect(url_for("faculty_login"))

    cursor = connection.cursor(dictionary=True)

    try:

        # ==================================================
        # FACULTY ASSIGNMENTS
        # ==================================================

        cursor.execute("""
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
        """, (session["user_id"],))

        assignments = cursor.fetchall()

        # ==================================================
        # TOTAL ASSIGNMENTS
        # ==================================================

        cursor.execute("""
            SELECT COUNT(*) AS assignment_count
            FROM assignments
            WHERE faculty_id = %s
        """, (session["user_id"],))

        assignment_count = cursor.fetchone()["assignment_count"]

        # ==================================================
        # TOTAL SUBMISSIONS
        # ==================================================

        cursor.execute("""
            SELECT COUNT(*) AS submission_count

            FROM submissions s

            INNER JOIN assignments a
                ON s.assignment_id = a.id

            WHERE a.faculty_id = %s
        """, (session["user_id"],))

        submission_count = cursor.fetchone()["submission_count"]

        # ==================================================
        # DISTINCT STUDENTS WHO SUBMITTED
        # ==================================================

        cursor.execute("""
            SELECT COUNT(DISTINCT s.student_id) AS students_submitted

            FROM submissions s

            INNER JOIN assignments a
                ON s.assignment_id = a.id

            WHERE a.faculty_id = %s
        """, (session["user_id"],))

        students_submitted = cursor.fetchone()["students_submitted"]

        # ==================================================
        # SEND DATA TO TEMPLATE
        # ==================================================

        return render_template(
            "faculty_dashboard.html",
            assignments=assignments,
            assignment_count=assignment_count,
            submission_count=submission_count,
            students_submitted=students_submitted
        )

    except mysql.connector.Error as error:

        print("FACULTY DASHBOARD ERROR:", error)

        flash(
            "Unable to load faculty dashboard.",
            "danger"
        )

        return render_template(
            "faculty_dashboard.html",
            assignments=[],
            assignment_count=0,
            submission_count=0,
            students_submitted=0
        )

    finally:

        cursor.close()
        connection.close()


# ==========================================================
# FACULTY UPLOAD ASSIGNMENTS
#
# BOTH ENDPOINT NAMES ARE PROVIDED:
# faculty_upload
# upload_assignments
#
# This prevents BuildError from old/new templates.
# ==========================================================

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
def upload_assignments():

    if "user_id" not in session or session.get("role") != "faculty":

        flash(
            "Please login as faculty first.",
            "danger"
        )

        return redirect(
            url_for("faculty_login")
        )

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

        uploaded_file = request.files.get("file")

        if not title:

            flash(
                "Please enter assignment title.",
                "danger"
            )

            return render_template(
                "upload_assignments.html"
            )

        if not due_date:

            flash(
                "Please select a due date.",
                "danger"
            )

            return render_template(
                "upload_assignments.html"
            )

        if not department:

            flash(
                "Please select a department.",
                "danger"
            )

            return render_template(
                "upload_assignments.html"
            )

        if not year_of_study:

            flash(
                "Please select year of study.",
                "danger"
            )

            return render_template(
                "upload_assignments.html"
            )

        if not uploaded_file or uploaded_file.filename == "":

            flash(
                "Please select an assignment file.",
                "danger"
            )

            return render_template(
                "upload_assignments.html"
            )

        if not allowed_file(uploaded_file.filename):

            flash(
                "This file type is not allowed.",
                "danger"
            )

            return render_template(
                "upload_assignments.html"
            )

        filename = secure_filename(
            uploaded_file.filename
        )

        filename = (
            str(session["user_id"])
            + "_"
            + filename
        )

        file_path = os.path.join(
            ASSIGNMENT_FOLDER,
            filename
        )

        uploaded_file.save(file_path)

        connection = get_db_connection()

        if not connection:

            flash(
                "Unable to connect to database.",
                "danger"
            )

            return render_template(
                "upload_assignments.html"
            )

        cursor = connection.cursor()

        try:

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
                    filename,
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

        except mysql.connector.Error as error:

            connection.rollback()

            print(
                "ASSIGNMENT UPLOAD ERROR:",
                error
            )

            flash(
                "Unable to upload assignment.",
                "danger"
            )

            return render_template(
                "upload_assignments.html"
            )

        finally:

            cursor.close()
            connection.close()

    return render_template(
        "upload_assignments.html"
    )


# ==========================================================
# FACULTY SUBMISSIONS
# ==========================================================

@app.route("/faculty/submissions")
@faculty_required
def faculty_submissions():

    department = request.args.get(
        "department",
        ""
    ).strip()

    year_of_study = request.args.get(
        "year_of_study",
        ""
    ).strip()

    connection = get_db_connection()

    if not connection:

        flash(
            "Unable to connect to database.",
            "danger"
        )

        return redirect(
            url_for("faculty_login")
        )

    cursor = connection.cursor(dictionary=True)

    try:

        query = """
            SELECT
                s.id,
                s.file_name,
                s.submitted_at,

                a.id AS assignment_id,
                a.title,
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

            INNER JOIN assignments a
                ON s.assignment_id = a.id

            INNER JOIN users u
                ON s.student_id = u.id

            WHERE a.faculty_id = %s
        """

        params = [session["user_id"]]

        if department:

            query += """
                AND a.department = %s
            """

            params.append(department)

        if year_of_study:

            query += """
                AND a.year_of_study = %s
            """

            params.append(year_of_study)

        query += """
            ORDER BY s.submitted_at DESC
        """

        cursor.execute(
            query,
            tuple(params)
        )

        submissions = cursor.fetchall()

        return render_template(
            "submissions.html",
            submissions=submissions,
            selected_department=department,
            selected_year=year_of_study
        )

    except mysql.connector.Error as error:

        print(
            "FACULTY SUBMISSIONS ERROR:",
            error
        )

        flash(
            "Unable to load submissions.",
            "danger"
        )

        return render_template(
            "submissions.html",
            submissions=[],
            selected_department=department,
            selected_year=year_of_study
        )

    finally:

        cursor.close()
        connection.close()


# ==========================================================
# SUBMISSIONS FOR ONE ASSIGNMENT
# ==========================================================

@app.route(
    "/faculty/assignment/<int:assignment_id>/submissions"
)
@faculty_required
def faculty_assignment_submissions(assignment_id):

    connection = get_db_connection()

    if not connection:

        flash(
            "Unable to connect to database.",
            "danger"
        )

        return redirect(
            url_for("faculty_dashboard")
        )

    cursor = connection.cursor(dictionary=True)

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
                a.department,
                a.year_of_study,

                u.id AS student_id,
                u.name AS student_name,
                u.email AS student_email,

                CASE
                    WHEN DATE(s.submitted_at) > a.due_date
                        THEN 'Late Submission'
                    ELSE 'On Time'
                END AS submission_status

            FROM submissions s

            INNER JOIN assignments a
                ON s.assignment_id = a.id

            INNER JOIN users u
                ON s.student_id = u.id

            WHERE s.assignment_id = %s
            AND a.faculty_id = %s

            ORDER BY s.submitted_at DESC
            """,
            (
                assignment_id,
                session["user_id"]
            )
        )

        submissions = cursor.fetchall()

        return render_template(
            "submissions.html",
            submissions=submissions,
            selected_department="",
            selected_year=""
        )

    except mysql.connector.Error as error:

        print(
            "ASSIGNMENT SUBMISSIONS ERROR:",
            error
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


# ==========================================================
# DOWNLOAD ASSIGNMENT
# ==========================================================

@app.route(
    "/download/assignment/<filename>"
)
def download_assignment(filename):

    return send_from_directory(
        ASSIGNMENT_FOLDER,
        filename,
        as_attachment=True
    )


# ==========================================================
# DOWNLOAD SUBMISSION
# ==========================================================

@app.route(
    "/download/submission/<filename>"
)
@faculty_required
def download_submission(filename):

    return send_from_directory(
        SUBMISSION_FOLDER,
        filename,
        as_attachment=True
    )


# ==========================================================
# ERROR HANDLERS
# ==========================================================

@app.errorhandler(404)
def page_not_found(error):

    return render_template(
        "index.html"
    ), 404


@app.errorhandler(500)
def internal_server_error(error):

    return """
    <h2>TaskTrack Server Error</h2>
    <p>Something went wrong. Please check the Flask terminal.</p>
    """, 500


# ==========================================================
# RUN APPLICATION
# ==========================================================

if __name__ == "__main__":

    print("========================================")
    print("TASKTRACK APPLICATION")
    print("DATABASE USED BY FLASK:",
          DB_CONFIG["database"])
    print("DATABASE HOST:",
          DB_CONFIG["host"])
    print("========================================")

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )
