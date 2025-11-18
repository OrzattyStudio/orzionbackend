
"""
Script to set up Supabase tables automatically
Run this once to create the rate_limits table in Supabase
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.supabase_service import get_supabase_service

def create_rate_limits_table():
    """Create rate_limits table in Supabase."""
    supabase = get_supabase_service()
    
    # Read the SQL file
    sql_file = os.path.join(os.path.dirname(__file__), '..', '..', 'SUPABASE_RATE_LIMITS.sql')
    with open(sql_file, 'r') as f:
        sql = f.read()
    
    try:
        # Execute the SQL
        # Note: Supabase Python client doesn't support raw SQL execution
        # You need to run this in Supabase SQL Editor manually
        print("⚠️  Please execute SUPABASE_RATE_LIMITS.sql in your Supabase SQL Editor")
        print("\n📋 SQL to execute:")
        print(sql)
        print("\n✅ Instructions:")
        print("1. Go to your Supabase project dashboard")
        print("2. Open SQL Editor")
        print("3. Copy and paste the SQL above")
        print("4. Click 'Run'")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    create_rate_limits_table()
