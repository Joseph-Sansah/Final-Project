from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, current_app, make_response, send_from_directory, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from mysql.connector import Error
import mysql.connector
from datetime import datetime, timedelta
import calendar as cal
from email.mime.text import MIMEText
import smtplib
import random
import string
import os
from flask import jsonify
import json
from flask_socketio import emit
from . import socketio
from flask import get_flashed_messages, flash, session, redirect, url_for, render_template, request, current_app
from app.models import get_db_connection
from app.models import calculate_progress

import app

UPLOAD_FOLDER = 'app/static/uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@socketio.on('connect')
def handle_connect():
    user_id = session.get('user_id')
    if user_id:
        emit('presence_update', {'user_id': user_id, 'status': 'Online'}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    user_id = session.get('user_id')
    if user_id:
        emit('presence_update', {'user_id': user_id, 'status': 'Offline'}, broadcast=True)


# Import the User model (if you uncomment the ORM-like usage in profile update)
from .models import User

main = Blueprint('main', __name__)

# --- HOME ROUTE ---
@main.route('/')
def home():
    return render_template('index.html')

# --- REGISTER ROUTE ---
@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        role = request.form['role']
        admin_code = request.form.get('admin_code', '')

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')

        conn = current_app.get_db_connection()
        if not conn:
            flash('Database connection error.', 'danger')
            return render_template('register.html')

        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        if user:
            flash('Email already registered.', 'danger')
            cursor.close()
            conn.close()
            return render_template('register.html')

        if role == 'admin':
            cursor.execute("SELECT code FROM admin_codes WHERE is_used=FALSE")
            valid_codes = [code['code'] for code in cursor.fetchall()]
            if admin_code not in valid_codes:
                flash('Invalid admin code.', 'danger')
                cursor.close()
                conn.close()
                return render_template('register.html')
            cursor.execute("UPDATE admin_codes SET is_used=TRUE WHERE code=%s", (admin_code,))

        password_hash = generate_password_hash(password)
        cursor.execute("""
            INSERT INTO users (full_name, email, password_hash, role, status, force_password_change)
            VALUES (%s, %s, %s, %s, 'Active', TRUE)
        """, (full_name, email, password_hash, role))

        conn.commit()
        cursor.close()
        conn.close()
        current_app.log_action(action='user_registered')
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('main.login'))

    return render_template('register.html')



@main.route('/instructor_dashboard', methods=['GET', 'POST'], endpoint='instructor_dashboard')
def instructor_dashboard():
    if session.get('role') != 'instructor':
        flash("Access denied.", 'danger')
        return redirect(url_for('main.login'))
    
    instructor_id = session['user_id']
    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    new_course_id = None
    new_forum_id = None
    
    # ==================== Handle POST Submissions ====================
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        try:
            if form_type == 'create_course':
                cursor.execute("""
                    INSERT INTO courses (title, description, tags, instructor_id, forum_id, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, (
                    request.form.get('course_title'),
                    request.form.get('course_description'),
                    request.form.get('tags'),
                    instructor_id,
                    request.form.get('forum_id') or None
                ))
                conn.commit()
                new_course_id = cursor.lastrowid
                flash("✅ Course created successfully!", 'success')
            elif form_type == 'create_forum':
                cursor.execute("""
                    INSERT INTO forums (course_id, instructor_id, title, description, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                """, (
                    request.form.get('course_id'),
                    instructor_id,
                    request.form.get('forum_title'),
                    request.form.get('forum_description') or ''
                ))
                conn.commit()
                new_forum_id = cursor.lastrowid
                flash("✅ Forum created successfully!", 'success')
            # ... other form_type handlers can be added here ...
        except Exception as e:
            conn.rollback()
            flash(f"❌ An error occurred: {str(e)}", 'danger')
    
    # ==================== Fetch Instructor Info ====================
    cursor.execute("SELECT full_name FROM users WHERE id = %s", (instructor_id,))
    instructor = cursor.fetchone()
    instructor_name = instructor['full_name'] if instructor else 'Instructor'
    
    # ==================== Fetch Forums Created by Instructor ====================
    try:
        cursor.execute("""
            SELECT f.id, f.title, f.description, f.created_at,
                   (SELECT COUNT(*) FROM forum_replies WHERE forum_id = f.id) AS reply_count,
                   u.full_name AS created_by
            FROM forums f
            JOIN users u ON f.instructor_id = u.id
            WHERE f.instructor_id = %s AND (f.is_deleted IS NULL OR f.is_deleted = 0)
            ORDER BY f.created_at DESC
        """, (instructor_id,))
        forums = cursor.fetchall()
        for forum in forums:
            forum['is_new'] = (forum['id'] == new_forum_id)
    except Exception as e:
        current_app.logger.error(f"Error fetching forums: {e}")
        forums = []
    
    # ==================== Fetch Courses Created by Instructor ====================
    try:
        cursor.execute("""
            SELECT c.id, c.title, c.description, c.tags,
                   (SELECT COUNT(*) FROM enrollments e WHERE e.course_id = c.id) AS enrolled_students
            FROM courses c
            WHERE c.instructor_id = %s AND (c.is_deleted IS NULL OR c.is_deleted = 0)
            ORDER BY c.created_at DESC
        """, (instructor_id,))
        courses = cursor.fetchall()
        for course in courses:
            course['is_new'] = (course['id'] == new_course_id)
    except Exception as e:
        current_app.logger.error(f"Error fetching courses: {e}")
        courses = []
    
    # ==================== Fetch Student Groups ====================
    groups = []
    try:
        # Check if the groups table exists
        cursor.execute("SHOW TABLES LIKE 'groups'")
        groups_table_exists = cursor.fetchone()
        
        if groups_table_exists:
            # Check if columns exist in groups table
            def column_exists(table, column):
                cursor.execute(f"""
                    SELECT COUNT(*) as count 
                    FROM information_schema.columns 
                    WHERE table_schema = DATABASE() 
                    AND table_name = '{table}' 
                    AND column_name = '{column}'
                """)
                return cursor.fetchone()['count'] > 0
            
            priority_exists = column_exists('groups', 'priority')
            max_members_exists = column_exists('groups', 'max_members')
            
            # Build the SELECT query dynamically based on available columns
            select_columns = "g.id, g.name, g.project_title, g.visibility, g.deadline, g.task_description, g.course_id"
            
            if priority_exists:
                select_columns += ", g.priority"
            
            if max_members_exists:
                select_columns += ", g.max_members"
            
            # Check if students table exists and has records
            cursor.execute("SHOW TABLES LIKE 'students'")
            students_table_exists = cursor.fetchone()
            
            if students_table_exists:
                # Check if students table has records
                cursor.execute("SELECT COUNT(*) as count FROM students")
                students_count = cursor.fetchone()['count']
                
                if students_count > 0:
                    # Use students table if it has records
                    query = f"""
                        SELECT {select_columns},
                               JSON_ARRAYAGG(JSON_OBJECT('id', s.id, 'full_name', u.full_name, 'email', u.email)) AS members
                        FROM `groups` g
                        LEFT JOIN student_group_members sgm ON g.id = sgm.group_id
                        LEFT JOIN students s ON sgm.student_id = s.id
                        LEFT JOIN users u ON s.user_id = u.id
                        WHERE g.instructor_id = %s
                        GROUP BY g.id
                        ORDER BY g.created_at DESC
                    """
                else:
                    # Use users table if students table is empty
                    query = f"""
                        SELECT {select_columns},
                               JSON_ARRAYAGG(JSON_OBJECT('id', u.id, 'full_name', u.full_name, 'email', u.email)) AS members
                        FROM `groups` g
                        LEFT JOIN student_group_members sgm ON g.id = sgm.group_id
                        LEFT JOIN users u ON sgm.student_id = u.id
                        WHERE g.instructor_id = %s
                        GROUP BY g.id
                        ORDER BY g.created_at DESC
                    """
            else:
                # Use users table if students table doesn't exist
                query = f"""
                    SELECT {select_columns},
                           JSON_ARRAYAGG(JSON_OBJECT('id', u.id, 'full_name', u.full_name, 'email', u.email)) AS members
                    FROM `groups` g
                    LEFT JOIN student_group_members sgm ON g.id = sgm.group_id
                    LEFT JOIN users u ON sgm.student_id = u.id
                    WHERE g.instructor_id = %s
                    GROUP BY g.id
                    ORDER BY g.created_at DESC
                """
            
            cursor.execute(query, (instructor_id,))
            raw_groups = cursor.fetchall()
            
            import json
            for group in raw_groups:
                try:
                    # Parse the JSON members field
                    members_json = group['members']
                    if members_json:
                        group['members'] = json.loads(members_json)
                    else:
                        group['members'] = []
                        
                    # Ensure task_description is available
                    if 'task_description' not in group or not group['task_description']:
                        group['task_description'] = "No description provided"
                    
                    # Ensure priority is available
                    if priority_exists and 'priority' in group and group['priority']:
                        group['priority'] = group['priority']
                    else:
                        group['priority'] = "medium"
                    
                    # Ensure max_members is available
                    if max_members_exists and 'max_members' in group and group['max_members']:
                        group['max_members'] = group['max_members']
                    else:
                        group['max_members'] = 5
                    
                    groups.append(group)
                except json.JSONDecodeError:
                    current_app.logger.error(f"Failed to parse members JSON for group {group['id']}")
                    group['members'] = []
                    groups.append(group)
        else:
            # If groups table doesn't exist, try to get data from group_projects table
            cursor.execute("SHOW TABLES LIKE 'group_projects'")
            group_projects_exists = cursor.fetchone()
            
            if group_projects_exists:
                cursor.execute("""
                    SELECT g.id, g.name, g.project_title,
                           (SELECT COUNT(*) FROM group_members gm WHERE gm.group_id = g.id) AS member_count
                    FROM group_projects g
                    WHERE g.instructor_id = %s
                """, (instructor_id,))
                raw_groups = cursor.fetchall()
                
                for group in raw_groups:
                    # Convert to match expected format
                    group['members'] = [{'id': i, 'full_name': f'Student {i}'} for i in range(1, group['member_count'] + 1)]
                    groups.append(group)
    except Exception as e:
        current_app.logger.error(f"Error fetching groups: {e}")
        flash("Error loading student groups. Please try again.", "error")
    
    # ==================== Fetch Other Dashboard Data ====================
    # Quizzes
    try:
        cursor.execute("""
            SELECT q.id, u.full_name AS student_name, qz.title AS quiz_title, q.score
            FROM quiz_submissions q
            JOIN users u ON q.student_id = u.id
            JOIN quizzes qz ON q.quiz_id = qz.id
            WHERE qz.instructor_id = %s
        """, (instructor_id,))
        submitted_quizzes = cursor.fetchall()
    except Exception as e:
        current_app.logger.error(f"Error fetching quizzes: {e}")
        submitted_quizzes = []
    
    # Assignments
    try:
        cursor.execute("""
            SELECT s.id, u.full_name AS student_name, a.assignment_title AS title, s.score, s.submission_date
            FROM submissions s
            JOIN users u ON s.student_id = u.id
            JOIN assignments a ON s.assignment_id = a.id
            WHERE a.instructor_id = %s
        """, (instructor_id,))
        submitted_assignments = cursor.fetchall()
    except Exception as e:
        current_app.logger.error(f"Error fetching assignments: {e}")
        submitted_assignments = []
    
    # Forum Feedback
    try:
        cursor.execute("""
            SELECT ff.id, ff.feedback, ff.rating, u.full_name, ff.forum_id
            FROM forum_feedback ff
            JOIN users u ON ff.student_id = u.id
            JOIN forums f ON ff.forum_id = f.id
            WHERE f.instructor_id = %s
        """, (instructor_id,))
        forum_feedback = cursor.fetchall()
    except Exception as e:
        current_app.logger.error(f"Error fetching forum feedback: {e}")
        forum_feedback = []
    
    # ==================== Build Chart Data for Feedback ====================
    feedback_labels = [f['full_name'] for f in forum_feedback] if forum_feedback else []
    feedback_scores = [f['rating'] for f in forum_feedback if f['rating'] is not None] if forum_feedback else []
    
    # Notifications
    try:
        cursor.execute("""
            SELECT message, is_read, created_at FROM notifications
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (instructor_id,))
        notifications = cursor.fetchall()
    except Exception as e:
        current_app.logger.error(f"Error fetching notifications: {e}")
        notifications = []
    
    # Students
    # Get total students enrolled in instructor's courses
    total_students = 0
    try:
        # Check if course_enrollments table exists
        cursor.execute("SHOW TABLES LIKE 'course_enrollments'")
        enrollments_table_exists = cursor.fetchone()
        
        # Check if students table exists
        cursor.execute("SHOW TABLES LIKE 'students'")
        students_table_exists = cursor.fetchone()
        
        if students_table_exists:
            cursor.execute("SELECT COUNT(*) as count FROM students")
            students_count = cursor.fetchone()['count']
            
            if students_count > 0:
                # Use students table if it has records
                cursor.execute("""
                    SELECT COUNT(DISTINCT s.id) as count
                    FROM students s
                    JOIN courses c ON s.course_id = c.id
                    WHERE c.instructor_id = %s
                """, (instructor_id,))
                total_students = cursor.fetchone()['count']
            elif enrollments_table_exists:
                # Use course_enrollments table if students table is empty
                cursor.execute("""
                    SELECT COUNT(DISTINCT u.id) as count
                    FROM users u
                    JOIN course_enrollments ce ON u.id = ce.student_id
                    JOIN courses c ON ce.course_id = c.id
                    WHERE u.role = 'student' AND c.instructor_id = %s
                """, (instructor_id,))
                total_students = cursor.fetchone()['count']
            else:
                # If neither students table has records nor course_enrollments exists, count all student users
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM users
                    WHERE role = 'student'
                """)
                total_students = cursor.fetchone()['count']
        elif enrollments_table_exists:
            # Use course_enrollments table if students table doesn't exist
            cursor.execute("""
                SELECT COUNT(DISTINCT u.id) as count
                FROM users u
                JOIN course_enrollments ce ON u.id = ce.student_id
                JOIN courses c ON ce.course_id = c.id
                WHERE u.role = 'student' AND c.instructor_id = %s
            """, (instructor_id,))
            total_students = cursor.fetchone()['count']
        else:
            # If neither table exists, count all student users
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM users
                WHERE role = 'student'
            """)
            total_students = cursor.fetchone()['count']
    except Exception as e:
        current_app.logger.error(f"Error calculating total students: {e}")
        total_students = 0
    
    # Get all students for the all_students variable
    try:
        cursor.execute("""
            SELECT id, full_name AS name, email, is_active
            FROM users
            WHERE role = 'student'
        """)
        all_students = cursor.fetchall()
    except Exception as e:
        current_app.logger.error(f"Error fetching all students: {e}")
        all_students = []
    
    # Stats
    ratings = [f['rating'] for f in forum_feedback if f['rating'] is not None]
    stats = {
        'total_students': total_students,
        'active_courses': len(courses),
        'peer_reviews': len(forum_feedback),
        'average_rating': round(sum(ratings) / max(1, len(ratings)), 2),
        'group_performance_score': 0  # Placeholder for later enhancement
    }
    
    cursor.close()
    conn.close()
    
    return render_template(
        'instructor_dashboard.html',
        instructor=instructor,
        instructor_name=instructor_name,
        courses=courses,
        forums=forums,
        submitted_quizzes=submitted_quizzes,
        submitted_assignments=submitted_assignments,
        forum_feedback=forum_feedback,
        notifications=notifications,
        groups=groups,
        all_students=all_students,
        stats=stats,
        feedback_labels=feedback_labels,
        feedback_scores=feedback_scores
    )


