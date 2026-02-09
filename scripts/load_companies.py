import sqlite3
import json

# Load companies from JSON
with open('data/companies.json', 'r') as f:
    companies = json.load(f)

# Connect to database
connection = sqlite3.connect('database.db')
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

print(f"\n📊 Total companies added: {len(companies)}")