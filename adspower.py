import random
import string
import logging
import time
import json
from typing import Dict, List, Optional, Any
import requests
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProxyConfig:
    proxy_type: str
    proxy_host: str
    proxy_port: int
    proxy_username: str
    proxy_password: str
    username: Optional[str] = None


@dataclass
class BrowserInfo:
    ws: Dict[str, str]  


class AdsPowerManager:
    def __init__(self, api_url: str = "http://local.adspower.net:50325"):
        self.api_url = api_url
        self.proxy: Optional[ProxyConfig] = None
        self.active_browsers: Dict[str, BrowserInfo] = {}
        self.session: Optional[requests.Session] = None

    def __enter__(self):
        self.session = requests.Session()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            self.session.close()

    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        if not self.session:
            self.session = requests.Session()
            
        url = f"{self.api_url}{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = self.session.get(
                    url, 
                    params=params,
                    headers={"Content-Type": "application/json"}
                )
            elif method.upper() == "POST":
                response = self.session.post(
                    url, 
                    json=data,
                    params=params,
                    headers={"Content-Type": "application/json"}
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Request failed for {method} {url}: {e}")
            raise

    def update_profile(self, profile_id: str, open_urls: list = []) -> bool:
        try:
            data = {
                "user_id": profile_id
            }

            if len(open_urls) > 0:
                data['open_urls'] = open_urls
            
            print(data)
            response = self._make_request("POST", "/api/v1/user/update", data)
            print(response)
            if response.get("code") == 0:
                logger.info(f"Successfully updated profile: {profile_id}")
                return True
            else:
                logger.error(f"Error updating profile: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating profile {profile_id}: {e}")
            return False

    def delete_profile(self, profile_id: str) -> bool:
        try:
            data = {"user_ids": [profile_id]}
            response = self._make_request("POST", "/api/v1/user/delete", data)
            
            if response.get("code") == 0:
                logger.info(f"Successfully deleted profile: {profile_id}")
                return True
            else:
                logger.error(f"Error deleting profile: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting profile {profile_id}: {e}")
            return False

    def get_proxy(self) -> Optional[ProxyConfig]:
        return self.proxy

    def _generate_random_string(self, length: int = 13) -> str:
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def create_profile(
        self, 
        proxy: Optional[ProxyConfig] = None, 
        starting_url: str = "https://www.mywisely.com"
    ) -> Optional[Dict]:
        try:
            if not proxy:
                raise ValueError("Proxy configuration is required")
            else:
                self.proxy = proxy

            if not self.proxy:
                logger.error("No proxy configuration available")
                return None

            if self.proxy.username and "xzxQQzmTHnk1" in self.proxy.username:
                self.proxy.username = self.proxy.username.replace(
                    "xzxQQzmTHnk1", 
                    self._generate_random_string()
                )

            logger.info(f"Creating profile with proxy: {self.proxy.proxy_host}:{self.proxy.proxy_port}")
            logger.info(f"Starting URL: {starting_url}")

            request_body = {
                "group_id": "0",
                "open_urls": [starting_url],
                "fingerprint_config": {
                    "webrtc": "proxy",
                    "random_ua": {
                        "ua_browser": ["chrome"],
                        "ua_system_version": ["Windows 11"]
                    },
                    "canvas": "0",
                    "webgl_image": "0",
                    "audio": "0",
                },
                "user_proxy_config": {
                    "proxy_soft": "other",
                    "proxy_type": self.proxy.proxy_type,
                    "proxy_host": self.proxy.proxy_host,
                    "proxy_port": self.proxy.proxy_port,
                    "proxy_user": self.proxy.proxy_username,
                    "proxy_password": self.proxy.proxy_password
                }
            }

            logger.debug(f"Request body: {request_body}")
            
            response = self._make_request("POST", "/api/v1/user/create", request_body)
            logger.info(f"Create profile response: {response}")
            
            if response.get("code") == -1:
                logger.error("Profile creation failed with code -1")
                return None

            return response.get("data")

        except Exception as e:
            logger.error(f"Error creating profile: {e}")
            return None

    def launch_browser(self, profile_id: str) -> Optional[BrowserInfo]:
        try:
            params = {
                "user_id": profile_id,
                "ip_tab": "0",
                "launch_args": f'["--start-maximized"]',
                "open_tabs": "1",

            }
            
            response = self._make_request("GET", "/api/v1/browser/start", params=params)
            
            if response.get("code") == 0:
                browser_data = response["data"]
                browser_info = BrowserInfo(ws=browser_data.get("ws", {}))
                self.active_browsers[profile_id] = browser_info
                
                logger.info(f"Browser launched successfully for profile: {profile_id}")
                logger.info(f"WebDriver URL: {browser_info.ws.get('puppeteer', 'N/A')}")
                return browser_info
            else:
                logger.error(f"Error launching browser: {response}")
                return None
                
        except Exception as e:
            logger.error(f"Error launching browser for profile {profile_id}: {e}")
            return None

    def close_browser(self, profile_id: str) -> bool:
        try:
            if profile_id not in self.active_browsers:
                logger.warning(f"No active browser found for profile: {profile_id}")
                return False

            data = {"user_id": profile_id}
            response = self._make_request("POST", "/api/v1/browser/stop", data)
            
            if response.get("code") == 0:
                del self.active_browsers[profile_id]
                logger.info(f"Browser closed successfully for profile: {profile_id}")
                return True
            else:
                logger.error(f"Error closing browser: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Error closing browser for profile {profile_id}: {e}")
            return False

    def check_proxy_type(self, profile_id: str, max_retries: int = 3) -> bool:
        for attempt in range(1, max_retries + 1):
            try:
                params = {"user_id": profile_id}
                response = self._make_request("GET", "/api/v1/user/list", params=params)
                
                logger.debug(f"Profile {profile_id} response: {response}")
                
                if response.get("code") != 0:
                    raise Exception("Failed to query profile information")

                profile_list = response.get("data", {}).get("list", [])
                if not profile_list:
                    return False

                proxy_type = (
                    profile_list[0]
                    .get("user_proxy_config", {})
                    .get("proxy_type")
                )
                return proxy_type == "http"

            except Exception as e:
                logger.error(f"Attempt {attempt} failed: {e}")
                
                if attempt < max_retries:
                    delay = random.uniform(1, 5)
                    time.sleep(delay)
                else:
                    return False

        return False

    def get_profiles(self, page: int = 1, page_size: int = 100) -> Optional[List[Dict]]:
        try:
            data = {
                "page": page,
                "page_size": page_size
            }
            
            response = self._make_request("POST", "/api/v1/user/list", data)
            
            if response.get("code") == 0:
                return response.get("data", {}).get("list", [])
            else:
                logger.error(f"Error getting profiles: {response}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting profiles: {e}")
            return None

    def close_all_browsers(self) -> bool:
        all_closed = True
        profile_ids = list(self.active_browsers.keys())
        
        for profile_id in profile_ids:
            success = self.close_browser(profile_id)
            if not success:
                all_closed = False

        return all_closed
