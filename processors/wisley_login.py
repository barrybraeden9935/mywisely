import os 
import json 
import traceback
from loguru import logger
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
        try:
            logger.info(f"Starting login process for profile {self.profile_id}")
            
            # Update profile with login URL
            logger.debug("Updating profile with login URL")
            self.adspower.update_profile(self.profile_id, ["https://www.mywisely.com/app/main/login/"])
            
            # Launch browser
            logger.debug("Launching browser")
            self.browser_info = self.adspower.launch_browser(self.profile_id)
            
            # Wait for page to load
            logger.info("Waiting for login page to load")
            page_loaded = self.analyzer.wait_for_page_load()
            if not page_loaded:
                logger.error("Login page failed to load")
                raise Exception("Page failed to load")
            
            # Click initial login button (if present)
            logger.debug("Attempting to click initial login button")
            login_button_clicked = self.analyzer.click_element_by_class('LOGIN_BUTTON')
            if not login_button_clicked:
                logger.error("Failed to click initial login button")
                return False
            logger.debug("Successfully clicked initial login button")
            
            # Click username input field
            logger.debug("Clicking username input field")
            username_input_clicked = self.analyzer.click_element_by_class('USERNAME_INPUT')
            if not username_input_clicked:
                logger.error("Failed to click username input field")
                return False
            logger.debug("Successfully clicked username input field")
            
            # Type username
            logger.debug(f"Typing username: {self.user_record['username']}")
            username_typed = self.analyzer.type_text_random(self.user_record['username'])
            if not username_typed:
                logger.error("Failed to type username")
                return False
            logger.debug("Successfully typed username")
            
            # Click password input field
            logger.debug("Clicking password input field")
            password_input_clicked = self.analyzer.click_element_by_class('PASSWORD_INPUT')
            if not password_input_clicked:
                logger.error("Failed to click password input field")
                return False
            logger.debug("Successfully clicked password input field")
            
            # Type password
            logger.debug("Typing password")
            password_typed = self.analyzer.type_text_random(self.user_record['password'])
            if not password_typed:
                logger.error("Failed to type password")
                return False
            logger.debug("Successfully typed password")
            
            # Click final login button
            logger.debug("Clicking final login button")
            final_login_clicked = self.analyzer.click_element_by_class('LOGIN_BUTTON')
            if not final_login_clicked:
                logger.error("Failed to click final login button")
                return False
            logger.debug("Successfully clicked final login button")

            # Click 2FA button
            logger.debug("Clicking 2FA button")
            twofa_button_clicked = self.analyzer.click_element_by_class('EMAIL_2FA_BUTTON')
            if not twofa_button_clicked:
                logger.error("Failed to click 2FA button")
                return False
            logger.debug("Successfully clicked 2FA button")

            # Click 2FA code input field
            logger.debug("Clicking 2FA code input field")
            twofa_input_clicked = self.analyzer.click_element_by_class('2FA_CODE_INPUT')
            if not twofa_input_clicked:
                logger.error("Failed to click 2FA code input field")
                return False
            logger.debug("Successfully clicked 2FA code input field")
            
            # Type 2FA code
            logger.debug("Typing 2FA code")
            twofa_code = ""
            twofa_code_typed = self.analyzer.type_text_random(twofa_code)
            if not twofa_code_typed:
                logger.error("Failed to type 2FA code")
                return False
            logger.debug("Successfully typed 2FA code")

            # Click submit 2FA button
            logger.debug("Clicking submit 2FA button")
            submit_twofa_clicked = self.analyzer.click_element_by_class('SUBMIT_2FA_BUTTON')
            if not submit_twofa_clicked:
                logger.error("Failed to click submit 2FA button")
                return False
            logger.debug("Successfully clicked submit 2FA button")
            
            logger.success(f"Login process completed successfully for profile {self.profile_id}")
            return True
            
        except Exception as e:
            logger.error(f"Login process failed with exception: {str(e)}")
            raise
        
    def login(self):
        try:
            self._login_internal()
        except Exception as e:
            # Capture the full traceback
            error_details = traceback.format_exc()
            print(error_details)
            self.update_output(f"ERROR: {str(e)}")
            self.update_output(f"TRACEBACK: {error_details}")
        
        return self.output