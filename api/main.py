from fastapi import FastAPI, HTTPException
from typing import List
import sys
from pathlib import Path
from datetime import datetime
import os
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

from services.apollo_client import ApolloClient
from services.database_service import DatabaseService
# Import the main enrichment functions
from main import enrich_companies, search_people, enrich_people, load_titles

app = FastAPI(title="LeadEngine API", version="1.0.0")

# Initialize services
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")
apollo_client = ApolloClient(api_key=APOLLO_API_KEY)
db = DatabaseService()

# Load default titles
DEFAULT_TITLES = load_titles()


@app.get("/enrich/custom")
async def enrich_custom(
    domains: str,
    titles: str,
    max_results: int = 10
):
    """
    Enrich companies with custom domains, titles, and search limit.
    Returns enriched people data. All data is cached in the database.
    
    Parameters:
    - domains: Comma-separated list of domains (e.g., "judo.bank,prospa.com")
    - titles: Comma-separated list of titles (e.g., "CTO,VP Engineering")
    - max_results: Maximum number of people per company (default: 10)
    
    Example:
    /enrich/custom?domains=judo.bank,prospa.com&titles=CTO,VP Engineering&max_results=20
    """
    try:
        # Parse comma-separated inputs
        domain_list = [d.strip() for d in domains.split(',')]
        title_list = [t.strip() for t in titles.split(',')]
        
        # Step 1: Add companies to database if they don't exist
        for domain in domain_list:
            company = db.get_company_by_domain(domain)
            if not company:
                conn = db._get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO companies (domain, created_at, updated_at)
                    VALUES (?, ?, ?)
                ''', (domain, datetime.now().isoformat(), datetime.now().isoformat()))
                conn.commit()
                conn.close()
        
        # Step 2: Enrich companies using the existing function
        enrich_companies(apollo_client, db, use_cache=True)
        
        # Step 3: Search for people using the existing function
        search_people(apollo_client, db, title_list, people_per_company=max_results, use_cache=True)
        
        # Step 4: Enrich people using the existing function
        enrich_people(apollo_client, db, reveal_contacts=True, use_cache=True)
        
        # Step 5: Get all enriched people data
        people_list = []
        total_people = 0
        
        for domain in domain_list:
            company = db.get_company_by_domain(domain)
            if company:
                conn = db._get_connection()
                conn.row_factory = lambda cursor, row: {
                    col[0]: row[idx] for idx, col in enumerate(cursor.description)
                }
                people = conn.execute('''
                    SELECT * FROM people 
                    WHERE company_id = ? AND enriched = TRUE
                    ORDER BY updated_at DESC
                    LIMIT ?
                ''', (company['company_id'], max_results)).fetchall()
                conn.close()
                
                total_people += len(people)
                
                for person in people:
                    people_list.append({
                        "first_name": person['first_name'],
                        "last_name": person['last_name'],
                        "title": person['title'],
                        "company": person['company_name'],
                        "email": person['email'],
                        "phone": person['phone'],
                        "linkedin_url": person['linkedin_url'],
                        "city": person['city'],
                        "state": person['state'],
                        "country": person['country'],
                        "location": ', '.join(filter(None, [person['city'], person['state'], person['country']]))
                    })
        
        return {
            "companies_processed": len(domain_list),
            "people_found": total_people,
            "people": people_list
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/enrich/default")
async def enrich_default():
    """
    Run enrichment with default financial services companies and titles.
    Uses companies from data/companies.json and default IT leadership titles.
    Returns all enriched people data. All data is cached in the database.
    
    No input required - just call this endpoint.
    """
    try:
        # Step 1: Enrich companies using the existing function
        enrich_companies(apollo_client, db, use_cache=True)
        
        # Step 2: Search for people using the existing function
        search_people(apollo_client, db, DEFAULT_TITLES, people_per_company=10, use_cache=True)
        
        # Step 3: Enrich people using the existing function
        enrich_people(apollo_client, db, reveal_contacts=True, use_cache=True)
        
        # Step 4: Get all enriched people
        conn = db._get_connection()
        conn.row_factory = lambda cursor, row: {
            col[0]: row[idx] for idx, col in enumerate(cursor.description)
        }
        all_people = conn.execute('''
            SELECT * FROM people WHERE enriched = TRUE
            ORDER BY updated_at DESC
        ''').fetchall()
        
        all_companies = conn.execute('SELECT COUNT(*) as count FROM companies').fetchone()
        conn.close()
        
        people_list = []
        for person in all_people:
            people_list.append({
                "first_name": person['first_name'],
                "last_name": person['last_name'],
                "title": person['title'],
                "company": person['company_name'],
                "email": person['email'],
                "phone": person['phone'],
                "linkedin_url": person['linkedin_url'],
                "city": person['city'],
                "state": person['state'],
                "country": person['country'],
                "location": ', '.join(filter(None, [person['city'], person['state'], person['country']]))
            })
        
        return {
            "companies_processed": all_companies['count'],
            "people_found": len(people_list),
            "people": people_list
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))