import getpass
from pathlib import Path


def main() -> None:
    """Interactive helper to create a .env file with Filevine credentials."""
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        resp = input(f"A .env file already exists at {env_path}. Overwrite it? [y/N] ").strip().lower()
        if resp != "y":
            print("Aborted. Existing .env left unchanged.")
            return

    pat = getpass.getpass("Enter your Filevine Personal Access Token: ")
    client_id = input("Enter your Filevine Client ID: ")
    client_secret = getpass.getpass("Enter your Filevine Client Secret: ")

    content = (
        f"FILEVINE_PAT={pat}\n"
        f"FILEVINE_CLIENT_ID={client_id}\n"
        f"FILEVINE_CLIENT_SECRET={client_secret}\n"
    )
    env_path.write_text(content)
    print(f"✅ Credentials written to {env_path}")


if __name__ == "__main__":
    main()
