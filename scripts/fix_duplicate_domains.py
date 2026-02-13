"""
Fix duplicate domains in the database by:
1. Keeping the enriched version (or first entry if none enriched)
2. Deleting duplicates
3. Adding UNIQUE constraint to domain field
"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'database.db')
connection = sqlite3.connect(db_path)
cursor = connection.cursor()

print("🔍 Analyzing database for duplicates...")

# Find all duplicate domains
cursor.execute('''
    SELECT domain, COUNT(*) as count 
    FROM companies 
    GROUP BY domain 
    HAVING count > 1
    ORDER BY count DESC
''')

duplicates = cursor.fetchall()
print(f"\n📊 Found {len(duplicates)} domains with duplicates")

if not duplicates:
    print("✅ No duplicates found!")
    connection.close()
    exit(0)

print("\n🧹 Cleaning up duplicates...")

total_deleted = 0

for domain, count in duplicates:
    # Get all companies with this domain
    cursor.execute('''
        SELECT company_id, name, enriched, apollo_id, created_at
        FROM companies 
        WHERE domain = ?
        ORDER BY enriched DESC, created_at ASC
    ''', (domain,))
    
    companies = cursor.fetchall()
    
    # Keep the first one (most enriched or oldest)
    keep_id = companies[0][0]
    keep_name = companies[0][1]
    
    # Delete the rest
    delete_ids = [c[0] for c in companies[1:]]
    
    print(f"\n  {domain}:")
    print(f"    ✓ Keeping: {keep_name} (ID: {keep_id})")
    
    for del_id in delete_ids:
        del_name = [c[1] for c in companies if c[0] == del_id][0]
        print(f"    ✗ Deleting: {del_name} (ID: {del_id})")
        
        # Delete associated people first (foreign key constraint)
        cursor.execute('DELETE FROM people WHERE company_id = ?', (del_id,))
        
        # Delete the company
        cursor.execute('DELETE FROM companies WHERE company_id = ?', (del_id,))
        total_deleted += 1

connection.commit()

print(f"\n✅ Deleted {total_deleted} duplicate companies")

# Now recreate the table with proper constraints
print("\n🔧 Rebuilding table with UNIQUE constraint on domain...")

# Create new table with correct schema
cursor.execute('''
    CREATE TABLE companies_new (
        company_id INTEGER PRIMARY KEY AUTOINCREMENT,
        apollo_id TEXT UNIQUE,
        name TEXT NOT NULL,
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
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
''')

# Copy data to new table
cursor.execute('''
    INSERT INTO companies_new 
    SELECT * FROM companies
''')

# Drop old table
cursor.execute('DROP TABLE companies')

# Rename new table
cursor.execute('ALTER TABLE companies_new RENAME TO companies')

connection.commit()
connection.close()

print("✅ Database fixed!")
print("\n📋 Summary:")
print(f"  - Removed {total_deleted} duplicate companies")
print(f"  - Added UNIQUE constraint to domain field")
print(f"  - Database is now clean and ready to use")

# Verify
connection = sqlite3.connect(db_path)
cursor = connection.cursor()
cursor.execute('SELECT COUNT(*) FROM companies')
total = cursor.fetchone()[0]
cursor.execute('SELECT COUNT(DISTINCT domain) FROM companies')
unique = cursor.fetchone()[0]
connection.close()

print(f"\n✓ Total companies: {total}")
print(f"✓ Unique domains: {unique}")

if total == unique:
    print("\n🎉 All domains are now unique!")
else:
    print("\n⚠️  Warning: Still have duplicates - run again")
