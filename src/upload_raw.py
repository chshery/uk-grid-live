import os
from pathlib import Path

from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()

service = BlobServiceClient.from_connection_string(os.getenv("AZURE_STORAGE_CONNECTION_STRING"))
container = service.get_container_client("raw")

local_root = Path("data/raw")
existing = {b.name for b in container.list_blobs()}

uploaded = 0
for file in local_root.rglob("*.json"):
    blob_name = file.relative_to(local_root).as_posix()   # e.g. carbon/regional_2026...json
    if blob_name in existing:
        continue
    with open(file, "rb") as f:
        container.upload_blob(name=blob_name, data=f)
    uploaded += 1
    print("Uploaded:", blob_name)

print(f"\nDone. {uploaded} new file(s) uploaded, {len(existing)} already in Azure.")