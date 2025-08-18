import os 
import json 
import traceback
from adspower import AdsPowerManager
from analyzer.analyzer import Analyzer

class WisleyLogin:
    def __init__(self, rdp_id, thread_id, email_record, user_record):
        self.rdp_id = rdp_id
        self.thread_id = thread_id
        self.email_record = email_record
        self.user_record = user_record
        self.profile_id = self.email_record.get('profile_id')
        self.output = ""
        if not self.profile_id:
            raise Exception(f"No profile ID found for email row {self.email_record}")
        self.adspower = AdsPowerManager()
        self.analyzer = Analyzer()

    def update_output(self, text):
        self.output += f"{text}\n"

    def _login_internal(self):
        """Internal login method that can raise exceptions"""
        self.browser_info = self.adspower.launch_browser(self.profile_id)
        page_loaded = self.analyzer.wait_for_page_load()
        if not page_loaded:
            raise Exception(f"Page failed to load")
        # Add your other login logic here...
        
    def login(self):
        try:
            self._login_internal()
        except Exception as e:
            # Capture the full traceback
            error_details = traceback.format_exc()
            self.update_output(f"ERROR: {str(e)}")
            self.update_output(f"TRACEBACK: {error_details}")
        
        return self.output