@main.route('/create_group', methods=['GET', 'POST'])
def create_group():
    from datetime import datetime
    import json
    import traceback
    user_id = session.get('user_id')
    role = session.get('role')
    
    # Authentication check
    if not user_id or role != 'instructor':
        flash("Unauthorized access.", "error")
        return redirect(url_for('auth.login'))
    
    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Handle Group Creation (POST)
    if request.method == 'POST' and request.form.get("action") == "create":
        group_name = request.form.get('group_name', '').strip()
        visibility = request.form.get('visibility', 'private')
        project_title = request.form.get('project_title', '').strip()
        task_description = request.form.get('task_description', '').strip()
        deadline = request.form.get('deadline', '').strip()
        course_id = request.form.get('course_id', '').strip()
        priority = request.form.get('priority', 'medium')  # Added priority field
        max_members = request.form.get('max_members', '5')  # Added max_members field
        student_ids = request.form.getlist('students[]')
        
        # Validation
        if not all([group_name, project_title, task_description, deadline, course_id]):
            flash("All fields are required.", "error")
            return redirect(url_for('main.create_group'))
            
        if not student_ids or len(student_ids) < 2:  # Updated to require at least 2 students
            flash("At least two students must be selected.", "error")
            return redirect(url_for('main.create_group'))
        
        # Date validation
        try:
            deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
            if deadline_date < datetime.now().date():
                flash("Deadline cannot be in the past.", "error")
                return redirect(url_for('main.create_group'))
        except ValueError:
            flash("Invalid deadline format. Please use YYYY-MM-DD.", "error")
            return redirect(url_for('main.create_group'))
        
        # Validate student IDs
        try:
            student_ids = [int(sid) for sid in student_ids]
        except ValueError:
            flash("Invalid student ID format.", "error")
            return redirect(url_for('main.create_group'))
        
        # Validate course ID
        try:
            course_id = int(course_id)
        except ValueError:
            flash("Invalid course selection.", "error")
            return redirect(url_for('main.create_group'))
        
        # Validate max_members
        try:
            max_members = int(max_members)
            if max_members < 2 or max_members > 20:
                flash("Maximum members must be between 2 and 20.", "error")
                return redirect(url_for('main.create_group'))
        except ValueError:
            flash("Invalid maximum members value.", "error")
            return redirect(url_for('main.create_group'))
        
        # Verify course exists and belongs to instructor
        try:
            cursor.execute("""
                SELECT id FROM courses 
                WHERE id = %s AND instructor_id = %s
            """, (course_id, user_id))
            if not cursor.fetchone():
                flash("Invalid course selection or you don't have permission for this course.", "error")
                return redirect(url_for('main.create_group'))
        except Exception as e:
            current_app.logger.error(f"Error validating course: {e}")
            flash("Error validating course selection. Please try again.", "error")
            return redirect(url_for('main.create_group'))
        
        # Verify students exist in database
        try:
            # Check if students table exists and has records
            cursor.execute("SHOW TABLES LIKE 'students'")
            students_table_exists = cursor.fetchone()
            
            if students_table_exists:
                # Check if students table has records
                cursor.execute("SELECT COUNT(*) as count FROM students")
                students_count = cursor.fetchone()['count']
                
                if students_count > 0:
                    # Use students table if it has records
                    placeholders = ','.join(['%s'] * len(student_ids))
                    cursor.execute(f"""
                        SELECT s.id, u.full_name, u.email 
                        FROM students s
                        JOIN users u ON s.user_id = u.id
                        WHERE s.id IN ({placeholders})
                    """, student_ids)
                else:
                    # Use users table if students table is empty
                    placeholders = ','.join(['%s'] * len(student_ids))
                    cursor.execute(f"""
                        SELECT id, full_name, email 
                        FROM users 
                        WHERE role = 'student' AND id IN ({placeholders})
                    """, student_ids)
            else:
                # Use users table if students table doesn't exist
                placeholders = ','.join(['%s'] * len(student_ids))
                cursor.execute(f"""
                    SELECT id, full_name, email 
                    FROM users 
                    WHERE role = 'student' AND id IN ({placeholders})
                """, student_ids)
                
            valid_students = cursor.fetchall()
            valid_student_ids = [s['id'] for s in valid_students]
            invalid_students = set(student_ids) - set(valid_student_ids)
            
            if invalid_students:
                flash(f"Invalid student IDs selected: {', '.join(map(str, invalid_students))}", "error")
                return redirect(url_for('main.create_group'))
        except Exception as e:
            current_app.logger.error(f"Error validating students: {e}")
            flash("Error validating student selection. Please try again.", "error")
            return redirect(url_for('main.create_group'))
        
        # Check for duplicate group name
        try:
            cursor.execute("""
                SELECT id FROM `groups` 
                WHERE name = %s AND instructor_id = %s
            """, (group_name, user_id))
            if cursor.fetchone():
                flash("A group with this name already exists. Please choose a different name.", "error")
                return redirect(url_for('main.create_group'))
        except Exception as e:
            current_app.logger.error(f"Error checking for duplicate group: {e}")
            flash("Error checking for duplicate group name. Please try again.", "error")
            return redirect(url_for('main.create_group'))
        
        # Create group
        try:
            cursor.execute("""
                INSERT INTO `groups` 
                (name, visibility, project_title, task_description, deadline, instructor_id, course_id, priority, max_members, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (group_name, visibility, project_title, task_description, deadline_date, user_id, course_id, priority, max_members))
            
            group_id = cursor.lastrowid
            
            # Add students to group
            for student_id in student_ids:
                cursor.execute("""
                    INSERT INTO student_group_members (group_id, student_id)
                    VALUES (%s, %s)
                """, (group_id, student_id))
            
            conn.commit()
            flash("✅ Group created and task assigned successfully!", "success")
            return redirect(url_for('main.create_group'))
            
        except Exception as e:
            conn.rollback()
            current_app.logger.error(f"❌ Group creation failed: {e}")
            current_app.logger.error(traceback.format_exc())
            
            # Provide more specific error messages based on common issues
            error_msg = str(e).lower()
            if "duplicate entry" in error_msg:
                flash("A group with this name already exists. Please choose a different name.", "error")
            elif "foreign key constraint" in error_msg:
                flash("Invalid student or course selected. Please check your selection.", "error")
            elif "column" in error_msg and "cannot be null" in error_msg:
                flash("Required information is missing. Please fill all fields.", "error")
            else:
                flash(f"Failed to create group: {str(e)}", "error")
            
            return redirect(url_for('main.create_group'))
    
    # Fetch all courses for the instructor
    try:
        cursor.execute("""
            SELECT id, title FROM courses 
            WHERE instructor_id = %s
            ORDER BY title ASC
        """, (user_id,))
        courses = cursor.fetchall()
        current_app.logger.info(f"Courses for instructor {user_id}: {courses}")
        
        if not courses:
            flash("You don't have any courses yet. Please create a course first.", "warning")
    except Exception as e:
        current_app.logger.error(f"Error fetching courses: {e}")
        flash("Error loading course data. Please try again.", "error")
        courses = []
    
    # Fetch all students for the form
    all_students = []
    try:
        # Check if students table exists
        cursor.execute("SHOW TABLES LIKE 'students'")
        students_table_exists = cursor.fetchone()
        
        if students_table_exists:
            # Check if students table has records
            cursor.execute("SELECT COUNT(*) as count FROM students")
            students_count = cursor.fetchone()['count']
            current_app.logger.info(f"Total students in database: {students_count}")
            
            if students_count > 0:
                # Use students table if it has records
                cursor.execute("""
                    SELECT s.id, u.full_name, u.email, s.course_id
                    FROM students s
                    JOIN users u ON s.user_id = u.id
                    ORDER BY u.full_name ASC
                """)
                all_students = cursor.fetchall()
                current_app.logger.info(f"Fetched {len(all_students)} students from students table")
            else:
                # Use users table if students table is empty
                current_app.logger.warning("Students table is empty, trying to get students from users table")
                cursor.execute("""
                    SELECT id, full_name, email, NULL as course_id
                    FROM users 
                    WHERE role = 'student'
                    ORDER BY full_name ASC
                """)
                all_students = cursor.fetchall()
                current_app.logger.info(f"Fetched {len(all_students)} students from users table")
        else:
            # Use users table if students table doesn't exist
            current_app.logger.warning("Students table does not exist, trying to get students from users table")
            cursor.execute("""
                SELECT id, full_name, email, NULL as course_id
                FROM users 
                WHERE role = 'student'
                ORDER BY full_name ASC
            """)
            all_students = cursor.fetchall()
            current_app.logger.info(f"Fetched {len(all_students)} students from users table")
            
        if not all_students:
            flash("No students found in the system. Please add students first.", "warning")
    except Exception as e:
        current_app.logger.error(f"Error fetching students: {e}")
        current_app.logger.error(traceback.format_exc())
        flash("Error loading student data. Please try again.", "error")
    
    # Fetch existing groups with member details
    created_groups = []
    try:
        # Check if students table exists and has records
        cursor.execute("SHOW TABLES LIKE 'students'")
        students_table_exists = cursor.fetchone()
        
        if students_table_exists:
            # Check if students table has records
            cursor.execute("SELECT COUNT(*) as count FROM students")
            students_count = cursor.fetchone()['count']
            
            if students_count > 0:
                # Use students table if it has records
                cursor.execute("""
                    SELECT g.id, g.name, g.project_title, g.visibility, g.deadline, g.task_description, g.course_id, g.priority, g.max_members,
                           JSON_ARRAYAGG(JSON_OBJECT('id', s.id, 'full_name', u.full_name, 'email', u.email)) AS members
                    FROM `groups` g
                    LEFT JOIN student_group_members sgm ON g.id = sgm.group_id
                    LEFT JOIN students s ON sgm.student_id = s.id
                    LEFT JOIN users u ON s.user_id = u.id
                    WHERE g.instructor_id = %s
                    GROUP BY g.id
                    ORDER BY g.created_at DESC
                """, (user_id,))
            else:
                # Use users table if students table is empty
                cursor.execute("""
                    SELECT g.id, g.name, g.project_title, g.visibility, g.deadline, g.task_description, g.course_id, g.priority, g.max_members,
                           JSON_ARRAYAGG(JSON_OBJECT('id', u.id, 'full_name', u.full_name, 'email', u.email)) AS members
                    FROM `groups` g
                    LEFT JOIN student_group_members sgm ON g.id = sgm.group_id
                    LEFT JOIN users u ON sgm.student_id = u.id
                    WHERE g.instructor_id = %s
                    GROUP BY g.id
                    ORDER BY g.created_at DESC
                """, (user_id,))
        else:
            # Use users table if students table doesn't exist
            cursor.execute("""
                SELECT g.id, g.name, g.project_title, g.visibility, g.deadline, g.task_description, g.course_id, g.priority, g.max_members,
                       JSON_ARRAYAGG(JSON_OBJECT('id', u.id, 'full_name', u.full_name, 'email', u.email)) AS members
                FROM `groups` g
                LEFT JOIN student_group_members sgm ON g.id = sgm.group_id
                LEFT JOIN users u ON sgm.student_id = u.id
                WHERE g.instructor_id = %s
                GROUP BY g.id
                ORDER BY g.created_at DESC
            """, (user_id,))
        
        raw_groups = cursor.fetchall()
        
        for group in raw_groups:
            try:
                # Parse the JSON members field
                members_json = group['members']
                if members_json:
                    group['members'] = json.loads(members_json)
                else:
                    group['members'] = []
                    
                # Ensure task_description is available
                if 'task_description' not in group or not group['task_description']:
                    group['task_description'] = "No description provided"
                
                # Ensure priority is available
                if 'priority' not in group or not group['priority']:
                    group['priority'] = "medium"
                
                # Ensure max_members is available
                if 'max_members' not in group or not group['max_members']:
                    group['max_members'] = 5
                
                # Get course title
                if 'course_id' in group and group['course_id']:
                    cursor.execute("""
                        SELECT title FROM courses WHERE id = %s
                    """, (group['course_id'],))
                    course = cursor.fetchone()
                    group['course_title'] = course['title'] if course else "Unknown Course"
                else:
                    group['course_title'] = "No Course"
                    
                created_groups.append(group)
            except json.JSONDecodeError:
                current_app.logger.error(f"Failed to parse members JSON for group {group['id']}")
                group['members'] = []
                created_groups.append(group)
    except Exception as e:
        current_app.logger.error(f"Error fetching groups: {e}")
        current_app.logger.error(traceback.format_exc())
        flash("Error loading existing groups. Please try again.", "error")
    
    cursor.close()
    conn.close()
    
    return render_template(
        'create_group.html',
        all_students=all_students,
        created_groups=created_groups,
        courses=courses
    )

@main.route('/delete_group/<int:group_id>', methods=['POST'])
def delete_group(group_id):
    user_id = session.get('user_id')
    role = session.get('role')
    
    # Authentication check
    if not user_id or role != 'instructor':
        flash("Unauthorized access.", "error")
        return redirect(url_for('auth.login'))
    
    conn = current_app.get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verify ownership before deletion
        cursor.execute("SELECT instructor_id FROM `groups` WHERE id = %s", (group_id,))
        group = cursor.fetchone()
        
        if not group:
            flash("Group not found.", "error")
            return redirect(url_for('main.create_group'))
            
        if group['instructor_id'] != user_id:
            flash("You don't have permission to delete this group.", "error")
            return redirect(url_for('main.create_group'))
        
        # Delete group members first (foreign key constraint)
        cursor.execute("DELETE FROM student_group_members WHERE group_id = %s", (group_id,))
        
        # Delete the group
        cursor.execute("DELETE FROM `groups` WHERE id = %s", (group_id,))
        
        conn.commit()
        flash("🗑️ Group deleted successfully.", "success")
        
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"❌ Failed to delete group {group_id}: {e}")
        flash("Failed to delete group. Please try again.", "error")
        
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('main.create_group'))

@main.route('/edit_group/<int:group_id>', methods=['POST'])
def edit_group(group_id):
    from datetime import datetime
    user_id = session.get('user_id')
    role = session.get('role')
    
    # Authentication check
    if not user_id or role != 'instructor':
        flash("Unauthorized access.", "error")
        return redirect(url_for('auth.login'))
    
    conn = current_app.get_db_connection()
    cursor = conn.cursor()
    
    # Collect form data
    group_name = request.form.get('group_name', '').strip()
    visibility = request.form.get('visibility', 'private')
    project_title = request.form.get('project_title', '').strip()
    task_description = request.form.get('task_description', '').strip()
    deadline = request.form.get('deadline', '').strip()
    priority = request.form.get('priority', 'medium')  # Added priority field
    
    # Validation
    if not all([group_name, project_title, task_description, deadline]):
        flash("All fields are required for editing.", "error")
        return redirect(url_for('main.create_group'))
    
    # Date validation
    try:
        deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
        if deadline_date < datetime.now().date():
            flash("Deadline cannot be in the past.", "error")
            return redirect(url_for('main.create_group'))
    except ValueError:
        flash("Invalid deadline format. Please use YYYY-MM-DD.", "error")
        return redirect(url_for('main.create_group'))
    
    try:
        # Verify ownership before editing
        cursor.execute("SELECT instructor_id FROM `groups` WHERE id = %s", (group_id,))
        group = cursor.fetchone()
        
        if not group:
            flash("Group not found.", "error")
            return redirect(url_for('main.create_group'))
            
        if group['instructor_id'] != user_id:
            flash("You don't have permission to edit this group.", "error")
            return redirect(url_for('main.create_group'))
        
        # Update group
        cursor.execute("""
            UPDATE `groups`
            SET name = %s, visibility = %s, project_title = %s,
                task_description = %s, deadline = %s, priority = %s
            WHERE id = %s AND instructor_id = %s
        """, (group_name, visibility, project_title, task_description, deadline_date, priority, group_id, user_id))
        
        conn.commit()
        flash("✏️ Group updated successfully!", "success")
        
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"❌ Failed to edit group {group_id}: {e}")
        flash("Failed to update group. Please try again.", "error")
        
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('main.create_group'))

@main.route('/duplicate_group/<int:group_id>', methods=['POST'])
def duplicate_group(group_id):
    from datetime import datetime
    import json
    user_id = session.get('user_id')
    role = session.get('role')
    
    # Authentication check
    if not user_id or role != 'instructor':
        flash("Unauthorized access.", "error")
        return redirect(url_for('main.create_group'))
    
    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Verify ownership before duplication
        cursor.execute("""
            SELECT g.name, g.visibility, g.project_title, g.task_description, g.deadline, 
                   g.course_id, g.priority, g.max_members
            FROM `groups` g
            WHERE g.id = %s AND g.instructor_id = %s
        """, (group_id, user_id))
        group = cursor.fetchone()
        
        if not group:
            flash("Group not found.", "error")
            return redirect(url_for('main.create_group'))
        
        # Create a new group with the same details but a modified name
        original_name = group['name']
        new_name = f"{original_name} (Copy)"
        
        # Check if the name already exists
        cursor.execute("""
            SELECT id FROM `groups` 
            WHERE name = %s AND instructor_id = %s
        """, (new_name, user_id))
        
        # If name exists, add a number
        counter = 1
        while cursor.fetchone():
            counter += 1
            new_name = f"{original_name} (Copy {counter})"
            cursor.execute("""
                SELECT id FROM `groups` 
                WHERE name = %s AND instructor_id = %s
            """, (new_name, user_id))
        
        # Create the new group
        cursor.execute("""
            INSERT INTO `groups` 
            (name, visibility, project_title, task_description, deadline, instructor_id, course_id, priority, max_members, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (new_name, group['visibility'], group['project_title'], group['task_description'], 
              group['deadline'], user_id, group['course_id'], group['priority'], group['max_members']))
        
        new_group_id = cursor.lastrowid
        
        # Copy the members from the original group
        cursor.execute("""
            INSERT INTO student_group_members (group_id, student_id)
            SELECT %s, student_id
            FROM student_group_members
            WHERE group_id = %s
        """, (new_group_id, group_id))
        
        conn.commit()
        flash(f"📋 Group '{original_name}' duplicated successfully as '{new_name}'!", "success")
        
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"❌ Failed to duplicate group {group_id}: {e}")
        flash("Failed to duplicate group. Please try again.", "error")
        
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('main.create_group'))

@main.route('/notify_group/<int:group_id>', methods=['POST'])
def notify_group(group_id):
    user_id = session.get('user_id')
    role = session.get('role')
    
    # Authentication check
    if not user_id or role != 'instructor':
        flash("Unauthorized access.", "error")
        return redirect(url_for('auth.login'))
    
    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Verify ownership before notification
        cursor.execute("""
            SELECT g.name, g.project_title, g.deadline
            FROM `groups` g
            WHERE g.id = %s AND g.instructor_id = %s
        """, (group_id, user_id))
        group = cursor.fetchone()
        
        if not group:
            flash("Group not found.", "error")
            return redirect(url_for('main.create_group'))
        
        # Get group members' emails
        cursor.execute("""
            SELECT u.email, u.full_name
            FROM student_group_members sgm
            JOIN users u ON sgm.student_id = u.id
            WHERE sgm.group_id = %s
        """, (group_id,))
        members = cursor.fetchall()
        
        if not members:
            flash("No members found in this group.", "warning")
            return redirect(url_for('main.create_group'))
        
        # In a real application, you would send an email here
        # For now, we'll just log the action and show a success message
        member_emails = [m['email'] for m in members]
        current_app.logger.info(f"Notification would be sent to: {member_emails}")
        
        flash(f"📧 Notification sent to {len(members)} group members for '{group['name']}'.", "success")
        
    except Exception as e:
        current_app.logger.error(f"❌ Failed to notify group {group_id}: {e}")
        flash("Failed to send notification. Please try again.", "error")
        
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('main.create_group'))

                    

@main.route('/create_quiz', methods=['GET', 'POST'])
def create_quizzes():
    """
    Handles GET, POST, and DELETE for quiz creation/management.
    - GET: Displays instructor-specific courses and quizzes.
    - POST: Creates new quiz (auto-enrolls all students).
    - DELETE: Deletes quiz and related questions/options.
    """
    instructor_id = session.get('user_id')
    if not instructor_id:
        flash('Please log in to create a quiz.', 'error')
        return redirect(url_for('auth.login'))

    conn = None
    cursor = None
    quizzes, courses = [], []

    try:
        conn = current_app.get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # ---------------- DELETE ----------------
        delete_id = request.args.get("delete")
        if delete_id:
            try:
                cursor.execute(
                    "SELECT id FROM quizzes WHERE id = %s AND created_by = %s",
                    (delete_id, instructor_id)
                )
                quiz = cursor.fetchone()
                if quiz:
                    cursor.execute("""
                        DELETE qo FROM quiz_options qo
                        JOIN quiz_questions qq ON qo.question_id = qq.id
                        WHERE qq.quiz_id = %s
                    """, (delete_id,))
                    cursor.execute("DELETE FROM quiz_questions WHERE quiz_id = %s", (delete_id,))
                    cursor.execute("DELETE FROM quizzes WHERE id = %s", (delete_id,))
                    conn.commit()
                    flash('Quiz deleted successfully.', 'success')
                else:
                    flash('You are not authorized to delete this quiz.', 'error')
            except Exception as e:
                conn.rollback()
                current_app.logger.error(f"Error deleting quiz: {e}")
                flash('Failed to delete quiz.', 'danger')
            return redirect(url_for('main.create_quizzes'))

        # ---------------- POST (Create quiz) ----------------
        if request.method == 'POST':
            quiz_data_json = request.form.get('quiz_data')
            if not quiz_data_json:
                flash('Invalid quiz data received.', 'error')
                return redirect(url_for('main.create_quizzes'))

            try:
                quiz_data = json.loads(quiz_data_json)
            except json.JSONDecodeError:
                flash('Failed to decode quiz data. Please try again.', 'error')
                return redirect(url_for('main.create_quizzes'))

            quiz_title = quiz_data.get('quiz_title')
            course_id = quiz_data.get('course_id')
            questions_data = quiz_data.get('questions', [])

            if not quiz_title or not course_id or not questions_data:
                flash('Quiz title, course, and at least one question are required.', 'error')
                return redirect(url_for('main.create_quizzes'))

            # Insert quiz
            cursor.execute("""
                INSERT INTO quizzes (title, course_id, created_by, created_at)
                VALUES (%s, %s, %s, NOW())
            """, (quiz_title, course_id, instructor_id))
            quiz_id = cursor.lastrowid

            # Insert questions + options
            for question in questions_data:
                question_text = question.get('question_text')
                question_type = question.get('question_type')

                cursor.execute("""
                    INSERT INTO quiz_questions (quiz_id, question_text, question_type)
                    VALUES (%s, %s, %s)
                """, (quiz_id, question_text, question_type))
                question_id = cursor.lastrowid

                if question_type == 'mcq':
                    options = question.get('options', [])
                    correct_index = question.get('correct_answer_index')

                    for i, option_text in enumerate(options):
                        is_correct = (i == correct_index)
                        cursor.execute("""
                            INSERT INTO quiz_options (question_id, option_text, is_correct)
                            VALUES (%s, %s, %s)
                        """, (question_id, option_text, is_correct))

                elif question_type == 'open_ended':
                    correct_answer = question.get('correct_answer')
                    cursor.execute("""
                        UPDATE quiz_questions
                        SET correct_answer_text = %s
                        WHERE id = %s
                    """, (correct_answer, question_id))

            # ✅ Auto-enroll all students to this quiz
            cursor.execute("SELECT id FROM users WHERE role = 'student'")
            students = cursor.fetchall()
            for student in students:
                cursor.execute("""
                    INSERT IGNORE INTO quiz_enrollments (quiz_id, student_id, enrolled_at)
                    VALUES (%s, %s, NOW())
                """, (quiz_id, student['id']))

            conn.commit()
            flash('Quiz created successfully and all students auto-enrolled!', 'success')
            return redirect(url_for('main.create_quizzes'))

        # ---------------- GET (Load quizzes + courses) ----------------
        cursor.execute("""
            SELECT q.id, q.title, c.title AS course_name
            FROM quizzes q
            JOIN courses c ON q.course_id = c.id
            WHERE q.created_by = %s
            ORDER BY q.id DESC
        """, (instructor_id,))
        quizzes = cursor.fetchall()

        cursor.execute("""
            SELECT id, title
            FROM courses
            WHERE instructor_id = %s
        """, (instructor_id,))
        courses = cursor.fetchall()

    except Exception as e:
        if conn:
            conn.rollback()
        current_app.logger.error(f"Error in create_quizzes: {e}")
        flash('An error occurred. Please try again.', 'danger')
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return render_template('create_quizzes.html', quizzes=quizzes, courses=courses)



