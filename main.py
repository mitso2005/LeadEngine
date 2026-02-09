import json
from pathlib import Path
from services.apollo_client import ApolloClient, APOLLO_API_KEY
from services.database_service import DatabaseService
from typing import List, Optional
import time
import os

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://webhook.site/55dac724-e0b4-458e-8e20-b42ab21fb2b4")

def load_titles() -> List[str]:
    """Load titles from data/titles.json"""
    titles_file = Path("data/titles.json")
    with open(titles_file, 'r') as f:
        return json.load(f)

def enrich_companies(client: ApolloClient, db: DatabaseService):
    """
    Enrich companies that haven't been enriched yet
    Uses cache - only calls API for unenriched companies
    """
    print("\n=== ENRICHING COMPANIES ===")
    
    # Get companies that need enrichment
    companies_to_enrich = db.get_unenriched_companies()
    
    if not companies_to_enrich:
        print("✅ All companies already enriched!")
        return
    
    print(f"Found {len(companies_to_enrich)} companies to enrich")
    
    # Extract domains
    domains = [c['domain'] for c in companies_to_enrich]
    
    # Batch process (10 per batch - API limit)
    batch_size = 10
    batches = [domains[i:i + batch_size] for i in range(0, len(domains), batch_size)]
    
    for idx, batch in enumerate(batches, 1):
        print(f"\nBatch {idx}/{len(batches)}: {len(batch)} companies")
        
        result = client.org_bulk_enrich(batch)
        
        if "error" in result:
            print(f"  ✗ API Error: {result['error']}")
            continue
        
        if "organizations" in result:
            for org_data in result["organizations"]:
                if org_data is None:
                    continue
                
                domain = org_data.get("primary_domain")
                if domain:
                    db.save_company_enrichment(domain, org_data)
                    print(f"  ✓ Enriched: {org_data.get('name')}")
        
        if idx < len(batches):
            time.sleep(2)
    
    print(f"\n✅ Company enrichment complete!")

def search_people(client: ApolloClient, db: DatabaseService, titles: List[str], people_per_company: int = 5):
    """
    Search for people at companies that need it
    Uses cache - only searches if people_searched=FALSE or people_found_count < 5
    """
    print(f"\n=== SEARCHING FOR PEOPLE ===")
    
    # Get companies that need people search
    companies_to_search = db.get_companies_needing_people_search()
    
    if not companies_to_search:
        print("✅ All companies already have sufficient people!")
        return
    
    print(f"Found {len(companies_to_search)} companies needing people search")
    
    for company in companies_to_search:
        apollo_id = company.get('apollo_id')
        if not apollo_id:
            print(f"\n⚠️  Skipping {company['name']} - no Apollo ID")
            continue
        
        print(f"\n{company['name']} (ID: {apollo_id}):")
        
        result = client.people_search(
            organization_ids=[apollo_id],
            person_titles=titles,
            per_page=people_per_company
        )
        
        if "error" not in result and "people" in result:
            people = result["people"]
            print(f"  Found {len(people)} people")
            
            for person_data in people:
                person = db.save_person(company['company_id'], person_data)
                print(f"    ✓ {person['first_name']} {person['last_name']} - {person['title']}")
            
            # Mark search as complete
            db.mark_people_search_complete(company['company_id'], len(people))
        else:
            print(f"  ✗ Error: {result.get('error', 'Unknown error')}")
            # Still mark as searched to avoid infinite retries
            db.mark_people_search_complete(company['company_id'], 0)
        
        time.sleep(1.5)
    
    print(f"\n✅ People search complete!")

def enrich_people(client: ApolloClient, db: DatabaseService, reveal_contacts: bool = False, webhook_url: Optional[str] = None):
    """
    Enrich people who haven't been enriched yet
    Uses cache - only enriches if enriched=FALSE
    """
    print(f"\n=== ENRICHING PEOPLE ===")
    
    # Get people that need enrichment
    people_to_enrich = db.get_unenriched_people()
    
    if not people_to_enrich:
        print("✅ All people already enriched!")
        return
    
    print(f"Found {len(people_to_enrich)} people to enrich")
    
    if reveal_contacts:
        print(f"📞 Phone numbers will be sent to: {webhook_url}")
        print(f"⚠️  This will use API credits!")
    
    # Batch process (10 per batch - API limit)
    batch_size = 10
    batches = [people_to_enrich[i:i + batch_size] for i in range(0, len(people_to_enrich), batch_size)]
    
    for idx, batch in enumerate(batches, 1):
        print(f"\nBatch {idx}/{len(batches)}: {len(batch)} people")
        
        # Use Apollo IDs for matching
        match_details = [{"id": person["apollo_id"]} for person in batch]
        
        result = client.people_bulk_match(
            people=match_details,
            reveal_personal_emails=reveal_contacts,
            reveal_phone_number=reveal_contacts,
            webhook_url=webhook_url if reveal_contacts else None
        )
        
        if "error" not in result and "matches" in result:
            for match_data in result["matches"]:
                if match_data:
                    apollo_id = match_data.get('id')
                    db.update_person_enrichment(apollo_id, match_data)
                    
                    email_status = "✓" if match_data.get('email') else "✗"
                    phone_status = "✓" if match_data.get('phone_numbers') else "✗"
                    print(f"  {match_data['first_name']} {match_data['last_name']}: Email {email_status} | Phone {phone_status}")
        else:
            print(f"  ✗ Error in batch: {result.get('error', 'Unknown error')}")
        
        time.sleep(2)
    
    print(f"\n✅ People enrichment complete!")

def main():
    """Main orchestration with database caching"""
    print("Apollo Lead Engine Starting...")
    
    # Initialize services
    client = ApolloClient(api_key=APOLLO_API_KEY)
    db = DatabaseService()  # Uses database instead of LocalDataStore
    
    # Load titles
    titles = load_titles()
    
    print(f"\n📊 Configuration:")
    stats = db.get_stats()
    print(f"  Total Companies: {stats['total_companies']}")
    print(f"  Enriched Companies: {stats['enriched_companies']}")
    print(f"  Total People: {stats['total_people']}")
    print(f"  Target titles: {len(titles)}")
    
    # PHASE 1: Enrich companies (only unenriched ones)
    enrich_companies(client, db)
    
    # PHASE 2: Search for people (only companies needing search)
    search_people(client, db, titles, people_per_company=5)
    
    # PHASE 3: Enrich people (only unenriched ones)
    enrich_people(client, db, reveal_contacts=True, webhook_url=WEBHOOK_URL)
    
    # Final statistics
    print("\n" + "="*50)
    print("FINAL STATISTICS")
    print("="*50)
    stats = db.get_stats()
    for key, value in stats.items():
        print(f"  {key.replace('_', ' ').title()}: {value}")
    
    print("\n✅ All done!")

if __name__ == "__main__":
    main()