# Value Engine Upgrade Pack

Готовый пакет для разработчика: апгрейд текущего движка ставок на тоталы с упором на прозрачность, калибровку вероятностей и контроль качества через CLV.

## Что реализовано

### Апгрейд 1 — удалено всё, чего нет в реализации
Из движков убраны мёртвые правила по рынкам, которые модель не генерирует:
- убраны `btts_yes`, `btts_no`, `team_home_win`, `team_away_win`
- `engine_value.py` и `engine_safe.py` работают только с текущими рынками тоталов

### Апгрейд 2 — лигозависимые базовые параметры
Для каждой лиги теперь есть bootstrap-параметры:
- `goal_avg_home`
- `goal_avg_away`
- `home_advantage`
- `min_lambda`
- `max_lambda`
- clamp-диапазоны для attack / defence

Важно: это стартовые параметры, а не «истина». Их нужно потом подогнать на ваших исторических данных.

### Апгрейд 3 — recency weighting
В `team_stats.py` реализовано экспоненциальное затухание веса матчей:

```python
weight = (RECENCY_DECAY ** idx) * (PREVIOUS_SEASON_WEIGHT ** season_offset)
```

- более свежие матчи весят больше
- прошлый сезон учитывается с пониженным весом
- fallback логика сохранена, но стала мягче

### Апгрейд 4 — влияние отсутствующих игроков
`player_impact.py` подключён в пайплайн модели, но включается флагом:

```env
VALUE_ENGINE_ENABLE_PLAYER_IMPACT=1
```

По умолчанию он выключен, потому что пока нет нормального парсинга составов. В коде это специально закомментировано и обернуто в feature flag.

### Апгрейд 5 — калибровка вероятностей
Добавлен модуль:
- `value_engine/calibration/calibrator.py`

Что он делает:
1. забирает историю уже сыгранных ставок
2. строит bin-based calibration map
3. сохраняет её в JSON
4. при прогнозе применяет к raw probability калиброванную вероятность

Подход намеренно простой и прозрачный, без тяжёлых внешних ML-зависимостей.

### Апгрейд 6 — CLV / closing-line tracking
Добавлен трекер:
- `value_engine/roi/tracker.py`

Он умеет:
- логировать picks в момент отбора
- позже принимать closing odds
- считать CLV
- сеттлить ставки после результата
- строить summary по ROI / CLV / hit rate

### Апгрейд 7 — прямой расчёт тоталов через сумму Пуассона
Вместо матрицы счётов:
- теперь используется свойство:
  - если `H ~ Poisson(lambda_home)`
  - и `A ~ Poisson(lambda_away)`
  - тогда `T = H + A ~ Poisson(lambda_home + lambda_away)`

Это проще, быстрее и чище именно для рынков тоталов.

### Апгрейд 8 — fair odds и edge
В каждом рынке теперь считаются:
- `fair_odds = 1 / probability`
- `edge = odds - fair_odds`
- `edge_percent = odds / fair_odds - 1`

`value = probability * odds - 1` тоже оставлен.

---

## Структура проекта

```text
value_engine_upgrade_repo/
├─ README.md
├─ requirements.txt
├─ pyproject.toml
├─ .env.example
├─ examples/
│  └─ offline/
│     ├─ fixtures.sample.json
│     ├─ team_matches.json
│     ├─ odds.json
│     ├─ missing_players.json
│     ├─ results.sample.json
│     └─ closing_odds.sample.json
├─ scripts/
│  ├─ run_predictions.py
│  ├─ calibrate_markets.py
│  ├─ settle_picks.py
│  ├─ update_closing_lines.py
│  └─ report_performance.py
└─ value_engine/
   ├─ __init__.py
   ├─ settings.py
   ├─ engine_value.py
   ├─ engine_safe.py
   ├─ team_aliases.py
   ├─ calibration/
   │  ├─ __init__.py
   │  └─ calibrator.py
   ├─ data/
   │  ├─ __init__.py
   │  ├─ api_football.py
   │  └─ leagues.py
   ├─ markets/
   │  ├─ __init__.py
   │  └─ mapper.py
   ├─ model/
   │  ├─ __init__.py
   │  ├─ model.py
   │  ├─ team_stats.py
   │  ├─ player_impact.py
   │  └─ poisson.py
   └─ roi/
      ├─ __init__.py
      └─ tracker.py
```

---

## Быстрый старт

### 1. Распаковать архив

```bash
unzip value_engine_upgrade_repo.zip
cd value_engine_upgrade_repo
```

### 2. Создать окружение

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Скопировать env

```bash
cp .env.example .env
```

### 4. Быстрый offline smoke test без API

