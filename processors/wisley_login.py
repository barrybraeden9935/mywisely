import os 
import json 
from adspower import AdsPowerManager
from analyzer.analyzer import Analyzer

class WisleyLogin:
    def __init__(self, rdp_id, thread_id, email_record, user_record):
        self.rdp_id = rdp_id
        self.thread_id = thread_id
        self.email_record = email_record
        self.user_record = user_record
        self.profile_id = self.email_record.get('profile_id')
        if not self.profile_id:
            raise Exception(f"No profile ID found for email row {self.email_record}")

        self.adspower = AdsPowerManager()
        self.analyzer = Analyzer()

    def login(self,):
        self.browser_info = self.adspower.launch_browser(self.profile_id)

        page_loaded = self.analyzer.wait_for_page_load()
        if not page_loaded:
            return
        


