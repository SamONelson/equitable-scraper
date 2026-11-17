import os
import sys
from dataclasses import dataclass
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from policy import Policy, PolicyValueCodes, write_policies_csv

USERNAME_INPUT_FIELD_ID = "username"
PASSWORD_INPUT_FIELD_ID = "password"
LOGIN_WITH_EMAIL_BUTTON_XPATH = "//button[normalize-space()='Log in with email']"
LOGIN_CONTINUE_BUTTON_CSS_SELECTOR = "button[data-action-button-primary='true']"
LOGIN_ALERT_CSS_SELECTOR = "#prompt-alert"

POLICY_KEYS_TEXT_XPATH = (
    "//div[contains(@class,'clickable_policy')]"
    "//p[contains(@class,'policy_label') and normalize-space()='Policy']"
    "/following-sibling::p[contains(@class,'policy_data')]"
)
POLICY_ARROW_BUTTON_XPATH = "//a[contains(@class,'policy_link_arrow')]"

# Values page
VALUES_ROWS_XPATH = "//div[contains(@class,'details_row')]"
POLICY_KEYS_TEXT_ATTRIBUTE = "innerHTML"

POLICY_DATA_VALUES_TAB_ID = "Values"
POLICY_DATA_VALUES_TABLE_VALUES_XPATH = "//div[@id='policy_details']//div[@class='Values']//p"
POLICY_DATA_VALUES_TABLE_VALUES_ATTRIBUTE = "innerHTML"

BACK_BUTTON_XPATH = "//*[contains(@class, 'back_link')]"
LOGOUT_BUTTON_XPATH = "//*[@class='btn_logout']"

DEFAULT_TIMEOUT = 30
OUTPUT_FILENAME = 'Policy_data.csv'


@dataclass
class Config:
    portal_url: str
    username: str
    password: str


def check_environment(name):
    value = os.environ.get(name, 'NOT_DEFINED')
    if not value.strip() or value == 'NOT_DEFINED':
        print(f"Must provide Environment Variable: {name}")
        sys.exit(-1)
    print(f"Checked {name}")
    return value


def config_from_args(argv):
    if len(argv) != 4:
        print("Must provide exact arguments. PortalUrl Username Password")
        sys.exit(-1)
    print("# of args provided", len(argv))
    return Config(
        portal_url=argv[1],
        username=argv[2],
        password=argv[3],
    )


def config_from_environment():
    names = ['PORTAL_URL', 'USERNAME', 'PASSWORD']
    print("# of args provided", 0)
    values = {name: check_environment(name) for name in names}
    return Config(
        portal_url=values['PORTAL_URL'],
        username=values['USERNAME'],
        password=values['PASSWORD'],
    )


def load_config(argv=None):
    argv = sys.argv if argv is None else argv
    if len(argv) > 1:
        config = config_from_args(argv)
        print("Properties to scrape set from CLI Args.")
        return config
    config = config_from_environment()
    print("Properties to scrape set from Docker Environment.")
    return config


def setup_webdriver():
    print('webdriver setup')
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    driver.set_window_size(1920, 1080)
    return driver


def output_folder():
    return os.environ.get('OUTPUT_FOLDER') or '.'


def take_screenshot(driver, location):
    folder = output_folder()
    os.makedirs(folder, exist_ok=True)
    now = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    name = f'{now}-{location}.png'
    driver.save_screenshot(os.path.join(folder, name))


def set_input(input_element: WebElement, value):
    input_element.clear()
    input_element.send_keys(value)


def wait_for(driver, locator, timeout=DEFAULT_TIMEOUT):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located(locator))


def wait_clickable(driver, locator, timeout=DEFAULT_TIMEOUT):
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(locator))


def element_text(element):
    return ' '.join((element.text or element.get_attribute('textContent') or '').split())


