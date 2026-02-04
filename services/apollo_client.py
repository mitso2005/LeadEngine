from dotenv import load_dotenv
import os
import requests
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import time

load_dotenv()
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")

class ApolloClient:
    BASE_URL = "https://api.apollo.io/api/v1"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Cache-Control": "no-cache",
            "Content-Type": "application/json",
            "accept": "application/json",
            "x-api-key": api_key
        }
        self.rate_limit_delay = 1.0  # seconds between requests
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict:
        """Make API request with rate limiting and error handling"""
        url = f"{self.BASE_URL}/{endpoint}"
        
        try:
            time.sleep(self.rate_limit_delay)  # Rate limiting
            
            if method.upper() == "GET":
                response = requests.get(url, headers=self.headers, params=params)
            else:
                response = requests.post(url, headers=self.headers, json=data, params=params)
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            print(f"API Error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return {"error": str(e)}
    
    # ==================== ORGANIZATION ENRICHMENT ====================
    
    def org_enrich(self, domain: str) -> Dict:
        """
        Enrich a single organization by domain
        
        Args:
            domain: Company domain (e.g., "judo.bank")
        
        Returns:
            Dict containing organization data
        """
        return self._make_request("GET", "organizations/enrich", params={"domain": domain})
    
    def org_bulk_enrich(self, domains: List[str]) -> Dict:
        """
        Bulk enrich multiple organizations (up to 10 per request)
        
        Args:
            domains: List of company domains
        
        Returns:
            Dict containing bulk enrichment results
        """
        data = {"domains": domains}
        return self._make_request("POST", "organizations/bulk_enrich", data=data)
    
    # ==================== PEOPLE SEARCH ====================
    
    def people_search(self, 
                     organization_domains: Optional[List[str]] = None,
                     person_titles: Optional[List[str]] = None,
                     person_seniorities: Optional[List[str]] = None,
                     page: int = 1,
                     per_page: int = 10,
                     **kwargs) -> Dict:
        """
        Search for people with filters
        
        Args:
            organization_domains: List of company domains to filter by
            person_titles: List of job titles to filter by
            person_seniorities: List of seniorities (e.g., ["director", "vp", "cxo"])
            page: Page number for pagination
            per_page: Results per page (default 10, max 100)
            **kwargs: Additional filters (see Apollo API docs)
        
        Returns:
            Dict containing search results
        """
        data = {
            "page": page,
            "per_page": per_page,
        }
        
        if organization_domains:
            data["organization_domains"] = organization_domains
        
        if person_titles:
            data["person_titles"] = person_titles
        
        if person_seniorities:
            data["person_seniorities"] = person_seniorities
        
        # Add any additional filters
        data.update(kwargs)
        
        return self._make_request("POST", "mixed_people/search", data=data)
    
    # ==================== PEOPLE ENRICHMENT ====================
    
    def people_match(self, 
                    first_name: Optional[str] = None,
                    last_name: Optional[str] = None,
                    organization_name: Optional[str] = None,
                    domain: Optional[str] = None,
                    email: Optional[str] = None,
                    linkedin_url: Optional[str] = None,
                    reveal_personal_emails: bool = False,
                    reveal_phone_number: bool = False) -> Dict:
        """
        Match and enrich a single person
        
        Args:
            first_name: Person's first name
            last_name: Person's last name
            organization_name: Company name
            domain: Company domain
            email: Person's email
            linkedin_url: Person's LinkedIn URL
            reveal_personal_emails: Whether to reveal personal emails (uses credits)
            reveal_phone_number: Whether to reveal phone numbers (uses credits)
        
        Returns:
            Dict containing person data
        """
        params = {
            "reveal_personal_emails": str(reveal_personal_emails).lower(),
            "reveal_phone_number": str(reveal_phone_number).lower()
        }
        
        data = {}
        if first_name:
            data["first_name"] = first_name
        if last_name:
            data["last_name"] = last_name
        if organization_name:
            data["organization_name"] = organization_name
        if domain:
            data["domain"] = domain
        if email:
            data["email"] = email
        if linkedin_url:
            data["linkedin_url"] = linkedin_url
        
        return self._make_request("POST", "people/match", data=data, params=params)
    
    def people_bulk_match(self, 
                         people: List[Dict],
                         reveal_personal_emails: bool = False,
                         reveal_phone_number: bool = False) -> Dict:
        """
        Bulk match and enrich multiple people (up to 10 per request)
        
        Args:
            people: List of person objects with matching criteria
                   Each dict can contain: first_name, last_name, organization_name, 
                   domain, email, linkedin_url
            reveal_personal_emails: Whether to reveal personal emails (uses credits)
            reveal_phone_number: Whether to reveal phone numbers (uses credits)
        
        Returns:
            Dict containing bulk match results
        """
        params = {
            "reveal_personal_emails": str(reveal_personal_emails).lower(),
            "reveal_phone_number": str(reveal_phone_number).lower()
        }
        
        data = {"details": people}
        
        return self._make_request("POST", "people/bulk_match", data=data, params=params)