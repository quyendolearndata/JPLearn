from jplearn_api.main import create_app
from jplearn_api.openapi_diff import compare_openapi, load_handwritten_spec
from jplearn_api.settings import Settings


def test_generated_openapi_matches_handwritten_on_implemented_ops():
    settings = Settings(
        database_url="postgresql://jplearn_test:jplearn_test@127.0.0.1:5432/jplearn_test",
        jwt_secret="test-secret",
        openapi_ui=False,
    )
    problems = compare_openapi(load_handwritten_spec(), create_app(settings).openapi())
    assert problems == []


def test_docs_and_openapi_json_stay_off(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404
