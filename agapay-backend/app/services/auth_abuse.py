"""Atomic, shared database budgets. No raw email/address keys in persistence."""
import hashlib
import ipaddress
import hmac
import time
from fastapi import HTTPException
from sqlalchemy import case, delete, select, func
from sqlalchemy.exc import SQLAlchemyError
from app.database import SessionLocal
from app.identity_models import AuthBudget
from app.config import get_settings


class AuthLimiter:
    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    def hit(self, key, limit, window=900):
        now=int(time.time()); digest=hashlib.sha256(key.encode()).hexdigest()
        try:
            with self.session_factory() as db:
                dialect=db.bind.dialect.name
                if dialect=='sqlite':
                    from sqlalchemy.dialects.sqlite import insert
                elif dialect=='postgresql':
                    from sqlalchemy.dialects.postgresql import insert
                else:
                    raise HTTPException(503,'Shared authentication budget storage is unsupported')
                db.execute(delete(AuthBudget).where(AuthBudget.reset_at < now-60))
                if db.get(AuthBudget,digest) is None and db.scalar(select(func.count()).select_from(AuthBudget))>=100000:
                    raise HTTPException(429,"Authentication budget capacity reached; try again later",headers={"Retry-After":"60"})
                statement=insert(AuthBudget).values(key_hash=digest,count=1,reset_at=now+window)
                statement=statement.on_conflict_do_update(index_elements=['key_hash'],set_={
                    'count':case((AuthBudget.reset_at<=now,1),else_=AuthBudget.count+1),
                    'reset_at':case((AuthBudget.reset_at<=now,now+window),else_=AuthBudget.reset_at),
                },where=(AuthBudget.reset_at<=now)|(AuthBudget.count<limit)).returning(AuthBudget.reset_at)
                accepted=db.execute(statement).scalar_one_or_none(); db.commit()
                if accepted is None:
                    raise HTTPException(429,'Too many attempts. Please try again later.',headers={'Retry-After':str(window)})
        except SQLAlchemyError:
            raise HTTPException(503,'Authentication protection is unavailable; try again later') from None

    def clear(self,key):
        with self.session_factory() as db:
            db.execute(delete(AuthBudget).where(AuthBudget.key_hash==hashlib.sha256(key.encode()).hexdigest()));db.commit()

    def reset(self):
        """Test/maintenance helper; never exposed as a network endpoint."""
        with self.session_factory() as db:db.execute(delete(AuthBudget));db.commit()


limiter=AuthLimiter()


def request_ip(request):
    """Only an explicitly trusted peer with a valid short-lived BFF signature may assert an address."""
    peer=request.client.host if request.client else 'unknown'
    settings=get_settings()
    try:
        trusted=any(ipaddress.ip_address(peer) in ipaddress.ip_network(network) for network in settings.auth_trusted_proxy_peers)
        address=str(ipaddress.ip_address(request.headers.get('x-agapay-client-ip','')))
        timestamp=request.headers.get('x-agapay-client-time','')
        signature=request.headers.get('x-agapay-client-signature','')
        key=settings.auth_proxy_key.get_secret_value()
        message=f'{timestamp}\n{address}\n{request.method}\n{request.url.path}'
        expected=hmac.new(key.encode(),message.encode(),'sha256').hexdigest()
        if trusted and len(key)>=32 and abs(time.time()-int(timestamp))<=30 and hmac.compare_digest(signature,expected):return address
    except (ValueError,TypeError):pass
    return peer
