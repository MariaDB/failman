import io
import os
import builtins
import pytest
import smtplib
from unittest.mock import patch, mock_open, MagicMock

import requests
import yaml

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from failman import (  # replace with actual module name, e.g. build_report
    Build,
    load_config,
    builds_to_csv,
    builds_to_html_table,
    send_email_with_csv,
    get_builders_details,
    get_latest_builds_on_branch,
    join_builders_with_change,
)


@pytest.fixture
def sample_builds():
    return [
        Build(name="build-A", url="http://example.com/A", commit="abc123", branch="main", status="success"),
        Build(name="build-B", url="http://example.com/B", commit="def456", branch="dev", status="failed"),
    ]


# -----------------------
# load_config
# -----------------------

def test_load_config_from_file(tmp_path):
    data = {"a": 1, "b": 2}
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(yaml.dump(data))
    result = load_config(str(yaml_path))
    assert result == data


@patch("requests.get")
def test_load_config_from_url(mock_get):
    fake_yaml = yaml.dump({"x": 10})
    mock_get.return_value.status_code = 200
    mock_get.return_value.text = fake_yaml
    mock_get.return_value.raise_for_status = lambda: None

    result = load_config("https://example.com/config.yaml")
    assert result == {"x": 10}
    mock_get.assert_called_once_with("https://example.com/config.yaml")


# -----------------------
# builds_to_csv
# -----------------------

def test_builds_to_csv(sample_builds):
    csv_output = builds_to_csv(sample_builds)
    assert "Branch,Build,Commit,Status,URL" in csv_output
    assert "main" in csv_output
    assert "dev" in csv_output
    assert csv_output.count("\n") == 3  # header + 2 rows


# -----------------------
# builds_to_html_table
# -----------------------

def test_builds_to_html_table_groups_by_branch(sample_builds):
    html = builds_to_html_table(sample_builds)
    assert "<h3>Branch:" in html
    assert "<table" in html
    assert "build-A" in html
    assert "build-B" in html
    # ensure hyperlinks are present
    assert '<a href="http://example.com/A">build-A</a>' in html


# -----------------------
# send_email_with_csv
# -----------------------

@patch("smtplib.SMTP_SSL")
def test_send_email_with_csv(mock_smtp):
    smtp_instance = mock_smtp.return_value.__enter__.return_value
    send_email_with_csv(
        sender_email="a@example.com",
        recipient_email="b@example.com",
        subject="Test",
        html_body="<p>Hello</p>",
        csv_content="x,y,z",
        smtp_relay="smtp.example.com",
        smtp_port=465,
    )
    smtp_instance.sendmail.assert_called_once()
    args, kwargs = smtp_instance.sendmail.call_args
    assert "a@example.com" in args[0]
    assert "b@example.com" in args[1]
    assert "Content-Type: multipart/mixed" in args[2]


# -----------------------
# get_builders_details
# -----------------------

@patch("requests.get")
def test_get_builders_details(mock_get):
    mock_get.return_value.json.return_value = {
        "builders": [{"builderid": 1, "name": "B1"}]
    }
    result = get_builders_details("http://api.example.com")
    mock_get.assert_called_once_with("http://api.example.com/builders")
    assert result == [{"builderid": 1, "name": "B1"}]


# -----------------------
# get_latest_builds_on_branch
# -----------------------

@patch("requests.get")
def test_get_latest_builds_on_branch(mock_get):
    mock_get.return_value.json.return_value = {
        "changes": [{"sourcestamp": {"branch": "main"}}]
    }
    result = get_latest_builds_on_branch("main", "http://api.example.com")
    mock_get.assert_called_once_with(
        "http://api.example.com/changes?branch=main&limit=1&order=-changeid"
    )
    assert result[0]["sourcestamp"]["branch"] == "main"


# -----------------------
# join_builders_with_change
# -----------------------

def test_join_builders_with_change():
    builders = [{"builderid": 1, "name": "B1"}, {"builderid": 2, "name": "B2"}]
    builds = [
        {"builderid": 1, "number": 42, "state_string": "success"},
        {"builderid": 3, "number": 43, "state_string": "failed"},
    ]
    result = join_builders_with_change(
        builders,
        builds,
        branch="main",
        revision="abc",
        buildbot_url="http://bb/",
    )
    assert len(result) == 1
    b = result[0]
    assert isinstance(b, Build)
    assert b.name == "B1"
    assert "http://bb/#/builders/1/builds/42" in b.url
    assert b.status == "success"
