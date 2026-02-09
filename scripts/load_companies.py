import sqlite3
import json
import os

# Use relative paths
script_dir = os.path.dirname(__file__)
json_path = os.path.join(script_dir, '..', 'data', 'companies.json')
db_path = os.path.join(script_dir, '..', 'data', 'database.db')

# Load companies from JSON
with open(json_path, 'r') as f:
    companies = json.load(f)

# Connect to database
connection = sqlite3.connect(db_path)
cursor = connection.cursor()

# Insert each company
for name, domain in companies.items():
    cursor.execute('''
        INSERT OR IGNORE INTO companies (name, domain)
        VALUES (?, ?)
    ''', (name, domain))
    print(f"✅ Added: {name} - {domain}")

connection.commit()
connection.close()

print(f"\nTotal companies added: {len(companies)}")