// Пайплайн Jenkins для IlCarro. Устройство и запуск — commands.md (раздел Jenkins),
// настройка job и вебхука — docs/jenkins-setup.md.
//
// Разбиение тестов то же, что в GitHub Actions (.github/workflows/tests.yml):
//   * "not selenium" — API и Playwright, один раз, без Grid;
//   * "selenium"     — Selenium-тесты в выбранном браузере через Selenium Grid.
// Маркер selenium ставит хук в conftest.py по фикстурам; полноту разбиения проверяет
// scripts/check_ci_split.py в job split-check GitHub Actions.
// В отличие от GitHub Actions, браузер один (параметр BROWSER), части идут друг за другом
// в одном compose-проекте, а о прогонах на main сообщает GitHub Actions, не Jenkins.

pipeline {
    agent any

    options {
        timeout(time: 60, unit: 'MINUTES')               // сборка образа + две части тестов; зависший Grid не повесит сборку навсегда
        buildDiscarder(logRotator(numToKeepStr: '20'))   // старые сборки и их отчёты не копятся на диске
        // Изоляция сборок обеспечена именами compose-проектов, но три узла браузера и тесты
        // в три потока — тяжёлая нагрузка; вторая сборка IlCarro ждёт в очереди, а не делит машину
        disableConcurrentBuilds()
    }

    parameters {
        choice(name: 'BROWSER', choices: ['chrome', 'firefox', 'edge'], description: 'Браузер для Selenium-тестов (API и Playwright от него не зависят)')
        string(name: 'TEST_MARKER', defaultValue: '', description: 'Маркеры pytest: smoke, api, "api and security"... Пусто — все тесты')
    }

    environment {
        // Первая сборка нового job (в том числе от вебхука) может прийти без параметров:
        // Jenkins узнаёт о них из Jenkinsfile только во время этой сборки
        SELECTED_BROWSER = "${params.BROWSER ?: 'chrome'}"
        // Узлы какого браузера поднимает compose (у каждого узла свой профиль). Задано здесь,
        // а не в стадии: docker compose down в post тоже должен видеть узлы этого профиля
        COMPOSE_PROFILES = "${params.BROWSER ?: 'chrome'}"
        // Уникальный compose-проект на каждую сборку: свои контейнеры, сеть и том с видео.
        // Не пересекается ни с локальным стендом (ilcarro-tests), ни с Phonebook, ни с другой
        // сборкой; down в post удаляет только этот проект. Имя проекта compose допускает только
        // строчные буквы, цифры, «-» и «_» — имя job приводится к этому виду
        COMPOSE_PROJECT_NAME = "ilcarro-jenkins-${env.JOB_NAME.toLowerCase().replaceAll('[^a-z0-9]+', '-')}-${env.BUILD_NUMBER}"
        // Образ с тестами — общий для всех сборок job (без номера сборки): следующая сборка
        // берёт его слои из кэша и пересобирает только изменившееся (обычно — слой с кодом).
        // Им пользуется docker-compose.jenkins-build.yml; там же образ получает метку
        // ilcarro.jenkins.image=<это имя>, по которой post удаляет старые версии образа этого job
        QA_IMAGE = "ilcarro-jenkins-${env.JOB_NAME.toLowerCase().replaceAll('[^a-z0-9]+', '-')}-qa-framework"
        // Второй файл убирает публикацию порта хаба и bind-монтирование allure-results
        // (почему — в его шапке). Через переменную его видят все команды, включая down в post
        COMPOSE_FILE = 'docker-compose.yml:docker-compose.jenkins-build.yml'
    }

    stages {
        stage('Prepare') {
            steps {
                script {
                    if (!['chrome', 'firefox', 'edge'].contains(env.SELECTED_BROWSER)) {
                        error("Неизвестный браузер: '${env.SELECTED_BROWSER}'. Допустимо: chrome, firefox, edge")
                    }
                    // Браузер и фильтр — в описании сборки: видно в списке сборок, не открывая лог
                    currentBuild.description = "${env.SELECTED_BROWSER} · ${params.TEST_MARKER?.trim() ?: 'все тесты'}"
                }
                // Workspace Jenkins переживает сборку: без очистки в отчёт попали бы результаты
                // прошлых сборок (урок Phonebook)
                sh 'rm -rf allure-results && mkdir -p allure-results'
                sh '''
                    echo "================ Параметры сборки ================"
                    echo "Браузер Selenium (BROWSER):  $SELECTED_BROWSER"
                    echo "Узлы Grid (COMPOSE_PROFILES): $COMPOSE_PROFILES"
                    echo "Маркер (TEST_MARKER):        ${TEST_MARKER:-<пусто — все тесты>}"
                    echo "Compose-проект сборки:       $COMPOSE_PROJECT_NAME"
                    echo "Образ с тестами (кэш job):   $QA_IMAGE"
                    echo "=================================================="
                    docker compose version
                '''
            }
        }

        stage('API and Playwright') {
            steps {
                // catchError: сбой этой части красит стадию и сборку, но Selenium-часть всё равно
                // идёт — как независимые job'ы GitHub Actions
                catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                    script {
                        // up qa-framework --no-deps: стартует только контейнер с тестами, без хаба
                        // и узлов. Не run --rm, как в GitHub Actions: контейнер должен остаться,
                        // чтобы забрать из него результаты
                        int code = runPart('not selenium', '--no-deps --exit-code-from qa-framework qa-framework', 'allure-results/not-selenium')
                        judgePart('API and Playwright', 'not selenium', code, 'allure-results/not-selenium')
                    }
                }
            }
        }

        stage('Selenium (Grid)') {
            steps {
                catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                    script {
                        // up без списка сервисов: хаб, узлы профиля COMPOSE_PROFILES и тесты.
                        // --exit-code-from останавливает стенд после тестов и возвращает код pytest
                        int code = runPart('selenium', '--exit-code-from qa-framework', 'allure-results/selenium')
                        judgePart("Selenium (${env.SELECTED_BROWSER})", 'selenium', code, 'allure-results/selenium')
                    }
                }
            }
        }
    }

    post {
        always {
            // Сначала уборка, потом отчёт: результаты уже в workspace, а сбой генерации отчёта
            // не должен оставить контейнеры висеть. Только проект этой сборки: down -v удаляет
            // его контейнеры, сеть и тома. Образ QA_IMAGE остаётся — это кэш для следующей
            // сборки (--rmi не нужен). Никаких prune: они глобальны.
            // Проверка имени — страховка: пустое имя означало бы проект ilcarro-tests
            // из docker-compose.yml, то есть локальный стенд
            sh '''
                case "$COMPOSE_PROJECT_NAME" in
                    ilcarro-jenkins-*) docker compose down -v --remove-orphans \
                        || echo "ВНИМАНИЕ: уборка проекта $COMPOSE_PROJECT_NAME не удалась — проверь docker ps -a" ;;
                    *) echo "ВНИМАНИЕ: неожиданное имя compose-проекта '$COMPOSE_PROJECT_NAME' — уборка пропущена" ;;
                esac
            '''
            // Старые версии образа этого job. Пересборка переносит имя QA_IMAGE на новый образ,
            // прежний остаётся без имени (dangling), но с меткой ilcarro.jenkins.image — по ней
            // и удаляем. Сам QA_IMAGE (у него есть имя) и чужие образы фильтр не выбирает.
            // Образ, который ещё держит контейнер, docker image rm без -f не удалит — это не ошибка
            sh '''
                case "$QA_IMAGE" in
                    ilcarro-jenkins-*)
                        old="$(docker image ls -q --filter dangling=true --filter "label=ilcarro.jenkins.image=$QA_IMAGE")"
                        if [ -n "$old" ]; then
                            echo "Удаляем старые версии образа $QA_IMAGE: $old"
                            docker image rm $old || echo "ВНИМАНИЕ: часть старых версий $QA_IMAGE удалить не удалось"
                        fi
                        docker image ls --filter "label=ilcarro.jenkins.image=$QA_IMAGE" ;;
                    *) echo "ВНИМАНИЕ: неожиданное имя образа '$QA_IMAGE' — уборка старых версий пропущена" ;;
                esac
            '''

            script {
                collectAllureResults(['allure-results/not-selenium', 'allure-results/selenium'], 'allure-results/report')
            }

            // Как в Phonebook: плагин Allure генерирует отчёт и сам хранит историю сборок (график трендов)
            allure([
                includeProperties: false,
                jdk: '',
                properties: [],
                reportBuildPolicy: 'ALWAYS',
                results: [[path: 'allure-results/report']]
            ])
        }
    }
}

