#!/usr/bin/env python3
"""
download_filevine_documents.py

Download every document from a given Filevine project into a local folder that mirrors the
project’s Filevine folder hierarchy.

🆕 **June 2025** — Now guarantees that *all* folders are created locally even when they contain
no documents. Useful if you want an exact offline mirror of the project structure.

Prerequisites
-------------
1. `pip install requests python-dotenv`
2. Create a `.env` file in the same directory with:
   FILEVINE_PAT=xxxxx
   FILEVINE_CLIENT_ID=xxxxx
   FILEVINE_CLIENT_SECRET=xxxxx

Usage
-----
python download_filevine_documents.py --project 11915028 --dest ./downloads --workers 4

Options
-------
--project   The Filevine projectId (integer; required)
--dest      Local directory that will contain the downloaded tree (default ./downloads)
--workers   Parallel download workers (default 4)
--dry-run   List files & folders without downloading
"""
import argparse
import concurrent.futures
import logging
import os
import pathlib
import sys
import time
from typing import Dict, List, Optional


import requests
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# Logging setup
# -----------------------------------------------------------------------------
logger = logging.getLogger("filevine_export")


def setup_logging(log_file: str) -> None:
    """Configure logging to file and console."""
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(message)s")

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(sh)

# -----------------------------------------------------------------------------
# API helpers
# -----------------------------------------------------------------------------
API_ROOT = "https://api.filevineapp.com/fv-app/v2"

def get_access_token(pat: str, client_id: str, client_secret: str) -> str:
    """Exchange a Personal‑Access‑Token for an OAuth bearer token."""
    url = "https://identity.filevine.com/connect/token"
    data = {
        "token": pat,
        "grant_type": "personal_access_token",
        "scope": (
            "fv.api.gateway.access tenant filevine.v2.api.* openid email "
            "fv.auth.tenant.read"
        ),
        "client_id": client_id,
        "client_secret": client_secret,
    }
    r = requests.post(url, data=data, timeout=30)
    r.raise_for_status()
    token = r.json().get("access_token")
    if not token:
        raise RuntimeError("access_token missing from token response")
    return token


def get_org_and_user_ids(access_token: str) -> Dict[str, str]:
    """Return dict with org_id and user_id strings."""
    url = f"{API_ROOT}/utils/GetUserOrgsWithToken"
    r = requests.post(url, headers={"Authorization": f"Bearer {access_token}"}, timeout=30)
    r.raise_for_status()
    info = r.json()

    def _pick_id(data: dict, key: str) -> Optional[str]:
        val = data.get(key) or data.get(key.lower())
        if isinstance(val, dict):
            return val.get("native") or val.get("partner")
        return val

    user_id = _pick_id(info.get("user", {}), "userId") or _pick_id(info, "userId")
    if not user_id:
        raise RuntimeError("Unable to parse userId from GetUserOrgsWithToken")

    orgs = info.get("orgs", [])
    if orgs:
        org_id = _pick_id(orgs[0], "orgId")
    else:
        org_id = _pick_id(info, "orgId")
    if not org_id:
        raise RuntimeError("Unable to parse orgId from GetUserOrgsWithToken")

    return {"org_id": str(org_id), "user_id": str(user_id)}


# -----------------------------------------------------------------------------
# Folder utilities
# -----------------------------------------------------------------------------

