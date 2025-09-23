import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

load_dotenv()

host = os.getenv("DB_HOST")
port = int(os.getenv("DB_PORT", 3306))
user = os.getenv("DB_USER")
pw = os.getenv("DB_PASSWORD")
db = os.getenv("DB_NAME")

try:
    conn = mysql.connector.connect(
        host=host, port=port, user=user, password=pw, database=db
    )
    cur = conn.cursor()
    cur.execute("SELECT 1")
    print("✅ DB connection OK:", cur.fetchone())
    cur.close()
    conn.close()
except Error as e:
    print("❌ DB connection FAILED:", e)
