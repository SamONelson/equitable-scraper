# Equitable-Scraper

A Selenium script that logs into the Equitable Life client portal, opens the **Values** page of each of your policies, and saves the figures to `Policy_data.csv`. It runs headless Chromium inside a Docker container, so you don't need a browser or chromedriver on the host.

## Features

- Completes the portal's Auth0 login: clicks **Log in with email**, then submits the email and password
- Handles the **MFA / email verification code** prompt when the portal asks for one (from an env var, a file, or typed in interactively)
- Finds every policy on the account overview and reads 10 values from each policy's **Values** page (cash value, surrender value, loan balances and more)
- Writes **one CSV row per policy**, including a base64 screenshot of that policy's Values page
- Takes a **screenshot at each step** of the run, so you can see where it got to
- On failure, saves the **page HTML, a screenshot and an error log** to an `error/` folder
- Always logs out at the end, even if scraping fails partway

## Files

| File | Purpose |
|------|---------|
| `src/main.py` | The scraper: config, browser setup, login, MFA, scraping and logout |
| `src/policy.py` | `Policy` data model and the CSV writer |
| `src/test.py` | Unit tests for `policy.py` (no browser or network needed) |
| `Dockerfile` | `python:3.12-slim` image with Chromium and chromedriver; runs `main.py` |
| `requirements.txt` | Python dependencies (`selenium==4.21.0`) |
| `.env` | Your portal credentials (gitignored and excluded from the Docker build) |
| `AGENTS.md` | Notes for AI coding agents working on the project |

## Setup

### 1. Create your `.env` file

Create `.env` in the project root:

```sh
PORTAL_URL=https://client.equitable.ca/landing/en/log-in
USERNAME=your_email@example.com
PASSWORD=your_password
```

`.env` is listed in `.gitignore` and `.dockerignore`, so it is never committed or copied into the image.

### 2. Build the image

```bash
docker build -t equitable-scraper:latest .
```

Rebuild whenever you change anything in `src/` or the `Dockerfile`.

### 3. Run it

```bash
mkdir -p docker-volume
```

```bash
docker run -it --rm \
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp \
  -e SE_CACHE_PATH=/tmp/selenium \
  --env-file .env \
  -v "$PWD/docker-volume:/opt/equitable-scraper/policy-data" \
  equitable-scraper:latest
```

- The volume mount keeps the results after the container exits. Without it, the CSV and screenshots are lost.
- `--user`, `HOME` and `SE_CACHE_PATH` run the container as your own user, so the output files belong to you and not to root. Selenium needs a writable home and cache directory when it runs as a non-root user.
- `-it` is optional. It lets you type an MFA code if the portal asks for one (see below).
- On SELinux hosts (e.g. Fedora), add `:z` to the mount: `-v "$PWD/docker-volume:/opt/equitable-scraper/policy-data:z"`.

Results appear in `docker-volume/`.

### 4. MFA codes (optional)

You can skip this step. The scraper only needs a code if the portal asks for one after the password. If it doesn't, the login goes straight through and none of the settings below are used.

When the portal does ask, the scraper looks for the code in this order:

1. The `MFA_CODE` environment variable
2. A file at the path in `MFA_CODE_FILE`. This is a path inside the container, so put the file in a mounted folder.
3. Typing it in at a prompt, if the container has a terminal (`docker run -it`)

If none of these is available, the run stops with `RuntimeError: MFA code required...`.

## Configuration

Settings are read from environment variables. Pass them with `--env-file`, not `-e`, so your password doesn't end up in your shell history or in `ps` output.

### Required

| Variable | Description |
|----------|-------------|
| `PORTAL_URL` | Portal login page URL |
| `USERNAME` | Portal login email |
| `PASSWORD` | Portal password |

If one is missing, empty, or still set to `NOT_DEFINED` (the image default), the scraper prints `Must provide Environment Variable: <NAME>` and exits.

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `OUTPUT_FOLDER` | `/opt/equitable-scraper/policy-data` in Docker, `.` otherwise | Where the CSV, screenshots and `error/` folder are written |
| `MFA_CODE` | *(none)* | Verification code, used only if the portal asks for one |
| `MFA_CODE_FILE` | *(none)* | Path to a file containing the verification code, used only if the portal asks for one |

