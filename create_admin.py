import sqlite3
from werkzeug.security import generate_password_hash

# Connect to database (this will create it if it doesn't exist)
conn = sqlite3.connect('database.db')
c = conn.cursor()

# Ensure users table exists
c.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL
)''')

# Create the admin account
username = "admin"
password = generate_password_hash("admin123") # Change "admin123" to your preferred password
role = "admin"

try:
    c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', (username, password, role))
    conn.commit()
    print("Success! Admin account created. Username: admin | Password: admin123")
except sqlite3.IntegrityError:
    print("Admin account already exists.")

conn.close()