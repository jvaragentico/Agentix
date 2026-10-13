import pytest


def test_owner_journal_pages_and_isolation(client, participants):
    p = participants
    entries = client.get("/v1/wallet/entries", headers=p["buyer"]).json()
    assert len(entries) == 3  # Funding plus both sides of project allocation.
    assert [e["id"] for e in entries] == sorted(e["id"] for e in entries)
    for i, entry in enumerate(entries):
        assert set(entry) == {"id", "journal_id", "account_id", "amount"}
        assert client.get(f"/v1/wallet/entries?limit=1&offset={i}", headers=p["buyer"]).json() == [
            entry
        ]
    assert client.get("/v1/wallet/entries?offset=3", headers=p["buyer"]).json() == []
    assert sum(e["amount"] for e in entries) == 1000
    for auth in (p["seller"], p["outsider"]):
        assert client.get("/v1/wallet/entries", headers=auth).json() == []
    assert client.get("/v1/wallet/entries", headers=p["agent_auth"]).status_code == 403


@pytest.mark.parametrize(
    "query",
    ["limit=0", "limit=101", "limit=1.5", "offset=-1", "offset=abc", "offset=9007199254740992"],
)
def test_wallet_page_validation(client, participants, query):
    response = client.get("/v1/wallet/entries?" + query, headers=participants["buyer"])
    assert response.status_code == 422
    assert response.json()["error"]["retryable"] is False