@main.route('/delete_quiz/<int:quiz_id>', methods=['POST'])
def delete_quiz(quiz_id):
    """
    Deletes a quiz and its associated questions/options, but only if the
    current user is the one who created it.
    """
    conn = None
    cursor = None
    
    instructor_id = session.get('user_id')
    if not instructor_id:
        flash('You do not have permission to perform this action.', 'error')
        return redirect(url_for('main.create_quizzes'))

    try:
        conn = current_app.get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Verify the quiz exists and belongs to the current instructor
        cursor.execute("SELECT id FROM quizzes WHERE id = %s AND created_by = %s", (quiz_id, instructor_id))
        quiz_to_delete = cursor.fetchone()
        
        if not quiz_to_delete:
            flash('Quiz not found or you do not have permission to delete it.', 'warning')
            return redirect(url_for('main.create_quizzes'))

        # Delete all options associated with this quiz's questions
        cursor.execute("""
            DELETE FROM quiz_options 
            WHERE question_id IN (
                SELECT id FROM quiz_questions WHERE quiz_id = %s
            )
        """, (quiz_id,))
        
        # Delete the questions themselves
        cursor.execute("DELETE FROM quiz_questions WHERE quiz_id = %s", (quiz_id,))

        # Finally, delete the quiz
        cursor.execute("DELETE FROM quizzes WHERE id = %s", (quiz_id,))

        conn.commit()
        flash('Quiz deleted successfully.', 'success')

    except Exception as e:
        if conn:
            conn.rollback()
        current_app.logger.error(f"Error deleting quiz {quiz_id}: {e}")
        flash('Failed to delete quiz. Please try again.', 'danger')

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return redirect(url_for('main.create_quizzes'))



# Show all available quizzes for student
@main.route('/student_quizzes')
def student_quizzes():
    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM quizzes")
        quizzes = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return render_template('student_quizzes.html', quizzes=quizzes)


# Attempt a specific quiz
@main.route('/quiz/<int:quiz_id>', methods=['GET'])
def attempt_quiz(quiz_id):
    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM quizzes WHERE id = %s", (quiz_id,))
        quiz = cursor.fetchone()

        cursor.execute("SELECT * FROM questions WHERE quiz_id = %s", (quiz_id,))
        questions = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return render_template('attempt_quiz.html', quiz=quiz, questions=questions)



# Directory where uploaded files will be stored
UPLOAD_FOLDER = 'static/uploads/assignments'
all_assignments = []
next_assignment_id = 1

# A helper function to find an assignment by its ID
def find_assignment_by_id(assignment_id):
    # This function now searches the 'all_assignments' list
    for assignment in all_assignments:
        if assignment['id'] == assignment_id:
            return assignment
    return None


# Route to add assignments
UPLOAD_FOLDER = 'static/uploads/assignments'
@main.route('/add_assignments', methods=['GET', 'POST'])
def add_assignments():
    """
    Handles adding new assignments and displaying existing ones.
    Assignments are saved permanently in the database.
    """
    instructor_id = session.get('user_id')
    if not instructor_id:
        flash("You must be logged in as an instructor to add assignments.", "danger")
        return redirect(url_for('main.login'))

    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        due_date_str = request.form.get('due_date', '').strip()

        if not title or not description or not due_date_str:
            flash(' All fields are required.', 'error')
            return redirect(url_for('main.add_assignments'))

        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
        except ValueError:
            flash(' Invalid date format. Please use YYYY-MM-DD.', 'error')
            return redirect(url_for('main.add_assignments'))

        file_url = None
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename.strip():
                filename = secure_filename(file.filename)
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                file_path = os.path.join(UPLOAD_FOLDER, filename)

                if os.path.exists(file_path):
                    flash(' A file with this name already exists. Please rename your file.', 'warning')
                    return redirect(url_for('main.add_assignments'))

                try:
                    file.save(file_path)
                    file_url = f'{UPLOAD_FOLDER}/{filename}'
                except Exception as e:
                    flash(f' Error uploading file: {e}', 'error')
                    return redirect(url_for('main.add_assignments'))

        try:
            cursor.execute("""
                INSERT INTO assignments (title, description, due_date, file_url, instructor_id, created_on)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (title, description, due_date, file_url, instructor_id, datetime.utcnow()))
            conn.commit()
            flash(' Assignment added successfully!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f' Error saving assignment: {e}', 'error')

        return redirect(url_for('main.add_assignments'))

    # GET request: fetch all assignments created by this instructor
    cursor.execute("""
        SELECT id, title, description, due_date, file_url, created_on
        FROM assignments
        WHERE instructor_id = %s
        ORDER BY due_date ASC
    """, (instructor_id,))
    assignments = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('add_assignments.html', assignments=assignments)


@main.route('/assignments/delete/<int:assignment_id>', methods=['POST'])
def delete_assignment(assignment_id):
    """
    Handles the deletion of a specific assignment.
    Deletes both DB record and any associated uploaded file.
    """
    instructor_id = session.get('user_id')
    if not instructor_id:
        flash("You must be logged in to perform this action.", "danger")
        return redirect(url_for('main.login'))

    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, file_url FROM assignments
        WHERE id = %s AND instructor_id = %s
    """, (assignment_id, instructor_id))
    assignment = cursor.fetchone()

    if not assignment:
        flash(' Assignment not found or unauthorized.', 'error')
        cursor.close()
        conn.close()
        return redirect(url_for('main.add_assignments'))

    # Delete file if it exists
    if assignment['file_url']:
        try:
            file_path = os.path.join(current_app.root_path, assignment['file_url'])
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            flash(f' Error deleting file: {e}', 'warning')

    # Delete DB record
    try:
        cursor.execute("DELETE FROM assignments WHERE id = %s", (assignment_id,))
        conn.commit()
        flash(' Assignment deleted successfully!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f' Error deleting assignment: {e}', 'error')
    cursor.close()
    conn.close()
    return redirect(url_for('main.add_assignments'))




@main.route('/create_forum', methods=['GET', 'POST'])
def create_forum():
    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)

    user_id = session.get('user_id')
    role = session.get('role')
    name = session.get('name')

    new_forum_id = None

    # Fetch instructor's courses for dropdown
    instructor_courses = []
    if role == 'instructor' and user_id:
        cursor.execute("""
            SELECT id, title AS course_name, created_at
            FROM courses
            WHERE instructor_id = %s AND (is_deleted IS NULL OR is_deleted = 0)
            ORDER BY created_at DESC
        """, (user_id,))
        instructor_courses = cursor.fetchall()

    # ==================== Handle AJAX-based POST ====================
    if request.method == 'POST' and request.is_json:
        if role != 'instructor':
            return jsonify({'success': False, 'message': 'Only instructors can create forums.'}), 403

        data = request.get_json()
        topic = data.get('topic', '').strip()
        description = data.get('description', '').strip()
        course_id = data.get('course_id')
        created_at = datetime.now()

        if not topic or not description or not course_id:
            return jsonify({'success': False, 'message': 'All fields are required.'}), 400

        try:
            # Insert forum
            cursor.execute("""
                INSERT INTO forums (instructor_id, course_id, title, description, created_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, course_id, topic, description, created_at))
            new_forum_id = cursor.lastrowid

            # ✅ Auto-enroll all students to forum
            cursor.execute("SELECT id FROM users WHERE role = 'student'")
            students = cursor.fetchall()
            for student in students:
                cursor.execute("""
                    INSERT IGNORE INTO forum_enrollments (forum_id, student_id, enrolled_at)
                    VALUES (%s, %s, NOW())
                """, (new_forum_id, student['id']))

            conn.commit()

            return jsonify({
                'success': True,
                'message': 'Forum topic created successfully and all students auto-enrolled!',
                'forum': {
                    'id': new_forum_id,
                    'topic': topic,
                    'description': description,
                    'author': name or 'Instructor',
                    'author_id': user_id,
                    'created_at': created_at.strftime('%Y-%m-%d %H:%M'),
                    'course_id': course_id,
                    'replies': []
                }
            })
        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'message': f"Error creating forum: {str(e)}"}), 500

    # ==================== Handle regular POST (non-AJAX) ====================
    if request.method == 'POST' and not request.is_json:
        if role == 'instructor':
            topic = request.form.get('topic', '').strip()
            description = request.form.get('description', '').strip()
            course_id = request.form.get('course_id')

            if topic and description and course_id:
                try:
                    cursor.execute("""
                        INSERT INTO forums (instructor_id, course_id, title, description, created_at)
                        VALUES (%s, %s, %s, %s, NOW())
                    """, (user_id, course_id, topic, description))
                    new_forum_id = cursor.lastrowid

                    # ✅ Auto-enroll all students to forum
                    cursor.execute("SELECT id FROM users WHERE role = 'student'")
                    students = cursor.fetchall()
                    for student in students:
                        cursor.execute("""
                            INSERT IGNORE INTO forum_enrollments (forum_id, student_id, enrolled_at)
                            VALUES (%s, %s, NOW())
                        """, (new_forum_id, student['id']))

                    conn.commit()
                    flash("Forum created successfully and all students auto-enrolled!", "success")
                except Exception as e:
                    conn.rollback()
                    flash(f"Error creating forum: {str(e)}", "error")
            else:
                flash("All fields are required.", "warning")

    # ==================== Load forums and replies ====================
    if role == 'instructor':
        cursor.execute("""
            SELECT f.id, f.title AS topic, f.description, f.created_at,
                   u.full_name AS author, f.instructor_id, c.title AS course_title
            FROM forums f
            JOIN users u ON f.instructor_id = u.id
            JOIN courses c ON f.course_id = c.id
            WHERE f.instructor_id = %s AND (f.is_deleted IS NULL OR f.is_deleted = 0)
            ORDER BY f.created_at DESC
        """, (user_id,))
    else:
        cursor.execute("""
            SELECT f.id, f.title AS topic, f.description, f.created_at,
                   u.full_name AS author, f.instructor_id, c.title AS course_title
            FROM forums f
            JOIN users u ON f.instructor_id = u.id
            JOIN courses c ON f.course_id = c.id
            WHERE f.is_deleted IS NULL OR f.is_deleted = 0
            ORDER BY f.created_at DESC
        """)

    all_forums = cursor.fetchall()
    forum_data = []

    for forum in all_forums:
        cursor.execute("""
            SELECT r.id, r.content, r.created_at, u.full_name AS responder,
                   r.user_id, r.rating
            FROM forum_replies r
            JOIN users u ON r.user_id = u.id
            WHERE r.forum_id = %s
            ORDER BY r.created_at ASC
        """, (forum['id'],))
        replies = cursor.fetchall()

        for reply in replies:
            reply['is_mine'] = (reply['user_id'] == user_id)

        forum['replies'] = replies
        forum['is_new'] = (forum['id'] == new_forum_id)
        forum_data.append(forum)

    cursor.close()
    conn.close()

    return render_template(
        'create_forum.html',
        forum_threads=forum_data,
        role=role,
        user_id=user_id,
        instructor_courses=instructor_courses
    )




@main.route('/delete_forum/<int:forum_id>', methods=['POST'])
def delete_forum(forum_id):
    """
    Permanently deletes a forum from the database.
    Only the instructor who created the forum can delete it.
    """
    user_id = session.get('user_id')
    role = session.get('role')

    if not user_id or role != 'instructor':
        flash("Unauthorized access.", "error")
        return redirect(url_for('auth.login'))

    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Verify ownership
        cursor.execute("""
            SELECT instructor_id FROM forums 
            WHERE id = %s
        """, (forum_id,))
        forum = cursor.fetchone()

        if forum and forum['instructor_id'] == user_id:
            cursor.execute("""
                DELETE FROM forums WHERE id = %s
            """, (forum_id,))
            conn.commit()
            message = "Forum permanently deleted."
            status = 200
        else:
            message = "Unauthorized or forum not found."
            status = 403

    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error deleting forum {forum_id}: {e}")
        message = "An error occurred while deleting the forum."
        status = 500

    finally:
        cursor.close()
        conn.close()

    # Support AJAX and standard form submission
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': status == 200, 'message': message}), status
    else:
        flash(message, "success" if status == 200 else "error")
        return redirect(url_for('main.create_forum'))




@main.route('/reply_forum/<int:forum_id>', methods=['POST'])
def reply_forum(forum_id):
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json()
    content = data.get('content')
    user_id = session.get('user_id')
    responder = session.get('name') or "Student"  # Or use session.get('username') if preferred
    created_at = datetime.now()
    if not content:
        return jsonify({'success': False, 'message': 'Reply content is required'}), 400
    conn = current_app.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO forum_replies (forum_id, user_id, responder, content, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (forum_id, user_id, responder, content, created_at))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()
    return jsonify({'success': True, 'message': 'Reply posted successfully!'})


@main.route('/instructor_forums')
def instructor_forums():
    if session.get('role') != 'instructor':
        flash("Access denied.", 'danger')
        return redirect(url_for('main.login'))

    instructor_id = session['user_id']
    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Default values
    instructor_name, instructor_email, instructor_avatar = "Instructor", "", None
    forums, instructor_replies, unrated_replies, rated_replies, top_students = [], [], [], [], []
    total_forums = total_replies = total_student_replies = total_unrated = total_rated = 0
    activity_labels, activity_values = [], []

    try:
        # --- Instructor profile ---
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM information_schema.columns 
            WHERE table_schema = DATABASE() 
              AND table_name = 'users' 
              AND column_name = 'avatar'
        """)
        avatar_exists = cursor.fetchone()['count'] > 0

        if avatar_exists:
            cursor.execute("SELECT full_name, email, avatar FROM users WHERE id = %s", (instructor_id,))
        else:
            cursor.execute("SELECT full_name, email FROM users WHERE id = %s", (instructor_id,))
        instructor = cursor.fetchone()
        if instructor:
            instructor_name = instructor['full_name']
            instructor_email = instructor['email']
            if avatar_exists:
                instructor_avatar = instructor.get('avatar')

        # --- Column checks helper ---
        def column_exists(table, column):
            cursor.execute(f"""
                SELECT COUNT(*) as count 
                FROM information_schema.columns 
                WHERE table_schema = DATABASE() 
                  AND table_name = '{table}' 
                  AND column_name = '{column}'
            """)
            return cursor.fetchone()['count'] > 0

        forums_is_deleted_exists = column_exists('forums', 'is_deleted')
        forum_replies_is_deleted_exists = column_exists('forum_replies', 'is_deleted')
        forum_replies_rating_exists = column_exists('forum_replies', 'rating')
        forum_replies_feedback_exists = column_exists('forum_replies', 'feedback')

        # --- Forums query ---
        forums_query = """
            SELECT f.id, f.title, f.description, f.created_at, f.course_id,
                   (SELECT COUNT(*) FROM forum_replies WHERE forum_id = f.id
        """
        if forum_replies_is_deleted_exists:
            forums_query += " AND (is_deleted IS NULL OR is_deleted = 0)"
        forums_query += """) AS total_replies,

                   (SELECT COUNT(*) FROM forum_replies 
                    WHERE forum_id = f.id AND user_id != %s"""
        if forum_replies_is_deleted_exists:
            forums_query += " AND (is_deleted IS NULL OR is_deleted = 0)"
        forums_query += """) AS student_replies,

                   (SELECT AVG(rating) FROM forum_replies 
                    WHERE forum_id = f.id AND rating IS NOT NULL"""
        if forum_replies_is_deleted_exists:
            forums_query += " AND (is_deleted IS NULL OR is_deleted = 0)"
        forums_query += """) AS avg_rating,

                   c.title AS course_title
            FROM forums f
            LEFT JOIN courses c ON f.course_id = c.id
            WHERE f.instructor_id = %s
        """
        if forums_is_deleted_exists:
            forums_query += " AND (f.is_deleted IS NULL OR f.is_deleted = 0)"
        forums_query += " ORDER BY f.created_at DESC"

        # Correct params: one for user_id != %s, one for f.instructor_id = %s
        cursor.execute(forums_query, (instructor_id, instructor_id))
        forums = cursor.fetchall()

        # --- Rest of your queries unchanged (instructor replies, unrated, rated, stats, activity, etc.) ---
        # [Keep your existing code for instructor_replies, unrated_replies, rated_replies, top_students, and activity here]
        # They don’t need changes because they already match params correctly.

        # Stats
        total_forums = len(forums)
        total_replies = sum(f['total_replies'] for f in forums)
        total_student_replies = sum(f['student_replies'] for f in forums)
        total_unrated = len(unrated_replies)
        total_rated = len(rated_replies)

    except Exception as e:
        current_app.logger.error(f"Error in instructor_forums route: {e}")
        flash("An error occurred. Please try again.", 'danger')
    finally:
        cursor.close()
        conn.close()

    return render_template(
        'instructor_forums.html',
        instructor_name=instructor_name,
        instructor_email=instructor_email,
        instructor_avatar=instructor_avatar,
        forums=forums,
        instructor_replies=instructor_replies,
        unrated_replies=unrated_replies,
        rated_replies=rated_replies,
        top_students=top_students,
        total_forums=total_forums,
        total_replies=total_replies,
        total_student_replies=total_student_replies,
        total_unrated=total_unrated,
        total_rated=total_rated,
        activity_labels=activity_labels,
        activity_values=activity_values
    )


@main.route('/rate_student_reply', methods=['POST'])
def rate_student_reply():
    if session.get('role') != 'instructor':
        flash("Access denied.", 'danger')
        return redirect(url_for('main.login'))
    
    reply_id = request.form.get('reply_id')
    rating = request.form.get('rating')
    feedback = request.form.get('feedback', '')
    
    if not reply_id or not rating:
        flash("Invalid rating submission.", 'danger')
        return redirect(url_for('main.instructor_forums'))
    
    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            flash("Rating must be between 1 and 5.", 'danger')
            return redirect(url_for('main.instructor_forums'))
    except ValueError:
        flash("Invalid rating value.", 'danger')
        return redirect(url_for('main.instructor_forums'))
    
    instructor_id = session['user_id']
    conn = current_app.get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if columns exist in the forum_replies table
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM information_schema.columns 
            WHERE table_schema = DATABASE() 
            AND table_name = 'forum_replies' 
            AND column_name = 'rating'
        """)
        rating_exists = cursor.fetchone()['count'] > 0
        
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM information_schema.columns 
            WHERE table_schema = DATABASE() 
            AND table_name = 'forum_replies' 
            AND column_name = 'feedback'
        """)
        feedback_exists = cursor.fetchone()['count'] > 0
        
        # Verify the reply belongs to a forum in the instructor's course
        cursor.execute("""
            SELECT fr.id 
            FROM forum_replies fr
            JOIN forums f ON fr.forum_id = f.id
            WHERE fr.id = %s AND f.instructor_id = %s
        """, (reply_id, instructor_id))
        
        if not cursor.fetchone():
            flash("You don't have permission to rate this reply.", 'danger')
            return redirect(url_for('main.instructor_forums'))
        
        # Build the update query dynamically based on available columns
        if rating_exists and feedback_exists:
            # Both columns exist
            cursor.execute("""
                UPDATE forum_replies 
                SET rating = %s, feedback = %s 
                WHERE id = %s
            """, (rating, feedback, reply_id))
        elif rating_exists:
            # Only rating column exists
            cursor.execute("""
                UPDATE forum_replies 
                SET rating = %s 
                WHERE id = %s
            """, (rating, reply_id))
        elif feedback_exists:
            # Only feedback column exists
            cursor.execute("""
                UPDATE forum_replies 
                SET feedback = %s 
                WHERE id = %s
            """, (feedback, reply_id))
        else:
            # Neither column exists - we can't update anything
            flash("Rating system is not available at the moment.", 'warning')
            return redirect(url_for('main.instructor_forums'))
        
        conn.commit()
        flash("✅ Reply rated successfully!", 'success')
        
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error rating reply: {e}")
        flash("Failed to rate reply. Please try again.", 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('main.instructor_forums'))




