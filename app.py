from functools import wraps
from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, send_from_directory)
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "development_secret_key"
)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST"),
    "user": os.environ.get("DB_USER"),
    "password": os.environ.get("DB_PASSWORD"),
    "database": os.environ.get("DB_NAME"),
    "port": int(
        os.environ.get(
            "DB_PORT",
            3306
        )
    )
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ASSIGNMENT_UPLOAD_FOLDER = os.path.join(
    BASE_DIR, "uploads", "assignments"
)

SUBMISSION_UPLOAD_FOLDER = os.path.join(
    BASE_DIR, "uploads", "submissions"
)
os.makedirs(ASSIGNMENT_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SUBMISSION_UPLOAD_FOLDER, exist_ok=True)
app.config["ASSIGNMENT_UPLOAD_FOLDER"] = ASSIGNMENT_UPLOAD_FOLDER
app.config["SUBMISSION_UPLOAD_FOLDER"] = SUBMISSION_UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024


def get_db_connection():
    try:
        return mysql.connector.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"],
            port=DB_CONFIG["port"]
        )
    except Error as e:
        print(
            "DATABASE CONNECTION ERROR:",
            e
        )

        return None


def student_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):

        if session.get("role") != "student":
            flash("Please login as a student.", "error")
            return redirect(url_for("student_login"))

        return function(*args, **kwargs)

    return wrapper


