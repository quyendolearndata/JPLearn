import copy

from jplearn_api.main import create_app
from jplearn_api.openapi_diff import compare_openapi, load_handwritten_spec, main
from jplearn_api.settings import Settings


def _valid_spec():
    settings = Settings(
        database_url="postgresql://jplearn_test:jplearn_test@127.0.0.1:5432/jplearn_test",
        jwt_secret="test-secret-at-least-32-bytes-long-for-pyjwt-security",
        openapi_ui=False,
    )
    return load_handwritten_spec(), create_app(settings).openapi()


def test_generated_openapi_matches_handwritten_on_implemented_ops():
    handwritten, generated = _valid_spec()
    problems = compare_openapi(handwritten, generated)
    assert problems == []


def test_docs_and_openapi_json_stay_off(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_negative_removing_required_field_fails_diff():
    handwritten, generated = _valid_spec()
    mutated = copy.deepcopy(generated)
    # Remove required field 'email' from RegisterBody
    schema = mutated["components"]["schemas"]["RegisterBody"]
    schema["required"].remove("email")

    problems = compare_openapi(handwritten, mutated)
    assert any("missing required fields ['email']" in p for p in problems)


def test_negative_changing_parameter_type_fails_diff():
    handwritten, generated = _valid_spec()
    mutated = copy.deepcopy(generated)
    # Change ci_level query param type from integer to string
    params = mutated["paths"]["/catalog"]["get"]["parameters"]
    ci_param = next(p for p in params if p["name"] == "ci_level")
    ci_param["schema"] = {"type": "string"}

    problems = compare_openapi(handwritten, mutated)
    assert any("type mismatch" in p and "ci_level" in p for p in problems)


def test_negative_removing_endpoint_fails_diff():
    handwritten, generated = _valid_spec()
    mutated = copy.deepcopy(generated)
    del mutated["paths"]["/auth/register"]

    problems = compare_openapi(handwritten, mutated)
    assert any("generated missing required POST /auth/register" in p for p in problems)


def test_negative_extra_endpoint_fails_diff():
    handwritten, generated = _valid_spec()
    mutated = copy.deepcopy(generated)
    mutated["paths"]["/rogue-endpoint"] = {
        "post": {
            "operationId": "rogue",
            "responses": {"200": {"description": "ok"}},
        },
    }

    problems = compare_openapi(handwritten, mutated)
    assert any("extra POST /rogue-endpoint not in handwritten contract" in p for p in problems)


def test_main_cli_returns_non_zero_on_mismatch(monkeypatch):
    import jplearn_api.openapi_diff as diff_mod

    # Patch compare_openapi to return a problem
    monkeypatch.setattr(diff_mod, "compare_openapi", lambda _h, _g: ["synthetic error"])
    exit_code = diff_mod.main([])
    assert exit_code == 1

