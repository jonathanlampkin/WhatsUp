import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), '../database/database.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT * FROM google_nearby_places")
rows = cursor.fetchall()

print("Contents of google_nearby_places table:")
for row in rows:
    print(row)

conn.close()
