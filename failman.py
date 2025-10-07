import csv
import os
import smtplib
from collections import defaultdict
from dataclasses import dataclass
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from io import StringIO
from typing import Dict, List

import requests
import yaml
from dotenv import load_dotenv


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

@dataclass
class Build:
    name: str
    url: str
    commit: str
    branch: str
    status: str


def load_config(config_path_or_url):
    if config_path_or_url.startswith("http://") or config_path_or_url.startswith("https://"):
        resp = requests.get(config_path_or_url)
        resp.raise_for_status()
        config = yaml.safe_load(resp.text)
    else:
        with open(config_path_or_url, "r") as file:
            config = yaml.safe_load(file)
    return config

def builds_to_csv(builds: List[Build]) -> str:
    """
    Generate a CSV string from Build objects.
    """
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Branch", "Build", "Commit", "Status", "URL"])
    for b in builds:
        writer.writerow([b.branch, b.name, b.commit, b.status, b.url])
    return output.getvalue()


def builds_to_html_table(builds: List[Build]) -> str:
    # Group builds by branch
    grouped: Dict[str, List[Build]] = defaultdict(list)
    for b in builds:
        grouped[b.branch].append(b)

    # Separator — Gmail-friendly horizontal line with padding
    separator = "<hr style='border:none;border-top:1px solid #ccc;margin:20px 0;'>"

    html_parts = []

    # Sort branches descending
    for branch in sorted(grouped.keys(), reverse=True):
        builds_in_branch = grouped[branch]

        # Branch header
        html_parts.append(f"<h3>Branch: {branch}</h3>")
        html_parts.append(separator)

        # Sort builds by name ascending inside the branch
        builds_in_branch_sorted = sorted(builds_in_branch, key=lambda b: b.name.lower())

        # Build table for this branch
        rows = ["<tr><th>Build</th><th>Commit</th><th>Status</th></tr>"]
        for b in builds_in_branch_sorted:
            hyperlink = f'<a href="{b.url}">{b.name}</a>'
            rows.append(
                f"<tr>"
                f"<td>{hyperlink}</td>"
                f"<td>{b.commit}</td>"
                f"<td>{b.status}</td>"
                f"</tr>"
            )
        table_html = f"<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse'>{''.join(rows)}</table>"
        html_parts.append(table_html)

        # Separator after table
        html_parts.append(separator)

    return "\n".join(html_parts)


def send_email_with_csv(
    sender_email: str,
    recipient_email: str,
    subject: str,
    html_body: str,
    csv_content: str,
    smtp_relay: str,
    smtp_port: int
) -> None:
    """
    Send an HTML email via Gmail with a CSV attachment.
    """
    msg = MIMEMultipart("mixed")
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = subject

    # Add HTML body
    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(html_body, "html", 'utf-8'))
    msg.attach(alternative)

    # Attach CSV
    part = MIMEBase("application", "octet-stream")
    part.set_payload(csv_content.encode("utf-8"))
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", 'attachment; filename="builds_report.csv"')
    msg.attach(part)

    with smtplib.SMTP_SSL(smtp_relay, smtp_port) as smtp:
        # No login, IP-based authentication handled by Google
        smtp.sendmail(sender_email, recipient_email, msg.as_string())

def get_builders_details(api_url):
    url = f"{api_url}/builders"
    response = requests.get(url)
    data = response.json()
    filtered = [b for b in data.get("builders", [])]
    return filtered


def get_latest_builds_on_branch(branch, api_url):
    url = f"{api_url}/changes?branch={branch}&limit=1&order=-changeid"
    response = requests.get(url)
    data = response.json()
    changes = data.get("changes", [])
    return changes


def join_builders_with_change(builders, builds, branch, revision, buildbot_url):
    build_map = {b["builderid"]: b for b in builds}
    builds = []
    for builder in builders:
        builderid = builder["builderid"]
        build_data = build_map.get(builderid)

        if build_data:
            builds.append(
                Build(
                    name=builder["name"],
                    branch=branch,
                    commit=revision,
                    url=f"{buildbot_url}#/builders/{builder['builderid']}/builds/{build_data.get('number')}",
                    status=build_data.get("state_string"),
                )
            )
    return builds


if __name__ == "__main__":
    # INIT
    load_dotenv()
    subject = os.getenv("SUBJECT")
    default_config_path = os.path.join(SCRIPT_DIR, "config.yaml")
    config_location = os.getenv("CONFIG_URL", default_config_path)
    config = load_config(config_location)
    sender = os.getenv("SENDER")
    recipient = os.getenv("RECIPIENT_EMAIL")
    buildbot_url = os.getenv("BASE_BUILDBOT_URL")
    api_url = buildbot_url + "api/v2"
    smtp_relay = os.getenv("SMTP_RELAY_SERVER")
    smtp_port = int(os.getenv("SMTP_RELAY_PORT"))

    BUILDS = []
    builders = get_builders_details(api_url)
    filtered_builders = set(config["configuration"].get("builder_filter") or [])
    builders = [builder for builder in builders if not filtered_builders or builder["name"] in filtered_builders]

    for branch in config["configuration"]["branches"]:
        changes = get_latest_builds_on_branch(branch, api_url)
        if changes:
            builds = join_builders_with_change(
                builders,
                builds=changes[0]["builds"],
                branch=changes[0]["sourcestamp"]["branch"],
                revision=changes[0]["sourcestamp"]["revision"],
                buildbot_url=buildbot_url,
            )
            BUILDS.extend(builds)
    failed_builds = [
        b
        for b in BUILDS
        if b.status.lower() not in ["acquiring locks", "building", "build successful", "preparing worker"]
    ]

    if failed_builds:
        html_content = builds_to_html_table(failed_builds)
        csv_content = builds_to_csv(failed_builds)
        send_email_with_csv(
            sender, recipient, subject, html_content, csv_content, smtp_relay, smtp_port
        )
    else:
        print("Grab a coffee and enjoy a bug free world!")
