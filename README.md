# 🚗 IlCarro Test Automation Framework

Robust, production-ready hybrid test automation framework for the "IlCarro" (Car Rental) web application. 

This project demonstrates a senior-level approach to QA automation, combining classic UI testing, API integration, and modern tools to ensure fast, stable, and secure test execution.

## 🛠️ Tech Stack
* **Language:** Python 3.12
* **Frameworks:** Pytest, Selenium WebDriver, Playwright (Sync API)
* **API Testing:** Requests
* **Data Generation:** Faker
* **Reporting:** Allure Report
* **CI/CD:** GitHub Actions, GitHub Pages
* **Notifications:** Telegram Bot API

## 🚀 Key Architectural Features

* **Hybrid Testing Approach:** Tests use API calls to set up preconditions (e.g., creating a car or user) and teardown data, drastically reducing UI test execution time and ensuring test isolation.
* **Dual Framework Support:** Implemented primarily using **Selenium (Page Object Model)** with an integrated **Playwright** module to demonstrate modern tool capabilities (Strict Mode, Auto-waiting, Browser Contexts).
* **Smart Browser Cascading:** The framework automatically detects the environment. It runs headless Google Chrome in CI/CD (GitHub Actions) for consistency, but gracefully falls back to Microsoft Edge for local execution if Chrome is unavailable.
* **Dynamic Data Generation:** Uses dynamic querying to the backend API to fetch a valid list of cities for testing, avoiding hardcoded data and preventing false negatives due to data desynchronization.
* **Security & Log Masking:** Sensitive data (passwords, tokens) are strictly masked (`********`) in all console outputs, test logs, and Allure reports.
* **Legacy Bug Handling:** Integrates a quarantine pattern for known frontend-backend data mismatches (e.g., the 'Beersheba'/'Beer Sheva' 400 Bad Request integration bug), utilizing `@pytest.mark.xfail` to document the issue without failing the pipeline.
* **Parallel Execution Ready:** Configured to run concurrently using `pytest-xdist` with strictly isolated test environments.

## ⚙️ Setup & Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/QA3553_IlCarro_Tests.git
   ```
2. Create and activate a virtual environment.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install
   ```
4. Create a `.env` file in the root directory and add your credentials:
   ```env
   USER_EMAIL=your_test_email@gmail.com
   USER_PASSWORD=your_secure_password
   HEADLESS_MODE=false
   ENABLE_CONSOLE_LOGS=true
   ```

## 🏃‍♂️ How to Run Tests

**Run all Selenium UI and API tests (recommended with 3 workers for stability):**
```bash
pytest tests/ -s -n 3 --alluredir=allure-results
```

**Run modern Playwright tests (headed mode):**
```bash
pytest tests/test_playwright_login.py -s --headed
```

**Generate and view Allure Report locally:**
```bash
allure serve allure-results
```

## 📊 CI/CD Pipeline
The project is fully integrated with **GitHub Actions**. Upon every manual dispatch, the pipeline:
1. Sets up the Python environment and installs dependencies.
2. Executes the full test suite in headless mode.
3. Generates an Allure Report.
4. Deploys the report to GitHub Pages.
5. Sends a Telegram notification with a direct link to the test results.

---
*Author: Maxim Vinogradov*