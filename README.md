# Buildbot Failed Builds Reporter

This script collects the latest failed builds from a [Buildbot](https://buildbot.net/) instance, generates both an **HTML report** and a **CSV file**, and sends them via email using an SMTP relay (IP-based authentication).

## Features

- ✅ Fetches builders and latest builds per branch from the Buildbot API
- ✅ Filters builds by branch and builder names. See Config.
- ✅ Identifies **failed builds**
- ✅ Generates:
  - HTML tables grouped by branch
  - A CSV report with details for each failed build
- ✅ Sends an email with both the HTML report (inline) and the CSV as an attachment
- ✅ SMTP relay connection with **IP-based authentication** (no login required)

## Requirements

- Buildbot REST API (v2) accessible
- SMTP relay server accessible from the host machine
- [Google Workspace SMTP relay](https://support.google.com/a/answer/176600?hl=en) or similar

## Config

- the configuration file can be either a local file or a URL. To use an URL set `CONFIG_URL` in the `.env` file
- `branches` list for making calls to buildbot `/changes` api and retrieve the latest builds per branch
- `builder_filter` empty to get results for all builders from the `/builders` API


## How to run

Set according to your setup:
```
SENDER=#SENDER_EMAIL#
RECIPIENT_EMAIL=#RECEIVER_EMAIL#
SMTP_RELAY_SERVER=smtp-relay.gmail.com
SMTP_RELAY_PORT=465
BASE_BUILDBOT_URL=#BUILDBOT BASE URL#
```

```bash
pip install -r requirements.txt
python3 failman.py
```

Or in `Docker` as a scheduled event. Set the desired schedule in `crontab`
```
docker build -t failman .
docker run -d --name failman failman
```

The repository default `config.yaml` is present in the image and used when no
`CONFIG_URL` is set in the `.env` file.

