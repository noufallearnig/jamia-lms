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
    if not url:
        return ""
    match = re.search(r'(?:v=|\/|embed\/|youtu\.be\/|shorts\/)([0-9A-Za-z_-]{11})', url)
    if match:
        video_id = match.group(1)
        return f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0&enablejsapi=1"
    return url

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        author TEXT DEFAULT 'Faculty',
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT NOT NULL,
        topic TEXT NOT NULL,
        video_url TEXT NOT NULL,
        teacher_name TEXT DEFAULT 'Faculty'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS kithabs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        filename TEXT NOT NULL,
        faculty TEXT DEFAULT 'Faculty'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT NOT NULL,
        title TEXT NOT NULL,
        filename TEXT NOT NULL,
        faculty TEXT DEFAULT 'Faculty'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS works (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        due_date TEXT NOT NULL,
        faculty TEXT DEFAULT 'Faculty'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        work_id INTEGER NOT NULL,
        student_username TEXT DEFAULT '',
        filename TEXT NOT NULL,
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'Pending'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS grades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        subject TEXT NOT NULL,
        score INTEGER NOT NULL,
        teacher TEXT DEFAULT 'Faculty'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS parent_student_link (
        parent_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        PRIMARY KEY (parent_id, student_id),
        FOREIGN KEY(parent_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS progress_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        report_type VARCHAR(50) NOT NULL,
        content TEXT NOT NULL,
        created_by INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(student_id) REFERENCES users(id),
        FOREIGN KEY(created_by) REFERENCES users(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS parent_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        status VARCHAR(50) DEFAULT 'Pending Admin',
        forwarded_teacher_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(parent_id) REFERENCES users(id),
        FOREIGN KEY(student_id) REFERENCES users(id),
        FOREIGN KEY(forwarded_teacher_id) REFERENCES users(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS admin_teacher_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS teacher_admin_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        report_type VARCHAR(50) NOT NULL,
        message TEXT NOT NULL,
        status VARCHAR(50) DEFAULT 'Pending Review',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(teacher_id) REFERENCES users(id),
        FOREIGN KEY(student_id) REFERENCES users(id)
    )''')

    def ensure_column(table_name, col_name, col_type):
        c.execute(f"PRAGMA table_info({table_name})")
        existing_cols = [row[1] for row in c.fetchall()]
        if col_name not in existing_cols:
            try:
                c.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass

    ensure_column("submissions", "student_username", "TEXT DEFAULT ''")
    ensure_column("submissions", "filename", "TEXT DEFAULT ''")
    ensure_column("submissions", "submitted_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    ensure_column("submissions", "status", "TEXT DEFAULT 'Pending'")
    ensure_column("grades", "teacher", "TEXT DEFAULT 'Faculty'")
    ensure_column("announcements", "author", "TEXT DEFAULT 'Faculty'")
    ensure_column("announcements", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    ensure_column("classes", "teacher_name", "TEXT DEFAULT 'Faculty'")
    
    ensure_column("kithabs", "faculty", "TEXT DEFAULT 'Faculty'")
    ensure_column("notes", "faculty", "TEXT DEFAULT 'Faculty'")
    ensure_column("works", "faculty", "TEXT DEFAULT 'Faculty'")

    conn.commit()
    conn.close()

init_db()

# ----------------- AUTHENTICATION -----------------
@app.route('/')
def home():
    return render_template('index.html')

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
            
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            elif user['role'] == 'parent':
                return redirect(url_for('parent_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
                
        flash("Invalid username or password.", "error")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'username' not in session:
        return redirect(url_for('login'))
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

# ----------------- ADMIN DASHBOARD & USER MANAGEMENT -----------------
@app.route('/admin')
def admin_dashboard():
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db()
    users = conn.execute('SELECT id, username, role FROM users ORDER BY id ASC').fetchall()
    
    feedbacks = conn.execute('''
        SELECT f.id, p.username as parent_name, s.username as student_name, f.message, f.status, f.created_at, f.forwarded_teacher_id
        FROM parent_feedback f
        JOIN users p ON f.parent_id = p.id
        JOIN users s ON f.student_id = s.id
        ORDER BY f.created_at DESC
    ''').fetchall()
    
    teachers = conn.execute('SELECT id, username FROM users WHERE role = "teacher"').fetchall()

    sent_admin_msgs = conn.execute('''
        SELECT a.id, a.message, a.created_at, 
               CASE WHEN a.teacher_id = 0 THEN 'Broadcast to All Faculty' ELSE u.username END as teacher_name
        FROM admin_teacher_messages a
        LEFT JOIN users u ON a.teacher_id = u.id
        ORDER BY a.created_at DESC
    ''').fetchall()

    teacher_admin_reports = conn.execute('''
        SELECT r.id, t.username as teacher_name, s.username as student_name, r.report_type, r.message, r.created_at
        FROM teacher_admin_reports r
        JOIN users t ON r.teacher_id = t.id
        LEFT JOIN users s ON r.student_id = s.id
        ORDER BY r.created_at DESC
    ''').fetchall()
    
    conn.close()
    return render_template('admin_dashboard.html', users=users, current_user_id=session.get('user_id'), username=session.get('username'), feedbacks=feedbacks, teachers=teachers, sent_admin_msgs=sent_admin_msgs, teacher_admin_reports=teacher_admin_reports)

@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        role = request.form.get('role', 'student').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if username and password:
            hashed_pw = generate_password_hash(password)
            conn = get_db()
            try:
                conn.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', (username, hashed_pw, role))
                conn.commit()
                flash(f"Account for '{username}' created successfully.", "success")
                conn.close()
                return redirect(url_for('admin_dashboard'))
            except sqlite3.IntegrityError:
                conn.close()
                flash(f"Username '{username}' already exists.", "error")
    return render_template('add_user.html')

@app.route('/admin/change_role/<int:user_id>', methods=['POST'])
def admin_change_role(user_id):
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    if user_id == session.get('user_id'):
        flash("You cannot alter your own admin privileges.", "error")
        return redirect(url_for('admin_dashboard'))
    new_role = request.form.get('new_role')
    conn = get_db()
    conn.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
    conn.commit()
    conn.close()
    flash("Role modified successfully.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reset_password/<int:user_id>', methods=['POST'])
def admin_reset_password(user_id):
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    new_password = request.form.get('new_password', '').strip()
    if new_password:
        hashed_pw = generate_password_hash(new_password)
        conn = get_db()
        conn.execute('UPDATE users SET password = ? WHERE id = ?', (hashed_pw, user_id))
        conn.commit()
        conn.close()
        flash("User password successfully updated.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def admin_delete_user(user_id):
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    if user_id == session.get('user_id'):
        flash("You cannot delete the active administrator account.", "error")
        return redirect(url_for('admin_dashboard'))
    conn = get_db()
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash("User account deleted permanently.", "success")
    return redirect(url_for('admin_dashboard'))

# ----------------- ADMIN FEEDBACK INBOX ACTIONS -----------------
@app.route('/admin/forward_feedback/<int:feedback_id>', methods=['POST'])
def admin_forward_feedback(feedback_id):
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    teacher_id = request.form.get('teacher_id')
    conn = get_db()
    conn.execute('UPDATE parent_feedback SET status = "Forwarded to Teacher", forwarded_teacher_id = ? WHERE id = ?', (teacher_id, feedback_id))
    conn.commit()
    conn.close()
    flash("Feedback forwarded to faculty member successfully.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_feedback/<int:feedback_id>', methods=['POST'])
def admin_delete_feedback(feedback_id):
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db()
    conn.execute('DELETE FROM parent_feedback WHERE id = ?', (feedback_id,))
    conn.commit()
    conn.close()
    flash("Feedback removed from Inbox.", "success")
    return redirect(url_for('admin_dashboard'))

# ----------------- ADMIN: TEACHER REPORTS RESOLUTION -----------------
@app.route('/admin/resolve_teacher_report/<int:report_id>', methods=['POST'])
def admin_resolve_teacher_report(report_id):
    if 'username' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db()
    conn.execute('DELETE FROM teacher_admin_reports WHERE id = ?', (report_id,))
    conn.commit()
    conn.close()
    flash("Teacher's report resolved and removed from inbox.", "success")
    return redirect(url_for('admin_dashboard'))

# ----------------- ADMIN: LINK PARENT TO STUDENT -----------------
@app.route('/admin_link_parent', methods=['POST'])
def admin_link_parent():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    parent_id = request.form.get('parent_id')
    student_id = request.form.get('student_id')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('INSERT INTO parent_student_link (parent_id, student_id) VALUES (?, ?)', (parent_id, student_id))
        conn.commit()
        flash("Parent and Student successfully linked!", "success")
    except Exception as e:
        flash("These accounts are already linked, or an error occurred.", "error")
        
    return redirect(url_for('admin_dashboard'))

# ----------------- ADMIN: SEND DIRECTIVE TO TEACHER -----------------
@app.route('/admin/send_directive', methods=['POST'])
def admin_send_directive():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    teacher_id = request.form.get('teacher_id')
    message = request.form.get('message')
    
    conn = get_db()
    conn.execute('INSERT INTO admin_teacher_messages (teacher_id, message) VALUES (?, ?)', (teacher_id, message))
    conn.commit()
    conn.close()
    flash("Directive sent to Faculty successfully.", "success")
    return redirect(url_for('admin_dashboard'))

# ----------------- ANNOUNCEMENTS -----------------
@app.route('/post_announcement', methods=['POST'])
def post_announcement():
    if 'username' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    message = request.form.get('message', '').strip()
    if message:
        conn = get_db()
        conn.execute('INSERT INTO announcements (author, message) VALUES (?, ?)', (session['username'], message))
        conn.commit()
        conn.close()
        flash("Announcement broadcasted successfully!", "success")
    return redirect(url_for('teacher_dashboard'))

@app.route('/delete_announcement/<int:ann_id>', methods=['POST'])
def delete_announcement(ann_id):
    if 'username' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM announcements WHERE id = ?', (ann_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('teacher_dashboard'))

# ----------------- DASHBOARDS -----------------
@app.route('/student')
def student_dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    announcements = conn.execute('SELECT * FROM announcements ORDER BY id DESC').fetchall()
    grades = conn.execute('SELECT g.id, g.subject, g.score, g.teacher FROM grades g JOIN users u ON g.student_id = u.id WHERE u.username = ? ORDER BY g.id DESC', (session['username'],)).fetchall()
    conn.close()
    return render_template('student_dashboard.html', announcements=announcements, grades=grades)

@app.route('/student/ai')
def student_ai():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('student_ai.html')

@app.route('/teacher')
def teacher_dashboard():
    if 'username' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    conn = get_db()
    students = conn.execute('SELECT id, username FROM users WHERE role = "student" ORDER BY id ASC').fetchall()
    announcements = conn.execute('SELECT * FROM announcements ORDER BY id DESC').fetchall()
    
    feedbacks = conn.execute('''
        SELECT f.message, p.username as parent_name, s.username as student_name, f.created_at
        FROM parent_feedback f
        JOIN users p ON f.parent_id = p.id
        JOIN users s ON f.student_id = s.id
        WHERE f.forwarded_teacher_id = ?
        ORDER BY f.created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    admin_directives = conn.execute('''
        SELECT message, created_at 
        FROM admin_teacher_messages 
        WHERE teacher_id = ? OR teacher_id = 0 
        ORDER BY created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    return render_template('teacher_dashboard.html', students=students, announcements=announcements, feedbacks=feedbacks, admin_directives=admin_directives)

# ----------------- TEACHER: REPORT TO ADMIN -----------------
@app.route('/teacher/report_to_admin', methods=['POST'])
def teacher_report_to_admin():
    if 'username' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    
    student_id = request.form.get('student_id', 0)
    report_type = request.form.get('report_type')
    message = request.form.get('message')
    teacher_id = session['user_id']
    
    conn = get_db()
    conn.execute('INSERT INTO teacher_admin_reports (teacher_id, student_id, report_type, message) VALUES (?, ?, ?, ?)', 
                 (teacher_id, student_id, report_type, message))
    conn.commit()
    conn.close()
    flash("Report successfully sent to the Administrator.", "success")
    return redirect(url_for('teacher_dashboard'))

# ----------------- CLASSES & YOUTUBE STREAMING -----------------
@app.route('/teacher/classes', methods=['GET', 'POST'])
def teacher_classes():
    if 'username' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    conn = get_db()
    if request.method == 'POST':
        subject = request.form.get('subject')
        topic = request.form.get('topic')
        raw_url = request.form.get('video_url')
        formatted_url = format_youtube_embed(raw_url)
        conn.execute('INSERT INTO classes (subject, topic, video_url, teacher_name) VALUES (?, ?, ?, ?)',
                     (subject, topic, formatted_url, session['username']))
        conn.commit()
        flash("Class session published successfully!", "success")
    classes = conn.execute('SELECT * FROM classes ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('teacher_classes.html', classes=classes)

@app.route('/student/classes')
def student_classes():
    if 'username' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    classes = conn.execute('SELECT * FROM classes ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('student_classes.html', classes=classes)

@app.route('/delete_class/<int:class_id>', methods=['POST'])
def delete_class(class_id):
    if 'username' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM classes WHERE id = ?', (class_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('teacher_classes'))

# ----------------- KITHABS, NOTES, WORKS -----------------
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/teacher/kithabs', methods=['GET', 'POST'])
def teacher_kithabs():
    if 'username' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    conn = get_db()
    if request.method == 'POST':
        title = request.form.get('title')
        file = request.files.get('pdf_file')
        if file and file.filename:
            filename = secure_filename(f"kithab_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            try:
                conn.execute('INSERT INTO kithabs (title, filename, faculty) VALUES (?, ?, ?)', (title, filename, session['username']))
            except sqlite3.IntegrityError:
                # Fallback for older database schemas containing 'author_teacher' column
                conn.execute('INSERT INTO kithabs (title, filename, faculty, author_teacher) VALUES (?, ?, ?, ?)', (title, filename, session['username'], session['username']))
            conn.commit()
            flash("Kithab uploaded successfully!", "success")
            
    kithabs = conn.execute('SELECT * FROM kithabs ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('teacher_kithabs.html', kithabs=kithabs)

@app.route('/student/library')
def student_library():
    if 'username' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    kithabs = conn.execute('SELECT * FROM kithabs ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('student_library.html', kithabs=kithabs)

@app.route('/delete_kithab/<int:kithab_id>', methods=['POST'])
def delete_kithab(kithab_id):
    if 'username' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM kithabs WHERE id = ?', (kithab_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('teacher_kithabs'))

@app.route('/teacher/notes', methods=['GET', 'POST'])
def teacher_notes():
    if 'username' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    conn = get_db()
    if request.method == 'POST':
        subject = request.form.get('subject')
        title = request.form.get('title')
        file = request.files.get('note_pdf')
        if file and file.filename:
            filename = secure_filename(f"note_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            try:
                conn.execute('INSERT INTO notes (subject, title, filename, faculty) VALUES (?, ?, ?, ?)', (subject, title, filename, session['username']))
            except sqlite3.IntegrityError:
                conn.execute('INSERT INTO notes (subject, title, filename, faculty, author_teacher) VALUES (?, ?, ?, ?, ?)', (subject, title, filename, session['username'], session['username']))
            conn.commit()
            flash("Note uploaded successfully!", "success")
            
    notes = conn.execute('SELECT * FROM notes ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('teacher_notes.html', notes=notes)

@app.route('/student/notes')
def student_notes():
    if 'username' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    notes = conn.execute('SELECT * FROM notes ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('student_notes.html', notes=notes)

@app.route('/delete_note/<int:note_id>', methods=['POST'])
def delete_note(note_id):
    if 'username' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM notes WHERE id = ?', (note_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('teacher_notes'))

@app.route('/teacher/works', methods=['GET', 'POST'])
def teacher_works():
    if 'username' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    conn = get_db()
    if request.method == 'POST':
        subject = request.form.get('subject')
        title = request.form.get('title')
        description = request.form.get('description')
        due_date = request.form.get('due_date')
        try:
            conn.execute('INSERT INTO works (subject, title, description, due_date, faculty) VALUES (?, ?, ?, ?, ?)',
                         (subject, title, description, due_date, session['username']))
        except sqlite3.IntegrityError:
            conn.execute('INSERT INTO works (subject, title, description, due_date, faculty, author_teacher) VALUES (?, ?, ?, ?, ?, ?)',
                         (subject, title, description, due_date, session['username'], session['username']))
        conn.commit()
        flash("Homework assigned successfully!", "success")
        
    works = conn.execute('SELECT w.*, (SELECT COUNT(*) FROM submissions s WHERE s.work_id = w.id) as sub_count FROM works w ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('teacher_works.html', works=works)

@app.route('/student/works')
def student_works():
    if 'username' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    works = conn.execute('''
        SELECT w.*, s.filename, s.submitted_at, s.status 
        FROM works w 
        LEFT JOIN submissions s ON w.id = s.work_id AND s.student_username = ? 
        ORDER BY w.id DESC
    ''', (session['username'],)).fetchall()
    conn.close()
    return render_template('student_works.html', works=works)

@app.route('/submit_work/<int:work_id>', methods=['POST'])
def submit_work(work_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    file = request.files.get('submission_file')
    if file and file.filename:
        filename = secure_filename(f"sub_{session['username']}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        conn = get_db()
        conn.execute('INSERT OR REPLACE INTO submissions (work_id, student_username, filename, status) VALUES (?, ?, ?, "Pending")',
                     (work_id, session['username'], filename))
        conn.commit()
        conn.close()
        flash("Homework submitted successfully!", "success")
    return redirect(url_for('student_works'))

@app.route('/delete_work/<int:work_id>', methods=['POST'])
def delete_work(work_id):
    if 'username' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM works WHERE id = ?', (work_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('teacher_works'))

@app.route('/teacher/submissions/<int:work_id>')
def teacher_submissions(work_id):
    if 'username' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    conn = get_db()
    work = conn.execute('SELECT * FROM works WHERE id = ?', (work_id,)).fetchone()
    submissions = conn.execute('SELECT id, student_username, filename, submitted_at, status FROM submissions WHERE work_id = ?', (work_id,)).fetchall()
    conn.close()
    return render_template('teacher_submissions.html', work=work, submissions=submissions)

@app.route('/approve_submission/<int:sub_id>', methods=['POST'])
def approve_submission(sub_id):
    if 'username' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    work_id = request.form.get('work_id')
    conn = get_db()
    conn.execute('UPDATE submissions SET status = "Approved" WHERE id = ?', (sub_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('teacher_submissions', work_id=work_id))

@app.route('/teacher/grades', methods=['GET', 'POST'])
def teacher_grades():
    if 'username' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    conn = get_db()
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        subject = request.form.get('subject')
        score = request.form.get('score')
        evaluating_teacher = session.get('username', 'Faculty')
        conn.execute('INSERT INTO grades (student_id, subject, score, teacher) VALUES (?, ?, ?, ?)', 
                     (student_id, subject, score, evaluating_teacher))
        conn.commit()
    students = conn.execute('SELECT id, username FROM users WHERE role = "student" ORDER BY id ASC').fetchall()
    grades = conn.execute('SELECT g.id, u.username, g.subject, g.score, g.teacher FROM grades g JOIN users u ON g.student_id = u.id ORDER BY g.id DESC').fetchall()
    conn.close()
    return render_template('teacher_grades.html', students=students, grades=grades)

@app.route('/delete_grade/<int:grade_id>', methods=['POST'])
def delete_grade(grade_id):
    if 'username' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM grades WHERE id = ?', (grade_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('teacher_grades'))

# ==========================================
# TEACHER: PROGRESS REPORTS FOR PARENTS
# ==========================================
@app.route('/teacher/reports', methods=['GET', 'POST'])
def teacher_reports():
    if 'username' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
    
    conn = get_db()
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        report_type = request.form.get('report_type')
        content = request.form.get('content')
        teacher_id = session['user_id']
        
        conn.execute('''
            INSERT INTO progress_reports (student_id, report_type, content, created_by)
            VALUES (?, ?, ?, ?)
        ''', (student_id, report_type, content, teacher_id))
        conn.commit()
        flash("Progress report sent to parents successfully!", "success")
        
    students = conn.execute('SELECT id, username FROM users WHERE role = "student" ORDER BY username ASC').fetchall()
    reports = conn.execute('''
        SELECT r.id, u.username as student_name, r.report_type, r.content, r.created_at
        FROM progress_reports r
        JOIN users u ON r.student_id = u.id
        WHERE r.created_by = ?
        ORDER BY r.created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    return render_template('teacher_reports.html', students=students, reports=reports)

@app.route('/delete_report/<int:report_id>', methods=['POST'])
def delete_report(report_id):
    if 'username' not in session or session.get('role') != 'teacher':
        return redirect(url_for('login'))
        
    conn = get_db()
    conn.execute('DELETE FROM progress_reports WHERE id = ?', (report_id,))
    conn.commit()
    conn.close()
    flash("Report deleted.", "success")
    return redirect(url_for('teacher_reports'))

# ==========================================
# PARENT MODULE ROUTES 
# ==========================================
@app.route('/parent_dashboard')
def parent_dashboard():
    if 'user_id' not in session or session.get('role') != 'parent':
        return redirect(url_for('login'))
    
    parent_id = session['user_id']
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('''
        SELECT u.id, u.username 
        FROM users u
        JOIN parent_student_link psl ON u.id = psl.student_id
        WHERE psl.parent_id = ?
    ''', (parent_id,))
    children = cur.fetchall()
    
    children_data = []
    
    for child in children:
        child_id = child[0]
        child_username = child[1]
        
        cur.execute('''
            SELECT report_type, content, created_at
            FROM progress_reports
            WHERE student_id = ?
            ORDER BY created_at DESC
        ''', (child_id,))
        teacher_reports = cur.fetchall()
        
        cur.execute('''
            SELECT w.title, w.subject, w.due_date, s.status
            FROM works w
            LEFT JOIN submissions s ON w.id = s.work_id AND s.student_username = ?
            ORDER BY w.id DESC
        ''', (child_username,))
        homeworks = cur.fetchall()
        
        total_works = len(homeworks)
        completed_works = sum(1 for hw in homeworks if hw[3] in ['Pending', 'Approved'])
        
        if total_works > 0:
            progress_percent = int((completed_works / total_works) * 100)
        else:
            progress_percent = 0
            
        children_data.append({
            'id': child_id,
            'username': child_username,
            'reports': teacher_reports,
            'homeworks': homeworks,
            'progress_percent': progress_percent,
            'total_works': total_works,
            'completed_works': completed_works
        })
        
    return render_template('parent_dashboard.html', children_data=children_data)

@app.route('/submit_parent_feedback', methods=['POST'])
def submit_parent_feedback():
    if 'user_id' not in session or session.get('role') != 'parent':
        return redirect(url_for('login'))
        
    parent_id = session['user_id']
    student_id = request.form.get('student_id')
    message = request.form.get('message')
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('SELECT 1 FROM parent_student_link WHERE parent_id = ? AND student_id = ?', (parent_id, student_id))
    is_authorized = cur.fetchone()
    
    if is_authorized:
        cur.execute('''
            INSERT INTO parent_feedback (parent_id, student_id, message) 
            VALUES (?, ?, ?)
        ''', (parent_id, student_id, message))
        conn.commit()
        flash("Your feedback has been securely submitted to the Administration.", "success")
    else:
        flash("Error: You are not authorized to submit feedback for this student.", "error")
        
    return redirect(url_for('parent_dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)