# =======================
# Forum Detail Page Route
# =======================
@main.route('/forum/<int:forum_id>')
def forum_detail(forum_id):
    student_id = session.get('user_id')
    if not student_id:
        flash("Please log in to view the forum.", "warning")
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # ---------- Enrollment Check ----------
        cursor.execute("""
            SELECT e.id 
            FROM enrollments e
            JOIN courses c ON e.course_id = c.id
            JOIN forums f ON f.course_id = c.id
            WHERE e.student_id = %s AND f.id = %s
        """, (student_id, forum_id))
        enrollment = cursor.fetchone()
        if not enrollment:
            flash("You are not enrolled in the course for this forum.", "danger")
            return redirect(url_for('main.forum_list'))

        # ---------- Forum Details ----------
        cursor.execute("""
            SELECT f.id, f.title, f.description, f.created_at,
                   c.id AS course_id, c.title AS course_title,
                   i.id AS instructor_id, i.name AS instructor_name,
                   (SELECT COUNT(*) FROM forum_replies r WHERE r.forum_id = f.id) AS total_replies
            FROM forums f
            JOIN courses c ON f.course_id = c.id
            LEFT JOIN instructors i ON c.instructor_id = i.id
            WHERE f.id = %s
        """, (forum_id,))
        forum = cursor.fetchone()

        if not forum:
            flash("Forum not found.", "danger")
            return redirect(url_for('main.forum_list'))

        # ---------- Get Course ID for Student List ----------
        course_id = forum.get('course_id')
        if not course_id:
            flash("Course information not available.", "warning")
            return redirect(url_for('main.forum_list'))

        # ---------- Students Enrolled in Course (for sidebar) ----------
        cursor.execute("""
            SELECT u.id, u.full_name, u.profile_image AS avatar,
                   (SELECT COUNT(*) FROM forum_replies fr 
                    WHERE (fr.user_id = u.id OR fr.student_id = u.id) AND fr.forum_id = %s) > 0 AS has_feedback
            FROM users u
            JOIN enrollments e ON u.id = e.student_id
            WHERE e.course_id = %s
            ORDER BY u.full_name
        """, (forum_id, course_id))
        students = cursor.fetchall()

        # ---------- Replies (using both user_id and student_id) ----------
        cursor.execute("""
            SELECT r.id, r.content, r.created_at, r.rating,
                   COALESCE(r.user_id, r.student_id) AS user_id, r.role,
                   u.full_name AS full_name, 
                   u.profile_image AS avatar
            FROM forum_replies r
            JOIN users u ON (u.id = r.user_id OR u.id = r.student_id)
            WHERE r.forum_id = %s
            ORDER BY r.created_at DESC
        """, (forum_id,))
        replies = cursor.fetchall()

        # ---------- Student Feedbacks (for Students tab) ----------
        cursor.execute("""
            SELECT r.id, r.content, r.created_at, r.rating,
                   COALESCE(r.user_id, r.student_id) AS user_id, r.role,
                   u.full_name AS full_name, 
                   u.profile_image AS avatar
            FROM forum_replies r
            JOIN users u ON (u.id = r.user_id OR u.id = r.student_id)
            WHERE r.forum_id = %s
            ORDER BY r.created_at DESC
        """, (forum_id,))
        student_feedbacks = cursor.fetchall()

    except Exception as e:
        flash(f"Database error: {str(e)}", "danger")
        return redirect(url_for('main.forum_list'))
    finally:
        cursor.close()
        conn.close()

    return render_template(
        "forum_detail.html",
        forum=forum,
        replies=replies,
        students=students,
        student_feedbacks=student_feedbacks,
        can_reply=True,
        current_user_id=student_id
    )


@main.route('/instructor_forum_detail/<int:forum_id>')
def instructor_forum_detail(forum_id):
    if session.get('role') != 'instructor':
        flash("Access denied.", 'danger')
        return redirect(url_for('main.login'))

    instructor_id = session['user_id']
    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Fetch forum details including creator and creation date
        cursor.execute("""
            SELECT f.id, f.title, f.description, f.created_at AS creation_date,
                   c.title AS course_title,
                   u.full_name AS instructor_name
            FROM forums f
            JOIN courses c ON f.course_id = c.id
            JOIN users u ON f.instructor_id = u.id
            WHERE f.id = %s AND f.instructor_id = %s
        """, (forum_id, instructor_id))
        forum = cursor.fetchone()

        if not forum:
            flash("Forum not found or you do not have permission to view it.", 'danger')
            return redirect(url_for('main.instructor_forums'))

        # Fetch feedbacks for the selected forum
        cursor.execute("""
            SELECT fr.id, fr.content AS comment, fr.created_at AS submission_date,
                   u.full_name AS student_name
            FROM forum_replies fr
            JOIN users u ON fr.user_id = u.id
            WHERE fr.forum_id = %s
        """, (forum_id,))
        feedbacks = cursor.fetchall()

    except Exception as e:
        current_app.logger.error(f"Error in instructor_forum_detail route: {e}")
        flash("An error occurred while retrieving forum details. Please try again.", 'danger')
    finally:
        cursor.close()
        conn.close()

    return render_template(
        'instructor_forum_detail.html',
        forum=forum,
        feedbacks=feedbacks
    )




@main.route('/forum/<int:forum_id>/reply', methods=['POST'])
def add_forum_reply(forum_id):
    student_id = session.get('user_id')
    if not student_id:
        flash("Please log in to post a reply.", "warning")
        return redirect(url_for('auth.login'))

    content = request.form.get('content')
    rating = request.form.get('rating', 0)  # Default to 0 if not provided

    if not content:
        flash("Feedback content cannot be empty.", "danger")
        return redirect(url_for('main.forum_detail', forum_id=forum_id))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Verify forum exists and user is enrolled
        cursor.execute("""
            SELECT f.id 
            FROM forums f
            JOIN courses c ON f.course_id = c.id
            JOIN enrollments e ON e.course_id = c.id
            WHERE f.id = %s AND e.student_id = %s
        """, (forum_id, student_id))
        forum = cursor.fetchone()
        
        if not forum:
            flash("Forum not found or you are not enrolled.", "danger")
            return redirect(url_for('main.forum_list'))

        # Insert the reply with both user_id and student_id
        cursor.execute("""
            INSERT INTO forum_replies (forum_id, user_id, student_id, content, rating, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, (forum_id, student_id, student_id, content, rating))

        conn.commit()
        flash("Your feedback has been posted successfully.", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Error posting reply: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('main.forum_detail', forum_id=forum_id))



@main.route('/forum_reply/<int:reply_id>/delete', methods=['POST'])
def delete_forum_reply(reply_id):
    student_id = session.get('user_id')
    if not student_id:
        flash("Please log in to delete your reply.", "warning")
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Check if the reply belongs to the current student
    cursor.execute("""
        SELECT forum_id FROM forum_replies
        WHERE id = %s AND user_id = %s
    """, (reply_id, student_id))
    
    reply = cursor.fetchone()
    if not reply:
        flash("You can only delete your own replies.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('main.forum_list'))

    # Delete the reply
    cursor.execute("DELETE FROM forum_replies WHERE id = %s", (reply_id,))
    conn.commit()
    
    forum_id = reply['forum_id']
    cursor.close()
    conn.close()
    
    flash("Your feedback has been deleted.", "success")
    return redirect(url_for('main.forum_detail', forum_id=forum_id))

# =======================
# Rate a Forum Reply
# =======================
@main.route("/rate_reply/<int:reply_id>", methods=["POST"])
def rate_forum_reply(reply_id):
    try:
        user_id = session.get("user_id")
        role = session.get("role")

        if role != "instructor":
            flash("Only instructors can rate replies.", "danger")
            return redirect(request.referrer)

        rating = request.form.get("rating", type=int)
        feedback = request.form.get("feedback")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE forum_replies 
            SET rating = %s, feedback = %s
            WHERE id = %s
        """, (rating, feedback, reply_id))
        conn.commit()

        flash("Reply rated successfully!", "success")
        return redirect(request.referrer)
    except Exception as e:
        print(f"Error in rate_forum_reply: {e}")
        flash("Error while rating reply.", "danger")
        return redirect(request.referrer)
    finally:
        cursor.close()
        conn.close()


# --- LOGIN ROUTE ---
from flask import (
    render_template, request, redirect, url_for, session,
    flash, current_app, get_flashed_messages
)
from werkzeug.security import check_password_hash

@main.route('/login', methods=['GET', 'POST'])
def login():
    # Clear session and isolate login-related flash messages
    session.clear()
    login_flashes = []

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please enter both email and password.', 'danger')
            return render_template('login.html', flashes=get_flashed_messages(with_categories=True))

        conn = current_app.get_db_connection()
        if not conn:
            flash('Unable to connect to the database. Please try again later.', 'danger')
            return render_template('login.html', flashes=get_flashed_messages(with_categories=True))

        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
                user = cursor.fetchone()

            if user and check_password_hash(user['password_hash'], password):
                session['user_id'] = user['id']
                session['role'] = user['role']
                session['full_name'] = user['full_name']

                current_app.log_action(action='user_login', user_id=user['id'])

                if user['role'] == 'instructor' and user.get('force_password_change'):
                    flash('You must change your password before continuing.', 'info')
                    return redirect(url_for('main.change_password'))

                return redirect(url_for(f"main.{user['role']}_dashboard"))
            else:
                flash('Invalid email or password. Please try again.', 'danger')

        except Exception as e:
            current_app.logger.exception(f"Login error for email {email}: {e}")
            flash('An unexpected error occurred during login. Please try again.', 'danger')

        finally:
            try:
                conn.close()
            except Exception as close_err:
                current_app.logger.warning(f"DB close error during login: {close_err}")

    # Only show login-related messages
    login_flashes = get_flashed_messages(with_categories=True)
    return render_template('login.html', flashes=login_flashes)



# --- PROFILE ROUTES ---
@main.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()

        if request.method == 'POST':
            full_name = request.form.get('full_name')
            email = request.form.get('email')
            institution = request.form.get('institution')
            bio = request.form.get('bio')
            interests = request.form.get('interests')
            file = request.files.get('profile_image')

            profile_image_filename = user.get("profile_image")

            # Handle profile image upload
            if file and file.filename and current_app.allowed_file(file.filename):
                import uuid, os
                ext = os.path.splitext(file.filename)[1].lower()
                filename = f"{uuid.uuid4().hex}{ext}"
                filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(filepath)
                profile_image_filename = filename

            # Update DB
            cursor.execute("""
                UPDATE users
                SET full_name = %s,
                    email = %s,
                    institution = %s,
                    bio = %s,
                    interests = %s,
                    profile_image = %s
                WHERE id = %s
            """, (full_name, email, institution, bio, interests, profile_image_filename, session['user_id']))

            conn.commit()
            flash("Profile updated successfully!", "success")
            current_app.log_action(action='profile_update', user_id=session['user_id'])
            return redirect(url_for('main.profile'))

        return render_template("profile.html", user=user)

    finally:
        cursor.close()
        conn.close()



# --- PASSWORD CHANGE ---
@main.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('main.login'))

    user_role = session.get('role')
    user_id = session['user_id']

    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch user
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    if not user:
        flash('User not found.', 'danger')
        cursor.close()
        conn.close()
        return redirect(url_for('main.login'))

    # Optional enforcement for instructors
    if user_role == 'instructor' and not user.get('force_password_change'):
        flash('Password change not required.', 'info')
        cursor.close()
        conn.close()
        return redirect(url_for('main.instructor_dashboard'))

    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # Validation
        if not check_password_hash(user['password_hash'], current_password):
            flash('Incorrect current password.', 'danger')
        elif new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
        elif len(new_password) < 6:
            flash('New password must be at least 6 characters long.', 'danger')
        else:
            new_password_hash = generate_password_hash(new_password)
            cursor.execute("""
                UPDATE users
                SET password_hash = %s,
                    force_password_change = FALSE
                WHERE id = %s
            """, (new_password_hash, user_id))
            conn.commit()
            flash('Password updated successfully!', 'success')
            current_app.log_action(action='password_change', user_id=user_id)

            cursor.close()
            conn.close()

            # Redirect based on role
            return redirect(url_for(f"main.{user_role}_dashboard"))

    cursor.close()
    conn.close()
    return render_template('change_password.html', user=user)



# --- LOGOUT ---
@main.route('/logout')
def logout():
    current_app.log_action(action='user_logout', user_id=session.get('user_id'))
    session.clear()
    return redirect(url_for('main.login'))


# --- STUDENT DASHBOARD ---
@main.route('/student_dashboard')
def student_dashboard():
    student_id = session.get('user_id')
    if not student_id:
        flash("Please log in to access your dashboard.", "warning")
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Student Info
    cursor.execute("SELECT full_name FROM users WHERE id = %s", (student_id,))
    student = cursor.fetchone()
    full_name = student['full_name'] if student else "Student"

    # Assignments (fetch all assignments in the system)
    cursor.execute("""
        SELECT a.id, a.title, a.due_date, u.full_name AS instructor_name
        FROM assignments a
        JOIN courses c ON a.course_id = c.id
        JOIN users u ON c.instructor_id = u.id
        ORDER BY a.due_date ASC
    """)
    assignments = cursor.fetchall()

    # Next Due Assignment
    cursor.execute("""
        SELECT a.due_date
        FROM assignments a
        ORDER BY a.due_date ASC
        LIMIT 1
    """)
    next_due = cursor.fetchone()
    next_due_date = next_due['due_date'] if next_due else None

    # Feedback Stats
    cursor.execute("SELECT COUNT(*) AS count FROM peer_feedback WHERE receiver_id = %s", (student_id,))
    feedback_received_count = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) AS count FROM peer_feedback WHERE giver_id = %s", (student_id,))
    feedback_given_count = cursor.fetchone()['count']

    # Active Peers
    cursor.execute("SELECT COUNT(*) AS count FROM users WHERE role = 'student' AND id != %s", (student_id,))
    active_peers_count = cursor.fetchone()['count']

    # Courses (all students see all courses)
    cursor.execute("""
        SELECT c.id, c.title, c.description, u.full_name AS instructor_name
        FROM courses c
        JOIN users u ON c.instructor_id = u.id
        ORDER BY c.created_at DESC
    """)
    my_courses = cursor.fetchall()

    # Quizzes
    cursor.execute("""
        SELECT q.id, q.title, q.total_marks, q.due_date, u.full_name AS instructor_name,
               COALESCE(sq.status, 'Not Started') AS status
        FROM quizzes q
        JOIN courses c ON q.course_id = c.id
        JOIN users u ON c.instructor_id = u.id
        LEFT JOIN student_quizzes sq ON sq.quiz_id = q.id AND sq.student_id = %s
        ORDER BY q.created_at DESC
    """, (student_id,))
    quizzes = cursor.fetchall()

    # Forums
    cursor.execute("""
        SELECT f.id, f.title, f.description,
               c.title AS course_title,
               u.full_name AS instructor_name
        FROM forums f
        JOIN courses c ON f.course_id = c.id
        JOIN users u ON c.instructor_id = u.id
        ORDER BY f.created_at DESC
    """)
    forums = cursor.fetchall()

    # Groups
    cursor.execute("""
        SELECT g.id, g.name, c.title AS course_title, u.full_name AS instructor_name
        FROM `groups` g
        JOIN group_members gm ON gm.group_id = g.id
        JOIN courses c ON g.course_id = c.id
        JOIN users u ON c.instructor_id = u.id
        WHERE gm.student_id = %s
    """, (student_id,))
    student_groups = cursor.fetchall()

    # Live Sessions
    cursor.execute("""
        SELECT cs.session_id, cs.topic, cs.start_time, g.name AS group_name
        FROM collab_sessions cs
        JOIN `groups` g ON cs.group_id = g.id
        WHERE g.id IN (
            SELECT group_id FROM group_members WHERE student_id = %s
        )
        ORDER BY cs.start_time ASC
    """, (student_id,))
    collab_sessions = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'student_dashboard.html',
        full_name=full_name,
        assignments=assignments,
        feedback_received_count=feedback_received_count,
        feedback_given_count=feedback_given_count,
        active_peers_count=active_peers_count,
        my_courses=my_courses,
        quizzes=quizzes,
        forums=forums,
        student_groups=student_groups,
        collab_sessions=collab_sessions,
        next_due_date=next_due_date
    )



@main.route("/get_dashboard_data")
def get_dashboard_data():
    student_id = session.get("user_id")
    if not student_id:
        return jsonify({"error": "Not logged in"}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Example: Assignments count
    cursor.execute("SELECT COUNT(*) AS count FROM assignments")
    assignments_count = cursor.fetchone()["count"]

    # Example: Feedback counts
    cursor.execute("SELECT COUNT(*) AS count FROM peer_feedback WHERE receiver_id = %s", (student_id,))
    feedback_received = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) AS count FROM peer_feedback WHERE giver_id = %s", (student_id,))
    feedback_given = cursor.fetchone()["count"]

    # Example: Peers count
    cursor.execute("SELECT COUNT(*) AS count FROM users WHERE role = 'student' AND id != %s", (student_id,))
    active_peers = cursor.fetchone()["count"]

    cursor.close()
    conn.close()

    return jsonify({
        "assignments_due": assignments_count,
        "feedback_received": feedback_received,
        "feedback_given": feedback_given,
        "active_peers": active_peers
    })


# POST: handle new session creation
@main.route("/api/instructor", methods=["GET"])
def get_instructor():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Assuming your users table has 'username' or 'full_name' instead of 'name'
    cursor.execute("""
        SELECT id, username, email 
        FROM users 
        WHERE id = %s AND role = 'instructor'
    """, (user_id,))
    instructor = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if instructor:
        # If you have a different column for the name, adjust accordingly
        # For example, if you have 'full_name' or 'first_name' + 'last_name'
        # This is just a placeholder - adjust to your actual schema
        instructor_data = {
            "id": instructor["id"],
            "name": instructor.get("username", "Instructor"),  # Fallback to username
            "email": instructor["email"]
        }
        return jsonify(instructor_data)
    return jsonify({"error": "Instructor not found"}), 404


@main.route("/api/courses", methods=["GET"])
def get_courses():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Assuming your courses table has 'course_name' instead of 'name'
    cursor.execute("""
        SELECT id, course_name, code 
        FROM courses 
        WHERE instructor_id = %s
        ORDER BY course_name
    """, (user_id,))
    courses = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    # Format courses for frontend
    formatted_courses = []
    for course in courses:
        formatted_courses.append({
            "id": course["id"],
            "name": course["course_name"]  # Map course_name to name for frontend
        })
    
    return jsonify(formatted_courses)


