import os 
import json 
import traceback
from loguru import logger
from adspower import AdsPowerManager
from analyzer.analyzer import Analyzer
from processors.gmail_manager import get2FACode

import asyncio
from playwright.async_api import async_playwright



class WisleyLogin:
    def __init__(self, task_repo, rdp_id, thread_id, email_record, user_record):
        self.rdp_id = rdp_id
        self.thread_id = thread_id
        self.email_record = email_record
        self.user_record = user_record
        self.profile_id = self.email_record.get('profile_id')
        self.output = ""
        self.task_repo = task_repo
        if not self.profile_id:
            raise Exception(f"No profile ID found for email row {self.email_record}")
        self.adspower = AdsPowerManager()
        self.analyzer = Analyzer()

    def update_output(self, text):
        self.output += f"{text}\n"

    async def _login_internal(self):
        """Internal login method that can raise exceptions"""
        try:
            self.update_output("🔄 Starting login process...")
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
            
            self.update_output("🔄 Filling step 1 (filling email and password)...")
            
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

            twofa_elements =  self.analyzer.detect_elements(0.8)
            needs_twofa = len(twofa_elements) >= 2

            if needs_twofa:
                self.update_output("🔄 Filling step 2 (filling 2fa)...")
                
                success, twofa_code = await get2FACode(self.task_repo, self.email_record['email'], 
                    self.thread_id, self.email_record['master_email'], self.rdp_id
                )

                if not success:
                    logger.error(f"Failed to fetch 2FA code from gmail API - {twofa_code}")
                    return False

                # Click 2FA code input field
                logger.debug("Clicking 2FA code input field")
                twofa_input_clicked = self.analyzer.click_element_by_class('2FA_CODE_INPUT')
                if not twofa_input_clicked:
                    logger.error("Failed to click 2FA code input field")
                    return False
                logger.debug("Successfully clicked 2FA code input field")
                
                # Type 2FA code
                logger.debug("Typing 2FA code")
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
            else:
                self.update_output("✉️ 2FA not required")
                
            logger.success(f"Login process completed successfully for profile {self.profile_id}")

            self.update_output("🔄 Getting balance...")
            main_balance, savings_balance = await self.get_balance_info_async(self.browser_info.ws['puppeteer'])
            self.update_output(f"💸 Balance: {main_balance}")
            self.update_output(f"💸 Savings balance: {savings_balance}")
            return True
            
        except Exception as e:
            logger.error(f"Login process failed with exception: {str(e)}")
            raise

    async def connect_browser(self, playwright_ws: str):
        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.connect_over_cdp(playwright_ws)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()
            
            return browser, page, playwright
            
        except Exception as e:
            print(f"Failed to connect to browser: {e}")
            raise

    async def get_balance_info_async(self, playwright_ws: str):
        browser, page, playwright = await self.connect_browser(playwright_ws)
        
        try:
            main_balance_text = await page.locator('[data-e2eauto="balance"]').inner_text()
            
            await page.goto("https://www.mywisely.com/app/main/future")
            savings_text = await page.locator('[data-e2eauto="totalEnvelopeSavingsCurrency"]').inner_text()
            
            return main_balance_text, savings_text
            
        finally:
            self.adspower.close_browser(self.profile_id)

    async def login(self):
        try:
            await self._login_internal()
            return self.output
        except Exception as e:
            # Capture the full traceback
            error_details = traceback.format_exc()
            print(error_details)
            self.update_output(f"ERROR: {str(e)}")
            self.update_output(f"TRACEBACK: {error_details}")
        
        return self.output