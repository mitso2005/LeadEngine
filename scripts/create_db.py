import sqlite3
import os
from datetime import datetime

# Define database path relative to project root
db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'database.db')

# Define connection and cursor
connection = sqlite3.connect(db_path)
cursor = connection.cursor()

# Create companies table
create_companies_table = '''CREATE TABLE IF NOT EXISTS companies (
    company_id INTEGER PRIMARY KEY AUTOINCREMENT,
    apollo_id TEXT UNIQUE,
    name TEXT,
    domain TEXT UNIQUE NOT NULL,
    industry TEXT,
    city TEXT,
    address TEXT,
    annual_revenue TEXT,
    employee_count INTEGER,
    engineering_headcount INTEGER,
    it_headcount INTEGER,
    short_description TEXT,
    people_found_count INTEGER DEFAULT 0,
    enriched BOOLEAN DEFAULT FALSE,
    people_searched BOOLEAN DEFAULT FALSE,
    searched_titles TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)'''

cursor.execute(create_companies_table)

# Create people table
create_people_table = '''CREATE TABLE IF NOT EXISTS people (
    person_id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    apollo_id TEXT UNIQUE,
    first_name TEXT,
    last_name TEXT,
    company_name TEXT,
    title TEXT,
    phone TEXT,
    email TEXT,
    linkedin_url TEXT,
    enriched BOOLEAN DEFAULT FALSE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
)'''

cursor.execute(create_people_table)

# Create indexes for faster lookups
cursor.execute('CREATE INDEX IF NOT EXISTS idx_companies_apollo_id ON companies(apollo_id)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_companies_enriched ON companies(enriched)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_companies_people_searched ON companies(people_searched)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_people_apollo_id ON people(apollo_id)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_people_company_id ON people(company_id)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_people_enriched ON people(enriched)')

# Commit and close
connection.commit()
connection.close()

print("✅ Database created successfully")
print("Cache logic:")
print("   - Company enrichment: Check enriched = FALSE")
print("   - People search: Check people_searched = FALSE AND people_found_count < 5")
print("   - People enrichment: Check enriched = FALSE")