@main.route("/api/sessions", methods=["GET", "POST"])
def handle_sessions():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == "POST":
        try:
            data = request.get_json()
            
            # Extract data from request
            title = data.get("title")
            course_id = data.get("course_id")
            date = data.get("date")
            time = data.get("time")
            duration = int(data.get("duration"))
            description = data.get("description", "")
            breakout_rooms = data.get("breakout_rooms", False)
            live_polls = data.get("live_polls", False)
            peer_feedback = data.get("peer_feedback", False)
            screen_sharing = data.get("screen_sharing", False)
            feedback_prompts = data.get("feedback_prompts", [])
            
            # Validate required fields
            if not title or not course_id or not date or not time:
                return jsonify({"error": "Missing required fields"}), 400
            
            # Convert to datetime
            start_time = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            end_time = start_time + timedelta(minutes=duration)
            
            # Get course name for the session
            cursor.execute("SELECT course_name FROM courses WHERE id = %s", (course_id,))
            course = cursor.fetchone()
            if not course:
                return jsonify({"error": "Course not found"}), 404
            
            # Insert session - adjust column names to match your schema
            cursor.execute("""
                INSERT INTO live_schedule 
                (title, description, start_time, end_time, instructor_id, course_id,
                 breakout_rooms, live_polls, peer_feedback, screen_sharing)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                title, description, start_time, end_time, user_id, course_id,
                breakout_rooms, live_polls, peer_feedback, screen_sharing
            ))
            session_id = cursor.lastrowid
            
            # Store feedback prompts
            for prompt in feedback_prompts:
                if prompt.strip():
                    cursor.execute("""
                        INSERT INTO feedback_prompts (session_id, prompt_text) 
                        VALUES (%s,%s)
                    """, (session_id, prompt.strip()))
            
            conn.commit()
            
            # Return the created session with course name
            new_session = {
                "id": session_id,
                "title": title,
                "course_name": course["course_name"],
                "date": date,
                "time": time,
                "duration": duration,
                "description": description,
                "breakout_rooms": breakout_rooms,
                "live_polls": live_polls,
                "peer_feedback": peer_feedback,
                "screen_sharing": screen_sharing
            }
            
            return jsonify(new_session), 201
            
        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500
        
    else:  # GET request
        cursor.execute("""
            SELECT ls.id, ls.title, ls.description, ls.start_time, ls.end_time, 
                   ls.breakout_rooms, ls.live_polls, ls.peer_feedback, ls.screen_sharing,
                   c.course_name
            FROM live_schedule ls
            JOIN courses c ON ls.course_id = c.id
            WHERE ls.instructor_id = %s AND ls.start_time >= NOW()
            ORDER BY ls.start_time ASC
        """, (user_id,))
        sessions_data = cursor.fetchall()
        
        # Format sessions for frontend
        formatted_sessions = []
        for session_data in sessions_data:
            # Extract date and time from start_time
            start_datetime = session_data["start_time"]
            date_str = start_datetime.strftime("%Y-%m-%d")
            time_str = start_datetime.strftime("%H:%M")
            
            # Calculate duration in minutes
            duration = int((session_data["end_time"] - session_data["start_time"]).total_seconds() / 60)
            
            formatted_sessions.append({
                "id": session_data["id"],
                "title": session_data["title"],
                "course_name": session_data["course_name"],
                "date": date_str,
                "time": time_str,
                "duration": duration,
                "description": session_data["description"],
                "breakout_rooms": bool(session_data["breakout_rooms"]),
                "live_polls": bool(session_data["live_polls"]),
                "peer_feedback": bool(session_data["peer_feedback"]),
                "screen_sharing": bool(session_data["screen_sharing"])
            })
        
        cursor.close()
        conn.close()
        
        return jsonify(formatted_sessions)


@main.route("/api/sessions/<int:session_id>", methods=["DELETE"])
def delete_session(session_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Check if session exists and belongs to this instructor
    cursor.execute("""
        SELECT id FROM live_schedule 
        WHERE id = %s AND instructor_id = %s
    """, (session_id, user_id))
    session = cursor.fetchone()
    
    if not session:
        cursor.close()
        conn.close()
        return jsonify({"error": "Session not found"}), 404
    
    try:
        # Delete feedback prompts first
        cursor.execute("DELETE FROM feedback_prompts WHERE session_id = %s", (session_id,))
        
        # Delete session
        cursor.execute("DELETE FROM live_schedule WHERE id = %s", (session_id,))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({"success": True})
    
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({"error": str(e)}), 500


@main.route("/live_schedule", methods=["GET", "POST"])
def live_schedule():
    # This route now serves the HTML page for the live schedule
    # The actual data is fetched via API calls from the frontend
    return render_template("live_schedule.html")


@main.route("/live_schedule/<int:session_id>/start")
def start_schedule(session_id):
    # In production: redirect to Zoom/Meet/Custom video URL
    flash(f"Live session {session_id} started!", "success")
    return redirect(url_for("main.live_schedule"))


@main.route("/live_schedule/<int:session_id>/edit", methods=["GET", "POST"])
def edit_schedule(session_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == "POST":
        try:
            title = request.form.get("sessionTitle")
            description = request.form.get("sessionDescription")
            cursor.execute("""
                UPDATE live_schedule 
                SET title=%s, description=%s
                WHERE id=%s
            """, (title, description, session_id))
            conn.commit()
            flash("Session updated!", "success")
            return redirect(url_for("main.live_schedule"))
        except Exception as e:
            conn.rollback()
            flash(f"Error editing session: {e}", "danger")
    
    cursor.execute("SELECT * FROM live_schedule WHERE id=%s", (session_id,))
    session_data = cursor.fetchone()
    
    cursor.close()
    conn.close()
    return render_template("edit_schedule.html", session=session_data)


@main.route("/live_schedule/<int:session_id>/cancel", methods=["POST"])
def cancel_schedule(session_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM live_schedule WHERE id=%s", (session_id,))
        conn.commit()
        flash("Session canceled successfully!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error canceling session: {e}", "danger")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for("main.live_schedule"))


# --- FORUM ROUTES ---
@main.route('/forums')
def forum_list():
    student_id = session.get('user_id')
    if not student_id:
        flash("Please log in to view forums.", "warning")
        return redirect(url_for('main.login'))  # ✅ use 'main.login'

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    from datetime import datetime, timedelta
    current_date = datetime.now()
    recent_threshold = current_date - timedelta(days=30)

    # ✅ Fetch forums created by instructors for courses the student is enrolled in
    cursor.execute("""
        SELECT f.id, f.title, f.description, f.created_at,
               c.title AS course_title,
               u.full_name AS instructor_name,
               (SELECT COUNT(*) FROM forum_replies r WHERE r.forum_id = f.id) AS total_replies,
               (SELECT AVG(rating) FROM forum_replies r WHERE r.forum_id = f.id AND r.rating IS NOT NULL) AS avg_rating
        FROM forums f
        JOIN courses c ON f.course_id = c.id
        JOIN users u ON c.instructor_id = u.id
        JOIN enrollments e ON e.course_id = c.id
        WHERE e.student_id = %s
        ORDER BY f.created_at DESC
    """, (student_id,))
    forums = cursor.fetchall()

    # ✅ Split forums into recent and past
    recent_forums = [f for f in forums if f['created_at'] >= recent_threshold]
    past_forums = [f for f in forums if f['created_at'] < recent_threshold]

    # ✅ Student’s total replies
    cursor.execute("""
        SELECT COUNT(*) AS user_replies
        FROM forum_replies
        WHERE student_id = %s
    """, (student_id,))
    user_replies = cursor.fetchone()['user_replies']

    # ✅ Student’s average rating
    cursor.execute("""
        SELECT AVG(rating) AS user_avg_rating
        FROM forum_replies
        WHERE student_id = %s AND rating IS NOT NULL
    """, (student_id,))
    result = cursor.fetchone()
    user_avg_rating = result['user_avg_rating'] if result and result['user_avg_rating'] else None

    cursor.close()
    conn.close()

    return render_template(
        'forum_list.html',
        recent_forums=recent_forums,
        past_forums=past_forums,
        total_forums=len(forums),
        user_replies=user_replies,
        user_avg_rating=user_avg_rating
    )


@main.route('/forum/<int:forum_id>')
def forum(forum_id):
    """Display a specific forum with replies and announcements (accessible to all students)."""
    student_id = session.get('user_id')
    if not student_id:
        flash("Please log in to view this forum.", "warning")
        return redirect(url_for('main.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get current user info
    cursor.execute("SELECT full_name, role FROM users WHERE id = %s", (student_id,))
    current_user = cursor.fetchone()

    # Forum details with course + instructor info (removed enrollment restriction)
    cursor.execute("""
        SELECT f.id, f.title, f.description, f.created_at, f.rating,
               c.id AS course_id, c.title AS course_title,
               u.full_name AS instructor_name
        FROM forums f
        JOIN courses c ON f.course_id = c.id
        JOIN users u ON c.instructor_id = u.id
        WHERE f.id = %s
    """, (forum_id,))
    forum = cursor.fetchone()

    if not forum:
        flash("Forum not found.", "error")
        cursor.close()
        conn.close()
        return redirect(url_for('main.student_dashboard'))

    # Forum replies (with optional instructor flag + rating)
    cursor.execute("""
        SELECT r.id, r.content, r.created_at,
               u.full_name AS student_name,
               CASE WHEN u.role = 'instructor' THEN 1 ELSE 0 END AS is_instructor,
               r.rating
        FROM forum_replies r
        JOIN users u ON r.student_id = u.id
        WHERE r.forum_id = %s
        ORDER BY r.created_at ASC
    """, (forum_id,))
    replies = cursor.fetchall()

    # Forum announcements (from instructor)
    cursor.execute("""
        SELECT content, created_at
        FROM forum_announcements
        WHERE forum_id = %s
        ORDER BY created_at DESC
    """, (forum_id,))
    announcements = cursor.fetchall()

    # Unread notifications count for current user
    cursor.execute("""
        SELECT COUNT(*) as unread_count
        FROM notifications 
        WHERE user_id = %s AND is_read = 0
    """, (student_id,))
    unread_notifications = cursor.fetchone()['unread_count']

    # Recent notifications for dropdown
    cursor.execute("""
        SELECT id, message, created_at, is_read
        FROM notifications 
        WHERE user_id = %s 
        ORDER BY created_at DESC 
        LIMIT 5
    """, (student_id,))
    recent_notifications = cursor.fetchall()

    # Track forum visit
    cursor.execute("""
        INSERT INTO forum_visits (user_id, forum_id, visited_at) 
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE visited_at = %s
    """, (student_id, forum_id, datetime.now(), datetime.now()))

    conn.commit()
    cursor.close()
    conn.close()

    return render_template(
        'forum.html',
        forum=forum,
        replies=replies,
        announcements=announcements,
        current_user=current_user,
        unread_notifications=unread_notifications,
        recent_notifications=recent_notifications,
        current_year=datetime.now().year
    )


# Additional route for notifications
@main.route('/notifications')
def notifications():
    """Display all notifications for the current user."""
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, message, type, created_at, is_read
        FROM notifications 
        WHERE user_id = %s 
        ORDER BY created_at DESC
    """, (user_id,))
    notifications = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('notifications.html', notifications=notifications)


@main.route('/notifications/mark_read/<int:notification_id>')
def mark_notification_read(notification_id):
    """Mark a specific notification as read."""
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE notifications 
        SET is_read = 1 
        WHERE id = %s AND user_id = %s
    """, (notification_id, user_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(request.referrer or url_for('main.notifications'))


@main.route('/notifications/mark_all_read')
def mark_all_notifications_read():
    """Mark all notifications as read for the current user."""
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE notifications 
        SET is_read = 1 
        WHERE user_id = %s AND is_read = 0
    """, (user_id,))

    conn.commit()
    cursor.close()
    conn.close()

    flash("All notifications marked as read.", "success")
    return redirect(url_for('main.notifications'))



# --- ASSIGNMENT ROUTES ---
UPLOAD_FOLDER = os.path.join("uploads", "assignments")

# 🔹 List assignments + handle submissions in one route
@main.route("/assignments", methods=["GET", "POST"])
def assignments():
    if "user_id" not in session:
        flash("Please log in to view assignments.", "warning")
        return redirect(url_for("main.login"))

    user_id = session["user_id"]

    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ✅ Handle submission / resubmission
    if request.method == "POST":
        assignment_id = request.form.get("assignment_id")
        file = request.files.get("solution_file")

        if not assignment_id or not file or file.filename == "":
            flash("Please select a file to upload.", "danger")
            return redirect(url_for("main.assignments"))

        # Save file
        filename = secure_filename(file.filename)
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        # Check if already submitted
        cursor.execute(
            "SELECT * FROM submissions WHERE assignment_id=%s AND student_id=%s",
            (assignment_id, user_id),
        )
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                """
                UPDATE submissions 
                SET file_path=%s, submitted_at=%s 
                WHERE id=%s
                """,
                (filename, datetime.utcnow(), existing["id"]),
            )
            flash("Your submission has been updated.", "success")
        else:
            cursor.execute(
                """
                INSERT INTO submissions (assignment_id, student_id, file_path, submitted_at)
                VALUES (%s, %s, %s, %s)
                """,
                (assignment_id, user_id, filename, datetime.utcnow()),
            )
            flash("Assignment submitted successfully.", "success")

        conn.commit()

    # ✅ Fetch assignments
    cursor.execute("SELECT * FROM assignments ORDER BY due_date ASC")
    assignments = cursor.fetchall()

    # ✅ Attach submission info for this student
    for a in assignments:
        cursor.execute(
            "SELECT * FROM submissions WHERE assignment_id=%s AND student_id=%s",
            (a["id"], user_id),
        )
        a["submission"] = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("assignments.html", assignments=assignments)


# 🔹 Download submission
@main.route("/submission/<int:submission_id>/download")
def download_submission(submission_id):
    if "user_id" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("main.login"))

    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT file_path FROM submissions WHERE id=%s", (submission_id,))
    submission = cursor.fetchone()

    cursor.close()
    conn.close()

    if not submission:
        flash("Submission not found.", "danger")
        return redirect(url_for("main.assignments"))

    filepath = os.path.join(UPLOAD_FOLDER, submission["file_path"])
    if not os.path.exists(filepath):
        flash("File not found on server.", "danger")
        return redirect(url_for("main.assignments"))

    return send_file(filepath, as_attachment=True)




