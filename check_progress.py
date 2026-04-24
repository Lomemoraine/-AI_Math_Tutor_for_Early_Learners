import sqlite3

# Connect to your local DB
conn = sqlite3.connect("tutor_progress.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# List learners
print("Learners:")
for row in cur.execute("SELECT * FROM learners"):
    print(dict(row))

# Show sessions
print("\nSessions:")
for row in cur.execute("SELECT * FROM sessions"):
    print(dict(row))

# Show responses
print("\nResponses:")
for row in cur.execute("SELECT learner_id, item_id, skill, difficulty, correct, ts FROM responses"):
    print(dict(row))

conn.close()