// ==========================================
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// ==========================================

/**
 * Выражение -m для части. Маркер пользователя добавляется через and и берётся в скобки:
 * без них "smoke or api and selenium" читается как "smoke or (api and selenium)" (как в GitHub Actions).
 */
String selectionFor(String expression) {
    String marker = params.TEST_MARKER?.trim()
    return marker ? "(${marker}) and ${expression}".toString() : expression
}

/**
 * Запускает одну часть тестов в docker compose и забирает её результаты Allure в resultsDir.
 * Возвращает код выхода docker compose (с --exit-code-from — код pytest).
 */
int runPart(String expression, String upArgs, String resultsDir) {
    String addopts = "-m \"${selectionFor(expression)}\""
    int code = 0
    // Значения — только через переменные окружения, не вклейкой в текст команды.
    // BROWSER задаётся явно: compose передаёт его в контейнер, а без него тесты молча шли бы
    // в chrome (урок Phonebook). TEST_MARKER обнуляется: Jenkins экспортирует параметры
    // в окружение, compose передал бы его в контейнер, и команда qa-framework поставила бы
    // его -m после PYTEST_ADDOPTS — отбор части был бы потерян
    withEnv(["BROWSER=${env.SELECTED_BROWSER}", "PYTEST_ADDOPTS=${addopts}", 'TEST_MARKER=']) {
        sh 'echo "Отбор: $PYTEST_ADDOPTS | браузер: $BROWSER | узлы Grid: $COMPOSE_PROFILES"'
        code = sh(script: "docker compose up --build ${upArgs}", returnStatus: true)
    }
    // Результаты забираем ВСЕГДА — отчёт нужнее всего при упавших тестах. Контейнер
    // остановлен, но не удалён: docker cp работает и с остановленным
    sh """
        mkdir -p '${resultsDir}'
        id="\$(docker compose ps -a -q qa-framework)"
        if [ -n "\$id" ]; then
            docker cp "\$id":/app/allure-results/. '${resultsDir}/' || echo "Результаты из контейнера забрать не удалось"
        else
            echo "Контейнер qa-framework не найден — результатов нет"
        fi
    """
    echo "Код выхода части '${expression}': ${code}"
    return code
}

