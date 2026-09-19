import sqlite3

# 1. Create a connection to a new database file
connection = sqlite3.connect('database.db')

# 2. Get a 'cursor' to type SQL commands
cursor = connection.cursor()

# 3. Write the SQL command to create our secure Users table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
''')

# 4. Save the changes and close the connection
connection.commit()
connection.close()

print("Database and Users table successfully created!")