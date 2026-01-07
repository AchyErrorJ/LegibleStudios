import asyncio
import httpx
import sys

# URL for a known, external, non-Revit service
TEST_URL = "https://www.google.com"

async def check_httpx_connectivity():
    print("--- HTTTPX CONNECTIVITY DIAGNOSTIC ---")
    
    # 1. Check Module Availability
    try:
        if 'httpx' not in sys.modules:
            print("1. ❌ FAILED: 'httpx' module is not in the system path.")
            print("   Please run: pip install httpx")
            return
        
        print("1. ✅ Module 'httpx' found.")
    except Exception:
        return

    # 2. Check Async HTTP Request
    print(f"2. Attempting connection to {TEST_URL}...")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(TEST_URL)
            
            if response.status_code == 200:
                print(f"3. ✅ SUCCESS! Connectivity established (Status 200 OK).")
                print("   Your Python environment is correctly configured to use httpx.")
            else:
                print(f"3. ⚠️ WARNING! Connection succeeded but non-200 status code: {response.status_code}")

    except httpx.ConnectError as e:
        print(f"3. ❌ FAILURE: Could not connect to external site.")
        print(f"   Reason: Connection Error. (Possible local firewall issue or network problem)")
    except Exception as e:
        print(f"3. ❌ FAILURE: Unhandled error.")
        print(f"   Error: {type(e).__name__}: {e}")

    print("--- DIAGNOSTIC COMPLETE ---")

if __name__ == "__main__":
    # Use asyncio to run the async test function
    try:
        asyncio.run(check_httpx_connectivity())
    except RuntimeError as e:
        if "cannot run" in str(e):
            print("Warning: Asyncio is already running. Trying direct run...")
            asyncio.get_event_loop().run_until_complete(check_httpx_connectivity())
        else:
            raise
