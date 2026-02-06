import json
from pathlib import Path
from services.data_store import LocalDataStore

def number_populate():
    """Populate phone numbers for enriched people using numbers.json as source"""
    numbers_file = Path("data/numbers.json")
    
    with open(numbers_file, 'r') as f:
        numbers_data = json.load(f)
    
    # Use LocalDataStore to load and save people data
    store = LocalDataStore()
    people_data = store._read_json(store.people_file)
    
    # Create a mapping of id to phone number
    id_to_phone = {entry['id']: entry['sanitized_number'] for entry in numbers_data}
    
    # Update people data with phone numbers
    updated_count = 0
    for person in people_data:
        apollo_id = person.get('apollo_id')  # Changed from 'id' to 'apollo_id'
        if apollo_id and apollo_id in id_to_phone:
            person['phone_number'] = id_to_phone[apollo_id]
            print(f"✓ Updated {person.get('first_name')} {person.get('last_name')}: {id_to_phone[apollo_id]}")
            updated_count += 1
    
    # Save updated people data
    store._write_json(store.people_file, people_data)
    
    # Re-export to CSV with phone numbers
    print(f"\n📊 Re-exporting to CSV...")
    store.export_to_csv()
    
    print(f"\n✅ Updated {updated_count} people with phone numbers!")
    print(f"   Check exports/people.csv for results")

if __name__ == "__main__":
    number_populate()