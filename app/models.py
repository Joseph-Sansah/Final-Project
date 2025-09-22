from flask import current_app
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
# We'll need to pass the db connection or app object for proper usage in a larger app
# For now, we'll assume access to app.get_db_connection is available when these models are used.

class User:
    """
    A simple model representing a user, for clarity and potential ORM transition.
    In this current setup, direct database calls are made in routes.py.
    This class can be expanded if an ORM like SQLAlchemy is introduced.
    """
    def __init__(self, id, full_name, email, password_hash, role, status='Active', force_password_change=False, profile_image=None, last_seen=None):
        self.id = id
        self.full_name = full_name
        self.email = email
        self.password_hash = password_hash
        self.role = role
        self.status = status
        self.force_password_change = force_password_change
        self.profile_image = profile_image
        self.last_seen = last_seen

    @staticmethod
    def get_by_id(user_id, app_instance):
        """Fetches a user by ID from the database."""
        conn = app_instance.get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user_data = cursor.fetchone()
            cursor.close()
            conn.close()
            if user_data:
                return User(**user_data)
        return None

    @staticmethod
    def get_by_email(email, app_instance):
        """Fetches a user by email from the database."""
        conn = app_instance.get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user_data = cursor.fetchone()
            cursor.close()
            conn.close()
            if user_data:
                return User(**user_data)
        return None

    def set_password(self, password):
        """Hashes and sets the user's password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Checks if the provided password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    def save(self, app_instance):
        """Saves or updates the user in the database."""
        conn = app_instance.get_db_connection()
        if conn:
            cursor = conn.cursor()
            if self.id: # Update existing user
                cursor.execute("""
                    UPDATE users SET full_name = %s, email = %s, password_hash = %s,
                    role = %s, status = %s, force_password_change = %s, profile_image = %s
                    WHERE id = %s
                """, (self.full_name, self.email, self.password_hash, self.role,
                      self.status, self.force_password_change, self.profile_image, self.id))
            else: # Insert new user
                cursor.execute("""
                    INSERT INTO users (full_name, email, password_hash, role, status, force_password_change, profile_image)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (self.full_name, self.email, self.password_hash, self.role,
                      self.status, self.force_password_change, self.profile_image))
                self.id = cursor.lastrowid # Get the ID of the newly inserted user
            conn.commit()
            cursor.close()
            conn.close()

            
import mysql.connector
from mysql.connector import Error

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host='localhost',
            database='collabo_learn',
            user='root',
            password='Js@1142550'
        )
        return connection
    except Error as e:
        print(f"Error connecting to database: {e}")
        return None
    
class User:
    @staticmethod
    def get_by_id(user_id):
        # Replace this with your DB logic to fetch the user
        pass

# This function is used by Flask-Login
def load_user(user_id):
    return User.get_by_id(user_id)


def calculate_progress(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Total assignments
    cursor.execute("""
        SELECT COUNT(*) FROM assignments
        WHERE student_id = %s
    """, (student_id,))
    total = cursor.fetchone()[0]

    # Completed assignments
    cursor.execute("""
        SELECT COUNT(*) FROM assignments
        WHERE student_id = %s AND status = 'completed'
    """, (student_id,))
    completed = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    if total == 0:
        return 0
    return round((completed / total) * 100)



from app import create_app, socketio