/**
 * Переводит код выхода части в статус стадии и сборки — как в Phonebook:
 * упавшие тесты (1) — UNSTABLE, сбой запуска — FAILURE. Плюс правила GitHub Actions:
 * пустой отбор (5) — ошибка, кроме явно заданного маркера.
 */
void judgePart(String title, String expression, int code, String resultsDir) {
    int results = Integer.parseInt(sh(
        script: "find '${resultsDir}' -maxdepth 1 -name '*-result.json' | wc -l",
        returnStdout: true).trim())

    // Код 1 без результатов — это docker compose, а не pytest: сверять параметры не с чем
    if (code == 0 || code == 5 || (code == 1 && results > 0)) {
        checkParamsReachedContainer(resultsDir, selectionFor(expression))
    }
    if (code == 0) {
        echo "${title}: все тесты прошли (результатов: ${results})"
    } else if (code == 1 && results > 0) {
        unstable("${title}: есть упавшие тесты — смотри Allure Report")
    } else if (code == 5) {
        if (params.TEST_MARKER?.trim()) {
            echo "${title}: маркер не отобрал тестов для этой части — пропуск (так бывает, например, с маркером api)"
        } else {
            error("${title}: не отобрано ни одного теста — проверь выражение отбора")
        }
    } else {
        // Код 1 без результатов — это docker compose (например, не собрался образ), а не pytest
        error("${title}: тесты не удалось запустить (код выхода ${code}, результатов: ${results})")
    }
}