def faculty_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):

        if session.get("role") != "faculty":
            flash("Please login as faculty.", "error")
            return redirect(url_for("faculty_login"))

        return function(*args, **kwargs)

    return wrapper


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not name or not email or not password:
            flash("Please fill all required fields.", "error")
            return render_template("register.html")

        connection = get_db_connection()

        if connection is None:
            flash("Unable to connect to database.", "error")
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

            if cursor.fetchone():
                flash(
                    "An account with this email already exists.",
                    "error"
                )
                return render_template("register.html")

            password_hash = generate_password_hash(password)

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
                    'faculty',
                    NULL,
                    NULL
                )
                """,
                (
                    name,
                    email,
                    password_hash
                )
            )

            connection.commit()

            flash(
                "Faculty account created successfully.",
                "success"
            )

            return redirect(url_for("faculty_login"))

        except Error as e:

            connection.rollback()
            print("FACULTY REGISTER ERROR:", e)

            flash(
                "Unable to create faculty account.",
                "error"
            )

        finally:
            cursor.close()
            connection.close()

    return render_template("register.html")


@app.route("/student/register", methods=["GET", "POST"])
def student_register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        department = request.form.get("department", "").strip()
        year_of_study = request.form.get("year_of_study", "").strip()

        if (
            not name
            or not email
            or not password
            or not department
            or not year_of_study
        ):
            flash("Please fill all fields.", "error")
            return render_template("student_register.html")

        connection = get_db_connection()

        if connection is None:
            flash("Unable to connect to database.", "error")
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

            if cursor.fetchone():
                flash(
                    "An account with this email already exists.",
                    "error"
                )
                return render_template("student_register.html")

            password_hash = generate_password_hash(password)

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
                    password_hash,
                    department,
                    year_of_study
                )
            )

            connection.commit()

            flash(
                "Student account created successfully.",
                "success"
            )

            return redirect(url_for("student_login"))

        except Error as e:

            connection.rollback()
            print("STUDENT REGISTER ERROR:", e)

            flash(
                "Unable to create student account.",
                "error"
            )

        finally:
            cursor.close()
            connection.close()

    return render_template("student_register.html")


@app.route("/student/login", methods=["GET", "POST"])
def student_login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not email or not password:
            flash(
                "Please enter email and password.",
                "error"
            )
            return render_template("student_login.html")

        connection = get_db_connection()

        if connection is None:
            flash(
                "Unable to connect to database.",
                "error"
            )
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

            user = cursor.fetchone()

            if user and check_password_hash(
                user["password"],
                password
            ):

                session.clear()

                session["user_id"] = user["id"]
                session["name"] = user["name"]
                session["email"] = user["email"]
                session["role"] = "student"
                session["department"] = user["department"]
                session["year_of_study"] = user["year_of_study"]

                return redirect(
                    url_for("student_dashboard")
                )

            flash(
                "Invalid student email or password.",
                "error"
            )

        except Error as e:

            print("STUDENT LOGIN ERROR:", e)

            flash(
                "Unable to login.",
                "error"
            )

        finally:
            cursor.close()
            connection.close()

    return render_template("student_login.html")


@app.route("/faculty/login", methods=["GET", "POST"])
def faculty_login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not email or not password:
            flash(
                "Please enter email and password.",
                "error"
            )
            return render_template("faculty_login.html")

        connection = get_db_connection()

        if connection is None:
            flash(
                "Unable to connect to database.",
                "error"
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

            user = cursor.fetchone()

            if user and check_password_hash(
                user["password"],
                password
            ):

                session.clear()

                session["user_id"] = user["id"]
                session["name"] = user["name"]
                session["email"] = user["email"]
                session["role"] = "faculty"

                return redirect(
                    url_for("faculty_dashboard")
                )

            flash(
                "Invalid faculty email or password.",
                "error"
            )

        except Error as e:

            print("FACULTY LOGIN ERROR:", e)

            flash(
                "Unable to login.",
                "error"
            )

        finally:
            cursor.close()
            connection.close()

    return render_template("faculty_login.html")


@app.route("/login")
def login():
    return redirect(url_for("student_login"))


@app.route("/student/dashboard")
@student_required
def student_dashboard():

    student_id = session["user_id"]
    department = session.get("department")
    year_of_study = session.get("year_of_study")

    connection = get_db_connection()

    if connection is None:
        flash(
            "Unable to connect to database.",
            "error"
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

                CASE
                    WHEN s.id IS NOT NULL
                    THEN 1
                    ELSE 0
                END AS submitted

            FROM assignments a

            LEFT JOIN users u
                ON a.faculty_id = u.id

            LEFT JOIN submissions s
                ON a.id = s.assignment_id
                AND s.student_id = %s

            WHERE a.department = %s
            AND a.year_of_study = %s

            ORDER BY
                a.due_date ASC,
                a.created_at DESC
            """,
            (
                student_id,
                department,
                year_of_study
            )
        )

        assignments = cursor.fetchall()

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM submissions
            WHERE student_id = %s
            """,
            (student_id,)
        )

        result = cursor.fetchone()

        submission_count = (
            result["total"]
            if result
            else 0
        )

        total_assignments = len(assignments)

        available_count = sum(
            1
            for assignment in assignments
            if not assignment["submitted"]
        )

        submitted_count = sum(
            1
            for assignment in assignments
            if assignment["submitted"]
        )

        return render_template(
            "student_dashboard.html",
            assignments=assignments,
            total_assignments=total_assignments,
            available_count=available_count,
            submission_count=submission_count,
            submitted_count=submitted_count,
            department=department,
            year_of_study=year_of_study
        )

    except Error as e:

        print("STUDENT DASHBOARD ERROR:", e)

        flash(
            "Unable to load student dashboard.",
            "error"
        )

        return redirect(url_for("student_login"))

    finally:
        cursor.close()
        connection.close()


@app.route(
    "/student/submit/<int:assignment_id>",
    methods=["POST"]
)
@student_required
def student_submit(assignment_id):

    student_id = session["user_id"]

    file = request.files.get("file")

    if not file or not file.filename:
        flash(
            "Please select a file.",
            "error"
        )
        return redirect(url_for("student_dashboard"))

    filename = secure_filename(file.filename)

    if not filename:
        flash(
            "Invalid file name.",
            "error"
        )
        return redirect(url_for("student_dashboard"))

    connection = get_db_connection()

    if connection is None:
        flash(
            "Unable to connect to database.",
            "error"
        )
        return redirect(url_for("student_dashboard"))

    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id,
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
                "error"
            )
            return redirect(url_for("student_dashboard"))

        if (
            assignment["department"] != session.get("department")
            or
            assignment["year_of_study"] != session.get("year_of_study")
        ):
            flash(
                "You cannot submit this assignment.",
                "error"
            )
            return redirect(url_for("student_dashboard"))

        safe_filename = (
            f"{student_id}_{assignment_id}_{filename}"
        )

        file_path = os.path.join(
            app.config["SUBMISSION_UPLOAD_FOLDER"],
            safe_filename
        )

        file.save(file_path)

        cursor.execute(
            """
            SELECT id, file_name
            FROM submissions
            WHERE assignment_id = %s
            AND student_id = %s
            """,
            (
                assignment_id,
                student_id
            )
        )

        existing = cursor.fetchone()

        if existing:

            old_file = existing["file_name"]

            cursor.execute(
                """
                UPDATE submissions
                SET file_name = %s,
                    submitted_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (
                    safe_filename,
                    existing["id"]
                )
            )

            if old_file != safe_filename:

                old_path = os.path.join(
                    app.config["SUBMISSION_UPLOAD_FOLDER"],
                    old_file
                )

                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except OSError:
                        pass

            message = (
                "Assignment submission updated successfully."
            )

        else:

            cursor.execute(
                """
                INSERT INTO submissions
                (
                    assignment_id,
                    student_id,
                    file_name,
                    submitted_at
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    assignment_id,
                    student_id,
                    safe_filename
                )
            )

            message = (
                "Assignment submitted successfully."
            )

        connection.commit()

        flash(message, "success")

    except Error as e:

        connection.rollback()

        print("STUDENT SUBMISSION ERROR:", e)

        flash(
            "Unable to submit assignment.",
            "error"
        )

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("student_dashboard"))


@app.route("/student/submissions")
@student_required
def student_submissions():

    student_id = session["user_id"]

    connection = get_db_connection()

    if connection is None:
        flash(
            "Unable to connect to database.",
            "error"
        )
        return redirect(url_for("student_login"))

    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                s.id AS submission_id,
                s.file_name AS submitted_file,
                s.submitted_at,

                a.id AS assignment_id,
                a.title AS assignment_title,
                a.description,
                a.subject,
                a.due_date,
                a.department,
                a.year_of_study,

                u.name AS faculty_name

            FROM submissions s

            INNER JOIN assignments a
                ON s.assignment_id = a.id

            LEFT JOIN users u
                ON a.faculty_id = u.id

            WHERE s.student_id = %s

            ORDER BY
                s.submitted_at DESC
            """,
            (student_id,)
        )

        submissions = cursor.fetchall()

        return render_template(
            "student_submissions.html",
            submissions=submissions
        )

    except Error as e:

        print("STUDENT SUBMISSIONS ERROR:", e)

        flash(
            "Unable to load submissions.",
            "error"
        )

        return redirect(url_for("student_dashboard"))

    finally:
        cursor.close()
        connection.close()


