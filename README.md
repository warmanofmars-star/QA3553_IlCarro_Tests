# 🚗 IlCarro Hybrid Test Automation Framework

[![UI Tests in Docker](https://github.com/warmanofmars-star/QA3553_IlCarro_Tests/actions/workflows/tests.yml/badge.svg)](https://github.com/warmanofmars-star/QA3553_IlCarro_Tests/actions)
📊 **Live Allure Report:** [View Dashboard](https://warmanofmars-star.github.io/QA3553_IlCarro_Tests/)

Robust, production-ready hybrid test automation framework for the "IlCarro" (Car Rental) web application, featuring a fully containerized **Infrastructure as Code (IaC)** approach and cross-browser CI/CD matrix execution.

This project demonstrates a senior-level approach to QA automation, combining classic UI testing, API integration, remote browser execution via Selenoid, advanced network mocking, and modern container orchestration.

## 🛠️ Tech Stack
* **Language:** Python 3.12
* **UI Frameworks:** Selenium WebDriver (Chrome, Firefox, Edge), Playwright (Sync API)
* **API Testing:** Requests
* **Containerization & Orchestration:** Docker, Docker Compose, Selenoid (with video-recorder)
* **Test Runner:** Pytest (with `pytest-xdist` for parallel execution)
* **Data Generation:** Faker & UUID
* **Reporting:** Allure Report (with embedded test session videos)
* **CI/CD:** GitHub Actions (Fully containerized pipeline execution with Build Matrix)
* **Notifications:** Telegram Bot API

## 🚀 Key Architectural Features

* **Cross-Browser CI/CD Matrix:** Configured GitHub Actions matrix strategy to dynamically spawn parallel test suites in Google Chrome and Mozilla Firefox inside isolated Docker containers.
* **Dockerized Infrastructure (IaC):** The entire test environment (framework, Selenoid hub, Chrome/Firefox instances, video recording) is orchestrated via Docker Compose, guaranteeing absolute consistency across local machines and CI/CD.
* **Allure Report Deduplication:** Custom Python data-processing injection inside the CI/CD pipeline ensures accurate merging of parallel matrix test execution results without data collisions.
* **Strict Data Isolation (Sandbox Users):** Employs a robust `temp_user` fixture that dynamically registers a unique user via API before each test. This eliminates race conditions during aggressive parallel execution (`pytest-xdist`) and leaves the database unpolluted.
* **Universal Video Attachment:** Every Selenium test is recorded via FFmpeg/Selenoid, while Playwright tests utilize the native recording engine. All resulting .mp4 files are automatically attached to the Allure report upon teardown.
* **Hybrid Testing Approach:** Tests use API calls to set up preconditions (e.g., creating a car or user) and teardown data, drastically reducing UI test execution time.
* **Network Interception & Mocking:** Utilizes Playwright's `page.route()` to intercept backend requests (e.g., fetching city lists) and inject mock responses, allowing strict isolation of frontend UI rendering logic from backend stability.
* **Dual Framework Support:** Implemented primarily using **Selenium (Page Object Model)** with an integrated **Playwright** module to demonstrate modern tool capabilities.
* **Smart Browser Cascading:** Automatically detects runtime context and provides seamless CLI configuration via custom `--browser_name` pytest argument.
* **Security & Log Masking:** Sensitive data (passwords, tokens) are strictly masked (********) in all console outputs, test logs, and Allure reports.
* **Context-Aware Custom Logging:** Features a proprietary logging utility, cleanly injected into test suites as a global Pytest fixture, that dynamically adapts to the execution environment, preventing OS-level file locks during parallel runs.
* **API Connection Pooling:** Utilizes `requests.Session()` for backend interactions, reusing TCP connections and automatically managing Bearer tokens.

## ⚙️ Setup & Installation

1. Clone the repository:
```bash
git clone https://github.com/warmanofmars-star/QA3553_IlCarro_Tests.git
```

2. Create and activate a virtual environment.

3. Install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

4. Create a `.env` file in the root directory and add your credentials:
```env
USER_EMAIL=your_test_email@gmail.com
USER_PASSWORD=your_secure_password
HEADLESS_MODE=false
USE_SELENOID=false
ENABLE_CONSOLE_LOGS=true
```

## 🏃‍♂️ How to Run Tests

**Run tests in the isolated Docker container (Recommended):**
```bash
docker compose up --build --exit-code-from qa-framework
```

**Run locally via Pytest (parallel execution & specific browser):**
```bash
pytest tests/ -n 3 --browser_name=firefox --video=on --clean-alluredir --alluredir=allure-results
```

**Run modern Playwright tests (headed mode for debugging):**
```bash
pytest tests/test_playwright_*.py -s --headed
```

**Generate and view Allure Report locally:**
```bash
allure serve allure-results
```

## 📊 CI/CD Pipeline
The project features an advanced **GitHub Actions** pipeline:
* Automatically triggers on manual dispatch (`workflow_dispatch`).
* Configured with a **Build Matrix** to dynamically spawn parallel test suites in Google Chrome and Mozilla Firefox.
* Executes a custom Python script to deduplicate and merge Allure results from multiple browser streams.
* Spins up a clean Linux runner, builds the Docker Compose stack, and executes all tests in parallel.
* Securely injects credentials via **GitHub Secrets**.
* Generates and deploys the unified Allure report to **GitHub Pages**.
* Sends automated execution status notifications with a direct link to Telegram.

## 🏗 Project Structure
```text
QA3553_IlCarro_Tests/
├── .github/workflows/    # CI/CD pipeline configuration with Matrix (tests.yml)
├── api/                  # API Client (Requests) for backend interactions
├── data/                 # Test data generators (Faker, UUID)
├── models/               # Data classes (Car, User)
├── pages/                # Page Object Model classes (Selenium & Playwright)
├── selenoid/             # Selenoid configuration (browsers.json)
├── tests/                # Test suites grouped by context
├── utils/                # Custom logger, WebDriver listener, API helpers
├── logs/                 # Auto-rotating local log files
├── conftest.py           # Pytest fixtures, Selenoid connection, video attachment hooks
├── Dockerfile            # Container definition for the test framework
├── docker-compose.yml    # Infrastructure orchestration (Selenoid + Framework + Network + Volumes)
└── requirements.txt      # Project dependencies
```

---
*Author: Maksim Vinogradov*