/**
 * Защита от урока Phonebook «параметр браузера молча игнорировался». environment.properties
 * пишет pytest_sessionfinish в conftest.py внутри контейнера: SeleniumBrowser — --browser_name,
 * MarkerFilter — выражение -m, с которыми pytest реально запустился. Расхождение — FAILURE.
 */
void checkParamsReachedContainer(String resultsDir, String expectedSelection) {
    String path = "${resultsDir}/environment.properties"
    if (!fileExists(path)) {
        error("В ${resultsDir} нет environment.properties — не видно, в каком браузере и с каким отбором шли тесты")
    }
    String browser = propertyFromFile(path, 'SeleniumBrowser')
    if (browser != env.SELECTED_BROWSER) {
        error("Параметр BROWSER=${env.SELECTED_BROWSER} не дошёл до контейнера: pytest запущен с --browser_name='${browser}'")
    }
    String selection = propertyFromFile(path, 'MarkerFilter')
    if (selection != expectedSelection) {
        error("Отбор не дошёл до контейнера: ожидался -m '${expectedSelection}', pytest запущен с '${selection}'")
    }
    echo "Параметры в контейнере подтверждены: SeleniumBrowser=${browser}, MarkerFilter=${selection}"
}

String propertyFromFile(String path, String key) {
    return sh(script: "sed -n 's/^${key}=//p' '${path}' | tr -d '\\r'", returnStdout: true).trim()
}

/**
 * Собирает результаты частей в одну папку для плагина Allure. Файлы результатов уникальны
 * (UUID в имени), а environment.properties у каждой части свой — их значения склеиваются
 * через «; », как в scripts/merge_allure_results.py, и дополняются данными сборки Jenkins.
 */
void collectAllureResults(List<String> parts, String target) {
    sh "rm -rf '${target}' && mkdir -p '${target}'"
    List<String> texts = []
    for (String dir : parts) {
        if (!fileExists(dir)) {
            continue
        }
        sh "cp -R '${dir}/.' '${target}/'"
        if (fileExists("${dir}/environment.properties")) {
            texts.add(readFile(file: "${dir}/environment.properties", encoding: 'UTF-8'))
        }
    }
    // JenkinsBrowser — то, что выбрали в Jenkins; SeleniumBrowser (из контейнера) — то, с чем
    // реально запустился pytest. В отчёте они стоят рядом
    Map<String, String> extra = [
        'CI'            : 'Jenkins',
        'JenkinsBuild'  : "${env.JOB_NAME} #${env.BUILD_NUMBER}".toString(),
        'JenkinsBrowser': env.SELECTED_BROWSER,
        'JenkinsMarker' : (params.TEST_MARKER?.trim() ?: '(все тесты)'),
    ]
    writeFile(file: "${target}/environment.properties", text: mergeProperties(texts, extra), encoding: 'UTF-8')
}

// @NonCPS: чистая обработка строк без шагов Jenkins; LinkedHashMap и его итераторы
// не сериализуются и не переживут точку сохранения CPS
@NonCPS
String mergeProperties(List<String> texts, Map<String, String> extra) {
    Map<String, List<String>> merged = [:]   // литерал Groovy — LinkedHashMap: порядок ключей сохраняется
    for (String text : texts) {
        for (String line : text.split('\n')) {
            int eq = line.indexOf('=')
            if (eq <= 0 || line.trim().startsWith('#')) {
                continue
            }
            String key = line.substring(0, eq).trim()
            String value = line.substring(eq + 1).trim()
            if (!merged.containsKey(key)) {
                merged.put(key, [])
            }
            if (!merged.get(key).contains(value)) {
                merged.get(key).add(value)
            }
        }
    }
    for (Map.Entry<String, String> entry : extra.entrySet()) {
        merged.put(entry.key, [entry.value])
    }
    StringBuilder out = new StringBuilder()
    for (Map.Entry<String, List<String>> entry : merged.entrySet()) {
        out.append(entry.key).append('=').append(entry.value.join('; ')).append('\n')
    }
    return out.toString()
}
