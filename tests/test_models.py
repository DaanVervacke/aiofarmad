from aiofarmad.models import FarmadTokens


def test_tokens_from_token_response() -> None:
    tokens = FarmadTokens.from_token_response(
        {"access_token": "a", "refresh_token": "r", "expires_in": "36000", "scope": "s"}
    )
    assert tokens.access_token == "a"
    assert tokens.refresh_token == "r"
    assert tokens.expires_in == 36000
    assert tokens.scope == "s"