@main.route('/collab_sessions', methods=['GET'])
def collab_sessions():
    """Render the live collaboration dashboard for students."""
    if 'user_id' not in session:
        flash("Please log in to access live collaboration sessions.", "warning")
        return redirect(url_for('main.login'))

    user_id = session['user_id']
    role = session.get('role', 'student')
    can_create_session = role in ['instructor', 'admin']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, topic, start_time, skill_focus
            FROM collab_sessions
            WHERE start_time >= NOW()
            ORDER BY start_time ASC
        """)
        collab_sessions = cursor.fetchall()
    except Exception as e:
        collab_sessions = []
        flash(f"Unable to load sessions: {e}", "danger")

    cursor.close()
    conn.close()

    return render_template(
        'collab_sessions.html',
        collab_sessions=collab_sessions,
        can_create_session=can_create_session
    )


@main.route('/join_session/<int:session_id>')
def join_session(session_id):
    """Redirect to session room or track participation."""
    if 'user_id' not in session:
        flash("Please log in to join a session.", "warning")
        return redirect(url_for('main.login'))

    # Optional: log participation, update presence, etc.
    flash("You've joined the session!", "info")
    return redirect(url_for('main.collab_sessions'))


@main.route('/create_session', methods=['POST'])
def create_session():
    """Allow instructors/admins to create new collaboration sessions."""
    if 'user_id' not in session or session.get('role') not in ['instructor', 'admin']:
        flash("You do not have permission to create a session.", "danger")
        return redirect(url_for('main.collab_sessions'))

    topic = request.form.get('topic')
    start_time_str = request.form.get('start_time')
    skill_focus = request.form.get('skill_focus', '')

    if not topic or not start_time_str:
        flash("Topic and start time are required.", "warning")
        return redirect(url_for('main.collab_sessions'))

    try:
        start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        flash("Invalid start time format.", "danger")
        return redirect(url_for('main.collab_sessions'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO collab_sessions (topic, start_time, skill_focus, created_by)
            VALUES (%s, %s, %s, %s)
        """, (topic, start_time, skill_focus, session['user_id']))
        conn.commit()
        flash("Collaboration session created successfully.", "success")
    except Exception as e:
        flash(f"Error creating session: {e}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('main.collab_sessions'))



@main.route('/session_room/<int:session_id>')
def session_room(session_id):
    if 'user_id' not in session:
        flash("Please log in to access the session room.", "warning")
        return redirect(url_for('main.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT topic, skill_focus FROM collab_sessions WHERE id = %s", (session_id,))
    session_data = cursor.fetchone()

    if not session_data:
        flash("Session not found.", "danger")
        return redirect(url_for('main.collab_sessions'))

    cursor.close()
    conn.close()

    return render_template('session_room.html', session=session_data, session_id=session_id, user_id=session['user_id'])


@main.route('/submit_feedback/<int:session_id>', methods=['POST'])
def submit_feedback(session_id):
    if 'user_id' not in session:
        flash("Please log in to submit feedback.", "warning")
        return redirect(url_for('main.login'))

    feedback_text = request.form.get('feedback', '').strip()
    if not feedback_text:
        flash("Feedback cannot be empty.", "danger")
        return redirect(url_for('main.session_room', session_id=session_id))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO session_feedback (session_id, user_id, feedback, timestamp)
        VALUES (%s, %s, %s, NOW())
    """, (session_id, session['user_id'], feedback_text))

    conn.commit()
    cursor.close()
    conn.close()

    flash("Feedback submitted successfully!", "success")
    return redirect(url_for('main.session_room', session_id=session_id))


@main.route('/quizzes')
def quizzes():
    user_id = session.get('user_id')
    if not user_id:
        flash("Session expired. Please log in again.", "warning")
        return redirect(url_for('main.login'))

    conn = current_app.get_db_connection()
    quizzes = []

    try:
        with conn.cursor(dictionary=True) as cursor:
            # Get quizzes assigned to student
            cursor.execute("""
                SELECT q.id, q.title, q.description, q.due_date,
                       (SELECT COUNT(*) FROM quiz_submissions WHERE student_id = %s AND quiz_id = q.id) AS submitted
                FROM quizzes q
                JOIN enrollments e ON e.course_id = q.id  -- adjust if quizzes are linked to courses
                WHERE e.student_id = %s
                ORDER BY q.due_date ASC
            """, (user_id, user_id))
            raw_quizzes = cursor.fetchall()

            for q in raw_quizzes:
                cursor.execute("""
                    SELECT id, question_text
                    FROM quiz_questions
                    WHERE quiz_id = %s
                """, (q['id'],))
                questions = cursor.fetchall()
                quizzes.append({
                    'id': q['id'],
                    'title': q['title'],
                    'description': q['description'],
                    'due_date': q['due_date'],
                    'status': 'completed' if q['submitted'] else 'pending',
                    'questions': [{'id': qn['id'], 'text': qn['question_text']} for qn in questions]
                })

    except Exception as e:
        current_app.logger.error(f"Error loading quizzes: {e}")
        flash("Unable to load quizzes.", "danger")

    finally:
        conn.close()

    return render_template('quizzes.html', quizzes=quizzes)


@main.route('/submit_quiz/<int:quiz_id>', methods=['POST'])
def submit_quiz(quiz_id):
    user_id = session.get('user_id')
    if not user_id:
        flash("Session expired. Please log in again.", "warning")
        return redirect(url_for('main.login'))

    conn = current_app.get_db_connection()

    try:
        with conn.cursor() as cursor:
            # Create submission record
            cursor.execute("""
                INSERT INTO quiz_submissions (student_id, quiz_id)
                VALUES (%s, %s)
            """, (user_id, quiz_id))
            submission_id = cursor.lastrowid

            # Get question IDs
            cursor.execute("""
                SELECT id FROM quiz_questions WHERE quiz_id = %s
            """, (quiz_id,))
            question_ids = [row[0] for row in cursor.fetchall()]

            # Save answers
            for qid in question_ids:
                answer = request.form.get(f'answer_{qid}', '').strip()
                cursor.execute("""
                    INSERT INTO quiz_answers (submission_id, question_id, answer_text)
                    VALUES (%s, %s, %s)
                """, (submission_id, qid, answer))

        conn.commit()
        flash("Quiz submitted successfully!", "success")

    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error submitting quiz {quiz_id} for user {user_id}: {e}")
        flash("Failed to submit quiz.", "danger")

    finally:
        conn.close()

    return redirect(url_for('main.quizzes'))


@main.route('/enrollment', methods=['GET', 'POST'])
def enrollment():
    return render_template('enrollment.html')

@main.route('/view_submissions')
def view_submissions():
    user_id = session.get('user_id')
    if not user_id:
        flash('Session expired. Please log in again.', 'warning')
        return redirect(url_for('main.login'))

    conn = current_app.get_db_connection()
    if not conn:
        flash("Database connection error.", "danger")
        return redirect(url_for('main.login'))

    try:
        with conn.cursor(dictionary=True) as cursor:
            # Fetch submissions made by the current user
            cursor.execute("""
                SELECT s.id, a.title, c.name AS course, s.submitted_at, s.grade
                FROM submissions s
                JOIN assignments a ON s.assignment_id = a.id
                JOIN courses c ON a.course_id = c.id
                WHERE s.student_id = %s
                ORDER BY s.submitted_at DESC
            """, (user_id,))
            raw_submissions = cursor.fetchall() or []

            # Format submissions for template
            submissions = []
            for sub in raw_submissions:
                submissions.append({
                    'id': sub['id'],
                    'title': sub['title'],
                    'course': sub['course'],
                    'submitted_on': sub['submitted_at'],
                    'grade': sub['grade'],
                    'feedback_url': url_for('main.view_feedback', submission_id=sub['id'])
                })

        return render_template('view_submissions.html', submissions=submissions)

    except Exception as e:
        current_app.logger.exception(f"Failed to load submissions for user {user_id}: {e}")
        flash("An error occurred while loading your submissions.", "danger")
        return redirect(url_for('main.dashboard'))

    finally:
        try:
            conn.close()
        except Exception as close_err:
            current_app.logger.warning(f"Failed to close DB connection: {close_err}")



@main.route('/peer_review')
def peer_review_hub():
    """Show the peer review hub when no specific submission is selected."""
    user_id = session.get('user_id')
    if not user_id:
        flash('Session expired. Please log in again.', 'warning')
        return redirect(url_for('main.login'))

    conn = current_app.get_db_connection()
    if not conn:
        flash("Database connection error.", "danger")
        return redirect(url_for('main.login'))

    try:
        with conn.cursor(dictionary=True) as cursor:
            # Get submissions available for peer review
            cursor.execute("""
                SELECT s.id, s.content, u.full_name AS author_name, a.title AS assignment_title
                FROM submissions s
                JOIN users u ON s.student_id = u.id
                JOIN assignments a ON s.assignment_id = a.id
                WHERE s.student_id != %s
            """, (user_id,))
            submissions = cursor.fetchall()

        return render_template(
            'peer_review_hub.html',
            submissions=submissions
        )

    except Exception as e:
        current_app.logger.exception(f"Error loading peer review hub: {e}")
        flash("An error occurred while loading the peer review hub.", "danger")
        return redirect(url_for('main.student_dashboard'))

    finally:
        try:
            conn.close()
        except Exception as close_err:
            current_app.logger.warning(f"Failed to close DB connection: {close_err}")


@main.route('/peer_review/<int:submission_id>')
def peer_review(submission_id):
    """View a specific submission for peer review."""
    user_id = session.get('user_id')
    if not user_id:
        flash('Session expired. Please log in again.', 'warning')
        return redirect(url_for('main.login'))

    conn = current_app.get_db_connection()
    if not conn:
        flash("Database connection error.", "danger")
        return redirect(url_for('main.login'))

    try:
        with conn.cursor(dictionary=True) as cursor:
            # Fetch submission details
            cursor.execute("""
                SELECT s.id, s.content, s.file_path, u.full_name AS author_name, s.assignment_id
                FROM submissions s
                JOIN users u ON s.student_id = u.id
                WHERE s.id = %s
            """, (submission_id,))
            submission = cursor.fetchone()
            if not submission:
                flash("Submission not found.", "danger")
                return redirect(url_for('main.peer_review_hub'))

            # Fetch assignment details
            assignment_id = submission.get('assignment_id')
            if not assignment_id:
                flash("Assignment ID missing in submission.", "danger")
                return redirect(url_for('main.peer_review_hub'))

            cursor.execute("""
                SELECT id, title, description, due_date
                FROM assignments
                WHERE id = %s
            """, (assignment_id,))
            assignment = cursor.fetchone()
            if not assignment:
                flash("Assignment details not found.", "danger")
                return redirect(url_for('main.peer_review_hub'))

        return render_template(
            'peer_review.html',
            assignment=assignment,
            submission=submission
        )

    except Exception as e:
        current_app.logger.exception(f"Error loading peer review page for submission {submission_id}: {e}")
        flash("An error occurred while loading the peer review page.", "danger")
        return redirect(url_for('main.peer_review_hub'))

    finally:
        try:
            conn.close()
        except Exception as close_err:
            current_app.logger.warning(f"Failed to close DB connection: {close_err}")


@main.route('/submit_peer_review/<int:submission_id>', methods=['POST'])
def submit_peer_review(submission_id):
    """Handle submission of a peer review."""
    user_id = session.get('user_id')
    if not user_id:
        flash('Session expired. Please log in again.', 'warning')
        return redirect(url_for('main.login'))

    rating = request.form.get('rating', type=int)
    comments = request.form.get('comments', '').strip()

    if not rating or not comments:
        flash('Please provide both a rating and comments.', 'warning')
        return redirect(url_for('main.peer_review', submission_id=submission_id))

    conn = current_app.get_db_connection()
    if not conn:
        flash("Database connection error.", "danger")
        return redirect(url_for('main.peer_review', submission_id=submission_id))

    try:
        with conn.cursor() as cursor:
            # Check if review already exists
            cursor.execute("""
                SELECT id FROM peer_feedback
                WHERE submission_id = %s AND reviewer_id = %s
            """, (submission_id, user_id))
            existing_review = cursor.fetchone()

            if existing_review:
                flash("You've already submitted a review for this submission.", "info")
                return redirect(url_for('main.peer_review_hub'))

            # Insert new peer review
            cursor.execute("""
                INSERT INTO peer_feedback (submission_id, reviewer_id, rating, comments, status, reviewed_at)
                VALUES (%s, %s, %s, %s, 'completed', NOW())
            """, (submission_id, user_id, rating, comments))
            conn.commit()

        flash('Your review has been submitted successfully!', 'success')
        return redirect(url_for('main.peer_review_hub'))

    except Exception as e:
        current_app.logger.exception(f"Failed to submit peer review for submission {submission_id}: {e}")
        flash("An error occurred while submitting your review.", "danger")
        return redirect(url_for('main.peer_review', submission_id=submission_id))

    finally:
        try:
            conn.close()
        except Exception as close_err:
            current_app.logger.warning(f"Failed to close DB connection: {close_err}")



# --- CALENDAR ROUTE ---
@main.route('/create_instructor')
def create_instructor():
    return render_template('create_instructor.html')


@main.route('/instructor/delete_material/<int:material_id>')
def delete_material(material_id):
    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM course_materials WHERE id = %s", (material_id,))
    material = cursor.fetchone()

    if not material or session.get('user_id') != material['instructor_id']:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('main.view_materials'))

    try:
        os.remove(material['filepath'])
    except FileNotFoundError:
        pass

    cursor.execute("DELETE FROM course_materials WHERE id = %s", (material_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Material deleted successfully!', 'info')
    return redirect(url_for('main.view_materials'))


# Simulated database
@main.route('/create_course', methods=['GET', 'POST'])
def create_course():
    user_id = session.get('user_id')
    role = session.get('role')

    # 🔐 Access control
    if not user_id or role != 'instructor':
        flash("Unauthorized access.", "error")
        return redirect(url_for('main.login'))

    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ==================== Handle Course Creation ====================
    if request.method == 'POST':
        title = request.form.get('courseTitle', '').strip()
        course_code = request.form.get('courseCode', '').strip()
        instructor_name = request.form.get('instructorName', '').strip()
        description = request.form.get('courseDescription', '').strip()
        materials = request.files.get('courseMaterials')

        # ✅ Validate required fields
        if not title or not course_code or not instructor_name or not description:
            flash("All fields except materials are required.", "warning")
        else:
            filename = None
            if materials and materials.filename:
                filename = secure_filename(materials.filename)
                upload_dir = os.path.join(current_app.static_folder, 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                upload_path = os.path.join(upload_dir, filename)
                materials.save(upload_path)

            try:
                # Insert new course
                cursor.execute("""
                    INSERT INTO courses (title, description, instructor_id, course_code, materials, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, (title, description, user_id, course_code, filename))
                course_id = cursor.lastrowid  # ✅ Get the new course ID

                # ✅ Auto-enroll all students
                cursor.execute("SELECT id FROM users WHERE role = 'student'")
                students = cursor.fetchall()

                for student in students:
                    cursor.execute("""
                        INSERT IGNORE INTO enrollments (student_id, course_id, enrolled_at)
                        VALUES (%s, %s, NOW())
                    """, (student['id'], course_id))

                conn.commit()
                flash("Course created successfully and all students auto-enrolled!", "success")

            except Exception as e:
                conn.rollback()
                flash(f"Error creating course: {str(e)}", "error")

    # ==================== Fetch Instructor's Courses ====================
    try:
        cursor.execute("""
            SELECT c.id, c.title, c.description, c.materials, c.course_code,
                   (SELECT COUNT(*) FROM enrollments WHERE course_id = c.id) AS enrolled_students
            FROM courses c
            WHERE c.instructor_id = %s AND (c.is_deleted IS NULL OR c.is_deleted = 0)
            ORDER BY c.created_at DESC
        """, (user_id,))
        courses = cursor.fetchall()
    except Exception as e:
        courses = []
        flash(f"Error loading courses: {str(e)}", "error")

    cursor.close()
    conn.close()

    return render_template('create_course.html', courses=courses)





@main.route('/delete_course/<int:course_id>', methods=['POST'])
def delete_course(course_id):
    user_id = session.get('user_id')
    role = session.get('role')

    if not user_id or role != 'instructor':
        flash("Unauthorized access.", "error")
        return redirect(url_for('main.login'))

    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Verify ownership
    cursor.execute("SELECT materials FROM courses WHERE id = %s AND instructor_id = %s", (course_id, user_id))
    course = cursor.fetchone()

    if not course:
        flash("Course not found or access denied.", "error")
        cursor.close()
        conn.close()
        return redirect(url_for('main.create_course'))

    try:
        # Delete course record
        cursor.execute("DELETE FROM courses WHERE id = %s", (course_id,))
        conn.commit()

        # Optionally delete uploaded file
        if course['materials']:
            file_path = os.path.join(current_app.static_folder, 'uploads', course['materials'])
            if os.path.exists(file_path):
                os.remove(file_path)

        flash("Course deleted successfully.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error deleting course: {str(e)}", "error")

    cursor.close()
    conn.close()
    return redirect(url_for('main.create_course'))




@main.route('/manage_course/<int:course_id>', methods=['GET'])
def manage_course(course_id):
    user_id = session.get('user_id')
    role = session.get('role')
    
    # Authentication check
    if not user_id or role != 'instructor':
        flash("Unauthorized access.", "error")
        return redirect(url_for('auth.login'))
    
    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Fetch course details
        cursor.execute("""
            SELECT id, title, description, materials, created_at
            FROM courses
            WHERE id = %s AND instructor_id = %s
        """, (course_id, user_id))
        course = cursor.fetchone()
        
        if not course:
            flash("Course not found or you don't have permission to access this course.", "error")
            return redirect(url_for('main.instructor_dashboard'))
        
        # Fetch all students in the system (automatically enrolled)
        cursor.execute("""
            SELECT id, full_name, email
            FROM users
            WHERE role = 'student'
            ORDER BY full_name ASC
        """)
        enrolled_students = cursor.fetchall()
        
        # Add progress information if available
        for student in enrolled_students:
            # Check if progress tracking is available
            cursor.execute("""
                SHOW COLUMNS FROM enrollments LIKE 'progress'
            """)
            progress_exists = cursor.fetchone()
            
            if progress_exists:
                # Try to get progress from enrollments table
                cursor.execute("""
                    SELECT progress
                    FROM enrollments
                    WHERE course_id = %s AND student_id = %s
                """, (course_id, student['id']))
                progress_data = cursor.fetchone()
                student['progress'] = progress_data['progress'] if progress_data and progress_data['progress'] else 0
            else:
                student['progress'] = 0
            
            # Check if enrollment_date is available
            cursor.execute("""
                SHOW COLUMNS FROM enrollments LIKE 'enrollment_date'
            """)
            enrollment_date_exists = cursor.fetchone()
            
            if enrollment_date_exists:
                # Try to get enrollment_date from enrollments table
                cursor.execute("""
                    SELECT enrollment_date
                    FROM enrollments
                    WHERE course_id = %s AND student_id = %s
                """, (course_id, student['id']))
                enrollment_data = cursor.fetchone()
                student['enrollment_date'] = enrollment_data['enrollment_date'] if enrollment_data and enrollment_data['enrollment_date'] else None
            else:
                student['enrollment_date'] = None
        
        # Fetch assignments
        cursor.execute("""
            SELECT id, title, description, due_date, 
                   CASE 
                     WHEN due_date < CURDATE() THEN 'overdue'
                     WHEN due_date > CURDATE() + INTERVAL 7 DAY THEN 'pending'
                     ELSE 'active'
                   END as status
            FROM assignments
            WHERE course_id = %s
            ORDER BY due_date ASC
        """, (course_id,))
        assignments = cursor.fetchall()
        
        # Calculate analytics data
        # Completion rate
        if enrolled_students:
            # Check if progress tracking is available
            cursor.execute("""
                SHOW COLUMNS FROM enrollments LIKE 'progress'
            """)
            progress_exists = cursor.fetchone()
            
            if progress_exists:
                cursor.execute("""
                    SELECT AVG(progress) as avg_progress
                    FROM enrollments
                    WHERE course_id = %s
                """, (course_id,))
                completion_rate_result = cursor.fetchone()
                completion_rate = round(completion_rate_result['avg_progress']) if completion_rate_result['avg_progress'] else 0
            else:
                completion_rate = 0
        else:
            completion_rate = 0
        
        # Average rating (if ratings exist in your system)
        cursor.execute("""
            SHOW TABLES LIKE 'course_ratings'
        """)
        ratings_table_exists = cursor.fetchone()
        
        if ratings_table_exists:
            cursor.execute("""
                SELECT AVG(rating) as avg_rating, COUNT(*) as rating_count
                FROM course_ratings
                WHERE course_id = %s
            """, (course_id,))
            rating_result = cursor.fetchone()
            average_rating = round(rating_result['avg_rating'], 1) if rating_result['avg_rating'] else 0
        else:
            average_rating = 0
        
        # Progress data for chart
        if enrolled_students:
            progress_labels = [student['full_name'] for student in enrolled_students]
            progress_data = [student['progress'] if student['progress'] else 0 for student in enrolled_students]
        else:
            progress_labels = []
            progress_data = []
        
        # Submission data for chart (if you have submission tracking)
        cursor.execute("""
            SHOW TABLES LIKE 'submissions'
        """)
        submissions_table_exists = cursor.fetchone()
        
        if submissions_table_exists:
            cursor.execute("""
                SELECT a.title, COUNT(s.id) as submission_count
                FROM assignments a
                LEFT JOIN submissions s ON a.id = s.assignment_id
                WHERE a.course_id = %s
                GROUP BY a.id, a.title
                ORDER BY a.due_date ASC
            """, (course_id,))
            submission_data = cursor.fetchall()
            
            submission_labels = [item['title'] for item in submission_data]
            submission_counts = [item['submission_count'] for item in submission_data]
        else:
            submission_labels = []
            submission_counts = []
        
    except Exception as e:
        current_app.logger.error(f"Error managing course {course_id}: {e}")
        flash("Error loading course data. Please try again.", "error")
        return redirect(url_for('main.instructor_dashboard'))
    
    finally:
        cursor.close()
        conn.close()
    
    return render_template('manage_course.html',
                           course=course,
                           enrolled_students=enrolled_students,
                           assignments=assignments,
                           completion_rate=completion_rate,
                           average_rating=average_rating,
                           progress_labels=progress_labels,
                           progress_data=progress_data,
                           submission_labels=submission_labels,
                           submission_data=submission_counts)


@main.route('/edit_course/<int:course_id>', methods=['POST'])
def edit_course(course_id):
    user_id = session.get('user_id')
    role = session.get('role')
    
    # Authentication check
    if not user_id or role != 'instructor':
        flash("Unauthorized access.", "error")
        return redirect(url_for('auth.login'))
    
    conn = current_app.get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verify ownership
        cursor.execute("SELECT instructor_id FROM courses WHERE id = %s", (course_id,))
        course = cursor.fetchone()
        
        if not course or course['instructor_id'] != user_id:
            flash("Course not found or you don't have permission to edit this course.", "error")
            return redirect(url_for('main.instructor_dashboard'))
        
        # Get form data
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        
        if not title or not description:
            flash("Title and description are required.", "error")
            return redirect(url_for('main.manage_course', course_id=course_id))
        
        # Handle file upload
        materials = None
        if 'materials' in request.files and request.files['materials'].filename != '':
            file = request.files['materials']
            filename = secure_filename(file.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            materials = filename
        
        # Update course
        if materials:
            cursor.execute("""
                UPDATE courses
                SET title = %s, description = %s, materials = %s
                WHERE id = %s AND instructor_id = %s
            """, (title, description, materials, course_id, user_id))
        else:
            cursor.execute("""
                UPDATE courses
                SET title = %s, description = %s
                WHERE id = %s AND instructor_id = %s
            """, (title, description, course_id, user_id))
        
        conn.commit()
        flash("Course updated successfully!", "success")
        
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error editing course {course_id}: {e}")
        flash("Error updating course. Please try again.", "error")
    
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('main.manage_course', course_id=course_id))



@main.route('/sync_enrollments/<int:course_id>', methods=['POST'])
def sync_enrollments(course_id):
    user_id = session.get('user_id')
    role = session.get('role')
    
    # Authentication check
    if not user_id or role != 'instructor':
        flash("Unauthorized access.", "error")
        return redirect(url_for('auth.login'))
    
    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)  # Ensure we get dictionaries
    
    try:
        # Verify ownership
        cursor.execute("SELECT instructor_id FROM courses WHERE id = %s", (course_id,))
        course = cursor.fetchone()
        
        if not course or course['instructor_id'] != user_id:
            flash("Course not found or you don't have permission to sync enrollments.", "error")
            return redirect(url_for('main.instructor_dashboard'))
        
        # Get all students in the system
        cursor.execute("""
            SELECT id FROM users WHERE role = 'student'
        """)
        all_students = cursor.fetchall()
        
        # Check if progress column exists
        cursor.execute("""
            SHOW COLUMNS FROM enrollments LIKE 'progress'
        """)
        progress_exists = cursor.fetchone()
        
        # Check if enrollment_date column exists
        cursor.execute("""
            SHOW COLUMNS FROM enrollments LIKE 'enrollment_date'
        """)
        enrollment_date_exists = cursor.fetchone()
        
        # Enroll all students who aren't already enrolled
        enrolled_count = 0
        for student in all_students:
            student_id = student['id']  # Access by key since we're using dictionary cursor
            
            # Check if student is already enrolled
            cursor.execute("""
                SELECT id FROM enrollments
                WHERE course_id = %s AND student_id = %s
            """, (course_id, student_id))
            if not cursor.fetchone():
                # Enroll student
                if progress_exists and enrollment_date_exists:
                    cursor.execute("""
                        INSERT INTO enrollments (course_id, student_id, enrollment_date, progress)
                        VALUES (%s, %s, CURDATE(), 0)
                    """, (course_id, student_id))
                elif progress_exists:
                    cursor.execute("""
                        INSERT INTO enrollments (course_id, student_id, progress)
                        VALUES (%s, %s, 0)
                    """, (course_id, student_id))
                elif enrollment_date_exists:
                    cursor.execute("""
                        INSERT INTO enrollments (course_id, student_id, enrollment_date)
                        VALUES (%s, %s, CURDATE())
                    """, (course_id, student_id))
                else:
                    cursor.execute("""
                        INSERT INTO enrollments (course_id, student_id)
                        VALUES (%s, %s)
                    """, (course_id, student_id))
                
                enrolled_count += 1
        
        conn.commit()
        flash(f"Successfully synced enrollments for {enrolled_count} students.", "success")
        
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error syncing enrollments for course {course_id}: {e}")
        current_app.logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        flash("Error syncing enrollments. Please try again.", "error")
    
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('main.manage_course', course_id=course_id))



@main.route('/remove_student/<int:course_id>', methods=['GET'])
def remove_student(course_id):
    user_id = session.get('user_id')
    role = session.get('role')
    
    # Authentication check
    if not user_id or role != 'instructor':
        flash("Unauthorized access.", "error")
        return redirect(url_for('auth.login'))
    
    student_id = request.args.get('student_id', '').strip()
    
    if not student_id:
        flash("Student ID is required.", "error")
        return redirect(url_for('main.manage_course', course_id=course_id))
    
    conn = current_app.get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verify ownership
        cursor.execute("SELECT instructor_id FROM courses WHERE id = %s", (course_id,))
        course = cursor.fetchone()
        
        if not course or course['instructor_id'] != user_id:
            flash("Course not found or you don't have permission to remove students.", "error")
            return redirect(url_for('main.instructor_dashboard'))
        
        # Remove student
        cursor.execute("""
            DELETE FROM enrollments
            WHERE course_id = %s AND student_id = %s
        """, (course_id, student_id))
        
        conn.commit()
        flash("Student removed from course successfully!", "success")
        
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error removing student from course {course_id}: {e}")
        flash("Error removing student. Please try again.", "error")
    
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('main.manage_course', course_id=course_id))

