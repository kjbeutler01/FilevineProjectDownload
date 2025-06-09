import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env file in the same directory
load_dotenv()

def main():
    # Load credentials from environment variables (populated by .env)
    pat = os.getenv("FILEVINE_PAT")
    client_id = os.getenv("FILEVINE_CLIENT_ID")
    client_secret = os.getenv("FILEVINE_CLIENT_SECRET")

    # Validate that all required environment variables are set
    if not all([pat, client_id, client_secret]):
        print(
            "Error: Please create a .env file in this folder with the following entries:\n"
            "FILEVINE_PAT=your_pat_here\n"
            "FILEVINE_CLIENT_ID=your_client_id_here\n"
            "FILEVINE_CLIENT_SECRET=your_client_secret_here"
        )
        return

    # 1) Exchange PAT + client creds for bearer token
    print("\nRequesting access token...")
    token_url = "https://identity.filevine.com/connect/token"
    data = {
        "token": pat,
        "grant_type": "personal_access_token",
        "scope": (
            "fv.api.gateway.access tenant filevine.v2.api.* openid email "
            "fv.auth.tenant.read"
        ),
        "client_id": client_id,
        "client_secret": client_secret
    }
    try:
        r = requests.post(token_url, data=data)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ Failed to obtain access token: {e}")
        return

    access_token = r.json().get("access_token")
    if not access_token:
        print(f"❌ No access token returned: {r.json()}")
        return
    print("✅ Access token obtained.")

    # 2) Fetch Org & User IDs
    print("Requesting Org ID and User ID...")
    org_user_url = (
        "https://api.filevineapp.com/fv-app/v2/utils/GetUserOrgsWithToken"
    )
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        r2 = requests.post(org_user_url, headers=headers)
        r2.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ Failed to retrieve Org/User IDs: {e}")
        return

    info = r2.json()

    # Parse nested userId
    user_id = None
    if "user" in info and isinstance(info["user"], dict):
        uid = info["user"].get("userId") or info["user"].get("userID")
        if isinstance(uid, dict):
            user_id = uid.get("native") or uid.get("partner")
    if not user_id:
        user_id = info.get("userId") or info.get("userID")

    # Parse first orgId
    org_id = None
    if "orgs" in info and isinstance(info["orgs"], list) and info["orgs"]:
        first = info["orgs"][0]
        org_id = first.get("orgId") or first.get("orgID")
    if not org_id:
        org_id = info.get("orgId") or info.get("orgID")

    if not user_id or not org_id:
        print(f"❌ Unable to parse Org/User IDs from response: {info}")
        return

    print("✅ Retrieved Org/User IDs successfully.")
    print(f"   • Org ID:  {org_id}")
    print(f"   • User ID: {user_id}")
    print(
        "\n🎉 Connection test successful — you’re authenticated and ready to call other endpoints!"
    )

if __name__ == "__main__":
    # Ensure python-dotenv is installed: pip install python-dotenv
    main()
