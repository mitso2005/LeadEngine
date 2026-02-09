import sqlite3
import pandas as pd
import os
from pathlib import Path

def export_to_csv(output_dir: str = "exports"):
    """Export database to CSV files"""
    
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
    people_df = pd.read_sql_query('SELECT * FROM people', conn)
    people_df.to_csv(output_path / "people.csv", index=False)
    print(f"✅ Exported {len(people_df)} people to {output_path / 'people.csv'}")
    
    conn.close()
    
    print(f"\n✅ Export complete! Files saved to {output_dir}/")

if __name__ == "__main__":
    export_to_csv()