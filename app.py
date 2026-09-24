import os
import re
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "jamia_secret_enterprise_lms_key_2026"
UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
DB_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'database.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def format_youtube_embed(url):
    if not url: return ""
    match = re.search(r'(?:v=|\/|embed\/|youtu\.be\/|shorts\/)([0-9A-Za-z_-]{11})', url)
    if match: return f"https://www.youtube-nocookie.com/embed/{match.group(1)}?rel=0&enablejsapi=1"
    return url

# NEW: Helper function to get live semester ID without relogging
def get_student_sem(conn, user_id):
    user = conn.execute('SELECT semester_id FROM users WHERE id = ?', (user_id,)).fetchone()
    return int(user['semester_id']) if user and user['semester_id'] else 0

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS semesters (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS folders (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, module TEXT NOT NULL, teacher TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS announcements (id INTEGER PRIMARY KEY AUTOINCREMENT, author TEXT DEFAULT 'Faculty', message TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS classes (id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT NOT NULL, topic TEXT NOT NULL, video_url TEXT NOT NULL, teacher_name TEXT DEFAULT 'Faculty')''')
    c.execute('''CREATE TABLE IF NOT EXISTS kithabs (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, filename TEXT NOT NULL, faculty TEXT DEFAULT 'Faculty')''')
    c.execute('''CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT NOT NULL, title TEXT NOT NULL, filename TEXT NOT NULL, faculty TEXT DEFAULT 'Faculty')''')
    c.execute('''CREATE TABLE IF NOT EXISTS works (id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL, due_date TEXT NOT NULL, faculty TEXT DEFAULT 'Faculty')''')
    c.execute('''CREATE TABLE IF NOT EXISTS submissions (id INTEGER PRIMARY KEY AUTOINCREMENT, work_id INTEGER NOT NULL, student_username TEXT DEFAULT '', filename TEXT NOT NULL, submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, status TEXT DEFAULT 'Pending')''')
    c.execute('''CREATE TABLE IF NOT EXISTS parent_student_link (parent_id INTEGER NOT NULL, student_id INTEGER NOT NULL, PRIMARY KEY (parent_id, student_id), FOREIGN KEY(parent_id) REFERENCES users(id) ON DELETE CASCADE, FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS progress_reports (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL, report_type VARCHAR(50) NOT NULL, content TEXT NOT NULL, created_by INTEGER NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(student_id) REFERENCES users(id), FOREIGN KEY(created_by) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS parent_feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, parent_id INTEGER NOT NULL, student_id INTEGER NOT NULL, message TEXT NOT NULL, status VARCHAR(50) DEFAULT 'Pending Admin', forwarded_teacher_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(parent_id) REFERENCES users(id), FOREIGN KEY(student_id) REFERENCES users(id), FOREIGN KEY(forwarded_teacher_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS admin_teacher_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, teacher_id INTEGER NOT NULL, message TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS teacher_admin_reports (id INTEGER PRIMARY KEY AUTOINCREMENT, teacher_id INTEGER NOT NULL, student_id INTEGER NOT NULL, report_type VARCHAR(50) NOT NULL, message TEXT NOT NULL, status VARCHAR(50) DEFAULT 'Pending Review', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(teacher_id) REFERENCES users(id), FOREIGN KEY(student_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS exam_links (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, url TEXT NOT NULL, teacher TEXT NOT NULL, semester_id INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    def ensure_column(table_name, col_name, col_type):
        c.execute(f"PRAGMA table_info({table_name})")
        existing_cols = [row[1] for row in c.fetchall()]
        if col_name not in existing_cols:
            try: c.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError: pass

    ensure_column("submissions", "student_username", "TEXT DEFAULT ''")
    ensure_column("submissions", "filename", "TEXT DEFAULT ''")
    ensure_column("submissions", "submitted_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    ensure_column("submissions", "status", "TEXT DEFAULT 'Pending'")
    ensure_column("submissions", "grade", "TEXT DEFAULT ''")
    ensure_column("announcements", "author", "TEXT DEFAULT 'Faculty'")
    ensure_column("announcements", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    ensure_column("classes", "teacher_name", "TEXT DEFAULT 'Faculty'")
    ensure_column("kithabs", "faculty", "TEXT DEFAULT 'Faculty'")
    ensure_column("notes", "faculty", "TEXT DEFAULT 'Faculty'")
    ensure_column("works", "faculty", "TEXT DEFAULT 'Faculty'")
    ensure_column("kithabs", "folder_id", "INTEGER DEFAULT 0")
    ensure_column("classes", "folder_id", "INTEGER DEFAULT 0")
    ensure_column("notes", "folder_id", "INTEGER DEFAULT 0")
    ensure_column("users", "semester_id", "INTEGER DEFAULT 0")
    ensure_column("folders", "semester_id", "INTEGER DEFAULT 0")
    ensure_column("announcements", "semester_id", "INTEGER DEFAULT 0")
    ensure_column("works", "semester_id", "INTEGER DEFAULT 0")
    ensure_column("exam_links", "semester_id", "INTEGER DEFAULT 0")

    conn.commit()
    conn.close()

init_db()

# ----------------- AUTHENTICATION -----------------
@app.route('/')
def home(): return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and (check_password_hash(user['password'], password) or user['password'] == password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['semester_id'] = user['semester_id']
            if user['role'] == 'admin': return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'teacher': return redirect(url_for('teacher_dashboard'))
            elif user['role'] == 'parent': return redirect(url_for('parent_dashboard'))
            else: return redirect(url_for('student_dashboard'))
        flash("Invalid username or password.", "error")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'username' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        old_pw = request.form.get('old_password', '').strip()
        new_pw = request.form.get('new_password', '').strip()
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if user and (check_password_hash(user['password'], old_pw) or user['password'] == old_pw):
            hashed = generate_password_hash(new_pw)
            conn.execute('UPDATE users SET password = ? WHERE id = ?', (hashed, session['user_id']))
            conn.commit()
            conn.close()
            flash("Password updated successfully!", "success")
            return redirect(url_for('home'))
        conn.close()
        flash("Current password entered is incorrect.", "error")
    return render_template('change_password.html')

# ----------------- ADMIN DASHBOARD & ROUTES -----------------
@app.route('/admin')
def admin_dashboard():
    if 'username' not in session or session.get('role') != 'admin': return redirect(url_for('login'))
    conn = get_db()
    users = conn.execute('SELECT u.id, u.username, u.role, u.semester_id, s.name as semester_name FROM users u LEFT JOIN semesters s ON u.semester_id = s.id ORDER BY u.id ASC').fetchall()
    semesters = conn.execute('SELECT * FROM semesters ORDER BY id ASC').fetchall()
    feedbacks = conn.execute('SELECT f.id, p.username as parent_name, s.username as student_name, f.message, f.status, f.created_at, f.forwarded_teacher_id FROM parent_feedback f JOIN users p ON f.parent_id = p.id JOIN users s ON f.student_id = s.id ORDER BY f.created_at DESC').fetchall()
    teachers = conn.execute('SELECT id, username FROM users WHERE role = "teacher"').fetchall()
    sent_admin_msgs = conn.execute('SELECT a.id, a.message, a.created_at, CASE WHEN a.teacher_id = 0 THEN "Broadcast to All Faculty" ELSE u.username END as teacher_name FROM admin_teacher_messages a LEFT JOIN users u ON a.teacher_id = u.id ORDER BY a.created_at DESC').fetchall()
    teacher_admin_reports = conn.execute('SELECT r.id, t.username as teacher_name, s.username as student_name, r.report_type, r.message, r.created_at FROM teacher_admin_reports r JOIN users t ON r.teacher_id = t.id LEFT JOIN users s ON r.student_id = s.id ORDER BY r.created_at DESC').fetchall()
    conn.close()
    return render_template('admin_dashboard.html', users=users, current_user_id=session.get('user_id'), username=session.get('username'), feedbacks=feedbacks, teachers=teachers, sent_admin_msgs=sent_admin_msgs, teacher_admin_reports=teacher_admin_reports, semesters=semesters)

@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if 'username' not in session or session.get('role') != 'admin': return redirect(url_for('login'))
    if request.method == 'POST':
        role = request.form.get('role', 'student').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        semester_id = int(request.form.get('semester_id', 0))
        if username and password:
            hashed_pw = generate_password_hash(password)
            conn = get_db()
            try:
                conn.execute('INSERT INTO users (username, password, role, semester_id) VALUES (?, ?, ?, ?)', (username, hashed_pw, role, semester_id))
                conn.commit()
                flash(f"Account for '{username}' created successfully.", "success")
                conn.close()
                return redirect(url_for('admin_dashboard'))
            except sqlite3.IntegrityError:
                conn.close()
                flash(f"Username '{username}' already exists.", "error")
    conn = get_db()
    semesters = conn.execute('SELECT * FROM semesters ORDER BY id ASC').fetchall()
    conn.close()
    return render_template('add_user.html', semesters=semesters)

@app.route('/admin/change_role/<int:user_id>', methods=['POST'])
def admin_change_role(user_id):
    if 'username' not in session or session.get('role') != 'admin': return redirect(url_for('login'))
    if user_id == session.get('user_id'): return redirect(url_for('admin_dashboard'))
    new_role = request.form.get('new_role')
    conn = get_db()
    conn.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
    conn.commit()
    conn.close()
    flash("Role modified successfully.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/assign_semester/<int:user_id>', methods=['POST'])
def admin_assign_semester(user_id):
    if 'username' not in session or session.get('role') != 'admin': return redirect(url_for('login'))
    sem_id = int(request.form.get('semester_id', 0))
    conn = get_db()
    conn.execute('UPDATE users SET semester_id = ? WHERE id = ?', (sem_id, user_id))
    conn.commit()
    conn.close()
    flash("Student's Semester updated successfully.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/create_semester', methods=['POST'])
def admin_create_semester():
    if 'username' not in session or session.get('role') != 'admin': return redirect(url_for('login'))
    sem_name = request.form.get('name', '').strip()
    if sem_name:
        conn = get_db()
        try:
            conn.execute('INSERT INTO semesters (name) VALUES (?)', (sem_name,))
            conn.commit()
            flash(f"Semester '{sem_name}' created.", "success")
        except sqlite3.IntegrityError: pass
        conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_semester/<int:sem_id>', methods=['POST'])
def admin_delete_semester(sem_id):
    if 'username' not in session or session.get('role') != 'admin': return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM semesters WHERE id = ?', (sem_id,))
    conn.execute('UPDATE users SET semester_id = 0 WHERE semester_id = ?', (sem_id,))
    conn.commit()
    conn.close()
    flash("Semester deleted.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reset_password/<int:user_id>', methods=['POST'])
def admin_reset_password(user_id):
    if 'username' not in session or session.get('role') != 'admin': return redirect(url_for('login'))
    new_password = request.form.get('new_password', '').strip()
    if new_password:
        hashed_pw = generate_password_hash(new_password)
        conn = get_db()
        conn.execute('UPDATE users SET password = ? WHERE id = ?', (hashed_pw, user_id))
        conn.commit()
        conn.close()
        flash("User password reset successfully.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def admin_delete_user(user_id):
    if 'username' not in session or session.get('role') != 'admin': return redirect(url_for('login'))
    if user_id == session.get('user_id'): return redirect(url_for('admin_dashboard'))
    conn = get_db()
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash("User account deleted permanently.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/forward_feedback/<int:feedback_id>', methods=['POST'])
def admin_forward_feedback(feedback_id):
    if 'username' not in session or session.get('role') != 'admin': return redirect(url_for('login'))
    teacher_id = request.form.get('teacher_id')
    conn = get_db()
    conn.execute('UPDATE parent_feedback SET status = "Forwarded to Teacher", forwarded_teacher_id = ? WHERE id = ?', (teacher_id, feedback_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_feedback/<int:feedback_id>', methods=['POST'])
def admin_delete_feedback(feedback_id):
    if 'username' not in session or session.get('role') != 'admin': return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM parent_feedback WHERE id = ?', (feedback_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/resolve_teacher_report/<int:report_id>', methods=['POST'])
def admin_resolve_teacher_report(report_id):
    if 'username' not in session or session.get('role') != 'admin': return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM teacher_admin_reports WHERE id = ?', (report_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin_link_parent', methods=['POST'])
def admin_link_parent():
    if 'user_id' not in session or session.get('role') != 'admin': return redirect(url_for('login'))
    parent_id = request.form.get('parent_id')
    student_id = request.form.get('student_id')
    conn = get_db()
    try:
        conn.execute('INSERT INTO parent_student_link (parent_id, student_id) VALUES (?, ?)', (parent_id, student_id))
        conn.commit()
    except Exception as e: pass
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/send_directive', methods=['POST'])
def admin_send_directive():
    if 'user_id' not in session or session.get('role') != 'admin': return redirect(url_for('login'))
    teacher_id = request.form.get('teacher_id')
    message = request.form.get('message')
    conn = get_db()
    conn.execute('INSERT INTO admin_teacher_messages (teacher_id, message) VALUES (?, ?)', (teacher_id, message))
    conn.commit()
    conn.close()
    flash("Message sent to Faculty.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_directive/<int:msg_id>', methods=['POST'])
def admin_delete_directive(msg_id):
    if 'username' not in session or session.get('role') != 'admin': return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM admin_teacher_messages WHERE id = ?', (msg_id,))
    conn.commit()
    conn.close()
    flash("Sent message deleted.", "success")
    return redirect(url_for('admin_dashboard'))

# ----------------- TEACHER DASHBOARD & MODULES -----------------
@app.route('/teacher/create_folder', methods=['POST'])
def create_folder():
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    module = request.form.get('module') 
    name = request.form.get('name')
    semester_id = int(request.form.get('semester_id', 0))
    conn = get_db()
    conn.execute('INSERT INTO folders (name, module, teacher, semester_id) VALUES (?, ?, ?, ?)', (name, module, session['username'], semester_id))
    conn.commit()
    conn.close()
    flash(f"Folder '{name}' created successfully!", "success")
    if module == 'kithabs': return redirect(url_for('teacher_kithabs'))
    elif module == 'classes': return redirect(url_for('teacher_classes'))
    else: return redirect(url_for('teacher_notes'))

@app.route('/teacher/delete_folder/<int:folder_id>', methods=['POST'])
def delete_folder(folder_id):
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    conn = get_db()
    folder = conn.execute('SELECT module FROM folders WHERE id = ?', (folder_id,)).fetchone()
    module = folder['module'] if folder else 'kithabs'
    conn.execute('DELETE FROM folders WHERE id = ?', (folder_id,))
    if module == 'kithabs': conn.execute('DELETE FROM kithabs WHERE folder_id = ?', (folder_id,))
    elif module == 'classes': conn.execute('DELETE FROM classes WHERE folder_id = ?', (folder_id,))
    elif module == 'notes': conn.execute('DELETE FROM notes WHERE folder_id = ?', (folder_id,))
    conn.commit()
    conn.close()
    flash("Folder and its contents deleted permanently.", "success")
    if module == 'kithabs': return redirect(url_for('teacher_kithabs'))
    elif module == 'classes': return redirect(url_for('teacher_classes'))
    else: return redirect(url_for('teacher_notes'))

@app.route('/teacher')
def teacher_dashboard():
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    conn = get_db()
    students = conn.execute('SELECT id, username FROM users WHERE role = "student" ORDER BY id ASC').fetchall()
    announcements = conn.execute('SELECT * FROM announcements ORDER BY id DESC').fetchall()
    feedbacks = conn.execute('SELECT f.message, p.username as parent_name, s.username as student_name, f.created_at FROM parent_feedback f JOIN users p ON f.parent_id = p.id JOIN users s ON f.student_id = s.id WHERE f.forwarded_teacher_id = ? ORDER BY f.created_at DESC', (session['user_id'],)).fetchall()
    admin_directives = conn.execute('SELECT message, created_at FROM admin_teacher_messages WHERE teacher_id = ? OR teacher_id = 0 ORDER BY created_at DESC', (session['user_id'],)).fetchall()
    my_escalations = conn.execute('SELECT * FROM teacher_admin_reports WHERE teacher_id = ? ORDER BY created_at DESC', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('teacher_dashboard.html', students=students, announcements=announcements, feedbacks=feedbacks, admin_directives=admin_directives, my_escalations=my_escalations)

@app.route('/post_announcement', methods=['POST'])
def post_announcement():
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    message = request.form.get('message', '').strip()
    if message:
        conn = get_db()
        conn.execute('INSERT INTO announcements (author, message) VALUES (?, ?)', (session['username'], message))
        conn.commit()
        conn.close()
        flash("Announcement broadcasted.", "success")
    return redirect(url_for('teacher_dashboard'))

@app.route('/delete_announcement/<int:ann_id>', methods=['POST'])
def delete_announcement(ann_id):
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM announcements WHERE id = ?', (ann_id,))
    conn.commit()
    conn.close()
    flash("Announcement deleted.", "success")
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/report_to_admin', methods=['POST'])
def teacher_report_to_admin():
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    student_id = request.form.get('student_id', 0)
    report_type = request.form.get('report_type')
    message = request.form.get('message')
    teacher_id = session['user_id']
    conn = get_db()
    conn.execute('INSERT INTO teacher_admin_reports (teacher_id, student_id, report_type, message) VALUES (?, ?, ?, ?)', (teacher_id, student_id, report_type, message))
    conn.commit()
    conn.close()
    flash("Report sent to Admin.", "success")
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/delete_escalation/<int:report_id>', methods=['POST'])
def teacher_delete_escalation(report_id):
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM teacher_admin_reports WHERE id = ? AND teacher_id = ?', (report_id, session['user_id']))
    conn.commit()
    conn.close()
    flash("Escalation report deleted.", "success")
    return redirect(url_for('teacher_dashboard'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ---------- CLASSES, KITHABS, NOTES ----------
@app.route('/teacher/classes')
def teacher_classes():
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    conn = get_db()
    semesters = conn.execute('SELECT * FROM semesters ORDER BY id ASC').fetchall()
    folders = conn.execute('SELECT f.id, f.name, f.module, f.teacher, f.created_at, f.semester_id, s.name as sem_name FROM folders f LEFT JOIN semesters s ON f.semester_id = s.id WHERE f.module="classes" ORDER BY f.id DESC').fetchall()
    conn.close()
    return render_template('teacher_classes.html', folders=folders, current_folder=None, semesters=semesters)

@app.route('/teacher/classes/folder/<int:folder_id>', methods=['GET', 'POST'])
def teacher_classes_inside(folder_id):
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    conn = get_db()
    if request.method == 'POST':
        topic = request.form.get('topic')
        raw_url = request.form.get('video_url')
        formatted_url = format_youtube_embed(raw_url)
        conn.execute('INSERT INTO classes (subject, topic, video_url, teacher_name, folder_id) VALUES ("Sub", ?, ?, ?, ?)', (topic, formatted_url, session['username'], folder_id))
        conn.commit()
        flash("Class session published successfully!", "success")
    folder = conn.execute('SELECT * FROM folders WHERE id=?', (folder_id,)).fetchone()
    classes = conn.execute('SELECT * FROM classes WHERE folder_id=? ORDER BY id DESC', (folder_id,)).fetchall()
    conn.close()
    return render_template('teacher_classes.html', folders=None, current_folder=folder, classes=classes)

@app.route('/delete_class/<int:class_id>', methods=['POST'])
def delete_class(class_id):
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    conn = get_db()
    item = conn.execute('SELECT folder_id FROM classes WHERE id=?', (class_id,)).fetchone()
    f_id = item['folder_id'] if item else None
    conn.execute('DELETE FROM classes WHERE id = ?', (class_id,))
    conn.commit()
    conn.close()
    if f_id: return redirect(url_for('teacher_classes_inside', folder_id=f_id))
    return redirect(url_for('teacher_classes'))

@app.route('/student/classes')
def student_classes():
    if 'username' not in session: return redirect(url_for('login'))
    conn = get_db()
    student_sem = get_student_sem(conn, session['user_id'])
    folders = conn.execute('SELECT * FROM folders WHERE module="classes" AND (semester_id=? OR semester_id=0) ORDER BY id DESC', (student_sem,)).fetchall()
    conn.close()
    return render_template('student_classes.html', folders=folders, current_folder=None)

@app.route('/student/classes/folder/<int:folder_id>')
def student_classes_inside(folder_id):
    if 'username' not in session: return redirect(url_for('login'))
    conn = get_db()
    folder = conn.execute('SELECT * FROM folders WHERE id=?', (folder_id,)).fetchone()
    classes = conn.execute('SELECT * FROM classes WHERE folder_id=? ORDER BY id DESC', (folder_id,)).fetchall()
    conn.close()
    return render_template('student_classes.html', folders=None, current_folder=folder, classes=classes)

@app.route('/teacher/kithabs')
def teacher_kithabs():
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    conn = get_db()
    semesters = conn.execute('SELECT * FROM semesters ORDER BY id ASC').fetchall()
    folders = conn.execute('SELECT f.id, f.name, f.module, f.teacher, f.created_at, f.semester_id, s.name as sem_name FROM folders f LEFT JOIN semesters s ON f.semester_id = s.id WHERE f.module="kithabs" ORDER BY f.id DESC').fetchall()
    conn.close()
    return render_template('teacher_kithabs.html', folders=folders, current_folder=None, semesters=semesters)

@app.route('/teacher/kithabs/folder/<int:folder_id>', methods=['GET', 'POST'])
def teacher_kithabs_inside(folder_id):
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    conn = get_db()
    if request.method == 'POST':
        title = request.form.get('title')
        file = request.files.get('pdf_file')
        if file and file.filename:
            filename = secure_filename(f"kithab_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            try: conn.execute('INSERT INTO kithabs (title, filename, faculty, folder_id) VALUES (?, ?, ?, ?)', (title, filename, session['username'], folder_id))
            except sqlite3.IntegrityError: conn.execute('INSERT INTO kithabs (title, filename, faculty, author_teacher, folder_id) VALUES (?, ?, ?, ?, ?)', (title, filename, session['username'], session['username'], folder_id))
            conn.commit()
            flash("Kithab uploaded to folder successfully!", "success")
    folder = conn.execute('SELECT * FROM folders WHERE id=?', (folder_id,)).fetchone()
    kithabs = conn.execute('SELECT * FROM kithabs WHERE folder_id=? ORDER BY id DESC', (folder_id,)).fetchall()
    conn.close()
    return render_template('teacher_kithabs.html', folders=None, current_folder=folder, kithabs=kithabs)

@app.route('/delete_kithab/<int:kithab_id>', methods=['POST'])
def delete_kithab(kithab_id):
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    conn = get_db()
    item = conn.execute('SELECT folder_id FROM kithabs WHERE id=?', (kithab_id,)).fetchone()
    f_id = item['folder_id'] if item else None
    conn.execute('DELETE FROM kithabs WHERE id = ?', (kithab_id,))
    conn.commit()
    conn.close()
    if f_id: return redirect(url_for('teacher_kithabs_inside', folder_id=f_id))
    return redirect(url_for('teacher_kithabs'))

@app.route('/student/library')
def student_library():
    if 'username' not in session: return redirect(url_for('login'))
    conn = get_db()
    student_sem = get_student_sem(conn, session['user_id'])
    folders = conn.execute('SELECT * FROM folders WHERE module="kithabs" AND (semester_id=? OR semester_id=0) ORDER BY id DESC', (student_sem,)).fetchall()
    conn.close()
    return render_template('student_library.html', folders=folders, current_folder=None)

@app.route('/student/library/folder/<int:folder_id>')
def student_library_inside(folder_id):
    if 'username' not in session: return redirect(url_for('login'))
    conn = get_db()
    folder = conn.execute('SELECT * FROM folders WHERE id=?', (folder_id,)).fetchone()
    kithabs = conn.execute('SELECT * FROM kithabs WHERE folder_id=? ORDER BY id DESC', (folder_id,)).fetchall()
    conn.close()
    return render_template('student_library.html', folders=None, current_folder=folder, kithabs=kithabs)

@app.route('/teacher/notes')
def teacher_notes():
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    conn = get_db()
    semesters = conn.execute('SELECT * FROM semesters ORDER BY id ASC').fetchall()
    folders = conn.execute('SELECT f.id, f.name, f.module, f.teacher, f.created_at, f.semester_id, s.name as sem_name FROM folders f LEFT JOIN semesters s ON f.semester_id = s.id WHERE f.module="notes" ORDER BY f.id DESC').fetchall()
    conn.close()
    return render_template('teacher_notes.html', folders=folders, current_folder=None, semesters=semesters)

@app.route('/teacher/notes/folder/<int:folder_id>', methods=['GET', 'POST'])
def teacher_notes_inside(folder_id):
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    conn = get_db()
    if request.method == 'POST':
        title = request.form.get('title')
        file = request.files.get('note_pdf')
        if file and file.filename:
            filename = secure_filename(f"note_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            try: conn.execute('INSERT INTO notes (subject, title, filename, faculty, folder_id) VALUES ("Sub", ?, ?, ?, ?)', (title, filename, session['username'], folder_id))
            except sqlite3.IntegrityError: conn.execute('INSERT INTO notes (subject, title, filename, faculty, author_teacher, folder_id) VALUES ("Sub", ?, ?, ?, ?, ?)', (title, filename, session['username'], session['username'], folder_id))
            conn.commit()
            flash("Note uploaded successfully!", "success")
    folder = conn.execute('SELECT * FROM folders WHERE id=?', (folder_id,)).fetchone()
    notes = conn.execute('SELECT * FROM notes WHERE folder_id=? ORDER BY id DESC', (folder_id,)).fetchall()
    conn.close()
    return render_template('teacher_notes.html', folders=None, current_folder=folder, notes=notes)

@app.route('/delete_note/<int:note_id>', methods=['POST'])
def delete_note(note_id):
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    conn = get_db()
    item = conn.execute('SELECT folder_id FROM notes WHERE id=?', (note_id,)).fetchone()
    f_id = item['folder_id'] if item else None
    conn.execute('DELETE FROM notes WHERE id = ?', (note_id,))
    conn.commit()
    conn.close()
    if f_id: return redirect(url_for('teacher_notes_inside', folder_id=f_id))
    return redirect(url_for('teacher_notes'))

@app.route('/student/notes')
def student_notes():
    if 'username' not in session: return redirect(url_for('login'))
    conn = get_db()
    student_sem = get_student_sem(conn, session['user_id'])
    folders = conn.execute('SELECT * FROM folders WHERE module="notes" AND (semester_id=? OR semester_id=0) ORDER BY id DESC', (student_sem,)).fetchall()
    conn.close()
    return render_template('student_notes.html', folders=folders, current_folder=None)

@app.route('/student/notes/folder/<int:folder_id>')
def student_notes_inside(folder_id):
    if 'username' not in session: return redirect(url_for('login'))
    conn = get_db()
    folder = conn.execute('SELECT * FROM folders WHERE id=?', (folder_id,)).fetchone()
    notes = conn.execute('SELECT * FROM notes WHERE folder_id=? ORDER BY id DESC', (folder_id,)).fetchall()
    conn.close()
    return render_template('student_notes.html', folders=None, current_folder=folder, notes=notes)

# ---------- WORKS & GRADING ----------
@app.route('/teacher/works', methods=['GET', 'POST'])
def teacher_works():
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    conn = get_db()
    if request.method == 'POST':
        subject = request.form.get('subject')
        title = request.form.get('title')
        description = request.form.get('description')
        due_date = request.form.get('due_date')
        semester_id = int(request.form.get('semester_id', 0))
        try: conn.execute('INSERT INTO works (subject, title, description, due_date, faculty, semester_id) VALUES (?, ?, ?, ?, ?, ?)', (subject, title, description, due_date, session['username'], semester_id))
        except sqlite3.IntegrityError: conn.execute('INSERT INTO works (subject, title, description, due_date, faculty, author_teacher, semester_id) VALUES (?, ?, ?, ?, ?, ?, ?)', (subject, title, description, due_date, session['username'], session['username'], semester_id))
        conn.commit()
        flash("Homework assigned successfully!", "success")
    semesters = conn.execute('SELECT * FROM semesters ORDER BY id ASC').fetchall()
    works = conn.execute('SELECT w.*, (SELECT COUNT(*) FROM submissions s WHERE s.work_id = w.id) as sub_count, sem.name as sem_name FROM works w LEFT JOIN semesters sem ON w.semester_id = sem.id ORDER BY w.id DESC').fetchall()
    conn.close()
    return render_template('teacher_works.html', works=works, semesters=semesters)

@app.route('/student/works')
def student_works():
    if 'username' not in session: return redirect(url_for('login'))
    conn = get_db()
    student_sem = get_student_sem(conn, session['user_id'])
    works = conn.execute('SELECT w.*, s.filename, s.submitted_at, s.status, s.grade FROM works w LEFT JOIN submissions s ON w.id = s.work_id AND s.student_username = ? WHERE w.semester_id = ? OR w.semester_id = 0 ORDER BY w.id DESC', (session['username'], student_sem)).fetchall()
    conn.close()
    return render_template('student_works.html', works=works)

@app.route('/submit_work/<int:work_id>', methods=['POST'])
def submit_work(work_id):
    if 'username' not in session: return redirect(url_for('login'))
    file = request.files.get('submission_file')
    if file and file.filename:
        filename = secure_filename(f"sub_{session['username']}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        conn = get_db()
        conn.execute('INSERT OR REPLACE INTO submissions (work_id, student_username, filename, status) VALUES (?, ?, ?, "Pending")', (work_id, session['username'], filename))
        conn.commit()
        conn.close()
    return redirect(url_for('student_works'))

@app.route('/delete_work/<int:work_id>', methods=['POST'])
def delete_work(work_id):
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM works WHERE id = ?', (work_id,))
    conn.commit()
    conn.close()
    flash("Homework assignment deleted.", "success")
    return redirect(url_for('teacher_works'))

@app.route('/teacher/submissions/<int:work_id>')
def teacher_submissions(work_id):
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    conn = get_db()
    work = conn.execute('SELECT * FROM works WHERE id = ?', (work_id,)).fetchone()
    submissions = conn.execute('SELECT id, student_username, filename, submitted_at, status, grade FROM submissions WHERE work_id = ?', (work_id,)).fetchall()
    conn.close()
    return render_template('teacher_submissions.html', work=work, submissions=submissions)

@app.route('/approve_submission/<int:sub_id>', methods=['POST'])
def approve_submission(sub_id):
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    work_id = request.form.get('work_id')
    grade = request.form.get('grade', 'Completed')
    conn = get_db()
    conn.execute('UPDATE submissions SET status = "Graded", grade = ? WHERE id = ?', (grade, sub_id))
    conn.commit()
    conn.close()
    flash("Homework graded successfully!", "success")
    return redirect(url_for('teacher_submissions', work_id=work_id))

# ---------- EXAMS & RESULTS ----------
@app.route('/teacher/exams', methods=['GET', 'POST'])
def teacher_exams():
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    conn = get_db()
    if request.method == 'POST':
        title = request.form.get('title')
        url = request.form.get('url')
        semester_id = int(request.form.get('semester_id', 0))
        conn.execute('INSERT INTO exam_links (title, url, teacher, semester_id) VALUES (?, ?, ?, ?)', (title, url, session['username'], semester_id))
        conn.commit()
        flash("Exam Portal Link Published!", "success")
    semesters = conn.execute('SELECT * FROM semesters ORDER BY id ASC').fetchall()
    links = conn.execute('SELECT e.*, s.name as sem_name FROM exam_links e LEFT JOIN semesters s ON e.semester_id = s.id ORDER BY e.id DESC').fetchall()
    conn.close()
    return render_template('teacher_exams.html', links=links, semesters=semesters)

@app.route('/delete_exam/<int:exam_id>', methods=['POST'])
def delete_exam(exam_id):
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM exam_links WHERE id = ?', (exam_id,))
    conn.commit()
    conn.close()
    flash("Exam Link removed.", "success")
    return redirect(url_for('teacher_exams'))

@app.route('/student/exams')
def student_exams():
    if 'username' not in session: return redirect(url_for('login'))
    conn = get_db()
    student_sem = get_student_sem(conn, session['user_id'])
    links = conn.execute('SELECT * FROM exam_links WHERE semester_id = ? OR semester_id = 0 ORDER BY id DESC', (student_sem,)).fetchall()
    conn.close()
    return render_template('student_exams.html', links=links)


# ---------- PROGRESS REPORTS ----------
@app.route('/teacher/reports', methods=['GET', 'POST'])
def teacher_reports():
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    conn = get_db()
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        report_type = request.form.get('report_type')
        content = request.form.get('content')
        conn.execute('INSERT INTO progress_reports (student_id, report_type, content, created_by) VALUES (?, ?, ?, ?)', (student_id, report_type, content, session['user_id']))
        conn.commit()
    students = conn.execute('SELECT id, username FROM users WHERE role = "student" ORDER BY username ASC').fetchall()
    reports = conn.execute('SELECT r.id, u.username as student_name, r.report_type, r.content, r.created_at FROM progress_reports r JOIN users u ON r.student_id = u.id WHERE r.created_by = ? ORDER BY r.created_at DESC', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('teacher_reports.html', students=students, reports=reports)

@app.route('/delete_report/<int:report_id>', methods=['POST'])
def delete_report(report_id):
    if 'username' not in session or session.get('role') != 'teacher': return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM progress_reports WHERE id = ?', (report_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('teacher_reports'))

# ---------- STUDENT HOME DASHBOARD & PARENT PORTAL ----------
@app.route('/student')
def student_dashboard():
    if 'username' not in session: return redirect(url_for('login'))
    conn = get_db()
    student_sem = get_student_sem(conn, session['user_id'])
    announcements = conn.execute('SELECT * FROM announcements ORDER BY id DESC').fetchall()
    works = conn.execute('SELECT w.title, s.status, s.grade FROM works w LEFT JOIN submissions s ON w.id = s.work_id AND s.student_username = ? WHERE w.semester_id = ? OR w.semester_id = 0 ORDER BY w.id DESC LIMIT 5', (session['username'], student_sem)).fetchall()
    conn.close()
    return render_template('student_dashboard.html', announcements=announcements, works=works)

@app.route('/student_dashboard')
def std_dash(): return redirect(url_for('student_dashboard'))

@app.route('/student/ai')
def student_ai():
    if 'username' not in session: return redirect(url_for('login'))
    return render_template('student_ai.html')

@app.route('/parent_dashboard')
def parent_dashboard():
    if 'user_id' not in session or session.get('role') != 'parent': return redirect(url_for('login'))
    parent_id = session['user_id']
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT u.id, u.username FROM users u JOIN parent_student_link psl ON u.id = psl.student_id WHERE psl.parent_id = ?', (parent_id,))
    children = cur.fetchall()
    children_data = []
    for child in children:
        child_id = child[0]
        child_username = child[1]
        cur.execute('SELECT report_type, content, created_at FROM progress_reports WHERE student_id = ? ORDER BY created_at DESC', (child_id,))
        teacher_reports = cur.fetchall()
        cur.execute('SELECT w.title, w.subject, w.due_date, s.status FROM works w LEFT JOIN submissions s ON w.id = s.work_id AND s.student_username = ? ORDER BY w.id DESC', (child_username,))
        homeworks = cur.fetchall()
        total_works = len(homeworks)
        completed_works = sum(1 for hw in homeworks if hw[3] in ['Graded', 'Approved'])
        progress_percent = int((completed_works / total_works) * 100) if total_works > 0 else 0
        children_data.append({
            'id': child_id, 'username': child_username, 'reports': teacher_reports,
            'homeworks': homeworks, 'progress_percent': progress_percent,
            'total_works': total_works, 'completed_works': completed_works
        })
    return render_template('parent_dashboard.html', children_data=children_data)

@app.route('/submit_parent_feedback', methods=['POST'])
def submit_parent_feedback():
    if 'user_id' not in session or session.get('role') != 'parent': return redirect(url_for('login'))
    parent_id = session['user_id']
    student_id = request.form.get('student_id')
    message = request.form.get('message')
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT 1 FROM parent_student_link WHERE parent_id = ? AND student_id = ?', (parent_id, student_id))
    if cur.fetchone():
        cur.execute('INSERT INTO parent_feedback (parent_id, student_id, message) VALUES (?, ?, ?)', (parent_id, student_id, message))
        conn.commit()
    return redirect(url_for('parent_dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)