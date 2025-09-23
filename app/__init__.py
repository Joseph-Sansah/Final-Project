import os
import json
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, session, render_template, request
from flask_socketio import SocketIO
from flask_login import LoginManager
import mysql.connector
from mysql.connector import Error

# --- Load environment variables ---
load_dotenv()

# --- Config ---
UPLOAD_FOLDER = os.path.join("static", "uploads")
ALLOWED_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif", "pdf", "doc", "docx", "ppt", "pptx", "zip", "txt"
}
DATA_FILE = "courses.json"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Extensions ---
socketio = SocketIO(async_mode="threading", cors_allowed_origins="*")  # Quick fix
login_manager = LoginManager()


# --- File Helpers ---
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def load_courses():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_courses(courses):
    with open(DATA_FILE, "w") as f:
        json.dump(courses, f, indent=4)


# --- Database Connection ---
def get_db_connection():
    """Return a new mysql.connector connection or None if fails."""
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", 3306))
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    database = os.getenv("DB_NAME", "")

    try:
        conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connection_timeout=10,
            charset="utf8mb4",
        )
        return conn
    except Error as e:
        print(f"❌ Database connection failed: {e}")
        return None


# --- Flask App Factory ---
def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "default_secret")
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

    # Attach helpers to app
    app.get_db_connection = get_db_connection
    app.allowed_file = allowed_file

    # --- Audit Logging ---
    def log_action(action, user_id=None, page_url=None):
        user_id = user_id or session.get("user_id")
        ip_address = request.remote_addr if request else "N/A"
        user_agent = request.headers.get("User-Agent") if request and request.headers else "N/A"
        page_url = page_url or (request.path if request else "N/A")
        timestamp = datetime.now()

        try:
            conn = app.get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO audit_logs (user_id, action, page_url, ip_address, user_agent, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (user_id, action, page_url, ip_address, user_agent, timestamp),
                )
                conn.commit()
                cursor.close()
                conn.close()
        except Exception as e:
            print(f"⚠ Audit log failed: {e}")

    app.log_action = log_action

    # --- System Settings Loader ---
    def get_system_settings():
        try:
            conn = app.get_db_connection()
            if conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT setting_key, setting_value FROM system_settings")
                settings = {row["setting_key"]: row["setting_value"] for row in cursor.fetchall()}
                cursor.close()
                conn.close()
                return settings
        except Exception as e:
            print(f"⚠ Error loading system settings: {e}")
        return {}

    @app.context_processor
    def inject_settings():
        return dict(settings_global=get_system_settings())

    # --- Maintenance Mode ---
    @app.before_request
    def check_maintenance():
        exempt_endpoints = ["static", "main.login", "main.register", "main.forgot_password", "main.home"]
        if request.endpoint in exempt_endpoints:
            return
        settings = get_system_settings()
        if settings.get("maintenance_mode") == "true" and session.get("role") != "admin":
            return render_template("maintenance.html")

    # --- Last Seen Tracker ---
    @app.before_request
    def update_last_seen():
        user_id = session.get("user_id")
        if user_id:
            try:
                conn = app.get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE users SET last_seen = NOW() WHERE id = %s", (user_id,))
                    conn.commit()
                    cursor.close()
                    conn.close()
            except Exception as e:
                print(f"⚠ Failed to update last seen: {e}")

    # --- Register Blueprints ---
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # --- Login Manager ---
    login_manager.init_app(app)
    login_manager.login_view = "main.login"
    login_manager.login_message_category = "info"

    from .models import load_user
    login_manager.user_loader(load_user)

    # --- Initialize SocketIO ---
    socketio.init_app(app)

    return app