def fetch_folder_tree(project_id: int, headers: Dict[str, str]) -> List[dict]:
    """Return list of folder JSON objects for the project."""
    url = f"{API_ROOT}/Folders/list"
    params = {"projectId": project_id, "includeArchivedFolders": "false"}
    r = requests.get(url, headers=headers, params=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    items = data.get("items", [])
    return items


def build_folder_maps(items: List[dict]) -> Dict[int, dict]:
    """Return mapping: folderId(native) -> folder dict (name, parentId)."""
    mapping = {}
    for f in items:
        fid = f["folderId"]["native"]
        mapping[fid] = {
            "name": f["name"],
            "parent": f["parentId"]["native"] if f["parentId"] else None,
        }
    return mapping


def folder_path(folder_id: int, folder_map: Dict[int, dict]) -> pathlib.Path:
    parts: List[str] = []
    cur = folder_id
    visited = set()
    while cur and cur not in visited and cur in folder_map:
        visited.add(cur)
        entry = folder_map[cur]
        parts.append(entry["name"])
        cur = entry["parent"]
    return pathlib.Path(*reversed(parts))


# -----------------------------------------------------------------------------
# Document utilities
# -----------------------------------------------------------------------------

def list_documents(project_id: int, headers: Dict[str, str]) -> List[dict]:
    """Return list of document JSON objects for the project."""
    url = f"{API_ROOT}/Documents"
    params = {"projectId": project_id}
    r = requests.get(url, headers=headers, params=params, timeout=60)
    r.raise_for_status()
    return r.json().get("items", [])


def get_presigned_url(doc_id: int, headers: Dict[str, str]) -> dict:
    url = f"{API_ROOT}/Documents/{doc_id}/locator"
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


# -----------------------------------------------------------------------------
# Download helpers
# -----------------------------------------------------------------------------

def download_document(
    doc: dict,
    folder_map: Dict[int, dict],
    base_dir: pathlib.Path,
    headers: Dict[str, str],
    dry_run: bool = False,
    max_retries: int = 3,
) -> None:
    doc_id = doc["documentId"]["native"]
    filename = doc["filename"]
    folder_id = doc["folderId"]["native"]

    rel_path = folder_path(folder_id, folder_map) / filename
    dest_path = base_dir / rel_path
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if dry_run:
        logger.info(f"[DRY‑RUN] Would download {doc_id} → {dest_path}")
        return

    for attempt in range(1, max_retries + 1):
        try:
            locator = get_presigned_url(doc_id, headers)
            url = locator["url"]
            with requests.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(dest_path, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            fh.write(chunk)
            logger.info(f"✅ {dest_path} ({doc_id})")
            return
        except Exception as e:
            if attempt < max_retries:
                wait = 2 ** attempt
                logger.warning(f"⚠️  Retry {attempt}/{max_retries} for {doc_id} in {wait}s: {e}")
                time.sleep(wait)
            else:
                logger.error(f"❌ Failed to download {doc_id} after {max_retries} attempts: {e}")


# -----------------------------------------------------------------------------
# Main program
# -----------------------------------------------------------------------------

def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Download Filevine project documents."
    )
    parser.add_argument("--project", type=int, help="Filevine projectId")
    parser.add_argument("--dest", help="Destination directory")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent download workers")
    parser.add_argument("--dry-run", action="store_true", help="List docs without downloading")
    parser.add_argument("--log", default="download_log.txt", help="Path to write log file")
    args = parser.parse_args()

    setup_logging(args.log)

    if args.project is None:
        pid = input("Enter the Filevine project ID: ").strip()
        if not pid:
            sys.exit("Project ID is required")
        try:
            args.project = int(pid)
        except ValueError:
            sys.exit("Project ID must be an integer")

    if args.dest is None:
        path = input("Enter the download destination directory: ").strip()
        if not path:
            sys.exit("Destination directory is required")
        args.dest = path

    pat = os.getenv("FILEVINE_PAT")
    cid = os.getenv("FILEVINE_CLIENT_ID")
    secret = os.getenv("FILEVINE_CLIENT_SECRET")
    if not all([pat, cid, secret]):
        sys.exit("Please provide FILEVINE_PAT, FILEVINE_CLIENT_ID, FILEVINE_CLIENT_SECRET in .env")

    logger.info("🔑 Exchanging PAT for access token…")
    access_token = get_access_token(pat, cid, secret)
    ids = get_org_and_user_ids(access_token)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-fv-orgid": ids["org_id"],
        "x-fv-userid": ids["user_id"],
        "Accept": "application/json",
    }

    logger.info("📂 Fetching folder structure…")
    folders = fetch_folder_tree(args.project, headers)
    folder_map = build_folder_maps(folders)
    logger.info(f"   {len(folder_map)} folders found.")

    base_dir = pathlib.Path(args.dest)
    base_dir.mkdir(parents=True, exist_ok=True)

    # NEW: mirror the folder tree even for empty folders
    logger.info("🗂️  Mirroring empty folders locally…")
    for fid in folder_map:
        (base_dir / folder_path(fid, folder_map)).mkdir(parents=True, exist_ok=True)

    logger.info("📑 Fetching document list…")
    documents = list_documents(args.project, headers)
    logger.info(f"   {len(documents)} documents found.")

    if args.dry_run:
        logger.info("⛔ Dry‑run complete. No files downloaded.")
        return

    logger.info("⬇️  Starting downloads…")
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [
            pool.submit(
                download_document,
                doc,
                folder_map,
                base_dir,
                headers,
                args.dry_run,
            )
            for doc in documents
        ]
        for f in concurrent.futures.as_completed(futures):
            _ = f.result()  # propagate exceptions

    logger.info("\n🎉 Done.")


if __name__ == "__main__":
    main()
