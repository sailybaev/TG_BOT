"""
Test backend connectivity and API endpoints
"""
import asyncio
import httpx


async def test_backend():
    """Test if backend is accessible"""
    backend_url = "http://localhost:8000"  # Change if needed

    print("🔍 Testing Tabys Backend Connectivity\n")
    print(f"Backend URL: {backend_url}\n")

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Test 1: Root endpoint
        print("1️⃣ Testing root endpoint (GET /)...")
        try:
            response = await client.get(f"{backend_url}/")
            print(f"   ✅ Status: {response.status_code}")
            print(f"   Response: {response.json()}\n")
        except Exception as e:
            print(f"   ❌ Error: {e}\n")

        # Test 2: Docs endpoint
        print("2️⃣ Testing docs endpoint (GET /docs)...")
        try:
            response = await client.get(f"{backend_url}/docs")
            print(f"   ✅ Status: {response.status_code}\n")
        except Exception as e:
            print(f"   ❌ Error: {e}\n")

        # Test 3: Telegram auth endpoints (without auth)
        print("3️⃣ Testing telegram-auth endpoints...")

        # Test verify-otp
        print("   - POST /api/v1/telegram-auth/verify-otp (should fail - no auth)")
        try:
            response = await client.post(
                f"{backend_url}/api/v1/telegram-auth/verify-otp",
                json={
                    "otp_token": "TEST1234",
                    "telegram_user_id": "123456789"
                }
            )
            print(f"     Status: {response.status_code}")
            if response.status_code != 200:
                print(f"     Response: {response.text}")
        except Exception as e:
            print(f"     ❌ Error: {e}")

        # Test logout
        print("   - POST /api/v1/telegram-auth/logout (should fail - no session)")
        try:
            response = await client.post(
                f"{backend_url}/api/v1/telegram-auth/logout",
                json={"telegram_user_id": "123456789"}
            )
            print(f"     Status: {response.status_code}")
            if response.status_code != 200:
                print(f"     Response: {response.text}")
        except Exception as e:
            print(f"     ❌ Error: {e}")

        print("\n" + "="*50)
        print("✅ Backend connectivity test complete!")
        print("\nℹ️  Expected results:")
        print("  - Root: 200 OK")
        print("  - Docs: 200 OK")
        print("  - verify-otp: 401 Unauthorized (invalid OTP)")
        print("  - logout: 404 Not Found (no session)")
        print("\n⚠️  If you see 'Method Not Allowed' (405):")
        print("  - Check if endpoint exists in backend")
        print("  - Check HTTP method (GET vs POST)")
        print("  - Verify router is included in main.py")


if __name__ == "__main__":
    asyncio.run(test_backend())
