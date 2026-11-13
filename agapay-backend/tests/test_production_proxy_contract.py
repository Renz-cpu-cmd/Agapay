"""Production proxy wiring: TLS scheme assertions only from a reviewed peer."""
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


@pytest.mark.parametrize('peer,expected', [('127.0.0.1','https'),('192.0.2.100','http')])
def test_proxy_scheme_requires_explicit_trusted_peer(peer,expected):
    probe=FastAPI()
    @probe.get('/')
    def inspect_scheme(request:Request):return {'scheme':request.url.scheme}
    configured=ProxyHeadersMiddleware(probe,trusted_hosts='127.0.0.1')
    with TestClient(configured,client=(peer,54321)) as browser:
        response=browser.get('/',headers={'X-Forwarded-Proto':'https'})
        assert response.json()=={'scheme':expected}
