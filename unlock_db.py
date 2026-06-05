import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def wipe_and_reset_tables():
    url = DATABASE_URL
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
        
    try:
        print("🔗 Connecting to database for systemic cleanup...")
        conn = psycopg2.connect(url)
        cursor = conn.cursor()
        
        # Safely drop old tables to wipe out schema discrepancies
        print("⚠️ Dropping old tasks and users tables...")
        cursor.execute("DROP TABLE IF EXISTS tasks CASCADE;")
        cursor.execute("DROP TABLE IF EXISTS users CASCADE;")
        
        conn.commit()
        cursor.close()
        conn.close()
        print("🎉 Clean slate achieved! Old tables successfully removed.")
    except Exception as e:
        print(f"❌ Cleanup operation crashed: {e}")

if __name__ == "__main__":
    wipe_and_reset_tables()