
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("❌ Critical: SUPABASE_URL or SUPABASE_KEY missing in .env")
    exit(1)

client = create_client(url, key)

print("🔍 Testing connection to 'imported_files' table...")
try:
    # Try to fetch one row or just describe columns if possible
    res = client.table("imported_files").select("*").limit(1).execute()
    print("✅ Table 'imported_files' exists and is accessible.")

    # Check column types if possible? No, but let's check one row if it exists
    if res.data:
        print(f"📊 Sample record: {res.data[0]}")
    else:
        print("ℹ️ Table is empty.")

    # Try a test insert
    test_data = {
        "file_name": "connection_test.csv",
        "file_mtime": 123456789,
        "file_type": "test"
    }
    print("🧪 Attempting test insert/upsert...")
    client.table("imported_files").upsert(test_data, on_conflict="file_name,file_mtime").execute()
    print("✅ Test upsert successful!")

    # Cleanup
    client.table("imported_files").delete().eq("file_name", "connection_test.csv").execute()
    print("🧹 Test record cleaned up.")

except Exception as e:
    print(f"❌ Error: {e}")
    if "PGRST205" in str(e) or "does not exist" in str(e):
        print("\n💡 SOLUTION: The table 'imported_files' is missing. Please copy and run the SQL migration I provided in the Supabase SQL Editor.")
    elif "403" in str(e):
        print("\n💡 SOLUTION: Permission denied. Ensure your Supabase RLS policies allow inserts or that you are using a service_role key if required (though anon key should work if RLS is off).")
