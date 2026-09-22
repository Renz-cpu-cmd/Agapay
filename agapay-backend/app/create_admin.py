"""Run `python -m app.create_admin` locally; credentials are never seeded or printed."""
from getpass import getpass

from pydantic import ValidationError
from sqlalchemy import select

from app.account_schemas import RegisterRequest
from app.database import Base, SessionLocal, engine
from app.models import User
from app.services.administrator_setup import create_first_administrator, setup_complete
from fastapi import HTTPException


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if setup_complete(db):
            raise SystemExit("Administrator setup is complete. Manage additional accounts through the web app.")
        try:
            name = input("Administrator name: ")
            email = input("Email: ")
            phone = input("Phone: ")
            barangay = input("Barangay: ")
            password = getpass("Password (12–128 characters): ")
            if password != getpass("Confirm password: "):
                raise SystemExit("Passwords do not match; nothing was created.")
            payload = RegisterRequest(name=name, email=email, phone=phone, barangay=barangay, password=password)
        except ValidationError as exc:
            # Never print Pydantic's raw input, which can contain the password.
            raise SystemExit("; ".join(e["msg"] for e in exc.errors(include_input=False))) from None
        if db.scalar(select(User.id).where(User.email == str(payload.email))):
            raise SystemExit("That email already belongs to an account; nothing was changed.")
        try:
            create_first_administrator(db, payload)
        except HTTPException as exc:
            raise SystemExit(exc.detail) from None
        print("Administrator created. Sign in through the web command center.")


if __name__ == "__main__":
    main()
