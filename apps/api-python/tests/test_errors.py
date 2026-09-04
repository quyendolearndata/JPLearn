def test_unknown_route_uses_nest_error_shape(client):
    response = client.get("/definitely-missing")
    assert response.status_code == 404
    body = response.json()
    assert body["statusCode"] == 404
    assert "detail" not in body
    assert "message" in body


def test_method_not_allowed_is_not_422(client):
    response = client.post("/health")
    assert response.status_code != 422
    assert "detail" not in response.json()
