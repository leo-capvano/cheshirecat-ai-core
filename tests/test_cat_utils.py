import os
import pytest
from cat import urls, paths, utils


def test_get_base_url(client):
    # TODOV2: update to new env var CCAT_URL
    assert urls.BASE_URL == "http://localhost:1865"
    # test when CCAT_CORE_USE_SECURE_PROTOCOLS is set
    os.environ["CCAT_CORE_USE_SECURE_PROTOCOLS"] = "1"
    assert urls.BASE_URL == "https://localhost:1865"
    os.environ["CCAT_CORE_USE_SECURE_PROTOCOLS"] = "0"
    assert urls.BASE_URL == "http://localhost:1865"
    os.environ["CCAT_CORE_USE_SECURE_PROTOCOLS"] = ""
    assert urls.BASE_URL == "http://localhost:1865"


# TODOV2: check get_api_url()


def test_get_base_path(client):
    assert paths.BASE_PATH == os.getcwd() + "/src/cat"


def test_get_project_path(client):
    # during tests, project is in a temp folder
    pytest_tmp_folder = paths.PROJECT_PATH
    assert pytest_tmp_folder.startswith("/tmp/pytest-")
    assert pytest_tmp_folder.endswith("/mocks")


def test_get_data_path(client):
    # "data" in production, "mocks/data" during tests
    assert paths.DATA_PATH == os.path.join(paths.PROJECT_PATH, "data")


def test_get_plugin_path(client):
    # "plugins" in production, "mocks/plugins" during tests
    assert paths.PLUGINS_PATH == os.path.join(paths.PROJECT_PATH, "plugins")


def test_get_uploads_path(client):
    # "uploads" in production, "mocks/uploads" during tests
    assert paths.UPLOADS_PATH == os.path.join(paths.DATA_PATH, "uploads")

def test_levenshtein_distance():
    assert utils.levenshtein_distance("hello world", "hello world") == 0.0
    assert utils.levenshtein_distance("hello world", "") == 1.0

def test_parse_json():
    json_string = """{
    "a": 2
}"""

    expected_json = {"a": 2}

    prefixed_json = "anything \n\t```json\n" + json_string
    assert utils.parse_json(prefixed_json) == expected_json

    suffixed_json = json_string + "\n``` anything"
    assert utils.parse_json(suffixed_json) == expected_json

    unclosed_json = """{"a":2"""
    assert utils.parse_json(unclosed_json) == expected_json

    unclosed_key_json = """{"a":2, "b":"""
    assert utils.parse_json(unclosed_key_json) == expected_json

    invalid_json = """yaml is better"""
    with pytest.raises(Exception) as e:
        utils.parse_json(invalid_json) == expected_json
    assert "substring not found" in str(e.value)


