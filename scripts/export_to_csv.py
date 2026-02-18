import sqlite3
import pandas as pd
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.database_service import DatabaseService

def export_to_csv(output_dir: str = "exports"):
    """Export database to CSV files"""
    db = DatabaseService()

    # Set up paths
    script_dir = os.path.dirname(__file__)
    db_path = os.path.join(script_dir, '..', 'data', 'database.db')
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    
    # Export companies
    companies_df = pd.read_sql_query('SELECT * FROM companies', conn)
    companies_df.to_csv(output_path / "companies.csv", index=False)
    print(f"✅ Exported {len(companies_df)} companies to {output_path / 'companies.csv'}")
    
    # Export people
    people = db._get_connection().execute('SELECT * FROM people').fetchall()
    people_df = pd.DataFrame(people, columns=[
        'person_id', 'company_id', 'apollo_id', 'first_name', 'last_name',
        'company_name', 'title', 'phone', 'email', 'linkedin_url', 
        'enriched', 'created_at', 'updated_at', 'city', 'state', 'country',
    ])
    
    # Add three static columns
    people_df['owner'] = 'Matt Partington'
    people_df['type'] = 'New Lead'
    people_df['source'] = 'LeadEngine'

    people_df.to_csv(output_path / "people.csv", index=False)
    print(f"✅ Exported {len(people_df)} people to {output_path / 'people.csv'}")
    
    conn.close()
    
    print(f"\n✅ Export complete! Files saved to {output_dir}/")

if __name__ == "__main__":
    export_to_csv()