@app.route("/faculty/dashboard")
@faculty_required
def faculty_dashboard():

    faculty_id = session["user_id"]

    connection = get_db_connection()

    if connection is None:
        flash(
            "Unable to connect to database.",
            "error"
        )
        return redirect(url_for("faculty_login"))

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
                a.department,
                a.year_of_study,
                a.created_at,

                (
                    SELECT COUNT(*)
                    FROM submissions s
                    WHERE s.assignment_id = a.id
                ) AS submission_count

            FROM assignments a

            WHERE a.faculty_id = %s

            ORDER BY
                a.created_at DESC
            """,
            (faculty_id,)
        )

        assignments = cursor.fetchall()

        assignment_count = len(assignments)

        cursor.execute(
            """
            SELECT COUNT(*) AS total

            FROM submissions s

            INNER JOIN assignments a
                ON s.assignment_id = a.id

            WHERE a.faculty_id = %s
            """,
            (faculty_id,)
        )

        result = cursor.fetchone()

        submission_count = (
            result["total"]
            if result
            else 0
        )

        cursor.execute(
            """
            SELECT
                COUNT(DISTINCT s.student_id) AS total

            FROM submissions s

            INNER JOIN assignments a
                ON s.assignment_id = a.id

            WHERE a.faculty_id = %s
            """,
            (faculty_id,)
        )

        result = cursor.fetchone()

        students_submitted = (
            result["total"]
            if result
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

        print("FACULTY DASHBOARD ERROR:", e)

        flash(
            "Unable to load faculty dashboard.",
            "error"
        )

        return redirect(url_for("faculty_login"))

    finally:
        cursor.close()
        connection.close()


@app.route(
    "/faculty/upload",
    methods=["GET", "POST"]
)
@faculty_required
def faculty_upload():

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        subject = request.form.get("subject", "").strip()
        description = request.form.get("description", "").strip()
        department = request.form.get("department", "").strip()
        year_of_study = request.form.get("year_of_study", "").strip()
        due_date = request.form.get("due_date", "").strip()

        file = request.files.get("file")

        if (
            not title
            or not subject
            or not department
            or not year_of_study
            or not due_date
        ):
            flash(
                "Please fill all required fields.",
                "error"
            )
            return render_template(
                "upload_assignments.html"
            )

        filename = None

        if file and file.filename:

            original_filename = secure_filename(
                file.filename
            )

            if original_filename:

                filename = (
                    f"{session['user_id']}_"
                    f"{original_filename}"
                )

                file.save(
                    os.path.join(
                        app.config["ASSIGNMENT_UPLOAD_FOLDER"],
                        filename
                    )
                )

        connection = get_db_connection()

        if connection is None:
            flash(
                "Unable to connect to database.",
                "error"
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

        except Error as e:

            connection.rollback()

            print("FACULTY UPLOAD ERROR:", e)

            flash(
                "Unable to upload assignment.",
                "error"
            )

        finally:
            cursor.close()
            connection.close()

    return render_template(
        "upload_assignments.html"
    )


# ============================================================
# FACULTY SUBMISSIONS WITH DEPARTMENT AND YEAR FILTER
# ============================================================

@app.route("/faculty/submissions")
@faculty_required
def faculty_submissions():

    faculty_id = session["user_id"]

    # --------------------------------------------------------
    # GET FILTER VALUES
    # --------------------------------------------------------

    selected_department = request.args.get(
        "department",
        ""
    ).strip()

    selected_year = request.args.get(
        "year_of_study",
        ""
    ).strip()

    # --------------------------------------------------------
    # DATABASE CONNECTION
    # --------------------------------------------------------

    connection = get_db_connection()

    if connection is None:

        flash(
            "Unable to connect to database.",
            "error"
        )

        return redirect(
            url_for("faculty_dashboard")
        )

    cursor = connection.cursor(dictionary=True)

    try:

        # ----------------------------------------------------
        # BASE QUERY
        # ----------------------------------------------------

        query = """
            SELECT

                s.id AS submission_id,
                s.file_name AS submitted_file,
                s.submitted_at,

                a.id AS assignment_id,
                a.title AS assignment_title,
                a.description,
                a.subject,
                a.due_date,
                a.department,
                a.year_of_study,

                u.id AS student_id,
                u.name AS student_name,
                u.email AS student_email

            FROM submissions s

            INNER JOIN assignments a
                ON s.assignment_id = a.id

            INNER JOIN users u
                ON s.student_id = u.id

            WHERE a.faculty_id = %s
        """

        # ----------------------------------------------------
        # QUERY PARAMETERS
        # ----------------------------------------------------

        parameters = [faculty_id]

        # ----------------------------------------------------
        # DEPARTMENT FILTER
        # ----------------------------------------------------

        if selected_department:

            query += """

                AND a.department = %s

            """

            parameters.append(
                selected_department
            )

        # ----------------------------------------------------
        # YEAR OF STUDY FILTER
        # ----------------------------------------------------

        if selected_year:

            query += """

                AND a.year_of_study = %s

            """

            parameters.append(
                selected_year
            )

        # ----------------------------------------------------
        # ORDER RESULTS
        # ----------------------------------------------------

        query += """

            ORDER BY
                s.submitted_at DESC

        """

        # ----------------------------------------------------
        # EXECUTE QUERY
        # ----------------------------------------------------

        cursor.execute(
            query,
            tuple(parameters)
        )

        submissions = cursor.fetchall()

        # ----------------------------------------------------
        # SHOW MESSAGE IF NO RESULTS
        # ----------------------------------------------------

        if (
            (selected_department or selected_year)
            and
            not submissions
        ):

            flash(
                "No submissions found for the selected Department and Year of Study.",
                "error"
            )

        # ----------------------------------------------------
        # RETURN PAGE
        # ----------------------------------------------------

        return render_template(

            "submissions.html",

            submissions=submissions,

            assignment=None,

            selected_department=selected_department,

            selected_year=selected_year

        )

    except Error as e:

        print(
            "FACULTY SUBMISSIONS ERROR:",
            e
        )

        flash(
            "Unable to load submissions.",
            "error"
        )

        return redirect(
            url_for("faculty_dashboard")
        )

    finally:

        cursor.close()

        connection.close()


@app.route(
    "/faculty/assignment/<int:assignment_id>/submissions"
)
@faculty_required
def faculty_assignment_submissions(assignment_id):

    faculty_id = session["user_id"]

    connection = get_db_connection()

    if connection is None:
        flash(
            "Unable to connect to database.",
            "error"
        )
        return redirect(url_for("faculty_dashboard"))

    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id,
                title,
                description,
                subject,
                due_date,
                file_name,
                department,
                year_of_study
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
                "error"
            )
            return redirect(url_for("faculty_dashboard"))

        cursor.execute(
            """
            SELECT
                s.id AS submission_id,
                s.file_name AS submitted_file,
                s.submitted_at,

                u.id AS student_id,
                u.name AS student_name,
                u.email AS student_email,
                u.department,
                u.year_of_study

            FROM submissions s

            INNER JOIN users u
                ON s.student_id = u.id

            WHERE s.assignment_id = %s

            ORDER BY
                s.submitted_at DESC
            """,
            (assignment_id,)
        )

        submissions = cursor.fetchall()

        return render_template(
            "submissions.html",
            submissions=submissions,
            assignment=assignment
        )

    except Error as e:
        print("ASSIGNMENT SUBMISSIONS ERROR:", e)
        flash(
            "Unable to load assignment submissions.",
            "error"
        )
        return redirect(
            url_for("faculty_dashboard")
        )
    finally:
        cursor.close()
        connection.close()


@app.route("/download/assignment/<path:filename>")
@student_required
def download_assignment(filename):

    return send_from_directory(
        app.config["ASSIGNMENT_UPLOAD_FOLDER"],
        filename,
        as_attachment=True
    )


@app.route("/download/submission/<path:filename>")
@faculty_required
def download_submission(filename):

    return send_from_directory(
        app.config["SUBMISSION_UPLOAD_FOLDER"],
        filename,
        as_attachment=True
    )


@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(url_for("index"))


@app.errorhandler(404)
def page_not_found(error):
    return render_template("index.html"), 404


@app.errorhandler(413)
def file_too_large(error):

    flash(
        "File is too large. Maximum size is 16 MB.",
        "error"
    )

    if session.get("role") == "student":
        return redirect(url_for("student_dashboard"))

    if session.get("role") == "faculty":
        return redirect(url_for("faculty_dashboard"))

    return redirect(url_for("index"))


@app.errorhandler(500)
def internal_server_error(error):

    print("SERVER ERROR:", error)

    return """
    <h2>TaskTrack Server Error</h2>
    <p>Please check the VS Code terminal for the error.</p>
    """, 500


if __name__ == "__main__":

    app.run(
        debug=True,
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        )
    )
