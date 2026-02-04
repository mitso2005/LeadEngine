import os
from services.apollo_client import ApolloClient, APOLLO_API_KEY

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
    
    print(f"\nConfiguration:")
    print(f"  Companies: {len(domains)}")
    print(f"  Target titles: {len(titles)}")
    
    # PHASE 1: Enrich companies (4 API calls)
    enrich_companies(client, store, domains)
    
    # PHASE 2: Search for people (120 API calls)
    people = search_people(client, store, domains, titles, people_per_company=3)
    
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