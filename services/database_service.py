import sqlite3
import os
from typing import Dict, List, Optional
from datetime import datetime

class DatabaseService:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'database.db')
        self.db_path = db_path
    
    def _get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    # ==================== COMPANY METHODS ====================
    
    def get_company_by_domain(self, domain: str) -> Optional[Dict]:
        """Get company from cache by domain"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM companies WHERE domain = ?
        ''', (domain,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_unenriched_companies(self) -> List[Dict]:
        """Get all companies that haven't been enriched yet"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM companies WHERE enriched = FALSE
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    # Replace the save_company_enrichment method:
    def save_company_enrichment(self, domain: str, apollo_data: Dict) -> Dict:
        """Save enriched company data from Apollo"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Extract department headcounts from departmental_head_count dict
        engineering_headcount = 0
        it_headcount = 0
        
        dept_headcount = apollo_data.get('departmental_head_count', {})
        if dept_headcount:
            engineering_headcount = dept_headcount.get('engineering', 0)
            it_headcount = dept_headcount.get('information_technology', 0)
        
        cursor.execute('''
            UPDATE companies 
            SET apollo_id = ?,
                industry = ?,
                city = ?,
                address = ?,
                annual_revenue = ?,
                employee_count = ?,
                engineering_headcount = ?,
                it_headcount = ?,
                short_description = ?,
                enriched = TRUE,
                updated_at = CURRENT_TIMESTAMP
            WHERE domain = ?
        ''', (
            apollo_data.get('id'),
            apollo_data.get('industry'),
            apollo_data.get('city'),
            apollo_data.get('raw_address'),
            apollo_data.get('organization_revenue'),
            apollo_data.get('estimated_num_employees'),
            engineering_headcount,
            it_headcount,
            apollo_data.get('short_description'),
            domain
        ))
        
        conn.commit()
        conn.close()
        
        return self.get_company_by_domain(domain)
    
    def get_companies_needing_people_search(self) -> List[Dict]:
        """Get companies that need people search (not searched OR found < 5 people)"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        ''' Can change this to:
            SELECT * FROM companies 
            WHERE enriched = TRUE 
            AND (people_searched = FALSE or people_found_count < 10)

            if we want to re-search companies that had few people found 
            the first time or change the number of people found threshold
        '''
        cursor.execute('''
            SELECT * FROM companies 
            WHERE enriched = TRUE 
            AND (people_searched = FALSE)
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def mark_people_search_complete(self, company_id: int, people_count: int):
        """Mark that people search was completed for a company"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE companies
            SET people_searched = TRUE,
                people_found_count = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE company_id = ?
        ''', (people_count, company_id))
        
        conn.commit()
        conn.close()
    
    # ==================== PEOPLE METHODS ====================

    def save_person(self, company_id: int, apollo_data: Dict) -> Dict:
        """Save person from Apollo search results"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR IGNORE INTO people (
                company_id, apollo_id, first_name, last_name, 
                company_name, title, enriched
            ) VALUES (?, ?, ?, ?, ?, ?, FALSE)
        ''', (
            company_id,
            apollo_data.get('id'),
            apollo_data.get('first_name'),
            apollo_data.get('last_name'),
            apollo_data.get('organization', {}).get('name'),
            apollo_data.get('title')
        ))
        
        conn.commit()
        conn.close()
        
        return self.get_person_by_apollo_id(apollo_data.get('id'))
    
    def get_unenriched_people(self) -> List[Dict]:
        """Get all people that haven't been enriched yet"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM people WHERE enriched = FALSE
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]

    # Replace the update_person_enrichment method:
    def update_person_enrichment(self, apollo_id: str, apollo_data: Dict):
        """Update person with enriched data (email, phone, LinkedIn, last_name)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Extract phone number from phone_numbers array if present
        phone = None
        if apollo_data.get('phone_numbers'):
            phone = apollo_data['phone_numbers'][0].get('sanitized_number')
        
        cursor.execute('''
            UPDATE people
            SET last_name = ?,
                email = ?,
                phone = ?,
                linkedin_url = ?,
                enriched = TRUE,
                updated_at = CURRENT_TIMESTAMP
            WHERE apollo_id = ?
        ''', (
            apollo_data.get('last_name'),
            apollo_data.get('email'),
            phone,
            apollo_data.get('linkedin_url'),
            apollo_id
        ))
        
        conn.commit()
        conn.close()

    def get_person_by_apollo_id(self, apollo_id: str) -> Optional[Dict]:
        """Get person by Apollo ID"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM people WHERE apollo_id = ?
        ''', (apollo_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    # ==================== STATS ====================
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM companies')
        total_companies = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM companies WHERE enriched = TRUE')
        enriched_companies = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM companies WHERE people_searched = TRUE')
        searched_companies = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM people')
        total_people = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM people WHERE enriched = TRUE')
        enriched_people = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_companies': total_companies,
            'enriched_companies': enriched_companies,
            'searched_companies': searched_companies,
            'total_people': total_people,
            'enriched_people': enriched_people
        }