@main.route('/update_course_materials/<int:course_id>', methods=['POST'])
def update_course_materials(course_id):
    user_id = session.get('user_id')
    role = session.get('role')
    
    # Authentication check
    if not user_id or role != 'instructor':
        flash("Unauthorized access.", "error")
        return redirect(url_for('auth.login'))
    
    conn = current_app.get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verify ownership
        cursor.execute("SELECT instructor_id FROM courses WHERE id = %s", (course_id,))
        course = cursor.fetchone()
        
        if not course or course['instructor_id'] != user_id:
            flash("Course not found or you don't have permission to update course materials.", "error")
            return redirect(url_for('main.instructor_dashboard'))
        
        # Handle file upload
        if 'materials' in request.files and request.files['materials'].filename != '':
            file = request.files['materials']
            filename = secure_filename(file.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Update course materials
            cursor.execute("""
                UPDATE courses
                SET materials = %s
                WHERE id = %s AND instructor_id = %s
            """, (filename, course_id, user_id))
            
            conn.commit()
            flash("Course materials updated successfully!", "success")
        else:
            flash("Please select a file to upload.", "error")
        
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error updating course materials for course {course_id}: {e}")
        flash("Error updating course materials. Please try again.", "error")
    
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('main.manage_course', course_id=course_id))


@main.route('/instructor/monitor_discussions')
def monitor_discussions():
    if 'user_id' not in session or session.get('role') != 'instructor':
        return redirect(url_for('main.login'))

    # You can add logic to fetch discussion data here
    return render_template('monitor_discussions.html')


@main.route('/instructor/peer_analytics')
def peer_analytics():
    if 'user_id' not in session or session.get('role') != 'instructor':
        return redirect(url_for('main.login'))

    instructor_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Total feedback given to instructor
    cursor.execute("""
        SELECT COUNT(*) AS total_feedback
        FROM feedback
        WHERE instructor_id = %s
    """, (instructor_id,))
    total_feedback = cursor.fetchone()['total_feedback'] or 0

    # Average feedback per student
    cursor.execute("""
        SELECT COUNT(DISTINCT giver_id) AS student_count
        FROM feedback
        WHERE instructor_id = %s
    """, (instructor_id,))
    student_count = cursor.fetchone()['student_count'] or 0
    avg_feedback_per_student = round(total_feedback / student_count, 2) if student_count else 0

    # Active collaborations (combined from feedback and peer_feedback)
    cursor.execute("""
        SELECT COUNT(*) AS active_collaborations
        FROM (
            SELECT giver_id AS user_id
            FROM feedback
            WHERE instructor_id = %s
            GROUP BY giver_id
            HAVING COUNT(DISTINCT student_id) > 1

            UNION

            SELECT reviewer_id AS user_id
            FROM peer_feedback
            GROUP BY reviewer_id
            HAVING COUNT(DISTINCT reviewee_id) > 1
        ) AS collab
    """, (instructor_id,))
    active_collaborations = cursor.fetchone()['active_collaborations'] or 0

    # Most engaged student
    cursor.execute("""
        SELECT u.full_name, COUNT(*) AS feedback_count
        FROM feedback f
        JOIN users u ON f.giver_id = u.id
        WHERE f.instructor_id = %s
        GROUP BY f.giver_id
        ORDER BY feedback_count DESC
        LIMIT 1
    """, (instructor_id,))
    top_student_row = cursor.fetchone()
    top_student = top_student_row['full_name'] if top_student_row else 'N/A'

    # Feedback activity (last 7 days)
    today = datetime.today()
    start_date = today - timedelta(days=6)
    cursor.execute("""
        SELECT DATE(created_at) AS date, COUNT(*) AS count
        FROM feedback
        WHERE instructor_id = %s AND created_at BETWEEN %s AND %s
        GROUP BY DATE(created_at)
        ORDER BY DATE(created_at)
    """, (instructor_id, start_date, today))
    feedback_data = cursor.fetchall()

    feedback_labels = [(start_date + timedelta(days=i)).strftime('%b %d') for i in range(7)]
    feedback_counts = {row['date'].strftime('%b %d'): row['count'] for row in feedback_data}
    feedback_values = [feedback_counts.get(label, 0) for label in feedback_labels]

    # Top collaborators
    cursor.execute("""
        SELECT u.full_name, COUNT(*) AS count
        FROM feedback f
        JOIN users u ON f.giver_id = u.id
        WHERE f.instructor_id = %s
        GROUP BY f.giver_id
        ORDER BY count DESC
        LIMIT 5
    """, (instructor_id,))
    top_collaborators = cursor.fetchall()
    collaborator_labels = [row['full_name'] for row in top_collaborators]
    collaborator_values = [row['count'] for row in top_collaborators]

    # Total peer feedback involving instructor's assignments
    cursor.execute("""
        SELECT COUNT(*) AS total_peer_feedback
        FROM peer_feedback
        WHERE assignment_id IN (
            SELECT id FROM assignments WHERE instructor_id = %s
        )
    """, (instructor_id,))
    peer_feedback_row = cursor.fetchone()
    total_peer_feedback = peer_feedback_row['total_peer_feedback'] if peer_feedback_row else 0

    cursor.close()
    conn.close()

    return render_template('peer_analytics.html',
                           avg_feedback_per_student=avg_feedback_per_student,
                           active_collaborations=active_collaborations,
                           top_student=top_student,
                           total_feedback=total_feedback,
                           total_peer_feedback=total_peer_feedback,
                           feedback_labels=feedback_labels,
                           feedback_values=feedback_values,
                           collaborator_labels=collaborator_labels,
                           collaborator_values=collaborator_values)



@main.route('/admin_dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        flash('Access denied. Only administrators can view this dashboard.', 'danger')
        return redirect(url_for('main.login'))
    current_app.log_action(action='view_admin_dashboard', user_id=session['user_id'])
    return render_template('admin_dashboard.html')


@main.route('/user_management')
def user_management():
    if session.get('role') != 'admin':
        flash('Access denied. Only administrators can manage users.', 'danger')
        return redirect(url_for('main.login'))

    conn = current_app.get_db_connection()
    if not conn:
        flash('Database connection error.', 'danger')
        return redirect(url_for('main.admin_dashboard'))

    cursor = conn.cursor(dictionary=True)
    try:
        # Fetch user details including full_name
        cursor.execute("""
            SELECT id, full_name AS name, email, role, status, last_seen, profile_image 
            FROM users 
            ORDER BY full_name ASC
        """)
        users = cursor.fetchall()
    except Exception as e:
        current_app.logger.error(f"Error fetching users: {e}")
        users = []
    finally:
        cursor.close()
        conn.close()

    current_app.log_action(action='view_user_management', user_id=session['user_id'])
    return render_template('user_management.html', users=users)



from werkzeug.security import generate_password_hash

@main.route('/add_user', methods=['POST'])
def add_user():
    if session.get('role') != 'admin':
        return jsonify({"message": "Access denied. Only administrators can add users.", "status": "error"}), 403

    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    role = data.get('role')
    status = data.get('status')
    password = data.get('password')

    if not all([name, email, role, status, password]):
        return jsonify({"message": "All fields are required.", "status": "error"}), 400

    # Hash the password before storing it
    hashed_password = generate_password_hash(password)

    conn = current_app.get_db_connection()
    cursor = conn.cursor()
    try:
        # Check for duplicate email
        cursor.execute("SELECT COUNT(*) FROM users WHERE email = %s", (email,))
        if cursor.fetchone()[0] > 0:
            return jsonify({"message": "Email already exists.", "status": "error"}), 400

        # Insert new user
        cursor.execute("""
            INSERT INTO users (full_name, email, role, status, password_hash)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, email, role, status, hashed_password))
        conn.commit()
        return jsonify({"message": "User added successfully.", "status": "success"}), 200
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error adding user: {e}")
        return jsonify({"message": "Failed to add user.", "status": "error"}), 500
    finally:
        cursor.close()
        conn.close()

@main.route('/edit_user/<int:user_id>', methods=['PUT'])
def edit_user(user_id):
    if session.get('role') != 'admin':
        return jsonify({"message": "Access denied. Only administrators can edit users.", "status": "error"}), 403

    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    role = data.get('role')
    status = data.get('status')

    if not all([name, email, role, status]):
        return jsonify({"message": "All fields are required.", "status": "error"}), 400

    conn = current_app.get_db_connection()
    if not conn:
        return jsonify({"message": "Database connection error.", "status": "error"}), 500

    cursor = conn.cursor()
    try:
        # Update user details
        cursor.execute("""
            UPDATE users
            SET full_name = %s, email = %s, role = %s, status = %s
            WHERE id = %s
        """, (name, email, role, status, user_id))
        conn.commit()
        return jsonify({"message": "User updated successfully.", "status": "success"}), 200
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error editing user: {e}")
        return jsonify({"message": "Failed to update user.", "status": "error"}), 500
    finally:
        cursor.close()
        conn.close()


@main.route('/audit_logs', methods=['GET', 'POST'])
def audit_logs():
    if session.get('role') != 'admin':
        flash('Access denied. Only administrators can manage audit logs.', 'danger')
        return redirect(url_for('main.login'))

    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Handle clearing all logs
    if request.method == 'POST' and request.form.get('clear_logs') == 'true':
        try:
            cursor.execute("DELETE FROM audit_logs")
            conn.commit()
            flash('All logs cleared successfully.', 'success')
        except Exception as e:
            conn.rollback()
            current_app.logger.error(f"Error clearing logs: {e}")
            flash('Failed to clear logs.', 'danger')

    # Filters for GET request
    search_user = request.args.get('search_user', '').strip()
    action_type = request.args.get('action_type', '').strip()
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    query = """
        SELECT a.*, u.full_name AS user_name, u.email, u.role
        FROM audit_logs a
        LEFT JOIN users u ON a.user_id = u.id
        WHERE 1=1
    """
    filters = []
    params = []

    if search_user:
        filters.append("(u.full_name LIKE %s OR u.email LIKE %s)")
        params += [f"%{search_user}%", f"%{search_user}%"]

    if action_type:
        filters.append("a.action = %s")
        params.append(action_type)

    if date_from:
        filters.append("DATE(a.timestamp) >= %s")
        params.append(date_from)

    if date_to:
        filters.append("DATE(a.timestamp) <= %s")
        params.append(date_to)

    if filters:
        query += " AND " + " AND ".join(filters)

    query += " ORDER BY a.timestamp DESC"

    cursor.execute(query, tuple(params))
    logs = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('audit_logs.html', logs=logs,
                           search_user=search_user, action_type=action_type,
                           date_from=date_from, date_to=date_to)



@main.route('/delete_log/<int:log_id>', methods=['POST'])
def delete_log(log_id):
    if session.get('role') != 'admin':
        flash('Access denied. Only administrators can delete logs.', 'danger')
        return redirect(url_for('main.audit_logs'))

    conn = current_app.get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM audit_logs WHERE id = %s", (log_id,))
        conn.commit()
        flash('Log deleted successfully.', 'success')
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error deleting log: {e}")
        flash('Failed to delete log.', 'danger')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('main.audit_logs'))


@main.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if session.get('role') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.login'))

    # Prevent admin from deleting themselves
    if session.get('user_id') == user_id:
        flash("You cannot delete your own admin account.", "danger")
        return redirect(url_for('main.user_management'))

    conn = current_app.get_db_connection()
    if not conn:
        flash('Database connection error.', 'danger')
        return redirect(url_for('main.user_management'))

    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        flash("User deleted.", "info")
        current_app.log_action(action=f"Deleted user with ID {user_id}", user_id=session['user_id'])
    except Exception as e:
        conn.rollback()
        flash(f"Error deleting user: {e}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('main.user_management'))


   #====== Admin Codes Management =========
@main.route('/admin_codes', methods=['GET', 'POST'])
def admin_codes():
    
    conn = current_app.get_db_connection()
    if not conn:
        flash('Database connection error.', 'danger')
        return redirect(url_for('main.admin_dashboard'))

    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        try:
            # Generate a new admin code
            new_code = ''.join(random.choices(string.digits, k=6))
            cursor.execute("INSERT INTO admin_codes (code, is_used) VALUES (%s, %s)", (new_code, False))
            conn.commit()
            flash(f"New admin code generated: {new_code}", 'success')
        except Exception as e:
            conn.rollback()
            current_app.logger.error(f"Error generating admin code: {e}")
            flash('Failed to generate admin code.', 'danger')

    # Fetch unused admin codes
    cursor.execute("SELECT code FROM admin_codes WHERE is_used = FALSE")
    unused_codes = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin_codes.html', codes=unused_codes)

# Role-based Dashboard Redirect
@main.route('/dashboard')
def dashboard():
    if 'role' not in session:
        return redirect(url_for('main.login'))
    return redirect(url_for(f"main.{session['role']}_dashboard"))


@main.route('/feedbacks')
def feedbacks():
    # Placeholder for feedbacks logic
    current_app.log_action(action='view_feedbacks', user_id=session.get('user_id'))
    return render_template('feedbacks.html')


@main.route('/review_feedback')
def review_feedback():
    if session.get('role') != 'instructor':
        flash('Access denied. Only instructors can review feedback.', 'danger')
        return redirect(url_for('main.login'))

    conn = current_app.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT f.created_at, f.assignment_title, f.reviewer_name, f.reviewee_name, f.score, f.comments
            FROM feedbacks f
            ORDER BY f.created_at DESC
        """)
        feedbacks = cursor.fetchall()
    except Exception as e:
        current_app.logger.error(f"Error fetching feedbacks: {e}")
        feedbacks = []
    finally:
        cursor.close()
        conn.close()

    return render_template('review_feedback.html', feedbacks=feedbacks)

# --- COURSES ---
@main.route('/courses')
def student_courses():
    student_id = session.get('user_id')
    if not student_id:
        flash("Please log in to view your courses.", "warning")
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # --- Fetch enrolled courses ---
        cursor.execute("""
            SELECT c.id, c.title, c.description, c.created_at,
                   u.full_name AS instructor_name, u.avatar_url AS instructor_avatar
            FROM enrollments e
            JOIN courses c ON e.course_id = c.id
            LEFT JOIN users u ON c.instructor_id = u.id
            WHERE e.student_id = %s AND c.is_deleted = 0 AND c.is_active = 1
            ORDER BY c.created_at DESC
        """, (student_id,))
        courses_raw = cursor.fetchall()

        courses = []
        for course in courses_raw:
            course_id = course['id']

            # --- Fetch materials ---
            cursor.execute("""
                SELECT id, title AS name
                FROM course_materials
                WHERE course_id = %s
                ORDER BY uploaded_at DESC
            """, (course_id,))
            materials = cursor.fetchall()

            # --- Progress calculation ---
            cursor.execute("""
                SELECT COUNT(*) AS total FROM course_materials WHERE course_id = %s
            """, (course_id,))
            total_materials = cursor.fetchone()['total']

            cursor.execute("""
                SELECT COUNT(*) AS completed
                FROM student_material_progress
                WHERE student_id = %s AND material_id IN (
                    SELECT id FROM course_materials WHERE course_id = %s
                ) AND is_completed = 1
            """, (student_id, course_id))
            completed_materials = cursor.fetchone()['completed']

            cursor.execute("""
                SELECT COUNT(*) AS total FROM assignments WHERE course_id = %s
            """, (course_id,))
            total_assignments = cursor.fetchone()['total']

            cursor.execute("""
                SELECT COUNT(*) AS completed
                FROM student_assignments
                WHERE student_id = %s AND assignment_id IN (
                    SELECT id FROM assignments WHERE course_id = %s
                ) AND status = 'completed'
            """, (student_id, course_id))
            completed_assignments = cursor.fetchone()['completed']

            total_tasks = total_materials + total_assignments
            completed_tasks = completed_materials + completed_assignments
            progress = int((completed_tasks / total_tasks) * 100) if total_tasks else 0

            # --- Assemble course object ---
            course.update({
                'materials': materials,
                'progress': progress,
                'instructor_avatar': course.get('instructor_avatar') or '/static/img/default-avatar.png'
            })
            courses.append(course)

        # --- Student name for greeting ---
        cursor.execute("SELECT first_name FROM users WHERE id = %s", (student_id,))
        student_name = cursor.fetchone()['first_name']

    finally:
        cursor.close()
        conn.close()

    return render_template('courses.html',
                           courses=courses,
                           student_name=student_name,
                           current_year=datetime.utcnow().year)



@main.route('/course/<int:course_id>')
def course_detail(course_id):
    student_id = session.get('user_id')
    if not student_id:
        flash("Please log in to access course details.", "warning")
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # --- Course Info ---
    cursor.execute("""
        SELECT c.id AS course_id, c.title AS course_title, c.description AS course_description,
               u.full_name AS instructor_name
        FROM courses c
        LEFT JOIN users u ON c.instructor_id = u.id
        WHERE c.id = %s
    """, (course_id,))
    course = cursor.fetchone()
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for('main.student_dashboard'))

    # --- Materials ---
    try:
        cursor.execute("""
            SELECT cm.id, cm.filename AS title, cm.description, cm.filepath AS file_path, cm.uploaded_at,
                   IF(smp.is_completed IS NULL, 0, smp.is_completed) AS is_completed
            FROM course_materials cm
            LEFT JOIN student_material_progress smp ON cm.id = smp.material_id AND smp.student_id = %s
            WHERE cm.course_id = %s
            ORDER BY cm.uploaded_at DESC
        """, (student_id, course_id))
    except:
        cursor.execute("""
            SELECT cm.id, cm.filename AS title, cm.description, cm.filepath AS file_path, cm.uploaded_at
            FROM course_materials cm
            WHERE cm.course_id = %s
            ORDER BY cm.uploaded_at DESC
        """, (course_id,))
    materials = cursor.fetchall()
    for m in materials:
        m['is_completed'] = m.get('is_completed', 0)

    # --- Assignments ---
    cursor.execute("""
        SELECT a.id, a.title, a.description, a.due_date,
               IF(sa.id IS NULL, 0, 1) AS is_submitted
        FROM assignments a
        LEFT JOIN student_assignments sa ON a.id = sa.assignment_id AND sa.student_id = %s AND sa.status = 'completed'
        WHERE a.course_id = %s
        ORDER BY a.due_date ASC
    """, (student_id, course_id))
    assignments = cursor.fetchall()

    # --- Forums ---
    cursor.execute("""
        SELECT f.id, f.title, f.description, f.created_at, f.rating
        FROM forums f
        WHERE f.course_id = %s AND f.is_deleted = 0
        ORDER BY f.created_at DESC
    """, (course_id,))
    forums = cursor.fetchall()

    # --- Progress Calculation ---
    total_materials = len(materials)
    completed_materials = sum(1 for m in materials if m['is_completed'])

    total_assignments = len(assignments)
    completed_assignments = sum(1 for a in assignments if a['is_submitted'])

    total_tasks = total_materials + total_assignments
    completed_tasks = completed_materials + completed_assignments
    progress = int((completed_tasks / total_tasks) * 100) if total_tasks else 0

    # --- Enrolled Students Count ---
    cursor.execute("""
        SELECT COUNT(*) AS enrolled_count
        FROM enrollments
        WHERE course_id = %s
    """, (course_id,))
    enrolled_count = cursor.fetchone()['enrolled_count']

    # --- Unread Notifications (optional) ---
    cursor.execute("""
        SELECT COUNT(*) AS unread_notifications
        FROM notifications
        WHERE user_id = %s AND is_read = 0
    """, (student_id,))
    unread_notifications = cursor.fetchone()['unread_notifications']

    cursor.close()
    conn.close()

    return render_template('course_detail.html',
                           course=course,
                           materials=materials,
                           assignments=assignments,
                           forums=forums,
                           progress=progress,
                           materials_completed=completed_materials,
                           assignments_completed=completed_assignments,
                           enrolled_count=enrolled_count,
                           unread_notifications=unread_notifications)




