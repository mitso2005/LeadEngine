import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional
from services.database_service import DatabaseService
import shutil

class WebhookMonitor:
    """
    Monitors webhook_endpoint_data/ folder for phone number files from Apollo API.
    Automatically processes files and updates the database with phone numbers.
    """
    
    def __init__(self, webhook_dir: str = "webhook_endpoint_data", expected_batches: int = 0):
        self.webhook_dir = Path(webhook_dir)
        self.webhook_dir.mkdir(exist_ok=True)
        self.expected_batches = expected_batches
        self.processed_files = set()
        self.db = DatabaseService()
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.total_numbers_added = 0
        self._completion_event = threading.Event()
        
    def set_expected_batches(self, count: int):
        """Update the expected number of batches (called from main.py)"""
        with self.lock:
            self.expected_batches = count
            print(f"Webhook Monitor: Expecting {count} batches")
    
    def start(self):
        """Start monitoring in a background thread"""
        if self.running:
            return
        
        # Clean up any old webhook files from previous runs
        self._cleanup_old_files()
        
        # Reset state for new monitoring session
        with self.lock:
            self.processed_files.clear()
            self.total_numbers_added = 0
        self._completion_event.clear()
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        print("Webhook Monitor: Started listening for phone numbers...")
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        print(f"🛑 Webhook Monitor: Stopped (processed {len(self.processed_files)} files)")
    
    def _monitor_loop(self):
        """Main monitoring loop - runs in background thread"""
        while self.running:
            try:
                self._check_and_process_files()
                time.sleep(1)  # Check every second
            except Exception as e:
                print(f"⚠️  Webhook Monitor Error: {e}")
                time.sleep(2)
    
    def _check_and_process_files(self):
        """Check for new JSON files and process them"""
        json_files = list(self.webhook_dir.glob("*.json"))
        
        # Find new files
        new_files = [f for f in json_files if f not in self.processed_files]
        
        if new_files:
            for file in new_files:
                self._process_file(file)
                with self.lock:
                    self.processed_files.add(file)
            
            # Check if we've received all expected batches
            with self.lock:
                files_processed = len(self.processed_files)
                all_done = self.expected_batches > 0 and files_processed >= self.expected_batches

            if all_done:
                print(f"\n✅ All {files_processed} webhook batches processed!")
                print(f"Total phone numbers added: {self.total_numbers_added}")
                self._completion_event.set()
                self.running = False
                self._cleanup_files()
    
    def _process_file(self, filepath: Path):
        """Process a single webhook JSON file"""
        try:
            with open(filepath, 'r') as f:
                phone_data = json.load(f)
            
            if not isinstance(phone_data, list):
                print(f"⚠️  Invalid format in {filepath.name}")
                return
            
            # Update database with phone numbers
            count = 0
            for entry in phone_data:
                apollo_id = entry.get('id')
                phone_number = entry.get('sanitized_number')
                
                if apollo_id and phone_number:
                    success = self._update_phone_number(apollo_id, phone_number)
                    if success:
                        count += 1
            
            with self.lock:
                self.total_numbers_added += count
            
            print(f"Processed {filepath.name}: {count} phone numbers added ({len(self.processed_files) + 1}/{self.expected_batches if self.expected_batches > 0 else '?'})")
            
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON error in {filepath.name}: {e}")
        except Exception as e:
            print(f"⚠️  Error processing {filepath.name}: {e}")
    
    def _update_phone_number(self, apollo_id: str, phone_number: str) -> bool:
        """Update a person's phone number in the database"""
        try:
            conn = self.db._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE people
                SET phone = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE apollo_id = ?
            ''', (phone_number, apollo_id))
            
            rows_affected = cursor.rowcount
            conn.commit()
            conn.close()
            
            return rows_affected > 0
        except Exception as e:
            print(f"⚠️  Database error for {apollo_id}: {e}")
            return False
    
    def _cleanup_files(self):
        """Remove all processed webhook files"""
        try:
            file_count = len(list(self.webhook_dir.glob("*.json")))
            
            # Delete all JSON files
            for file in self.webhook_dir.glob("*.json"):
                file.unlink()
            
            # Reset tracking
            with self.lock:
                self.processed_files.clear()
                self.expected_batches = 0
            
            print(f"🗑️  Cleaned up {file_count} webhook files")
            
        except Exception as e:
            print(f"⚠️  Cleanup error: {e}")
    
    def _cleanup_old_files(self):
        """Remove old webhook files at startup"""
        try:
            old_files = list(self.webhook_dir.glob("*.json"))
            if old_files:
                for file in old_files:
                    file.unlink()
                print(f"🗑️  Cleaned up {len(old_files)} old webhook files from previous run")
        except Exception as e:
            print(f"⚠️  Old file cleanup error: {e}")
    
    def wait_for_completion(self, timeout: int = 300):
        """
        Wait for all expected batches to be processed
        
        Args:
            timeout: Maximum seconds to wait (default 5 minutes)
        """
        completed = self._completion_event.wait(timeout=timeout)
        if not completed:
            print(f"⏱️  Webhook Monitor: Timeout waiting for batches")
        return completed
