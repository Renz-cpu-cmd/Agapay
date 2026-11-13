"""Reviewable AGAPAY app issuer setup; never creates government authority or subscriptions."""
import argparse
from sqlalchemy import select
from app.database import SessionLocal
from app.governance_models import AlertAuthority, AuthorityGrant, VerifiedArea
from app.models import Station, User
from app.services.alert_governance import record

AUTHORITY_ID = "AGAPAY_APP_OPS"
AREA_ID = "AGAPAY:APPLICATION"


def bootstrap(db, *, admin_email, station_ids, citywide=False, apply=False):
    admin = db.scalar(select(User).where(User.email == admin_email, User.role == "admin", User.is_active.is_(True)))
    if not admin:
        raise ValueError("Select an existing active administrator; this command never creates or promotes accounts")
    known = list(db.scalars(select(Station.station_id).where(Station.station_id.in_(station_ids))))
    if set(known) != set(station_ids):
        raise ValueError("Every requested station must already exist")
    plan = {"authority_id": AUTHORITY_ID, "authority_class": "app_operator",
        "area_id": AREA_ID, "area_class": "application", "admin_id": admin.id,
        "station_ids": station_ids, "citywide": citywide, "apply": apply}
    if not apply:
        return plan
    area = db.get(VerifiedArea, AREA_ID)
    if area is None:
        db.add(VerifiedArea(id=AREA_ID, name="AGAPAY application advisories", area_class="application",
            identifier_scheme="AGAPAY application audience namespace",
            evidence="App-owner authorized prototype namespace. Identifies application scope, not geography or flood exposure."))
    elif area.area_class != "application":
        raise ValueError("Conflicting area registry; manual review required")
    authority = db.get(AlertAuthority, AUTHORITY_ID)
    if authority is None:
        db.add(AlertAuthority(id=AUTHORITY_ID, name="AGAPAY App Operations", authority_class="app_operator",
            evidence="App-owner designated internal operator for prototype app advisories. No public evacuation authority claimed."))
    elif authority.authority_class != "app_operator":
        raise ValueError("Conflicting issuing authority; manual review required")
    db.flush()
    grant = db.get(AuthorityGrant, (AUTHORITY_ID, admin.id))
    if grant is None:
        db.add(AuthorityGrant(authority_id=AUTHORITY_ID, user_id=admin.id,
            area_ids=[AREA_ID], station_ids=station_ids, citywide=citywide, active=True, revision=1))
    elif set(grant.station_ids) != set(station_ids) or grant.citywide != citywide or grant.area_ids != [AREA_ID]:
        raise ValueError("Existing grant differs. Review and version-change it through the administrator API; no overwrite performed")
    record(db, admin, "prototype_app_issuer_configured", AUTHORITY_ID,
        "App owner requested a ready prototype policy and internal app issuer", plan)
    db.commit()
    return plan


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--station", action="append", default=[])
    parser.add_argument("--allow-citywide", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        print(bootstrap(db, admin_email=args.admin_email, station_ids=args.station,
                        citywide=args.allow_citywide, apply=args.apply))
