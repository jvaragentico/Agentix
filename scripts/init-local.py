"""Create private development configuration without overwriting existing secrets."""

import os
import secrets
from pathlib import Path

path = Path(".runtime/development.env")
path.parent.mkdir(exist_ok=True)
if path.exists():
    print("Existing development environment preserved.")
else:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n")
        f.write(f"AGENTIX_ADMIN_TOKEN={secrets.token_urlsafe(40)}\n")
        f.write("AGENTIX_ENABLE_TEST_FUNDING=true\n")
        f.write("AGENTIX_ENABLE_FREE_MODEL=true\n")
        f.write("AGENTIX_FREE_MODEL_PROVIDER=pollinations\n")
    print("Private configuration created in .runtime/development.env.")
