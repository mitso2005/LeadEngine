import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

class LocalDataStore:
    """
    Local JSON-based storage that mirrors PostgreSQL schema for easy migration
    """
    
    def __init__(self, data_dir: str = "apollo_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Initialize storage files
        self.companies_file = self.data_dir / "companies.json"
        self.people_file = self.data_dir / "people.json"
        self.searches_file = self.data_dir / "searches.json"
        
        self._init_files()
    
    def _init_files(self):
        """Initialize JSON files if they don't exist"""
        for file in [self.companies_file, self.people_file, self.searches_file]:
            if not file.exists():
                file.write_text(json.dumps([], indent=2))
    
    def _read_json(self, filepath: Path) -> List[Dict]:
        """Read JSON file, handling empty files."""
        try:
            # Check if file is empty
            if filepath.stat().st_size == 0:
                return []
            with open(filepath, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            # If file is corrupted or doesn't exist, return empty list
            return []
    
    def _write_json(self, filepath: Path, data: List[Dict]):
        """Write JSON file"""
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    # ==================== COMPANIES ====================
    
    def save_company(self, domain: str, apollo_data: Dict):
        """
        Save or update company data with detailed fields.
        """
        companies = self._read_json(self.companies_file)
        
        # Check if company exists
        existing_idx = None
        for idx, comp in enumerate(companies):
            if comp['domain'] == domain:
                existing_idx = idx
                break
        
        # Apollo returns organization data at the top level, not nested
        org = apollo_data
        
        # Extract departmental headcounts
        dept_headcount = org.get("departmental_head_count", {})
        engineering_headcount = dept_headcount.get("engineering", 0) if dept_headcount else 0
        it_headcount = dept_headcount.get("information_technology", 0) if dept_headcount else 0
        
        company_record = {
            "domain": domain,
            "apollo_id": org.get("id"),  # Apollo organization ID for people search
            "name": org.get("name"),
            "company_phone": org.get("phone"),
            "industry": org.get("industry"),
            "keywords": org.get("keywords"),
            "estimated_num_employees": org.get("estimated_num_employees"),
            "raw_address": org.get("raw_address"),
            "city": org.get("city"),
            "short_description": org.get("short_description"),
            "annual_revenue": org.get("organization_revenue"),
            "engineering_headcount": engineering_headcount,
            "information_technology_headcount": it_headcount,
            "departmental_headcount": dept_headcount,  # Store full dict for reference
            "total_funding": org.get("total_funding"),
            "funding_events": org.get("funding_events"),
            "raw_apollo_data": apollo_data,  # Store the full response for future use
            "updated_at": datetime.now().isoformat()
        }
        
        if existing_idx is not None:
            # Update existing record
            companies[existing_idx].update(company_record)
        else:
            # Add new record
            company_record["created_at"] = datetime.now().isoformat()
            companies.append(company_record)
        
        self._write_json(self.companies_file, companies)
        return company_record
    
    def get_company(self, domain: str) -> Optional[Dict]:
        """Get company by domain"""
        companies = self._read_json(self.companies_file)
        for comp in companies:
            if comp['domain'] == domain:
                return comp
        return None
    
    def get_all_companies(self) -> List[Dict]:
        """Get all companies"""
        return self._read_json(self.companies_file)
    
    # ==================== PEOPLE ====================
    
    def save_person(self, person_data: Dict, company_domain: Optional[str] = None):
        """
        Save or update person data
        """
        people = self._read_json(self.people_file)
        
        apollo_id = person_data.get('id') or person_data.get('person', {}).get('id')
        
        # Check if person exists
        existing_idx = None
        for idx, person in enumerate(people):
            if person.get('apollo_id') == apollo_id:
                existing_idx = idx
                break
        
        person_obj = person_data.get('person', person_data)
        
        person_record = {
            "apollo_id": apollo_id,
            "first_name": person_obj.get('first_name'),
            "last_name": person_obj.get('last_name'),
            "email": person_obj.get('email'),
            "phone_number": person_obj.get('phone_numbers', [{}])[0].get('sanitized_number') if person_obj.get('phone_numbers') else None,
            "title": person_obj.get('title'),
            "seniority": person_obj.get('seniority'),
            "company_domain": company_domain or person_obj.get('organization', {}).get('website_url', '').replace('http://', '').replace('https://', '').split('/')[0],
            "company_name": person_obj.get('organization', {}).get('name'),
            "linkedin_url": person_obj.get('linkedin_url'),
            "raw_apollo_data": person_data,
            "updated_at": datetime.now().isoformat()
        }
        
        if existing_idx is not None:
            people[existing_idx].update(person_record)
        else:
            person_record["created_at"] = datetime.now().isoformat()
            people.append(person_record)
        
        self._write_json(self.people_file, people)
        return person_record
    
    def get_people_by_company(self, domain: str) -> List[Dict]:
        """Get all people from a company"""
        people = self._read_json(self.people_file)
        return [p for p in people if p.get('company_domain') == domain]
    
    def get_all_people(self) -> List[Dict]:
        """Get all people"""
        return self._read_json(self.people_file)
    
    # ==================== SEARCH LOGS ====================
    
    def log_search(self, search_type: str, filters: Dict, results_count: int):
        """Log search queries for tracking API usage"""
        searches = self._read_json(self.searches_file)
        
        search_record = {
            "search_type": search_type,
            "filters": filters,
            "results_count": results_count,
            "timestamp": datetime.now().isoformat()
        }
        
        searches.append(search_record)
        self._write_json(self.searches_file, searches)
        return search_record
    
    # ==================== UTILITY METHODS ====================
    
    def export_to_csv(self, output_dir: str = "exports"):
        """Export all data to CSV files for easy viewing"""
        import pandas as pd
        
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Export companies
        companies = self.get_all_companies()
        if companies:
            # Flatten complex fields for CSV
            companies_flat = []
            for c in companies:
                flat_copy = c.copy()
                # Remove raw data
                flat_copy.pop('raw_apollo_data', None)
                
                # Handle departmental_headcount - ensure it's JSON string for CSV
                dept_headcount = flat_copy.get('departmental_headcount', {})
                if isinstance(dept_headcount, dict):
                    flat_copy['departmental_headcount'] = json.dumps(dept_headcount)
                
                # Flatten other lists/dicts
                for key, value in flat_copy.items():
                    if key not in ['departmental_headcount', 'engineering_headcount', 'information_technology_headcount'] and isinstance(value, (list, dict)):
                        flat_copy[key] = json.dumps(value)
                
                # Reorder columns: put eng/IT headcounts before departmental_headcount, and funding fields at the end
                ordered_copy = {}
                for k, v in flat_copy.items():
                    if k not in ['engineering_headcount', 'information_technology_headcount', 'departmental_headcount', 'total_funding', 'funding_events']:
                        ordered_copy[k] = v
                
                # Add headcount columns in order
                ordered_copy['engineering_headcount'] = flat_copy.get('engineering_headcount', 0)
                ordered_copy['information_technology_headcount'] = flat_copy.get('information_technology_headcount', 0)
                ordered_copy['departmental_headcount'] = flat_copy.get('departmental_headcount')
                ordered_copy['total_funding'] = flat_copy.get('total_funding')
                ordered_copy['funding_events'] = flat_copy.get('funding_events')
                
                companies_flat.append(ordered_copy)
            pd.DataFrame(companies_flat).to_csv(output_path / "companies.csv", index=False)
        
        # Export people
        people = self.get_all_people()
        if people:
            people_flat = []
            for p in people:
                flat_copy = p.copy()
                flat_copy.pop('raw_apollo_data', None)
                people_flat.append(flat_copy)
            pd.DataFrame(people_flat).to_csv(output_path / "people.csv", index=False)
        
        print(f"✅ Exported data to {output_dir}/")
    
    def get_stats(self) -> Dict:
        """Get statistics about stored data"""
        companies = self.get_all_companies()
        people = self.get_all_people()
        
        return {
            "total_companies": len(companies),
            "total_people": len(people),
            "companies_with_data": len([c for c in companies if c.get('estimated_num_employees')]),
            "people_with_email": len([p for p in people if p.get('email')]),
            "people_with_phone": len([p for p in people if p.get('phone_number')])
        }