```bash
export VALUE_ENGINE_OFFLINE_DIR=examples/offline
python scripts/run_predictions.py \
  --fixtures examples/offline/fixtures.sample.json \
  --mode both \
  --pretty
```

Так можно проверить проект без внешнего API.

### 5. Работа с реальным API

В `.env` заполнить:

```env
API_FOOTBALL_KEY=your_key
API_FOOTBALL_BASE_URL=https://v3.football.api-sports.io
VALUE_ENGINE_OFFLINE_DIR=
```

После этого можно использовать реальные fixture id / team id / league code.

---

## Как работает модель

### Шаг 1. Собирается история команды
Из `get_team_last_matches(...)` подтягиваются последние матчи в рамках нужной лиги и сезона.

Далее считается взвешенная статистика:
- `goals_for`
- `goals_against`
- `home_goals_for`
- `home_goals_against`
- `away_goals_for`
- `away_goals_against`

Свежим матчам даётся больший вес.

### Шаг 2. Строятся ожидаемые голы
Для каждой стороны:

```text
attack_strength = team_gf / league_base
defence_strength = opp_ga / league_base
lambda = league_base * attack_strength * defence_strength * side_adjustment
```

Где:
- `league_base` разный для home и away
- `side_adjustment` учитывает home advantage
- после расчёта λ ограничивается диапазоном `min_lambda ... max_lambda`

### Шаг 3. При необходимости применяется player impact
Если включён флаг `VALUE_ENGINE_ENABLE_PLAYER_IMPACT=1`, то λ корректируется через:
- `attack_modifier`
- `defence_modifier`

### Шаг 4. Считаются вероятности тоталов
Используется распределение Пуассона по суммарной λ:

```text
lambda_total = lambda_home + lambda_away
T ~ Poisson(lambda_total)
```

После этого считаются:
- Over 1.5
- Under 1.5
- Over 2.5
- Under 2.5
- Under 3.5

### Шаг 5. Калибровка вероятностей
Если включён `VALUE_ENGINE_ENABLE_CALIBRATION=1` и существует calibration JSON:
- raw probability прогоняется через calibration map
- дальше value считается уже по calibrated probability

### Шаг 6. Считаются fair odds / edge / value
Для каждого рынка:
- `fair_odds = 1 / probability`
- `edge = odds - fair_odds`
- `edge_percent = odds / fair_odds - 1`
- `value = probability * odds - 1`

### Шаг 7. Движки отбирают рынки
- `engine_value.py` — отбор value-сценариев
- `engine_safe.py` — более консервативный профиль

---

## Как работать с калибровкой

Это важный блок. Без него value часто выглядит лучше на бумаге, чем на дистанции.

### Что нужно, чтобы калибровка заработала
Нужно накопить лог ставок, у которых уже известен исход:
- raw probability
- итог рынка (выиграл / проиграл)

Это уже заложено в `tracker.py`.

### Рабочий цикл

#### Этап A. Генерируете picks
```bash
export VALUE_ENGINE_OFFLINE_DIR=examples/offline
python scripts/run_predictions.py \
  --fixtures examples/offline/fixtures.sample.json \
  --mode both
```

В этот момент picks автоматически пишутся в runtime storage:
- `.runtime/tracked_picks.json`

#### Этап B. Когда матчи сыграны — сеттлите picks
Подготовьте JSON с результатами вида:

```json
[
  {
    "match_id": 9001,
    "goals": { "home": 2, "away": 1 }
  }
]
```

И затем:

```bash
python scripts/settle_picks.py \
  --results examples/offline/results.sample.json
```

#### Этап C. Обучаете calibration map
```bash
python scripts/calibrate_markets.py
```

После этого создастся файл:
- `.runtime/calibration_models.json`

#### Этап D. Включаете применение калибровки
В `.env`:

```env
VALUE_ENGINE_ENABLE_CALIBRATION=1
```

Теперь новые прогнозы будут считать value уже по calibrated probability.

### Что лежит в calibration JSON
Для каждого рынка хранится piecewise-linear map:
- набор точек `(raw_pred_mean, calibrated_rate)`

Например условно:
- raw 0.55 → calibrated 0.51
- raw 0.70 → calibrated 0.66

Это значит, что модель была чересчур оптимистична, и вероятности поджимаются вниз.

### Практические рекомендации
- запускать калибровку имеет смысл после накопления хотя бы 100+ settled picks на рынок
- лучше обучать отдельно по рынкам:
  - `over_2_5`
  - `under_2_5`
  - `under_3_5`
- не смешивать лиги и сезоны без проверки
- после крупных изменений модели calibration map нужно перестраивать

---

## Как работать с CLV

CLV нужен не для красоты, а чтобы понять, обыгрывает ли модель closing line.

