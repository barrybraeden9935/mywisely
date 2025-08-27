import time
import traceback

async def get2FACode(task_repo, email_address, thread_id, master_email, rdp_id):
    try:
        additional_data = {
            "rdp_id": rdp_id,
            "thread_id": thread_id,
            "master_email": master_email,
            "service": "wisley_login"
        }
        
        timeout = time.time() + 60 * 3
        task_info = await task_repo.create_task("TWOFA", additional_data, 'PENDING', None, email_address, {})

        while time.time() < timeout:
            task_details = await task_repo.get_task_by_id(task_info['id'])
            task_details = task_details[0]
            
            if task_details['status'] != 'COMPLETED':
                time.sleep(5)
                continue

            output = task_details.get("output")
            if not output:
                await task_repo.delete_by_id(task_info['id'])
                return False, f"No task found with id {task_info['id']}"

            print(output)
            success = output.get("success")
            code = output.get("code")
            if str(success).lower() != 'true':
                await task_repo.delete_by_id(task_info['id'])
                return False, f"Failed to get 2FA code with output {code}"
            
            await task_repo.delete_by_id(task_info['id'])
            return True, code
        
        await task_repo.delete_by_id(task_info['id'])
        return False, "Timeout waiting for 2FA code"
        
    except Exception as error:
        print(traceback.format_exc())
        return False, traceback.format_exc()