### Command-line arguments

You can pass the three required values as arguments instead: `python main.py <PORTAL_URL> <USERNAME> <PASSWORD>`. When arguments are given, the environment variables are ignored. Avoid this for the same reason as `-e`.

### Selectors and timeouts

The CSS and XPath selectors for the portal's pages are constants at the top of `src/main.py`. If the portal's markup changes and the scraper can't find something, update them there. Page waits time out after 30 seconds (`DEFAULT_TIMEOUT`), and the login step waits up to 60 seconds.

## Data files

Everything is written to `OUTPUT_FOLDER` (`docker-volume/` with the run command above):

| Path | Contents |
|------|----------|
| `Policy_data.csv` | A header row plus one row per policy |
| `<timestamp>-<step>.png` | A screenshot from each step, e.g. `2026-10-30_02-37-27-login-username.png` |
| `error/page_source.html` | HTML of the page the scraper was on when it failed |
| `error/<timestamp>-failure.png` | Screenshot at the moment of failure |
| `error/log.txt` | Exception type and message, timestamp and current URL |

Screenshots build up over runs, but the CSV and the files in `error/` are replaced each time.

### CSV columns

All values are saved as text exactly as the portal shows them (e.g. `$23,449.75`). If a label isn't found on a policy's page, its column contains `None`.

| Column | Portal label it is read from |
|--------|------------------------------|
| `key` | Policy number from the account overview |
| `screenshotBase64` | Base64 PNG screenshot of the policy's Values page |
| `cashValue` | Cash Value of Paid Up Additions |
| `divDepo` | Dividends on Deposit |
| `loanBalance` | Loan Balance |
| `automaticPremiumLoanBalance` | Automatic Premium Loan Balance |
| `totalSurrender` | Total Cash Surrender Value |
| `loanAvailable` | Loan Available |
| `cashValuePUA` | Guaranteed Cash Value |
| `premiumDepositFund` | Premium Deposit Fund |
| `loanInterestCapitalized` | Loan Interest Capitalized |
| `totalAdjustedCostBasis` | Total Adjusted Cost Basis |

The CSV is written even when a run fails. If the failure happens before any policy is scraped, `Policy_data.csv` is replaced with an **empty file**, so copy it somewhere else if you want to keep earlier results.

The CSV contains your policy numbers, balances and screenshots of your policy pages, so treat it as sensitive.

## Running the tests

The tests only cover `policy.py` and don't need Selenium or a network connection.

```bash
cd src && python3 -m unittest -v test.py
```

Or inside the image:

```bash
docker run --rm --entrypoint python equitable-scraper:latest -m unittest -v test
```

## Running without Docker

You need Python 3.12+, Chrome or Chromium, and a matching chromedriver on your `PATH`.

```bash
pip install -r requirements.txt
```

```bash
set -a; source .env; set +a
OUTPUT_FOLDER=./docker-volume python3 src/main.py
```

Without `OUTPUT_FOLDER`, the output goes to the current directory.

## Troubleshooting

- **`Must provide Environment Variable: NAME`**: that variable is missing or empty. Check `.env` and make sure you passed `--env-file .env`.
- **`Login failed: ...`**: the portal showed an error message, usually because of wrong credentials. The message is the portal's own text.
- **`MFA code required...`**: the portal asked for a verification code and none was supplied. See [MFA codes](#4-mfa-codes-optional).
- **Timeouts or selector errors**: the portal's markup may have changed. Look at `error/page_source.html` and the failure screenshot, then update the selectors at the top of `src/main.py`.
- **`Policy key/arrow count mismatch`**: the account overview page didn't match the selectors the scraper expects. Fix it the same way as selector errors.
- **Output files owned by root**: you ran the container without `--user`. Fix ownership with `sudo chown -R "$USER":"$USER" docker-volume`.