def wait_for_login(driver, timeout=60):
    def login_state(d):
        # Success
        if d.find_elements(By.XPATH, LOGOUT_BUTTON_XPATH):
            return 'logged_in'

        # Explicit error message
        for alert in d.find_elements(By.CSS_SELECTOR, LOGIN_ALERT_CSS_SELECTOR):
            message = element_text(alert)
            if message:
                return ('error', message)

        # MFA / email verification code prompt still present
        if d.find_elements(By.ID, 'code'):
            return 'mfa_code'

        return False

    result = WebDriverWait(driver, timeout).until(login_state)

    if isinstance(result, tuple):
        raise RuntimeError(f"Login failed: {result[1]}")

    if result == 'logged_in':
        return  # done

    # ----- MFA path -----
    if result == 'mfa_code':
        code_input = wait_for(driver, (By.ID, 'code'))
        mfa_code = os.environ.get('MFA_CODE')
        if not mfa_code:
            mfa_code_file = os.environ.get('MFA_CODE_FILE')
            if mfa_code_file and os.path.isfile(mfa_code_file):
                with open(mfa_code_file, 'r') as f:
                    mfa_code = f.read().strip()
            elif sys.stdin.isatty() and sys.stdout.isatty():
                print("MFA / email verification code required.")
                mfa_code = input("Enter MFA code: ").strip()
            else:
                raise RuntimeError(
                    "MFA code required. Set the MFA_CODE environment variable, "
                    "or create MFA_CODE_FILE pointing to a file containing the code, "
                    "or run the tool interactively (e.g., docker run -it)."
                )
        if not mfa_code:
            raise RuntimeError("Empty MFA code supplied")

        set_input(code_input, mfa_code)
        wait_clickable(driver, (By.CSS_SELECTOR, LOGIN_CONTINUE_BUTTON_CSS_SELECTOR)).click()

        # Wait only for the final logged-in state (or a real error)
        def after_mfa(d):
            if d.find_elements(By.XPATH, LOGOUT_BUTTON_XPATH):
                return 'logged_in'
            for alert in d.find_elements(By.CSS_SELECTOR, LOGIN_ALERT_CSS_SELECTOR):
                message = element_text(alert)
                if message:
                    return ('error', message)
            # Still sitting on the code page → invalid/expired code
            if d.find_elements(By.ID, 'code'):
                return False
            return False

        post = WebDriverWait(driver, DEFAULT_TIMEOUT).until(after_mfa)
        if isinstance(post, tuple):
            raise RuntimeError(f"Login failed after MFA: {post[1]}")
        # We are now logged in – no recursion needed
        return

def navigate_to_equitable(driver, config):
    print("navigate to equitable")
    driver.get(config.portal_url)
    wait_clickable(driver, (By.XPATH, LOGIN_WITH_EMAIL_BUTTON_XPATH))
    take_screenshot(driver, 'navigate_to_equitable')


def login(driver, config):
    print('login')
    wait_clickable(driver, (By.XPATH, LOGIN_WITH_EMAIL_BUTTON_XPATH)).click()

    username = wait_clickable(driver, (By.ID, USERNAME_INPUT_FIELD_ID))
    set_input(username, config.username)
    take_screenshot(driver, 'login-username')
    wait_clickable(driver, (By.CSS_SELECTOR, LOGIN_CONTINUE_BUTTON_CSS_SELECTOR)).click()

    password = wait_clickable(driver, (By.ID, PASSWORD_INPUT_FIELD_ID))
    set_input(password, config.password)
    take_screenshot(driver, 'login-password')
    wait_clickable(driver, (By.CSS_SELECTOR, LOGIN_CONTINUE_BUTTON_CSS_SELECTOR)).click()
    wait_for_login(driver)


def scrape_policies_data(driver):
    print('scraping policies data')

    # Wait until the policy cards have actually appeared
    WebDriverWait(driver, DEFAULT_TIMEOUT).until(
        lambda d: len(d.find_elements(By.XPATH, POLICY_ARROW_BUTTON_XPATH)) > 0
    )
    take_screenshot(driver, 'scrape_policies_data')

    policy_key_elements = driver.find_elements(By.XPATH, POLICY_KEYS_TEXT_XPATH)
    policy_arrow_elements = driver.find_elements(By.XPATH, POLICY_ARROW_BUTTON_XPATH)

    if len(policy_key_elements) != len(policy_arrow_elements):
        raise RuntimeError(
            f"Policy key/arrow count mismatch: {len(policy_key_elements)} keys vs "
            f"{len(policy_arrow_elements)} arrows"
        )

    policies = []
    for policy_key_element, policy_arrow_element in zip(policy_key_elements, policy_arrow_elements):
        policy_key = policy_key_element.get_attribute(POLICY_KEYS_TEXT_ATTRIBUTE)
        policies.append(scrape_policy_data(driver, policy_key, policy_arrow_element))
    return policies

