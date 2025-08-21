import requests
import json
import time
import traceback

def get2FACode(api_prefix, email_address, thread_id, master_email, rdp_id):
    try:
        # Initial search request
        search_payload = {
            'emailAddress': email_address,
            'threadID': thread_id,
            'masterEmail': master_email,
            'rdpID': rdp_id,
            'service': 'wisley_login'
        }
        
        search_resp = requests.post(
            f"{api_prefix}/search2FA",
            headers={'Content-Type': 'application/json'},
            data=json.dumps(search_payload)
        )
        
        print(search_resp.json())
        
        # Set timeout to 3 minutes (60 seconds * 3)
        timeout = time.time() + 60 * 3
        
        while time.time() < timeout:
            response = requests.post(
                f"{api_prefix}/get2FA",
                headers={'Content-Type': 'application/json'},
                data=json.dumps({'emailAddress': email_address})
            )
            
            if response.ok:
                data = response.json()
                print(data)
                if data['status'] != 'PENDING':
                    success = data['status'] != 'ERROR'
                    return success, data['code']
            
            # Wait 2 seconds before next attempt
            time.sleep(2)
        
        return False, "Timeout waiting for 2FA code"
        
    except Exception as error:
        print(e)
        return False, traceback.format_exc()