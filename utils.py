import random
import string
from typing import Optional



def generate_session_id(length: int = 10) -> str:
    characters = string.ascii_letters + string.digits
    return ''.join(random.choices(characters, k=length))

def create_proxy(proxy_provider: str) -> str:
    while True:
        session_id = generate_session_id()
        proxy_string: Optional[str] = None
        
        if proxy_provider == "OXYLABS":
            proxy_string = (
                f"ol-pro.wiredproxies.com:7777:"
                f"customer-PP_0ZN9GKM-cc-US-sessid-{session_id}-sesstime-30:"
                f"posvm53j"
            )
        elif proxy_provider == "PACKET":
            proxy_string = (
                f"ps-pro.wiredproxies.com:31112:"
                f"PP_MFUBYIC:"
                f"oyowqrp6_country-us_session-{session_id}"
            )
        elif proxy_provider == "SMART":
            proxy_string = (
                f"sp-pro.wiredproxies.com:7000:"
                f"user-PP_P2OPJT1-country-US-session-{session_id}-sessionduration-30:"
                f"od5zcgk6"
            )
        elif proxy_provider == "RAYO":
            proxy_string = (
                f"la.residential.rayobyte.com:8000:"
                f"barrybraeden9935_gmail_com:"
                f"7DfQxX5juUuYvLK-country-US-hardsession-{session_id}"
            )
        elif proxy_provider == "LIGHTNING":
            proxy_string = (
                f"res-us.lightningproxies.net:9999:"
                f"dwamdwaklmdaw1-zone-lightning-region-us-session-{session_id}-sessTime-59:"
                f"dwamdwaklmdaw1"
            )
        
        if proxy_string is None:
            raise ValueError(f"Unknown proxy provider: {proxy_provider}")
        
        return proxy_string

