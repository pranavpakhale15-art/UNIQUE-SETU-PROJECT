import getpass, re
from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError
from app.database.mongodb import connect, close
from app.core.security import hash_password
from app.utils.identifiers import normalize_indian_mobile

def main():
    db=connect()
    name=input("Admin full name: ").strip()
    try:
        mobile=normalize_indian_mobile(input("Admin mobile number: "))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    password=getpass.getpass("Strong password (10+ chars, letters and numbers): ")
    if len(mobile)!=10 or len(password)<10 or not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise SystemExit("Invalid mobile or weak password")
    now=datetime.now(timezone.utc)
    try:
        db.users.insert_one({"full_name":name,"mobile_number":mobile,"normalized_mobile_number":mobile,"email":None,
          "password_hash":hash_password(password),"role":"admin","permissions":["*"],"account_status":"active","preferred_language":"mr",
          "created_at":now,"updated_at":now,"last_login_at":None,"created_by":None})
    except DuplicateKeyError:
        raise SystemExit("That mobile number already exists; no account changed.")
    print("Admin account created.")
    close()
if __name__=="__main__": main()
