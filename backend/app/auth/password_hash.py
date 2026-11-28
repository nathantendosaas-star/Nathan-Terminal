"""Generate APP_PASSWORD_HASH for the Render environment."""
import getpass
from app.auth.router import hash_password

if __name__ == "__main__":
    password = getpass.getpass("Choose terminal password: ")
    confirm = getpass.getpass("Confirm password: ")
    if len(password) < 12:
        raise SystemExit("Use at least 12 characters.")
    if password != confirm:
        raise SystemExit("Passwords do not match.")
    print("\nAPP_PASSWORD_HASH=" + hash_password(password))
