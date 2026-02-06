import json
from pathlib import Path

import requests
from services.apollo_client import ApolloClient, APOLLO_API_KEY
from services.data_store import LocalDataStore
from typing import List, Optional
import time
import os

# Webhook URL for receiving phone numbers from Apollo
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://webhook.site/55dac724-e0b4-458e-8e20-b42ab21fb2b4")

def load_companies() -> dict:
    """Load companies from data/companies.json"""
    companies_file = Path("data/companies.json")
    with open(companies_file, 'r') as f:
        return json.load(f)

def load_titles() -> List[str]:
    """Load titles from data/titles.json"""
    titles_file = Path("data/titles.json")
    with open(titles_file, 'r') as f:
        return json.load(f)

def enrich_companies(client: ApolloClient, store: LocalDataStore, domains: List[str]):
    """
    Enrich companies in batches of 10 (API limit)
    """
    print("\n=== ENRICHING COMPANIES ===")
    
    batch_size = 10
    batches = [domains[i:i + batch_size] for i in range(0, len(domains), batch_size)]
    
    for idx, batch in enumerate(batches, 1):
        print(f"\nBatch {idx}/{len(batches)}: {len(batch)} companies")
        
        # Check cache first
        cached_domains = [d for d in batch if store.get_company(d)]
        new_domains = [d for d in batch if not store.get_company(d)]
        
        if cached_domains:
            print(f"  Found {len(cached_domains)} companies in cache.")
        
        if not new_domains:
            print("  All companies in this batch are already cached.")
            continue

        # Bulk enrich new domains
        print(f"  Enriching {len(new_domains)} new companies...")
        result = client.org_bulk_enrich(new_domains)
        
        if "error" in result:
            print(f"  ✗ API Error: {result['error']}")
            continue
        
        if "organizations" not in result:
            print(f"  ✗ Unexpected response format")
            continue
        
        if "organizations" in result:
            for org_data in result["organizations"]:
                if org_data is None:
                    print(f"  ✗ No data returned for one company in batch")
                    continue

                # The organization data is at the top level, not nested
                domain = org_data.get("primary_domain")
                
                if domain:
                    company = store.save_company(domain, org_data)
                    print(f"  ✓ Saved: {company['name']} ({company.get('estimated_num_employees', 'N/A')} employees)")
                else:
                    print(f"  ✗ No domain found: {org_data.get('name', 'Unknown')}")
        else:
            print(f"  ✗ Error in batch: {result.get('error', 'Unknown error')}")
        
        # Rate limiting between batches
        if idx < len(batches):
            time.sleep(2)
    
    print(f"\n✅ Company enrichment complete!")

def search_people(client: ApolloClient, store: LocalDataStore, domains: List[str], titles: List[str], people_per_company: int = 5):
    """
    Search for people at each company with target titles
    ~120 API calls (40 companies × 5 people each, batched)
    """
    print(f"\n=== SEARCHING FOR PEOPLE ({people_per_company} per company) ===")
    
    all_people = []
    
    for domain in domains:
        company = store.get_company(domain)
        
        if not company:
            print(f"\n⚠️  Skipping {domain} - not enriched yet")
            continue
            
        company_name = company['name']
        apollo_id = company.get('apollo_id')
        
        if not apollo_id:
            print(f"\n⚠️  Skipping {company_name} - no Apollo ID found")
            continue
        
        print(f"\n{company_name} (ID: {apollo_id}):")
        
        # Search for people at this company using organization ID
        result = client.people_search(
            organization_ids=[apollo_id],
            person_titles=titles,
            per_page=people_per_company
        )
        
        # Debug: Check what we got back
        if "error" not in result and "people" in result:
            people = result["people"]
            print(f"  Found {len(people)} people")
            
            # Debug first person to see actual company
            if people and len(people) > 0:
                first_person = people[0]
                actual_company = first_person.get('organization', {}).get('name', 'Unknown')
                if actual_company.lower() != company_name.lower() and actual_company != 'Unknown':
                    print(f"  ⚠️  WARNING: API returned people from '{actual_company}' instead of '{company_name}'!")
            
            for person_data in people:
                person = store.save_person(person_data, domain)
                all_people.append(person)
                print(f"    ✓ {person['first_name']} {person['last_name']} - {person['title']}")
            
            # Log this search
            store.log_search("people_search", {"apollo_id": apollo_id, "titles": titles}, len(people))
        else:
            print(f"  ✗ Error: {result.get('error', 'Unknown error')}")
        
        time.sleep(1.5)  # Rate limiting
    
    print(f"\n✅ Found {len(all_people)} people total!")
    return all_people

