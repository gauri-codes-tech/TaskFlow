
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from pathlib import Path
from dotenv import load_dotenv
from psycopg.rows import dict_row
import psycopg
import re
import os

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "taskflow-local-development-key"
)

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

CATEGORIES = ["Work", "Study", "Personal", "Other"]


def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing from .env")

    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row
    )


def set_user_session(user):
    first_name = (user["first_name"] or "").strip()
    last_name = (user["last_name"] or "").strip()

    initials = (
        (first_name[:1] if first_name else "")
        + (last_name[:1] if last_name else "")
    ).upper()

    if not initials:
        initials = user["username"][:2].upper()

    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["first_name"] = first_name
    session["last_name"] = last_name
    session["initials"] = initials


def get_logged_in_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    conn = get_db_connection()

    try:
        user = conn.execute(
            """
            SELECT id, first_name, last_name, username, email
            FROM users
            WHERE id = %s
            """,
            (user_id,)
        ).fetchone()

        return user
    finally:
        conn.close()


def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Please log in first"}), 401
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


def task_to_dict(task):
    return {
        "id": task["id"],
        "title": task["title"],
        "description": task["description"] or "",
        "priority": task["priority"],
        "due_date": task["due_date"] or "",
        "category": task["category"] or "Other",
        "completed": bool(task["completed"])
    }


@app.route("/")
@login_required
def home():
    user = get_logged_in_user()

    if user is None:
        session.clear()
        return redirect(url_for("login"))

    set_user_session(user)

    first_name = (user["first_name"] or "").strip()
    last_name = (user["last_name"] or "").strip()

    workspace_name = (
        f"{first_name}'s Workspace"
        if first_name
        else f"{user['username']}'s Workspace"
    )

    return render_template(
        "index.html",
        first_name=first_name,
        last_name=last_name,
        full_name=f"{first_name} {last_name}".strip(),
        initials=session["initials"],
        workspace_name=workspace_name
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not first_name or not last_name:
            return render_template(
                "register.html",
                error="Please enter your first and last name."
            )

        if len(username) < 3:
            return render_template(
                "register.html",
                error="Username must contain at least 3 characters."
            )

        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            return render_template(
                "register.html",
                error="Please enter a valid email address."
            )

        password_pattern = (
            r"^(?=.*[A-Z])(?=.*[0-9])(?=.*[^A-Za-z0-9\s])\S{8,16}$"
        )

        if not re.match(password_pattern, password):
            return render_template(
                "register.html",
                error=(
                    "Password must be 8–16 characters long and contain "
                    "at least one uppercase letter, one number, and "
                    "one special character. Spaces are not allowed."
                )
            )

        conn = get_db_connection()

        try:
            existing_users = conn.execute(
                "SELECT COUNT(*) AS count FROM users"
            ).fetchone()["count"]

            password_hash = generate_password_hash(password)

            cursor = conn.execute(
                """
                INSERT INTO users
                (first_name, last_name, username, email, password_hash)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (first_name, last_name, username, email, password_hash)
            )

            user_id = cursor.fetchone()["id"]

            if existing_users == 0:
                conn.execute(
                    """
                    UPDATE tasks
                    SET user_id = %s
                    WHERE user_id IS NULL
                    """,
                    (user_id,)
                )

            conn.commit()

            user = conn.execute(
                "SELECT * FROM users WHERE id = %s",
                (user_id,)
            ).fetchone()

            set_user_session(user)
            return redirect(url_for("home"))

        except psycopg.IntegrityError:
            conn.rollback()
            return render_template(
                "register.html",
                error="That username or email is already registered."
            )

        finally:
            conn.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        user = get_logged_in_user()

        if user:
            set_user_session(user)
            return redirect(url_for("home"))

        session.clear()

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db_connection()

        try:
            user = conn.execute(
                "SELECT * FROM users WHERE email = %s",
                (email,)
            ).fetchone()
        finally:
            conn.close()

        if not user:
            return render_template(
                "login.html",
                error="This email is not registered. Please create an account.",
                email=email
            )

        if not check_password_hash(user["password_hash"], password):
            return render_template(
                "login.html",
                error="Incorrect password. Please enter the correct password.",
                email=email
            )

        set_user_session(user)
        return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/calendar")
@login_required
def calendar():
    return render_template("calendar.html")


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = get_logged_in_user()

    if user is None:
        session.clear()
        return redirect(url_for("login"))

    message = None
    error = None

    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()

        if not first_name or not last_name:
            error = "Please enter your first and last name."

        elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            error = "Please enter a valid email address."

        else:
            conn = get_db_connection()

            try:
                conn.execute(
                    """
                    UPDATE users
                    SET first_name = %s, last_name = %s, email = %s
                    WHERE id = %s
                    """,
                    (first_name, last_name, email, session["user_id"])
                )

                conn.commit()
                message = "Profile updated successfully!"

            except psycopg.IntegrityError:
                conn.rollback()
                error = "This email address is already registered."

            finally:
                conn.close()

        user = get_logged_in_user()

        if user:
            set_user_session(user)

    return render_template(
        "profile.html",
        user=user,
        message=message,
        error=error
    )


@app.route("/change-password", methods=["POST"])
@login_required
def change_password():
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    user = get_logged_in_user()

    if user is None:
        session.clear()
        return redirect(url_for("login"))

    conn = get_db_connection()

    try:
        full_user = conn.execute(
            "SELECT password_hash FROM users WHERE id = %s",
            (session["user_id"],)
        ).fetchone()

        if not check_password_hash(
            full_user["password_hash"], current_password
        ):
            return render_template(
                "profile.html",
                user=user,
                error="Your current password is incorrect."
            )

        password_pattern = (
            r"^(?=.*[A-Z])(?=.*[0-9])(?=.*[^A-Za-z0-9\s])\S{8,16}$"
        )

        if not re.match(password_pattern, new_password):
            return render_template(
                "profile.html",
                user=user,
                error=(
                    "Password must be 8-16 characters and contain "
                    "at least one uppercase letter, one number and "
                    "one special symbol. Spaces are not allowed."
                )
            )

        if new_password != confirm_password:
            return render_template(
                "profile.html",
                user=user,
                error="New passwords do not match."
            )

        if check_password_hash(full_user["password_hash"], new_password):
            return render_template(
                "profile.html",
                user=user,
                error=(
                    "Your new password must be different from "
                    "your current password."
                )
            )

        new_hash = generate_password_hash(new_password)

        conn.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (new_hash, session["user_id"])
        )

        conn.commit()

        return render_template(
            "profile.html",
            user=user,
            message="Password changed successfully!"
        )

    finally:
        conn.close()


@app.route("/api/tasks", methods=["GET"])
@login_required
def get_tasks():
    conn = get_db_connection()

    try:
        tasks = conn.execute(
            """
            SELECT * FROM tasks
            WHERE user_id = %s
            ORDER BY id DESC
            """,
            (session["user_id"],)
        ).fetchall()

        return jsonify([task_to_dict(task) for task in tasks])

    finally:
        conn.close()


@app.route("/api/tasks", methods=["POST"])
@login_required
def add_task():
    data = request.get_json(silent=True) or {}

    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    priority = data.get("priority", "Medium")
    due_date = data.get("due_date", "")
    category = data.get("category", "Personal")

    if not title:
        return jsonify({"error": "Task title is required"}), 400

    if priority not in ["Low", "Medium", "High"]:
        return jsonify({"error": "Invalid priority"}), 400

    if category not in CATEGORIES:
        return jsonify({"error": "Invalid category"}), 400

    conn = get_db_connection()

    try:
        cursor = conn.execute(
            """
            INSERT INTO tasks
            (title, description, priority, due_date, category, user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                title, description, priority, due_date,
                category, session["user_id"]
            )
        )

        task_id = cursor.fetchone()["id"]
        conn.commit()

        task = conn.execute(
            "SELECT * FROM tasks WHERE id = %s AND user_id = %s",
            (task_id, session["user_id"])
        ).fetchone()

        return jsonify(task_to_dict(task)), 201

    finally:
        conn.close()


@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
@login_required
def update_task(task_id):
    data = request.get_json(silent=True) or {}

    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    priority = data.get("priority", "Medium")
    due_date = data.get("due_date", "")
    category = data.get("category", "Personal")

    if not title:
        return jsonify({"error": "Task title is required"}), 400

    if priority not in ["Low", "Medium", "High"]:
        return jsonify({"error": "Invalid priority"}), 400

    if category not in CATEGORIES:
        return jsonify({"error": "Invalid category"}), 400

    conn = get_db_connection()

    try:
        cursor = conn.execute(
            """
            UPDATE tasks
            SET title = %s, description = %s, priority = %s,
                due_date = %s, category = %s
            WHERE id = %s AND user_id = %s
            """,
            (
                title, description, priority, due_date,
                category, task_id, session["user_id"]
            )
        )

        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "Task not found"}), 404

        task = conn.execute(
            "SELECT * FROM tasks WHERE id = %s AND user_id = %s",
            (task_id, session["user_id"])
        ).fetchone()

        return jsonify(task_to_dict(task))

    finally:
        conn.close()


