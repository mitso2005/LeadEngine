import json
from pathlib import Path

import requests
from services.apollo_client import ApolloClient, APOLLO_API_KEY
from services.data_store import LocalDataStore
from typing import List
import time

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
'''
def search_people(client: ApolloClient, store: LocalDataStore, domains: List[str], titles: List[str], people_per_company: int = 3):
    """
    Search for people at each company with target titles
    ~120 API calls (40 companies × 3 people each, batched)
    """
    print(f"\n=== SEARCHING FOR PEOPLE ({people_per_company} per company) ===")
    
    all_people = []
    
    for domain in domains:
        company = store.get_company(domain)
        company_name = company['name'] if company else domain
        
        print(f"\n{company_name}:")
        
        # Search for people at this company with target titles
        result = client.people_search(
            organization_domains=[domain],
            person_titles=titles,
            per_page=people_per_company
        )
        
        if "error" not in result and "people" in result:
            people = result["people"]
            print(f"  Found {len(people)} people")
            
            for person_data in people:
                person = store.save_person(person_data, domain)
                all_people.append(person)
                print(f"    ✓ {person['first_name']} {person['last_name']} - {person['title']}")
            
            # Log this search
            store.log_search("people_search", {"domain": domain, "titles": titles}, len(people))
        else:
            print(f"  ✗ Error: {result.get('error', 'Unknown error')}")
        
        time.sleep(1.5)  # Rate limiting
    
    print(f"\n✅ Found {len(all_people)} people total!")
    return all_people

def enrich_people(client: ApolloClient, store: LocalDataStore, people: List[dict], reveal_contacts: bool = False):
    """
    Bulk enrich people to get contact details
    ~12 API calls (120 people ÷ 10 per batch)
    WARNING: Setting reveal_contacts=True uses additional credits
    """
    print(f"\n=== ENRICHING PEOPLE (reveal_contacts={reveal_contacts}) ===")
    
    batch_size = 10
    batches = [people[i:i + batch_size] for i in range(0, len(people), batch_size)]
    
    for idx, batch in enumerate(batches, 1):
        print(f"\nBatch {idx}/{len(batches)}: {len(batch)} people")
        
        # Prepare bulk match data
        match_details = []
        for person in batch:
            match_details.append({
                "first_name": person["first_name"],
                "last_name": person["last_name"],
                "domain": person["company_domain"]
            })
        
        # Bulk match/enrich
        result = client.people_bulk_match(
            people=match_details,
            reveal_personal_emails=reveal_contacts,
            reveal_phone_number=reveal_contacts
        )
        
        if "error" not in result and "matches" in result:
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
    # people = search_people(client, store, domains, titles, people_per_company=3)
    
    # PHASE 3: Enrich people (OPTIONAL - 12 API calls + extra credits for contact reveal)
    # Uncomment to enable people enrichment
    # enrich_people(client, store, people, reveal_contacts=False)
    
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