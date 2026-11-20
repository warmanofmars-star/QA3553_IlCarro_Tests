<!-- translation-of: docs/jenkins-setup.md sha256:548689d909c7 -->
# Setting up Jenkins for IlCarro

> Russian original: [jenkins-setup.md](jenkins-setup.md)

A step-by-step guide: how to connect IlCarro to the Jenkins that already runs for Phonebook.
How the pipeline itself works — see [`commands.md`](../commands.md) *(in Russian)*, section “CI: Jenkins”.

## 0. What must already be in place

The same Jenkins as for Phonebook: the `jenkins-master` container (Jenkins 2.580.2), started from the
Phonebook repository with `docker compose -f docker-compose.jenkins.yml up -d --build`.
IlCarro does not need a separate Jenkins: a second container named `jenkins-master` with ports
8080/50000 would not start next to the first one.

Check that:

- http://localhost:8080 opens and the `Phonebook_Docker_Tests` job is there;
- Jenkins has **2 executors** (Manage Jenkins → Nodes → Built-In Node → Configure → Number of executors):
  IlCarro and Phonebook builds can run at the same time;
- Docker inside Jenkins sees the host's Docker. Nothing needs to be run in the Script Console: the first
  build checks this — the log of the `Prepare` stage will contain the output of `docker compose version`.
  Docker Compose **2.24.4 or newer** is required (`docker-compose.jenkins-build.yml` uses the
  `!reset` and `!override` tags). The Jenkins image from Phonebook installs compose from Docker's official
  repository when the image is built — if the version is old, rebuild the image (the command above).

## 1. Plugins

The same ones the Phonebook Jenkinsfile uses, except the Telegram part (IlCarro does not need Credentials Binding for
`TG_BOT_TOKEN`/`TG_CHAT_ID`). Manage Jenkins → Plugins → Installed plugins — all of them must
be enabled:

| Plugin | Why |
|---|---|
| **Pipeline** (`workflow-aggregator`) | Declarative Pipeline: `pipeline { … }`, `catchError`, `unstable`, `withEnv` |
| **Git** (`git`) | Pipeline script from SCM: Jenkins clones the repository itself |
| **GitHub** (`github`) | The “GitHub hook trigger for GITScm polling” trigger and receiving the webhook at `/github-webhook/` |
| **Allure Jenkins Plugin** (`allure-jenkins-plugin`) | The `allure(...)` step: the report and the trend chart on the build page |

“Install suggested plugins” installs these on the first start of Jenkins, except Allure. Since Phonebook
is built with an Allure report, all of this is already installed.

**Allure Commandline:** Manage Jenkins → Tools → Allure Commandline installations — there must be
an installation (Phonebook already has one). The Jenkinsfile does not refer to it by name and uses the one available.

## 2. Create the job

1. Dashboard → **New Item** → a name, for example `IlCarro_Docker_Tests` → type **Pipeline** → OK.
   The name becomes part of the build's compose project name (`ilcarro-jenkins-ilcarro-docker-tests-<номер>`, ending with the build number);
   there are no restrictions on it — the Jenkinsfile converts it to a valid form itself.
2. In the **Triggers** section, tick **GitHub hook trigger for GITScm polling**.
3. In the **Pipeline** section:
   - Definition: **Pipeline script from SCM**;
   - SCM: **Git**;
   - Repository URL: `https://github.com/warmanofmars-star/QA3553_IlCarro_Tests.git`;
   - Credentials: **- none -** — the repository is public;
   - Branch Specifier: `*/main`;
   - Script Path: `Jenkinsfile`;
   - Lightweight checkout — can stay enabled.
4. **Save**.

Do not add the `BROWSER` and `TEST_MARKER` parameters by hand: Jenkins reads them from the Jenkinsfile
during the first build. Before it the button is called **Build Now**, after it — **Build with Parameters**.

## 3. First build

1. Click **Build Now**. The first build runs with the default parameters: `chrome`, all tests.
   The first time it takes longer than usual: the test image is built and the Selenium Grid images are downloaded.
2. Open the build → **Console Output** and check:
   - in the `Prepare` stage — the «Параметры сборки» (“Build parameters”) block (browser, marker, compose project name
     `ilcarro-jenkins-…`) and the line `Docker Compose version …` — the version is 2.24.4 or newer;
   - in each part — the line `Отбор: -m "not selenium" | браузер: chrome | …` (“Selection: … | browser: …”) and `-m "selenium"`;
   - after each part — `Параметры в контейнере подтверждены: SeleniumBrowser=chrome, MarkerFilter=…` (“Parameters confirmed in the container”);
   - at the end — the cleanup: `docker compose down` removes the containers, network, volume and image **only**
     with the `ilcarro-jenkins-…` prefix.
3. Build colour: blue/green — all tests passed; **yellow (UNSTABLE)** — there are failed tests
   (known bugs in the report are xfailed, they do not colour the build); **red (FAILURE)** — a launch failure
   or a parameter that did not reach the container.
4. The build page has an **Allure Report** link. The **Environment** block shows `JenkinsBrowser`
   and `SeleniumBrowser` with the same value, `JenkinsBuild`, `MarkerFilter`
   (`not selenium; selenium` for a full run).
5. Check that no containers are left after the build: `docker ps -a --filter "name=ilcarro-jenkins"` —
   empty.
6. Now **Build with Parameters** → `BROWSER=firefox` → the report and the log must show `firefox`.
   This guards against the Phonebook lesson, where the browser choice was once silently ignored.

## 4. GitHub webhook

The ngrok tunnel is the same as for Phonebook (`ngrok http 8080`). If it is already running, a new one
is not needed: one address receives webhooks from both repositories, and Jenkins finds the job by the repository
URL itself.

1. Copy the HTTPS address from the ngrok console, for example `https://abcd-1234.ngrok-free.app`.
2. GitHub → the IlCarro repository → **Settings → Webhooks → Add webhook**:
   - Payload URL: `https://abcd-1234.ngrok-free.app/github-webhook/` (the trailing slash is required);
   - Content type: `application/json`;
   - Secret: empty;
   - Which events: **Just the push event**;
   - Active: ✓ → **Add webhook**.
3. GitHub sends a test ping right away: in the list of webhooks it must have a green tick
   (Recent Deliveries → response 200).
4. Check: after the next push to `main` (for example, merging a PR) the job gets a new build
   with the cause “Started by GitHub push”. Pushes to other branches reach Jenkins too, but do not start
   a build: the job watches only `main`.

A free ngrok address changes every time the tunnel is restarted — then update the Payload URL
in the webhooks of **both** repositories (IlCarro and Phonebook).

## 5. If something goes wrong

| Symptom | Where to look |
|---|---|
| `yaml: unknown tag !reset` / `!override` | an old Docker Compose in the Jenkins image — rebuild the image (section 0) |
| `Cannot connect to the Docker daemon` | the Jenkins container was started without `/var/run/docker.sock` or not as root — the Jenkins compose file in Phonebook |
| `Параметр BROWSER=… не дошёл до контейнера` (“the BROWSER parameter did not reach the container”) | the build is red on purpose: the tests ran in the wrong browser — send the build log |
| `не отобрано ни одного теста` (“no tests selected”) | an error in the selection expression; with a marker set, an empty part is allowed |
| No Allure Report link | the Allure plugin or the Allure Commandline installation (section 1) |
| A push does not start a build | the webhook's Recent Deliveries in GitHub, whether the ngrok tunnel is alive, the trigger checkbox in the job |
| Containers are left after the build | `docker ps -a --filter "name=ilcarro-jenkins"`; the cleanup command — in `commands.md` *(in Russian)* |