### Как это устроено в пакете
Когда движок выбирает ставку, в трекер сохраняются:
- `odds_picked`
- `probability`
- `fair_odds`
- `value`

Позже вы подаёте closing odds отдельным JSON:

```json
[
  {
    "match_id": 9001,
    "market": "over_2_5",
    "closing_odds": 1.83
  }
]
```

И выполняете:

```bash
python scripts/update_closing_lines.py \
  --closing examples/offline/closing_odds.sample.json
```

### Что посчитает система
Для каждой ставки:
- `clv_pct = odds_picked / closing_odds - 1`
- `clv_implied_shift = 1/closing_odds - 1/odds_picked`

Если взяли коэффициент 1.95, а close пришёл 1.83:
- это хорошо
- рынок ушёл в вашу сторону
- `clv_pct > 0`

### Как читать summary
Запуск:

```bash
python scripts/report_performance.py
```

Смотрите прежде всего:
- `roi_pct`
- `avg_clv_pct`
- `positive_clv_rate`

Практически:
- если ROI пока шумит, но `positive_clv_rate` стабильно высокий, у модели может быть реальное преимущество
- если ROI положительный, но CLV слабый — возможно, просто удачный short-term ран

### Как интегрировать CLV в production
Минимальный цикл:
1. модель отобрала ставки
2. в момент отбора сохранили `picked_odds`
3. ближе к старту матча повторно сняли рынок либо загрузили closing feed
4. обновили `closing_odds`
5. после матча засеттлили исход
6. построили summary

В реальном проекте developer может:
- либо брать close из вашего же API-провайдера
- либо импортировать CSV/JSON от стороннего odds feed
- либо делать периодические snapshots и считать последний pre-match snapshot closing line

---

## Player impact: как подключать потом

Сейчас feature уже встроен, но выключен по умолчанию.

### Как включить
```env
VALUE_ENGINE_ENABLE_PLAYER_IMPACT=1
```

### Что нужно для полноценной работы
Ваш data-layer должен уметь возвращать список отсутствующих игроков в формате:

```json
[
  {
    "name": "Top Striker",
    "position": "Attacker"
  }
]
```

Функция:
- `get_team_missing_players(team_id, fixture_id)`

Если она пока не реализована качественно, лучше держать flag выключенным.

---

## Offline режим для разработчика

Чтобы разработчик сразу смог прогнать пакет без интеграции API, в `examples/offline/` лежат sample-файлы.

### Что есть
- `fixtures.sample.json` — список матчей
- `team_matches.json` — история матчей по ключу `league_id:season:team_id`
- `odds.json` — коэффициенты по fixture id
- `results.sample.json` — результаты для сеттла
- `closing_odds.sample.json` — closing lines
- `missing_players.json` — пример данных по отсутствующим

### Smoke flow
```bash
export VALUE_ENGINE_OFFLINE_DIR=examples/offline

python scripts/run_predictions.py \
  --fixtures examples/offline/fixtures.sample.json \
  --mode both \
  --pretty

python scripts/update_closing_lines.py \
  --closing examples/offline/closing_odds.sample.json

python scripts/settle_picks.py \
  --results examples/offline/results.sample.json

python scripts/calibrate_markets.py

python scripts/report_performance.py
```

---

## Что нужно разработчику сделать в первую очередь

1. Подключить реальные endpoints в `value_engine/data/api_football.py`
2. Проверить соответствие названий рынков в odds feed внутренним ключам:
   - `over_1_5`
   - `under_1_5`
   - `over_2_5`
   - `under_2_5`
   - `under_3_5`
3. Подогнать league bootstrap params в `data/leagues.py`
4. Начать копить tracked picks
5. Через 100–300 settled picks обучить calibration
6. Добавить автоматический импорт closing odds
7. Только после этого оценивать ROI на дистанции

---

## Ограничения текущей версии

- пока всё ещё только totals
- нет 1X2 / BTTS
- bootstrap league params заданы вручную и требуют тюнинга
- calibration простая, bin-based
- player impact зависит от качества источника составов
- реальная «прибыльность» должна подтверждаться только бэктестом и CLV

---

## Команды для разработчика

### Прогнозы и value
```bash
python scripts/run_predictions.py \
  --fixtures path/to/fixtures.json \
  --mode both \
  --output out/picks.json \
  --pretty
```

### Сеттл результатов
```bash
python scripts/settle_picks.py \
  --results path/to/results.json
```

### Обновить closing odds
```bash
python scripts/update_closing_lines.py \
  --closing path/to/closing_odds.json
```

### Переобучить калибровку
```bash
python scripts/calibrate_markets.py \
  --min-samples 30 \
  --bins 8
```

### Итоговый отчёт
```bash
python scripts/report_performance.py
```