def scrape_policy_data(driver, policy_key, policy_arrow_element: WebElement):
    print('scraping policy')
    take_screenshot(driver, 'scrape_policy_data-policy-arrow')
    policy_arrow_element.click()

    # Wait for details page (AJAX content that contains the Values link)
    WebDriverWait(driver, DEFAULT_TIMEOUT).until(
        lambda d: d.find_elements(By.ID, "Values")
    )
    take_screenshot(driver, 'scrape_policy_data-details-loaded')

    # Get the real Values URL and navigate directly
    values_link = driver.find_element(By.ID, "Values")
    values_url = values_link.get_attribute("href")
    print(f"Navigating to Values page: {values_url}")
    driver.get(values_url)

    # Wait for Values content
    WebDriverWait(driver, DEFAULT_TIMEOUT).until(
        lambda d: "/Policy/Values/" in d.current_url
        and d.find_elements(By.XPATH, "//div[contains(@class,'details_row')]")
    )
    take_screenshot(driver, 'scrape_policy_data-values-page')

    # Parse rows
    rows = driver.find_elements(By.XPATH, "//div[contains(@class,'details_row')]")
    values = {}
    for row in rows:
        label_ps = row.find_elements(By.CSS_SELECTOR, ".detail_label p")
        value_ps = row.find_elements(By.CSS_SELECTOR, ".grid_8 p, .grid_2 p")
        labels = [element_text(p) for p in label_ps if element_text(p)]
        vals   = [element_text(p) for p in value_ps if element_text(p)]
        for i, label in enumerate(labels):
            if i < len(vals):
                values[label] = vals[i]

    print("Extracted Values page labels:")
    for k, v in values.items():
        print(f"  '{k}' → '{v}'")

    policy = Policy()
    policy.key = policy_key
    policy.screenshotBase64 = driver.get_screenshot_as_base64()

    def get_val(*candidates):
        for label, val in values.items():
            for cand in candidates:
                if cand.lower() in label.lower():
                    return val
        return None

    policy.cashValue                   = get_val("Cash Value of Paid Up Additions", "Cash Value of PUA")
    policy.divDepo                     = get_val("Dividends on Deposit")
    policy.loanBalance                 = get_val("Loan Balance")
    policy.automaticPremiumLoanBalance = get_val("Automatic Premium Loan Balance")
    policy.totalSurrender              = get_val("Total Cash Surrender Value")
    policy.loanAvailable               = get_val("Loan Available")
    policy.cashValuePUA                = get_val("Guaranteed Cash Value")
    policy.premiumDepositFund          = get_val("Premium Deposit Fund")
    policy.loanInterestCapitalized     = get_val("Loan Interest Capitalized")
    policy.totalAdjustedCostBasis      = get_val("Total Adjusted Cost Basis")

# Go back to Account Overview – more reliable than the Back button
    overview_url = driver.current_url.split("/policy/")[0] + "/client/en"
    # Fallback if the split fails
    if "client/en" not in overview_url:
        overview_url = "https://www.equitable.ca/client/en"   # or whatever your portal base is

    print(f"Returning to overview: {overview_url}")
    driver.get(overview_url)

    WebDriverWait(driver, DEFAULT_TIMEOUT).until(
        lambda d: d.find_elements(By.XPATH, POLICY_ARROW_BUTTON_XPATH)
        or "Account Overview" in d.title
    )
    return policy

def logout(driver):
    print('logout')
    wait_clickable(driver, (By.XPATH, LOGOUT_BUTTON_XPATH)).click()
    take_screenshot(driver, 'logout')


def main(argv=None):
    config = load_config(argv)
    driver = setup_webdriver()
    policies = []
    logged_in = False
    try:
        navigate_to_equitable(driver, config)
        login(driver, config)
        logged_in = True
        policies = scrape_policies_data(driver)
    except Exception as e:
        print("Scrape failed; taking failure screenshot and saving error info")
        error_dir = os.path.join(output_folder(), 'error')
        os.makedirs(error_dir, exist_ok=True)
        # save current page HTML
        try:
            with open(os.path.join(error_dir, 'page_source.html'), 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
        except Exception as html_exc:
            print(f"Failed to save page source: {html_exc}")
        # save screenshot inside error folder
        try:
            ts = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            driver.save_screenshot(os.path.join(error_dir, f'{ts}-failure.png'))
        except Exception as screenshot_exc:
            print(f"Failure screenshot failed: {screenshot_exc}")
        # write exception info to a log file
        try:
            with open(os.path.join(error_dir, 'log.txt'), 'w', encoding='utf-8') as f:
                f.write(f"Exception type: {type(e).__name__}\n")
                f.write(f"Exception message: {str(e)}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"URL: {driver.current_url}\n")
        except Exception as log_exc:
            print(f"Failed to write log: {log_exc}")
        raise
    finally:
        try:
            path = write_policies_csv(policies, OUTPUT_FILENAME)
            print(f"Wrote {len(policies)} policy record(s) to {path}")
        finally:
            if logged_in:
                try:
                    logout(driver)
                except Exception as exc:
                    print(f"Logout failed: {exc}")
            driver.quit()
    return policies


if __name__ == '__main__':
    main()
