# AGENTS.md

Guidance for working in the Equitable-Scraper project.

## What this project is

A Selenium scraper that logs into the Equitable Life policy portal, visits each
policy's **Values** tab, records cash/surrender/loan figures, and writes them to
`Policy_data.csv` along with a base64 screenshot per policy.

- `src/main.py` — CLI/env config, browser setup, two-step login, scrape flow, logout.
- `src/policy.py` — `Policy` data model, `PolicyValueCodes` labels, CSV writer.
- `src/test.py` — `unittest` suite for the policy model and CSV writer.
- `Dockerfile` — `python:3.12-slim` + Chromium/chromedriver; runs `main.py`.
- `.env` — local credentials (gitignored, excluded from the Docker build context).

## Requirements

- Python 3.12+ (the code uses PEP 701 f-strings and structural pattern matching).
- To run for real: Chrome/Chromium + matching chromedriver, or Docker.
- `selenium==4.21.0` (see `requirements.txt`).

## Configuration

Set these via environment variables, an env file, or (discouraged) 3 CLI args:

| Name | Meaning |
| --- | --- |
| `PORTAL_URL` | Portal login URL |
| `USERNAME` | Portal username |
| `PASSWORD` | Portal password |
| `OUTPUT_FOLDER` | Directory for CSV + screenshots (defaults to `.`) |

CLI form (positional, 3 args):
`main.py <PORTAL_URL> <USERNAME> <PASSWORD>`

If any variable is missing the process exits with `-1` and prints the missing name.

Login is a three-step Auth0 flow: on the React landing page click
`Log in with email`, enter the username/email and submit, then enter the
password and submit. There is no security-question step. The old landing page
exposed `#username` directly; the new one requires the `Log in with email`
button first.

## Run with Docker

```sh
docker build -t equitable-scraper:latest .

docker run --rm \
  --env-file .env \
  -v "$PWD/docker-volume:/opt/equitable-scraper/policy-data" \
  equitable-scraper:latest
```

Do not pass secrets with `-e PASSWORD=...`; it exposes them in shell history and
`ps`. Use `--env-file`. Never commit `.env`.

## Run locally (Linux, with Chrome installed)

```sh
pip install -r requirements.txt
PORTAL_URL=... USERNAME=... PASSWORD=... \
OUTPUT_FOLDER=./docker-volume python src/main.py
```

## Tests and checks

```sh
cd src && python3 -m unittest -v test.py
python3 -m py_compile src/main.py src/policy.py src/test.py
```

`src/test.py` only covers `policy.py`; it does not need Selenium or network.

## Behaviour and gotchas

- Every run overwrites `OUTPUT_FOLDER/Policy_data.csv`; it is not appended.
- The CSV has one header row and one row per policy (all policies are collected
  before writing).
- The CSV is written before logout so a logout failure does not lose data.
- Waits use `WebDriverWait` (30s default) instead of `time.sleep`.
- Selectors are module-level constants at the top of `main.py`; update them if
  the portal markup changes.
- `get_table_value` returns `None` if a label has no following value element.
- Screenshots are written to `OUTPUT_FOLDER` as `<timestamp>-<step>.png`.
- `Policy.screenshotBase64` is stored in the CSV and makes the file large; it is
  intentionally part of the output.
- The browser runs headless with `--no-sandbox` (required in the container).

## Style

- Keep stdlib-first; the only third-party dependency is Selenium.
- Match the existing `snake_case` functions and UPPER_CASE constants.
- Do not add comments-only changes; keep diffs focused.
