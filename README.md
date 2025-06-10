# FilevineProjectDownload

This repository contains example scripts that interact with the [Filevine](https://www.filevine.com/) API. The main script `ProjectDocsDownload.py` downloads every document from a Filevine project and recreates the same folder hierarchy on your local drive. A second script, `TestConnection.py`, verifies that your credentials work by retrieving your organization and user IDs.

## Setup

1. Install dependencies:
   ```bash
   pip install requests python-dotenv
   ```
2. Generate a `.env` file containing your credentials:
   ```bash
   python create_env.py
   ```
   The script prompts for your Personal Access Token, Client ID and Client Secret
   and writes them to `.env` in this folder. Alternatively you can create the file
   manually with the following values:
   ```
   FILEVINE_PAT=your_personal_access_token
   FILEVINE_CLIENT_ID=your_client_id
   FILEVINE_CLIENT_SECRET=your_client_secret
   ```

These environment variables are required for authenticating with the Filevine API.

## Usage

**Download project documents**
```bash
python ProjectDocsDownload.py --project <projectId> --dest ./downloads --workers 4
```
- `--project`  – ID of the Filevine project to download from (required).
- `--dest`     – Local directory where documents will be written. The script creates sub‑folders to mirror Filevine's structure.
- `--workers`  – Number of concurrent download workers (default: 4).
- `--dry-run`  – Show which files would be downloaded without saving anything.

**Test your credentials**
```bash
python TestConnection.py
```
This script exchanges your PAT for an access token and prints the detected organization and user IDs.

## License

This project is released under the terms of the GNU General Public License v3. See the [LICENSE](LICENSE) file for details.
