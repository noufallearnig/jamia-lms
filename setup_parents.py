import sqlite3

# Connect to your database. 
# Note: If your database file has a different name than 'lms.db', change it below!
conn = sqlite3.connect('lms.db')
cursor = conn.cursor()

# 1. Create a table to link parents to their children
cursor.execute('''
CREATE TABLE IF NOT EXISTS parent_student_link (
    parent_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    PRIMARY KEY (parent_id, student_id),
    FOREIGN KEY(parent_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
)
''')

# 2. Create a table for student progress reports
cursor.execute('''
CREATE TABLE IF NOT EXISTS progress_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    report_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(student_id) REFERENCES users(id),
    FOREIGN KEY(created_by) REFERENCES users(id)
)
''')

# 3. Create a table for parents to send feedback to the Admin
cursor.execute('''
CREATE TABLE IF NOT EXISTS parent_feedback (
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
)
''')

conn.commit()
conn.close()
print("Success! The new tables for Parents have been added to your database.")