def enrich_people(client: ApolloClient, store: LocalDataStore, people: List[dict], reveal_contacts: bool = False, webhook_url: Optional[str] = None):
    """
    Bulk enrich people to get contact details
    ~12 API calls (120 people ÷ 10 per batch)
    WARNING: Setting reveal_contacts=True uses additional credits
    Note: Phone numbers are delivered asynchronously to webhook_url
    """
    print(f"\n=== ENRICHING PEOPLE (reveal_contacts={reveal_contacts}) ===")
    if reveal_contacts and webhook_url:
        print(f"📞 Phone numbers will be sent to: {webhook_url}")
        print(f"⚠️  This will use API credits!")
    elif reveal_contacts:
        print(f"⚠️  This will use API credits!")
    
    batch_size = 10
    batches = [people[i:i + batch_size] for i in range(0, len(people), batch_size)]
    
    for idx, batch in enumerate(batches, 1):
        print(f"\nBatch {idx}/{len(batches)}: {len(batch)} people")
        
        # Prepare bulk match data using Apollo IDs (more reliable than name matching)
        match_details = []
        for person in batch:
            match_details.append({
                "id": person["apollo_id"]  # Use Apollo ID for exact matching
            })
        
        # Bulk match/enrich
        result = client.people_bulk_match(
            people=match_details,
            reveal_personal_emails=reveal_contacts,
            reveal_phone_number=reveal_contacts,
            webhook_url=webhook_url if reveal_contacts else None
        )
        
        if "error" not in result and "matches" in result:
            # Debug: Check first match structure
            if idx == 1 and len(result["matches"]) > 0 and result["matches"][0]:
                first_match = result["matches"][0]
                print(f"  DEBUG - First match keys: {list(first_match.keys())[:15]}")
                print(f"  DEBUG - Has email: {first_match.get('email')}")
                print(f"  DEBUG - Has phone_numbers: {first_match.get('phone_numbers')}")
            
            for match_data in result["matches"]:
                if match_data:  # Some matches may be None
                    person = store.save_person(match_data)
                    email_status = "✓" if person.get('email') else "✗"
                    phone_status = "✓" if person.get('phone_number') else "✗"
                    print(f"  {person['first_name']} {person['last_name']}: Email {email_status} | Phone {phone_status}")
        else:
            print(f"  ✗ Error in batch: {result.get('error', 'Unknown error')}")
        
        time.sleep(2)  # Rate limiting
    
    print(f"\n✅ People enrichment complete!")

'''
def main():
    url = "https://api.apollo.io/api/v1/organizations/enrich?domain=judo.bank"

    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "accept": "application/json",
        "x-api-key": APOLLO_API_KEY
    }

    response = requests.get(url, headers=headers)

    print(response.text)
'''
def main():
    """Main orchestration"""
    print("Apollo Lead Engine Starting...")
    
    # Initialize services
    client = ApolloClient(api_key=APOLLO_API_KEY)
    store = LocalDataStore()
    
    # Load configuration
    companies_dict = load_companies()
    domains = list(companies_dict.values())
    titles = load_titles()
    
    print(f"\n Configuration:")
    print(f"  Companies: {len(domains)}")
    print(f"  Target titles: {len(titles)}")
    
    # PHASE 1: Enrich companies (4 API calls)
    enrich_companies(client, store, domains)
    
    # PHASE 2: Search for people (120 API calls)
    people = search_people(client, store, domains, titles, people_per_company=5)
    
    # PHASE 5: Enrich people (OPTIONAL - 20 API calls + extra credits for contact reveal)
    # Uncomment to enable people enrichment
    enrich_people(client, store, people, reveal_contacts=True, webhook_url=WEBHOOK_URL)
    
    # Show statistics
    print("\n" + "="*50)
    print("FINAL STATISTICS")
    print("="*50)
    stats = store.get_stats()
    for key, value in stats.items():
        print(f"  {key.replace('_', ' ').title()}: {value}")
    
    # Export to CSV
    store.export_to_csv()
    
    print("\n✅ All done! Check apollo_data/ for JSON files and exports/ for CSVs")

if __name__ == "__main__":
    main()