@main.route('/upload_assignment', methods=['POST'])
def upload_assignment():
    if session.get('role') != 'instructor':
        flash('Unauthorized access. Only instructors can upload assignments.', 'danger')
        return redirect(url_for('main.login'))

    title = request.form['title']
    course_id = request.form['course_id']
    description = request.form['description']
    due_date = request.form['due_date']
    status = request.form['status']

    conn = current_app.get_db_connection()
    if not conn:
        flash('Database connection error.', 'danger')
        return redirect(url_for('main.manage_assignments'))

    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO assignments (title, course_id, description, due_date, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (title, course_id, description, due_date, status))
        conn.commit()
        flash('Assignment uploaded successfully!', 'success')
        current_app.log_action(action='upload_assignment', user_id=session['user_id'])
    except Exception as e:
        print("Assignment upload error:", e)
        flash('Assignment upload failed.', 'danger')
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('main.manage_assignments'))



@main.route('/settings', methods=['GET', 'POST'])
def system_settings():
    if session.get('role') != 'admin':
        flash('Unauthorized access. Only administrators can change system settings.', 'danger')
        return redirect(url_for('main.login'))

    conn = current_app.get_db_connection()
    if not conn:
        flash('Database connection error.', 'danger')
        return redirect(url_for('main.admin_dashboard'))

    cursor = conn.cursor()

    if request.method == 'POST':
        try:
            for key in request.form:
                value = request.form[key]
                cursor.execute("""
                    INSERT INTO system_settings (setting_key, setting_value)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE setting_value = %s
                """, (key, value, value))
            conn.commit()
            flash('Settings updated successfully.', 'success')
            current_app.log_action(action='update_system_settings', user_id=session['user_id'])
        except Exception as e:
            conn.rollback()
            flash(f'Failed to update settings: {str(e)}', 'danger')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('main.system_settings'))

    cursor.execute("SELECT setting_key, setting_value FROM system_settings")
    settings_list = cursor.fetchall()
    # Convert list of tuples to dictionary for easier access in template
    settings = {row[0]: row[1] for row in settings_list}
    cursor.close()
    conn.close()
    current_app.log_action(action='view_system_settings', user_id=session['user_id'])
    return render_template('system_settings.html', settings=settings, now=datetime.utcnow())


@main.route('/generate_admin_code_route')
def generate_admin_code_route():
    if session.get('role') != 'admin':
        return make_response("<h3>Unauthorized</h3><p>Only admins can generate codes.</p>", 403)

    code = ''.join(random.choices(string.digits, k=6))
    conn = current_app.get_db_connection()
    if not conn:
        return make_response("<p>Database connection error.</p>", 500)
    cursor = conn.cursor()

    try:
        cursor.execute("INSERT INTO admin_codes (code) VALUES (%s)", (code,))
        conn.commit()
        current_app.log_action(action='generate_single_admin_code', user_id=session['user_id'])
        return make_response(f"<h3>New admin code generated: <strong>{code}</strong></h3>", 200)
    except Exception as e:
        conn.rollback()
        return make_response(f"<p>Failed to generate code: {str(e)}</p>", 500)
    finally:
        cursor.close()
        conn.close()


def send_credentials(email, password):
    
    try:
        msg = MIMEText(f"Your account has been created.\n\nEmail: {email}\nPassword: {password}\n\nPlease change your password upon first login.")
        msg['Subject'] = "Your CollaboLearn Login Details"
        msg['From'] = current_app.config.get('MAIL_USERNAME', "your_email@gmail.com") # Use config for flexibility
        msg['To'] = email

        with smtplib.SMTP_SSL(current_app.config.get('MAIL_SERVER', "smtp.gmail.com"),
                              current_app.config.get('MAIL_PORT', 465)) as server:
            server.login(current_app.config.get('MAIL_USERNAME', "your_email@gmail.com"),
                         current_app.config.get('MAIL_PASSWORD', "your_app_password")) # Use app password or secure method
            server.send_message(msg)
        print(f"Credentials sent to {email}")
    except Exception as e:
        print(f"Failed to send email to {email}: {e}")
        # In a real app, you might want to log this error more formally


@main.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('reset_email')
        if not email:
            flash("Please enter your email address.", "warning")
        else:
            
            flash(f"If {email} is registered, a password reset link has been sent to your email.", "info")
            current_app.log_action(action='forgot_password_request', user_id=None) # No user_id yet
        return redirect(url_for('main.login'))
    return render_template('forgot_password.html')


@main.route('/analytics')
def analytics():
    if session.get('role') != 'admin':
        flash('Access denied. Only administrators can view analytics.', 'danger')
        return redirect(url_for('main.login'))

    conn = current_app.get_db_connection()
    if not conn:
        flash('Database connection error.', 'danger')
        return render_template('admin_analytics_dashboard.html', analytics_data={})

    cursor = conn.cursor(dictionary=True)

    # Total users by role
    cursor.execute("SELECT role, COUNT(*) as count FROM users GROUP BY role")
    user_roles_data = {row['role']: row['count'] for row in cursor.fetchall()}

    # Total courses
    cursor.execute("SELECT COUNT(*) as total_courses FROM courses")
    total_courses = cursor.fetchone()['total_courses']

    # Total enrollments
    cursor.execute("SELECT COUNT(*) as total_enrollments FROM enrollments")
    total_enrollments = cursor.fetchone()['total_enrollments']

    # Active users today
    cursor.execute("""
        SELECT COUNT(DISTINCT user_id) AS active_users
        FROM activity_log
        WHERE DATE(timestamp) = CURDATE()
    """)
    active_users = cursor.fetchone()['active_users']

    # Total submissions
    cursor.execute("SELECT COUNT(*) AS total_submissions FROM submissions")
    total_submissions = cursor.fetchone()['total_submissions']

    # Average feedback rating
    cursor.execute("SELECT ROUND(AVG(rating), 2) AS avg_feedback FROM feedback")
    avg_feedback = cursor.fetchone()['avg_feedback'] or 0.0

    # System load (example: count of active sessions)
    cursor.execute("SELECT COUNT(*) AS system_load FROM sessions WHERE active = 1")
    system_load = cursor.fetchone()['system_load']

    # Chart data: user engagement (daily counts for past 7 days)
    cursor.execute("""
        SELECT DATE(timestamp) AS day, COUNT(*) AS count
        FROM activity_log
        WHERE timestamp >= CURDATE() - INTERVAL 7 DAY
        GROUP BY day
        ORDER BY day ASC
    """)
    user_engagement = cursor.fetchall()

    # Chart data: feedback sentiment over time
    cursor.execute("""
        SELECT DATE(created_at) AS day, AVG(rating) AS avg_rating
        FROM feedback
        WHERE created_at >= CURDATE() - INTERVAL 30 DAY
        GROUP BY day
        ORDER BY day ASC
    """)
    feedback_sentiment = cursor.fetchall()

    # Chart data: most visited pages
    cursor.execute("""
        SELECT page, COUNT(*) AS visits
        FROM page_visits
        GROUP BY page
        ORDER BY visits DESC
        LIMIT 5
    """)
    page_visits = cursor.fetchall()

    # Chart data: new users weekly
    cursor.execute("""
        SELECT WEEK(created_at) AS week, COUNT(*) AS new_users
        FROM users
        WHERE created_at >= CURDATE() - INTERVAL 8 WEEK
        GROUP BY week
        ORDER BY week ASC
    """)
    user_growth = cursor.fetchall()

    cursor.close()
    conn.close()

    analytics_data = {
        'user_roles': user_roles_data,
        'total_courses': total_courses,
        'total_enrollments': total_enrollments,
        'active_users': active_users,
        'total_submissions': total_submissions,
        'avg_feedback': avg_feedback,
        'system_load': system_load,
        'charts': {
            'user_engagement': user_engagement,
            'feedback_sentiment': feedback_sentiment,
            'page_visits': page_visits,
            'user_growth': user_growth
        }
    }

    current_app.log_action(action='view_analytics', user_id=session['user_id'])
    return render_template('analytics.html', analytics_data=analytics_data)






@main.route('/chat')
def chat():
    # 1. Check if the user is logged in and is a student or any valid role
    user_id = session.get('user_id')
    user_role = session.get('role')

    if not user_id:
        flash('Please log in to access the chat.', 'warning')
        return redirect(url_for('main.login'))
    
    # 2. Establish a database connection
    conn = current_app.get_db_connection()
    if not conn:
        flash("Database connection error.", "danger")
        return redirect(url_for('main.login'))

    try:
        with conn.cursor(dictionary=True) as cursor:
            # ✅ Fetch the current user's profile info
            cursor.execute("""
                SELECT id, full_name, profile_image
                FROM users
                WHERE id = %s
            """, (user_id,))
            current_user = cursor.fetchone()

            if not current_user:
                flash('User profile not found. Please log in again.', 'warning')
                return redirect(url_for('main.login'))

            # ✅ Fetch recent messages from the database
            cursor.execute("""
                SELECT m.id, m.message_text, m.created_at, u.full_name, u.profile_image
                FROM messages m
                JOIN users u ON m.user_id = u.id
                ORDER BY m.created_at ASC
                LIMIT 50  # Limit to the last 50 messages
            """)
            messages = cursor.fetchall()
        
        # 3. Log the action and render the template with data
        current_app.log_action(action='view_chat', user_id=user_id)
        
        return render_template(
            'chat.html',
            current_user=current_user,
            messages=messages
        )

    except Exception as ex:
        current_app.logger.exception("Error loading chat page for user_id: %s", user_id)
        flash("An unexpected error occurred. Please try again.", "danger")
        return redirect(url_for('main.login'))
    finally:
        conn.close()



@main.route('/goals', methods=['GET'])
def goals():
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in to view your goals.', 'warning')
        return redirect(url_for('main.login'))

    conn = current_app.get_db_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT id, title, description, progress, deadline, status, difficulty, reward_points
                FROM goals
                WHERE user_id = %s
                ORDER BY deadline ASC
            """, (user_id,))
            goals = cursor.fetchall()

        return render_template('goals.html', goals=goals)

    except Exception as e:
        current_app.logger.error(f"Error loading goals: {e}")
        flash("Could not load goals.", "danger")
        return redirect(url_for('main.dashboard'))


@main.route('/create_goal', methods=['POST'])
def create_goal():
    user_id = session.get('user_id')
    if not user_id:
        flash('Session expired. Please log in again.', 'warning')
        return redirect(url_for('main.login'))

    title = request.form.get('title')
    description = request.form.get('description')
    deadline = request.form.get('deadline')
    difficulty = request.form.get('difficulty')

    reward_points = {
        'easy': 10,
        'medium': 25,
        'hard': 50
    }.get(difficulty, 20)

    conn = current_app.get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO goals (user_id, title, description, deadline, difficulty, reward_points)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, title, description, deadline, difficulty, reward_points))
            conn.commit()

        flash('Goal created successfully!', 'success')
        return redirect(url_for('main.goals'))

    except Exception as e:
        current_app.logger.error(f"Error creating goal: {e}")
        flash("Failed to create goal.", "danger")
        return redirect(url_for('main.goals'))


@main.route('/send_invite', methods=['POST'])
def send_invite():
    """
    API endpoint to send a collaboration invite.

    This route handles a POST request from the client-side to create
    a new collaboration invite in the database. It validates the user,
    checks for the existence of the peer, and ensures the user is not
    inviting themselves.
    """
    # 1. User Authentication Check
    user_id = session.get('user_id')
    if not user_id:
        # Return a JSON error response for an unauthorized request
        return jsonify({'success': False, 'message': 'Authentication required.'}), 401
    
    # 2. Data Validation from Request
    data = request.get_json()
    peer_id = data.get('peer_id')

    if not peer_id:
        # Return a JSON error for a bad request (missing data)
        return jsonify({'success': False, 'message': 'Peer ID is required.'}), 400

    if user_id == int(peer_id):
        # A user cannot send an invite to themselves
        return jsonify({'success': False, 'message': 'You cannot send an invite to yourself.'}), 400

    # 3. Establish Database Connection
    conn = current_app.get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "Database connection error."}), 500

    try:
        with conn.cursor(dictionary=True) as cursor:
            # 4. Validate that the peer_id exists in the database
            cursor.execute("SELECT id FROM users WHERE id = %s", (peer_id,))
            peer = cursor.fetchone()

            if not peer:
                return jsonify({'success': False, 'message': 'Peer not found.'}), 404

            # 5. Check if an invite already exists to avoid duplicates
            cursor.execute("""
                SELECT id FROM collaboration_invites
                WHERE (sender_id = %s AND receiver_id = %s) 
                OR (sender_id = %s AND receiver_id = %s)
                AND status = 'pending'
            """, (user_id, peer_id, peer_id, user_id))
            existing_invite = cursor.fetchone()
            
            if existing_invite:
                return jsonify({'success': False, 'message': 'An active invite with this user already exists.'}), 409

            # 6. Insert the new collaboration invite into the database
            cursor.execute("""
                INSERT INTO collaboration_invites (sender_id, receiver_id, status, created_at)
                VALUES (%s, %s, 'pending', NOW())
            """, (user_id, peer_id))
            conn.commit()

        # 7. Success Response
        return jsonify({'success': True, 'message': f'Invite sent successfully to peer ID: {peer_id}.'})

    except Exception as ex:
        # 8. Error Handling
        current_app.logger.exception("Error sending invite from user %s to peer %s.", user_id, peer_id)
        conn.rollback() # Rollback the transaction on error
        return jsonify({"success": False, "message": "An unexpected server error occurred."}), 500

    finally:
        # 9. Close Database Connection
        conn.close()


# 📥 Peer Feedback Page
@main.route('/peer_feedback') 
def peer_feedback():
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to access the feedback board.")
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 🔶 Public suggestions (students only)
    cursor.execute("""
        SELECT f.id, f.suggestion_text, f.feedback_text, f.timestamp, f.likes,
               u.full_name AS giver_name
        FROM feedback f
        JOIN users u ON f.giver_id = u.id
        WHERE u.role = 'student'
        ORDER BY f.timestamp DESC
    """)
    suggestions = cursor.fetchall()

    # 🔷 Comments per suggestion (students only)
    for s in suggestions:
        cursor.execute("""
            SELECT c.comment_text AS text,
                   u.full_name AS commenter_name,
                   c.timestamp
            FROM feedback_comments c
            JOIN users u ON c.commenter_id = u.id
            WHERE c.feedback_id = %s
              AND u.role = 'student'
            ORDER BY c.timestamp ASC
        """, (s['id'],))
        s['comments'] = cursor.fetchall()

    # 🟢 Active students (last 10 min)
    cursor.execute("""
        SELECT id, full_name AS name, avatar_url,
               CASE WHEN last_active >= %s THEN 'active' ELSE 'inactive' END AS status
        FROM users
        WHERE id != %s
          AND role = 'student'
        ORDER BY full_name ASC
    """, (datetime.utcnow() - timedelta(minutes=10), user_id))
    active_users = cursor.fetchall()

    # ✨ Recommended peers (same courses)
    cursor.execute("""
        SELECT DISTINCT u.id, u.full_name AS name, u.avatar_url, u.last_active
        FROM users u
        JOIN enrollments e ON u.id = e.user_id
        WHERE e.course_id IN (
            SELECT course_id FROM enrollments WHERE user_id = %s
        )
          AND u.id != %s
          AND u.role = 'student'
        ORDER BY u.last_active DESC
        LIMIT 10
    """, (user_id, user_id))
    recommended_peers = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('peer_feedback.html',
                           suggestions=suggestions,
                           active_users=active_users,
                           recommended_peers=recommended_peers)


# ❤️ Like a suggestion
@main.route('/like_feedback/<int:feedback_id>', methods=['POST'])
def like_feedback(feedback_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE feedback SET likes = likes + 1 WHERE id = %s", (feedback_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True, 'feedback_id': feedback_id})


# 💬 Post a comment
@main.route('/comment_feedback/<int:feedback_id>', methods=['POST'])
def comment_feedback(feedback_id):
    commenter_id = session.get('user_id')
    comment_text = request.form.get('comment')

    if not commenter_id or not comment_text:
        flash("You must be logged in and provide a comment.")
        return redirect(url_for('main.peer_feedback'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO feedback_comments (feedback_id, commenter_id, comment_text, timestamp)
        VALUES (%s, %s, %s, %s)
    """, (feedback_id, commenter_id, comment_text, datetime.utcnow()))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('main.peer_feedback'))


# 📥 Post a suggestion
@main.route('/post_suggestion', methods=['POST'])
def post_suggestion():
    giver_id = session.get('user_id')
    suggestion_text = request.form.get('suggestion')

    if not giver_id or not suggestion_text:
        flash("You must be logged in and provide a suggestion.")
        return redirect(url_for('main.peer_feedback'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO feedback (giver_id, suggestion_text, feedback_text, timestamp, likes)
        VALUES (%s, %s, %s, %s, 0)
    """, (giver_id, suggestion_text, "", datetime.utcnow()))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('main.peer_feedback'))


# 🧑‍🤝‍🧑 Fetch peer chat messages
@main.route('/peer_chat/<int:peer_id>')
def peer_chat(peer_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 403

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT m.id, m.sender_id, m.receiver_id, m.message_text AS content, m.timestamp,
               u.full_name AS sender_name
        FROM peer_messages m
        JOIN users u ON m.sender_id = u.id
        WHERE ((m.sender_id = %s AND m.receiver_id = %s)
            OR (m.sender_id = %s AND m.receiver_id = %s))
          AND u.role = 'student'
        ORDER BY m.timestamp ASC
    """, (user_id, peer_id, peer_id, user_id))
    messages = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify(messages)


# 📨 Send peer message
@main.route('/send_peer_message/<int:peer_id>', methods=['POST'])
def send_peer_message(peer_id):
    sender_id = session.get('user_id')
    message_text = request.form.get('message')

    if not sender_id or not message_text:
        return jsonify({'error': 'Missing data'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO peer_messages (sender_id, receiver_id, message_text, timestamp)
        VALUES (%s, %s, %s, %s)
    """, (sender_id, peer_id, message_text, datetime.utcnow()))
    message_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        'success': True,
        'id': message_id,
        'sender_id': sender_id,
        'receiver_id': peer_id,
        'content': message_text,
        'timestamp': datetime.utcnow().isoformat()
    })


# 🗑️ Delete peer message
@main.route('/delete_peer_message/<int:message_id>', methods=['DELETE'])
def delete_peer_message(message_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT sender_id FROM peer_messages WHERE id = %s", (message_id,))
    row = cursor.fetchone()

    if not row:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Message not found'}), 404

    if row[0] != user_id:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Not authorized'}), 403

    cursor.execute("DELETE FROM peer_messages WHERE id = %s", (message_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True, 'deleted_id': message_id})

@main.before_request
def update_last_active():
    user_id = session.get('user_id')
    if user_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_active = %s WHERE id = %s", (datetime.utcnow(), user_id))
        conn.commit()
        cursor.close()
        conn.close()

