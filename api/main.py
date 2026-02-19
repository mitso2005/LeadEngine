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
from services.webhook_monitor import WebhookMonitor
# Import the main enrichment functions
from main import enrich_companies, search_people, enrich_people, load_titles

app = FastAPI(title="LeadEngine API", version="1.0.0")

# Initialize services
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
apollo_client = ApolloClient(api_key=APOLLO_API_KEY)
db = DatabaseService()
webhook_monitor = WebhookMonitor() if WEBHOOK_URL else None

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
        
        # Step 2: Start webhook monitor if available
        if webhook_monitor:
            webhook_monitor.start()
        
        # Step 3: Enrich companies using the existing function
        enrich_companies(apollo_client, db, use_cache=True)
        
        # Step 4: Search for people - smart caching based on titles
        # Only search companies that haven't been searched with these specific titles
        for domain in domain_list:
            company = db.get_company_by_domain(domain)
            if not company or not company.get('apollo_id'):
                continue
            
            # Check if we need to search for these titles
            if db.needs_title_search(company['company_id'], title_list):
                print(f"Searching {company['name']} for new titles: {title_list}")
                
                result = apollo_client.people_search(
                    organization_ids=[company['apollo_id']],
                    person_titles=title_list,
                    per_page=max_results,
                    person_locations=["Australia"]
                )
                
                if "error" not in result and "people" in result:
                    people = result["people"]
                    print(f"  Found {len(people)} people")
                    
                    for person_data in people:
                        person = db.save_person(company['company_id'], person_data)
                        print(f"    ✓ {person['first_name']} {person.get('last_name', '')} - {person['title']}")
                    
                    # Mark search as complete with these titles
                    db.mark_people_search_complete(company['company_id'], len(people), title_list)
                else:
                    print(f"  ✗ Error: {result.get('error', 'Unknown error')}")
                    db.mark_people_search_complete(company['company_id'], 0, title_list)
            else:
                print(f"✓ Using cached results for {company['name']} - titles already searched")
        
        # Step 5: Enrich people using the existing function
        enrich_people(apollo_client, db, reveal_contacts=True, webhook_url=WEBHOOK_URL, webhook_monitor=webhook_monitor, use_cache=True)
        
        # Step 6: Wait for webhook monitor to finish processing phone numbers
        if webhook_monitor and webhook_monitor.expected_batches > 0:
            print("⏳ Waiting for webhook phone numbers...")
            webhook_monitor.wait_for_completion(timeout=120)
            webhook_monitor.stop()
        
        # Step 7: Get all enriched people data
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
        # Step 1: Start webhook monitor if available
        if webhook_monitor:
            webhook_monitor.start()
        
        # Step 2: Enrich companies using the existing function
        enrich_companies(apollo_client, db, use_cache=True)
        
        # Step 3: Search for people using the existing function
        search_people(apollo_client, db, DEFAULT_TITLES, people_per_company=10, use_cache=True)
        
        # Step 4: Enrich people using the existing function
        enrich_people(apollo_client, db, reveal_contacts=True, webhook_url=WEBHOOK_URL, webhook_monitor=webhook_monitor, use_cache=True)
        
        # Step 5: Wait for webhook monitor to finish processing phone numbers
        if webhook_monitor.expected_batches > 0:
            print("\n⏳ Waiting for all webhook phone numbers to be processed...")
            webhook_monitor.wait_for_completion(timeout=120)
        
        # Stop webhook monitor
        webhook_monitor.stop()
        
        # Step 6: Get all enriched people
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


@app.get("/")
async def root():
    """Health check and API information"""
    return {
        "status": "healthy",
        "service": "LeadEngine API",
        "version": "1.0.0",
        "endpoints": {
            "GET /enrich/custom": "Enrich with custom domains, titles, and max results",
            "POST /enrich/default": "Enrich with default financial services data",
            "GET /stats": "Get database statistics",
            "GET /people": "Get all people from database",
            "GET /companies": "Get all companies from database",
            "DELETE /companies?domain=example.com": "Delete a company and all its people"
        }
    }


@app.get("/stats")
async def get_stats():
    """Get current database statistics"""
    conn = db._get_connection()
    stats = conn.execute('''
        SELECT 
            (SELECT COUNT(*) FROM companies) as total_companies,
            (SELECT COUNT(*) FROM companies WHERE enriched = TRUE) as enriched_companies,
            (SELECT COUNT(*) FROM people) as total_people,
            (SELECT COUNT(*) FROM people WHERE enriched = TRUE) as enriched_people
    ''').fetchone()
    conn.close()
    
    return {
        "total_companies": stats[0],
        "enriched_companies": stats[1],
        "total_people": stats[2],
        "enriched_people": stats[3]
    }


@app.get("/people")
async def get_all_people():
    """Get all people from the database"""
    try:
        conn = db._get_connection()
        conn.row_factory = lambda cursor, row: {
            col[0]: row[idx] for idx, col in enumerate(cursor.description)
        }
        people = conn.execute('''
            SELECT * FROM people
            ORDER BY updated_at DESC
        ''').fetchall()
        conn.close()
        
        return {
            "count": len(people),
            "people": people
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/companies")
async def get_all_companies():
    """Get all companies from the database"""
    try:
        conn = db._get_connection()
        conn.row_factory = lambda cursor, row: {
            col[0]: row[idx] for idx, col in enumerate(cursor.description)
        }
        companies = conn.execute('''
            SELECT * FROM companies
            ORDER BY updated_at DESC
        ''').fetchall()
        conn.close()
        
        return {
            "count": len(companies),
            "companies": companies
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/companies")
async def delete_company(domain: str):
    """Delete a company and all associated people by domain (query parameter version)"""
    try:
        # Get company
        company = db.get_company_by_domain(domain)
        if not company:
            raise HTTPException(status_code=404, detail=f"Company with domain '{domain}' not found")
        
        conn = db._get_connection()
        cursor = conn.cursor()
        
        # Delete all people associated with this company
        cursor.execute('DELETE FROM people WHERE company_id = ?', (company['company_id'],))
        people_deleted = cursor.rowcount
        
        # Delete the company
        cursor.execute('DELETE FROM companies WHERE company_id = ?', (company['company_id'],))
        
        conn.commit()
        conn.close()
        
        return {
            "message": f"Successfully deleted company '{company.get('name', domain)}'",
            "domain": domain,
            "people_deleted": people_deleted
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))