@app.route("/api/tasks/<int:task_id>/toggle", methods=["PATCH"])
@login_required
def toggle_task(task_id):
    conn = get_db_connection()

    try:
        task = conn.execute(
            """
            SELECT * FROM tasks
            WHERE id = %s AND user_id = %s
            """,
            (task_id, session["user_id"])
        ).fetchone()

        if task is None:
            return jsonify({"error": "Task not found"}), 404

        new_status = 0 if task["completed"] else 1

        conn.execute(
            """
            UPDATE tasks
            SET completed = %s
            WHERE id = %s AND user_id = %s
            """,
            (new_status, task_id, session["user_id"])
        )

        conn.commit()

        updated_task = conn.execute(
            """
            SELECT * FROM tasks
            WHERE id = %s AND user_id = %s
            """,
            (task_id, session["user_id"])
        ).fetchone()

        return jsonify(task_to_dict(updated_task))

    finally:
        conn.close()


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
@login_required
def delete_task(task_id):
    conn = get_db_connection()

    try:
        cursor = conn.execute(
            """
            DELETE FROM tasks
            WHERE id = %s AND user_id = %s
            """,
            (task_id, session["user_id"])
        )

        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "Task not found"}), 404

        return jsonify({"message": "Task deleted successfully"})

    finally:
        conn.close()


if __name__ == "__main__":
    app.run(debug=True)
