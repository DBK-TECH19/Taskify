import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# We need the service role key to bypass the lock because your anon key is currently blocked by RLS
SUPABASE_URL = os.getenv("SUPABASE_URL")
# Go to your .env file and temporarily swap your SUPABASE_KEY here with the "Secret key" (service_role) from your earlier screenshot if you have it, or we can use SQL.