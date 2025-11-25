import os
import pytest
import time
import jwt

from cat.env import get_env
from cat.auth import AuthPermission, AuthResource

from tests.utils import send_websocket_message, send_http_message

# TODOAUTH: test token refresh / invalidation / logoff
def is_jwt(token):
    assert False
    # load this function from auth handler

JWT_ALGO = "HS256"

def test_is_jwt(client):
    assert not is_jwt("not_a_jwt.not_a_jwt.not_a_jwt")

    actual_jwt = jwt.encode(
        {"username": "Alice"},
        "some_secret",
        algorithm=JWT_ALGO,
    )
    assert is_jwt(actual_jwt)


def test_refuse_issue_jwt(client):
    creds = {"username": "admin", "password": "wrong"}
    res = client.post("/auth/token", json=creds)

    # wrong credentials
    assert res.status_code == 403
    json = res.json()
    assert json["detail"] == "Invalid Credentials"


def test_issue_jwt(client):
    creds = {
        "username": "admin",
        "password": "admin"
    }
    res = client.post("/auth/token", json=creds)
    assert res.status_code == 200

    # did we obtain a JWT?
    assert res.json()["token_type"] == "bearer"
    received_token = res.json()["access_token"]
    assert is_jwt(received_token)

    # is the JWT correct for core auth handler?
    auth_handler = client.app.state.ccat.auth_handler
    user_info = auth_handler.authorize_user_from_jwt(
        received_token, AuthResource.LLM, AuthPermission.WRITE
    )
    assert len(user_info.id) == 36 and len(user_info.id.split("-")) == 5 # uuid4
    assert user_info.name == "admin"

    # manual JWT verification
    try:
        payload = jwt.decode(
            received_token,
            get_env("CCAT_JWT_SECRET"),
            algorithms=[JWT_ALGO],
        )
        assert payload["username"] == "admin"
        assert (
            payload["exp"] - time.time() < 60 * 60 * 24
        )  # expires in less than 24 hours
    except jwt.exceptions.DecodeError:
        assert False


def test_issue_jwt_for_new_user(client, admin_headers):

    # create new user
    creds = {
        "username": "Alice",
        "password": "Alice",
    }

    # we sohuld not obtain a JWT for this user
    # because it does not exist
    res = client.post("/auth/token", json=creds)
    assert res.status_code == 403
    assert res.json()["detail"] == "Invalid Credentials"

    # let's create the user (using api key)
    res = client.post("/users", headers=admin_headers, json=creds)
    assert res.status_code == 200

    # now we should get a JWT
    res = client.post("/auth/token", json=creds)
    assert res.status_code == 200

    # did we obtain a JWT?
    assert res.json()["token_type"] == "bearer"
    received_token = res.json()["access_token"]
    assert is_jwt(received_token)

    # new jwt works
    res = client.get("/status", headers={ "Authorization": f"Bearer {res.json()['access_token']}"})
    assert res.status_code == 200


# test token expiration after successfull login
# NOTE: here we are using the client fixture (see conftest.py)
def test_jwt_expiration(client):

    # set ultrashort JWT expiration time
    os.environ["CCAT_JWT_EXPIRE_MINUTES"] = "0.05"  # 3 seconds

    # not allowed
    response = client.get("/status")
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid Credentials"

    # request JWT
    creds = {
        "username": "admin",
        "password": "admin",
    }
    res = client.post("/auth/token", json=creds)
    assert res.status_code == 200
    token = res.json()["access_token"]

    # allowed via JWT
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/status", headers=headers)
    assert response.status_code == 200

    # wait for expiration time
    time.sleep(3)

    # not allowed because JWT expired
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/status", headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid Credentials"

    # restore default env
    del os.environ["CCAT_JWT_EXPIRE_MINUTES"]


# test ws and http endpoints can get user_id from JWT
def test_jwt_imposes_user_id(client):

    # not allowed
    response = client.get("/status")
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid Credentials"

    # request JWT
    creds = {
        "username": "admin", # TODOAUTH: use another user?
        "password": "admin",
    }
    res = client.post("/auth/token", json=creds)
    assert res.status_code == 200
    token = res.json()["access_token"]

    # we will send this message both via http and ws, having the user_id carried by the JWT
    message = "hey"

    # send user specific message via http
    headers = {
        "Authorization": f"Bearer {token}",
        "user_id": "fake"
    }
    res =send_http_message(message, client, headers=headers)
    assert res["user_id"] == "admin"

    # send user specific request via ws
    query_params = {"token": token}
    res = send_websocket_message(message, client, user_id="fake", query_params=query_params)
    assert res["user_id"] == "admin"


# test that a JWT signed knowing the secret, passes
def test_jwt_self_signature_passes(client, admin_headers):

    # get list of users (we need the ids)
    response = client.get("/users", headers=admin_headers)
    assert response.status_code == 200
    users = response.json()

    for user in users:

        # create a self signed JWT using the default secret              
        token = jwt.encode(
            {"sub": user["id"], "username": user["username"]},
            "meow_jwt",
            algorithm=JWT_ALGO,
        )

        headers = {
            "Authorization": f"Bearer {token}"
        }
        response = send_http_message("hey", client, headers=headers)
        assert "You did not configure" in response["text"]

        params = {"token": token}
        response = send_websocket_message("hey", client, query_params=params)
        assert "You did not configure" in response["text"]


# test that a JWT signed with the wrong secret is not accepted
def test_jwt_self_signature_fails(client, admin_headers):

    # get list of users (we need the ids)
    response = client.get(
        "/users",
        headers=admin_headers
    )
    assert response.status_code == 200
    users = response.json()

    for user in users:

        # create a self signed JWT using the default secret              
        token = jwt.encode(
            {"sub": user["id"], "username": user["username"]},
            "wrong_secret",
            algorithm=JWT_ALGO,
        )

        # not allowed because CCAT_JWT_SECRET for client is `meow_jwt`
        headers = {
            "Authorization": f"Bearer {token}"
        }
        response = client.post("/chat", headers=headers)
        assert response.status_code == 403

        # not allowed because CCAT_JWT_SECRET for client is `meow_jwt`
        params = {"token": token}
        with pytest.raises(Exception) as e_info:
            send_websocket_message("hey", client, query_params=params)
            assert str(e_info.type.__name__) == "WebSocketDisconnect"


# TODOV2: all tests messaging the cat with the old `user_message_json` object must be updated to ChatRequest



    
    
