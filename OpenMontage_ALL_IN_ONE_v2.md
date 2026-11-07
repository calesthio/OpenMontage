# OpenMontage — единый файл контекста

Содержание:
1. OpenMontage_chat_summary_and_analysis.md
2. OPENMONTAGE_UNIFIED_PROJECT_CONTEXT_RU.md
3. OPENMONTAGE_HANDOFF_RU.md
4. OpenMontage_last_chat_full.md (последний чат целиком)
5. PART5_CHAT_2026-10-18_to_2026-10-20_FACTORY_RUN.md (чат «Фабрика в Codespaces: Kilo + OpenCode», 18-20 окт 2026, в самом конце файла)
6. PART6_CHAT_2026-10-21_to_2026-10-22_AI_PHOTO_GENERATION_NICHE.md (чат «AI photo generation niche», 21-22 окт 2026, полная переписка, в самом конце файла)



================================================================================
# ФАЙЛ: OpenMontage_chat_summary_and_analysis.md
================================================================================

# OpenMontage: итог последнего чата и глубокий разбор

**Чат:** «Поиск лучшей ниши для бизнеса» (68 сообщений, 16 окт 2026 08:58 UTC → 17 окт 2026 13:48 UTC).
**Это единственный чат в экспорте.** Он же самый свежий.
**Состояние на последнее сообщение:** агенту отправлен большой «MASTER RUN» (фазы P1–P7). Его результатов в чате нет.

Документ состоит из трёх частей.
- **Часть A** — что произошло и где вы сейчас.
- **Часть B** — глубокий разбор: что хорошо, что вызывает сомнения, что делать дальше.
- **Приложение** — полная переписка (ваши сообщения и ответы Claude, без технических выдач инструментов).

---

# Часть A. Что в чате произошло

## A1. Цель проекта

Построить автоматизированную «фабрику» длинных англоязычных документальных YouTube-видео без лица в кадре.
- Платформа: OpenMontage. Агент работает в GitHub Codespaces через Kilo Code.
- Режим строго $0: без платных API, без платных футажей.
- Результат должен быть проверяемым: каждый факт со ссылкой на источник, права на каждый клип, жёсткий QA.

## A2. Как менялась ниша

| Шаг | Что предлагалось | Итог |
|---|---|---|
| 1 | «Скрытый бизнес за обычными вещами» (гипотеза из старых файлов) | Perplexity подтвердил в суженном виде: логистика и инфраструктура |
| 2 | Компании и знаменитости | Знаменитости отвергнуты (права, клевета). Компании только как «второй слой» |
| 3 | Пилоты «вода», «контейнеровоз», «электросеть» | Footage по воде в основном фото, не видео |
| 4 | «Куда уходят деньги» (инфраструктура с другим углом) | **Вы отвергли инфраструктуру** |
| 5 | **История испытаний авиации и космоса на архивных кадрах NASA/ВВС** | **Принята** |

Что Claude выбирал при оценке ниш (веса: кадры 25, политика 20, конкуренция 20, спрос 15, RPM 10, автоматизация 10):
- Авиация/космос 7.1.
- История XX века на кадрах NARA 6.8.
- Инфраструктура 6.5.
- Бизнес и финансы 4.8.

Это **собственные оценки Claude**, не измерения. При большем весе спроса вперёд выходит история XX века.

## A3. Пилотная тема

**Controlled Impact Demonstration (CID):** NASA и FAA 1 декабря 1984 намеренно разбили дистанционно управляемый Boeing 720 на озере Роджерс (авиабаза Эдвардс). Проверялась антитуманная присадка к топливу FM-9.

Запасные темы после проверки кадров: X-15, XB-70, Helios, шаттл (посадочные тесты).
Тема Lunar Landing Research Vehicle отброшена: найдено 2 видео.

## A4. Архитектура фабрики (решения)

- **Максимум 3 рантайм-компонента:** OpenMontage (платформа, AGPL-3.0), HyperFrames (оригинальная графика, Apache-2.0), голосовая модель. Всё остальное — закреплённые скиллы или «только как образец». Четвёртый репозиторий только с вашего согласия.
- **Модель прав (fail-closed):** `rights_basis = explicit_license | source_policy_us_gov | unknown`. Неизвестное = не использовать. Любой клип с чужим кредитом (CNN, «courtesy of», копирайт) = REJECT, даже если вы его просмотрите.
- **Стадия 0 «жизнеспособность темы»:** ≥10 пригодных видеоклипов и ≥3 первичных документа до написания сценария.
- **Сценарий с учётом реальных кадров** (раньше сценарий жил отдельно и ломался на «нет футажа»).
- **Гейт «добавленная ценность»** (против политики YouTube о повторно используемом и «inauthentic» контенте). Стартовые пороги — догадки: закадровый голос ≥90% длительности, ≥1 оригинальная схема на 90 с, без архивных клипов >20 с без пояснения, фото-слайдшоу ≤15 с.
- **Каждое утверждение сценария привязано к `claim_id`** в реестре доказательств.
- **Монтаж:** EDL с написанной причиной каждой склейки и линтер ритма.
- **Звук:** голос главный, музыка (если будет) приглушается, двухпроходная нормализация громкости. Стартовая цель −14 LUFS и пик −1.5 dBTP (это допущение из вторичных источников).
- **Музыка в пилоте: нет**, пока не будет файла лицензии.
- **Публикация только вручную через YouTube Studio** (API-загрузка из непроверенного проекта Google даёт приватные видео).
- **Ноль секретов в первой версии** (позже появился один: токен Kaggle).
- **Четыре агента Kilo:** `editor`, `qa-reviewer`, `evidence-checker`, `footage-scout`. Файлы созданы, `kilo agent list` их показал. Но запускались они **inline** (оркестратор играл роли сам), то есть независимости нет.

## A5. Журнал вех

| Веха | Что сделано | Результат / коммит |
|---|---|---|
| A | Проверка реальности + спецификация профиля ниши | выполнена (хэш в чате не назван) |
| B | Проба кадров через API | NO-GO по всем темам: Boeing 13 видео / 1 с явной лицензией; LLRV 2 / 0; шаттл 22 / 5. NTRS работал |
| S | Аудит инструментов, 7 скиллов | `ff35182`. Piper-голос lessac: лицензия UNKNOWN. OpenMontage = AGPL-3.0 |
| D1 | Аудит звука и монтажа, скиллы | `74ee25a` (отчёт в чате не показан) |
| P+ | План v3.2, 4 агента, спецификация QA | `f5099cb` |
| C1 | Модель прав, переклассификация клипов | NO-GO по 5 темам: 0 пригодных из 10 нужных (гейт слишком жёсткий) |
| C2 | Причины отклонений, очередь на просмотр | `447ee60`: 37 клипов, 29 отклонено, 8 ждут просмотра, 0 пригодных |
| C3 | Диагностика классификации и NTRS | Найдена ошибка агента (правило применено жёстче записанного). NTRS: порт 443 не открывается, блокировка постоянная |
| C4 | Только Boeing 720 | 11 клипов NASA по теме, 6 первичных документов. Для полного ролика `NEEDS_OWNER_REVIEW`, для среза 30–60 с требования выполнены |
| C5 | Диагностика archive.org | «0 байт» были из-за отсутствия `-L` (редирект). Блокировки нет. 2 контакт-листа |
| Q1 | Инструмент проверки видео `tools/qa/qc.py` (TDD) | `59cdf6a`, 11 тестов. Пилот про поддоны: **FAILED** (−17.1 LUFS, пик 0.0 dBTP) |
| D2 | Финальная обработка звука `finish_audio` (TDD) | 5 тестов. До −17.2 LUFS / 0.0 dBTP, после −15.3 / −4.5 |
| C6 | Остальные контакт-листы, карта сюжетных блоков | `0610da1` (отчёт в чате не показан) |
| V | Kokoro-82M вместо Piper lessac | `7fd52a4`. Скорость на CPU 1.58–1.75× от реального времени. Финальный MP4: −15.0 LUFS / −4.3 dBTP. Встроенный AAC-энкодер работает |
| K0 | Проверка доступа к Kaggle | CLI 2.2.4, токена нет, агент остановился правильно |
| K1 | Мост Codespace → Kaggle | `21903ee`, 16 тестов, живая «hello»-задача прошла (`COMPLETE`, sha256 сверен). Интернет в ядре был выключен |
| E1 | Реестр утверждений CID-01…16 и сценарий на ~50 с | промпт выдан; запускали ли отдельно, неясно. В MASTER RUN он вошёл как P2 |
| FS1 | Реестр источников футажа | промпт выдан; вошёл в MASTER RUN как P5 |
| **MASTER RUN** | P1 лицензии голосов → P2 доказательства и сценарий → P3 Kaggle bake-off голосов → P4 интеграция TTS → P5 реестр источников → P6 технический срез ~50 с → P7 глобальная проверка | **отправлен, результата нет** |

## A6. Выбор голоса

- **Piper lessac — запрещён для публичных видео.** Карточка голоса не содержит поля лицензии, а ссылается на датасет Lessac Blizzard 2013 с ограничением. Заявленный «CC-BY-4.0» нигде не подтверждён.
- **Kokoro-82M** (Apache-2.0 по весам и пакетам) — проверенный запасной вариант. Остаточный риск: часть обучающих данных v1.0 — синтетика с неизвестным происхождением.
- **Основной выбор Claude: Chatterbox Turbo (MIT)**, затем Maya1 (Apache-2.0), затем Kokoro. Выбор сделан **без прослушивания**, по лицензии, управляемости эмоций и поместится ли на T4.
- **Нельзя:** Higgs Audio V3, Breeze TTS 2, IndexTTS-2.5, XTTS v2, F5-TTS (веса), Fish Speech, Voxtral (некоммерческие лицензии).
- Orpheus не берём, пока не проверена лицензия весов (источники расходятся).
- Chatterbox ставит скрытый водяной знак Perth. Клонирование чужих голосов запрещено правилами промптов.

## A7. Источники футажей (список из чата)

**Основа (права по политике источника, но каждый клип проверять):**
NASA Image and Video Library (images.nasa.gov), NASA SVS (svs.gsfc.nasa.gov), Internet Archive (Moving Image, Prelinger, stock_footage), Library of Congress (loc.gov/free-to-use), US National Archives (catalog.archives.gov), DVIDS (dvidshub.net), Wikimedia Commons (категория Videos), Open Beelden (openbeelden.nl).

**Осторожно (атрибуция, ограничения):** Vimeo Creative Commons, Mazwai, Videezy, Vidsplay.

**Только атмосферные вставки:** Pexels, Pixabay, Mixkit, Coverr.

**Каталоги-репозитории:** `neutraltone/awesome-stock-resources`, страница Wikimedia Commons «Free media resources/Video». Использовать только как справочник: каждый источник проверяется отдельно (это есть в P5).

## A8. Скиллы и репозитории, которые изучили

- **Ставить (закреплённо):** из `obra/superpowers` — test-driven-development, systematic-debugging, verification-before-completion; из `Jakeschincariol/youtube-agent-skill` — yt-script, yt-package, yt-chapters, yt-seo; из `agamm/video-agent` — cutting-rhythm, edl-edit, audio-edit.
- **Для исследования ниш (не ставились):** `larrygmaguire-hash/youtube-researcher-mcp`, `MalekAG/claude-code-setup`, `TimBroddin/skills`, `Skillproofdev/research-discipline`.
- **Не брать:** `everything-kilo-code` (136 скиллов), 81 скилл из самого OpenMontage (есть платные и скачивание чужих видео), `video-use` (платный ключ ElevenLabs), OpenVids (только macOS/Windows), Apify-обёртки.
- **Идеи без копирования:** `free-studio-flow` (граф задач и fail-closed проверки), `youtube-factory-pipeline` (роли агентов).

## A9. Открытые вопросы (что блокирует публикацию)

1. **Контакт-листы 11 клипов:** ответы на три вопроса (узнаваемый человек? логотип/эмблема? чужой кредит?). Ждут вас с сообщения [41], то есть больше суток чата.
2. **Согласие на голос** (Kokoro/Chatterbox) с остаточным риском данных — вместе с родителем.
3. **Монетизация:** AdSense требует 18+, нужен аккаунт родителя/опекуна. Доступность монетизации для вашей страны не проверена.
4. **Одиночные источники:** CID-13 («присадка не снизила огонь») держится на одном источнике, а это главный вывод ролика. Сценарная строка S8 заблокирована до второго источника.
5. **Эмблемы в кадре** (NASA/FAA/Boeing): решение за вами по цитатам правил NASA.
6. **Музыка:** политика «без музыки, пока нет лицензии».
7. **Конкуренция и спрос не измерены.** Это сквозной пробел.
8. **Kaggle:** верификация телефона и включение интернета/GPU для ядра не подтверждены.
9. **NTRS из песочницы агента недоступен**, документы он не читал. Их прочитал Claude через веб-инструмент.

## A10. Что подтверждено, что нет

| Утверждение | Статус |
|---|---|
| Агенты существуют в `.kilo/agents/` | подтверждено командой `kilo agent list` |
| Агенты изолированы и независимы | **нет**: роли исполнялись inline, права не проверены |
| QC-инструмент и финальная обработка звука работают | подтверждено тестами и запуском на реальном файле |
| Мост на Kaggle работает | подтверждено на «hello»-задаче без интернета и GPU |
| Клипы CID разрешены к публикации | **нет**: права по метаданным ОК, флаги людей и логотипов не проверены |
| 9 из 11 клипов — один удар с разных камер | гипотеза агента по метаданным |
| Факты сценария CID | извлечены Claude из текста NASA Facts и TM-4084 (OCR). Цифры из таблицы TM-4084 помечены OCR_UNVERIFIED |
| Лицензия Chatterbox Turbo / Maya1 | **не проверена**, это содержание фазы P1 |
| Спрос и конкуренция | не измерены |

---

# Часть B. Глубокий разбор («ultra thinking»)

Ниже мои выводы по прочитанному. Я говорю прямо, потому что вы просили честность.

## B1. Главный вывод

**За два дня построена сильная инженерная основа, но не получено ни одного публикуемого видео, и главный бизнес-вопрос ни разу не проверен.**

- Единственное готовое видео (поддоны, 85 с) не годится для публикации: источники третичные, нет `qa_report.json`, а новый QC дал ему FAILED.
- Ниша выбрана по критерию «где удобно брать кадры», а не по критерию «где есть зрители, которым можно что-то дать лучше конкурентов».
- Узкое место сместилось: теперь оно **не в агенте, а в трёх решениях, которые только вы можете принять** (контакт-листы, голос, родитель).

## B2. Что сделано хорошо

1. **Честность агента.** Он остановился там, где не было токена. Признал, что роли исполнялись inline. Нашёл и исправил свою ошибку в C3. Не писал «успех» при ошибке сети.
2. **Fail-closed подход работает как защита.** Гейт поймал реальные проблемы: клипы со сторонним кредитом (CNN, Fight for Space), громкость и клиппинг пилота, лицензию Piper.
3. **Принцип «не доверяй, проверяй» применён к самому Claude.** Claude нашёл у агента расхождение в цифрах и пересчитал. Первичные документы по CID он прочитал сам, когда у агента не работал NTRS.
4. **QC и звук сделаны через TDD** и проверены на реальном файле. Это основа, которая пригодится при любой нише.
5. **Лицензионная дисциплина.** Piper lessac заблокирован вовремя, до публичного видео. Это самая дорогая из возможных ошибок, и её избежали.
6. **Приватность и безопасность:** токен задан через Codespaces secret, а не вставлен в чат, и правила промптов запрещают его печатать.

## B3. Что вызывает сомнения

### 1) Ниша не проверена на спрос и конкуренцию (самое важное)

- Баллы 7.1 против 6.8 против 6.5 — субъективные, разница меньше любой погрешности.
- Claude несколько раз предлагал дешёвую проверку: 5 запросов в поиске YouTube и скриншоты топ-10 с подписчиками и просмотрами. **Её так и не сделали.** Это 15 минут работы, и она важнее, чем вся Kaggle-инфраструктура.
- Есть конкретный риск: Claude сам нашёл канал, который перезаливает восстановленные кадры NASA. Тема CID уже подробно описана в Википедии и самим NASA. Насколько она «занята» на YouTube, не измерено.
- Сигналы, которые стоит искать: есть ли у ролика по CID сотни тысяч просмотров у маленького канала, и чем он выигрывает. Без этого ниша остаётся гипотезой.

### 2) Объём вех не пропорционален результату

- Около 20 вех, огромные промпты, десятки документов в `docs/openmontage/`. Видео нет.
- Каждая веха добавляет документы и риск расхождений между ними. Уже был такой случай: в итоговой проверке C3 агент не упомянул Boeing, хотя по его же цифрам тема проходила порог.
- Риск классического перепроектирования: фабрика для шаблонного производства, хотя качество «первого хорошего видео» не доказано.

### 3) Гейт прав был слишком жёстким и стоил нескольких вех

- «Неизвестно = не использовать» отклонил почти все клипы NASA, потому что API не отдаёт поле прав. Для материалов NASA права определяются политикой источника. Это признал и Claude.
- Исправлено только частично. Окончательное решение (кто и как «разрешает» клип) всё ещё зависит от вас.
- Важная деталь: **вы не можете «легализовать» клип просмотром**, если в нём чужой кредит. Это правило верное, держите его.

### 4) Нет независимой проверки

- `qa-reviewer` исполняется тем же оркестратором, который делал работу. Это самопроверка.
- Claude, который пишет план и промпты, тоже не независим от плана. Его «глобальная проверка» по скриншотам будет ограничена тем, что агент сам написал в отчёте.
- Настоящая независимость: **новая сессия агента или другая модель, которая видит только репозиторий и `qa_report.json`**, и/или вы сами для ключевых мест (клипы, источники, голос).

### 5) Единый источник для главного вывода ролика

- Сильнейшая «идея» ролика: полноразмерный тест показал, что присадка не уменьшила пожар, хотя малые тесты обещали. Это CID-13, и он **держится на одном источнике** (NASA Facts).
- «Два источника» в реестре (NASA Facts и TM-4084) оба из NASA. Для чисел это допустимо, но это не независимые источники в строгом смысле.
- Числа из таблицы TM-4084 вытащены OCR и не проверены глазами.

### 6) Мост Kaggle: оправдан не для всякой озвучки

- Kokoro на CPU работает в 1.6–1.75× от реального времени: 8 минут озвучки ≈ 13–14 минут. Это терпимо. Проблема была в диске Codespace (torch и кэши), а не в скорости.
- Мост добавляет задержки на каждую задачу (запуск ядра, установка пакетов, загрузка весов), квоту GPU (30 ч/неделю, это из сторонних источников) и ещё одну точку отказа.
- Оправдан, если вы реально хотите Chatterbox/Maya1 (им нужен GPU). Для Kokoro достаточно CPU-версии torch или ONNX-варианта без torch. Это вариант «проще и дешевле», который Claude упоминал, но не проверял.
- Не проверено: условия Kaggle для такого использования как «сервера озвучки». Квоты и правила стоит прочитать самому.

### 7) Выбор голоса сделан без прослушивания

- Chatterbox Turbo выбран по лицензии и функциям. Для документальной озвучки «эмоциональность» не всегда плюс: у Chatterbox параметр «преувеличения» легко даёт театральность. Для серьёзной темы испытаний часто лучше сдержанная подача.
- Критерий победителя в P3 (WER ≤ 8%, нет обрезки, тишина/клиппинг) измеряет разборчивость, не качество подачи. **Финальное слово остаётся за вашим слухом.**
- Возможен разумный компромисс: Kokoro как основной, Chatterbox как улучшение, если на слепом тесте A/B/C он заметно лучше.

### 8) Нужно ли ≥10 клипов, и хватит ли кадров на 6–10 минут

- 9 из 11 клипов по CID — вероятно одна съёмка удара с разных камер. Для ролика нужны блоки: подготовка, дистанционное управление, полёт, удар, пожар, последствия.
- Claude сам предложил заменить счёт клипов покрытием **сюжетных блоков (≥6 блоков)**. Это правильнее. Пилот на 4–6 минут реалистичнее, чем на 8–10.
- Что можно проверить дополнительно (я этого не проверял): коллекция «Dryden Aircraft Movie Collection» на сайте NASA Armstrong, официальный канал NASA/Armstrong на YouTube, архив FAA. В чате упоминается лишь, что Armstrong выгрузил около 500 архивных роликов. Какие из них про CID, неизвестно.
- Фото с анимацией и оригинальная графика законны и даже полезны для политики «добавленной ценности», если они не превращаются в слайдшоу.

### 9) MASTER RUN: большой риск за одну сессию

- Семь фаз, несколько часов, бесплатная модель Kilo. Ранее в этом же проекте бесплатная модель выдумывала идентификаторы источников (`f1/f2`).
- Хорошо: файл состояния, коммит после каждой фазы, возможность продолжить, правило остановки при нехватке диска.
- Слабые места:
  - **P3 может упереться в Kaggle:** для интернета и GPU нужна верификация телефона. Проверьте заранее.
  - **P6 зависит от кадров, которые вы ещё не просмотрели.** Он использует `NEEDS_REVIEW`-клипы, результат помечен NOT_PUBLISHABLE. Это нормально, но не даёт готового видео.
  - **P7 «глобальная проверка» снова inline.**
  - Промпт большой, и модель может «сжать» детали.

### 10) Юридические и организационные пункты, которые легко потерять

- **AdSense/YPP:** аккаунт родителя/опекуна, письменное согласие, и вам нужно выяснить, как это работает в вашей стране. Это не вопрос агента.
- **Голос:** решение о принятии остаточного риска (данные Kokoro, водяной знак Chatterbox) должно быть зафиксировано и согласовано с владельцем аккаунта.
- **AGPL-3.0 у OpenMontage:** для частного использования не проблема. Станет вопросом, если вы будете предоставлять фабрику другим как сервис или распространять изменённую версию. Запомнить.
- **Политика YouTube:** «добавленная ценность» оценивается людьми и системами целиком. Гейт в репозитории только прокси. Прохождение гейта не гарантия монетизации.
- **Логотипы:** эмблема NASA на самолёте внутри архивного кадра — одно. Логотип NASA на вашей обложке или в оформлении канала, создающий впечатление поддержки NASA, — другое и недопустимо (правила NASA).

### 11) Безопасность

- `KAGGLE_API_TOKEN` лежит в окружении Codespace, значит доступен любому процессу агента. Агент в то же время читает веб-страницы и ставит пакеты. Это классическая поверхность для prompt injection.
- Что стоит сделать: токен только с нужными правами, **сменить токен после завершения большой сессии**, проверить `git log`/`git ls-files` на секреты (это есть в P7), не давать агенту лишнего сетевого доступа.
- Никогда не присылайте токены в чат (вы пока этого не делали).

## B4. Что я бы делал дальше (порядок)

**Перед MASTER RUN или параллельно с ним (≈30 минут вашего времени):**

1. **Проверка спроса (15 минут).** Ввести в YouTube запросы: `boeing 720 controlled impact demonstration`, `nasa crashed a plane on purpose`, `crash in the desert nasa`, `nasa flight test history`, `x-15 test flights documentary`. Для топ-10 по каждому записать: канал, подписчики, дата, просмотры. Прислать мне скриншоты. Решение «ниша живая или нет» по этим данным, не по баллам.
2. **Контакт-листы (10 минут).** Ответить на три вопроса про каждый клип (человек / логотип / чужой кредит). «Не уверен» = не используем.
3. **Kaggle (5 минут).** В настройках аккаунта подтвердить телефон и убедиться, что в ядре можно включить интернет и GPU. Иначе P3 заблокируется.

**В ходе MASTER RUN:**

4. После P1 (лицензии голосов) проверьте таблицу сами: лицензии Chatterbox Turbo/Maya1 взяты из официальных карточек? Если нет — кандидат исключён.
5. После P3 послушайте A/B/C 3–5 минут. Если сомневаетесь, остаётесь на Kokoro.
6. P6 (срез) — технический тест, не публикация. Смотреть на него как на проверку монтажа, звука и QC.

**После MASTER RUN:**

7. **Определение «готово» для версии 1:** одно видео 4–6 минут, ≥6 сюжетных блоков, каждое утверждение со ссылкой, QC без FAILED, ваш просмотр клипов, решение по голосу, загрузка как «непубличное» вручную в Studio.
8. **Независимая проверка:** новая сессия, где агент/модель видит только `GLOBAL_CHECK`, `qa_report.json`, `CID_CLAIM_LEDGER.md` и сами первичные документы. Или передайте мне текстовые файлы, а не скриншоты: так я проверю цифры построчно.
9. **Второй источник для CID-13:** TM-89642 / FAA summary report (в реестре уже есть ссылки). Без него S8 не публикуется.
10. **Только после 1–2 опубликованных видео** строить «конвейер» и масштабироваться. Метрики для решения go/no-go: CTR, удержание первых 30 с, средняя длительность просмотра, возвращающиеся зрители.

## B5. Если вы хотите упростить

Минимальный путь к первому видео, если сократить инфраструктуру:
- Озвучка: Kokoro на CPU (CPU-версия torch), без Kaggle.
- Кадры: проверенные 4–6 клипов CID + фото и оригинальная графика.
- Сценарий: 6–8 предложений с `claim_id` (он у вас уже готов).
- QC и финальный звук: уже есть.
- Публикация: вручную, непубличным видео, показать 3–5 знакомым и сравнить с конкурентами.

Kaggle и Chatterbox можно добавить позже, когда ясно, что качество голоса — реальный ограничитель.

## B6. Список проверок, которые я не мог сделать

- Я не видел отчётов D1, C6 и E1, скриншоты есть только по тем, что описаны в чате.
- Я не открывал репозиторий агента, GitHub и Kaggle. Всё о состоянии кода основано на пересказе в чате.
- Лицензии моделей и условия Kaggle я не перепроверял, они указаны так, как их проверяли в чате.
- Числа конкурентов и RPM в чате — оценки сторонних сайтов.
- Правовые вопросы (AdSense для несовершеннолетнего, лицензии, право на изображение) — не юридическая консультация.

---

# Приложение. Индекс ключевых промптов в переписке

| № сообщения | Промпт |
|---|---|
| 3 | Промпт для Perplexity: выбор ниши среди 100 |
| 9 | Аудит футажей «How a City Gets Water» |
| 13 | Аудит и установка одного скилла (youtube-researcher-mcp) |
| 23 | Milestone A (профиль ниши) и B (проба тем) |
| 25 | Milestone S (аудит инструментов, установка скиллов) |
| 29 | Дополнение к Milestone S |
| 31 | Milestone C1 (модель прав) |
| 33 | Milestone D1 (звук и монтаж) |
| 35 | Milestone P (план v3.2) |
| 37 | Milestone P+ (план, 4 агента, спецификация QA) |
| 39 | C1 v2 (через агентов) |
| 41 | C2 (причины отклонений, очередь просмотра) |
| 43 | C3 (диагностика классификации и NTRS) |
| 45 | C4 (только Boeing 720) |
| 47 | C5 (диагностика archive.org) и Q1 (инструмент QC) |
| 49 | C6 (контакт-листы) и D2 (финальный звук) |
| 51 | V (Kokoro: лицензия, установка, тест) |
| 53 | Освобождение диска |
| 55 | E1 (реестр утверждений, сценарий) |
| 57 | K0 (проект моста Kaggle) |
| 59 | K1 (код моста, живая задача) |
| 65 | FS1 (реестр источников футажа) |
| 67 | **MASTER RUN P1–P7** |

Полный текст всех промптов находится ниже, в переписке.

---

# Приложение. Полная переписка
(Ваши сообщения и ответы Claude. Результаты веб-поиска и выдачи инструментов опущены. Строки «🔎» показывают, что именно искал Claude.)



---

## [0] ВЫ · 2026-10-16 08:58 UTC
Изучи файлы и потом скажи где мы остановились и дай мне промп для перплексити чтобы он нашёл для нас самую лучшую нишу
_Вложения: OPENMONTAGE_UNIFIED_PROJECT_CONTEXT_RU.md, OPENMONTAGE_HANDOFF_RU.md_

---

## [1] CLAUDE · 2026-10-16 08:59 UTC
🔎 bash_tool: cd /mnt/user-data/uploads && wc -c *.md && cat OPENMONTAGE_HANDOFF_RU.md

🔎 bash_tool: cd /mnt/user-data/uploads && cat OPENMONTAGE_UNIFIED_PROJECT_CONTEXT_RU.md

## Где мы остановились

**Файл от 16 октября (новее) говорит:**
- Строим фабрику документальных YouTube-видео на английском, режим строго $0. Сначала нужен один пилот на 6-10 минут, потом масштабирование.
- Рабочая ниша: **"The Hidden Business Behind Everyday Things"** (скрытый бизнес за обычными вещами: логистика, упаковка, инфраструктура). Это только гипотеза, не доказанная ниша.
- Ветка `factory/business-documentary-pilot`. Один этап рендера прошёл: 84 сек, 1920×1080, H.264/AAC, стоимость 0.
- Исправление subtitle resolver (в схеме `style` строка, а resolver ждал dict) сделано только во временном скрипте `/tmp/kilo/stage10b_compose.py`. В продовый код оно, возможно, не попало.
- Независимый выбор ниши через Perplexity по 100 темам запрошен, но результата в файлах нет. Это следующий шаг.

**Файл от 14 октября (старше):**
- Ночной runner для Kilo: на момент отчёта PID 28688, OmniRoute не работал, шла Kilo Free Mode.
- Стадии `topic → research → evidence → script → fact_check` прошли. `storyboard` застрял: модель выдумывала ID источников `f1/f2`.
- Стадии `narration`, `footage` и `render` в фабрике не реализованы (в отчёте 6 из 19 стадий). Полный end-to-end не доказан.
- Исследование 20-30 бесплатных API не сделано.

**Все статусы процессов, Git и ключей могли устареть.** Перед работой нужен read-only preflight: `git status`, `HEAD`, процессы, lock.

**Ближайшие шаги:**
1. Получить отчёт Perplexity по нише (промпт ниже).
2. Проверить, попал ли subtitle fix в продовый код.
3. Починить валидацию ID в storyboard.
4. Сделать пилот на 30-90 секунд с настоящими лицензированными кадрами.

## Промпт для Perplexity (Deep Research)

```text
Act as an independent YouTube strategy analyst. Today is October 16, 2026. Use only verifiable, current sources and cite every claim with a URL and access date. Do not trust any single claim without cross-checking; label every number as VERIFIED / ESTIMATE / UNKNOWN.

GOAL
Find the single best long-form (6–10 min), faceless, English-language documentary-style YouTube niche for a NEW channel with zero audience, produced by an automated AI pipeline (research → script → TTS narration → licensed stock/public-domain footage + original charts/diagrams → edit). Do not limit yourself to any preset list: consider ALL plausible niches (business case studies, company earnings explained, supply chains/logistics, infrastructure/engineering, economics, finance/investing, history, true crime, science/space, geography, aviation/megaprojects, psychology, applied AI for professions, etc.). Then rank them.

HARD CONSTRAINTS
- Budget $0: only free/open/local tools; no paid footage or APIs.
- Visuals must come from legally reusable sources (Wikimedia Commons, Internet Archive, NASA, government/public-domain, CC-BY with attribution, Pexels/Pixabay-type licenses with terms verified) plus original graphics. Penalize niches where good licensable footage is scarce.
- Must pass YouTube's current policies on "inauthentic content" (mass-produced/repetitive content), reused content, copyright, and advertiser-friendliness. Quote the current policy wording briefly and explain how an AI-assisted channel stays compliant (original script, original analysis, real value added, human review).
- Creator is a minor-age teenager in Kazakhstan: check AdSense age/payment constraints and realistic workarounds (parent/guardian account, Brand/partner options). Mention this as a risk factor, not a blocker for the niche ranking.
- Every factual claim in videos needs a primary source; penalize niches that depend on unverifiable rumors, living-person defamation risk, or graphic content that limits ads.

EVALUATE EACH CANDIDATE ON (score 1–10, with weights stated and sensitivity analysis)
1. Demand: Google Trends / YouTube search evidence, real example videos with title, channel, date, views, and channel size (compare views to the channel's median, not just absolute).
2. Competition & saturation, and whether small/new channels actually break out (find 5+ real examples of channels <10k subs with videos >100k views in the last 12 months).
3. Footage/licensing availability for 6–10 min videos.
4. Evergreen vs time-sensitive.
5. Fit for original narration (not re-telling a famous viral story).
6. Monetization: RPM ranges ONLY from named sources/creator disclosures with dates and method; separate RPM from CPM; state uncertainty. Ignore the unverified TikTok claim of "$4–$22 RPM by niche".
7. Production complexity for an automated pipeline and risk of factual errors.
8. Risk: demonetization, copyright strikes, AI-content policy, defamation.

OUTPUT FORMAT
1. Executive answer: the ONE best niche + 2 runners-up, with a 5-sentence justification.
2. Ranked top-10 table with weighted scores, key evidence links, and sensitivity analysis (what changes if weights change).
3. For the winner: 20 specific video ideas (title, search intent, why it's low-competition, primary sources available, footage sources available), and a repeatable episode structure with timestamps for 8 minutes.
4. 3 pilot videos to launch first + go/no-go criteria based on YouTube Studio metrics (CTR, first-30s retention, AVD, returning viewers, traffic source mix) — state clearly what benchmarks are context-dependent.
5. 90-day plan (upload cadence realistic for an automated pipeline with human review).
6. Evidence section: real channel/video examples with dates, views, links.
7. "Unknowns and risks" list: what could not be verified and how to test it cheaply.
8. Contradictions found between sources.

Be skeptical. If the evidence says the current hypothesis "The Hidden Business Behind Everyday Things" (hidden business/logistics/infrastructure behind everyday products) is NOT the best, say so and explain why. Test it explicitly against the top alternatives (company earnings explained, business case studies, economics explained, engineering/infrastructure, personal finance, aviation/megaprojects).
```

Если у вас есть список из 100 ниш, прикрепите его к промпту. Когда отчёт придёт, пришлите его мне, и я сверю с гипотезой.

---

## [2] ВЫ · 2026-10-16 09:05 UTC
_(без текста)_
_Вложения: OPENMONTAGE_UNIFIED_PROJECT_CONTEXT_RU_1.md, bfda38e9270bfdf8c5f3700cff94a3c8.webp, ec6a671319045f69d3a4a63f78d7d797.webp, d16a4cd5bcfd3229fe67620bd922daac.webp, f20e7c5ab2060b17113b71b2c8f7c2c5.webp, a2aeeb3082c34fac6dae61ec196d7dd8.webp, 7b43d889524256db29a1e2f46ddddc7d.webp, eec854207f61fd9fd9cdc1cfe7bec409.webp_

---

## [3] CLAUDE · 2026-10-16 09:06 UTC
🔎 bash_tool: cd /mnt/user-data/uploads && diff OPENMONTAGE_UNIFIED_PROJECT_CONTEXT_RU.md OPENMONTAGE_UNIFIED_PROJECT_CONTEXT_RU_1.md | head -50; echo rc=$?

Файл контекста идентичен предыдущему, так что статус тот же. Скриншоты с 100 нишами я переписал в список и вставил в промпт, чтобы Perplexity не нужно было ничего прикреплять. Цифры RPM из списка я намеренно оставил только как «заявленные автором, не проверены».

```text
Act as an independent YouTube strategy analyst. Today is October 16, 2026. Use only verifiable, current sources; cite every claim with URL + access date. Label every number VERIFIED / ESTIMATE / UNKNOWN. Cross-check; do not trust any single source.

GOAL
Choose the single best niche for a NEW long-form (6–10 min), faceless, English-language YouTube channel produced by an automated AI pipeline (research → script → free/local TTS → legally reusable footage + original charts/diagrams → edit → human review). Evaluate ALL 100 niches below independently, and also add any strong niche missing from the list (e.g., hidden business/supply chains/infrastructure, company earnings explained). Then rank.

THE 100 NICHES (names translated from Russian; the "RPM" values come from an unverified TikTok post by @weaponsgeek — treat them as CLAIMS ONLY, do not use as data, and do not confuse RPM with CPM):
1 Formula 1 news (7); 2 Company earnings breakdowns (22); 3 Simpsons predictions (5); 4 Ancient civilizations (7); 5 AI tutorials (14); 6 Luxury cars (8); 7 Animal facts (6); 8 Personal budgeting (20); 9 Old Hollywood (7); 10 Aviation news (10); 11 Geopolitics (11); 12 Driving tips (8); 13 Chess (5); 14 Billionaire stories (8); 15 History in simple terms (7); 16 Basketball documentaries (5); 17 Megaprojects (10); 18 Card strategy games (5); 19 Cruise tips (9); 20 Space exploration (6); 21 Formula 1 documentaries (7); 22 Royal family stories (7); 23 AI news (13); 24 Vintage cars (8); 25 Wildlife documentaries (6); 26 Business case studies (15); 27 Cartoons (5); 28 Plane crash investigations (10); 29 Vikings (7); 30 Luxury watches (8); 31 Toyota tips (8); 32 Investing for beginners (18); 33 Extinct animals (6); 34 Movie cars (7); 35 Company histories (13); 36 Airport tips (9); 37 Basketball news (5); 38 Medieval history (7); 39 Statistics in charts (12); 40 Shark facts (6); 41 Housing market news (16); 42 Celebrity/star documentaries (4); 43 Maps & geography (6); 44 Motorcycle riding tips (7); 45 Old money / aristocracy (7); 46 Astronomy (6); 47 Luxury (8); 48 Architecture (7); 49 NFL for beginners (5); 50 Economics in simple terms (16); 51 Native Americans (7); 52 MMA news (5); 53 Travel documentaries (8); 54 Company histories with analysis (12); 55 Engineering in simple terms (7); 56 Celebrity lives (4); 57 Aviation history (9); 58 Basketball news (5); 59 Ancient mysteries (7); 60 Formula 1 history (7); 61 Business & economics (14); 62 Golf (5); 63 Royal family news (7); 64 Airline industry (9); 65 History of great battles (7); 66 Climate & nature (6); 67 Luxury homes (8); 68 Sports business (5); 69 Gemstones (7); 70 Aircraft (7); 71 Economics documentaries (12); 72 Car collections (8); 73 Women's basketball (5); 74 Infrastructure in simple terms (10); 75 AI for productivity (12); 76 Ocean exploration (6); 77 American football (5); 78 Religion/Bible (4); 79 Geopolitical investigations (11); 80 Vintage America (7); 81 Animal documentaries (6); 82 European football (5); 83 Science in simple terms (6); 84 Motorcycle reviews (7); 85 History + economics (12); 86 Luxury travel (8); 87 Football history (5); 88 Aircraft in simple terms (9); 89 Rappers (4); 90 Frugal living (4); 91 Boxing documentaries (5); 92 History of architecture (7); 93 Men's style (4); 94 Women's style (4); 95 Geography in simple terms (6); 96 Mythology (4); 97 Psychology (4); 98 Boxing news (5); 99 Tips for seniors (4); 100 Historical documentaries (7).

HARD CONSTRAINTS
- Budget $0: free/open/local tools only; no paid footage/APIs.
- Visuals only from legally reusable sources (Wikimedia Commons, Internet Archive, NASA, government/public domain, CC-BY with attribution, free-license stock with verified terms) plus original graphics. Penalize niches with scarce licensable footage (sports leagues, celebrities, movie/TV clips, luxury brands, etc.).
- Must comply with YouTube's CURRENT policies on inauthentic/mass-produced content, reused content, copyright, advertiser-friendly guidelines. Quote key policy wording briefly and explain how an AI-assisted channel stays compliant (original script/analysis, human review).
- Creator is a teenager in Kazakhstan: check AdSense age/payment constraints and realistic legal workarounds (guardian account etc.). Treat as a risk note, not as a ranking factor.
- Every factual claim needs a primary source; penalize niches with rumor-based content, defamation risk with living people, or ad-limiting content (war, violence, religion, geopolitics controversy).
- News niches (sports/AI/aviation/housing news) are time-sensitive and hard to automate with fact-checking: score accordingly.

SCORING (1–10 each; state weights; run a sensitivity analysis)
1 Demand (Google Trends, YouTube search evidence, real videos with title/channel/date/views/channel size, views vs channel median)
2 Competition & small-channel breakout (find 5+ real channels <10k subs with a video >100k views in last 12 months, per top niche)
3 Licensable footage availability for 6–10 min
4 Evergreen vs time-sensitive
5 Room for original narration/angle (not retelling viral stories)
6 Monetization: RPM only from named sources/creator disclosures with date and method; separate from CPM; state uncertainty
7 Automation fit & factual-error risk
8 Policy/copyright/demonetization risk

OUTPUT
1. Executive answer: ONE best niche + 2 runners-up, 5-sentence justification.
2. Table of all 100 niches: quick score and a one-line reason (group obviously weak ones, e.g. sports news, celebrities, to save space); detailed top-10 table with weighted scores, evidence links, sensitivity analysis.
3. For the winner: 20 specific video ideas (title, search intent, why low-competition, primary sources, footage sources) + an 8-minute episode structure with timestamps.
4. 3 pilot videos + go/no-go criteria using YouTube Studio metrics (CTR, first-30s retention, AVD, returning viewers, traffic sources); say which benchmarks are context-dependent.
5. Realistic 90-day plan for an automated pipeline with human review.
6. Evidence section: real channel/video examples with dates, views, links.
7. Unknowns/risks + cheap tests to resolve them.
8. Contradictions between sources.

Be skeptical. Explicitly test my current hypothesis "The Hidden Business Behind Everyday Things" (hidden business/logistics/infrastructure behind everyday products; maps to #26, #35, #54, #61, #74, #85) against the top alternatives (#2 earnings breakdowns, #32/#8 personal finance, #50 economics, #17 megaprojects, #57/#64 aviation). If it is NOT the best, say so and why.
```

Когда отчёт придёт, пришлите его целиком, и я сверю с гипотезой. После этого можно вернуться к кодовой части: проверить, попал ли subtitle fix в продовый код, и починить ID в storyboard.

---

## [4] ВЫ · 2026-10-16 09:07 UTC
_(без текста)_
_Вложения: DOC-20261016-WA0120.pdf_

---

## [5] CLAUDE · 2026-10-16 09:07 UTC
## Вердикт по отчёту Perplexity

**Ниша подтверждена, но в суженном виде.** Побеждает «как устроены обычные вещи и системы» (логистика, цепочки поставок, инфраструктура). Широкое «hidden business» перегружено пересказами известных компаний, поэтому нужны конкретные системы с первичными источниками. Ближайшие альтернативы: инфраструктура/мегапроекты (7.8 против 8.1) и бизнес-провалы (7.4).

**Что в отчёте надёжно:**
- Политика YouTube: AI-контент монетизируется, если есть оригинальный анализ и человеческая проверка.
- AdSense требует 18+. Вариант для вас: аккаунт AdSense родителя или опекуна, оформить письменно.
- Структура видео на 8 минут и критерии go/no-go подходят нам.

**Что в отчёте слабо:**
- Сам Perplexity признаёт, что не проверил главное: есть ли каналы до 10k подписчиков с видео от 100k просмотров. Оценки спроса и конкуренции в таблице — его субъективные баллы.
- По вашим 100 нишам подробно разобраны только 10, остальные не оценены.
- RPM взяты из сторонних сайтов (WicMe, channel.farm), это оценки.

**Главная проблема: footage.** Perplexity пишет, что бесплатных кадров «исключительно много», но это верно для инфраструктуры: вода, электросети, порты, зерно, дороги (кадры от госструктур, NASA, Wikimedia). Для супермаркетов, e-commerce складов, кофе и доставки лицензируемых кадров мало. А именно их он предлагает как три пилота: бананы, молоко в супермаркете, last-mile. Это самые слабые пилоты для нашего пайплайна.

**Мой выбор пилотов (с учётом footage и источников):**
1. **How a City Gets Water** (идея №8 из отчёта): госкадры, данные коммунальных служб, понятная схема.
2. **How a Container Ship Moves 90% of Everything You Own** (№5): UNCTAD, порты, Wikimedia, отличные карты маршрутов.
3. **Why Electricity Cannot Be Stored in a Warehouse** (№10): документы операторов сетей, много диаграмм.

Если эти три пройдут проверку на footage и источники, бананы и last-mile можно делать позже с упором на оригинальную графику.

**Что осталось непроверенным, и дешёвые тесты:**
- Конкуренция: вручную посмотреть 30-50 свежих видео по этим темам и записать подписчиков канала, дату, просмотры и медиану канала.
- Footage: для каждого пилота найти минимум 20-30 лицензированных клипов до начала сценария.
- RPM: до монетизации не опираться ни на какие цифры.

Дальше есть два пути: проверить footage-покрытие для трёх пилотов или вернуться к коду (subtitle fix, storyboard ID). Какой выбираете?

---

## [6] ВЫ · 2026-10-16 09:08 UTC
А расскажи про компаний или про знаменитости как тебе такая ниша?

---

## [7] CLAUDE · 2026-10-16 09:08 UTC
## Компании и бизнес-истории (#26, #35, #54)

**Плюсы**
- Спрос высокий. Perplexity дал 8/10 по спросу и 8/10 по монетизации, это 3-е место в его рейтинге (7.4).
- Заявленный RPM в списке TikTok-автора выше среднего: 12-15 против 4-8 у большинства ниш. Эти цифры не проверены.
- Много материала для сценария: годовые отчёты, SEC-документы, интервью, архивные статьи.

**Минусы для нашей фабрики**
- **Footage.** У компаний нет лицензируемых кадров: логотипы и продукты защищены, офисы и CEO сняты чужими камерами. Остаётся стоковая «бизнес-картинка» и графики. Это ровно то «слайд-шоу со случайным B-roll», которого мы хотим избежать.
- **Конкуренция.** Perplexity поставил 5/10. Каналов про истории компаний очень много, а про famous-компании (Apple, Tesla, Nike) пересказов уже сотни. Новому каналу пробиться трудно.
- **Риск.** Утверждения о реальных людях и компаниях (провалы, скандалы, мошенничество) создают риск клеветы. Нужна строгая проверка каждого факта.
- **Политика YouTube.** Пересказ чужих статей и роликов без своего анализа считается неоригинальным контентом.

**Когда это работает:** если брать малоизвестные компании или провалы и строить рассказ вокруг схем и данных (финансовые графики, таймлайны, цепочки решений), а не вокруг кадров.

## Знаменитости (#42, #56, #89, #9 Old Hollywood)

Я бы **не брал**.
- RPM по списку самый низкий: 4-7.
- Лицензируемых кадров почти нет: фото, клипы и музыка принадлежат агентствам и студиям. Это прямой путь к страйкам.
- Высокий риск клеветы: жизнь живых людей, слухи, личные истории.
- Очень насыщенная ниша (клики, реакции, сплетни), оригинального ракурса у AI-канала нет.
- Perplexity поставил даже true crime (родственная ниша) на последнее место из 10: 4.8.

Единственное исключение: Old Hollywood об умерших людях, где фото и фильмы в public domain. Но это история кино, а не знаменитости, и RPM там всё равно около 7.

## Итог

| | Компании | Знаменитости |
|---|---|---|
| Footage | слабо | очень слабо |
| Риск | средний | высокий |
| Подходит фабрике | частично | нет |

**Рекомендация:** компании брать только как **второй слой** внутри выбранной ниши. Например, ролик «How a Container Ship Moves 90% of Everything» плюс блок «кто на этом зарабатывает». Так остаётся и кадровое покрытие (порты, инфраструктура), и бизнес-угол с лучшим RPM. Отдельный канал про компании я бы не начинал.

Хотите, составлю пилотный ролик так, чтобы бизнес-часть занимала 30-40%?

---

## [8] ВЫ · 2026-10-16 09:09 UTC
Хорошо какой самый лучший под нас выбери и продолжим

---

## [9] CLAUDE · 2026-10-16 09:09 UTC
## Выбор: «Как устроены системы вокруг нас» (инфраструктура и логистика, бизнес как второй слой)

**Почему именно она:**
- Лучший footage-fit: кадры госструктур, NASA, Wikimedia, порты, сети, водоканалы. Это прямо решает слабое место нашей фабрики.
- Первое место у Perplexity (8.1) плюс второе (7.8) почти совпадают: сужаем к инфраструктуре, где кадров больше всего.
- Вечный спрос: «как это работает» не устаревает.
- Низкий риск клеветы и политики, нет «AI даёт финансовые советы».
- Бизнес-слой («кто платит, где маржа») даёт лучший RPM без отдельной ниши.

**Позиционирование:** *«Как устроены системы, которыми мы пользуемся каждый день, и сколько они стоят.»*

**Пилот №1: How a City Gets Water.** Причины: больше всего госкадров, много открытых данных (отчёты водоканалов), понятные схемы, нет спорных тем. Пилоты №2 и №3: контейнерные перевозки и электросеть.

**Правило выбора темы:** тема принимается, только если есть минимум 5 источников и 20-30 лицензированных клипов. Иначе отбрасываем до написания сценария.

## Следующий шаг

Сначала проверяем, хватит ли footage для пилота. Промпт для Kilo (read-only, без правок кода):

```text
Read-only task. Do not modify code. Evaluate footage and source coverage for pilot video "How a City Gets Water" (6–8 min, English).

1. Run read-only preflight: git status --short --branch, current HEAD. Note any uncommitted changes; don't touch them.
2. Using the existing footage adapters (archive_org, wikimedia, etc.), search for clips/images covering: reservoirs/dams, intake, treatment plant (filtration, chlorination), pumping stations, underground pipes, water towers, tap/consumer, pipe leaks/maintenance. Real transport errors must surface, not be reported as "0 clips success" (see issue #511).
3. For each candidate record: asset_id, source URL, author, license + license URL, duration, which scene it covers. Discard anything without a verified license.
4. Find at least 5 primary sources (utility annual reports, EPA/WHO/government water data) with exact URLs; do not invent IDs or facts.
5. Output a coverage table: scene → number of licensed clips → gaps. Verdict: GO if ≥20 usable licensed clips and ≥5 sources, else NO-GO with the exact gaps.
6. Save the report to the existing docs/checkpoint location and list exactly what was observed vs assumed. Do not publish, do not reset/clean git, do not expose secrets.
```

Пришлите вывод агента. Если GO, идём на этапы сценария и evidence ledger. Если NO-GO, переходим к пилоту про контейнеры.

---

## [10] ВЫ · 2026-10-16 09:10 UTC
Давай про футажи сам а агент будет строить фабрику
_Вложения: Screenshot_20261016_134201.jpg_

---

## [11] CLAUDE · 2026-10-16 09:11 UTC
Принято: футажи беру на себя, агент строит фабрику. Сначала проверю, что реально есть по теме воды.

🔎 web_search: Wikimedia Commons category water treatment plant videos

🔎 web_search: public domain video water treatment plant Internet Archive Prelinger OR USGS OR EPA OR DVIDS

## Результат по футажам для пилота «How a City Gets Water»

**Вердикт: пока не GO.** Видео я не пересчитывал клип за клипом, но картина по источникам такая.

**Что реально бесплатно и легально:**
| Источник | Что есть | Условия |
|---|---|---|
| USGS | фото очистных и водозаборов | помечено Public Domain |
| CDC PHIL | фото водоочистки и лабораторий (2024) | без ограничений по авторскому праву |
| DoD / DVIDS | фото и видео (например, Minot Water Treatment, 5:41, 2011) | public domain, но нужна ссылка на автора и соблюдение ограничений на эмблемы и лица |
| Wikimedia Commons | ~320 файлов в «Water treatment», 227 в «Wastewater treatment» | лицензия у каждого файла своя, проверять отдельно |
| WPA / университетские архивы | исторические фото 1930-х | public domain в США, в других странах не гарантировано |

**Главная проблема:** почти всё из этого **фото и схемы, а не видео**. Видео нашлось только отдельными случаями (DVIDS Minot, один ролик Ruhr в Commons). Freepik, Magnific и Getty показывают красивые дроны, но это стоки с платными или ограниченными лицензиями. По правилу $0 они не подходят.

**Что это значит для пилота:**
- 6-8 минут одними лицензированными видеоклипами по воде не набрать.
- Выход: фото с Ken Burns-анимацией (Commons, USGS, CDC), много оригинальных схем и анимаций (этапы очистки, карта сети) и 3-5 настоящих видеоклипов из DVIDS и Commons.
- Это даже лучше для «оригинального контента» по политике YouTube, но визуально беднее, чем с живым видео.

**Не проверено:** точное число лицензированных видеоклипов и лицензии каждого файла. Это должен посчитать адаптер в OpenMontage.

## По скриншоту

- Агент завершил пилот про **поддоны** (pallets-hidden-business): 84.975 с, 1920×1080, 32 МБ, cost 0.0, 2158 тестов прошло.
- Честные пробелы, которые агент сам указал: нет `qa_report.json`, источники пока «tertiary» (не первичные), публикация исключена.
- Ветка на 2 коммита впереди remote (`0↓ 2↑`). Батарея 17%: **запушить коммиты**, чтобы не потерять работу.

## Следующий шаг для агента

```text
Read-only footage audit, no code changes. For pilot "How a City Gets Water":
1. Run existing footage adapters (wikimedia, archive_org, DVIDS/US-gov sources if present) for: reservoir, dam, intake, filtration, chlorination, pumping station, pipes, water tower, tap.
2. Count ONLY items that are VIDEO with a verified per-file license + license URL + author. Report separately: video clips vs still images.
3. Surface real transport errors (issue #511); never report an error as "0 clips success".
4. Output table: scene → licensed videos, licensed photos, gaps. Verdict GO if ≥8 licensed video clips + ≥25 licensed photos + ≥5 primary sources (utility/EPA/USGS reports), else NO-GO with exact gaps.
5. Then git push the 2 pending commits only if the branch remote is configured; do not reset/clean.
Report observed vs assumed.
```

Если по итогам аудита видео будет мало, пойдём на пилот про контейнерные перевозки, там у порта и NASA/DVIDS обычно богаче видео. Но это тоже нужно проверить, а не предполагать.

---

## [12] ВЫ · 2026-10-16 09:15 UTC
Изучи гитхаб и найди скилы по типу claude YouTube agent skills но для тебя и чтобы ты искал самый лучший нишу

---

## [13] CLAUDE · 2026-10-16 09:15 UTC
🔎 web_search: github Claude skills YouTube niche research agent skill SKILL.md

Нашёл несколько репозиториев. Код я не аудировал, только прочитал описания, поэтому всё ниже требует проверки перед установкой.

## Что подходит для выбора ниши

| Репозиторий | Что делает | Зачем нам |
|---|---|---|
| **larrygmaguire-hash/youtube-researcher-mcp** | MCP-сервер на YouTube Data API v3 плюс готовый `SKILL.md`: поиск видео, метаданные, engagement, размеры каналов, паттерны заголовков, отчёт по нише | Закрывает главный пробел отчёта Perplexity: каналы до 10k подписчиков с видео от 100k просмотров. Нужен бесплатный API-ключ Google |
| **MalekAG/claude-code-setup** | Набор из 32 скиллов, среди них `youtube-outliers`, `cross-niche-outliers`, `market-research` (Web/Reddit/X) | Поиск «выстреливших» видео в нише и смежных нишах. Копировать только нужные скиллы, не весь сетап |
| **TimBroddin/skills** (`youtube-research`) | Берёт каталог каналов, фильтрует видео по теме, транскрибирует нужные, делает отчёт с таймкодами | Разбор конкурентов: как они строят сценарий и чем выигрывают |
| **Skillproofdev/research-discipline** | 8 правил: источники живые, цитаты на каждое утверждение, проверка по двум независимым источникам, пометки `[unverified]` | Хорошо ложится на наш evidence ledger и защищает от выдуманных фактов |

## Что пропустить

- **AgriciDaniel/claude-blog** и **adityaarsharma/youtube-marketing-skills**: первый про блоги, второй пишет обратно в YouTube и WordPress и требует доступа к каналу. Это на потом, после первого видео.
- **charlie947/social-media-skills**: исследует соцсети через Claude for Chrome, к YouTube-нише отношения почти не имеет.

## Важные оговорки

- Эти скиллы работают в Claude Code или Kilo. В этом чате я их сам подключить не могу, сеть у меня отключена. Либо их ставит агент в Codespace, либо вы загружаете папку как zip в настройках «Customize skills» в Claude.
- Перед установкой агент должен прочитать `SKILL.md` и все скрипты на сетевые вызовы и работу с файлами. Токены и ключи в чат не вставлять.
- Все цифры (звёзды, число скиллов) взяты из описаний репозиториев, я их не проверял.
- Скиллы собирают данные, но «лучшую нишу» они не выберут. Решение остаётся за нами по весам и проверенным данным.

## Предлагаемый порядок

1. Получить бесплатный ключ YouTube Data API v3 (это ваш шаг, в Google Cloud).
2. Агент ставит `youtube-researcher-mcp` и прогоняет 3 темы пилотов: вода, контейнеры, электросеть.
3. Он собирает для каждой по 30-50 свежих видео: подписчики канала, дата, просмотры, медиана канала.
4. Отдельно `research-discipline` подключаем для evidence-этапа фабрики.

Промпт для агента:

```text
Task: audit and install ONE skill, read-only first. Repo: github.com/larrygmaguire-hash/youtube-researcher-mcp
1. Clone to /tmp, read README, skill/SKILL.md, and all source files. Report any network calls other than googleapis.com, any file writes outside the project, any env vars read. Do not install if anything is suspicious.
2. Check license and last commit date.
3. If clean: install per README, register as MCP in the project config, and wait for YOUTUBE_API_KEY (never ask me to paste it into chat; read it from env only).
4. Test with a single harmless search and report quota used.
5. Do not touch the factory code, do not push, do not expose secrets.
```

Дальше нужен ключ API. Он у вас уже есть, или объяснить, как получить?

---

## [14] ВЫ · 2026-10-16 09:17 UTC
Нет просто изучи репозиторий которому не нужно ничего скачай его себе скила и исползуй его и найди мне нишу для Ютуба самый лучший

---

## [15] CLAUDE · 2026-10-16 09:18 UTC
Скачать на свою машину я не могу: у меня нет сети в песочнице. Но я могу прочитать скилл и следовать его правилам. Читаю.

🔎 web_fetch: https://github.com/Skillproofdev/research-discipline

🔎 web_search: faceless YouTube channel supply chain infrastructure explainer small channel views growth 2026

🔎 web_search: Wendover Productions Practical Engineering Real Engineering subscribers infrastructure logistics explainer channels

## Как я работал

Скачать скилл на машину не могу (нет сети в песочнице), поэтому прочитал его `SKILL.md` и вручную применил его правила: живые источники вместо памяти, пометки `[unverified]`, адверсарный проход. Ключей он не требует.

## Что нашёл

**Подтверждено разными источниками:**
- YouTube в июле 2025 ввёл политику «inauthentic content», а в январе 2026 удалил волну каналов. Цель: массовый шаблонный контент без авторского взгляда. Сам AI и faceless-формат не запрещены (reap.video; тот же вывод у Perplexity со ссылкой на support.google.com).
- В этой нише сидят сильные игроки: Wendover (~4.8-4.9M подписчиков, в среднем 800K просмотров на видео, ролики ~22 мин), Practical Engineering (~4.5-4.8M), Real Engineering (~5.1M). `[данные агрегаторов, не из первоисточника]`

**Адверсарный вывод, который меняет план:**
- Практическая инженерия уже занимает «воду, канализацию, мусорные полигоны, плотины». Wendover занимает порты, авиацию, логистику. Прямо вставать в эти темы с физикой и инженерией нельзя: нас сравнят с 4-миллионными каналами.
- Мой прошлый пилот «How a City Gets Water» лежит в полосе Practical Engineering. Я бы от него отказался или сменил угол.

**Не подтверждено (`[unverified]`):**
- Есть ли маленькие каналы с видео от 100k просмотров именно в этой нише. Нашлись только общие SEO-статьи про faceless-каналы, надёжность низкая. Утверждение «under 10k subs удвоили просмотры Shorts» (Metricool) я не проверял по первоисточнику.
- Реальный RPM. Цифры дают агрегаторы (например, Wendover $7-21K/мес по VidIQ), это оценки.

## Вывод

**Ниша остаётся той же: «как устроены системы вокруг нас», но с другим углом.** Не «как это работает физически» (занято), а **«куда уходят деньги и почему это стоит столько»**: стоимость, маржа, кто получает плату. Примеры: «Куда уходят деньги, когда вы платите за воду», «Почему бананы дешёвые», «Сколько на самом деле стоит доставка последней мили».

Почему это лучше для нас:
- Угол «деньги и источники» требует документов и данных, а не лабораторных моделей и дорогого видео, как у конкурентов. Фабрике это подходит.
- Видео из лицензированных клипов не нужно: основа сюжета строится на графиках, схемах и фото из USGS, CDC, Wikimedia.
- Тема не совпадает по формату с Wendover и Practical Engineering.

**Рискованное допущение:** что такой угол реально находит аудиторию. Проверить можно только живыми данными YouTube: по каждому запросу («why is X so cheap» и т.п.) посмотреть, какие каналы ранжируются и сколько у них подписчиков. Это и есть шаг, для которого нужен YouTube Data API. Или можно сделать вручную: 5 запросов в YouTube, записать топ-10 результатов.

## Что делаем дальше

1. Пилот №1 пересобираем как **«Who Gets Paid When You Pay Your Water Bill»**: тарифы, расходы водоканала, инфраструктурные долги. Источники: отчёты водоканалов, EPA, USGS.
2. Агент проверяет, хватает ли лицензированных фото и графиков (запрос на аудит из прошлого ответа остаётся в силе, только с новой темой).
3. Вы вручную вводите 5 поисковых запросов по теме в YouTube и присылаете мне, кто в топе и сколько у них подписчиков. Я разберу.

Готов сделать шаг 3 прямо сейчас, если пришлёте скриншоты результатов поиска.

---

## [16] ВЫ · 2026-10-16 09:18 UTC
Нет я не хочу эту нишу найди мне другую нишу для Ютуба

---

## [17] CLAUDE · 2026-10-16 09:19 UTC
Понял, инфраструктуру убираю. Ищу другую нишу, где у нас сильнее всего именно footage. Проверяю источники.

🔎 web_search: NASA media usage guidelines public domain images video commercial use

🔎 web_search: YouTube channel space history archival NASA footage documentary small channel growth forgotten missions

## Новая ниша: история авиации и космоса на архивных кадрах NASA

**Формат:** «испытания, провалы и забытые программы». Например, эксперименты, которые NASA делало нарочно, и машины, которые почти никто не помнит.

**Почему она подходит нам:**
- **Footage решён.** По сообщению AFP, NASA открыла более 140 000 видео и фото. Armstrong Flight Research Center отдельно выгрузил около 500 архивных роликов: испытания Lunar Landing Research Vehicle, посадочные тесты шаттла, полёты X-1 и X-43A, а также контролируемое разрушение Boeing 720 в 1984 году. Это та самая ниша, где живого видео хватит на 6-8 минут, а не только фото.
- **Права.** По официальным правилам NASA, материалы обычно не защищены авторским правом США. Есть три оговорки: логотипы и эмблемы NASA использовать нельзя, на видео с узнаваемыми людьми для коммерческого использования может понадобиться их согласие (право на изображение), и часть материалов принадлежит третьим сторонам и помечена отдельно.
- **Первичные источники есть.** Технические отчёты NASA и расследования NTSB в открытом доступе.
- **Не пересекается с отвергнутой нишей** и с Practical Engineering и Wendover по темам.
- В вашем списке это ближайшие пункты: #57 история авиации, #20 освоение космоса, #28 расследования авиакатастроф.

**Что остаётся риском (проверено только частично):**
- Конкуренция в космосе большая. Каналы вроде Dutchsteammachine уже перезаливают реставрированные кадры NASA, поэтому YouTube может счесть пересказ чужих кадров неоригинальным. Нужен свой анализ и своя графика, а не просто нарезка.
- Спрос на конкретные забытые программы я не измерял. Это `[unverified]`.
- RPM из вашего списка (6-10) не проверен.
- Расследования катастроф с погибшими лучше брать осторожно: возможны ограничения рекламы и вопросы этики. Брать испытания и технику, а не трагедии с жертвами.

## 3 пилота для проверки

1. **The Plane NASA Crashed on Purpose**: контролируемое разрушение Boeing 720 (1984), отчёты NASA и FAA, кадры из архива.
2. **The Flying Bedstead That Trained Apollo Pilots**: Lunar Landing Research Vehicle, кадры и отчёты NASA.
3. **Landing the Shuttle on a Dry Lake**: посадочные тесты шаттла, документы Armstrong Center.

Детали в сценариях (даты, цифры, хронология) должны идти только из отчётов NASA, не из моей памяти.

## Следующий шаг: аудит кадров для агента

```text
Read-only footage audit, no code changes. Niche: NASA/aviation test history.
Pilot topics: (1) Boeing 720 Controlled Impact Demonstration 1984, (2) Lunar Landing Research Vehicle, (3) Space Shuttle landing tests at Edwards.
For each: use existing adapters (NASA Image and Video Library, archive_org, wikimedia) to list VIDEO clips with asset_id, URL, creator, rights statement, duration. Flag clips with identifiable persons, third-party copyright, or NASA logos. Surface real transport errors (issue #511).
Find ≥3 primary sources per topic (NASA/FAA/NTSB reports) with exact URLs; do not invent IDs.
Verdict per topic: GO if ≥10 usable video clips and ≥3 primary sources, else NO-GO with gaps.
Report observed vs assumed. Do not modify code or push.
```

Если аудит даст GO по двум из трёх, берём эту нишу. Подходит она вам по теме или хотите сначала посмотреть ещё одну альтернативу (например, древняя и средневековая история на кадрах музеев)?

---

## [18] ВЫ · 2026-10-16 09:20 UTC
Дальше изучай и найди самый лучший ultra thinking

---

## [19] CLAUDE · 2026-10-16 09:21 UTC
Запускаю глубокое исследование: сравниваю несколько ниш по footage, политике YouTube, конкуренции и данным о заработке.

🔎 web_search: YouTube RPM by niche 2026 history education science finance creator-reported data

🔎 web_fetch: https://support.google.com/youtube/answer/1311392?hl=en

🔎 web_search: National Archives NARA public domain film footage WWII Cold War free to use YouTube documentaries copyright

🔎 web_search: outlierkit history documentary faceless channel breakout small channel outlier videos archival footage

## Итог исследования

**Лучшая ниша для нас: история авиации и космических испытаний на архивных кадрах (NASA, ВВС, национальные архивы).** Запасной вариант: история XX века на кадрах NARA.

### Что проверил и насколько это надёжно

**1. Заработок.** Самый честный датасет, что я нашёл: 300 каналов, май 2025 - май 2026 (AIR Media-Tech). «Education & Science» там имеет медианный RPM $10.22 при медиане по всем нишам около $2.30, а Business & Finance показывает $2.01, но в выборке всего три канала. Цифры «финансы $20+» из списка TikTok это не подтверждает. Оговорки: это один датасет, его перепечатывают разные сайты (не независимые источники), а разброс огромный: от $2.31 до $19.50.

**2. Политика YouTube (первоисточник).** Повторное использование чужих материалов разрешено, если добавлены сюжет и комментарий, но слайд-шоу без повествования и копирование без существенных изменений не монетизируются, причём даже при разрешении правообладателя. Значит, общественное достояние само по себе не защищает. Нужны оригинальный сценарий, графика и анализ. Там же: AI-персоны с советами по финансам, праву и здоровью не монетизируются. Для нас финансы поэтому рискованнее, чем казалось.

**3. Кадры и права.** В NARA более 360 000 катушек, и большинство государственных фильмов свободны от авторского права, но сама NARA не подтверждает статус каждого материала, проверка лежит на пользователе. У NASA материалы в целом не защищены авторским правом США, но логотипы и узнаваемые люди при коммерческом использовании требуют осторожности. Один центр NASA выгружал около 500 архивных видео.

**4. Живой пример.** Канал The History Stop делает ролики на общедоступных архивах: лучший недавний ролик набрал около 163K просмотров, в 7 раз выше медианы канала. Это автоматическая оценка OutlierKit, размер канала мне неизвестен.

### Рейтинг (мои оценки 1-10 с весами: кадры 25, политика 20, конкуренция 20, спрос 15, RPM 10, автоматизация 10)

| Ниша | Балл |
|---|---|
| **История авиации и космических испытаний** | **7.1** |
| История XX века на кадрах NARA | 6.8 |
| Инфраструктура (отвергнута вами) | 6.5 |
| «Было и стало» по городам на архивных фото | 6.1 |
| Бизнес и финансы | 4.8 |

Если сильно увеличить вес спроса, вперёд выходит история XX века (спрос выше, но и конкуренция огромная). Если вес кадров и политики, побеждает авиация и космос.

### Чего я не знаю
- Реальную конкуренцию именно в авиационных испытаниях. Для этого нужен поиск по YouTube.
- Доступна ли монетизация для вашей страны, или нужен аккаунт родителя в другой стране. Проверьте в справке YouTube.
- Баллы выше это моя оценка, а не измерение.

### Что дальше
1. Промпт для агента про аудит кадров из прошлого ответа остаётся в силе (три пилота: Boeing 720, Lunar Landing Research Vehicle, посадочные тесты шаттла).
2. Вы: введите в поиск YouTube «boeing 720 controlled impact demonstration», «lunar landing research vehicle», «space shuttle landing tests» и пришлите скриншоты топ-10 с числом подписчиков и просмотров. По ним я пойму, свободна ли ниша.

---

## [20] ВЫ · 2026-10-16 09:25 UTC
Хорошо теперь строим фабрику под это вот мастер план по которому работает агент
_Вложения: OPENMONTAGE_FACTORY_MASTER_PLAN_RU_v3.md_

---

## [21] CLAUDE · 2026-10-16 09:25 UTC
🔎 bash_tool: cd /mnt/user-data/uploads && wc -c OPENMONTAGE_FACTORY_MASTER_PLAN_RU_v3.md && cat OPENMONTAGE_FACTORY_MASTER_PLAN_RU_v3.md

Мастер-план v3 под новую нишу почти не меняется: шесть сессий, схемы и гейты остаются. Нужны пять точечных правок.

## Что меняется в плане

1. **Тема (сессия 3):** вместо «закулисной экономики» выбираем историю испытаний авиации и космоса. Критерий темы: есть минимум 10 лицензированных видеоклипов, 3 первичных документа (отчёты NASA, FAA, NTSB) и нет кадров с погибшими.
2. **Источники кадров:** в плане упоминается Pexels, но для нас главные источники NASA, DVIDS, NARA, Internet Archive и Wikimedia. Вероятно, придётся добавить адаптеры для NASA и DVIDS (агент это проверит).
3. **`asset_record`:** добавляем флаги прав: `identifiable_persons`, `nasa_logo_visible`, `third_party_copyright`, `credit_required`. NASA разрешает использование материалов, но логотипы, люди на видео и сторонние кадры требуют отдельной проверки.
4. **Новый QA-гейт «добавленная ценность»:** по политике YouTube (reused content) архивные кадры без существенного оригинального комментария не монетизируются, даже если они свободны от авторских прав. Гейт блокирует ролик, где нет оригинального сценария, схем и источников на экране, или где длинные отрезки это просто фото-слайдшоу.
5. **Visual QA:** VLM не может определить, какой именно самолёт на кадре. Опора на метаданные архива (ID, дата, описание NASA), а не на «уверенность» модели.

**Пилот про поддоны** остаётся доказательством, что техническая цепочка работает (84.975 с, 2158 тестов, cost 0), но как публикуемый ролик не годится: источники третичные, нет `qa_report.json`. Недостающий QA-артефакт закроем позже, на сессии 5.

## Промпт для Kilo (Milestone A: документы и аудит кадров, без изменений кода)

```text
Single milestone: niche pivot documentation + read-only footage audit. Do NOT change code, install anything, run models, or kill/remove processes/locks.

CONTEXT
Niche decision: "Aviation & spaceflight test history" on public-domain/free archive footage (NASA, DVIDS/US military, NARA, Internet Archive, Wikimedia). Rejected niches: infrastructure, business/finance case studies, celebrities. Reasons: footage rights/volume, YouTube policy fit. Pilot topic candidates: (1) NASA Boeing 720 Controlled Impact Demonstration 1984, (2) Lunar Landing Research Vehicle, (3) Space Shuttle landing tests at Edwards. Do not state any fact about these topics from memory; facts only from retrieved primary documents.

STEPS
1. Preflight: pwd, git status --short --branch, HEAD, active processes/locks (look only). Preserve user changes.
2. Create docs/openmontage/NICHE_DECISION.md: decision, rejected alternatives with reasons, constraints, and UNKNOWNS (competition not measured; monetization eligibility for creator's country not verified; RPM only third-party estimates). No secrets.
3. Append a v3.1 changelog entry to the existing master plan (do not overwrite). Changes: (a) Session 3 topic criteria = aviation/space test history with ≥10 licensed video clips, ≥3 primary documents, no footage of fatalities; (b) asset_record gains rights flags: identifiable_persons, logo_visible, third_party_copyright, credit_required; (c) per-source storage policy (NASA/DVIDS/NARA: per_project_asset); (d) new QA gate "added value": block if no original narration/analysis, no original diagrams/source cards, or long still-image-only sequences (YouTube reused/inauthentic content policy applies even to public-domain footage); (e) visual QA relies on archive metadata (ID, date, caption) rather than VLM identification.
4. Footage audit for the 3 topics using ONLY existing adapters. List which adapters exist and which are missing (NASA Image and Video Library, DVIDS, NARA). For each topic output: video clips vs stills, per-clip asset_id/URL/creator/rights statement/duration, flags (persons, logos, third-party). Real transport errors must surface (issue #511); never report an error as zero clips.
5. List candidate primary documents (NASA NTRS, FAA, NTSB) with exact URLs, per topic. Do not summarize facts from memory.
6. Verdict per topic: GO if ≥10 usable licensed video clips and ≥3 primary documents, else NO-GO with exact gaps.
7. Update the existing work log/checkpoint (observed vs assumed). Commit docs only. Push current branch to origin without force if the remote is configured; report the real result.
Done = audit table + docs committed + exact next action. Never claim a test/commit/push you did not observe.
```

Когда придёт результат аудита, пришлю следующие два промпта:
- **Milestone B:** адаптеры NASA и DVIDS с флагами прав и тестами на ошибки сети.
- **Milestone C:** гейт «добавленная ценность» и `qa_report.json`.

---

## [22] ВЫ · 2026-10-16 09:36 UTC
Продумай план, архитектуру получше и улутчи этот промп

---

## [23] CLAUDE · 2026-10-16 09:37 UTC
Продумал заново. Прежний промпт смешивал документацию, правку плана и аудит кадров, и аудит мог дать NO-GO просто из-за отсутствия адаптера NASA, а не из-за нехватки кадров. Исправляю это.

## Архитектура: что добавляется к мастер-плану

1. **Ниша как конфиг, а не код** (`niche_profile.yaml`): разрешённые источники, запрещённый контент, нужные типы первичных документов, пороги гейтов. Если ниша снова поменяется, правится один файл, а не фабрика.
2. **Гейт жизнеспособности темы (стадия 0):** дешёвая проверка до траты времени моделей. Есть ли ≥10 лицензированных видеоклипов и ≥3 первичных документа? Нет, значит тема отбрасывается сразу.
3. **Реестр политик источников:** для каждого провайдера прописано, что можно хранить, какая нужна атрибуция и как извлекать флаги прав.
4. **Расширенный `asset_record`:** добавляются `archive_id`, `archive_caption`, `archive_date`, `identifiable_persons`, `logo_visible`, `third_party_copyright`, `credit_required`.
5. **Гейт «добавленная ценность»:** детерминированная проверка по timeline без LLM (доля озвучки, число оригинальных схем, длина клипов без пояснений, фото-слайдшоу). Стартовые пороги это мои догадки, их нужно подстроить после ручного просмотра, это не правила YouTube.
6. **Сверка кадра по метаданным архива** (ID, дата, описание) раньше VLM, потому что модель не определит конкретный самолёт.
7. **Правила доказательств:** первичные документы в приоритете, числа и даты подтверждаются двумя независимыми источниками.
8. **`qa_report.json`** как обязательный выход стадии QA (известный пробел из вашего скриншота).

**Порядок вех** (каждая это одна сессия): A проверка реальности + спецификация профиля → B проба кадров через API → C адаптеры и реестр политик → D гейты и `qa_report` → E срез 30-60 с → F пилот 6-10 мин.

## Промпт A (запускать первым)

```text
MILESTONE A — reality check + niche profile spec. Docs only. No code changes, no installs, no model runs, no process/lock changes. Time-box 25 min. Max 2 attempts per blocker, then record it and continue.

NICHE (decided): "Aviation & spaceflight test history" on free/public-domain archive footage. The niche must be CONFIG, not hardcoded.

1. Preflight (look only): pwd, git status --short --branch, HEAD, running processes, .kilo lock. Preserve user changes.
2. Reality check from CODE, not from docs. Output a table:
 a) Registered footage adapters; which are keyless vs need keys.
 b) Any NASA / DVIDS / NARA adapter? (yes/no, path)
 c) Does asset_record (or equivalent schema) have: license, attribution, sha256, in/out, storage_policy? List missing vs: archive_id, archive_caption, archive_date, identifiable_persons, logo_visible, third_party_copyright, credit_required.
 d) Where is per-provider storage/rights policy defined, if anywhere?
 e) Does any QA gate measure original-content share of the timeline? (yes/no, path)
 f) Does the QA stage write qa_report.json? (known gap: no)
3. Create docs/openmontage/NICHE_PROFILE_SPEC.md (spec only, no implementation): schema of niche_profile.yaml with fields:
 - allowed_sources + per-source storage_policy (query_only | per_project_asset | temporary_cache | needs_permission)
 - excluded_content (fatalities, graphic crash footage, identifiable private persons without clearance)
 - required_primary_doc_types (NASA NTRS, FAA, NTSB)
 - viability_gate: min_licensed_video_clips=10, min_primary_docs=3, configurable
 - added_value_gate (INITIAL GUESSES to tune after human review, NOT YouTube thresholds): narration on >=90% of runtime; >=1 original diagram/chart per 90 s; no unannotated archive clip >20 s; still-image-only sequence <=15 s; every claim has an on-screen source card or credits entry
 - episode_templates: >=3 distinct structures to avoid a templated feel
4. Create docs/openmontage/NICHE_DECISION.md: decision; rejected niches with reasons (infrastructure: rejected by owner; business/finance: weak footage + YouTube AI-persona rule; celebrities: rights/defamation); UNKNOWNS (competition not measured; monetization eligibility for creator's country not verified; RPM only third-party estimates).
5. Append a v3.1 entry to the master plan changelog (do not overwrite anything).
6. Update checkpoint/work log: observed vs assumed. Commit docs only. Push the current branch to origin without force if a remote is configured; report the real result.

Report format: the reality-check table, list of created files, one exact next action.
Never claim a test/commit/push you did not observe.
```

## Промпт B (после A)

```text
MILESTONE B — topic viability probe. Repo is read-only except one report file. Use a throwaway script in /tmp only. Free keyless APIs only: NASA Image and Video Library (images-api.nasa.gov), Internet Archive advanced search, Wikimedia Commons API. If an API needs a key or registration, mark BLOCKED — do not register, create accounts, or use paid routes.
Topics: (1) Boeing 720 Controlled Impact Demonstration 1984, (2) Lunar Landing Research Vehicle, (3) Space Shuttle landing tests at Edwards.
For each topic run 3–5 differently worded queries. Count VIDEO items separately from stills. For each video: id, URL, title, date, creator, rights statement, duration if available. Flag: identifiable persons, NASA logo, third-party credit, fatalities/crash with casualties.
Treat ERROR, 429 and EMPTY as separate states; never report an error as zero results or success.
Find >=3 candidate primary documents per topic (NASA NTRS, FAA, NTSB) with exact URLs. Do not state any fact about the topics from memory.
Verdict per topic using viability_gate from NICHE_PROFILE_SPEC.md: GO / NO-GO with exact gaps.
Save docs/openmontage/audit/VIABILITY_PROBE_<date>.md with the tables, delete the /tmp script after saving its output, commit the report only.
Never claim a command or commit you did not observe.
```

**Оговорка:** API NASA должен работать без ключа, но я не проверял это в песочнице. Если потребуется ключ, агент честно пометит BLOCKED, и тогда решим вместе, регистрировать ли бесплатный ключ.

Пришлите вывод агента после A или B.

---

## [24] ВЫ · 2026-10-16 09:46 UTC
Хорошо но ещё одна задача изучи все этапы работы по типу монтаж озвучка поиск футажей найди репозиторий в гитхабе или проекты которые помогают делать легче и качественнее и быстрее ultra thinking и ещё скилы полированные под Ютуб и для кодинга для фабрики

---

## [25] CLAUDE · 2026-10-16 09:48 UTC
Начинаю глубокое исследование по всем этапам. Сначала озвучка, выравнивание субтитров, монтаж и анимированные схемы.

🔎 web_search: best open source text-to-speech models 2026 comparison Kokoro Chatterbox Piper license commercial use English narration

Озвучка проверена, лицензии решают всё. Теперь выравнивание субтитров, монтаж и анимированные схемы.

🔎 web_search: WhisperX OR stable-ts OR "Montreal Forced Aligner" forced alignment word-level timestamps subtitles license comparison

Теперь монтаж и анимированные схемы (нужны для гейта «добавленная ценность»).

🔎 web_search: programmatic video open source MIT license Revideo Motion Canvas Manim Remotion license company comparison 2026

Теперь смотрю, что уже есть в самом OpenMontage, чтобы не дублировать, и ищу инструменты по поиску архивных кадров.

🔎 web_fetch: https://github.com/calesthio/OpenMontage

🔎 web_search: calesthio OpenMontage GitHub tools footage sources Remotion HyperFrames pipelines skills

🔎 web_search: Kilo Code agent skills SKILL.md support .kilo/skills install docs

🔎 web_search: obra superpowers skills test-driven-development systematic-debugging verification-before-completion SKILL.md license

🔎 web_search: Jakeschincariol youtube-agent-skill yt-script yt-package yt-chapters license github

Проверяю два допущения из прошлых промптов: нужен ли ключ для NASA Image Library и что с музыкой.

🔎 web_search: NASA Image and Video Library API images-api.nasa.gov search endpoint no API key required rate limit

🔎 web_search: free CC0 public domain background music for YouTube documentaries FreePD Free Music Archive Content ID claims risk

Провёл исследование по всем этапам. Главная находка меняет часть моих прошлых допущений.

## Находка: OpenMontage уже умеет многое из нужного

Судя по README, проект уже включает архивные источники Archive.org, NASA и Wikimedia Commons. Там же заявлены Piper TTS для офлайн-озвучки, Remotion и HyperFrames для композиции, FFmpeg для кодирования. Значит, адаптеры NASA писать с нуля, скорее всего, не надо: сначала проверить, работают ли они (с учётом issue #511). Число инструментов в разных источниках расходится (52 против 100+), вероятно, из-за разных дат. Пункт «аудит адаптеров» из Milestone A остаётся в силе.

## По этапам

**Озвучка.** Лицензия решает всё.
- Лучший кандидат: Kokoro 82M, лицензия Apache 2.0, а Chatterbox идёт под MIT. Запасной вариант: Chatterbox.
- Избегать: XTTS v2 (CPML, только некоммерческое), веса F5-TTS (CC-BY-NC), открытый Fish Speech (CC-BY-NC-SA), а также Voxtral (CC BY-NC).
- Противоречие по Piper (он стоит в OpenMontage по умолчанию): один источник указывает GPL-3.0 для движка и отдельную лицензию у каждого голоса, другой называет MIT. Лицензию конкретного голоса, который использует пилот, нужно проверить, пока не верить ни тому ни другому.

**Выравнивание субтитров.** У нас текст известен заранее, поэтому нужен forced alignment, а не распознавание. stable-ts выпущен под MIT, этот вариант проще. WhisperX даёт точность слов до 100 мс через wav2vec2, но он тяжелее (модель выравнивания ~360 МБ), а лицензию (в одном гайде Apache 2.0) нужно проверить в самом репозитории.

**Монтаж и анимированные схемы** (нужны для гейта «добавленная ценность»).
- HyperFrames и Motion Canvas/Revideo без платных лицензий: HyperFrames Apache-2.0, Motion Canvas и Revideo MIT.
- Remotion нужно держать в уме: это source-available, а не open source, платный тариф $25 за место действует свыше трёх человек. Триггер это размер коммерческой организации (4+ человека). Пока вы один, это не проблема, но при расширении команды проверить заново. Можно зафиксировать HyperFrames в `render_runtime`.
- Для схем в стиле 3Blue1Brown есть плагин Manim, лицензию я не проверял.

**Поиск кадров.** NASA Image and Video Library работает без ключа и содержит свыше 140 000 материалов. Подтверждение пока из сторонних описаний, официальную документацию я не открывал. Использовать API напрямую, а не через Apify-обёртки.

**Музыка.** По-хорошему в пилоте обойтись без неё. YouTube Audio Library безопаснее всего, а треки с пометкой «бесплатно» всё равно могут получить Content ID-претензию. Если брать другое, сохранять доказательство лицензии.

## Скилы

**Для YouTube: Jakeschincariol/youtube-agent-skill.** Существует, в нём 11 навыков и набор Python-линтеров (hookscore, title, chapters, retention). Брать `yt-script` (с привязкой к `claim_id`), `yt-package`, `yt-chapters`, `yt-seo`. Аудит безопасности от Socket относится к соседнему пути репозитория (`chatgpt-youtube-agent-skill`), поэтому «Pass» там не про наш пакет, читать скрипты самим.

**Для кода: obra/superpowers (MIT).** Нужны три навыка: test-driven-development, systematic-debugging, verification-before-completion. Они напрямую реализуют правила нашего плана («сначала тест», «не говори, что прошло, без проверки»). Ставить только их, а не весь фреймворк. В выдаче много форков, брать оригинал и зафиксировать commit.

**Как Kilo их читает:** проектные навыки лежат в `.kilo/skills/`, имя навыка должно совпадать с именем папки, `.claude/skills/` подхватывается в режиме совместимости. Более старая документация называет `.kilocode/skills/`, поэтому путь сверить с установленной версией.

**Не ставить:**
- everything-kilo-code: 136 навыков и 30 агентов, нарушает принцип минимума из мастер-плана.
- 81 навык из самого OpenMontage через `skills add`: они уже в репозитории, а среди них есть платные (ElevenLabs, HeyGen) и скачивание с YouTube. Скачивание чужих видео создаёт риск по политике reused content.
- Apify-актёры, XTTS, F5-TTS.

## Что не проверено
- Работоспособность адаптеров NASA/Archive.org/Wikimedia сейчас.
- Лицензия Piper-голоса, WhisperX, Manim.
- Реальное качество Kokoro на вашем железе.
- Всё из сторонних статей я воспринимаю как оценку, а не факт.

## Промпт для Kilo (Milestone S: аудит инструментов, без установки лишнего)

```text
MILESTONE S — tooling audit + minimal skill install. One session, max 25 min. No paid routes, no model downloads, no process/lock changes.
1. Preflight (look only): git status --short --branch, HEAD, processes, .kilo lock. Preserve user changes.
2. From CODE/CONFIG, report per stage which tool the last pilot actually used: TTS (which engine+voice), subtitle alignment, render_runtime (Remotion or HyperFrames), footage adapters, music. List exact paths/versions.
3. License check, from the repo's own LICENSE/README files: the Piper voice used (voice license), the render engine, and any model weights. Mark UNKNOWN if not stated. Do not rely on blog posts.
4. Do NOT install the full 81-skill OpenMontage pack, everything-kilo-code, or any skill that uses paid APIs (ElevenLabs/HeyGen) or downloads third-party YouTube videos.
5. Skills to install (project level, in the path the INSTALLED Kilo version documents; skill name must equal its folder name): from obra/superpowers (canonical repo, pin commit): test-driven-development, systematic-debugging, verification-before-completion. From Jakeschincariol/youtube-agent-skill: yt-script, yt-package, yt-chapters, yt-seo, plus their Python tools. Before installing, read every SKILL.md and script: report network calls, file writes, env vars, secrets. Do not install if anything is suspicious. Record source URL, commit hash, license.
6. Adapt yt-script locally: every factual sentence must reference a real claim_id from the evidence ledger; hook scores are heuristics, not forecasts.
7. Write docs/openmontage/TOOLING_DECISIONS.md: per stage -> chosen tool, license, cost ($0 check), unknowns, rollback. Update checkpoint/work log (observed vs assumed). Commit docs and skills only. Push without force if a remote is configured; report the real result.
Never claim a test, install, commit or push you did not observe.
```

Когда придёт вывод агента, пришлю дальше Milestone B с учётом уже существующих адаптеров.

---

## [26] ВЫ · 2026-10-16 10:32 UTC
И остальные этапи тоже продумай и ещё про футажи есть репозиторий который даёт доступ к многим футажам найди его название я уже забыл

---

## [27] CLAUDE · 2026-10-16 10:32 UTC
Ищу репозиторий с доступом к множеству футажей и сразу проверяю источники для остальных этапов.

🔎 web_search: GitHub open source stock footage search aggregator MCP Pexels Pixabay Archive.org Wikimedia NASA free video search tool

🔎 web_search: bazodev open-vids OpenVids GitHub desktop video editor asset search license

🔎 web_search: NASA Technical Reports Server NTRS API search public documents free no key; NTSB CAROL database aviation investigation reports API access

🔎 web_search: YouTube Data API videos.insert upload quota 1600 units unverified API project videos restricted private audit requirement

---

## [28] ВЫ · 2026-10-17 01:39 UTC
Continue

---

## [29] CLAUDE · 2026-10-17 01:39 UTC
## Забытый репозиторий: скорее всего один из этих трёх

**1. OpenVids (`bazodev/open-vids`).** Мой главный кандидат. Это открытый десктопный редактор под Apache-2.0, где агент-исследователь импортирует чужие материалы из разрешённых источников и сохраняет происхождение, автора и лицензию каждого файла. Список источников большой: NASA Scientific Visualization Studio, музейные коллекции (Met, Art Institute of Chicago, Cleveland, SMK), Wellcome, Smithsonian Open Access, Pexels, Pixabay, Flickr, Freesound, ccMixter. Ограничение: сборки только для macOS и Windows, в Codespace он не запустится. Брать из него идею схемы лицензий и список источников, а не само приложение.

**2. Сам OpenMontage.** Его конвейер документального монтажа строит индексируемый через CLIP корпус из Pexels, Archive.org, NASA, Wikimedia и Unsplash. Если вы имели в виду этот поиск, то он у нас уже есть.

**3. Библиотека `illustration` (PyPI).** Единый поиск по нескольким провайдерам с лицензиями в схеме, но для изображений, Wikimedia и Openverse без ключа, Pexels и Pixabay с ключом.

Остальные найденные (StockFinder AI, stock-images-mcp) работают только с Pexels и картинками, нам не подходят. Скажите, что из этого похоже, и я уточню.

## Остальные этапы фабрики

**Первичные документы.** Основной источник это NASA Technical Reports Server: он объединяет коллекцию NACA (1915-1958) и документы NASA с 1958 года, включая изображения и видео. Сторонние описания утверждают, что его публичный API работает без аутентификации, но это нужно проверить пробой. NTSB CAROL нам почти не нужен: там данные по авиационным расследованиям с 2008 года, а наши темы это испытания 1960-80-х.

**Публикация.** Важное ограничение: видео, загруженные через API из непроверенных проектов Google, созданных после 28 июля 2020, ограничены приватным режимом до прохождения аудита. Стоимость загрузки в квотах источники указывают по-разному (100 против 1600 единиц), так что на неё не опираемся. Вывод: **публиковать вручную через YouTube Studio**, а API использовать, если вообще, только для приватного черновика. Это совпадает с гейтом человеческого одобрения и с аккаунтом родителя.

| Этап | Решение |
|---|---|
| Тема | вручную, по критериям жизнеспособности |
| Доказательства | NTRS + правила research-discipline (два источника на цифры и даты) |
| Сценарий | yt-script с обязательным `claim_id` на каждое утверждение |
| Раскадровка | проверка ID по реестру доказательств (закрывает баг `f1/f2`) |
| Кадры | адаптеры OpenMontage + сверка с метаданными архива |
| Озвучка / субтитры | Kokoro, stable-ts |
| Монтаж | HyperFrames, оригинальные схемы |
| QA | гейт «добавленная ценность», ffprobe, громкость, `qa_report.json` |
| Упаковка | yt-package, yt-chapters; обложка собственной графикой без логотипа NASA и без людей (инструмент не исследован) |
| Загрузка | вручную в Studio, с пометкой синтетического контента, если применимо |
| Аналитика | выгрузка из Studio и retention-линтер из youtube-agent-skill |

**Не исследовано:** генерация обложек и инструменты фактчекинга. Для обложки пока хватит HTML-в-PNG через рендерер.

## Дополнение к Milestone S для агента

```text
ADDENDUM to Milestone S (same rules: read-only first, no paid routes, no process/lock changes).
1. Add to docs/openmontage/TOOLING_DECISIONS.md a row per remaining stage: primary-document research, claim ledger, storyboard ID validation, packaging (title/description/chapters/thumbnail), upload, analytics review. For each: existing tool in repo (path) or MISSING, license, $0 check, unknown.
2. Check whether the repo has an NTRS (NASA Technical Reports Server) client. If missing, DO NOT write one now; just record it as a Milestone B probe item: test the public NTRS API without a key, record status codes, rate limits, and the document fields available (id, title, center, date, PDF URL). Treat any failure as ERROR, not as zero results.
3. Record the upload decision: manual publish in YouTube Studio; API upload only as private draft later (unverified API projects are forced private). No OAuth setup, no credentials requests.
4. Reference-only: read the OpenVids (bazodev/open-vids, Apache-2.0) license-record schema and trusted-source list if reachable; summarize the fields worth copying into our asset_record. Do not copy code, do not install the app.
5. Commit docs only; push without force if a remote exists; report the real result. Never claim a command you did not observe.
```

Дальше после вывода агента выпускаю Milestone B с пробой NTRS и кадров NASA.

---

## [30] ВЫ · 2026-10-17 01:40 UTC
_(без текста)_
_Вложения: Screenshot_20261016_162314.jpg, Screenshot_20261016_161513.jpg, Screenshot_20261016_162319.jpg_

---

## [31] CLAUDE · 2026-10-17 01:40 UTC
## Что показали отчёты агента

**Milestone B: NO-GO по всем трём темам, но причина узкая.** Видео есть, а вот поле «права» в метаданных NASA API и Internet Archive отсутствует вовсе. Первичные документы проходят (NTRS без ключа работает, PDF подтверждены), блокирует только лицензионная часть.

| Тема | Видео | С явной лицензией | Вывод |
|---|---|---|---|
| Boeing 720 (1984) | 13 | 1 | не хватает 9 клипов |
| LLRV | 2 | 0 | тему **отбрасываем**: кадров нет |
| Шаттл/Edwards | 22 | 5 | не хватает 5, но тема самая близкая |

**Мой промах:** я считал, что API отдаёт поля прав, а наш гейт требовал «явную лицензию на каждом клипе». Для материалов NASA это слишком строго: права там определяются **политикой источника** (как мы смотрели ранее, обычно не защищены авторским правом, с исключениями для логотипов, людей и чужих материалов), а не полем на каждом файле. Исключения всё равно нужно ловить, поэтому слепо верить нельзя.

**Milestone S выполнен и закоммичен (ff35182, пуш прошёл).** Важное для нас:
- Озвучка пилота шла на **Piper, голос en_US-lessac-medium**. Лицензия голоса, движка и весов **UNKNOWN**, голос заявлен как CC-BY-4.0 только в манифесте. До решения вопроса публиковать видео с этим голосом нельзя.
- Субтитры шли на запасном режиме по сегментам (пословные метки пропущены). Нужен stable-ts.
- Рендер на **ffmpeg**, а HyperFrames «доступен, но не выбран». Для оригинальных схем (гейт «добавленная ценность») нужен именно HyperFrames.
- Сам OpenMontage под **AGPL-3.0**: для личного использования не проблема, но запомнить.
- Агент нашёл и починил до установки реальный баг: `yt-chapters` импортировал парсер из не установленного соседнего навыка.
- Семь скилов установлены в `.kilo/skills/`. Следующий шаг агента верный: проверить в живой сессии Kilo, что он их видит.

## Решение

Идём по варианту (a): уточнить модель прав и перепроверить клипы. Только с жёсткой защитой: неизвестное = не используем.

**Milestone C1 (документы и разметка, без кода):**

```text
MILESTONE C1 — rights model + clip re-classification + replacement topic probe. Docs/reports only: no code changes, no installs, no process/lock changes. Time-box 30 min. Free keyless APIs only; BLOCKED if a key/registration is needed. Treat ERROR/429/EMPTY as separate states, never as zero results.

1. Preflight (look only): git status, HEAD, processes. Preserve user changes.
2. Fetch the OFFICIAL NASA media usage guidelines page. Record the URL, access date, and a short paraphrase of: default copyright status, exceptions (logos/insignia, identifiable persons, third-party material, other). Do not rely on blog posts.
3. Write docs/openmontage/RIGHTS_MODEL.md. Define rights_basis = explicit_license | source_policy_us_gov | unknown. Rules (fail-closed):
 - source_policy_us_gov allowed only if: item is NASA-produced/NASA-center material per its own metadata; no third-party/"courtesy of"/copyright notice in credit/description fields; no per-item restriction text.
 - Flags: third_party_credit, logo_visible (unknown unless reviewed), identifiable_persons (unknown unless reviewed). Items with unreviewed flags count as NEEDS_REVIEW, not usable.
 - unknown => not usable. Record confidence (high/medium/low) and the exact metadata fields used as evidence.
4. Re-classify the clips from VIABILITY_PROBE_2026-10-16.md (11 NIX NASA-center clips for topic 1, 13 NASA-API clips for topic 3, plus the explicitly licensed ones). Table: asset_id, URL, rights_basis, flags found in metadata, verdict (USABLE / NEEDS_REVIEW / REJECT) and why. Do not look at pixels; metadata only.
5. For topic 3 (Shuttle landing tests): check from each clip's title/description whether it really shows Approach and Landing Tests/Edwards landings, or only launches/other ALT-era events. Mark unverified when vague. Do not state topic facts from memory.
6. Topic 2 (LLRV): retry with >=3 differently worded queries, including historical center names (e.g., Dryden, Flight Research Center) and ID-based searches. Confirm or revise the video count.
7. Probe 3 replacement candidates with the same method and the same states: X-15 research flights, XB-70 research flights, Helios prototype. Counts of video, rights_basis, primary docs from NTRS (exact URLs).
8. Recompute the viability gate using the new definition (usable video clips = rights_basis in explicit_license/source_policy_us_gov AND no unreviewed flags; NEEDS_REVIEW listed separately). Verdict per topic with exact gaps.
9. Update the existing checkpoint/work log (observed vs assumed). Commit docs only. Push without force; report the real result.
Never claim a command, commit or push you did not observe.
```

## Что дальше (после C1)

- **C2 (код, по TDD):** поля прав в `asset_record`, функция гейта жизнеспособности и тесты на реальных данных пробы.
- **D:** выбор озвучки и субтитров (проверка лицензии голоса, Kokoro против Piper, stable-ts), HyperFrames для схем.
- **E:** срез на 30-60 секунд, потом пилот.

Пришлите отчёт агента, когда C1 завершится.

---

## [32] ВЫ · 2026-10-17 01:44 UTC
В первую очередь нужно собрать и улутчить агента и инструменты фабрики по типу озвучки,монтажа и фонового звука и найди репозиторий где агент делает прекрасный монтаж с задним фоновым музыкой и ТД

---

## [33] CLAUDE · 2026-10-17 01:45 UTC
Ищу репозитории, где агент реально монтирует с музыкой и звуком, и инструменты для звукового микса.

🔎 web_search: open source AI agent video editor background music ducking sound design beat sync Claude Code skill GitHub

🔎 web_fetch: https://github.com/rugelees/video-agent

🔎 web_search: ffmpeg sidechaincompress music ducking under voice-over loudnorm two-pass YouTube loudness normalization -14 LUFS true peak documentary mix

## Репозиторий, который вы искали: `agamm/video-agent`

Ближе всего к «агент делает хороший монтаж». Наткнулся на его форк (rugelees), ставить нужно оригинал. Что в нём подходит нам:
- Лицензия MIT. Ядро полностью локальное, без API-ключей, на 21 покадровой команде ffmpeg.
- Результат это проверяемый список монтажа (EDL), где у каждого клипа написана причина, почему он тут и такой длины.
- Режим `--report` критикует ритм: одинаковая длина планов, склейки картинки и звука на одном кадре, паузы одной длины. Это идея для нашего QA-гейта.
- 12 скиллов, среди них `editor` (режим документального жанра), `cutting-rhythm`, `audio-edit` (нормализация громкости, музыка под речью), `video-transitions`.

**Ограничения (важно):**
- `transcribe` работает только на Apple Silicon через mlx-whisper, в нашем Codespace это не заработает. Нужен stable-ts.
- Команда `yt-dl` скачивает чужие видео. Использовать нельзя (политика reused content и права).
- На Linux нужно поменять кодек на libx264, а в их ffmpeg-сборке нет drawtext (текст рендерится через PIL).
- Часть Remotion там требует платной лицензии.

**Что берём:** не весь репозиторий, а подход: EDL с обоснованием каждой склейки, линтер ритма, три скилла (`cutting-rhythm`, `edl-edit`, `audio-edit`). Остальное пропускаем.

## Другие находки по звуку и монтажу

- **howseen-ai/claude-motion-design:** без Remotion, HTML + Playwright + ffmpeg; находит «дроп» музыки по энергии полос, ставит эффекты по измеренному пику, делает двухпроходную нормализацию. Брать как методологию.
- **saeedvaziry/caleb-video-editor:** определяет биты, такты и фразы, привязывает склейки; опциональная генерация музыки ACE-Step (MIT), но модель звуковых эффектов под Stability AI Community License. Тяжёлый, нужен GPU, на потом.
- **bestagentkits/motion-video-skill:** озвучку, музыку и эффекты генерирует через ваши аккаунты провайдеров, значит это платные маршруты. Можно прочитать только документ про звук, не ставить.
- **video-shotcraft:** хорошие материалы по звуковому дизайну, но заточен под промо-ролики. Музыка в нём с Mixkit по их бесплатной коммерческой лицензии. Content ID-претензии это не исключает.

## Звуковая цепочка для нас

Стартовая схема: **голос главный, музыка тихая подложка, один финальный проход громкости.**
1. Музыка автоматически приглушается под голосом (sidechain-компрессия в ffmpeg). Параметры из примера (порог 0.015, ratio 6, attack 200, release 1000) это отправная точка, настраивать на слух.
2. Двухпроходная нормализация. Ориентир: -14 LUFS и пик -1.0 dBTP, причём YouTube только понижает громкость слишком громких роликов, а тихие не поднимает. Источники расходятся (в одном гайде заявлено -16 как «стандарт»), так что -14 это рабочее допущение, а не закон.
3. Музыка в пилоте: **без неё**, пока нет файла лицензии. Если брать, то из YouTube Audio Library или с лицензией, сохранённой в записи (источник, текст лицензии, автор, дата, sha256).

Сам по себе «красивый монтаж» это решения о ритме: резать по границам фраз закадрового текста, чередовать длину планов, пускать звук с опережением картинки. Для архивных кадров под озвучку это важнее битов.

## Промпт для Kilo (Milestone D1)

```text
MILESTONE D1 — audio + editing toolchain: audit, decision, minimal install. Time-box 40 min. Allowed: docs, skills into .kilo/skills, throwaway scripts in /tmp. No paid routes, no keys, no process/lock changes. Max 2 attempts per blocker, then record BLOCKED.
1. Preflight (look only): git status, HEAD, processes. Preserve user changes.
2. Capability probe (observed): ffmpeg filters present (sidechaincompress, loudnorm, acrossfade, xfade, amix, alimiter, ebur128); python libs installed (pip list only).
3. Voice licenses from each repo's OWN LICENSE/model-card files (not blogs): Kokoro (code+weights), Piper voice en_US-lessac-medium (voice/dataset license), Chatterbox. Table: engine, code license, weights/voice license, commercial use, evidence path/URL, UNKNOWN where unstated. For ALLOWED candidates only, synthesize the same 60 s script on CPU; report real-time factor; save samples in /tmp; note "needs human listening". Do not claim quality.
4. Alignment: test stable-ts forced alignment (known text + audio). Report word-timestamp coverage vs the current segment fallback. If install fails, BLOCKED.
5. Audio finishing prototype in /tmp: voice + synthetic test-tone music bed (no downloaded music) -> sidechaincompress -> two-pass loudnorm (starting values I=-14, TP=-1.5, LRA=11) -> verify with ebur128: report measured integrated LUFS and true peak.
6. Editing doctrine: read upstream agamm/video-agent (MIT; the fork rugelees/video-agent is only a copy), pin commit. Read SKILL.md of editor, edl-edit, cutting-rhythm, audio-edit, video-transitions, captions, and any script: report network calls, env vars, writes. Do NOT install the repo; do NOT use yt-dl, vfx-edit or Remotion parts. Write docs/openmontage/EDITING_DOCTRINE.md: rules to port (EDL with per-cut rationale; pacing lint: shot-length variation, split edits/J-L cuts, pause lengths) mapped to OUR real timeline schema path; thresholds marked INITIAL GUESSES to tune after human review. Install only cutting-rhythm, edl-edit, audio-edit into .kilo/skills, adapted for Linux (no mlx-whisper, libx264), commit pinned.
7. Write docs/openmontage/MUSIC_POLICY.md: pilot uses NO music unless license evidence is stored; allowed sources; required record fields (source URL, license text, author, download date, sha256); Content ID risk noted as UNKNOWN.
8. Update TOOLING_DECISIONS.md and the checkpoint/work log (observed vs assumed). Commit; push without force; report real result.
Never claim a test, install, commit or push you did not observe.
```

Параллельно остаётся Milestone C1 (права на клипы NASA). Какой запускаем первым, решите сами: C1 даёт пилотную тему, D1 даёт качество монтажа и звука.

---

## [34] ВЫ · 2026-10-17 02:02 UTC
Давай так поработаем нужно сделать фабрику где максимум 2-3 репозитория который будет делать видео для Ютуба, а ты ищи весь гитхаб и найди такие репозиторий возможно это скилы или типо того для агента но всё равно мне, главное чтобы сделал качественный видео быстро и потом мозговой штурм и меняем мастер план немножко и по мастер плану строим фабрику ultra thinking

---

## [35] CLAUDE · 2026-10-17 02:03 UTC
Начинаю глубокий поиск по GitHub: ищу репозитории, которые могут быть ядром фабрики.

🔎 web_search: GitHub open source agent video production long-form YouTube documentary pipeline script narration footage edit render skills stars 2026

OpenMontage подтверждается как база. Теперь ищу второй и третий кандидаты: рендер/графика и «режиссёр» монтажа.

🔎 web_search: HyperFrames HTML to video open source Apache-2.0 GitHub agent skills render deterministic heygen

🔎 web_search: browser-use video-use GitHub edit videos with Claude Code transcription ElevenLabs Scribe requirements license

Читаю заново мастер-план v3, чтобы предлагать конкретные правки, а не общие.

🔎 bash_tool: cd /mnt/user-data/uploads && grep -n '^#' OPENMONTAGE_FACTORY_MASTER_PLAN_RU_v3.md | head -80; wc -l OPENMONTAGE_FACTORY_MASTER_PLAN_RU_v3.md

🔎 bash_tool: cd /mnt/user-data/uploads && sed -n 1,16p OPENMONTAGE_FACTORY_MASTER_PLAN_RU_v3.md; echo ------; sed -n 144,190p OPENMONTAGE_FACTORY_MASTER_PLAN_RU_v3.md; echo ------; sed -n 222,300p OPENMONTAGE_FACTORY_MASTER_PLAN_RU_v3.md

## Итог поиска: стек из трёх

Охватить весь GitHub невозможно, поэтому скажу прямо: я прогнал около десятка поисков и прочитал README самых вероятных кандидатов. Более сильной альтернативы для нашей задачи не нашёл.

| Роль | Что берём | Лицензия |
|---|---|---|
| Платформа (поиск кадров, пайплайн, этапы) | **OpenMontage** | AGPL-3.0 |
| Рендер, оригинальная графика, схемы, субтитры | **HyperFrames** (heygen-com) | Apache-2.0 |
| Голос | **Kokoro-82M** (модель, не репозиторий) | Apache-2.0 (по описаниям, проверка в D1) |

Всё остальное это **закреплённые файлы-инструкции (скиллы), а не репозитории**: три из superpowers, четыре из youtube-agent-skill, три из video-agent.

**Почему именно они:**
- OpenMontage умеет делать «настоящее видео» из бесплатных архивов (NASA, Archive.org, Wikimedia), а не только картинки с анимацией, и ведёт процесс research → proposal → script → scene_plan → assets → edit → compose. Зрелость средняя: 40 открытых issue, 70 открытых PR, релизов на GitHub нет, поэтому обязательно закреплять commit. Число звёзд источники называют разное (от 24K до 44K), на него не опираемся.
- HyperFrames: детерминированный рендер (одни входные данные дают одни кадры), лицензия Apache 2.0 без платежей за рендер, и в отличие от Remotion Remotion это source-available, а не open source. У него есть CLI с `lint`, `preview`, `render`, `transcribe`, `tts`, `doctor`.

**Отвергнуто и почему:**
- video-use (browser-use): требует платный ключ ElevenLabs, и лицензия явно не указана.
- OpenVids: только macOS и Windows.
- ViMax и подобные: мультиагентный генератор, нам нужны реальные архивные кадры, а не генерация.
- Остальное из прошлых поисков (motion-video-skill через платных провайдеров, Remotion-навыки): нарушают режим $0 или лицензию.

## Мозговой штурм: что меняем в мастер-плане

1. **Ниша.** Бизнес-документалка заменяется историей испытаний авиации и космоса. Это затрагивает сессию 3 и критерии темы.
2. **Модель прав.** Вместо «явная лицензия на каждом клипе» вводим `rights_basis`: явная лицензия, политика источника (материалы правительства США) или неизвестно. Неизвестное равно «не использовать». Это закрывает то, на чём упал Milestone B.
3. **Гейт «тема жизнеспособна» перед сценарием:** хватает ли лицензированных видеоклипов и первичных документов. Плюс **сценарий пишется с учётом того, какие кадры реально есть.** Это новое: раньше сценарий жил отдельно и потом ломался на «нет подходящего футажа».
4. **Новый блокирующий гейт «добавленная ценность»** (политика YouTube против reused content): оригинальный закадровый текст, оригинальные схемы, источники на экране, без фото-слайдшоу.
5. **Рендер в два слоя.** Основа остаётся на ffmpeg (проверено пилотом). HyperFrames добавляем только для оригинальной графики (схемы, карточки источников) как накладываемые слои. Полный переход на HyperFrames отложить, пока не докажем стабильность.
6. **Голос:** лицензия Piper-голоса UNKNOWN, значит блокер. Выбор между Kokoro и Piper по итогам D1.
7. **Скорость без потери качества.** Не оптимизируем вслепую: сначала измеряем время и ресурсы каждой стадии. Но закладываем: черновой рендер в низком разрешении для проверки, переиспользование успешных стадий (idempotent), озвучка по абзацам, проверка человеком по контакт-листу, а не просмотром всего ролика.
8. **Монтаж:** EDL с причиной каждой склейки и линтер ритма как QA-проверка.
9. **Публикация только вручную.** API-загрузка из непроверенного проекта Google даёт приватные видео, а аккаунт родителя для AdSense остаётся отдельным организационным вопросом.
10. **Правило стека:** новый репозиторий в рантайме добавляется только с вашего согласия, максимум три.
11. **Ноль секретов в первой версии.** Всё работает без ключей, чтобы не упираться в ручные шаги, которые вы откладываете.

## Порядок вех

**P** (правка плана) → **C1** (права на клипы, замена тем) → **D1** (голос, звук, доктрина монтажа) → **E** (срез 30-60 с) → **F** (пилот 6-10 мин).

## Промпт для Kilo: Milestone P (только документы)

```text
MILESTONE P — master plan revision v3.2. Docs only: no code changes, no installs, no network calls except reading. Time-box 20 min. No process/lock changes.
1. Preflight (look only): git status, HEAD. Preserve user changes. Locate the existing master plan file(s) and the docs/openmontage/ files created in Milestones A, B, S.
2. Do NOT delete old text. Append a v3.2 changelog entry (date 2026-10-16) and mark superseded passages with "SUPERSEDED by v3.2: <reason>".
3. Update these plan sections:
 - Niche: aviation & spaceflight test history on free/public-domain archive footage (replaces business documentary). Link NICHE_DECISION.md.
 - Runtime stack: max 3 repos/engines = OpenMontage (platform, AGPL-3.0), HyperFrames (render/graphics, Apache-2.0), Kokoro-82M model (voice, license to be verified from its own files). Everything else is pinned SKILL files or reference-only (AI Video Factory, faceless-video-pipeline: patterns only, no code copied). Adding a 4th runtime repo requires owner approval.
 - asset_record: add rights_basis (explicit_license | source_policy_us_gov | unknown), identifiable_persons, logo_visible, third_party_credit, archive_id, archive_caption. unknown => not usable.
 - New stage 0 "topic viability gate" (>=10 usable licensed video clips, >=3 primary docs) and "footage-aware scripting": storyboard consults the asset inventory before narration is finalized; slots without valid assets must be rewritten or BLOCKED.
 - Go/No-Go: add hard gate "added value" (original narration/analysis, original diagrams/source cards, no still-image-only sequence beyond a configurable limit; YouTube reused-content policy applies even to public-domain footage), and gate "voice license known".
 - Render: ffmpeg stays the base assembler; HyperFrames only for original graphic layers first; full migration only after measured stability.
 - Editing QA: EDL with per-cut rationale + deterministic pacing lint (thresholds are INITIAL GUESSES).
 - Audio: voice-first mix, sidechain ducking, two-pass loudnorm with starting target I=-14, TP=-1.5 (secondary sources; verify and tune).
 - Publishing: manual in YouTube Studio only (unaudited API projects force private uploads). Monetization ownership by guardian is an open owner decision.
 - Speed: record per-stage wall time and resource use in stage_checkpoint; add draft-render mode and contact-sheet review; no premature optimization.
 - Zero-secrets rule for v1 (no API keys required).
4. Update the milestone order: P -> C1 -> D1 -> E (30–60 s slice) -> F (6–10 min pilot). Mark A, B, S as DONE with commit hashes (read from git log, do not guess).
5. List open risks/unknowns (Piper voice license, rights basis for NASA clips, Content ID for music, competition unmeasured, monetization eligibility).
6. Update checkpoint/work log (observed vs assumed). Commit docs only; push without force; report the real result.
Never claim a commit or push you did not observe.
```

После P запускаем C1 (он у вас уже есть выше), затем D1. Отчёты агента присылайте скриншотами, как раньше.

---

## [36] ВЫ · 2026-10-17 02:09 UTC
Улутчи этот промп который дал потому-что я не вижу агента для монтажа видео и проверки и ТД изучи в интернете разные фабрики/заводы по созданию видео и найди самый лучший из бесплатных и возми оттуда самые лучшие примеры инструментов если можно то скопировать фабрику/завод полностью

---

## [37] CLAUDE · 2026-10-17 02:11 UTC
Ищу три вещи: как в Kilo настраиваются свои агенты (монтажёр, проверяющий), какие бесплатные «фабрики» существуют и что у них взять по контролю качества.

🔎 web_search: Kilo Code custom agents subagents markdown frontmatter .kilo/agents permissions read-only reviewer docs

🔎 bash_tool: cd /mnt/user-data/uploads && sed -n 92,143p OPENMONTAGE_FACTORY_MASTER_PLAN_RU_v3.md

🔎 web_search: summitsingh ai-video-factory GitHub fact-check QC pipeline stages tests license

🔎 web_search: ffmpeg automated video QC blackdetect freezedetect silencedetect ebur128 script check rendered video errors subtitle sync

## Почему вы не видите агентов

В Kilo свои агенты это отдельные markdown-файлы. Их кладут в `.kilo/agents/` (или в `~/.config/kilo/agents/`) и вызывают через `@имя`. Мой прошлый промпт (Milestone P) только правил документы, а Milestone S поставил скиллы. Роль `qa-reviewer` есть в мастер-плане, но **ни одного файла агента создано не было**. Монтажёра в плане вообще нет. Это моя недоработка.

## Что я нашёл по другим фабрикам

Скопировать «фабрику целиком» не получится, и это не нужно:
- **OpenMontage остаётся лучшей бесплатной базой** для документалки на реальных кадрах: документальный конвейер режет настоящие кадры из NASA, Archive.org и Wikimedia, а не картинки. Мы её уже клонировали целиком.
- **free-studio-flow** (Apache-2.0): исполнитель плана как граф, где проверки качества работают в режиме fail-closed, а возобновление после сбоя «авторитетное». Но это фабрика генеративного кино через Kaggle, а не архивных кадров. Берём **идею**.
- **youtube-factory-pipeline**: агенты Research, Idea (3 концепции → 1 выбранная), VisualAsset, Guide, Community. Зависит от стороннего LLM-роутера, лицензия в описании не видна. Берём только **схему ролей**.
- Cinef: AGPL и демо без настоящих моделей, пропускаем.

Правило: не копируем целиком чужие фабрики из-за лимита «максимум три репозитория», лицензий и того, что они генеративные.

## Контроль качества: что реально есть бесплатно

Дополнительный репозиторий не нужен. Хватает фильтров самого ffmpeg: blackdetect и freezedetect находят чёрные и замёрзшие кадры, а silencedetect и ebur128 дают тишину и громкость. Хороший принцип из чужой практики: если проверка не смогла запуститься, она проваливается, а не одобряет ролик. Пороги из того же поста (10% тишины, 20% чёрного) это авторские числа, у нас они стартовые догадки.

## Улучшенный промпт (Milestone P+): правка плана, команда агентов и спецификация QA

```text
MILESTONE P+ — master plan v3.2 + REAL Kilo agent team + QA spec. Docs/markdown only: no application code, no installs, no network except reading Kilo docs. Time-box 35 min. No process/lock changes. Preserve user changes.

0. Preflight (look only): git status, HEAD, `kilo --version`. Check what agents exist: run Kilo's agent-listing command (check `kilo agent --help` for the exact subcommand). Record output.

1. Read the INSTALLED Kilo version's docs/help for custom agents. Official model (verify, do not assume): agents are markdown files with YAML frontmatter in .kilo/agents/; frontmatter includes a mode (primary|subagent|all), optional hidden, and permission rules (read/edit/bash/task); invoked by @name; for read-only agents use an explicit deny fallback and allow only trusted commands; use task permissions to limit which subagents an agent may call. Follow whatever schema your version documents.

2. Create these agent files in .kilo/agents/ (mode: subagent unless the version requires otherwise). Keep each prompt short; shared rules stay in AGENTS.md. Every agent: never claim a command/commit/test you did not observe; output status PASS|REVIEW|BLOCKED|FAILED; fail closed (if a check cannot run -> BLOCKED, never PASS).
 a) editor — builds/edits the timeline: EDL JSON with a written rationale per cut, pacing report (shot-length variation, J/L split edits, pause lengths), audio plan (voice-first, sidechain ducking, two-pass loudnorm). Uses installed skills cutting-rhythm, edl-edit, audio-edit. May edit ONLY under projects/**/edit/** and EDL/timeline files; bash allowlist: ffprobe and analysis-only ffmpeg (-f null). No publishing, no downloads, no yt-dl.
 b) qa-reviewer — independent, read-only. Runs/reads hard checks: ffprobe stream facts, full decode, blackdetect, freezedetect, silencedetect, ebur128 (integrated LUFS + true peak), duration vs script, subtitle vs audio sync, credits.txt completeness, every factual sentence has a resolvable claim_id, rights_basis known for every clip, the added-value metrics. May write ONLY qa_report.json and docs/openmontage/audit/**. Bash: explicit deny fallback + allowlist (ffprobe, ffmpeg analysis, python -m json.tool, pytest read-only).
 c) evidence-checker — claims, primary sources (NASA NTRS etc.), contradictions; web read allowed, no shell, no secrets; may edit only the evidence ledger file.
 d) footage-scout — runs the project's own source adapters, classifies each clip with rights_basis (explicit_license | source_policy_us_gov | unknown), flags (identifiable_persons, logo_visible, third_party_credit); unknown => not usable; may edit only asset candidate files.
 e) Orchestrator rule in AGENTS.md: subagent proposes, orchestrator verifies, owner approves publishing; the orchestrator may delegate only to these four (+ existing built-ins). No two agents write the same file.
 After creating, run the listing command again and paste the REAL output: all four must appear. If the version does not isolate permissions, say so and mark the roles as sequential tasks, not isolated agents.

3. Write docs/openmontage/QA_SPEC.md (spec only): list of hard checks with the ffmpeg filters above; qa_report.json schema (job_id, check_id, status, evidence, measured_value, threshold, tool_version, timestamp); thresholds marked INITIAL GUESSES to tune after human review (silence ratio, black ratio, freeze duration, LUFS/true-peak starting target I=-14, TP=-1.5, subtitle drift); added-value metrics. Mapping: which master-plan gate each check enforces. Implementation is a LATER milestone (tests first).

4. Plan v3.2 (do not delete old text; mark "SUPERSEDED by v3.2: <reason>"; append changelog 2026-10-16):
 - Niche: aviation & spaceflight test history on free/public-domain archive footage (link NICHE_DECISION.md).
 - Stack: max 3 runtime repos/engines = OpenMontage (AGPL-3.0), HyperFrames (Apache-2.0, original graphics layers first), Kokoro-82M (model; license verified from its own files). Everything else = pinned skills or pattern-only references. A 4th runtime repo needs owner approval.
 - Patterns adopted: fail-closed QC gates with authoritative resume; EDL with rationale; pacing lint; idea stage: 3 topic concepts -> 1 selected.
 - asset_record: add rights_basis, identifiable_persons, logo_visible, third_party_credit, archive_id, archive_caption; unknown => not usable.
 - New stage 0 topic viability gate (>=10 usable licensed video clips, >=3 primary docs) + footage-aware scripting.
 - Go/No-Go: add "added value" gate and "voice license known" gate.
 - Publishing manual only (unaudited API projects force private).
 - Speed: per-stage wall time/resource logging, draft-render mode, contact-sheet review; no premature optimization.
 - Zero-secrets rule for v1.
 - Milestone order: P+ -> C1 (rights/clips) -> D1 (voice/audio/editing doctrine) -> Q (QC tool with TDD + qa_report.json) -> E (30–60 s slice) -> F (6–10 min pilot). Mark A, B, S done with real hashes from git log.
 - Open risks: Piper voice license, rights basis for NASA clips, Content ID for music, competition unmeasured, monetization eligibility.

5. Update AGENTS.md (roster, permissions summary, rules above) and the checkpoint/work log (observed vs assumed). Commit docs + agent files only; push without force; report the real result.

Report: the pasted agent listing, list of created files, one exact next action.
```

Главное, что вы должны увидеть после запуска: в отчёте будет вставлен **реальный список агентов** с `editor`, `qa-reviewer`, `evidence-checker`, `footage-scout`. Если их там нет, значит агенты не созданы, и это нужно будет разбирать. Сам скрипт проверки ролика (с тестами и `qa_report.json`) идёт отдельной вехой Q.

---

## [38] ВЫ · 2026-10-17 02:47 UTC
_(без текста)_
_Вложения: Screenshot_20261017_074725.jpg_

---

## [39] CLAUDE · 2026-10-17 02:48 UTC
## Что показал отчёт

**Milestone P+ выполнен.** Агенты созданы, и это подтверждено командой, а не словами: `kilo agent list` показал все четыре (`editor`, `evidence-checker`, `footage-scout`, `qa-reviewer`). Коммит `f5099cb` запушен без force, дерево чистое.

В логе виден и коммит `74ee25a` (milestone-d1: аудит звука и монтажа, закреплённые скиллы). Значит D1 тоже выполнен, хотя его отчёт я не видел. Если пришлёте его скриншот, посмотрю решения по голосу (лицензия Piper против Kokoro) и по звуковой цепочке.

**Что пока не доказано:**
- Листинг показывает, что агенты существуют, но **не доказывает, что права изолированы** (что `qa-reviewer` реально не может писать куда попало). Это проверим на живом использовании.
- В статус-баре виден «запрос на вытягивание №804». Проверьте, что это ваш PR в вашем форке, а не что-то ушло в чужой репозиторий. Это мелочь, но лучше убедиться.
- Название ветки всё ещё `business-documentary-pilot`. Это косметика, переименуем позже.

## Дальше: C1 (права на клипы NASA), теперь через агентов

Прошлый промпт C1 я улучшил: теперь он заставляет задействовать новые агенты, чтобы вы видели, как команда работает.

```text
MILESTONE C1 (v2) — rights model + clip re-classification + replacement topic probe, executed THROUGH the Kilo subagents. Docs/reports only: no application code, no installs, no process/lock changes. Time-box 35 min. Free keyless APIs only; BLOCKED if a key/registration is needed. Treat ERROR/429/EMPTY as separate states, never as zero results.

0. Preflight (look only): git status, HEAD, `kilo agent list`. Preserve user changes.
1. Fetch the OFFICIAL NASA media usage guidelines page myself (orchestrator). Record URL, access date, short paraphrase: default copyright status; exceptions (logos/insignia, identifiable persons, third-party material, other).
2. Write docs/openmontage/RIGHTS_MODEL.md: rights_basis = explicit_license | source_policy_us_gov | unknown. Fail-closed rules:
 - source_policy_us_gov only if the item is NASA-produced per its own metadata AND no third-party/"courtesy of"/copyright notice in credit/description AND no per-item restriction text.
 - Flags identifiable_persons, logo_visible stay UNKNOWN unless reviewed; unreviewed => NEEDS_REVIEW, not usable.
 - unknown => not usable. Record confidence and the exact metadata fields used as evidence.
3. DELEGATE to @footage-scout: re-classify the clips from docs/openmontage/audit/VIABILITY_PROBE_2026-10-16.md (11 NIX NASA-center clips for Boeing 720 topic, 13 NASA-API clips for Shuttle topic, plus the explicitly licensed ones). Metadata only, no pixel judging. Table: asset_id, URL, rights_basis, flags found, verdict (USABLE / NEEDS_REVIEW / REJECT) + why. Also: do the Shuttle clips really show Approach and Landing Tests/Edwards, or other ALT-era/launch events (from titles/descriptions only; mark unverified if vague)? Retry LLRV with >=3 differently worded queries, incl. historical center names (Dryden, Flight Research Center) and ID searches.
4. Replacement candidates, also via @footage-scout: X-15 research flights, XB-70 research flights, Helios prototype. Per topic: video count, rights_basis, usable count.
5. DELEGATE to @evidence-checker: >=3 primary documents per topic (NASA NTRS; FAA/NTSB only if relevant) with exact URLs and whether a PDF is retrievable. No topic facts from memory.
6. Recompute the stage 0 viability gate with the new definition (usable = rights_basis in explicit_license/source_policy_us_gov AND no unreviewed flags; NEEDS_REVIEW listed separately). Verdict per topic with exact gaps.
7. DELEGATE to @qa-reviewer (read-only): review the produced report for unsupported claims, counts that do not add up, and any "success" that hides an ERROR. Include its status (PASS/REVIEW/BLOCKED) and findings verbatim.
8. Report which subagent produced what (observed), update checkpoint/work log (observed vs assumed). Commit docs only; push without force; report the real result.
Never claim a command, commit, push or subagent run you did not observe. If a subagent could not run or its permissions blocked a needed action, say so.
```

Когда придёт отчёт C1, у нас будет либо «GO» по одной-двум темам, либо замена тем. Тогда запускаем веху Q (код проверки ролика с тестами) и срез E на 30-60 секунд.

---

## [40] ВЫ · 2026-10-17 02:57 UTC
_(без текста)_
_Вложения: Screenshot_20261017_075730.jpg_

---

## [41] CLAUDE · 2026-10-17 02:58 UTC
## Что показал отчёт C1

**Хорошо:** отчёт честный. Он прямо пишет, что подагенты в этом запуске не работали как отдельные процессы. Файлы `.kilo/agents/*` существуют, но инструмент `task` в этой сессии знает только `explore` и `general`, поэтому роли выполнял сам оркестратор. Из этого следуют две вещи:
- **«PASS от qa-reviewer» здесь не независимая проверка.** Агент проверил сам себя. Относитесь к нему как к самопроверке.
- Агентов вы можете вызывать **вручную**: в строке ввода Kilo напишите `@qa-reviewer ...` (так подагенты и вызываются по документации). Простой тест изоляции: `@qa-reviewer измени файл README.md`. Если права настроены, он откажет или спросит разрешение. Если отредактирует, права не изолированы, и мне нужно знать об этом.

**Итог по темам:** все 5 тем NO-GO по кадрам (0 пригодных из 10 нужных, первичных документов 0 из 3).

## Почему так вышло и в чём моя ошибка

Гейт сработал по задумке, но задумка плохо подходит к материалам NASA. Агент пишет, что API NASA не отдаёт поля о правах, поэтому правило «неизвестно значит не использовать» отклоняет почти всё (Boeing 720: 12 из 13 в REJECT, Шаттл: 17 из 22). Я сам предложил очень жёсткую схему и не учёл, что права NASA определяются **политикой источника**, а не полем у каждого файла. Проверять надо другое: есть ли у клипа признаки стороннего автора («courtesy of», copyright, чужой кредит) и есть ли на кадре люди и логотипы.

Есть и тревожный момент: **NTRS дал сетевую ошибку три раза подряд**, хотя в Milestone B тот же API работал и PDF открывались. Это либо временный сбой, либо что-то изменилось. Это надо перепроверить, а не принимать как факт.

## Мой выбор из трёх вариантов агента

**(c) + (a):** оставляем нишу, добавляем второй шаг проверки прав. Пивот (b) пока не нужен: проблема в способе проверки, а не в отсутствии кадров. Но ослаблять правило нельзя без причины и записи: новое определение пригодного клипа такое: «прошёл правило по метаданным **или** просмотрен владельцем (с именем и датой)».

**Ускорение:** не ждать. Короткий технический срез на 30-60 секунд (веха E) можно собрать из клипов со статусом `NEEDS_REVIEW`, пометив его **NOT_PUBLISHABLE**. Права на публикацию он не доказывает, зато вы увидите реальный результат и проверите работу монтажёра и QA.

## Промпт для Kilo (Milestone C2: причины отклонения + проверка прав + очередь на просмотр)

```text
MILESTONE C2 — rights evidence pass + NTRS retest + review queue. Docs/reports only: no application code, no installs, no process/lock changes. Time-box 35 min. Free keyless access only; BLOCKED if a key/registration is needed. ERROR/429/EMPTY are separate states, never zero results. Be honest about subagents: if you cannot run a .kilo/agents subagent as a separate process, say "executed inline", never claim independence.

0. Preflight (look only): git status, HEAD. Preserve user changes.
1. From docs/openmontage/audit/C1_RIGHTS_REPORT.md print a breakdown of verdicts by REASON CODE (why each clip was REJECT or NEEDS_REVIEW): counts per reason, top 3 reasons, and which exact metadata fields were missing. Do not guess; quote the fields.
2. NTRS retest: 3 attempts with backoff against the public NTRS citations search API plus one retrieval of a known PDF URL from Milestone B's probe. Record DNS/HTTP status per attempt, timestamps, and your classification: transient vs persistent. Compare with Milestone B (which succeeded). No retries beyond the cap.
3. Rights evidence pass on at most 12 clips (Shuttle/Edwards 5 NEEDS_REVIEW + top others + X-15 NEEDS_REVIEW): fetch each item's own public metadata/asset record. Record: nasa_id, center, any secondary creator / credit / "courtesy" / copyright text, description, date. Apply the EXISTING rules from RIGHTS_MODEL.md; do NOT loosen them. If you believe a rule is too strict for NASA-produced material, write a proposal in the report (rule text, risks, who decides = owner) but do not apply it.
4. Re-read the official NASA media usage guidelines page and quote the exact exception categories (short paraphrase) so the review checklist matches them.
5. Create docs/openmontage/audit/REVIEW_QUEUE.md: per clip: nasa_id, URL, evidence fields, and what a human must check (identifiable persons, logos/insignia, third-party material). If a small preview/low-res variant is listed in the asset manifest, download ONLY that (cap 200 MB total, into the gitignored projects/ area, never committed) and generate a contact sheet (ffmpeg tile of ~12 frames per clip). List the paths. If no preview exists, say so.
6. Write a PROPOSED gate wording (do not change the gate): usable = rule-pass OR owner-reviewed (reviewer, date, notes); tag NOT_PUBLISHABLE for a technical slice built from NEEDS_REVIEW clips.
7. Report, update checkpoint/work log (observed vs assumed). Commit docs only; push without force; report the real result.
Never claim a command, commit, push, download or subagent run you did not observe.
```

После отчёта C2 решим: либо вы за 10 минут просматриваете контакт-листы и подтверждаете клипы, либо меняем тему. Параллельно можно запускать D1-отчёт и веху Q.

---

## [42] ВЫ · 2026-10-17 03:07 UTC
_(без текста)_
_Вложения: Screenshot_20261017_080729.jpg_

---

## [43] CLAUDE · 2026-10-17 03:08 UTC
🔎 web_search: NASA NTRS API ntrs.nasa.gov/api/citations/search endpoint documentation change 2026

## Что показал отчёт C2

**Хорошее:** агент честно ничего не ослаблял. Итог: 37 клипов, из них 29 отклонено, 8 ждут просмотра, пригодных 0. Контакт-лист сгенерирован, всё закоммичено (`447ee60`). Подагенты снова выполнялись «inline», то есть самопроверка, а не независимая. Это нужно помнить.

**Три проблемы, которые я вижу:**

1. **25 клипов отклонены по причине «нет поля с правами».** Но моя же модель прав разрешает `source_policy_us_gov`, если клип произведён NASA (по метаданным) и нет упоминаний третьих лиц. Либо агент применил правило жёстче, чем записано, либо у этих клипов нет даже поля «центр NASA/создатель». Из отчёта этого не видно. Нужен разбор внутри этих 25.

2. **Ошибка классификации.** Агент пишет, что у клипов STS-1 («Provided by Fight for Space / Paul Hildebrandt») и STS-26 (кредиты CNN, NASA TV, Multnomah) есть чужие авторы, и всё равно пометил их `NEEDS_REVIEW`. По нашим правилам клип с кредитом третьей стороны **неприменим, это REJECT.** Ваш просмотр не может «легализовать» материал CNN. Исправить надо до того, как вы потратите время на просмотр.

3. **NTRS не отвечает (HTTP 000 четыре раза).** Код 000 значит, что соединение вообще не установилось, это не ответ сервера. Официальная документация NTRS: корневой адрес `https://ntrs.nasa.gov/api`, поиск идёт методом POST (`/citations/search`), документ получается через GET `/citations/{id}`. Возможно, агент вызывал неправильным методом, но в Milestone B же работало. Нужна диагностика, а не вывод «заблокировано». Приятная новость: на странице документа NTRS указано «Work of the US Gov. Public Use Permitted», то есть для документов есть явное поле прав. Запасной путь: NASA публикует массовые файлы метаданных `ntrs-public-metadata-{год}.ndjson`.

## Решение

**Не менять нишу.** Пока не доказано, что проблема в самих кадрах, а не в способе проверки. Но ставлю жёсткий срок: если после C3 ни по одной теме не наберётся ≥10 клипов, произведённых NASA и без чужих кредитов, меняем тему.

**Что не ждёт footage:** веха Q (скрипт проверки ролика с тестами и `qa_report.json`). Её можно тестировать на уже готовом пилотном MP4 про поддоны (он только для внутренних тестов, права не важны). Запустим параллельно после C3.

## Промпт для Kilo (Milestone C3)

```text
MILESTONE C3 — rights classification diagnosis + NTRS network diagnosis. Docs/reports only: no application code, no installs, no process/lock changes. Time-box 30 min. Free keyless access only. ERROR/429/EMPTY are separate states. Execute subagent roles inline if separate runs are impossible and state clearly "inline, not independent". Do NOT loosen RIGHTS_MODEL.md.

0. Preflight (look only): git status, HEAD. Preserve user changes.
1. Break down the 25 clips rejected as "no license/rights statement" (R1) into sub-reasons, quoting the exact metadata fields present/missing per clip: (a) center/creator field says NASA AND no third-party text/credit AND no restriction text (candidates for source_policy_us_gov under the EXISTING rule, listed by nasa_id); (b) center/creator field missing or not NASA; (c) other. State whether the earlier R1 verdict was a correct application of RIGHTS_MODEL.md or a stricter one; quote the rule text. If it was stricter than the written rule, list which clips would change verdict under the written rule, WITHOUT changing the gate.
2. Fix the classification inconsistency: any clip with third-party credit/courtesy/copyright text (e.g., STS-1 "Provided by Fight for Space / Paul Hildebrandt", STS-26 CNN/NASA TV/Multnomah) must be REJECT under RIGHTS_MODEL.md, not NEEDS_REVIEW. Recompute counts per topic and state the new NEEDS_REVIEW list (only clips whose sole open issue is identifiable_persons/logo_visible).
3. NTRS network diagnosis (max 8 requests, each with 20 s timeout, record status, exit code, timestamp, and the exact method used):
 - DNS resolve of ntrs.nasa.gov; TLS handshake (curl -v) to https://ntrs.nasa.gov/api/openapi/ ; GET https://ntrs.nasa.gov/citations/20260001965 (a page known to exist).
 - POST https://ntrs.nasa.gov/api/citations/search with a JSON body per the official OpenAPI (read the OpenAPI document first; quote the request schema you used). Compare with how Milestone B called NTRS successfully (read the Milestone B report and the script history if available) — was it a different method/URL/headers?
 - Reachability of images-api.nasa.gov and archive.org right now, to separate "local network" from "NTRS side".
 - Classify: transient / persistent / wrong request / local network. If still blocked, check Content-Length (HEAD) of one ntrs-public-metadata-{year}.ndjson file from the NASA STI harvesting page; download ONLY if <= 50 MB into the gitignored projects/ area; otherwise report the size and skip.
4. Candidate sweep for topics Shuttle/Edwards and X-15 only: using the NASA Image and Video Library API (keyless), query by center filter if the API supports one, otherwise by center-specific keywords. Collect up to 15 video candidates per topic; apply RIGHTS_MODEL.md; report counts of: rule-pass (usable pending flag review), NEEDS_REVIEW, REJECT, with reason codes.
5. Update docs/openmontage/audit/REVIEW_QUEUE.md with ONLY the corrected NEEDS_REVIEW clips, the contact-sheet path, and a one-line checklist per clip for the owner: "identifiable person? (yes/no/unclear) | logo or insignia visible? (yes/no/unclear) | third-party credit? (yes/no)". Owner rule: any third-party credit = REJECT regardless of review.
6. Gate check: for each topic report "usable-pending-review count" vs the viability threshold (>=10 clips, >=3 primary docs). Give an explicit pivot recommendation if no topic can reach 10 even after review.
7. Report, update checkpoint/work log (observed vs assumed). Commit docs only; push without force; report the real result.
Never claim a command, commit, push or subagent run you did not observe.
```

После отчёта C3 я скажу, идти ли дальше с этой нишей и нужно ли вам смотреть контакт-лист.

---

## [44] ВЫ · 2026-10-17 03:16 UTC
_(без текста)_
_Вложения: Screenshot_20261017_081623.jpg_

---

## [45] CLAUDE · 2026-10-17 03:17 UTC
Отчёт честный, но вижу в нём расхождение с цифрами Milestone B. Проверяю, можно ли закрыть блокировку NTRS моими инструментами: первичные документы по Boeing 720 я могу найти и открыть сам, минуя заблокированную сеть агента.

🔎 web_search: NASA Controlled Impact Demonstration Boeing 720 1984 technical report NTRS ntrs.nasa.gov

## Что показал отчёт C3

**Хорошее:** агент нашёл свою ошибку (в C1 он применил правило жёстче записанного), исправил классификацию клипов с чужими кредитами (REJECT), и расследовал NTRS по пунктам. Диагноз NTRS надёжный: DNS работает, а подключение к ntrs.nasa.gov по порту 443 не устанавливается, хотя `images-api.nasa.gov` и `archive.org` отвечают. Это **постоянная блокировка с его стороны сети**, а не неправильный запрос.

## Где я не согласен с рекомендацией «пивот»

Агент пишет «ни одна тема не набирает 10 клипов, первичных документов 0/3». Но:

1. **Для Boeing 720 его же цифры говорят другое:** после исправления 11 клипов в статусе «нужна проверка» и только 1 отклонён (11 ≥ 10). В итоговой проверке гейта Boeing вообще не упомянут: считались только Шаттл и X-15.
2. **«0 из 3 первичных документов» это артефакт сломанной сети.** В Milestone B для Boeing было проверено 4 документа NTRS, из них 2+ PDF. Нельзя считать их несуществующими из-за сегодняшнего сетевого сбоя.
3. **Для технического среза на 30-60 секунд не нужно 10 клипов:** по мастер-плану хватает 3-6 реальных клипов. Порог 10 относится к полному ролику.

## Первичные документы я нашёл сам (через веб-поиск, минуя заблокированную сеть)

По теме Controlled Impact Demonstration (1 декабря 1984, Boeing 720) на NTRS есть как минимум шесть документов:
- NASA-TP-2589: данные ударных нагрузок с 330+ временных рядов ускорений, https://ntrs.nasa.gov/citations/19860021249
- NASA-TM-89642 / DOT/FAA/CT-87/10: описание программы целиком, статус прав «Work of the US Gov. Public Use Permitted», https://ntrs.nasa.gov/citations/19880000639
- NASA-TM-85925: системы дистанционного управления самолётом, https://ntrs.nasa.gov/citations/19850015486
- NASA TM 4084 (Horton, Kempel): лётные испытания и управляемый удар, https://ntrs.nasa.gov/api/citations/19890006539/downloads/19890006539.pdf
- Hayduk: обзор CID, https://ntrs.nasa.gov/citations/19860012463
- сводный отчёт FAA/DOT, https://rosap.ntl.bts.gov/view/dot/92854/dot_92854_DS1.pdf

Оговорка: это проверка метаданных и частично текста из результатов поиска, а не чтение PDF целиком. Факты для сценария будут браться только из самих документов позже, а не из моей памяти.

## Вывод

**Не пивотить сейчас.** CID (Boeing 720) остаётся главным кандидатом: документы есть, кадров на срез хватает, на полный ролик нужно подтвердить 10+ после проверки дублей и тематики (клипы могут повторять одно и то же видео). Если после проверки клипов по CID ≥10 не наберётся, тогда пивот.

## Промпт для Kilo (Milestone C4: только Boeing 720)

```text
MILESTONE C4 — CID (Boeing 720, 1 Dec 1984) focus. Docs/reports only: no application code, no installs, no process/lock changes. Time-box 30 min. Do NOT lower the 10-clip gate for the full video. Execute subagent roles inline if separate runs are impossible and say "inline, not independent".

0. Preflight (look only): git status, HEAD. Preserve user changes.
1. Create docs/openmontage/audit/EVIDENCE_CID_PRIMARY_DOCS.md. Provenance for every entry: "metadata verified externally by Claude (web search, 2026-10-17) because this sandbox cannot reach ntrs.nasa.gov; NOT agent-verified; PDF retrieval not yet confirmed". Entries (title, id, URL, org, NTRS rights statement if shown):
 - NASA-TP-2589, "Impact data from a transport aircraft during a controlled impact demonstration", https://ntrs.nasa.gov/citations/19860021249
 - NASA-TM-89642 / DOT/FAA/CT-87/10, "Full-scale Transport Controlled Impact Demonstration Program", https://ntrs.nasa.gov/citations/19880000639
 - NASA-TM-85925, "Remote control of an impact demonstration vehicle", https://ntrs.nasa.gov/citations/19850015486
 - NASA TM 4084, "Flight Test Experience and Controlled Impact of a Remotely Piloted Jet Transport Aircraft", https://ntrs.nasa.gov/api/citations/19890006539/downloads/19890006539.pdf
 - Hayduk, "CID overview", https://ntrs.nasa.gov/citations/19860012463
 - FAA/DOT Summary Report, https://rosap.ntl.bts.gov/view/dot/92854/dot_92854_DS1.pdf
 Do not paste document text and do not derive topic claims from memory. Mark each as EXTERNALLY_VERIFIED_METADATA.
2. For the 11 Boeing NEEDS_REVIEW clips and the 1 REJECT: table with asset id, title, description, date, duration, center, collection. From METADATA ONLY classify: on-topic (depicts the CID flight/impact/fire/post-impact) | related (preparation, other tests) | unclear. Detect duplicates (same footage under different items) by title/description/duration similarity. Give a deduplicated count.
3. Gate recompute for CID under the WRITTEN gate: usable-pending-review count after dedupe and on-topic filter; primary docs count from step 1 (state that verification came from outside the sandbox). Verdict for the FULL video (>=10 clips, >=3 docs). Separately state whether the 30–60 s technical slice requirement (3–6 clips per master plan) is met. Resolve the earlier inconsistency: why the C3 gate check did not list Boeing 720.
4. Owner review pack: for each deduplicated on-topic clip build a contact sheet (ffmpeg tile of ~12 frames) from previews if available; if only thumbnails exist, say so. Save to gitignored projects/c4_review/ (cap 200 MB, never commit media). Update docs/openmontage/audit/REVIEW_QUEUE.md with paths and a per-clip owner checklist: "identifiable person? | logo/insignia visible (NASA, FAA, Boeing, other)? | third-party credit? (yes => REJECT)".
5. Re-read the official NASA media usage guidelines and write a PROPOSED (not applied) wording for incidental insignia visible on vehicles in footage, quoting the exact exception categories. Mark it "owner decision".
6. Update the plan/work log: slice and pilot topic candidate = CID 1984; fallback topics listed. Report observed vs assumed. Commit docs only; push without force; report the real result.
Never claim a command, commit, push, download or subagent run you did not observe.
```

После C4 вам нужно будет за 10 минут просмотреть контакт-листы (по списку: люди, логотипы, чужой кредит). Я напишу, как это сделать с телефона. Параллельно можно запускать веху Q.

---

## [46] ВЫ · 2026-10-17 03:38 UTC
_(без текста)_
_Вложения: Screenshot_20261017_083756.jpg_

---

## [47] CLAUDE · 2026-10-17 03:39 UTC
Отчёт C4 закрыл главный вопрос по документам и счёту клипов. Проверяю, что это за клипы NIX, чтобы понять, как вам их просматривать, раз контакт-листы не получились.

🔎 web_search: archive.org NIX-LV-1998-00090 NASA Image eXchange controlled impact demonstration Boeing 720

## Что показал отчёт C4

**Хорошее:** это самый содержательный отчёт на данный момент.
- 6 первичных документов внесены в реестр с честной пометкой «проверено извне, PDF не получены».
- 11 клипов Boeing 720 (NIX-EM-0004-01/02, NIX-LV-1998-00090…00098): все созданы NASA, без чужих кредитов, все по теме (удар и пожар). Один клип отклонён за чужой кредит, один ролик с Commons отклонён за стороннего загрузчика.
- Гейт: 11 клипов (порог 10) и 6 документов (порог 3). **Для полного ролика статус `NEEDS_OWNER_REVIEW`, для среза на 30-60 секунд требование выполнено.** Противоречие C3 снято.

**Две оговорки:**
1. «Нет дубликатов» определено только по метаданным. Идущие подряд номера `NIX-LV-1998-00090…00098` похожи на фрагменты одной плёнки, возможны повторы кадров. Это видно только при просмотре.
2. **Контакт-листы не созданы: загрузки с archive.org вернули 0 байт или HTML.** Это важнее, чем просто неудобство для вашего просмотра: если фабрика не может скачать эти клипы, она не соберёт из них видео. Нужна диагностика. Вероятные причины (гипотезы): неверный адрес файла (HTML-страница ошибки) или блокировка сети. Для отличия служит запрос метаданных archive.org со списком настоящих файлов.

Для справки: тема хорошо подтверждается и официальными источниками NASA, например документом NASA Facts про CID, который стоит добавить в реестр.

## Как вам просматривать клипы (пока нет контакт-листов)

Откройте в браузере телефона страницы 11 клипов на archive.org и посмотрите каждый. Для каждого ответьте на три вопроса:
1. **Есть ли узнаваемый человек в кадре?** (лицо крупным планом и т. п.)
2. **Видны ли логотипы или эмблемы?** (NASA, FAA, Boeing, авиакомпания)
3. **Есть ли чужой кредит на экране?** (CNN и т. п. Если да, клип отклоняется, ваша проверка этого не исправит.)

Любое «не уверен» считается «нет, не используем». Ответы пришлите мне в виде «1: нет/нет/нет, 2: ...», я оформлю запись для агента.

Список ссылок агент выведет в следующем шаге (C5), я заложил это в промпт.

## Решение по эмблемам (ваше, но с моим мнением)

Агент подготовил формулировку (в REVIEW_QUEUE.md и отчёте C4, я её не видел). Моё предварительное чтение правил NASA: эмблема на самолёте в кадре из собственного архива NASA это одно, а использование логотипа NASA в **нашей** обложке, названии или оформлении канала, будто NASA нас поддерживает, это другое и недопустимо. Решайте после того, как прочитаете цитаты из правил в отчёте.

## Что запускать

Две вехи подряд (в одной сессии Kilo они не мешают друг другу). Сначала C5, потом Q1. Q1 это как раз тот самый «агент проверки»: код проверки видео, не зависящий от прав на кадры.

**Milestone C5 (диагностика загрузок + список ссылок для вас):**

```text
MILESTONE C5 — archive.org download diagnosis + owner review list. Docs/reports only: no application code, no installs, no process/lock changes. Time-box 25 min. Max 10 network requests, 20 s timeout each. ERROR/HTTP status/EMPTY are separate states. Execute subagent roles inline if separate runs are impossible and say so.
0. Preflight (look only): git status, HEAD. Preserve user changes.
1. For the 11 CID clips (NIX-EM-0004-01/02, NIX-LV-1998-00090…00098): fetch the archive.org metadata JSON per item (https://archive.org/metadata/<identifier>). Record HTTP status and the REAL file list (name, format, size). Never construct file names by guessing.
2. For ONE item, test: HEAD then ranged GET (first 64 KB) of (a) a thumbnail file and (b) the smallest video derivative, using file names from step 1. Record status, final URL after redirects, content-type, content-length. Classify: wrong URL (404 HTML) | access-restricted | blocked egress | hotlink/other. Compare with the pilot's successful Wikimedia Commons downloads: read-only look at how direct_clip_search builds archive.org download URLs (metadata file list vs constructed URLs).
3. If a working URL is found: download ONLY preview-size derivatives (cap 200 MB total, gitignored projects/c5_review/, never committed), build ffmpeg contact sheets (~12 frames per clip), list paths. If not: BLOCKED with the exact classification.
4. PRINT IN THE TERMINAL (not only in a file) a numbered list of the 11 archive.org item page URLs, each with a one-line description and duration from the metadata, so the owner can open them on a phone. Also write the same list to docs/openmontage/audit/REVIEW_QUEUE.md.
5. Add NASA Facts "Controlled Impact Demonstration" (https://www.nasa.gov/centers/dryden/pdf/315492main_FS-2009-02-003-CID.pdf) to EVIDENCE_CID_PRIMARY_DOCS.md as EXTERNALLY_VERIFIED_METADATA (source: Claude web search 2026-10-17; not agent-verified).
6. Flag the sequential IDs NIX-LV-1998-00090…00098: from metadata, are they segments of one reel (possible overlapping footage)? Say what viewing is needed to confirm.
7. Report observed vs assumed; update checkpoint/work log. Commit docs only; push without force; report the real result.
Never claim a command, commit, push, download or subagent run you did not observe.
```

**Milestone Q1 (код проверки видео, TDD):**

```text
MILESTONE Q1 — media-level QC tool per docs/openmontage/QA_SPEC.md, test-first. No new dependencies (stdlib + ffmpeg/ffprobe only). Time-box 45 min. No network, no model downloads, no process/lock changes. Execute roles inline and say so.
0. Preflight (look only): git status, HEAD. Find existing tool/test conventions and where tools live (read first). Preserve user changes.
1. Write FAILING tests first (generate fixtures at test time with ffmpeg lavfi into tmp dirs; never commit media): good clip (color + sine tone, 1080p, with audio); clip with a black segment; clip with a silent segment; clip with a frozen segment; clip without audio; wrong resolution/aspect; corrupt file (truncated); subtitle file whose last cue ends after the audio duration; check that cannot run (tool missing/unparseable output). Run them and show the red result.
2. Implement the QC module with checks: ffprobe stream facts (video+audio present, resolution, fps, duration), full decode (-f null, errors counted), blackdetect, freezedetect, silencedetect, ebur128 (integrated LUFS + true peak), SRT sanity (monotonic, no overlap, last cue <= audio duration + tolerance). Thresholds from a config file with the INITIAL GUESSES from QA_SPEC.md (document each as a guess). FAIL-CLOSED: a check that cannot run => BLOCKED, never PASS. Optional checks whose inputs are absent (credits.txt, claim_id ledger, rights records) => NOT_RUN, listed explicitly; the release verdict treats NOT_RUN as not-passed.
3. Output qa_report.json per the QA_SPEC schema (job_id, check_id, status in PASS|REVIEW|BLOCKED|FAILED|NOT_RUN, evidence, measured_value, threshold, tool_version, timestamp). Never write secrets.
4. Make the tests green; run the new tests AND the existing fast test suite; run ruff on changed files. Report exact commands and exit codes.
5. Smoke test on the existing pilot MP4 if present locally (renders/pallets-hidden-business.mp4): run the QC tool, show the real qa_report.json summary. This is an internal tool test, not a publishability claim.
6. Wire the qa-reviewer agent doc to call this tool (update .kilo/agents/qa-reviewer.md and AGENTS.md; keep permissions read-only plus qa_report.json).
7. Update docs/work log (observed vs assumed). Commit code+tests+docs; push without force; report the real result.
Never claim a test, command, commit or push you did not observe.
```

После C5 пришлите отчёт, и я помогу оформить ваш просмотр клипов. После Q1 можно запускать срез E (30-60 секунд) на проверенных клипах.

---

## [48] ВЫ · 2026-10-17 07:17 UTC
_(без текста)_
_Вложения: Screenshot_20261017_120252.jpg, Screenshot_20261017_121645.jpg_

---

## [49] CLAUDE · 2026-10-17 07:18 UTC
## Что показали отчёты

### Q1: инструмент проверки ролика готов

- Модуль `tools/qa/qc.py`, 11 тестов написаны первыми и все проходят, пороги вынесены в конфиг, схема `qa_report.json` по спецификации, коммит `59cdf6a`. Фабрика теперь умеет проверять видео сама, это закрывает вашу претензию про «агента проверки».
- **Первая реальная находка:** на пилотном MP4 про поддоны вердикт `FAILED`. Громкость -17.1 LUFS (ниже допуска ±2 от -14) и пик 0.0 dBTP (допуск -1.5). Пик на нуле означает риск искажений после сжатия YouTube. Это именно то, что выдаёт озвучка без финальной нормализации. Пороги пока стартовые догадки, но пик на 0.0 в любом случае плох.
- Честные оговорки агента: `ruff` не установлен, линтер не запускался (только `py_compile`), роли снова выполнялись inline.

### C5: загрузка с archive.org работает

Блокировки не было. Прошлые «0 байт / HTML» получились потому, что запрос шёл без `-L` (не следовал за перенаправлением 302). Это моя гипотеза «неверный запрос» оказалась верной по сути. Реальные списки файлов получены для 4 из 11 клипов, скачаны превью (~2.6 МБ), собраны контакт-листы для двух клипов (`EM-0004-01` и `LV-1998-00090`), список из 11 ссылок выведен и записан, NASA Facts добавлен (документов теперь 7).

### Важный вывод про клипы

`NIX-LV-1998-00090…00098` это 9 из 10 подразумеваемых частей, и агент считает их **съёмкой одного удара с разных камер** с вероятным пересечением по времени, а не одной линейной плёнкой. Если это подтвердится, у нас 11 клипов, но почти все про один момент. Для ролика на 6-10 минут нужны ещё кадры подготовки, дистанционного пилотирования, полёта, последствий. Это значит, что **порог «≥10 клипов» плохо измеряет то, что нам нужно.** Лучше мерить покрытие сюжетных блоков: ≥6 блоков, в каждом хотя бы один клип. Пока это моя гипотеза, контакт-листы её проверят. Реалистичный первый пилот, возможно, окажется 4-6 минут, а не 8-10.

## Что вы делаете прямо сейчас (5 минут)

В VS Code откройте в проводнике папку `projects/c5_review/` и два файла `EM-0004-01_contact_sheet.jpg` и `LV-1998-00090_contact_sheet.jpg`. По каждому ответьте:
1. Узнаваемый человек крупным планом? (да/нет/не уверен)
2. Видны логотипы или эмблемы? (какие)
3. Чужой кредит или титры на кадрах? (да/нет)

Пришлите мне в виде «1: нет/…, 2: …». «Не уверен» считается «не используем».

## Два промпта для агента

**Milestone C6 (остальные контакт-листы, длительности, сводка по голосу):**

```text
MILESTONE C6 — finish contact sheets for all 11 CID clips + durations + coverage map + voice decision summary. Docs/reports only: no application code, no installs, no process/lock changes. Time-box 30 min. Use curl -L (follow redirects). Cap: 30 network requests, 20 s timeout each; total downloads <= 200 MB into gitignored projects/c5_review/ (never committed). ERROR/HTTP status/EMPTY are separate states. Roles inline: say so.
0. Preflight (look only): git status, HEAD. Preserve user changes.
1. Fetch the metadata JSON (REAL file list, never guessed names) for the 7 clips not yet done. Pick the smallest video derivative per clip (the ~512kb mp4 if present). Download and build ffmpeg contact sheets (~12 frames per clip). Result: 11 contact sheets in projects/c5_review/. Print their paths in the terminal.
2. Record per clip: duration (ffprobe), resolution, whether the source has audio. Update REVIEW_QUEUE.md with a table: clip, duration, contact-sheet path, owner checklist columns (person | logo/insignia | third-party credit), empty for the owner.
3. Coverage map (metadata and ffprobe only, do not judge pixels): for each clip, the narrative beat its title/description suggests (preparation | remote piloting | flight | impact | fire | aftermath | other | unclear). Report the number of distinct beats covered and which beats have zero clips. Propose (do not apply) a viability-gate wording based on distinct narrative beats (e.g., >= 6 beats, >= 1 usable clip each) in addition to the raw clip count.
4. Print a short summary of docs/openmontage/TOOLING_DECISIONS.md and any D1 report: the voice license decision (Piper en_US-lessac-medium vs Kokoro vs other: license evidence, UNKNOWN items) and what blocks publication.
5. Report observed vs assumed; update checkpoint/work log. Commit docs only; push without force; report the real result.
Never claim a command, commit, push, download or subagent run you did not observe.
```

**Milestone D2 (финальная обработка звука, проверка QC-инструментом, TDD):**

```text
MILESTONE D2 — audio finishing module, test-first, verified by our own QC tool. No new dependencies (stdlib + ffmpeg), no network, no model downloads, no process/lock changes. Time-box 40 min. Roles inline: say so.
0. Preflight (look only): git status, HEAD. Read first: how the render path handles audio today (e.g., the 44100 Hz unification), tools/qa/qc.py, config/qc_thresholds.json, docs/openmontage/EDITING_DOCTRINE.md, MUSIC_POLICY.md, and the voice decision in TOOLING_DECISIONS.md. Preserve user changes.
1. Failing tests first (fixtures generated with ffmpeg lavfi in tmp dirs; never commit media): (a) voice-like tone at low level + peak near 0 dBFS -> after finishing: integrated loudness within target tolerance and true peak <= -1.5 dBTP (measured with the QC module's ebur128 check); (b) with a music bed: music is ducked under voice (measure level difference in voiced vs unvoiced segments); (c) no music: finishing still works; (d) mono/stereo and 22050/44100 Hz inputs; (e) failure path: ffmpeg filter missing or measurement unparsable -> BLOCKED, never silent success. Show the red result.
2. Implement tools/audio/finish_audio.py (or the repo's convention): two-pass loudnorm (measure, then apply with measured values) + limiter for true peak; optional sidechain ducking when a music track is given. STARTING targets I=-14, TP=-1.5, LRA=11 read from config (guesses, secondary sources; for narration-first content -16..-14 may be acceptable: record this question for the owner). No music is used in the pilot unless MUSIC_POLICY.md license evidence exists.
3. Green tests; run the new tests AND the existing fast suite; report exact commands and exit codes.
4. Smoke: re-process ONLY the audio of the local pilot MP4 (renders/pallets-hidden-business.mp4) into /tmp, run the QC tool on the result, show before/after ebur128 numbers. Internal test only; not a publishability claim; do not overwrite the original.
5. Do NOT wire it into the render pipeline yet; write docs/openmontage/AUDIO_FINISHING.md with the proposed integration point (path and function) for the next milestone.
6. Update docs/work log (observed vs assumed). Commit code+tests+docs; push without force; report the real result.
Never claim a test, command, commit or push you did not observe.
```

После C6 и ваших ответов по контакт-листам оформим решения по клипам, затем можно запускать срез E: короткий сценарий по NASA Facts (с первичным документом и claim_id), озвучка, монтаж, финальный звук, проверка QC.

---

## [50] ВЫ · 2026-10-17 08:09 UTC
_(без текста)_
_Вложения: Screenshot_20261017_130647.jpg, Screenshot_20261017_130852.jpg_

---

## [51] CLAUDE · 2026-10-17 08:10 UTC
D2 выполнен, а блокер остаётся: лицензия голоса. Это можно проверить сейчас по первоисточникам, не дожидаясь агента.

🔎 web_search: rhasspy piper-voices en_US lessac MODEL_CARD license dataset Blizzard commercial use

Это важная находка. Проверяю запасной вариант (Kokoro) по первоисточнику.

🔎 web_search: hexgrad Kokoro-82M Hugging Face model card license Apache 2.0 training data permissive non-copyrighted audio

## Что показали отчёты

**D2 выполнен.** Модуль финальной обработки звука работает, 5 тестов проходят. Реальный результат на звуке пилота: **до** -17.2 LUFS и пик 0.0 dBTP (клиппинг), **после** -15.3 LUFS и пик -4.5 dBTP, проверка нашим же QC прошла. Цель была -14, получилось -15.3: в допуске (±2), но это напоминание, что цифры стартовые догадки.

Две оговорки агента, которые стоит запомнить:
- Кодеки AAC (`f32le-aac`, `s16-aac-after-limiter`) в этой сборке ffmpeg **сломаны**, поэтому модуль выдаёт WAV. Значит, в конвейере громкость нужно **перемерять на финальном MP4 после кодирования в AAC**, потому что кодирование может поднять пик.
- Быстрый набор тестов репозитория запускается скриптом, а не через pytest (собрал 0 тестов), и `ruff` не установлен.

**Второй скриншот:** это повторная отправка промпта D2. Агент правильно заметил, что всё уже сделано, и ничего не менял. Повторно слать не нужно.

**C6 тоже выполнен** (коммит `0610da1`), но его отчёта я не видел. Пришлите скриншот, а также ответы по контакт-листам (3 вопроса про каждый клип из прошлого сообщения), иначе клипы остаются неподтверждёнными.

## Главное: голос Piper lessac нельзя публиковать

Я проверил по первоисточникам. Это даже хуже, чем «лицензия неизвестна»:
- Карточка голоса `lessac (medium)` пишет только «обучен с нуля» на корпусе Lessac Blizzard 2013 со ссылкой на лицензию этого датасета. Слова про CC-BY-4.0, которые агент нашёл в манифесте, **ничем не подтверждены.**
- По прочтению участников обсуждения в репозитории Piper, эта лицензия ограничивает использование материалов исследовательскими целями и запрещает коммерческое развитие. Это мнение сообщества, а не юридическое заключение, но вопрос о разрешении правообладателя в открытом обсуждении остаётся без подтверждённого ответа. Монетизируемый YouTube-канал это коммерческое использование.
- Производные голоса (libritts_r и др.) тоже затронуты: их карточки указывают, что они дообучены на основе lessac.

**Вывод: голос lessac используем только внутри тестов, ни одного публичного видео с ним.**

## Замена: Kokoro-82M

- Лицензия весов Apache 2.0, модель развёрнута во многих проектах и коммерческих API.
- По карточке модели обучена исключительно на данных с разрешающими или не защищёнными авторским правом лицензиями (общественное достояние, Apache/MIT и т. п.). В таблице обучающих данных есть наборы под CC BY 3.0 и 4.0 (Koniwa tnc, SIWIS). Версия 1.0 дополнительно использовала синтетические данные от участников, и лицензии тех источников из карточки не видны. Остаточный риск небольшой, но он не нулевой.

Решение за вами (и за родителем как владельцем аккаунта AdSense): я бы принял Kokoro как голос по умолчанию и записал в реестр рисков строку про происхождение обучающих данных.

## Промпт для Kilo (Milestone V: Kokoro, проверка лицензии и тест)

```text
MILESTONE V — replace Piper lessac with Kokoro-82M: license evidence, install, CPU test. Time-box 40 min. Allowed: pip install of kokoro + minimal deps inside the project's Python environment, download of the Kokoro-82M weights (~330 MB, cap 600 MB) into a gitignored cache dir. No paid routes, no keys, no process/lock changes. Roles inline: say so.
0. Preflight (look only): git status, HEAD, Python env, free disk, `which espeak-ng`. Preserve user changes. Check whether OpenMontage already has a Kokoro provider/tool/config (read first, report path); if yes use it, do not write a second one.
1. License evidence from the OFFICIAL files: fetch hexgrad/Kokoro-82M README front matter (license field), LICENSE file if any, and the training-data table; also the license of the `kokoro` and `misaki` Python packages (from their repos/PyPI metadata). Table: component, license, evidence URL, retrieved date, UNKNOWN where unstated. Record the facts: weights Apache-2.0; training data includes CC BY items (names as listed in the card) and v1.0 mentions contributed synthetic data — mark the origin of those synthetic data UNKNOWN. Also record, from the Piper voices Hugging Face repo, that lessac-medium's MODEL_CARD has no license field and points to the Lessac Blizzard 2013 dataset license (quote URL). Decision text: Piper lessac voices are NOT cleared for published/monetized videos.
2. Install and run on CPU: synthesize the same 60 s script used for the earlier test (or a neutral public-domain-safe paragraph) with 3 Kokoro English voices. Report real-time factor, memory, and any espeak-ng/G2P dependency problems. Samples to /tmp only (never committed).
3. Run tools/qa/qc.py on each sample (ffprobe, decode, silencedetect, ebur128) and then tools/audio/finish_audio.py on one sample; show before/after loudness. Record that AAC encoders were reported broken in this ffmpeg build: test whether libx264 + a working AAC encoder exists for the FINAL mux (e.g., list available encoders), and report which one to use; measure loudness on the final MP4, not only on WAV.
4. Write docs/openmontage/VOICE_DECISION.md: chosen voice engine (Kokoro), evidence table, residual risks (training-data provenance, CC BY items), and the open owner/guardian decision on accepting that risk. Update TOOLING_DECISIONS.md and the "voice license known" gate status (known = Apache-2.0 weights with documented data caveats; Piper lessac = blocked).
5. Do NOT change pipeline code in this milestone; if integration is needed, write a short proposal (file, function) for the next milestone.
6. Report observed vs assumed; update checkpoint/work log. Commit docs only; push without force; report the real result.
Never claim a command, install, download, commit or push you did not observe.
```

## Дальше

1. V (голос) → 2. вы смотрите контакт-листы и присылаете ответы → 3. Срез E1: сценарий на 30-60 секунд по документам NASA (каждое утверждение со ссылкой на источник), без медиа → 4. E2: озвучка, монтаж, финальный звук, QC.

---

## [52] ВЫ · 2026-10-17 08:38 UTC
Что делать агент всё ещё работает а памяти почти нету
_Вложения: Screenshot_20261017_133722.jpg_

---

## [53] CLAUDE · 2026-10-17 08:38 UTC
**Не паникуйте, но действуйте сейчас.** Диск почти полон: GitHub Codespaces предупреждает об этом, когда свободно меньше 1%. Скорее всего, место съели `torch` и его CUDA-библиотеки (их ставит `pip` вместе с Kokoro), плюс скачанные веса и старые файлы. Агент не сломан, но если место кончится, он не сможет записать файлы и сделать коммит.

## Что делать (3 минуты)

**1. Агента не прерывайте.** Его текущая команда короткая (синтез и подсчёт размера кэша). Просто не давайте ему начинать новые скачивания.

**2. Откройте вторую вкладку терминала** (кнопка «+» вверху панели терминала) и посмотрите, что занимает место:

```bash
df -h /workspaces ~ /tmp 2>/dev/null
du -xsh ~/.cache ~/.local ~/.python /tmp/hf-cache /workspaces/OpenMontage/projects 2>/dev/null
du -xh --max-depth=1 /workspaces/OpenMontage 2>/dev/null | sort -h | tail -8
```

**3. Освободите безопасные кэши** (это не затрагивает репозиторий):

```bash
pip cache purge
rm -rf ~/.cache/pip
sudo apt-get clean
npm cache clean --force 2>/dev/null
df -h /workspaces
```

**Не удаляйте:**
- `projects/c5_review/`: там контакт-листы клипов, которые вы ещё не просмотрели.
- `.git`, `renders/`, весь репозиторий.
- `/tmp/hf-cache`, пока агент не закончит тест (там веса Kokoro, ~330 МБ; после теста их можно убрать, `/tmp` и так временный).

Если после этого свободно меньше нескольких сотен МБ, пришлите мне вывод первой команды (`du`), я скажу, что ещё можно удалить.

## Если агент выдал «No space left on device»

Нажмите **Esc**, освободите место, затем напишите ему:

```text
Continue Milestone V from where you stopped. First run read-only preflight: git status, df -h, check which steps are already done (samples in /tmp, weights cache, any uncommitted files). Do not re-download weights if the cache is intact. Do not start any new large install. Report free disk space before each heavy step.
```

## На будущее

Тяжёлый стек (`torch` с CUDA-пакетами занимает несколько ГБ) плохо подходит для Codespace с ограниченным диском. После завершения V проверим два более лёгких пути:
- установка **CPU-версии torch** (она заметно меньше), либо
- ONNX-вариант Kokoro без torch (идея, лицензию обёртки нужно проверить по её репозиторию, я этого ещё не делал).

Когда агент закончит V, пришлите скриншот его отчёта.

---

## [54] ВЫ · 2026-10-17 08:51 UTC
_(без текста)_
_Вложения: Screenshot_20261017_135100.jpg_

---

## [55] CLAUDE · 2026-10-17 08:52 UTC
Отчёт V хороший. Пока вы читаете, я вынимаю из NASA Facts проверяемые утверждения для сценария: агент не может открыть NTRS, а я могу.

🔎 web_fetch: https://www.nasa.gov/centers/dryden/pdf/315492main_FS-2009-02-003-CID.pdf

🔎 web_fetch: https://ntrs.nasa.gov/api/citations/19890006539/downloads/19890006539.pdf

## Что показал отчёт V

**Milestone V выполнен** (коммит `7fd52a4`, запушен).
- Лицензии из официальных файлов: веса Kokoro, пакеты `kokoro` и `misaki` под Apache-2.0. Piper lessac остаётся неизвестным и **заблокирован**.
- Реальные цифры: Kokoro работает на CPU **медленнее реального времени** (RTF 1.58-1.75, то есть минута звука ≈ 1.6-1.75 минуты синтеза). Шестиминутная озвучка займёт около 10-11 минут. Приемлемо, на длинном тексте не измерялось.
- Сырой звук Kokoro очень тихий (-21.8…-25.4 LUFS), после `finish_audio` -15.0 LUFS и пик -4.4, на финальном MP4 -15.0/-4.3, QC прошёл, **нативный AAC-энкодер работает.** Вопрос про ломаный AAC закрыт.
- В обучающих данных агент отмечает **синтетические данные от закрытых TTS-сервисов с неизвестным происхождением.** Это главный остаточный риск.
- **Диск:** `/workspaces` заполнен на 98% (свободно 820 МБ). Веса лежат в `/tmp`, который временный (после пересоздания Codespace скачивать заново, ~313 МБ).

## Два решения, которые нужны от вас

**1. Голос Kokoro (согласование).** Что известно точно: лицензия весов Apache-2.0, она широко используется в коммерческих проектах. Что неизвестно: происхождение части обучающих данных. Это риск автора модели, но юридически его нельзя исключить. Моя рекомендация: принять Kokoro условно, записать риск в реестр и **сообщить родителю как владельцу аккаунта AdSense.** Решение за вами и за ним.

**2. Контакт-листы клипов (всё ещё жду ответы).** Нужны ответы по 3 вопросам на каждый клип.

## Что сделал я: прочитал два первичных документа целиком

Агент не может открыть NTRS, поэтому я прочитал текст двух документов: NASA Facts (кратко) и NASA TM-4084 (технический отчёт). Они **подтверждают друг друга** по ключевым цифрам (14 испытательных полётов, 69 заходов, 16 ч 22 мин дистанционного управления, точка невозврата 150 футов). Есть также детали, которые есть только в одном документе, и ряд пунктов, которые мы пометим как «нужен второй источник».

Самое интересное для сюжета: за всё время практики самолёт ни разу не подходил к месту удара ниже 150 футов, и пилоту на земле было трудно оценивать глубину по низкокачественному 525-строчному видеомонитору. А итог по топливу: полномасштабный эксперимент показал, что присадка не снизила распространение и интенсивность огня, хотя мелкие наземные тесты обещали обратное.

## Промпт для Kilo (Milestone E1: реестр утверждений и черновик сценария, только документы)

```text
MILESTONE E1 — claim ledger + 60 s slice script v0 for CID (Boeing 720, 1 Dec 1984). Docs only: no application code, no installs, no process/lock changes. Time-box 25 min. Roles inline: say so. Paraphrase only; never paste long passages from the source documents.
0. Preflight (look only): git status, HEAD, df -h /workspaces (report free space; do not delete anything). Preserve user changes.
1. Try ONCE to fetch the NASA Facts PDF from nasa.gov (https://www.nasa.gov/centers/dryden/pdf/315492main_FS-2009-02-003-CID.pdf). If reachable, verify each FS-derived claim below against the text and set AGENT_VERIFIED_TEXT; if not, keep EXTERNALLY_VERIFIED. Do NOT retry NTRS (known blocked).
2. Create docs/openmontage/evidence/CID_CLAIM_LEDGER.md. Provenance: "claims extracted by Claude from the full text of NASA Facts FS-2009-02-003-DFRC and NASA TM-4084 (Horton & Kempel, Nov 1988), retrieved 2026-10-17; agent has not read the NTRS PDF (network blocked)". Columns: claim_id | paraphrased claim | source(s) with section/page | status (TWO_SOURCES | SINGLE_SOURCE | OCR_UNVERIFIED) | needs. Claims, verbatim as given (do not add any):
 CID-01 On 1 Dec 1984 the remotely piloted Boeing 720 flew the 15th and final flight of the program and was crash-landed at Edwards (Rogers Dry Lake). [FS; TM-4084] TWO_SOURCES
 CID-02 The aircraft was an obsolete four-engine Boeing 720 airliner obtained from the FAA. [FS; TM-4084] TWO_SOURCES
 CID-03 Purpose included testing the FM-9 anti-misting fuel additive to reduce post-crash fire; other objectives: crash structural data, seat/restraint effectiveness. [FS; TM-4084] TWO_SOURCES
 CID-04 The airplane carried no flight crew on the final flight and was flown from a ground cockpit; FS names NASA research pilot Fitzhugh Fulton at the Dryden remotely controlled vehicle facility. [FS; TM-4084 for ground cockpit] pilot name = SINGLE_SOURCE (FS)
 CID-05 Before the final flight: 14 test flights with crew aboard, 10 remote takeoffs, 13 remote landings on the abort runway, 69 approaches to the impact site, 16 h 22 min of remote control. [FS; TM-4084] TWO_SOURCES (note: TM says go-around at 200 ft in practice)
 CID-06 In practice the airplane was never flown lower than 150 ft above ground toward the impact site. [TM-4084 concluding remarks] SINGLE_SOURCE
 CID-07 Below 150 ft above ground the airplane was committed to impact. [FS; TM-4084] TWO_SOURCES
 CID-08 At the decision point the airplane was slightly right of the centerline; the pilot judged there was enough altitude to correct and continued. [FS; TM-4084 region D] TWO_SOURCES
 CID-09 The left wing hit the ground first, short of the wing cutters (qualitative). [FS; TM-4084] TWO_SOURCES. Numbers from the TM-4084 table (impact ~282 ft short, ~12 deg bank vs 0 ±2 goal, sink rate 17.4 ft/s vs 17 ±1) are OCR_UNVERIFIED: the table text was garbled; verify visually in the PDF before use.
 CID-10 One wing cutter struck the inboard engine on the right wing, causing a massive fuel leak that ignited; the right wing broke off; the fuselage was engulfed in a fireball; the fire took more than an hour to extinguish. [FS] SINGLE_SOURCE
 CID-11 76,000 lb of modified Jet-A fuel was on board. [FS] SINGLE_SOURCE; needs TM-89642 or the FAA summary report
 CID-12 Takeoff gross weight for the impact flight: 200,500 lb; approximate empty weight 98,000 lb. [TM-4084] SINGLE_SOURCE
 CID-13 In the full-scale test the modified fuel was ineffective at reducing fire propagation or intensity (small-scale ground tests had suggested otherwise); the FAA requirements for the additive were cancelled. [FS] SINGLE_SOURCE; LOAD-BEARING, needs a second source (TM-89642 / FAA summary report)
 CID-14 The ground pilot had poor depth perception via a low-resolution 525-line monitor; the tracking radar was not accurate enough for the guidance task (e.g., a 23 ft discrepancy against a 15 ft tolerance). [TM-4084] SINGLE_SOURCE
 CID-15 From the remotely-piloted-vehicle standpoint the program was considered a success although not all impact parameters were met. [TM-4084] SINGLE_SOURCE
 CID-16 Cameras in the cabin showed dummies shaken and small panels falling; seats stayed attached; the data helped the FAA set new rules on fire prevention and fire-retardant materials. [FS] SINGLE_SOURCE
3. Create docs/openmontage/slice/CID_SLICE_SCRIPT_v0.md (status: DRAFT, NOT_PUBLISHABLE: clips unreviewed, voice sign-off pending). One sentence per line with its claim_ids:
 S1 "On December first, 1984, NASA crashed a Boeing 720 airliner on purpose." [CID-01]
 S2 "Nobody was on board. A pilot flew it by remote control from the ground." [CID-04]
 S3 "The goal was to test a fuel additive meant to stop crash fires." [CID-03]
 S4 "Before the real thing, the team flew fourteen test flights with crews aboard and practiced sixty-nine approaches to the crash site." [CID-05]
 S5 "But in practice, the airplane had never flown lower than a hundred and fifty feet toward the crash site." [CID-06]
 S6 "On the real flight, it arrived slightly off the centerline, and its left wing hit first." [CID-08, CID-09]
 S7 "The fuel ignited into a fireball that burned for more than an hour." [CID-10]
 S8 "And the additive that had worked in small tests did not reduce the fire at full scale." [CID-13]
 Mark S5, S7, S8 as depending on SINGLE_SOURCE claims; S8 is blocked for publication until CID-13 has a second source.
4. Run the QC module's claim_ids check against the script + ledger (tools/qa/qc.py). Show the real output. If the expected file format differs from these docs, adapt the docs to the tool (not the tool to the docs) and report the mismatch.
5. Add the new documents to EVIDENCE_CID_PRIMARY_DOCS.md as "full text read externally (NASA Facts, TM-4084)"; keep others as metadata only.
6. Update checkpoint/work log (observed vs assumed). Commit docs only; push without force; report the real result.
Never claim a command, commit, push, fetch or subagent run you did not observe.
```

## Порядок дальше

1. **E1** (этот промпт): сценарий на 50 секунд с привязкой каждого предложения к источнику.
2. **Вы:** ответы по контакт-листам и решение по Kokoro.
3. **K1:** подключение Kokoro-инструмента и `finish_audio` в конвейер (тесты первыми).
4. **E2:** сборка среза (озвучка, монтаж по EDL, финальный звук, QC).

Перед E2 освободите место на диске: сейчас 820 МБ свободно, а рендер и клипы займут сотни мегабайт. Команды для проверки я давал выше. Пришлите вывод `du`, если не уверены, что удалять.

---

## [56] ВЫ · 2026-10-17 08:55 UTC
Если озвучку нельзя запустить в codespace давай запустим его в kaggle и построить между codespace и kaggle сеть чтобы команда из codespace шёл и запускал работу озвучки и потом звук обратно в codespace изучи и найди самый простой и лучший способ чтобы можно было полностью контролировать kaggle из codespace особенно агент

---

## [57] CLAUDE · 2026-10-17 08:56 UTC
Сначала проверяю, что сейчас актуально для управления Kaggle из командной строки и через MCP.

🔎 web_search: Kaggle API CLI kernels push status output KAGGLE_API_TOKEN KGAT authentication 2026 docs

🔎 web_search: Kaggle notebooks GPU quota 30 hours per week session limit 12 hours internet access requires phone verification save version commit run

## Сначала важное уточнение

Озвучка в Codespace **уже работает**: Kokoro на CPU дал скорость 1.6x реального времени, то есть минута звука синтезируется примерно за 1.6 минуты. Проблема не в запуске, а в диске (98% занято: `torch` и кэши). Поэтому Kaggle нужен для двух вещей: убрать тяжёлый стек из Codespace и дать место для будущих тяжёлых задач (генерация картинок и видео на GPU). Мост строить стоит.

## Самый простой и надёжный способ: официальный Kaggle CLI, без MCP

- Агент управляет Kaggle обычными командами в терминале. `kaggle kernels push` загружает код и метаданные ядра и сразу запускает его, а `kaggle kernels status` показывает, работает ли последний запуск, завершился успехом или упал. Результат забирается через `kaggle kernels output`.
- Рабочая схема из практики: правим локально, коммитим в git, пушим ядро одной командой и забираем вывод командой output. Это ровно то, что нужно агенту.
- Для ускорителя есть флаг: `--accelerator`, например NvidiaTeslaT4.
- Токен: поддерживается переменная окружения `KAGGLE_API_TOKEN`.
- **MCP не берём.** Сторонний `kaggle-mcp` даёт 51 инструмент и тоже требует ваш токен, но это лишняя зависимость и лишняя поверхность для атак, а настройка MCP у вас раньше уже вызывала проблемы. CLI делает то же самое проще.

**Чего CLI не умеет:** секреты Kaggle задаются только на сайте, из CLI их не создать. Нам это и не нужно, потому что вес Kokoro на HuggingFace публичный.

## Как будет устроен мост (протокол задач)

1. В Codespace агент создаёт папку задачи: `job.json` (входной текст, голос, параметры), `kernel-metadata.json`, `run.py`.
2. Мост-скрипт делает `kaggle kernels push`, затем опрашивает `status` с паузами и общим таймаутом.
3. Ядро на Kaggle ставит Kokoro, скачивает веса, синтезирует, пишет `output/<job_id>.wav` и `manifest.json` (sha256, длительность, версии, лицензия).
4. Мост забирает вывод, **сверяет sha256 и манифест**, запускает наш QC и только потом объявляет «успех». Любая ошибка (таймаут, `error`, пустой вывод) это `FAILED`/`BLOCKED`, а не тишина.
5. Один файл звука и один манифест на задачу (раньше у вас были проблемы с CLI при выгрузке сотен файлов).

Дополнительно: ядро **приватное**, одна «рабочая лошадка» и очередь задач по одной, никаких секретов в коде ядра, только текст туда и звук обратно. Входной текст небольшой, поэтому он встраивается в `run.py`, отдельный датасет Kaggle не нужен.

## Ограничения, о которых надо знать

- GPU: минимум 30 часов в неделю, сессия до 12 часов. Для GPU нужна верификация телефона.
- Фоновый запуск (то, что делает `push`) не зависит от интерактивной сессии: пакетная сессия неинтерактивна, а интерактивная тратит квоту даже когда ничего не считает. Для озвучки хватит CPU-режима, он экономит GPU-часы.
- Накладные расходы: старт ядра, установка пакетов и загрузка весов занимают минуты на каждую задачу. Для коротких озвучек в Codespace быстрее, мост выгоден для крупных задач.
- Квоты и условия Kaggle меняются, цифры выше из сторонних описаний, проверьте в вашем аккаунте.

## Ваши шаги (3 минуты, один раз)

1. На kaggle.com: аватар → **Settings → API → Create New Token**. Скопируйте токен (начинается с `KGAT_`).
2. На github.com: **Settings → Codespaces → Secrets → New secret**, имя `KAGGLE_API_TOKEN`, значение токен, доступ к репозиторию OpenMontage.
3. Перезапустите Codespace (Stop → Start), чтобы переменная появилась в терминале.
4. **Токен не вставляйте ни в чат со мной, ни в чат с агентом.** Агент увидит только то, что переменная задана.

## Промпт для Kilo (Milestone K0: проверка доступа и проект моста, без кода)

```text
MILESTONE K0 — Kaggle bridge preflight + design. Docs/reports only: no application code, no changes to the pipeline, no process/lock changes. Time-box 30 min. NEVER print, log or commit the token value: only report whether KAGGLE_API_TOKEN is set (yes/no) and its length. Roles inline: say so.
0. Preflight (look only): git status, HEAD, df -h /workspaces (report free space). Preserve user changes.
1. Reachability (max 6 requests, 20 s timeout each; record statuses as separate states): DNS + HTTPS to kaggle.com and api.kaggle.com. Classify: reachable | blocked | error.
2. Install the OFFICIAL CLI: pip install kaggle (package from Kaggle/kaggle-cli). Report version, install size, and that it did not enlarge /workspaces beyond a few MB. Do not install any third-party Kaggle MCP or wrappers.
3. Auth test, read-only: with KAGGLE_API_TOKEN set in the environment, run `kaggle kernels list --mine` (page size small). Report success/failure and the exact error class (no secrets in logs). If the variable is not set, STOP and report "owner must create the Codespaces secret KAGGLE_API_TOKEN and restart the codespace".
4. Read the installed CLI's help for `kernels push`, `status`, `output`, `list`, and check: does `push` support `--accelerator`, `--no-run`, a timeout option? What are the exact status strings returned by `status`? Quote from --help, do not guess.
5. Write docs/openmontage/KAGGLE_BRIDGE_DESIGN.md: the job protocol: job folder layout (job.json, kernel-metadata.json, run.py), a single private runner kernel (slug TBD) with serialized jobs, one wav + manifest.json per job (sha256, duration, library versions, license facts), push -> poll with backoff and total timeout -> output -> verify sha256/manifest -> run tools/qa/qc.py -> result JSON. Fail-closed table: each failure (auth, 409/conflict, queue, timeout, error status, empty output, hash mismatch) -> status + action. Constraints noted as UNVERIFIED: GPU 30 h/week, 12 h session, phone verification, internet toggle. Secrets rule: nothing secret inside the kernel; Kaggle Secrets cannot be set via CLI. Disk rule: after the bridge works, heavy packages (torch/kokoro) can be removed from the Codespace.
6. Propose the next milestones (K1: bridge code with tests using a fake `kaggle` executable on PATH + a live "hello" CPU job; K2: Kokoro job end-to-end). No implementation now.
7. Update checkpoint/work log (observed vs assumed). Commit docs only; push without force; report the real result.
Never claim a command, install, commit or push you did not observe.
```

Если на шаге 3 агент напишет «переменная не задана», значит шаги 1-3 из моего списка ещё не сделаны. После K0 пришлите отчёт. Дальше K1 (код моста с тестами и живой «hello»-задачей), потом K2 (озвучка целиком).

---

## [58] ВЫ · 2026-10-17 09:04 UTC
_(без текста)_
_Вложения: Screenshot_20261017_140354.jpg_

---

## [59] CLAUDE · 2026-10-17 09:04 UTC
## Что показал отчёт K0

**Всё сделано правильно, и остановка на шаге 3 тоже правильная:** агент не нашёл `KAGGLE_API_TOKEN` и не пошёл дальше.

- Диск: свободно **3.2 ГБ** (занято 90%), стало лучше.
- `kaggle.com` и `api.kaggle.com` из Codespace доступны.
- CLI `kaggle` 2.2.4 установлен (1.3 МБ), сторонних надстроек нет.
- Два расхождения с тем, что я писал: в установленной версии **нет флага `--no-run`** (в документации в репозитории он был), и **точные названия статусов (`status`) в `--help` не указаны.** Поэтому мост не должен «угадывать» строки статусов: их надо взять из реального запуска. Это заложено в K1.

## Ваш шаг (то, что сейчас блокирует работу)

1. kaggle.com → аватар → **Settings → API → Create New Token**, скопируйте токен (начинается с `KGAT_`).
2. github.com → **Settings → Codespaces → Secrets → New secret**: имя `KAGGLE_API_TOKEN`, значение токен, репозиторий OpenMontage.
3. Перезапустите Codespace (Stop → Start). Если переменная всё равно пустая, сделайте Rebuild.
4. **Токен не отправляйте ни мне, ни агенту.**

Проверка без показа токена (в терминале):

```bash
[ -n "$KAGGLE_API_TOKEN" ] && echo "set" || echo "not-set"
kaggle kernels list --mine --page-size 5
```

Если первая строка выдала `set`, а вторая список (или пустой список без ошибки), всё готово. Если ошибка авторизации, пришлите мне текст ошибки (без токена).

## Промпт для Kilo (Milestone K1: код моста с тестами + живая проверка)

Запускайте только после успешной проверки выше.

```text
MILESTONE K1 — Kaggle bridge code (test-first) + one live "hello" CPU job. Time-box 50 min. NEVER print, log, commit or pass on a command line the token value. No GPU, no datasets, no Kaggle Secrets, no third-party Kaggle wrappers/MCP. Roles inline: say so.
0. Preflight (look only): git status, HEAD, df -h /workspaces. Check `[ -n "$KAGGLE_API_TOKEN" ]` (yes/no only). If not set -> STOP and report. Run `kaggle kernels list --mine --page-size 5`; if it fails -> STOP and report the error class. Read docs/openmontage/KAGGLE_BRIDGE_DESIGN.md first and follow it. Preserve user changes.
1. Failing tests first (put the module under tools/kaggle_bridge/, follow repo conventions; stdlib only, subprocess without shell=True). Tests use a FAKE `kaggle` executable placed first on PATH in a tmp dir that simulates: push OK; status sequence queued->running->complete; status error; status never finishing (total-timeout => BLOCKED); an UNKNOWN status string (non-terminal until timeout, then BLOCKED, never success); output missing manifest; sha256 mismatch; empty output; auth failure (non-zero exit); 409/conflict on push (bounded retry, then BLOCKED). Also assert: the token never appears in logs/args/result JSON; backoff and timeouts are honored; fail-closed on anything unparseable. Show the red result.
2. Implement build_job_folder (generate kernel-metadata.json from `kaggle kernels init` output, do not guess field names), push (use -t/--timeout to bound the run), poll with backoff and total timeout, fetch_output, verify (manifest: job_id, files[{name,sha256,bytes}], created_utc, versions), and a result JSON. Success requires verified manifest + matching sha256; anything else is BLOCKED/FAILED.
3. Green tests; run new tests AND the existing fast suite; report exact commands and exit codes.
4. LIVE smoke job (real Kaggle, ONE push): private kernel, CPU only, enable_gpu false, enable_internet false, code uses only Python stdlib: writes hello.txt and manifest.json (sha256, bytes, created_utc, python version) into /kaggle/working. Kernel slug <owner>/of-bridge-runner where <owner> is read from the CLI/config output (do not guess; if not determinable, STOP and ask). Poll every >=15 s up to 15 min; RECORD EVERY DISTINCT STATUS STRING observed, plus timings (push->running, running->complete, output download) and any CLI quirks. Download output into the gitignored projects/ area, verify through the bridge's own verify step, show the result JSON.
5. Update KAGGLE_BRIDGE_DESIGN.md: replace UNVERIFIED items with observed facts (status strings, timings, --no-run absence, timeout option behavior); keep everything else marked UNVERIFIED.
6. Update checkpoint/work log (observed vs assumed). Commit code+tests+docs; push without force; report the real result.
Never claim a test, command, push, commit or Kaggle run you did not observe.
```

После K1 пришлите отчёт, дальше K2 (озвучка Kokoro на Kaggle, с проверкой скорости и качества против Codespace).

---

## [60] ВЫ · 2026-10-17 12:23 UTC
_(без текста)_
_Вложения: Screenshot_20261017_140807.jpg_

---

## [61] CLAUDE · 2026-10-17 12:23 UTC
Агент остановился правильно: токена нет. Но в его выводе есть более простой путь: вход через OAuth. Проверяю, как он работает в удалённом терминале.

🔎 web_search: kaggle auth login OAuth headless --no-launch-browser kaggle-cli authentication docs credentials cached

## Что произошло

Агент остановился ровно там, где должен: переменной `KAGGLE_API_TOKEN` в терминале нет, поэтому `kaggle kernels list --mine` вернул «Authentication required». Ничего не сломано и ничего не потеряно: код моста не писался, лишних запусков на Kaggle не было. Промпт K1 остаётся прежним, его нужно будет отправить после успешной авторизации. Пока токена нет, повторно слать его не стоит (потеряете минуту).

## Два способа авторизации

**Вариант A: токен в Codespaces Secrets (надёжный, я его описывал).**
1. kaggle.com → аватар → **Settings → API → Create New Token** (скопируйте значение, оно начинается с `KGAT_`).
2. github.com → **Settings → Codespaces → Secrets → New secret**: имя `KAGGLE_API_TOKEN`, значение токен, доступ к репозиторию OpenMontage.
3. Перезапустите Codespace (Stop → Start). Если переменная всё ещё пустая, сделайте Rebuild.

**Вариант B: вход через OAuth, без токена.** В тексте ошибки сам CLI советует `kaggle auth login` и пишет, что токен не нужен, а учётные данные сохраняются локально. Но я не нашёл документации о том, как этот вход работает в удалённом терминале (нужен ли локальный адрес обратного вызова, есть ли режим «без браузера»), поэтому **это не проверено**. Попробовать можно за минуту:

```bash
kaggle auth login --help
```

Если в справке есть режим без браузера (что-то вроде вывода ссылки или кода для ввода), запустите `kaggle auth login`, откройте показанную ссылку в браузере телефона и подтвердите вход. Если справка про браузер на той же машине (Codespace его не имеет), переходите к варианту A.

## Проверка (без показа токена)

```bash
[ -n "$KAGGLE_API_TOKEN" ] && echo "set" || echo "not-set"
kaggle kernels list --mine --page-size 5
```

Вторая команда должна вывести список (пустой список тоже нормально) без ошибки. Если вход был через OAuth, первая строка может показать `not-set`, а вторая всё равно сработает: это допустимо.

Если будет ошибка, пришлите мне её текст (без токена). Когда вторая команда проходит, отправляйте агенту промпт K1 без изменений.

Заодно: батарея телефона на 18%. Codespace продолжает работать независимо от телефона, но для этих шагов лучше поставить его на зарядку.

---

## [62] ВЫ · 2026-10-17 12:35 UTC
Всё что дальше
_Вложения: Screenshot_20261017_173504.jpg_

---

## [63] CLAUDE · 2026-10-17 12:35 UTC
## Секрет добавлен правильно

На скриншоте `KAGGLE_API_TOKEN` в списке секретов репозитория, значение скрыто. Теперь он должен попасть в терминал Codespace, но **только после перезапуска.**

## Шаг 1: перезапустить Codespace (2 минуты)

1. Откройте в браузере **github.com/codespaces**.
2. Напротив вашего Codespace нажмите **«…» → Stop codespace.**
3. Подождите, пока статус станет «Stopped», затем нажмите на название, чтобы открыть заново.

Файлы репозитория при этом сохраняются. Возможна потеря временных данных: веса Kokoro лежат в `/tmp`, при необходимости они скачаются заново (~313 МБ).

## Шаг 2: проверка (в терминале, без показа токена)

```bash
[ -n "$KAGGLE_API_TOKEN" ] && echo "set" || echo "not-set"
kaggle kernels list --mine --page-size 5
```

Нужен результат: `set`, затем список ядер (пустой тоже нормально) без «Authentication required». Если там `not-set`, значит Codespace не подхватил секрет: сделайте **Rebuild** (в меню «…» рядом с Codespace или в палитре команд VS Code «Codespaces: Rebuild Container») и проверьте снова. Если ошибка другая, пришлите её текст мне, токен не присылайте.

## Шаг 3: запустить K1 (промпт без изменений)

```text
MILESTONE K1 — Kaggle bridge code (test-first) + one live "hello" CPU job. Time-box 50 min. NEVER print, log, commit or pass on a command line the token value. No GPU, no datasets, no Kaggle Secrets, no third-party Kaggle wrappers/MCP. Roles inline: say so.
0. Preflight (look only): git status, HEAD, df -h /workspaces. Check `[ -n "$KAGGLE_API_TOKEN" ]` (yes/no only). If not set -> STOP and report. Run `kaggle kernels list --mine --page-size 5`; if it fails -> STOP and report the error class. Read docs/openmontage/KAGGLE_BRIDGE_DESIGN.md first and follow it. Preserve user changes.
1. Failing tests first (put the module under tools/kaggle_bridge/, follow repo conventions; stdlib only, subprocess without shell=True). Tests use a FAKE `kaggle` executable placed first on PATH in a tmp dir that simulates: push OK; status sequence queued->running->complete; status error; status never finishing (total-timeout => BLOCKED); an UNKNOWN status string (non-terminal until timeout, then BLOCKED, never success); output missing manifest; sha256 mismatch; empty output; auth failure (non-zero exit); 409/conflict on push (bounded retry, then BLOCKED). Also assert: the token never appears in logs/args/result JSON; backoff and timeouts are honored; fail-closed on anything unparseable. Show the red result.
2. Implement build_job_folder (generate kernel-metadata.json from `kaggle kernels init` output, do not guess field names), push (use -t/--timeout to bound the run), poll with backoff and total timeout, fetch_output, verify (manifest: job_id, files[{name,sha256,bytes}], created_utc, versions), and a result JSON. Success requires verified manifest + matching sha256; anything else is BLOCKED/FAILED.
3. Green tests; run new tests AND the existing fast suite; report exact commands and exit codes.
4. LIVE smoke job (real Kaggle, ONE push): private kernel, CPU only, enable_gpu false, enable_internet false, code uses only Python stdlib: writes hello.txt and manifest.json (sha256, bytes, created_utc, python version) into /kaggle/working. Kernel slug <owner>/of-bridge-runner where <owner> is read from the CLI/config output (do not guess; if not determinable, STOP and ask). Poll every >=15 s up to 15 min; RECORD EVERY DISTINCT STATUS STRING observed, plus timings (push->running, running->complete, output download) and any CLI quirks. Download output into the gitignored projects/ area, verify through the bridge's own verify step, show the result JSON.
5. Update KAGGLE_BRIDGE_DESIGN.md: replace UNVERIFIED items with observed facts (status strings, timings, --no-run absence, timeout option behavior); keep everything else marked UNVERIFIED.
6. Update checkpoint/work log (observed vs assumed). Commit code+tests+docs; push without force; report the real result.
Never claim a test, command, push, commit or Kaggle run you did not observe.
```

## Что дальше, по порядку

Пока K1 работает, можно параллельно (в другой вкладке терминала, после завершения K1 не мешая ему) готовить остальное. Очередь:

1. **K1:** мост на Kaggle, «hello»-задача.
2. **K2:** озвучка Kokoro на Kaggle, сравнение скорости с Codespace (я пришлю промпт после отчёта K1).
3. **E1:** реестр утверждений и сценарий на 50 секунд (промпт из моего сообщения про NASA Facts и TM-4084, если вы его ещё не запускали).
4. **Ваши решения:** ответы по 11 контакт-листам клипов и согласие по голосу Kokoro (с родителем).
5. **K3:** подключение Kokoro и `finish_audio` в конвейер (тесты первыми).
6. **E2:** сборка среза 30-60 секунд: озвучка, монтаж, финальный звук, QC.

Пришлите отчёт K1, когда он завершится.

---

## [64] ВЫ · 2026-10-17 13:04 UTC
Может не Кокоро а какойто  другой который хороший в английском языке и эмоциональный и ТД и про футажи дай мне ссылки и список сайтов где мы будем получать футажи но по больше изучай сайты которые дают бесплатно или репозиторий который даёт бесплатном доступе все сайты с футажами

---

## [65] CLAUDE · 2026-10-17 13:05 UTC
Исследую обе темы: голоса получше Kokoro и полный набор бесплатных источников футажей.

🔎 web_search: best open source expressive TTS 2026 narration emotion Chatterbox Orpheus Qwen3-TTS Higgs Audio Maya1 license Apache MIT commercial comparison

Голоса разобраны. Теперь футажи: ищу репозиторий-каталог бесплатных источников.

🔎 web_search: GitHub awesome list free stock footage public domain video sources archive collection repository

## Голос: что лучше Kokoro для «эмоционально и по-английски»

Kokoro быстрый и безопасный по лицензии, но управлять эмоциями в нём нечем. Нашёл три сильных кандидата с разрешающей лицензией:

| Модель | Лицензия | Чем хороша | Железо |
|---|---|---|---|
| **Chatterbox / Chatterbox Turbo** | MIT | Параметр «exaggeration» (сила эмоции) и теги вроде `[laugh]` | Turbo (англ., 350M) 4-8 ГБ видеопамяти, T4 на Kaggle хватает |
| **Maya1** | Apache-2.0 | «Дизайн голоса» текстом (опишите диктора), теги смеха, шёпота и т. п., 3B, только английский | нужен GPU |
| **Qwen3-TTS** | Apache-2.0 | Подача описывается словами, есть VoiceDesign | нужен CUDA GPU, без него медленно |

- Chatterbox: лицензия MIT, управление «преувеличением» эмоции, Maya1: Apache 2.0, создан для выразительного дизайна голоса с тегами смеха, плача и шёпота.
- Для коммерческих проектов с разрешающими лицензиями сильнее всего Orpheus (теги вроде `<sigh>`), Chatterbox (exaggeration и `[laugh]`) и Qwen3-TTS (инструкции обычными словами).

**Что надо знать:**
- **Нельзя** использовать для публичных видео: Higgs Audio V3 (только исследования и некоммерческое использование), Breeze TTS 2 (только исследования и некоммерческое, хоть и первый по рейтингу), IndexTTS-2.5 (лицензия ограничивает коммерческое использование). Из прошлых проверок также XTTS, F5-TTS (веса) и Fish Speech.
- **Источники расходятся по Orpheus:** одни называют лицензию Apache-2.0, другие пишут, что код под Apache, а веса наследуют ограничения лицензии Llama. До проверки по официальной карточке модели его не берём.
- **Chatterbox ставит в звук скрытый водяной знак:** Perth Watermarker, неслышимая нейросетевая метка, переживающая сжатие. Для YouTube это не мешает, но пометьте в реестре рисков.
- **Клонирование чужого голоса не используем:** нужны права на эталонную запись. Нужен либо стандартный голос, либо «дизайн голоса» текстом (Maya1, Qwen3-TTS).
- **Рейтинги ненадёжны.** По одному из них Kokoro набирает 1064, а Chatterbox 1026, то есть по общей естественности Kokoro даже выше, а Chatterbox выигрывает только управляемостью эмоций. Источник (Cartesia) сам продаёт TTS, это возможная предвзятость. **Решать будет ваш слух, не таблицы.**

**План:** голосовой «бой» на Kaggle: одни и те же 60 секунд сценария (про CID) озвучить Kokoro, Chatterbox Turbo и Maya1, вы слушаете вслепую (без подписей) и выбираете. Это и будет K2.

## Где брать футажи

**Уровень A: основа для нашей ниши (авиация и космос, история).** Права по политике источников, не по каждому файлу:

| Источник | Ссылка | Что есть | Права (кратко) |
|---|---|---|---|
| NASA Image and Video Library | https://images.nasa.gov | Видео и фото миссий, летные испытания | в основном не защищено авторским правом США, исключения: эмблемы, люди, третьи лица |
| NASA SVS (визуализации) | https://svs.gsfc.nasa.gov | Научные анимации | проверить по странице |
| Internet Archive, Moving Image | https://archive.org/details/movies | Миллионы видео | у каждого файла своя лицензия |
| Prelinger Archives | https://archive.org/details/prelinger | Научно-популярные, промышленные и учебные фильмы | много общественного достояния, проверять каждый |
| IA Stock Footage | https://archive.org/details/stock_footage | Клипы для вставки | Creative Commons, проверять |
| Library of Congress | https://www.loc.gov/free-to-use/ | Коллекции «free to use» | проверять оговорки по элементу |
| US National Archives | https://catalog.archives.gov | Государственные фильмы | в основном государственные работы США |
| DVIDS | https://www.dvidshub.net | Военная авиация и техника | государственная работа, нужно указывать автора |
| Wikimedia Commons | https://commons.wikimedia.org/wiki/Category:Videos | Видео, свободные лицензии | у каждого файла своя |
| Open Beelden (NL) | https://www.openbeelden.nl | Нидерландский архив | CC (использовали в пилоте) |

**Уровень B: осторожно, нужна атрибуция или ограничения:** Vimeo Creative Commons (группы по типу лицензии), Mazwai, Videezy, Vidsplay (нужна атрибуция).

**Уровень C: общие стоки только для атмосферных вставок.** Не для архивных кадров:
- Pexels https://www.pexels.com/videos/ , Pixabay https://pixabay.com/videos/ (осторожнее: лицензия Pixabay с ограничениями), Mixkit https://mixkit.co/free-stock-video/ , Coverr https://coverr.co .

**Прочее найденное:** B-roll Национальной службы парков США и Public Domain Project от Pond5 (статус Pond5 сейчас не проверял), CDC B-roll (государственная работа, общественное достояние).

**Репозитории-каталоги** (то, что вы просили):
- https://github.com/neutraltone/awesome-stock-resources : список ссылок на бесплатные сайты фото, видео и иллюстраций. Одна из тем-страниц показывает, что часть форков и перепечаток давно не обновлялась, поэтому каждую ссылку проверять.
- https://commons.wikimedia.org/wiki/Commons:Free_media_resources/Video : курируемый список свободных видеоисточников.
- В OpenMontage уже есть адаптеры для Archive.org, NASA, Wikimedia, Pexels, Pixabay.

**Оговорки:** «бесплатно» не значит «разрешено везде». Права проверяются по каждому клипу или по политике источника, а YouTube отдельно требует оригинальной добавленной ценности. Ссылки глубже корневых страниц я не проверял, адаптеры проверят их живьём.

## Два промпта

**1. Milestone FS1 (реестр источников футажей, документы + проверки):**

```text
MILESTONE FS1 — footage source registry + keyless probing. Docs/reports only: no application code, no installs, no process/lock changes. Time-box 40 min. Free access only; BLOCKED if a key/registration is needed (do not register). Max 30 network requests, 20 s timeout, use curl -L. ERROR/HTTP status/EMPTY are separate states. Roles inline: say so.
0. Preflight (look only): git status, HEAD. Preserve user changes.
1. Create docs/openmontage/footage/SOURCE_REGISTRY.md (and a machine-readable footage_sources.yaml if the repo has a convention for it). One row per source with: name, root URL, content type, search method (API keyless | API key required | web only), rights policy page URL (official page, retrieved date), default rights_basis (explicit_license | source_policy_us_gov | per_item_license | unknown), attribution required (yes/no/unknown), existing adapter in the repo (path or MISSING), probe result. Sources: NASA Image and Video Library, NASA SVS, Internet Archive (Moving Image, Prelinger, stock_footage), Library of Congress (free-to-use), US National Archives catalog, DVIDS, Wikimedia Commons, Open Beelden, Europeana, Smithsonian Open Access, NPS B-roll, CDC B-roll, Vimeo CC, Pexels, Pixabay, Mixkit, Coverr, Videezy, Mazwai, Vidsplay, Pond5 Public Domain Project (status unknown: verify it still exists).
2. For each, fetch the OFFICIAL rights/terms page (not blogs) and record a short paraphrase of: commercial use, attribution, restrictions (logos, persons, third-party). Mark UNKNOWN if not stated. Pexels/Pixabay/Mixkit/Coverr: record the exact restrictions on redistribution and on use in monetized video.
3. Probe keyless search for the top 6 (NASA, IA, Wikimedia, LoC, NARA, DVIDS): one small query ("Boeing 720 controlled impact" or the nearest equivalent), record HTTP status, whether a key is required, and which fields expose rights/credit. Do not download media.
4. Compare with the repo's existing adapters; list MISSING adapters and which are worth writing (keyless + clear rights policy). Do not write them now.
5. Add the awesome-lists (neutraltone/awesome-stock-resources; Wikimedia Commons Free_media_resources/Video) as REFERENCE ONLY: do not copy their lists blindly; every source used must pass steps 1-3.
6. Report observed vs assumed; update checkpoint/work log. Commit docs only; push without force; report the real result.
Never claim a command, fetch, commit or push you did not observe.
```

**2. K2 в новой редакции (после успешного K1): голосовой «бой» на Kaggle.** Я пришлю его сразу после отчёта K1, потому что он зависит от реальных статусов Kaggle, которые K1 запишет. Что в нём будет: те же 60 секунд, три движка (Kokoro, Chatterbox Turbo, Maya1), лицензии из официальных карточек моделей, замер скорости, финальная обработка звука для всех трёх, и пронумерованные файлы без названий моделей, чтобы вы слушали вслепую.

---

## [66] ВЫ · 2026-10-17 13:46 UTC
Выбери самый лучший программу для озвучки сам и все k1,2,3 и остальные в один промп чтобы закончить всё за раз и потом сделаем глобальную проверку
_Вложения: Screenshot_20261017_184503.jpg_

---

## [67] CLAUDE · 2026-10-17 13:48 UTC
## Результат K1

**Мост Kaggle работает.** Коммит `21903ee`, 16 тестов проходят, живая «hello»-задача прошла полный цикл: приватное ядро `forts845/of-bridge-runner`, статус `KernelWorkerStatus.COMPLETE`, файл получен, sha256 сверен. Узнали три важных факта:
1. Название ядра должно превращаться в ту же строку, что и его идентификатор, иначе будет ошибка 409.
2. Флага `--no-run` в CLI нет.
3. Тестовое ядро работало **без интернета**. Для озвучки интернет нужен (установка пакетов и загрузка весов). Если Kaggle его не включит, вероятная причина это непройденная верификация телефона, агент должен остановиться и сказать вам.

## Выбор голоса (моё решение)

Основной: **Chatterbox Turbo (MIT).** Причины: лицензия разрешает коммерческое использование, есть управление эмоциями, английский, помещается в видеопамять Kaggle T4. Запасные по порядку: Maya1 (Apache-2.0, «дизайн голоса» текстом), затем Kokoro (уже проверен). Честно: **слушать их я не могу**, поэтому порядок предпочтений мой, а брак отсекают измерения (распознавание речи обратно в текст, громкость, тишина, обрезка). Вам останутся слепые файлы A/B/C для прослушивания, это необязательное и не блокирующее решение. Клонирование чужих голосов запрещено правилами промпта.

## Один большой промпт

Одна сессия на всё рискованнее, чем отдельные вехи, поэтому я встроил защиты: **файл состояния** (`MASTER_RUN_STATE.md`), коммит после каждой фазы, возможность продолжить с места остановки, блокировка вместо тихого пропуска и остановка при нехватке диска. Ожидайте несколько часов.

```text
MASTER RUN — voice bake-off on Kaggle, TTS integration, footage registry, evidence+script, 50 s technical slice, global check. ONE session with checkpoints.

GLOBAL RULES
- State file docs/openmontage/MASTER_RUN_STATE.md. At start: read it if it exists and RESUME at the first phase not DONE. After EVERY phase: update it (DONE|BLOCKED|SKIPPED + evidence + commit hash), commit, push non-force.
- Phases run P1->P7. A BLOCKED phase never silently skips: record the exact blocker + owner action; continue only with phases that do not depend on it.
- Max 2 fix attempts per blocker, then BLOCKED.
- NEVER print/log/commit/pass on a command line KAGGLE_API_TOKEN or any secret; env checks yes/no only. No registrations, no other credentials, no paid routes, no third-party Kaggle wrappers/MCP, no voice cloning of any third-party or real person's voice.
- Network allowed only: kaggle via the CLI/bridge, images-api.nasa.gov, nasa.gov, archive.org (curl -L), official license/terms pages, Hugging Face/GitHub/PyPI pages for LICENSE evidence. NTRS is known blocked: do not retry.
- ERROR / HTTP status / EMPTY are separate states. Never guess file names (use metadata listings). Fail-closed: anything unmeasured is BLOCKED or NOT_RUN, never PASS.
- Disk: df -h /workspaces before each heavy step; if free < 800 MB write state and STOP the whole run. Downloads only into gitignored projects/ or /tmp, never committed; delete temp files you created.
- Code is test-first (show red, then green); run new tests AND the existing fast suite; report exact commands and exit codes.
- Roles inline: say "inline, not independent". Never claim a command/test/commit/push/Kaggle run you did not observe. Report measured numbers only; do NOT judge audio/video "quality" or "naturalness".
- Preflight at start: git status, HEAD, df, `[ -n "$KAGGLE_API_TOKEN" ]` (yes/no), `kaggle kernels list --mine --page-size 5`. If auth fails: STOP.

P1 VOICE LICENSE EVIDENCE (docs). Candidates in preference order (chosen by Claude/owner): (1) Chatterbox Turbo (Resemble AI; fall back to base Chatterbox if Turbo is unavailable), (2) Maya1, (3) Kokoro-82M. From OFFICIAL repo/model-card files record: code license, weights license, training-data statement, commercial-use statement, watermarking, whether a reference audio clip is REQUIRED (if required, only a clip we generated ourselves is allowed, else the candidate is excluded), VRAM need. Also the license of the ASR checker (faster-whisper/openai-whisper + weights). Exclude any research-only/non-commercial license. Write docs/openmontage/VOICE_BAKEOFF_LICENSES.md. A candidate without verified permissive code+weights evidence is excluded.

P2 EVIDENCE LEDGER + SCRIPT (docs). If docs/openmontage/evidence/CID_CLAIM_LEDGER.md and docs/openmontage/slice/CID_SLICE_SCRIPT_v0.md already exist, verify and skip. Otherwise create them. Provenance for claims: "extracted by Claude from full text of NASA Facts FS-2009-02-003-DFRC and NASA TM-4084 (Horton & Kempel), retrieved 2026-10-17; NTRS blocked from this sandbox". Try ONCE to fetch the NASA Facts PDF from nasa.gov (https://www.nasa.gov/centers/dryden/pdf/315492main_FS-2009-02-003-CID.pdf); if reachable, mark FS-derived claims AGENT_VERIFIED_TEXT. Paraphrase only. Claims (do not add others): CID-01 On 1 Dec 1984 the remotely piloted Boeing 720 flew the 15th and final flight and was crash-landed at Edwards [FS;TM] TWO. CID-02 Obsolete four-engine 720 obtained from the FAA [FS;TM] TWO. CID-03 Purpose: test FM-9 anti-misting fuel additive to reduce post-crash fire; also structural data and seat/restraint tests [FS;TM] TWO. CID-04 No flight crew aboard on the final flight; flown from a ground cockpit; FS names NASA research pilot Fitzhugh Fulton [FS;TM] name SINGLE. CID-05 Before the final flight: 14 test flights with crew aboard, 10 remote takeoffs, 13 remote landings, 69 approaches to the impact site, 16 h 22 min of remote control [FS;TM] TWO. CID-06 In practice the airplane was never flown lower than 150 ft above ground toward the impact site [TM] SINGLE. CID-07 Below 150 ft the airplane was committed to impact [FS;TM] TWO. CID-08 At the decision point it was slightly right of centerline; the pilot judged altitude sufficient and continued [FS;TM] TWO. CID-09 Left wing hit first, short of the wing cutters [FS;TM] TWO; TM numeric table values are OCR_UNVERIFIED (do not use numbers). CID-10 A cutter struck the right inboard engine, massive fuel leak ignited, right wing broke off, fireball, fire > 1 hour [FS] SINGLE. CID-11 76,000 lb of modified fuel on board [FS] SINGLE. CID-12 Takeoff weight 200,500 lb [TM] SINGLE. CID-13 In the full-scale test the modified fuel was ineffective at reducing fire; FAA additive requirements were cancelled [FS] SINGLE, LOAD-BEARING, needs a second source. CID-14 Ground pilot had poor depth perception via a 525-line monitor; tracking radar accuracy insufficient [TM] SINGLE. CID-15 From the remote-piloting standpoint the program was considered a success though not all impact parameters were met [TM] SINGLE. CID-16 Cabin cameras showed dummies shaken, seats stayed attached; data informed new FAA fire-prevention/fire-retardant rules [FS] SINGLE.
Script (one sentence per line, with claim_ids; status DRAFT, NOT_PUBLISHABLE): S1 "On December first, 1984, NASA crashed a Boeing 720 airliner on purpose." [CID-01] S2 "Nobody was on board. A pilot flew it by remote control from the ground." [CID-04] S3 "The goal was to test a fuel additive meant to stop crash fires." [CID-03] S4 "Before the real thing, the team flew fourteen test flights with crews aboard and practiced sixty-nine approaches to the crash site." [CID-05] S5 "But in practice, the airplane had never flown lower than a hundred and fifty feet toward the crash site." [CID-06] S6 "On the real flight, it arrived slightly off the centerline, and its left wing hit first." [CID-08, CID-09] S7 "The fuel ignited into a fireball that burned for more than an hour." [CID-10] S8 "And the additive that had worked in small tests did not reduce the fire at full scale." [CID-13]. Mark S5, S7, S8 as depending on SINGLE_SOURCE claims; S8 is BLOCKED for publication until CID-13 has a second source. Run the QC module's claim_ids check on script+ledger and show the real output (adapt docs to the tool, not the tool to the docs).

P3 KAGGLE VOICE BAKE-OFF (needs P1+P2; ONE GPU job, one retry allowed). Reuse the bridge and the private runner kernel (title must slugify to the id suffix). Job settings: enable_internet=true, accelerator NvidiaTeslaT4 via --accelerator. If Kaggle refuses internet/GPU, STOP the phase as BLOCKED with the exact error and the owner action (e.g., verify phone number in Kaggle settings). Job code (no secrets): install needed libs (record versions), download weights from Hugging Face, synthesize the script sentence by sentence for each candidate that passed P1 in preference order (Maya1 only if total GPU job time stays <= 40 min), concatenate with short pauses, measure real-time factor, transcribe each output with Whisper for word timestamps and WER vs the script (normalized text), detect clipping/silence. Outputs (<= 12 files): <engine>.wav, words_<engine>.json, metrics.json, manifest.json (sha256, bytes, library versions, license facts, watermark note). Record GPU time used. Download via the bridge, verify sha256/manifest, then run tools/qa/qc.py and tools/audio/finish_audio.py on each wav and record LUFS/true peak before/after.
Selection rule (document in docs/openmontage/VOICE_DECISION.md; thresholds are INITIAL GUESSES): winner = first engine in preference order that passes ALL: P1 license gate; WER <= 8%; no truncation (duration >= 0.8 x words/150 wpm); QC silence/clipping within config thresholds. Create blind files projects/voice_blind/A.wav,B.wav,C.wav (shuffled) and a SEPARATE mapping file; owner listening is optional, owner veto allowed, not blocking. Record residual risks: training-data provenance, watermark (if any), no cloning used.

P4 TTS INTEGRATION (test-first; needs P3 or at least P1). Implement the TTS tool per KOKORO_TTS_PROPOSAL.md conventions (e.g. tools/audio/tts_kaggle.py): text+job_id -> bridge job -> verified wav + words.json. config/voice.json with engine, license_status, fallback. LICENSE GATE: engines with unknown/blocked license (e.g., Piper en_US-lessac-medium) must be REFUSED in code. If the bridge is BLOCKED, fall back to local Kokoro (CPU) if installed, otherwise return BLOCKED (never silent success). Tests with a fake bridge: success; bridge BLOCKED -> fallback; license unknown -> refuse; hash mismatch -> reject; token never in logs. Wire finish_audio after TTS and make loudness verification run on the FINAL MP4 (AAC re-encode can raise true peak). Update AGENTS.md and docs.

P5 FOOTAGE SOURCE REGISTRY (docs + probes; independent of P2-P4). Create docs/openmontage/footage/SOURCE_REGISTRY.md (+ footage_sources.yaml if the repo has a convention). One row per source: name, root URL, content type, search method (API keyless | key required | web only), OFFICIAL rights page URL + retrieved date, default rights_basis (explicit_license | source_policy_us_gov | per_item_license | unknown), attribution required, existing adapter in repo (path|MISSING), probe result. Sources: NASA Image and Video Library; NASA SVS; Internet Archive (Moving Image, Prelinger, stock_footage); Library of Congress free-to-use; US National Archives catalog; DVIDS; Wikimedia Commons; Open Beelden; Europeana; Smithsonian Open Access; NPS B-roll; CDC B-roll; Vimeo CC; Pexels; Pixabay; Mixkit; Coverr; Videezy; Mazwai; Vidsplay; Pond5 Public Domain Project (verify it still exists). Fetch only official terms pages; paraphrase restrictions (commercial use, attribution, logos, persons, third-party material); Pexels/Pixabay/Mixkit/Coverr: record redistribution limits and monetized-video use. Probe keyless search for NASA, IA, Wikimedia, LoC, NARA, DVIDS with one small query each (max 30 requests, 20 s timeout, no media downloads); record whether a key is required and which fields expose rights/credit. List MISSING adapters worth writing (keyless + clear rights policy); do NOT write them. Treat awesome-stock-resources and Wikimedia Commons Free_media_resources/Video as REFERENCE ONLY.

P6 TECHNICAL SLICE ~50 s (needs P2, P3/P4; may use NEEDS_REVIEW clips; output is NOT_PUBLISHABLE). Select 3-6 clips for script beats from the C4/C6 review queue and coverage map: only clips with rights_basis explicit_license or source_policy_us_gov and NO third-party credit; never REJECT clips. Download with curl -L using the REAL derivative names from archive.org metadata; total cap 250 MB; record sha256. Build: narration from the P3/P4 winner; EDL with a written rationale per cut (edit/edl.json); pacing lint per EDITING_DOCTRINE; subtitles from word timestamps (cue grouping, <= 2 lines); source cards (NASA Facts FS-2009-02-003-DFRC, NASA TM-4084) as on-screen text; credits.txt listing every clip (id, creator, URL, rights_basis); 1920x1080 30 fps H.264/AAC via ffmpeg; run finish_audio; run tools/qa/qc.py on the FINAL MP4 including claim_ids, rights_basis, credits_complete, added_value, ebur128 -> qa_report.json. Metadata flag NOT_PUBLISHABLE with reasons: unreviewed clip flags (persons/logos), single-source claims, voice owner sign-off, S8 blocked. Output to projects/slice_cid_v0/ (gitignored); also a contact sheet of ~12 frames of the final video.

P7 GLOBAL CHECK. Write docs/openmontage/GLOBAL_CHECK_2026-10-17.md: (a) full table of phases with status and commit hashes; (b) all tests run now (new + existing) with exact commands/exit codes; (c) ffprobe + full decode + qa_report summary for the slice; (d) repo hygiene: git status, no secrets/media committed (check with git grep/ls-files for large or secret-like files, never printing a token), disk free; (e) every open gate (voice license, rights flags, single-source claims, insignia decision, guardian/AdSense, Kokoro/Chatterbox risk sign-off, Content ID/music policy); (f) docs/openmontage/OWNER_ACTIONS.md: numbered, minimal steps for the owner (listen to blind A/B/C; review contact sheets with the 3 questions; sign-offs); (g) print in the terminal the exact text the owner can paste to run an independent read-only review: "@qa-reviewer Review docs/openmontage/GLOBAL_CHECK_2026-10-17.md and projects/slice_cid_v0/qa_report.json, read-only. Report PASS/REVIEW/BLOCKED with evidence per check." Commit docs/code/tests only; push non-force; final report: phases DONE/BLOCKED, key measured numbers, one exact next action.
```

## Пока агент работает

- Телефон на 13%: поставьте на зарядку и держите вкладку открытой. По умолчанию Codespace может остановиться из-за простоя (около 30 минут по умолчанию), этот срок можно увеличить в настройках GitHub Codespaces, проверьте там «idle timeout».
- Если сессия оборвётся, просто напишите агенту: «Resume the MASTER RUN from docs/openmontage/MASTER_RUN_STATE.md», он продолжит с последней завершённой фазы.

## После завершения

Пришлите мне скриншоты финального отчёта (P7) и файла `OWNER_ACTIONS.md`. Потом сделаем глобальную проверку: я посмотрю результаты как независимый ревьюер, вы послушаете слепые файлы A/B/C и посмотрите контакт-листы клипов (по трём вопросам), а решение по голосу и права на публикацию оформим вместе с родителем.



================================================================================
# ФАЙЛ: OPENMONTAGE_UNIFIED_PROJECT_CONTEXT_RU.md
================================================================================

# OpenMontage Factory — единый контекст проекта, история решений и план дальнейшей работы

**Версия:** 1.0  
**Дата обновления:** 16 октября 2026  
**Назначение:** единый handoff-документ для пользователя, Kilo Code, OpenCode и других агентов. Сохраняет цель проекта, архитектуру, ограничения, решения, наблюдения из чата, вопросы для проверки и следующий план работ.

> **Правило достоверности:** документ объединяет сведения из текущего разговора и ранее сохранённых документов Library. Состояния Codespace, процессов, веток, ключей, моделей, квот, тестов и GitHub могут измениться. Перед действиями их нужно проверить в текущей рабочей копии. Нельзя выдавать старый статус за актуальный.

## 1. Краткое резюме

Строится **OpenMontage Documentary Factory** — воспроизводимая, максимально автоматизированная система производства англоязычных документальных YouTube-видео. Сначала нужно получить **одно качественное пилотное видео длиной 6–10 минут**, затем проверить весь цикл и только после этого масштабировать его в надёжный конвейер.

Текущая рабочая концепция канала: **The Hidden Business Behind Everyday Things** / **Behind Everyday Systems**.

Обещание зрителю: *“How overlooked businesses make money — and what happens when their systems fail.”*

Рассказывать, как производятся, перевозятся, обслуживаются и финансируются привычные товары и необходимые системы; где находятся узкие места, почему что-то дорого, кто на этом зарабатывает и что происходит при сбоях.

Это пока **рабочая гипотеза о нише**, а не доказательство низкой конкуренции или гарантии заработка. Пользователь попросил независимое исследование всех 100 предложенных ниш через Perplexity Deep Research. RPM-оценки из поста TikTok @weaponsgeek ($4–$22) помечены как непроверенные и не должны использоваться как фактические данные.

## 2. Главные цели и жёсткие ограничения

### Цели
- Довести существующий OpenMontage до реального end-to-end процесса.
- В первую очередь улучшать Kilo Code: правила, контекст, субагенты, skills, plugins/MCP, права, восстановление после перезапуска, контроль качества.
- Быстро и безопасно работать в ограниченных по времени сессиях GitHub Codespaces.
- Делать оригинальные, фактически проверенные документальные видео, а не шаблонные слайд-шоу со случайным B-roll.
- Получать проверяемые артефакты на каждом этапе и иметь возможность возобновить работу без повторного выполнения уже завершённых стадий.
- После проверки одного вертикального среза построить воспроизводимый конвейер.

### Ограничения
- Строгий режим **$0**: только проверенные бесплатные или локальные инструменты. Неизвестная цена = запрещено до проверки. Никакого платного fallback и обхода квот.
- Реальные кадры должны иметь подтверждённые права и происхождение. Нельзя выдавать иллюстративные или сгенерированные кадры за реальные доказательства.
- Каждый значимый факт должен иметь источник и статус проверки.
- Не публиковать и не планировать публикацию автоматически: финальное человеческое одобрение обязательно.
- Не добавлять новый фреймворк (например, LangChain) без доказанной необходимости: OpenMontage уже агентно-ориентирован, новый фреймворк может дублировать имеющуюся архитектуру.
- Не запускать два конкурирующих агента, которые одновременно редактируют одни и те же файлы.
- Не выполнять `git reset`, `git clean`, удаление lock-файлов или остановку процессов без проверки и разрешения.
- Не утверждать, что тест прошёл, коммит создан или GitHub обновлён, если это реально не подтверждено.
- Пользователь предпочитает короткие, чёткие промпты для Kilo Code и минимум лишнего рассуждения; рабочие промпты для coding agents писать на английском, общаться с пользователем — по-русски.

## 3. Репозиторий и рабочая среда

- Репозиторий/fork: https://github.com/sora73636-stack/OpenMontage
- Upstream: https://github.com/calesthio/OpenMontage
- Пользователь работает с Android-браузера и GitHub Codespaces (`github.dev`).
- Ранее упоминались `scripts/overnight.sh`, `scripts/overnight_factory_runner.py`, `scripts/kilo_llm_backend.py`, `pipeline_defs/documentary-montage.yaml`, `.kilo/overnight.lock`.
- Точные пути, активную ветку, состояние Git, процессы и статус runner нужно проверять заново. Старые PID/lock-статусы — исторические сведения, не текущая истина.
- Ранее интеграция GitHub через ChatGPT API возвращала `403 Resource not accessible by integration`; не заявлять о внесении изменений в удалённый репозиторий, пока commit/push не подтверждён.

### Известный исторический технический риск
Issue OpenMontage #511: адаптеры `archive_org`, `wikimedia`, `pond5_pd` ранее могли скрывать транспортные ошибки и сообщать успешный результат с нулём клипов. https://github.com/calesthio/OpenMontage/issues/511 . Текущий статус issue и фактическое поведение нужно проверить на рабочей копии; HTTP 200 или пустой список сами по себе не доказывают достоверность фактов или работоспособность источника.

## 4. Целевая архитектура

### Сквозной pipeline
1. **Topic selection** — тема, целевой зритель, вопрос, уникальный угол.
2. **Research** — сбор первичных и надёжных вторичных источников.
3. **Evidence ledger** — нормализованные источники, утверждения, цитаты/данные, даты, противоречия и статус факт-чека.
4. **Script** — сценарий, где каждый значимый факт связан с существующим `claim_id`.
5. **Fact-check** — проверка доказательств, чисел, цитат, причинно-следственных связей и контекста.
6. **Storyboard** — визуальные слоты и цель каждого кадра, привязанные к утверждениям или явно помеченные как иллюстративные.
7. **Footage discovery & rights** — поиск, проверка лицензии, автора, URL, временного интервала и допустимости использования.
8. **Narration / TTS** — бесплатная/локальная озвучка, выбранная после проверки качества, лицензии и доступности.
9. **Subtitles** — тайминг, выравнивание с речью, читаемость и стиль.
10. **Edit decisions / timeline** — монтажные решения, длины планов, переходы, графики, музыка только при законных правах.
11. **Assembly / render** — реальная сборка видео.
12. **Technical QA** — ffprobe, полный decode, длительность, разрешение, fps, codec, аудио, loudness/true peak, тишина, чёрные/замороженные кадры, субтитры.
13. **Editorial / visual QA** — совпадение кадра с narration/claim, разнообразие, повторы, отсутствие вводящих в заблуждение визуалов.
14. **Human approval** — обязательная финальная редакционная и правовая проверка.
15. **Packaging** — название, описание, главы, thumbnail/обложка, список источников. Публикация остаётся ручной до доказанной стабильности.

### Контрольные артефакты
`topic_brief`, `research_notes`, `evidence_manifest`, `script`, `fact_check_report`, `storyboard`, `footage_manifest`, `rights_manifest`, `narration_manifest`, `subtitle_manifest`, `edit_decisions`, `timeline`, `render_report`, `qa_report`, `human_approval_record`, `package_manifest`, `checkpoint/resume record`.

Артефакты должны быть версионируемыми и валидироваться схемами. Не создавать параллельные схемы с противоречащими полями; сначала обнаружить существующие схемы проекта и расширять их минимально.

### Evidence manifest — обязательные поля как минимум
- `claim_id` — уникальный ID фактического утверждения;
- точный текст утверждения;
- `source_id` и URL;
- название источника, автор/организация;
- дата публикации, дата доступа;
- точный фрагмент/таблица/страница или координаты данных;
- тип источника: primary / secondary / dataset / interview / other;
- уровень поддержки, ограничения, возможные противоречия;
- статус факт-чека и reviewer;
- связь с фрагментом сценария и storyboard slot.

Не придумывать IDs вроде `f1`/`f2`: все ссылки должны существовать в манифесте и проходить проверку.

### Footage/rights manifest — обязательные поля как минимум
- `asset_id`, URL страницы источника и прямой URL файла, если применимо;
- автор/правообладатель;
- лицензия и ссылка на точные условия;
- дата доступа/загрузки;
- временной интервал исходного клипа;
- storyboard slot / сцена;
- причина визуального соответствия и score, если есть;
- `evidence_role`: evidence / illustration / reconstruction / generated;
- запреты/атрибуция/ограничения;
- контрольная сумма или другая идентификация файла, если доступна.

CLIP/VLM-score может быть подсказкой, но не доказательством релевантности, фактической истинности или прав на актив.

## 5. Архитектура агентов и инструментов

### Минимальная команда — не раздувать число агентов
- **Orchestrator / lead engineer (Kilo Code):** выбирает следующий приоритет, проверяет инструкции, координирует задачи, объединяет результаты и сохраняет checkpoint.
- **bug-hunter (read-only):** локализует дефект, приводит пути/строки, минимальное воспроизведение, не меняет код.
- **research-evidence (read-only по коду):** собирает источники и проверяет claims/лицензии; не имеет прав на код/публикацию.
- **qa-reviewer (read-only):** проверяет diff, схемы, тесты, регрессии и отчёт.
- **test engineer** — подключать, когда есть конкретная тестируемая задача; не обязателен как отдельный постоянно работающий агент.

На старте достаточно 3–4 фактических ролей. Не делать десятки похожих субагентов. У каждой роли должны быть узкая задача, входы/выходы, права, таймаут, лимит попыток и формат отчёта. Главный агент отвечает за проверку результатов субагентов.

### Skills / plugins / MCP
Перед подключением каждого компонента проверить:
1. официальный источник и совместимость с установленной версией Kilo;
2. лицензию и происхождение;
3. исполняемые команды/доступ к shell и файловой системе;
4. внешние сетевые вызовы и передачу данных;
5. фактическую стоимость и лимиты;
6. пересечение с уже имеющимися возможностями OpenMontage;
7. минимальный тест и путь отката.

Не устанавливать плагины только потому, что они популярны. Не передавать секреты моделям/сервисам, условия хранения которых неизвестны.

### YouTube Agent Skill — потенциально полезный вспомогательный пакет
В предыдущем исследовании `Jakeschincariol/youtube-agent-skill` имел 11 навыков: `/yt-script`, `/yt-package`, `/yt-edit`, `/yt-comment`, `/yt-plan`, `/yt-viral`, `/yt-retention`, `/yt-shorts`, `/yt-seo`, `/yt-chapters`, `/yt-audit`.

Это вспомогательный growth/editorial слой, а не готовая фабрика. Навыки не обеспечивают лицензирование footage, TTS, полноценный монтаж/рендер или автоматическую интеграцию с YouTube Analytics. Хуки/viral scoring — эвристики, а не гарантированный прогноз просмотров. Проверять полный каталог навыков, скрипты, hooks/data, команды и безопасность перед переносом.

## 6. План на 6 рабочих сессий

Это шесть управляемых сессий, не обещание шести календарных дней. Приоритет — закончить вертикальный срез, не начинать масштабирование преждевременно.

### Сессия 1 — аудит и стабилизация
- Read-only preflight: `pwd`, `git status --short --branch`, `git log -1 --oneline`, diff, изменённые/неотслеживаемые файлы.
- Прочитать `AGENTS.md`, `AGENT_GUIDE.md`, `PROJECT_CONTEXT.md` и актуальные инструкции, если они существуют.
- Проверить процессы, runner, locks, checkpoints, фактический provider/model и бюджетный guard.
- Картировать уже реализованные этапы и тесты; проверить #511.
- Ничего не удалять/не сбрасывать; не выполнять массовые изменения.
- Артефакты: audit, work log, resume checkpoint — только после проверки путей и без перезаписи чужих файлов.

### Сессия 2 — Kilo Code и агентная система
- Оптимизировать правила проекта и постоянный контекст.
- Настроить короткие задачи, ограничение повторных попыток, целевые тесты, diff review и checkpoint.
- Проверить custom modes/subagents/skills/MCP по документации установленной версии.
- Минимальный набор ролей и allowlist инструментов.
- Не добавлять новый orchestration framework без доказанной необходимости.

### Сессия 3 — исследование и доказательства одного пилота
- Выбрать конкретный сюжет в пределах стартовой ниши.
- Создать topic brief, evidence manifest, script и storyboard.
- Каждое значимое утверждение должно иметь существующий источник и claim ID.
- Проверить наличие достаточно качественного и лицензируемого footage до того, как тратить время на полный сценарий/рендер.
- Отбрасывать тему, если нет источников, прав или визуального покрытия.

### Сессия 4 — минимальный end-to-end vertical slice
- Сначала короткий тест 30–90 секунд с narration, subtitles, реальными лицензированными кадрами, оригинальной схемой/графиком, монтажом и рендером.
- Проверить manifest, временные интервалы, аудио/видео и reproducibility.
- Не переписывать архитектуру ради одного видео; исправлять минимальные дефекты в текущем pipeline.

### Сессия 5 — полный пилот 6–10 минут и QA
- Увеличить проверенный процесс до целевого хронометража.
- Запустить технический QA: `ffprobe`, decode, duration/resolution/fps/codec, audio, loudness/true peak, silence, black/frozen frames, subtitles.
- Запустить editorial QA: visual alignment, факт/визуальное соответствие, повторы, pacing, источники, права.
- Исправить блокирующие ошибки и повторить тесты.
- Human approval; без него не публиковать.

### Сессия 6 — воспроизводимый конвейер
- Сделать stage contracts, manifests, idempotency, retry/backoff, timeouts, checkpoint/resume.
- Добавить targeted CI/tests и безопасное логирование.
- Зафиксировать точную процедуру запуска одного ролика и восстановления после перезапуска.
- Масштабировать только если один пилот повторяемо проходит quality gates.
- Первые 3 ролика — release/smoke gate, но не доказательство долговременной надёжности или бизнес-модели.

## 7. Как работать быстрее в ограниченном Codespaces

Пользователь сообщил, что время Codespaces ограничено. Уменьшать нужно лишние действия, а не просто требовать от модели «думать быстрее».

### Рабочий промпт для Kilo Code (английский)
```text
You are building OpenMontage Factory under a strict Codespaces time budget.
Follow the current project instructions and master plan. Execute the single
highest-priority unfinished task; do not merely describe a plan.

1. Start with a read-only preflight: git status, current branch/HEAD, existing
   instructions, active processes/locks, and current checkpoint. Preserve all
   user changes.
2. Select one small, high-impact task. Read only the files needed for it.
3. Do not redo completed stages, run broad research, install optional tools,
   or start unrelated refactors.
4. Make the smallest reliable change using the existing architecture.
5. Run the most relevant targeted test first. Run the full suite only when
   justified by the change.
6. Try at most two focused fixes for the same blocker. If still blocked,
   record evidence, avoid risky workarounds, and save a checkpoint.
7. Before the session ends, update the existing work log/checkpoint with:
   completed work, changed files, commands/tests and actual results, blockers,
   current git status, and the exact next action.
8. Never claim success without observed evidence. Never reset/clean Git,
   delete locks, kill unknown processes, expose secrets, or publish videos
   without permission.
Definition of done: one working, validated increment and a recoverable
checkpoint—not a long plan or an unfinished large refactor.
Start now and execute.
```

### Практические меры
- Одно изменение/один баг за сессию.
- Читать только необходимые файлы; не просить агента сканировать весь репозиторий без конкретной цели.
- Сначала targeted tests, потом более широкие тесты по необходимости.
- Не запускать много субагентов для простой правки.
- Сохранять контрольную точку и Git diff до исчерпания времени.
- Уменьшать число повторных попыток; после двух неудач записывать блокер и переключаться на безопасную задачу.
- Использовать `/compact`, если поддерживается текущим интерфейсом/режимом, и отключать неиспользуемые MCP. Проверить точные настройки в текущей версии.
- Не оставлять параллельно два runner/агента, редактирующих те же файлы.

## 8. Модели в Kilo: что обсуждали и что проверить

Пользователь показал два скриншота меню моделей в Kilo Code 7.8.12, где присутствовали Auto Free Kilo Gateway; OpenRouter Free Models Router; StepFun Step 5 Preview; Gemini 3 Flash Preview; Google Gemini варианты для TTS/Live, Nano Banana, Veo; Cohere North Mini Code (free); NVIDIA Nemotron 3 Ultra, 3 Super, 3.5 Lightning, 3.5 Super VL, 3 Nano Omni, Content Safety; Poolside Laguna S 2.1 и Laguna XS 2.1; Gemma 4 26B A4B / 31B; Inkling Small / Inkling; Dots3-Note Preview; Glyph Cluster (Stealth); Fireworks Ember-1; Schematron V2 Turbo / Small; Kimi for Coding / HighSpeed; несколько старых/выводимых из эксплуатации Gemini/ByteDance маршрутов.

### Рабочая рекомендация, не окончательный рейтинг
- **Step 5 Preview** — продолжать текущую инженерную работу, если конкретный маршрут действительно бесплатен. В предыдущей сессии на нём был получен 84-секундный MP4 1920×1080 (H.264/AAC), но это доказывает только один успешный этап, не завершение фабрики.
- **Nemotron 3.5 Super VL Free** — тестировать для визуального QA, скриншотов, кадров и мультимодальных задач; также сравнить на реальном баге кодинга.
- **Glyph Cluster Free** — кандидат для независимого текстового анализа/кодинга; прозрачность провайдера и политика хранения данных требуют осторожности. Не передавать секреты.
- **Laguna S 2.1 Free** и **Cohere North Mini Code Free** — альтернативы для сравнения на одном и том же реальном баге.
- **Gemma 4 26B/31B** и **Gemini 3 Flash Preview** — возможные резервы для коротких задач.
- **Nemotron 3.5 Content Safety** — специализированный модератор, не основной кодер.
- TTS-модели использовать только для озвучки, image/video генераторы — только для вспомогательных визуалов; не выдавать generated imagery за доказательные реальные кадры.
- Auto Free и OpenRouter Free Router удобны, но фактическая модель/маршрут может меняться. Для критической задачи лучше фиксировать проверенный маршрут, если это не ухудшает доступность.

### Правило выбора модели
Не ранжировать по маркетинговым словам, количеству параметров или отметке `Recommended` без контекста. Для нашей задачи проверить:
1. исправление реального бага в OpenMontage;
2. правильный минимальный diff;
3. успешный targeted test;
4. отсутствие посторонних изменений;
5. число повторных попыток и время до результата;
6. реальная цена маршрута и квоты;
7. политика данных и стабильность доступа.

Не считать опубликованные результаты разных бенчмарков напрямую сопоставимыми, если версии/окружения отличаются. Бесплатность проверять в текущем UI/API на момент запуска; она может меняться.

## 9. Выбор ниши: история и текущая гипотеза

### Список 100 тем
Пользователь предоставил 100 тем из семи скриншотов, отсортированных по заявленному RPM: от «Разбор отчётности компаний» ($22 по списку) до нескольких категорий по $4. Все цифры — из поста TikTok @weaponsgeek и **не проверены**. Нельзя считать их доказанными доходами и нельзя путать RPM с CPM.

### Текущая гипотеза позиционирования
**The Hidden Business Behind Everyday Things** / **Behind Everyday Systems**.

Более точный стартовый фокус первых 20–30 видео: малоизвестные, необходимые отрасли, промышленные процессы и цепочки поставок за знакомыми товарами: промышленная упаковка и картон; поддоны; коммерческая стирка; лифты и обслуживание; вывоз отходов и переработка; парковки; промышленные газы; склады и логистика; поставки продуктовых магазинов; грузовые перевозки; компоненты для заводов; вода, электроэнергия, дата-центры и критическая инфраструктура — позже, если пилоты подтверждают интерес.

### Почему эта гипотеза подходит фабрике
- много evergreen-сюжетов;
- реальные производственные кадры и собственные схемы/графики;
- естественное сочетание бизнес-модели, истории, логистики и инженерии;
- можно делать оригинальное объяснение, а не общий пересказ известной компании;
- подходит к существующему пайплайну footage + narration + montage + QA.

### Основные альтернативы, которые нельзя считать окончательно побеждёнными
- разбор финансовой отчётности;
- бизнес-кейсы и истории компаний;
- экономика простым языком;
- прикладной ИИ для конкретных профессий;
- инженерия и инфраструктурные системы;
- личные финансы и инвестиции;
- авиация/мегапроекты;
- наука/космос/география.

### Требуемая проверка ниши
Пользователь попросил Perplexity Deep Research независимо выбрать лучшую нишу из всех 100. Для анализа нужны:
- официальный YouTube policy по monetization, reused/inauthentic content, copyright, advertiser suitability;
- реальные примеры каналов/видео с датами, views, каналом и сравнением с нормальными результатами канала;
- Google Trends/YouTube Studio Trends, где доступны;
- оценка реального footage и лицензий;
- оценка сложности, evergreen, конкуренции и возможности оригинального повествования;
- RPM только с указанием метода, даты и ограничений;
- итоговый top-10 с весами и анализом чувствительности;
- 3 пилотных видео и критерии go/no-go;
- явный список неизвестного.

### Предварительные сюжетные идеи
1. Why Glass Recycling Is Harder Than It Looks
2. How Copper Gets From a Mine Into Your Home
3. Why Data Centers Need So Much Power
4. How Shipping Containers Changed Global Trade
5. What Happens to a Car Battery After It Dies?
6. Why Cement Is So Hard to Make Cleaner
7. How Drinking Water Reaches a City
8. Why Food Must Stay Cold Across Thousands of Miles
9. How Airport Baggage Systems Avoid Chaos
10. Why Some Plastics Cannot Be Recycled Economically
11. How Cardboard Boxes Survive Global Shipping
12. Why Semiconductor Factories Need Ultra-Pure Water
13. How Wastewater Gets Cleaned
14. Why Power Grids Need Backup Capacity
15. How Modern Bricks Are Made at Industrial Scale
16. What Actually Happens Inside a Container Port
17. Why Bridge Joints Move With the Weather
18. How Used Clothing Moves Around the World
19. Why Sand Is a Critical Industrial Resource
20. How Lithium Moves From Rock to Battery
21. Why Food Spoils During Transport—and How Refrigerated Shipping Works
22. What Happens When a Major Undersea Cable Breaks
23. Why Recycling Aluminum Is Different From Recycling Glass
24. How Cities Handle Millions of Tons of Waste

Это гипотезы, а не подтверждённые низкоконкурентные запросы. Перед утверждением каждой темы проверить спрос, конкуренцию, источники, права и возможность собрать достаточное визуальное покрытие.

## 10. Три пилота и критерии решения

Не начинать с массового выпуска. Выбрать три темы с близким намерением аудитории, например:
1. How Supermarkets Really Make Money
2. The Hidden Business Behind Shipping Containers
3. Why Airports Are Giant Businesses

Или выбрать более узкие промышленные сюжеты после проверки спроса/footage. Три пилота не доказывают прибыльность, но проверяют способность фабрики производить ролики и дают первые сигналы аудитории.

Для каждого пилота записывать: время производства по стадиям; фактическую стоимость; количество ошибок и повторных рендеров; источники/claims и статус факт-чека; долю сцен с подтверждёнными правами; technical QA и editorial QA; CTR, удержание первых 30 секунд, average view duration, returning viewers, search/suggested traffic — после появления данных YouTube Studio.

Не устанавливать универсальные пороги без контекста размера канала и типа трафика. Сравнивать пилоты между собой и с релевантными собственными/конкурентными данными. До появления достаточных данных не делать выводов о доходе.

## 11. История наблюдений из текущего разговора

### Рендер и исправление subtitle resolver
На скриншоте Codespaces Kilo работал в `/workspaces/OpenMontage`, в ветке `factory/business-documentary-pilot` (снимок статуса, а не гарантия текущего состояния). Агент обнаружил конфликт схемы/инструмента: resolver ожидал `subtitles.style` как dict, тогда как схема указывала string. Агент изменил тестовый/временный скрипт `stage10b_compose.py` в `/tmp/kilo`, заменив поля subtitle path/style и выполнил его. В выводе:
- `edit_decisions valid: 7 cuts`
- `compose success: True`
- `cost: 0.0`
- `output: 84.0 seconds, 1920x1080, h264 + aac`
- затем агент сообщил, что исправляет устаревшие ключи в report.

Это свидетельство, что одна стадия рендера сработала. Неизвестно из скриншотов, был ли временный скрипт перенесён в production-код, прошли ли полные тесты и сохранены ли изменения в Git. Проверить diff/файлы до продолжения; не считать баг исправленным в репозитории только по скриншоту.

### Модели
Пользователь показал меню Kilo 7.8.12 и спрашивал, какую модель выбрать. Решение: Step 5 Preview как текущий рабочий кандидат; Nemotron 3.5 Super VL для мультимодального QA; Glyph Cluster для независимого текстового review; Laguna S 2.1 и North Mini Code как альтернативы. Это предварительный выбор, требующий контролируемого теста на одном реальном баге и проверки нулевой цены/квоты.

### Ускорение агента
Пользователь сообщил, что время Codespaces ограничено. Поэтому каждая сессия должна давать один законченный инкремент и обновлять checkpoint. Не тратить большую часть сессии на повторное исследование или планирование, если задача уже определена.

### Промпт для Perplexity
Пользователь получил англоязычный промпт Deep Research, требующий независимо выбрать лучшую нишу из 100, не доверять TikTok RPM, изучить реальные источники и конкурентов, оценить fit для OpenMontage, выдать top-10, 20 идей, 90-дневный план и 3 пилота. Этот документ сохраняет смысл требований; если отчёт Perplexity будет получен, добавить его результаты с датами и ссылками, не стирая старые гипотезы.

## 12. Приоритетный backlog

### P0 — сначала
1. Проверить текущую рабочую копию: путь, branch/HEAD, git status, diff, незакоммиченные файлы.
2. Проверить активные процессы Kilo/runner, locks и checkpoint. Не запускать второй runner и не удалять lock вслепую.
3. Прочитать актуальные `AGENTS.md`/`AGENT_GUIDE.md`/`PROJECT_CONTEXT.md` и существующий progress log.
4. Проверить, где в production-коде находится subtitle resolver и schema mismatch; определить, попал ли временный fix в рабочую копию.
5. Проверить текущие тесты/manifest и убедиться, что успешный 84-секундный рендер воспроизводим.
6. Зафиксировать фактический бесплатный маршрут модели и бюджетный guard.
7. Убедиться, что evidence IDs валидируются и source adapter ошибки не маскируются под пустой успех.

### P1 — после безопасного preflight
1. Завершить один вертикальный срез с настоящими лицензированными кадрами, narration, subtitles и QA.
2. Привести evidence/storyboard/footage manifests к согласованной схеме.
3. Добавить targeted tests на schema mismatch, несуществующие IDs, сетевые ошибки и отсутствие лицензии.
4. Сделать воспроизводимый resume checkpoint.
5. Провести сравнительный тест Step 5 vs Nemotron 3.5 Super VL vs Glyph Cluster (и при необходимости Laguna/North Mini Code) на одной задаче с измерением времени/повторных попыток/тестов.
6. Получить и разобрать независимый отчёт Perplexity о нише.

### P2 — только после успешного пилота
1. Оптимизировать упаковку роликов, названия, thumbnail, главы и SEO.
2. Автоматизировать сбор метрик YouTube Studio/CSV после публикации, не предполагая наличие API без проверки.
3. Добавить повторяемый набор pipeline templates для подтверждённых сюжетов.
4. Расширять тематику только после подтверждения аудитории и качества.
5. Рассмотреть ночной runner только после проверки его безопасности, лимитов, resume и единственного владельца исполнения.

## 13. Как агент должен вести журнал и восстанавливаться

На каждом завершённом инкременте обновлять существующий журнал/чекпойнт. Если файла ещё нет, сначала проверить структуру проекта и создать файл в подходящем существующем каталоге, не дублируя уже существующий документ.

Checkpoint должен содержать:
- timestamp;
- repo path, branch, HEAD;
- git status и незакоммиченные изменения;
- что завершено и какие файлы изменены;
- команды и точные результаты тестов;
- какой provider/model реально использовался и подтверждён ли $0;
- какие процессы/locks остаются активными;
- известные ошибки/риски;
- точное следующее действие одной фразой;
- инструкции для безопасного resume.

Не писать в checkpoint API keys, пароли, токены или иные секреты.

## 14. Неизвестное и не подтверждённое

- Текущее состояние Codespace, Git branch, HEAD, diff и runner.
- Попал ли fix из `/tmp/kilo/stage10b_compose.py` в production-код.
- Полный результат тестов после рендера и актуальный статус issue #511.
- Текущая доступность и бесплатные лимиты Step 5, Nemotron 3.5 Super VL, Glyph Cluster, Laguna и North Mini Code.
- Реальные правила хранения/использования данных для выбранного маршрута каждого провайдера.
- Какая из 100 ниш покажет лучшие реальные результаты у нового канала.
- Реальный RPM будущего канала, доля аудитории по странам, CTR и retention.
- Лицензии конкретных видеоклипов до проверки конкретных источников и условий.
- Успешная работа всей фабрики end-to-end; 84-секундный рендер не подтверждает её полностью.

## 15. Документы, которые уже существуют в Library

Список найденных документов в ChatGPT Library на 16 октября 2026 (дубликаты существуют и в корне, и в `/OpenMontage`):
- `OPENMONTAGE_FACTORY_MASTER_PLAN_RU.md`
- `OPENMONTAGE_FACTORY_MASTER_PLAN_RU_v3.md`
- `OPENMONTAGE_FINAL_FACTORY_PLAN_RU_v2.md`
- `OPENMONTAGE_HANDOFF_RU.md`
- `OPENMONTAGE_KILO_AGENT_PLAYBOOK_RU.md`
- `KILO_UNIVERSAL_OPENMONTAGE_PROMPT_RU.txt`
- `OPENMONTAGE_BUSINESS_DOCUMENTARY_ADAPTATION_PLAN_RU.md`
- `OPENMONTAGE_MEDIA_AND_TTS_RESEARCH_RU.md`
- `OPENMONTAGE_VISUAL_ALIGNMENT_QA_RU.md`
- `OPENMONTAGE_COMPONENT_RESEARCH_ADDENDUM_V4_RU.md`
- `OPENMONTAGE_RESEARCH_ADDENDUM_v3_RU.md`
- `OPENMONTAGE_NICHE_STRATEGY_HIDDEN_SYSTEMS_RU.md`
- `BEST_YOUTUBE_NICHE_DEEP_RESEARCH_OCT_2026_RU.md`
- `FINAL_NICHE_RESEARCH_2026_EN.md`
- `YOUTUBE_NICHE_COMPARISON_TOP_RU_OCT2026.md`
- `YOUTUBE_NICHE_SHORTLIST_REAL_RESEARCH_OCT2026_RU.md`
- `SHORTLIST_LONGFORM_YOUTUBE_NICHES_OCT_2026_RU.md`
- `YOUTUBE_NICHE_RESEARCH_TELEGRAM_FORUMS_OCT_2026_RU.md`
- `BEHIND_EVERYDAY_SYSTEMS_CRITICAL_REVIEW_RU.md`
- `Исследовательский отчёт: интеграция LLM-агентов в YouTube-пайплайн`

Это список Library, а не подтверждение, что все эти файлы находятся в текущем Codespace. Перед использованием искать в Library или проверять Git.

## 16. Changelog

- **2026-10-16, v1.0:** объединены основной мастер-план v3, handoff, нишевая гипотеза, ограничения проекта, шесть этапов, Kilo speed prompt, модельный shortlist, наблюдение о 84-секундном рендере, требования к исследованию Perplexity и backlog.
- Статусы динамической среды не обновлялись через реальный доступ к текущему Codespace в рамках этого документа.
- Никаких утверждений о новом commit/push или изменениях репозитория этим документом не делается.




================================================================================
# ФАЙЛ: OPENMONTAGE_HANDOFF_RU.md
================================================================================

# OpenMontage — полный handoff для нового чата

**Язык общения:** со мной говорить по-русски. Промпты для Kilo Code, OpenCode и других coding agents писать на английском.  
**Снимок контекста:** по состоянию на сообщения от 14 октября 2026 года. Все живые процессы, файлы, ключи, маршруты и статусы необходимо перепроверить в Codespace: приведённые ниже статусы — последние наблюдавшиеся в чате, а не гарантия того, что они всё ещё актуальны.

## 1. Главная цель проекта

Построить **OpenMontage Documentary Factory** — настоящую автоматизированную фабрику документальных видео, а не только CLI или разовый ролик. Фабрика должна проходить путь от темы и исследования через доказательства, сценарий, fact-check, storyboard, озвучку, поиск/загрузку footage, монтажные решения, timeline, аудио, render, QA и packaging. Каждый этап должен иметь реальные входы/выходы, валидацию, provenance, сохранение состояния и возможность resume.

Приоритеты пользователя:
- Довести фабрику до реально работающего end-to-end пайплайна с проверенным свежим видео и аудио.
- Работать максимально бесплатно: **никакого платного fallback**, неясных тарифов, trial-only использования в production или обхода квот.
- Долгая автономная работа ночью: агент сам выбирает следующий этап, выполняет код, тесты, QA, сохраняет checkpoint и продолжает, без рутинных запросов разрешения.
- Модели должны автоматически переключаться при 429, timeout и 5xx; не зависать на одной модели.
- Иметь один ясный документ архитектуры и отдельный checkpoint для возобновления работы.
- Сначала проверять текущую реальность репозитория. Не верить старым отчётам без проверки.

## 2. Роли инструментов — очень важно не перепутать

- **OpenCode сейчас используется пользователем как сильный инженер/строитель системы:** он должен подготовить и исправить ночной runner для Kilo, конфигурацию, интеграции и код.
- **Kilo Code должен быть ночным worker/исполнителем:** runner запускает `kilo run`, а не `opencode run`.
- **OmniRoute** — предполагаемый шлюз моделей, доступный по `http://127.0.0.1:20128/v1`, когда его сервер запущен и доступен.
- **Kilo Gateway `kilo-auto/free`** — отдельный встроенный маршрут Kilo. Он управляется на стороне Kilo; нельзя считать, что в него можно локально добавить OmniRoute. Если это не поддерживается официально, использовать отдельный Kilo-provider alias `omniroute/auto-free` и переключение между отдельными bounded Kilo-сессиями.
- **Overnight runner** (`scripts/overnight_factory_runner.py` + `scripts/overnight.sh`) — единственный контроллер повторных Kilo-сессий, состояния, таймаутов, логов и checkpoints.
- Не запускать OpenCode и Kilo как два конкурирующих исполнителя, которые редактируют одни файлы одновременно.

## 3. Состояние ночного запуска на последнем известном шаге

Последнее подтверждённое отчётом состояние, 14 октября 2026:
- Runner запускался вручную командой ниже, ограничение — 5 итераций и максимум 6 часов.
- В последнем отчёте runner был `RUNNING`, PID `28688`, lock `.kilo/overnight.lock` был занят.
- Было реализовано потоковое логирование из дочернего процесса Kilo (`python -u`), сообщения `[FACTORY]` стали появляться до выхода процесса.
- При запуске `KILO_FREE_MODE=1` основной маршрут реально был Kilo-native Free Mode, **не OmniRoute**.
- OmniRoute в тот момент был недоступен: `127.0.0.1:20128` connection refused; переменная `KILO_OMNIROUTE_API_KEY` отсутствовала. Management key намеренно не использовали.
- Старый job `openmontage_factory_build_1791962002_bebb39` прошёл `topic`, `research`, `evidence`, `script`, `fact_check`, но был заблокирован на `storyboard`: модель ссылалась на неизвестные source IDs `f1/f2`. Storyboard не должен придумывать IDs.
- Повторная попытка с `kilo/liquid/lfm-2.5-2.6b:free` дала ответ, но валидация источников не прошла. Пять предыдущих стадий сохранились; их не нужно выполнять снова.
- Более новый запуск job `openmontage_factory_build_1791963825_26029b` был начат на `omniroute/auto`, но так как OmniRoute был down, нужно выяснить, каким фактическим маршрутом он продолжился и какой статус сейчас.
- Ранее другая сессия показала runner PID `2014` и job `overnight_20261014T071322`, затем runner был исправлен и запущен новый PID `28688`. При новом чате обязательно проверить все процессы и lock, не убивать случайно не тот процесс.
- Статус процесса, logs, checkpoints и ключей может измениться после переноса чата. Начинать с read-only preflight.

### Проверенные команды управления

В репозитории `documentary-factory`, из `/workspaces/OpenMontage`:

```bash
./scripts/overnight.sh status
```

```bash
KILO_FREE_MODE=1 ./scripts/overnight.sh start --iterations 5 --hours 6 --topic "OpenMontage Factory Build"
```

```bash
./scripts/overnight.sh stop
```

Использовать `start` только по явной команде пользователя. Сам аудит не должен стартовать ночной цикл. Не запускать второй runner, если уже работает первый. Не удалять `.kilo/overnight.lock` вслепую.

Типичные пути:
- `scripts/overnight.sh`
- `scripts/overnight_factory_runner.py`
- `scripts/kilo_llm_backend.py`
- `.kilo/overnight.lock`
- `logs/overnight/`
- `docs/openmontage/FACTORY_BLUEPRINT.md`
- `docs/openmontage/OVERNIGHT_CHECKPOINT.md`
- `projects/factory_state/overnight/`

## 4. Что уже было реализовано/проверено (перепроверить после переноса)

Последний технический отчёт сообщал:
- `scripts/kilo_llm_backend.py`: per-model timeout 60 → 120 секунд через `KILO_PER_MODEL_TIMEOUT_S`; до 180 секунд для reasoning моделей через `KILO_REASONING_TIMEOUT_S`; candidate pool с cooldown; `eligible_models()`; обработка HTTP 429 `Retry-After`; bounded exponential backoff с базой 2 сек и потолком 30 сек; `KILO_PREFERRED_MODEL`; максимум 3–4 candidate model.
- `scripts/overnight_factory_runner.py`: запускает дочернюю сессию Kilo, потоково сохраняет stdout/stderr/heartbeat с моделью, попыткой и elapsed time; при общем лимите итерации 600 сек — SIGTERM, затем SIGKILL, сохраняет partial output.
- `factory/llm_gateway.py`: `Retry-After` bounded до 30 секунд.
- `openmontage_factory_cli.py resume --model`: ограничение на допустимые `:free` модели, отбрасывает платные/непроверенные варианты (следует проверить реальную логику, не считать суффикс `:free` достаточным доказательством бесплатности).
- JSON parser: вместо жадного `{.*}` используется поиск сбалансированных фигурных скобок; JSON decode с `strict=False` переносит необработанные переводы строк и табы. В отчёте было 6 regression tests.
- `tests/factory/test_kilo_failover.py`: 6 тестов прошли (timeout rotation, 180s reasoning, 429 + skip, bounded backoff, fail-closed auth, Retry-After + skip).
- Существующие тесты `kilo_free_mode` / `omniroute_default` / `no_key`: отчёт говорил 17/17 passed. Всего последняя сводка — **23 теста прошли**.
- `tests/factory/test_omniroute_default.py`: раньше 6/6 passed.
- FFmpeg/ffprobe доступны; реальный отдельный тестовый H.264/AAC ролик на 12 секунд прошёл проверку через ffprobe. Это НЕ означает полного прохождения factory render stage.
- Старый артефакт `projects/youtube_documentary_real/final_3min_correct_v2.mp4` размером примерно 66 MB существовал ранее. Не объявлять его свежим результатом последнего end-to-end запуска.
- Последняя команда commit/preflight сообщала commit `704581d`; предыдущие известные commits: `67533d8`, `ee9b9cb`, `8fe8746`; также упоминались `5906c67` и `74527f4`. Проверить текущий `HEAD`, историю и рабочее дерево, не предполагать, что эти хэши все в текущей ветке.
- Были файлы `docs/openmontage/FACTORY_BLUEPRINT.md` и `docs/openmontage/OVERNIGHT_CHECKPOINT.md`, но Blueprint, по одному отчёту, был заменён минимальной заглушкой. Проверить `git diff` и восстановить полную архитектуру из истории/настоящего состояния, если необходимо.

## 5. Реальные блокеры OpenMontage

### 5.1 Storyboard должен ссылаться на реальный evidence ledger

Главный известный блокер — `storyboard` вернул ссылку на неизвестные IDs `f1/f2`. Исправление:
- Передавать модели полный актуальный список валидных claim/source IDs из ledger.
- Валидировать каждый scene/source ID against real ledger.
- При неизвестных ID — bounded regeneration/repair с использованием существующих валидных IDs.
- Никогда не придумывать IDs и не ослаблять fact-check.
- При resume начинать с `storyboard`, сохраняя уже успешно завершённые `topic/research/evidence/script/fact_check`.

### 5.2 Ненадёжные ответы LLM

Модели могут вернуть malformed JSON, короткий сценарий или reasoning metadata без usable output.
- Разбирать только поддерживаемые user-facing поля официального API-ответа; не извлекать hidden reasoning как контент сценария.
- Empty/malformed output: bounded retry → следующий approved free candidate → checkpoint/blocked.
- Проверять schema, target duration/word count, ссылки на доказательства и фактическую точность.
- Не обходить валидаторы и не выдумывать факты, источники или метаданные.

### 5.3 Evidence retrieval

- Нужны минимум 5 разных релевантных источников, когда они доступны.
- Расширять запросы, нормализовать URL, убирать дубликаты, проверять качество/релевантность.
- Если источников недостаточно, честно блокировать задачу и checkpoint, не понижать минимум автоматически.
- В одном из прошлых запусков topic `nature` дал 13 claims; другой запуск дал 11 источников, но это не гарантия для любой темы.

### 5.4 Полный E2E ещё НЕ доказан

В последнем честном отчёте M3 имел только стадии `topic/research/evidence/script/fact_check/storyboard` как implemented. `narration`, `footage`, и `render` были `NOT_IMPLEMENTED` по дизайну M3. В другом отчёте говорилось 6/19 стадий implemented. Текущий реальный статус нужно исследовать. Отдельный FFmpeg render path на 12 секунд не является полным factory E2E. Нужно последовательно реализовать недостающие stages и доказать свежим артефактом весь путь до QA.

## 6. Модельная система и строгий бесплатный режим

### Желаемая архитектура
- Kilo Code — ночной worker.
- OpenCode — сильный инженерный инструмент для подготовки/исправления самого Kilo runner, если пользователь запускает такую работу; не должен незаметно подменять Kilo в runner.
- OmniRoute — предпочтительный provider/gateway, если он жив и доступен через restricted client key.
- `omniroute/auto-free` — отдельный пользовательский Kilo alias через custom OpenAI-compatible provider. Не утверждать, что OmniRoute можно вставить внутрь Kilo server-managed `kilo-auto/free`, пока нет официального механизма.
- `kilo-auto/free` — независимый маршрут на стороне Kilo, потенциально fallback в следующей bounded Kilo-сессии, если он доступен и его условия приемлемы.
- Не рассчитывать на больше квоты только потому, что маршрутизатор имеет много моделей: лимиты часто общие на аккаунт/IP/provider; не обходить лимиты сменой идентичностей/IP.

### Известные OmniRoute сведения (все перепроверить)
- Ранее OmniRoute v3.8.51, локальная точка `http://127.0.0.1:20128/v1`.
- В одном из последних reports: port 20128 refused, OmniRoute не запущен и `KILO_OMNIROUTE_API_KEY` отсутствовал. Поэтому последний активный маршрут был `KILO_FREE_MODE=1`, то есть Kilo-native Free Mode.
- Не fallback-ить клиентскую переменную к `OMNIROUTE_API_KEY`, потому что она могла использовать привилегированный server/environment key. Требовать только `KILO_OMNIROUTE_API_KEY`. Не выставлять management key всем дочерним процессам.
- В Kilo был alias list из 7 combo aliases:
  - `auto-coding` → `auto/coding`
  - `auto-reasoning-reliable` → `auto/reasoning:reliable`
  - `auto-fast` → `auto/fast`
  - `auto-best-free` → `auto/best-free`
  - `auto-chat` → `auto/chat`
  - `auto-smart` → `auto/smart`
  - `auto-cheap` → `auto/cheap`
- Нужен реальный Kilo runtime test, что provider виден в `/models`, streaming/tool calls работают и logs показывают actual upstream. CURL alone недостаточно.
- Нужны bounded retry/cooldown/circuit breaker и фактический failover между approved candidates. На 429 учитывать `Retry-After`; на timeout/5xx — bounded exponential backoff; на auth/ACL/billing/unknown pricing — fail-closed.
- `$0` domain budgets в исторической конфигурации не обеспечивали enforcement в request path. Не гарантировать нулевые затраты только по бюджету в БД.

### API keys / секреты
- В переписке были скриншоты с клиентскими ключами и `STORAGE_ENCRYPTION_KEY`. Значения намеренно не переносятся в этот файл. Проверь текущий ротационный статус безопасно.
- Не включать API ключи и их значения в файл, Git, отчёты или скриншоты.
- Никогда не использовать privileged/management key как клиентский credential.
- `KILO_OMNIROUTE_API_KEY` должен быть отдельным ограниченным ключом. Если ключ отсутствует — честно checkpoint и остановка LLM вызова; не подменять его админским.
- `STORAGE_ENCRYPTION_KEY` не менять вслепую: сначала изучить поддерживаемую процедуру миграции/повторного шифрования; замена может сделать stored encrypted provider credentials нечитаемыми.
- Проверь наличие ключа в текущем shell и наличие соответствующего Codespaces Secret отдельно. Наличие в shell само по себе не доказывает persistence после rebuild.

## 7. Историческая карта OmniRoute provider eligibility (не считать текущей до live audit)

В одном из аудитов сообщалось о 10 активных соединениях: `bytez`, `cloudflare-ai`, `cohere`, `freemodel-dev`, `friendliai`, `gemini`, `groq`, `kilo-gateway`, `routeway`, `xkiro`. Это может измениться. В старых отчётах присутствовали и другие провайдеры; несколько конфликтующих отчётов нельзя считать текущей конфигурацией.

Предварительная классификация из прежних отчётов:
- **Groq:** бесплатно в рамках официальных model-specific limits; квоты/модели меняются.
- **Google Gemini API / AI Studio:** есть free-tier модели с региональными и model-specific ограничениями; проверить current pricing, data use, eligibility.
- **xKiro:** исторически заявлялось 50 credits/month с model multiplier; проверить current official terms.
- **Routeway:** исторически заявлялась бесплатная квота/`:free` models; проверить реальные текущие лимиты и pricing.
- **Kilo Gateway:** имеет rotating free set; точный список брать из live official catalog и model metadata.
- **NVIDIA NIM:** упоминался в прежних отчётах как free tier, но его наличие среди реально активных соединений противоречиво; проверить current state и лимиты.
- **Cohere:** в прежнем аудите classified trial-only/prototyping, no production/commercial; не использовать в production без перепроверки условий.
- **Bytez:** условно бесплатно только для моделей до 7B по прежним сведениям; overage/кредиты риск. Проверять каждую модель.
- **Cloudflare Workers AI:** quota может быть бесплатной, но gateway/proxy terms были неясны; использование через OmniRoute должно быть признано разрешённым прежде чем включать.
- **Cerebras:** прежний отчёт говорил про $5 trial и способ оплаты, не recurrent free; НЕ включать как free без текущего официального подтверждения.
- **freemodel-dev, friendliai:** в одном live каталоге connections были активны, но модели отсутствовали; классифицировать как UNVERIFIED пока не доказано другое.
- **OpenRouter, Kiro paid routes, Ollama Cloud, etc.:** в предыдущих отчётах часть connections были отключены/заблокированы. Не менять это автоматически.

Все эти оценки исторические. Следующая задача — заново исследовать /connect в Kilo Code, `opencode models`/provider configuration и другие совместимые free API с официальными pricing/terms страницами и реальными лимитами. Не создавать много аккаунтов/ключей в целях обхода ограничений.

## 8. Запрос пользователя, который ещё НЕ выполнен

Пользователь попросил:
> Изучить все, что есть в `/connect` в Kilo Code, OpenCode и других бесплатных coding agents; исследовать API-провайдеры, найти 20–30 бесплатных API, упорядочить от лучших к худшим и проверить, действительно ли сейчас столько бесплатных моделей/токенов.

В новом чате выполнить глубокое актуальное исследование с web sources, включая официальную документацию, price/free-tier pages, GitHub issues/discussions, форумы/Reddit и видео YouTube, если надёжно доступны. Нельзя выдавать старую цифру моделей за current факт.

Для каждого кандидата собрать:
1. Провайдер/агент и способ подключения (`/connect`, API key, OAuth, gateway).
2. Реально подтверждённые free models и exact IDs.
3. Точные token/request rate limits (RPM/TPM/RPD/monthly credits), контекст и output limits, как опубликовано.
4. Требуется ли банковская карта, trial, подтверждение номера или billing account.
5. Ограничения по коммерческому/prod использованию, данные/приватность, региональные ограничения.
6. Совместимость с Kilo/OpenCode/OmniRoute, OpenAI-compatible base URL, tools/streaming.
7. Риски 429, нестабильности, ротации каталога и fallback.
8. Официальные URL и дата проверки.
9. Итоговый рейтинг по полезности для ночной разработки OpenMontage, а не просто по числу моделей.

Кандидаты для перепроверки (это shortlist, не утверждение о текущей бесплатности): Groq, Gemini API/AI Studio, Kilo Gateway/Auto Free, Routeway, xKiro, NVIDIA NIM, Cloudflare Workers AI, Bytez, Cohere (trial restrictions), OpenCode Zen, OpenRouter `:free` models, GitHub Models (если текущий public/free-tier доступен), Hugging Face Inference Providers/free credits, Cerebras (перепроверить trial vs recurring), Mistral API, Together AI, Fireworks, SambaNova, DeepInfra, Replicate, SiliconFlow, Nebius AI Studio, Vercel AI Gateway, Pollinations, Ollama local, LM Studio local и другие актуальные варианты. Не все из них являются permanently free, часть может требовать оплаты/карты/кредитов. Утверждения подтверждать актуальными источниками.

На выходе дать таблицу не менее 20 кандидатов, распределить на: confirmed free within limits; temporary/trial; local/self-hosted; conditional/unverified; paid/no longer free. Затем рекомендовать лучший пул для OmniRoute/Kilo без paid fallback. Не придумывать квоты.

## 9. Tools/plugins, которые рассматривали

- **GSD Core:** полезен для последовательных milestone plan/execute/verify. Проверить текущую совместимость и присутствие; официальная установка под Kilo ранее упоминалась как `npx @opengsd/gsd-core@latest --kilo --local`, но перед запуском читать актуальный installer diff и избегать дублирования уже имеющихся workflows.
- **CodeRabbit CLI:** независимый review при наличии разрешённой бесплатной квоты и приемлемой privacy policy. Не добавлять paid billing. Если недоступен, использовать локального `code-reviewer` agent.
- **Context7 MCP:** полезен для актуальной документации библиотек/API, настроить и действительно вызвать, если стабилен/без ключа в рамках доступной квоты.
- **GitHub MCP:** read-only по возможности для issues/PR/CI/release info; не давать auto-write permission.
- **Playwright MCP:** ставить только если в репозитории реально есть web UI, который нужно browser-test.
- **Roo Code:** не устанавливать (в предыдущем чате определён как archived/discontinued в 2026; перепроверь свежесть если релевантно).
- **Ralph Loop:** не ставить Claude-specific plugin в Kilo; реализовать аналогичный ограниченный loop поверх Kilo CLI.
- Не устанавливать всё подряд. Сверять source, license, compatibility, active use и отсутствие paid plan requirement.

## 10. Kilo Auto Approve / автономность

Пользователь хочет, чтобы агент не останавливался на подтверждениях рутинных действий. Нужно:
- Проверить реальную schema установленной версии Kilo, загруженный global/project config и специальные защиты config-edit.
- Автоматически разрешить рутинные project-scoped read/edit/test/build/QA/agent/tool/documentation operations.
- Проверить, что изменение `kilo.json`/конфигурации больше не вызывает неожиданный prompt, если это можно сделать официально.
- Не давать blanket approval опасным операциям: destructive Git, secret disclosure, credential/ACL changes, billing activation, publish/deploy, destructive DB/encryption changes.
- Проверять effective settings через harmless реальные тесты; не считать файл конфигурации доказательством.
- Не оставлять заблокированный шаг бездействовать: checkpoint, записать точную причину и продолжить независимую безопасную работу.

## 11. Ожидаемая архитектура ночного runner

- Один runner, process lock и ограничение итераций/времени.
- Явный ручной старт; аудит не запускает night run автоматически.
- В каждой итерации fresh bounded `kilo run`, один measurable milestone.
- Потоковые unbuffered logs/heartbeat с моделью, попыткой, elapsed time, следующей попыткой — без секретов.
- При 429 читать Retry-After, cooldown failed candidate; при 5xx/timeout bounded exponential backoff.
- На auth/ACL/billing/unknown pricing — fail closed.
- При успехе: tests, review, actual artifact/QA, update checkpoint/blueprint, isolated commit, следующая итерация.
- При сбое: сохранить состояние, продолжить с последней проверенной точки, не повторять успешные стадии.
- При исчерпании моделей: safe non-LLM work; не бесконечно повторять запрос.
- Остановить только конкретный runner через `overnight.sh stop`; не убивать другие процессы и не удалять lock вслепую.
- Codespaces имеет ограничения по времени жизни; один runner не гарантирует 12–24 ч без перерыва. Нужно надёжное resume.

## 12. Структура OpenMontage и правила реализации

Проект исторически использует agent-first архитектуру: агент планирует/координирует, Python/workers выполняют bounded операции, state/persistence/retries/validation остаются детерминированными. Не превращать фабрику в монолитный Python orchestrator и не заменять реальные stages моками.

Исторически существовали:
- `factory/job_state.py` — atomic state, resume, idempotency, transient/permanent errors.
- `factory/provider_abstraction.py` — capability routing, local tools/worker adapters.
- `factory/provenance.py` — provider/model/artifact/duration/status/fallback/free telemetry.
- `factory/pipeline_runner.py` и `openmontage_factory_cli.py` — стадии/jobs/resume/QA.
- `factory/llm_gateway.py` — LLM invocation/failover.
- `scripts/kilo_llm_backend.py` — Kilo backend/fallback.
- `scripts/overnight_factory_runner.py` и `scripts/overnight.sh` — bounded background workflow.

Stage graph в текущем M3 отчёте: `topic → research → evidence → script → fact_check → storyboard`; дальше должны быть реально реализованы `narration → footage → footage_intelligence → editorial → timeline → audio → render → qa → packaging/thumbnail/human_review/publish/analytics` (точный граф и имена стадий перепроверить в repo; старые отчёты противоречили числу stages — 14 или 19).

## 13. Как начать новый чат

Первым делом прочитать этот handoff, затем попросить пользователя дать актуальный короткий status из Codespace или audit read-only. Самостоятельно проверять текущий repo/process/branch/logs, не полагаться на старые PID или checkpoint. Пользователь хочет сначала исследование free APIs и установку полезных инструментов, но не забывать текущую непосредственную цель — сделать ночной Kilo runner рабочим и продолжать фабрику.

Стиль ответа пользователю: русский, по делу. Кодинг-промпты — короткие по возможности и на английском. Когда пользователь просит промпт, выдавать копируемый англоязычный блок. Не представлять вывод агента как собственную проверку: явно разделять «сообщил агент» и «подтверждено проверкой».

## 14. Готовый стартовый prompt для нового ChatGPT-чата

Скопировать в новый чат вместе с прикреплённым handoff-файлом:

> Прочитай полностью приложенный `OPENMONTAGE_HANDOFF_RU.md` и используй его как контекст проекта. Общайся со мной на русском, а промпты для coding agents пиши на английском. Не повторяй старые утверждения как проверенные факты: сначала уточни, что изменилось, и проверь актуальные данные.
>
> Моя первоочередная задача: исследовать актуальные бесплатные API-модели и способы подключения через `/connect` в Kilo Code, OpenCode и других релевантных coding agents. Найди и ранжируй 20–30 реально доступных кандидатов: провайдер, точные бесплатные модели, лимиты RPM/TPM/RPD/monthly credits, context/output limits, карточка/оплата/trial requirements, условия production/commercial использования, privacy, совместимость с Kilo/OpenCode/OmniRoute и официальные ссылки с датой проверки. Используй официальные тарифы/документацию, GitHub issues/discussions, Reddit и доступные YouTube источники. Разделяй recurring-free, quota-free, trial-only, local/self-hosted, conditional/unverified и paid. Не придумывай токены/квоты и не предлагай обход лимитов множественными аккаунтами или IP.
>
> Затем помоги безопасно проверить актуальный Codespace и ночной runner, исправить OmniRoute availability/client-key isolation и динамическую ротацию бесплатных моделей, а потом продолжить OpenMontage до реального end-to-end видео. OpenCode используется для подготовки/исправления системы, но Kilo Code остаётся ночным worker. Сначала read-only preflight, не убивай неизвестные процессы и не запускай второй runner, пока состояние текущего не проверено. Секреты не выводить, не сохранять в файлы и никогда не fallback-ить на management key.
>
> Приоритет — реальные подтверждённые результаты, прозрачные блокеры, безопасные checkpoints и короткие итоговые отчёты. Начни с актуального исследования API и read-only проверки живого состояния; не утверждай, что что-то запущено или проверено, пока нет доказательств.




================================================================================
# ФАЙЛ: OpenMontage_last_chat_full.md (последний чат «Качество футажей в видео»)
================================================================================

# Качество футажей в видео
created 2026-10-17T17:44:07.309035Z updated 2026-10-18T12:30:43.271798Z
summary: **Conversation overview**

The person is building OpenMontage, a YouTube documentary factory project running on GitHub Codespaces with Kilo Code agents, focused on a pilot video about NASA/FAA's 1984 Controlled Impact Demonstration (CID) test of a remotely-piloted Boeing 720. The project enforces strict rights/provenance rules (fail-closed, rights_basis tracking), a QC gate (tools/qa/qc.py), and claim-sourcing requirements (claim ledger with two-source verification). Repository lives on GitHub under sora73636-stack/OpenMontage, branch factory/business-documentary-pilot.

Across the session, Claude reviewed a MASTER_RUN agent report, helped reconcile an externally-sourced "master setup file" (KILO_CODE_YOUTUBE_FACTORY_MASTER.md) against the existing project rules via a selective-merge milestone (M1), and repeatedly guided iterative fixes to a 46-56 second video slice: switching footage layout (framed 2x inserts for 320x240 archive clips instead of stretching), adding NASA still photos as primary visuals, restoring Kokoro TTS narration after it was accidentally dropped, and fixing a QC freeze-frame/loudness failure. The person personally reviewed rendered video via a local HTTP server on ports 8000/8080 (python3 -m http.server) viewed through VS Code's Ports panel, confirming no visible logos or recognizable people and accepting the final footage quality. Claude also found and vetted a second source for claim CID-13 (FAA report DOT/FAA/CT-87/10) to unblock a previously single-sourced script line, with an explicit caution about a contradiction between NASA Facts and the FAA report regarding fire intensity claims.

When GitHub Codespaces free hours neared exhaustion (90% used), Claude guided a full project migration to a different GitHub account (dragongod73584-design) via fork, including committing previously-uncommitted files (AGENTS.md changes, installed skills, audio-edit skill, docs/agent-improvement, docs/architecture, templates) and creating a portable rebuild system (scripts/rebuild_slice_assets.sh, HANDOFF_NEW_ACCOUNT.md, a manifest with URLs/sha256). Claude flagged that using multiple free GitHub accounts to bypass usage limits violates GitHub's terms and advised using an account belonging to a parent or other consenting person instead, noting one visible account name appeared to belong to someone else without clear consent to use it.

A significant bug was found and partially fixed: the rebuild script falsely reported "DONE" despite a JSONDecodeError because the manifest file contained markdown-style comment lines before the JSON content; Claude diagnosed this and had the person manually convert the file to valid JSON, then prepared a follow-up prompt instructing the agent to fix the script to be fail-closed (non-zero exit on any parse/hash error, never claim success without verifying N/N assets) with test-first development, and to handle a Python version mismatch (repo pins 3.10, Codespace runs 3.14.2) by creating an isolated venv.

The person asked Claude to research and rank free AI models available in Kilo Code and OpenCode (Zen) based on benchmarks and agentic-coding performance; Claude did web research and provided rankings while cautioning that most published benchmarks are self-reported by model vendors, noting privacy risks ("may train" labels) for several free models, and recommending Nemotron 3.5 Super VL as the default choice (vision support, highest real-world Kilo usage, track record on this project) with Laguna S 2.1 as a secondary option for code/test tasks (noting it is scheduled for retirement around Oct 31). The person then asked about free OpenCode Zen models; this research was in progress when the conversation ended.

Throughout, the person showed a preference for receiving single consolidated prompts to paste directly into the Kilo agent rather than piecemeal instructions, explicitly requesting combined/condensed prompts multiple times ("дай мне М полностью в одном промпте", "дай мне все промпты"). The person also requested that agent final reports be shortened to a fixed short format (max 12 lines: Status/Commit/Done/Failed/Owner decision/Next action), which Claude codified as a persistent project rule. The person communicates in Russian, works from a mobile device (noted low battery multiple times), and makes final subjective calls on footage/audio quality by direct playback review rather than relying on automated QC alone.

**Tool kn

## [human] 2026-10-17T17:44:07.619036Z
Изучи все файлы и скажи где мы остановились
[attachment: OpenMontage_chat_summary_and_analysis.md]
# OpenMontage: итог последнего чата и глубокий разбор

**Чат:** «Поиск лучшей ниши для бизнеса» (68 сообщений, 16 окт 2026 08:58 UTC → 17 окт 2026 13:48 UTC).
**Это единственный чат в экспорте.** Он же самый свежий.
**Состояние на последнее сообщение:** агенту отправлен большой «MASTER RUN» (фазы P1–P7). Его результатов в чате нет.

Документ состоит из трёх частей.
- **Часть A** — что произошло и где вы сейчас.
- **Часть B** — глубокий разбор: что хорошо, что вызывает сомнения, что делать дальше.
- **Приложение** — полная переписка (ваши сообщения и ответы Claude, без технических выдач инструментов).

---

# Часть A. Что в чате произошло

## A1. Цель проекта

Построить автоматизированную «фабрику» длинных англоязычных документальных YouTube-видео без лица в кадре.
- Платформа: OpenMontage. Агент работает в GitHub Codespaces через Kilo Code.
- Режим строго $0: без платных API, без платных футажей.
- Результат должен быть проверяемым: каждый факт со ссылкой на источник, права на каждый клип, жёсткий QA.

## A2. Как менялась ниша

| Шаг | Что предлагалось | Итог |
|---|---|---|
| 1 | «Скрытый бизнес за обычными вещами» (гипотеза из старых файлов) | Perplexity подтвердил в суженном виде: логистика и инфраструктура |
| 2 | Компании и знаменитости | Знаменитости отвергнуты (права, клевета). Компании только как «второй слой» |
| 3 | Пилоты «вода», «контейнеровоз», «электросеть» | Footage по воде в основном фото, не видео |
| 4 | «Куда уходят деньги» (инфраструктура с другим углом) | **Вы отвергли инфраструктуру** |
| 5 | **История испытаний авиации и космоса на архивных кадрах NASA/ВВС** | **Принята** |

Что Claude выбирал при оценке ниш (веса: кадры 25, политика 20, конкуренция 20, спрос 15, RPM 10, автоматизация 10):
- Авиация/космос 7.1.
- История XX века на кадрах NARA 6.8.
- Инфраструктура 6.5.
- Бизнес и финансы 4.8.

Это **собственные оценки Claude**, не измерения. При большем весе спроса вперёд выходит история XX века.

## A3. Пилотная тема

**Controlled Impact Demonstration (CID):** NASA и FAA 1 декабря 1984 намеренно разбили дистанционно управляемый Boeing 720 на озере Роджерс (авиабаза Эдвардс). Проверялась антитуманная присадка к топливу FM-9.

Запасные темы после проверки кадров: X-15, XB-70, Helios, шаттл (посадочные тесты).
Тема Lunar Landing Research Vehicle отброшена: найдено 2 видео.

## A4. Архитектура фабрики (решения)

- **Максимум 3 рантайм-компонента:** OpenMontage (платформа, AGPL-3.0), HyperFrames (оригинальная графика, Apache-2.0), голосовая модель. Всё остальное — закреплённые скиллы или «только как образец». Четвёртый репозиторий только с вашего согласия.
- **Модель прав (fail-closed):** `rights_basis = explicit_license | source_policy_us_gov | unknown`. Неизвестное = не использовать. Любой клип с чужим кредитом (CNN, «courtesy of», копирайт) = REJECT, даже если вы его просмотрите.
- **Стадия 0 «жизнеспособность темы»:** ≥10 пригодных видеоклипов и ≥3 первичных документа до написания сценария.
- **Сценарий с учётом реальных к
[attachment: OPENMONTAGE_UNIFIED_PROJECT_CONTEXT_RU.md]
# OpenMontage Factory — единый контекст проекта, история решений и план дальнейшей работы

**Версия:** 1.0  
**Дата обновления:** 16 октября 2026  
**Назначение:** единый handoff-документ для пользователя, Kilo Code, OpenCode и других агентов. Сохраняет цель проекта, архитектуру, ограничения, решения, наблюдения из чата, вопросы для проверки и следующий план работ.

> **Правило достоверности:** документ объединяет сведения из текущего разговора и ранее сохранённых документов Library. Состояния Codespace, процессов, веток, ключей, моделей, квот, тестов и GitHub могут измениться. Перед действиями их нужно проверить в текущей рабочей копии. Нельзя выдавать старый статус за актуальный.

## 1. Краткое резюме

Строится **OpenMontage Documentary Factory** — воспроизводимая, максимально автоматизированная система производства англоязычных документальных YouTube-видео. Сначала нужно получить **одно качественное пилотное видео длиной 6–10 минут**, затем проверить весь цикл и только после этого масштабировать его в надёжный конвейер.

Текущая рабочая концепция канала: **The Hidden Business Behind Everyday Things** / **Behind Everyday Systems**.

Обещание зрителю: *“How overlooked businesses make money — and what happens when their systems fail.”*

Рассказывать, как производятся, перевозятся, обслуживаются и финансируются привычные товары и необходимые системы; где находятся узкие места, почему что-то дорого, кто на этом зарабатывает и что происходит при сбоях.

Это пока **рабочая гипотеза о нише**, а не доказательство низкой конкуренции или гарантии заработка. Пользователь попросил независимое исследование всех 100 предложенных ниш через Perplexity Deep Research. RPM-оценки из поста TikTok @weaponsgeek ($4–$22) помечены как непроверенные и не должны использоваться как фактические данные.

## 2. Главные цели и жёсткие ограничения

### Цели
- Довести существующий OpenMontage до реального end-to-end процесса.
- В первую очередь улучшать Kilo Code: правила, контекст, субагенты, skills, plugins/MCP, права, восстановление после перезапуска, контроль качества.
- Быстро и безопасно работать в ограниченных по времени сессиях GitHub Codespaces.
- Делать оригинальные, фактически проверенные документальные видео, а не шаблонные слайд-шоу со случайным B-roll.
- Получать проверяемые артефакты на каждом этапе и иметь возможность возобновить работу без повторного выполнения уже завершённых стадий.
- После проверки одного вертикального среза построить воспроизводимый конвейер.

### Ограничения
- Строгий режим **$0**: только проверенные бесплатные или локальные инструменты. Неизвестная цена = запрещено до проверки. Никакого платного fallback и обхода квот.
- Реальные кадры должны иметь подтверждённые права и происхождение. Нельзя выдавать иллюстративные или сгенерированные кадры за реальные доказательства.
- Каждый значимый факт должен иметь источник и статус проверки.
- Не публиковать и не планировать публикацию автоматически: финальное человеческое одобрение обязательно.
-
[attachment: OPENMONTAGE_HANDOFF_RU.md]
# OpenMontage — полный handoff для нового чата

**Язык общения:** со мной говорить по-русски. Промпты для Kilo Code, OpenCode и других coding agents писать на английском.  
**Снимок контекста:** по состоянию на сообщения от 14 октября 2026 года. Все живые процессы, файлы, ключи, маршруты и статусы необходимо перепроверить в Codespace: приведённые ниже статусы — последние наблюдавшиеся в чате, а не гарантия того, что они всё ещё актуальны.

## 1. Главная цель проекта

Построить **OpenMontage Documentary Factory** — настоящую автоматизированную фабрику документальных видео, а не только CLI или разовый ролик. Фабрика должна проходить путь от темы и исследования через доказательства, сценарий, fact-check, storyboard, озвучку, поиск/загрузку footage, монтажные решения, timeline, аудио, render, QA и packaging. Каждый этап должен иметь реальные входы/выходы, валидацию, provenance, сохранение состояния и возможность resume.

Приоритеты пользователя:
- Довести фабрику до реально работающего end-to-end пайплайна с проверенным свежим видео и аудио.
- Работать максимально бесплатно: **никакого платного fallback**, неясных тарифов, trial-only использования в production или обхода квот.
- Долгая автономная работа ночью: агент сам выбирает следующий этап, выполняет код, тесты, QA, сохраняет checkpoint и продолжает, без рутинных запросов разрешения.
- Модели должны автоматически переключаться при 429, timeout и 5xx; не зависать на одной модели.
- Иметь один ясный документ архитектуры и отдельный checkpoint для возобновления работы.
- Сначала проверять текущую реальность репозитория. Не верить старым отчётам без проверки.

## 2. Роли инструментов — очень важно не перепутать

- **OpenCode сейчас используется пользователем как сильный инженер/строитель системы:** он должен подготовить и исправить ночной runner для Kilo, конфигурацию, интеграции и код.
- **Kilo Code должен быть ночным worker/исполнителем:** runner запускает `kilo run`, а не `opencode run`.
- **OmniRoute** — предполагаемый шлюз моделей, доступный по `http://127.0.0.1:20128/v1`, когда его сервер запущен и доступен.
- **Kilo Gateway `kilo-auto/free`** — отдельный встроенный маршрут Kilo. Он управляется на стороне Kilo; нельзя считать, что в него можно локально добавить OmniRoute. Если это не поддерживается официально, использовать отдельный Kilo-provider alias `omniroute/auto-free` и переключение между отдельными bounded Kilo-сессиями.
- **Overnight runner** (`scripts/overnight_factory_runner.py` + `scripts/overnight.sh`) — единственный контроллер повторных Kilo-сессий, состояния, таймаутов, логов и checkpoints.
- Не запускать OpenCode и Kilo как два конкурирующих исполнителя, которые редактируют одни файлы одновременно.

## 3. Состояние ночного запуска на последнем известном шаге

Последнее подтверждённое отчётом состояние, 14 октября 2026:
- Runner запускался вручную командой ниже, ограничение — 5 итераций и максимум 6 часов.
- В последнем отчёте runner был `RUNNING`, PID `28688`, lock `.kilo/overnig

## [assistant] 2026-10-17T17:44:22.759571Z
**Где остановились:** агенту отправлен большой MASTER RUN (фазы P1–P7), и результатов от него в чате пока нет.

**Что уже сделано**
- **Ниша:** выбрана история испытаний авиации и космоса на архивных кадрах NASA, ВВС и NARA. Пилотная тема: Controlled Impact Demonstration (CID), когда в 1984 году NASA намеренно разбила дистанционно управляемый Boeing 720.
- **Инструменты:** Kilo-агенты созданы и видны в `kilo agent list`, но запускались inline, поэтому независимой проверки пока нет. Инструмент QC (`tools/qa/qc.py`, 11 тестов) и финальная обработка звука `finish_audio` работают. Мост Codespace → Kaggle прошёл живую «hello»-задачу (коммит `21903ee`).
- **Голос:** Piper lessac запрещён для публичных видео из-за неподтверждённой лицензии. Запасной вариант Kokoro (Apache-2.0) проверен. В MASTER RUN основным кандидатом поставлен Chatterbox Turbo, но он выбран без прослушивания.
- **Источники и сценарий:** шесть первичных документов внесены в реестр, 16 утверждений (CID-01…16) и сценарий на ~50 секунд подготовлены.
- **Кадры:** 11 клипов NASA по CID прошли проверку по метаданным. Для полного ролика статус `NEEDS_OWNER_REVIEW`, для среза на 30–60 секунд требования выполнены.

**Что ждёт именно вас**
1. Контакт-листы 11 клипов: узнаваемый человек, логотип, чужой кредит. «Не уверен» значит не используем. Ждут с самого начала проверки клипов.
2. Согласие на остаточный риск голоса вместе с родителем.
3. Монетизация: AdSense требует 18+, нужен аккаунт родителя. Доступность монетизации в вашей стране не проверена.
4. Верификация телефона на Kaggle, иначе фаза P3 с GPU и интернетом заблокируется.
5. Проверка спроса: 5 запросов в YouTube и скриншоты топ-10. Конкуренция и спрос до сих пор не измерены, а это главный пробел.

**Что блокирует публикацию**
- Утверждение CID-13 («присадка не снизила огонь») держится на одном источнике, поэтому строка сценария S8 заблокирована до второго.
- NTRS недоступен из песочницы агента, документы читал я.
- Эмблемы NASA, FAA и Boeing в кадре и политика по музыке требуют вашего решения.
- Единственное готовое видео (про поддоны) не годится для публикации, QC дал ему FAILED.

**Следующий шаг:** дождаться отчёта агента по MASTER RUN. Если сессия оборвётся, напишите ему: «Resume the MASTER RUN from docs/openmontage/MASTER_RUN_STATE.md». Пока он работает, займитесь пунктами 1, 4 и 5, это около 30 минут. Потом пришлите скриншот финального отчёта P7, и я сделаю глобальную проверку.

## [human] 2026-10-17T17:45:37.693595Z
Вот и я параллельно сделал это изучи файл и скажи как-то можно обеденить эти скилы плагины в нашу фабрику
[attachment: KILO_CODE_YOUTUBE_FACTORY_MASTER.md]
# Kilo Code + OpenMontage Factory — master setup file

> **This is NOT `AGENTS.md` and does not replace your existing `AGENTS.md`.** Upload this file to the repository root as `KILO_CODE_YOUTUBE_FACTORY_MASTER.md`. It contains the two ZIP kits' setup instructions and embedded source resources. After uploading it, explicitly tell Kilo Code to read and execute this file.
>
> The existing root `AGENTS.md` must remain in place. Kilo should inspect it, preserve its content, and propose a small merge or a reference to this file only if needed.

## ACTIVE INSTRUCTIONS — APPLY THESE FIRST

### Mission
Improve the reliability of Kilo Code workflows and build/test the OpenMontage Factory YouTube production pipeline. Improve the workflow, project instructions, Skills, tools, tests and documentation; do not claim that the model itself is retrained or permanently learns new weights.

### Required startup behavior for every relevant task
1. Read the existing root `AGENTS.md` plus this `KILO_CODE_YOUTUBE_FACTORY_MASTER.md` when bootstrapping, then check the current repository, branch, README, Git status and architecture before edits.
2. Classify the task. Load only the Skills that are relevant; for factory work, use the orchestrator and the applicable research, rights, rendering, QA, publishing or self-improvement skill. Do not claim a Skill or MCP was used unless its contents were read or the tool actually ran.
3. If a project Skill does not exist yet, use its embedded resource below as the source of truth and materialize the corresponding `skills/<name>/SKILL.md` file on the first bootstrap task.
4. Before editing, inspect existing files, make timestamped backups outside generated/replaced folders, and use small reversible changes. Never overwrite unknown user content without comparing it first.
5. Run appropriate tests and report real `PASS`, `FAIL`, or `NOT_CHECKED` statuses. Do not invent command output or claim a test passed if it was not run.
6. Finish significant engineering tasks with: files changed, actual Skills/tools used, checks run and results, remaining limitations, and lessons/backlog items when evidence supports them.

### First-run bootstrap — perform when the user asks you to execute this file
This Markdown file is not automatically active just because it exists in the repository. When the user asks you to execute it, do not stop at summarizing the plan. Perform the following safe steps in this order:

1. **Preflight.** Confirm repo root and branch; inspect `git status`, project README and existing instructions/config. Identify OS and how Kilo is running if available. Never print tokens, passwords, cookies, `.env` contents or other secrets.
2. **Backup.** Before changing any existing instruction or Skill, write a timestamped backup outside the directory being replaced. Record backup paths in the setup report. Do not add backups or secrets to Git.
3. **Materialize embedded resources.** Recreate the project files listed under `## EMBEDDED KIT R

## [assistant] 2026-10-17T17:45:59.193593Z
**Сначала итог по скриншоту: MASTER RUN завершён.** Коммит `8bc5f7b` запушен, дерево чистое, кроме вашего `AGENTS.md` (он сохранён).

- **Готово:** P1 лицензии голосов (Chatterbox MIT, Maya1 Apache-2.0, Kokoro Apache-2.0 прошли), P2 реестр и сценарий (QC claim_ids 9/9), P4 интеграция TTS с лицензионным гейтом (5 тестов), P5 реестр 19 источников, P6 срез 48.93 с (QC 12/12 PASS, NOT_PUBLISHABLE), P7 глобальная проверка. Тестов 32 прошло.
- **Заблокировано:** P3 (голосовой «бой» на Kaggle). GPU-задача встала в очередь на 15+ минут и не запустилась. Нужна верификация телефона и квоты Kaggle, останется одна попытка.
- **Важная поправка:** срез собран на Kokoro, а не на Chatterbox. Выбор голоса без прослушивания так и не подтверждён.
- **Агенты снова работали inline.** Независимой проверки нет.
- **Клипов в срезе 4**, у всех не проверены люди и логотипы.

Дальше откройте `docs/openmontage/OWNER_ACTIONS.md`.

## Можно ли объединить ваш мастер-файл с фабрикой

**Да, но выборочно.** Большая часть файла у нас уже есть в более сильном виде, и слепое выполнение его даст дубли и конфликты.

**Что уже перекрыто нашей работой:**
- Правила прав и происхождения: у нас `rights_basis`, fail-closed, `RIGHTS_MODEL.md`. Они жёстче, чем «лицензия и ledger» из файла.
- QA-гейт: у нас рабочий `tools/qa/qc.py` с тестами и `qa_report.json`. Скилл `youtube-quality-gate` описывает то же словами, без кода.
- Публикация вручную, ноль секретов, роли агентов (`editor`, `qa-reviewer` и т. д.), журнал уроков и тесты тоже уже есть.
- Скиллы `video-pipeline-ffmpeg`, `licensed-footage-audit`, `youtube-research-and-scripting` в целом совпадают с нашими `yt-script`, `edl-edit`, `audio-edit`.

**Что полезно взять:**
1. `docs/agent-improvement/` (LESSONS, BACKLOG, EVALS). Простое и безопасное дополнение, у нас такого журнала нет.
2. `kilo-self-improvement` как скилл, если хотите цикл улучшений с замерами «до/после».
3. `youtube-publishing-analytics`: пригодится позже, после первого видео.
4. Идея проверять «Skill реально загружен, а не просто лежит файлом».

**Что я бы не брал или менял:**
- **Скилл `video-rendering-remotion` не нужен.** Мы зафиксировали HyperFrames, а у Remotion своя коммерческая лицензия.
- **Не выполнять файл целиком.** Это ваш дубль «большого промпта»: он заново аудитит репозиторий, создаёт `docs/architecture/*` и запускает свой срез параллельно нашему.
- **Список MCP и репозиториев** (GitHub MCP, Serena, YouTube MCP, n8n) противоречит нашему правилу «максимум 3 рантайм-компонента и ноль секретов в v1». Исключение возможно только с вашего согласия.
- **Глобальный `AGENTS.global.md`** добавляет правила в `~/.config/kilo/`, а не в проект. Это вне нашего контроля, лучше держать правила в проекте.
- Два скилла файла противоречат нашей истории: «примерно 8 скиллов» против наших 7 уже установленных, возможны конфликты имён.

**Практичный способ объединить, не ломая работу:**

```text
MILESTONE M1 — selective merge of KILO_CODE_YOUTUBE_FACTORY_MASTER.md. Docs/skills only. No MCP installs, no global config changes, no process/lock changes. Time-box 30 min. Roles inline: say so. Preserve user's AGENTS.md changes.
0. Preflight: git status, HEAD, kilo agent list, ls .kilo/skills.
1. Read the master file as REFERENCE ONLY. Do NOT execute its bootstrap or its "first-run vertical slice".
2. Create a comparison table docs/openmontage/MERGE_AUDIT.md: each of its 9 skills vs our existing tools/skills (overlap | gap | conflict) and each rule vs RIGHTS_MODEL/QA_SPEC/AGENTS.md.
3. Install ONLY: docs/agent-improvement/{LESSONS,BACKLOG,EVALS,CHANGELOG}.md (templates), and the kilo-self-improvement skill into .kilo/skills/ (project level). Read its SKILL.md first; report network calls/writes.
4. Do NOT install video-rendering-remotion (render stack is ffmpeg + HyperFrames). Skip skills that duplicate installed ones; list what was skipped and why.
5. Propose (do not apply) a short rules addition to AGENTS.md; show the diff.
6. Verify skill discovery with a real listing; mark anything unverified NOT_CHECKED.
Commit docs/skills only; push non-force; report the real result.
```

Если хотите, сначала посмотрите `OWNER_ACTIONS.md`: три ваших решения (голос, клипы, эмблемы) сейчас важнее, чем любые новые скиллы.

## [human] 2026-10-18T01:14:40.900907Z
Дай мне сразу М полностью в одном промпте

## [assistant] 2026-10-18T01:15:24.953434Z
Один промпт целиком. Он запускает только выборочное слияние (M1) и ничего не трогает вне проекта.

```text
MILESTONE M1 — selective merge of KILO_CODE_YOUTUBE_FACTORY_MASTER.md into the factory. Docs and project-level skills only. Time-box 35 min. No MCP installs, no global Kilo config changes (~/.config/kilo, kilo.json/kilo.jsonc untouched), no process/lock changes, no paid routes, no secrets. Roles inline: say "inline, not independent". Preserve the owner's uncommitted AGENTS.md modification exactly. Never claim a command, install, commit, push or skill discovery you did not observe.

0. PREFLIGHT (look only): git status --short --branch, HEAD, df -h /workspaces, `kilo agent list`, ls .kilo/skills, ls docs/agent-improvement (if it exists). Find KILO_CODE_YOUTUBE_FACTORY_MASTER.md in the repo (if not found: STOP and report the exact missing path). Back up AGENTS.md to a timestamped copy OUTSIDE tracked folders (e.g. /tmp), never committed.

1. TREAT THE MASTER FILE AS REFERENCE ONLY. Do NOT run its "first-run bootstrap", do NOT re-audit the whole repo, do NOT create docs/architecture/current-state.md or target-state.md, do NOT run its own vertical slice, do NOT run its install scripts. Our existing milestones (RIGHTS_MODEL, QA_SPEC, tools/qa/qc.py, finish_audio, TTS tool, MASTER_RUN results) are the source of truth when anything conflicts.

2. WRITE docs/openmontage/MERGE_AUDIT.md. Table A: each of the master file's 9 skills (kilo-self-improvement, youtube-factory-orchestrator, youtube-research-and-scripting, licensed-footage-audit, video-pipeline-ffmpeg, video-rendering-remotion, youtube-quality-gate, youtube-publishing-analytics, youtube-factory-self-improvement) vs what we already have (installed skills in .kilo/skills, tools, docs, agents). Columns: master item | our equivalent (path or NONE) | verdict (OVERLAP | GAP | CONFLICT) | decision (INSTALL | SKIP | MERGE-IDEAS-ONLY) | reason. Table B: each rule block of the master file (rights/provenance, publishing safety, pipeline stages, definition of done, self-improvement, MCP/tool list) vs our RIGHTS_MODEL.md, QA_SPEC.md, AGENTS.md, plan v3.2 (same columns). Flag every conflict explicitly, including: Remotion vs our HyperFrames decision; extra MCPs (GitHub MCP, Serena, jCodeMunch, YouTube MCP, n8n, Context7) vs the "max 3 runtime components + zero secrets in v1" rule; global AGENTS/global skill paths vs project-level only; the master file's NOT_CHECKED status wording vs our qa_report statuses (map them, do not replace ours).

3. INSTALL ONLY THESE (project level, nothing global):
 a) docs/agent-improvement/LESSONS.md, BACKLOG.md, EVALS.md, CHANGELOG.md from the master file's templates. If any exists, compare and merge, never overwrite. Seed LESSONS.md with these evidence-backed entries from our own history (observation -> evidence -> cause -> change), no secrets: (i) rights gate applied stricter than the written rule (C3); (ii) archive.org "0 bytes" caused by missing curl -L (C5); (iii) subagent roles executed inline, no independence; (iv) NTRS unreachable from the sandbox; (v) single-source load-bearing claim CID-13; (vi) disk filled by torch/caches in Codespace. Seed EVALS.md with 5 fixed tasks: qc.py on a known-bad MP4 must FAIL; finish_audio on clipped audio must reach target loudness/true peak; TTS tool must refuse Piper lessac; claim_ids check must fail on an unknown claim_id; a clip with third-party credit must classify REJECT.
 b) skill kilo-self-improvement into .kilo/skills/kilo-self-improvement/SKILL.md (name must equal folder name). BEFORE installing: read the full SKILL.md and report network calls, file writes, env vars. Adapt it: the loop must use our EVALS.md and must never modify global config, permissions or skills automatically.
 c) Optionally youtube-publishing-analytics ONLY as a stub in docs/openmontage/ (not an active skill), marked "after first published video; manual publish only; no OAuth now".
 d) Do NOT install video-rendering-remotion (render stack = ffmpeg + HyperFrames). Do NOT install skills that duplicate installed ones (orchestrator, research/scripting, licensed-footage-audit, ffmpeg pipeline, quality-gate): instead extract any missing checklist items into MERGE_AUDIT.md under "ideas to port" for owner review.

4. PROPOSE, DO NOT APPLY: a short additive rules block for the project AGENTS.md (max ~25 lines: load only relevant skills; report only skills/tools actually used; record repeatable failures in LESSONS.md; propose improvements via BACKLOG.md; no silent changes to config/MCP/permissions). Show it as a diff in docs/openmontage/AGENTS_PROPOSED_DIFF.md. Do not touch the real AGENTS.md.

5. VERIFY (observed only): list .kilo/skills and show that kilo-self-improvement has correct name/description front matter; if the installed Kilo can list skills (check `kilo --help` for a skills subcommand), run it and paste the real output; otherwise mark discovery NOT_CHECKED and say how the owner can check. Run tools/qa/qc.py's claim/rights checks or the existing fast test suite only to confirm nothing broke; report exact commands and exit codes.

6. UPDATE docs/openmontage/MASTER_RUN_STATE.md or the work log (observed vs assumed), add an M1 entry to docs/agent-improvement/CHANGELOG.md with rollback = git revert of this commit. Commit docs and skill files only (never AGENTS.md, never media, never secrets); push non-force; report the real result.

FINAL REPORT (short): files created/merged, skills installed vs skipped (with reasons), conflicts found, verification results (PASS/FAIL/NOT_CHECKED), what the owner must decide, one exact next action.
```

После выполнения пришлите скриншот отчёта. Параллельно можно открыть `docs/openmontage/OWNER_ACTIONS.md`: решения по голосу, клипам и эмблемам по-прежнему ждут вас.

## [human] 2026-10-18T01:26:55.924060Z


## [assistant] 2026-10-18T01:27:19.307704Z
Агент остановился правильно: файла `KILO_CODE_YOUTUBE_FACTORY_MASTER.md` в репозитории нет. Он лежит только у нас в чате, на диск Codespace его никто не загружал.

Заодно скриншот показал важное: мастер-файл уже частично выполнялся раньше. В `docs/architecture/current-state.md` и `target-state.md` стоит пометка, что они созданы при bootstrap этого файла (17 октября). В `.kilo/skills` уже лежат все 8 YouTube-скиллов и `kilo-self-improvement`, в `docs/agent-improvement/` есть BACKLOG, CHANGELOG, EVALS и LESSONS от 17 октября. То есть часть слияния уже сделана вашим параллельным запуском, причём без пометки, что в них писалось.

Из этого следует, что промпт M1 надо изменить: вместо «установить» он должен «сверить уже установленное с нашими решениями». Дублировать ничего не нужно.

**Что сделать (1 минута):** ответьте агенту в Kilo, что файла в репозитории нет и работать нужно по уже установленному:

```text
Do not wait for the master file. Proceed with M1 in AUDIT-AND-RECONCILE mode, because its outputs already exist in the repo. Use the installed state as the source of truth instead of the missing file:
1. Read the existing .kilo/skills/* (all 9 master-origin skills), docs/agent-improvement/*, docs/architecture/current-state.md and target-state.md. For each, report who/what created it (git log -- <path>, dates) and whether it contradicts our RIGHTS_MODEL.md, QA_SPEC.md, plan v3.2, or the "max 3 runtime components + zero secrets in v1" rule.
2. Write docs/openmontage/MERGE_AUDIT.md: table of each installed master-origin skill vs our own skills/tools (OVERLAP | GAP | CONFLICT | decision KEEP | DISABLE-PROPOSAL | MERGE-IDEAS). Flag explicitly: video-rendering-remotion (our render stack is ffmpeg + HyperFrames) and youtube-publishing-analytics (publishing is manual-only for now) as candidates to disable or mark inactive; list any skill-name overlaps with yt-script, yt-package, edl-edit, audio-edit.
3. Check docs/architecture/*.md for claims not verified against our actual state; mark mismatches, do not rewrite them.
4. Seed docs/agent-improvement/LESSONS.md and EVALS.md with the six lessons and five fixed evals (rights gate stricter than written rule; archive.org needs curl -L; roles executed inline; NTRS unreachable; single-source CID-13; disk filled by torch/caches; evals: qc.py fails a bad MP4; finish_audio hits loudness/true-peak target; TTS tool refuses Piper lessac; claim_ids check fails on unknown id; third-party-credit clip classifies REJECT). Merge, never overwrite existing entries.
5. Do NOT delete or move any skill; only PROPOSE disabling in MERGE_AUDIT.md. Do not touch AGENTS.md (owner's uncommitted changes). Propose an additive rules block in docs/openmontage/AGENTS_PROPOSED_DIFF.md.
6. Verify observed only (ls, front matter, existing fast tests with exit codes). Commit docs only, push non-force, report PASS/FAIL/NOT_CHECKED.
```

Диск 3.3 ГБ свободно, этого хватает. Пришлите скриншот отчёта, когда закончит.

## [human] 2026-10-18T01:27:49.894060Z
Нет файл есть пусть лучше ищет

## [assistant] 2026-10-18T01:28:09.791369Z
Понял. Тогда агент просто плохо искал: он искал по точному имени и по `*master*`, а файл мог попасть в Codespace под другим названием (например, с «(1)» в конце, как у `OPENMONTAGE_FACTORY_MASTER_PLAN_RU (1).md`) или в другую папку, не в `/workspaces/OpenMontage`.

Отправьте агенту этот промпт:

```text
The master file exists; the previous search was too narrow. Search harder, read-only, and do NOT stop until you have tried all of these:
1. Case-insensitive search of the whole filesystem for name fragments: find / -xdev -iname '*kilo*youtube*' -o -iname '*youtube*factory*' -o -iname '*kilo_code*' 2>/dev/null (exclude /proc, /sys, node_modules, .git).
2. Search file CONTENTS for unique strings from the file: grep -rIl --exclude-dir=.git --exclude-dir=node_modules -e 'Kilo Code + OpenMontage Factory' -e 'master setup file' -e 'EMBEDDED KIT RESOURCES' -e 'RESOURCE FILE:' /workspaces ~ /tmp 2>/dev/null
3. Check likely places: repo root, docs/, tools/, uploads/, ~/Downloads, /workspaces/*, /tmp, and git: git ls-files | grep -i -e kilo -e youtube -e master; git log --all --diff-filter=A --name-only | grep -i -e kilo_code -e youtube_factory.
4. Check untracked and ignored files: git status --short --ignored | grep -i -e kilo -e youtube -e master.
5. Case variants and suffixes: "(1)", "(2)", ".txt", ".md.txt", spaces instead of underscores.
Report every candidate path with size and mtime. If one matches (it should start with "# Kilo Code + OpenMontage Factory — master setup file" and contain "EMBEDDED KIT RESOURCES"), use it as the reference and continue the M1 milestone in AUDIT-AND-RECONCILE mode (installed skills and docs/agent-improvement already exist; compare, do not overwrite; propose, do not apply AGENTS.md changes). If truly nothing is found after all five steps, report the exact commands run and their output, then continue M1 using the installed state as the source of truth.
```

Если и после этого не найдёт, значит файл остался в загрузках телефона и в Codespace не попал. Тогда загрузите его в репозиторий через проводник VS Code (перетащить в папку `docs/`) и скажите агенту точный путь.

## [human] 2026-10-18T01:44:18.083063Z
Пуст вывод агента будет кратче

## [assistant] 2026-10-18T01:44:42.910239Z
Принято. Вот промпт, который делает отчёты агента короткими:

```text
OUTPUT STYLE (applies to every milestone from now on, saved as a project rule):
1. Work exactly as before; only the FINAL report is shortened. Keep full detail in files (docs/..., MASTER_RUN_STATE.md), not in the terminal.
2. Final report format, max 12 lines, no tables:
 - Status: DONE | PARTIAL | BLOCKED
 - Commit: <hash>, pushed yes/no
 - Done: up to 3 short bullets
 - Failed/NOT_CHECKED: up to 3 short bullets (or "none")
 - Owner decision needed: up to 3 bullets (or "none")
 - Next action: one sentence
3. No restating of the task, no list of every file, no per-skill tables. Say "details: <path>" instead.
4. Never shorten honesty: keep "inline, not independent", real PASS/FAIL/NOT_CHECKED, and any blocker. If something failed, say it first.
5. Append this rule to the existing work log or docs/agent-improvement/CHANGELOG.md (do not touch AGENTS.md), commit docs only, push non-force.
```

По M1 коротко: слияние выполнено, коммит `528b9fe`, запушен, `AGENTS.md` не тронут. Мастер-файл агент нашёл в истории git (`36e6595`), а не в рабочей папке. Тесты проходят, лишних скиллов не поставлено. От вас нужно прочитать `docs/openmontage/MERGE_AUDIT.md` (таблица B) и `AGENTS_PROPOSED_DIFF.md`, но это не срочно. Срочнее остаются решения из `OWNER_ACTIONS.md`: голос, клипы и эмблемы.

## [human] 2026-10-18T01:47:44.488730Z
Вот

## [assistant] 2026-10-18T01:48:11.722140Z
Я прочитал все пять экранов. Коротко.

**MERGE_AUDIT.md и AGENTS_PROPOSED_DIFF.md: можно принимать.** Четыре конфликта описаны верно, решения разумные: Remotion не используем, MCP не ставим, глобальные пути не трогаем, статус `NOT_CHECKED` из мастер-файла отображается на наши `BLOCKED`/`NOT_RUN`. Предложенный блок для `AGENTS.md` добавляет четыре правила (роли inline, только нужные скиллы, отчёт только о реально использованном, без тихих изменений конфига). Он безопасный, но я бы добавил в него и правило про короткий итоговый отчёт. Применять его пока не нужно: ваш `AGENTS.md` изменён и не закоммичен, сначала решите, что с ним делать.

**Одна мелкая неточность.** В таблице A у `youtube-publishing-analytics` написано SKIP, но скилл при этом уже установлен и активен. Агент пометил его «неактивным» только в тексте. Если хотите, чтобы он реально не срабатывал, его надо отключить или удалить из `.kilo/skills`. То же с `video-rendering-remotion`.

**OWNER_ACTIONS.md: это сейчас главное.** Всё, что блокирует публикацию, ждёт вас, ни один пункт не закрыт:
1. Голос: принять Kokoro (Apache-2.0, но есть CC BY-данные и неясное происхождение синтетики) или выбрать другой. Решение нужно записать вместе с родителем.
2. Клипы: 4 клипа среза, у каждого три вопроса (человек, логотип, чужой кредит). Файл `contact_sheet.jpg` лежит в `projects/slice_cid_v0/`.
3. CID-13 держится на одном источнике, и S8 из-за этого заблокирован. Такие же риски у CID-06, 10, 12, 14, 15.
4. Эмблемы NASA: решить, нужно ли отдельное разрешение.
5. Монетизация и AdSense: пока вообще не оценивались.
6. Kaggle: подтвердить телефон, потом можно повторить голосовой тест.

**С чего начать (10 минут):** откройте `contact_sheet.jpg` и ответьте мне по четырём клипам в виде «1: нет/нет/нет, 2: …». «Не уверен» значит не используем. Тогда я оформлю решение по клипам для агента. После этого откройте на телефоне `final_slice.mp4` и скажите, подходит ли голос Kokoro на слух.

## [human] 2026-10-18T01:49:27.221629Z
А где эти файлы

## [assistant] 2026-10-18T01:49:31.210665Z


## [human] 2026-10-18T01:53:22.869784Z
И видео озвучка хорошая оставляем и ещё в видео видны футажи но из качества желает оставлять лучшего

## [assistant] 2026-10-18T01:54:25.662147Z
**Голос Kokoro оставляем.** Это ваше решение после прослушивания, и оно закрывает пункт 1 из OWNER_ACTIONS. Осталось записать его вместе с остаточным риском данных, а родителю сообщить отдельно.

**По кадрам.** На скриншоте `contact_sheet.jpg` во всех 12 кадрах только логотип NASA, никакого реального видео. Скорее всего, это не футаж: archive.org для таких клипов отдаёт заглушку-превью с эмблемой, а агент мог собрать срез из неё. Если так, то у среза два дефекта:
- Картинка не настоящая, поэтому низкое качество, которое вы заметили, объясняется именно этим.
- Эмблема NASA на весь кадр это не «случайно попавшая в кадр» вещь, а прямое использование логотипа, которое правила NASA запрещают.

Пока я не уверен: это только контакт-лист. Откройте `final_slice.mp4` и скажите, видите ли вы там настоящие кадры (самолёт, пожар) или логотип. Если логотип, то клипы надо брать заново.

Промпт для агента:

```text
MILESTONE F1 — fix slice footage quality. Roles inline: say so. No new installs, no paid routes. Max 20 network requests, curl -L, total downloads <= 400 MB in gitignored projects/.
1. Diagnose: ffprobe each projects/slice_cid_v0/clip0*_scaled.mp4 and the source files (resolution, bitrate, duration, frame count). Extract 3 frames per clip and report whether frames are real footage or the NASA logo placeholder (compare frames to each other; identical frames = placeholder). State which archive.org file each clip actually came from.
2. For the 4 clips, fetch the archive.org metadata file list again and pick the BEST real video derivative (largest h264/mp4 or original MPEG2, not the ~512kb or thumbnail file, not .jpg/.gif). Record file name, size, resolution, sha256.
3. Rebuild the slice with the better files: scale with high quality (lanczos), no upscaling beyond 1080p, keep aspect (pad, don't stretch), crf 18, 30 fps. Re-run finish_audio and tools/qa/qc.py on the final MP4.
4. Contact sheet of the NEW final video: 12 frames. If any frame still shows the NASA logo or a title card as the main picture, mark logo_visible=true and REJECT that clip.
5. Update rights_records/credits, qa_report, docs. Commit docs/code only (never media), push non-force.
Final report max 12 lines: Status, Commit, Done, Failed, Owner decision, Next action.
```

После выполнения пришлите скриншот нового контакт-листа, и по нему ответите на три вопроса про клипы.

## [human] 2026-10-18T01:56:33.046001Z
final_slice.mp4 я вижу самолёт как они подают пожары и ТД но не вижу логотипов и ещё в видео использовались футажи с очень низким качеством мне бы хотелось чтобы качество было по лучше

## [assistant] 2026-10-18T01:56:58.751307Z
Тогда логотип на контакт-листе был просто заглушкой самого файла, а в видео настоящие кадры. Это хорошо: клипы реальные, и пункт «логотип виден» по вашему просмотру можно отметить «нет». Но проверьте и людей: был ли крупным планом узнаваемый человек?

**Про качество.** Причина почти наверняка в том, что агент брал самые лёгкие превью (файлы около 512 КБ, они мелкие и сильно сжатые), потому что мы ограничили загрузку 200 МБ. Это можно исправить: у NASA в этих же записях на archive.org обычно есть и более крупные копии. Честный предел: старые плёнки 1984 года сами по себе низкого разрешения, поэтому «1080p чётко» не получится, но заметно лучше, чем сейчас, возможно.

Отправьте агенту:

```text
MILESTONE F1 — improve slice footage quality. Roles inline: say so. No new installs, no paid routes. Max 25 network requests, curl -L, downloads <= 600 MB total in gitignored projects/. Delete temp files after.
1. Diagnose: ffprobe the 4 clips in projects/slice_cid_v0 (resolution, bitrate, fps) and report which archive.org file each came from. Owner saw real footage, so do not treat them as placeholders.
2. For each of the 4 clips, re-read the archive.org metadata file list (never guess names) and choose the BEST available video derivative (highest resolution/bitrate: original or large h264/mp4, not the ~512kb version). Report name, size, resolution, sha256 per clip. If a clip has no better file, say so and keep it.
3. Rebuild the slice: scale with lanczos, no upscaling beyond source (pad/letterbox, do not stretch), crf 18, 30 fps, keep audio chain. If a clip is much worse than the others, propose replacing it with a better CID clip from REVIEW_QUEUE (rights_basis source_policy_us_gov, no third-party credit).
4. Re-run finish_audio and tools/qa/qc.py on the final MP4. Make a before/after table of resolution and bitrate per clip.
5. Update rights_records and credits, commit docs/code only (no media), push non-force.
Final report max 12 lines: Status, Commit, Done, Failed, Owner decision, Next action.
```

Когда закончит, посмотрите новый `final_slice.mp4` и скажите, стало ли лучше. И ответьте на вопрос про людей в кадре: тогда закроем пункт по клипам.

## [human] 2026-10-18T02:26:22.032094Z


## [assistant] 2026-10-18T02:26:52.539579Z
**Итог F1: качество картинки это не исправило, и вот почему.** Все 4 клипа на archive.org существуют только в разрешении 320×240. Лучшей копии там нет, агент это проверил по метаданным. Он растянул их до 1920×1080 с чёрными полями, битрейт вырос, но чёткость от этого не появилась. Это предел источника, а не ошибка настройки.

**Новая проблема:** QC теперь выдаёт `FAILED`.
- Громкость −17.0 LUFS при цели −14 ±2. Это не критично: для озвучки без музыки −16…−14 обычно приемлемо. Допуск можно расширить, но решение за вами.
- `freezedetect`: замороженный участок 2.43 с при допуске 2.0 с. Может быть реальным стоп-кадром в плёнке или артефактом растяжения.

Коммит `a854e10` запушен, `AGENTS.md` не тронут.

**Что с качеством делать (выбор за вами):**
1. **Принять 320×240 как стиль архивной плёнки.** Тогда показывать их в уменьшенном размере в рамке на фоне, а не на весь экран. Так выглядит заметно лучше, и это нормальный приём для старых кадров.
2. **Искать те же события в лучшем качестве:** NASA Armstrong (YouTube-канал и коллекция Dryden), images.nasa.gov с «orig»-файлами, NASA SVS. Нужен поиск, это отдельная веха.
3. **Больше оригинальной графики** (схемы, карты, карточки источников), чтобы клипы были короче и не тянули картинку.

Моя рекомендация: 1 плюс 3 сейчас, 2 как отдельную проверку.

Промпт на оба шага:

```text
MILESTONE F2. Roles inline: say so. No installs, no paid routes. Max 25 network requests, curl -L, downloads <= 600 MB in gitignored projects/.
1. Layout fix: rebuild the slice so 320x240 archive clips are NOT stretched to full screen: place each at 2x integer scale (640x480) centered on a dark blurred/solid background with a thin frame, plus on-screen source card under it. Keep audio chain.
2. QC: investigate the 2.43 s freezedetect hit (frame-compare the segment: real still frame in source or artifact). If source still, trim/cut around it. Do NOT change thresholds; propose a threshold change for the -17.0 LUFS result in docs only, with reason (narration-only, no music).
3. Higher-quality source probe (read-only, keyless): search images.nasa.gov API and archive.org for the same CID footage with larger files (original/MPEG2/mp4 above 640x480), and check NASA Armstrong's Dryden collection pages. Report per clip: candidate, resolution, rights_basis, third-party credit, URL. Do not download more than 3 test files.
4. Re-run finish_audio and tools/qa/qc.py; commit docs/code only; push non-force.
Final report max 12 lines: Status, Commit, Done, Failed, Owner decision, Next action.
```

Параллельно ответьте на вопрос: был ли в кадрах узнаваемый человек крупным планом? Это последняя неотвеченная часть проверки клипов.

## [human] 2026-10-18T03:04:24.124339Z


## [assistant] 2026-10-18T03:04:31.533119Z
**Итог F2 (коммит `4564085`, запушен, `AGENTS.md` не тронут):**

- **Картинка:** клипы больше не растянуты. Каждый 320×240 показан в 2× (640×480) по центру на тёмном фоне с рамкой и карточкой источника. Это честный вид для старой плёнки, должно выглядеть заметно лучше.
- **Замёрзший кадр:** причина найдена. В клипе 1 первые 6 секунд были заставкой (логотип и титр), а не видео. Агент заменил их на движущийся фрагмент 6.0–10.5 с, `freezedetect` теперь PASS.
- **Лучшие источники:** их нет. Все видео CID на archive.org и в NASA API имеют максимум 320×240 (остальное это фото). Поиск лучшего качества там исчерпан.
- **QC всё ещё FAILED по двум пунктам:**
  - громкость −17.1 LUFS при цели −14 ±2 (агент предложил для озвучки без музыки −16 ±2, это в `EBUR128_THRESHOLD_PROPOSAL.md`, пороги не менял);
  - `silencedetect` 0.1006 при пороге 0.10, то есть на границе, в клипе 1 тихий участок.
- Проверки длительности, субтитров и claim_ids не запускались (`NOT_RUN`, нет входных данных).

**Что решить вам:**
1. Согласны ли на порог −16 ±2 для озвучки без музыки? Обоснование разумное, но это ваш выбор, а не мой.
2. Посмотрите новый `final_slice.mp4`: стало ли лучше?
3. Вопрос про людей в кадре всё ещё без ответа: был ли узнаваемый человек крупным планом?

**Совет по качеству:** лучшее, что можно сделать с такими кадрами, это больше своей графики (схемы траектории, карточки источников, цифры на экране) и короткие вставки архивных клипов. Тогда зритель видит плёнку как документ эпохи, а не как основное изображение. Это ложится и на требование YouTube о добавленной ценности.

Если ответите «да» по порогу, пришлю короткий промпт на применение (тест и запись в конфиг).

## [human] 2026-10-18T03:10:08.060158Z
Твоя задача изучить проблему с качеством футажей и найди решение

## [assistant] 2026-10-18T03:10:36.885539Z
Ищу сразу по трём направлениям: лучшие исходники тех же событий, бесплатное улучшение старой плёнки и приёмы монтажа.
```
This block is not supported on your current device yet.
```

```
This block is not supported on your current device yet.
```

```
This block is not supported on your current device yet.
```

```
This block is not supported on your current device yet.
```




**Причина понятна: это предел самой плёнки.** Все видео CID в открытых архивах имеют разрешение 320×240, это их оригинальный формат, а не наша ошибка. Выход есть, но не один, а набор приёмов.

**Что я нашёл**

1. **Фото высокого качества существуют.** На официальной странице NASA Armstrong (nasa.gov/centers/armstrong/multimedia/imagegallery/CID) лежат кадры CID: подлёт, удар, огненный шар, манекены в салоне. Одно из фото, например, 3000×2670 пикселей, и они в общественном достоянии. Для документалки это лучший материал: медленный наезд на чёткое фото смотрится заметно лучше, чем растянутая плёнка. Условия те же: без эмблем и людей крупным планом, права проверяем по каждой записи.
2. **Оригиналы съёмки лучше архивных копий.** Отчёт FAA/JPL (DOT/FAA/CT-85/35, 435 страниц) описывает каталог плёнок и лент, снятых 16-мм и другими камерами. Внутри салона снимали десять скоростных 16-мм камер (400 кадров/с), и вся плёнка сохранилась. Сканы этих оригиналов могли бы быть заметно чётче, но в открытом доступе я их не нашёл. Архив NASA Armstrong принимает запросы: ARC-DL-archives@mail.nasa.gov. Результат и сроки неизвестны.
3. **YouTube-канал NASA Armstrong** выложил около 500 архивных роликов, включая CID. Они могут быть чуть лучше, но я не знаю их реальное разрешение. Скачивать с YouTube мы себе запретили (правило «не качать видео с YouTube»), поэтому этот путь закрыт, пока вы сами не решите иначе.
4. **ИИ-улучшение возможно, но с оговорками.** Real-ESRGAN (лицензия BSD-3) и Video2X умеют увеличивать старое видео. На CPU это очень медленно, нужен GPU, а Kaggle у нас заблокирован верификацией телефона. Главное, ИИ достраивает детали, которых не было. Для документального «доказательства» это спорно: если применять, то только мягко и с пометкой в описании. Это четвёртый компонент, а наше правило допускает три, поэтому нужно ваше согласие. Улучшение лиц нельзя вообще.

**Моё решение по порядку**
1. **Сейчас, $0:** ролик строим на чётких фото NASA и своей графике (схема траектории, карта места, карточки источников, цифры). Видео-клипы идут короткими вставками по 3–6 секунд в рамке.
2. **Параллельно:** написать в архив NASA Armstrong с просьбой о более качественных копиях CID. Письмо подготовлю.
3. **Потом, по желанию:** тест мягкого ИИ-улучшения на одном клипе после Kaggle.

Промпт для агента:

```text
MILESTONE F3 — still-image-led slice. Roles inline: say so. No installs, no AI upscaling, no YouTube downloading. Max 25 network requests, curl -L, downloads <= 300 MB in gitignored projects/.
1. From https://www.nasa.gov/centers/armstrong/multimedia/imagegallery/CID/index.html (and linked item pages) list every CID photo: id (EC84-/ECN-), caption, max resolution, rights text on the NASA page, any credit line. Keep only NASA-produced, no third-party credit. Download the highest-res version of up to 8, record sha256 and resolution. Flag identifiable_persons and logo_visible from caption only (owner reviews pixels).
2. Build the slice again: stills as primary visuals with slow pan/zoom (ffmpeg zoompan, max 1.15x, 1080p, no upscaling beyond source), archive clips only as 3-6 s inserts in the 2x framed layout, plus 2 original graphics (flight-path/timeline card and key-numbers card from the claim ledger, claim_ids shown). Voice unchanged (Kokoro). Added-value gate: report share of original graphics vs archive.
3. Run finish_audio and tools/qa/qc.py. Do not change thresholds.
4. Write docs/openmontage/FOOTAGE_QUALITY.md: findings (all CID video 320x240; stills hi-res), a draft email to ARC-DL-archives@mail.nasa.gov requesting higher-quality digitized CID film/video copies (no claims, just a request), and the AI-upscaling option marked "needs owner approval, 4th component".
5. Commit docs/code only (no media), push non-force.
Final report max 12 lines: Status, Commit, Done, Failed, Owner decision, Next action.
```

После запуска посмотрите новый `final_slice.mp4`. Если стало лучше, продолжаем по этому пути. Одновременно ответьте на вопрос про людей в кадрах клипов.

## [human] 2026-10-18T06:17:02.454217Z


## [assistant] 2026-10-18T06:17:13.510570Z
**Итог F3 (коммит `550f3e9`, запушен, `AGENTS.md` не тронут):** срез пересобран на фото. Готово 5 фото NASA Armstrong с плавным наездом, 3 коротких клипа плёнки в рамке, 2 оригинальные графики (маршрут и ключевые цифры с `claim_id`). Состав: фото ≈59%, архив ≈25%, графика ≈16%. Звук прошёл `finish_audio`. Документ `FOOTAGE_QUALITY.md` и черновик письма в архив NASA готовы.

**QC снова FAILED, но причины теперь объяснимые, а не качество:**
- `freezedetect` 4 с: это неподвижные титульные карточки, то есть задумано. Но гейт этого не знает.
- `silencedetect` 0.84 и громкость −22.3 LUFS: это тихие паузы без озвучки. Агент использовал только звук архивных клипов, **озвучки Kokoro в этой версии нет**. Это моя недоработка в промпте: я не написал, что голос надо оставить. Агент написал «voice unchanged», но фактически озвучки нет.

То есть этот вариант проверку не пройдёт, пока озвучка не вернётся и карточки не получат исключение. Пороги менять нельзя, но можно честно разметить карточки как «статичные по замыслу».

**Что решить вам:**
1. Одобрить письмо в архив NASA (`ARC-DL-archives@mail.nasa.gov`)? Это просьба о копиях получше, ничего не обещаем.
2. ИИ-улучшение плёнки: пока не нужно, фото решили главную проблему.
3. Посмотреть новое видео: стало ли чётче?

Дальше починим озвучку и QC:

```text
MILESTONE F4. Roles inline: say so. No installs, no new downloads, no threshold changes in qc.py.
1. Rebuild the F3 slice WITH the Kokoro narration (46 s, tools TTS + finish_audio) laid over the visuals; archive-clip audio muted or ducked under voice. Re-time visual beats to the script sentences S1-S8 (S8 stays BLOCKED/omitted: use only S1-S7) using word timestamps; regenerate subtitles.srt.
2. Static title/source cards: add a declared per-segment exemption mechanism in the QC config (e.g. segments flagged static_by_design in edit_decisions.json) so freezedetect hits inside those segments are reported as REVIEW with the reason, not silently ignored. Failing outside them stays FAILED. Show the code change test-first (red then green) and run existing fast tests.
3. Run qc.py on the final MP4 with duration_vs_script, subtitle_sync, claim_ids, rights_basis, credits_complete provided so they are not NOT_RUN. Report the real statuses; do not tune thresholds. Loudness target stays as configured; report measured LUFS.
4. Contact sheet (12 frames) and path. Commit docs/code/tests only (no media), push non-force.
Final report max 12 lines: Status, Commit, Done, Failed, Owner decision, Next action.
```

Пришлите отчёт, потом посмотрите `final_slice.mp4`.

## [human] 2026-10-18T06:57:12.585214Z


## [assistant] 2026-10-18T06:57:20.118285Z
**F4 выполнен (коммит `f819d38`, запушен, `AGENTS.md` не тронут).**

- Срез снова с озвучкой Kokoro: 46 с, фразы S1–S7 (S8 исключена, пока нет второго источника), фото с наездом, клипы в рамке, две графики, субтитры пересозданы.
- **QC: общий PASS.** Громкость −15.3 LUFS (в допуске), длительность, субтитры, `claim_ids`, права и credits проверены и пройдены. Единственная пометка REVIEW: неподвижные титульные карточки, они задуманы. Пороги не менялись, исключение для статичных сегментов добавлено с тестами (9 тестов проходят).
- Оговорка: проверки делал тот же агент, роли inline, независимого ревью нет.

**Что осталось до публикации (всё на вас, не на коде):**
1. **Посмотрите новый `final_slice.mp4`** и скажите, стало ли чётче и звучит ли голос нормально.
2. **Люди в кадре:** был ли узнаваемый человек крупным планом в фото или клипах? Пока без вашего ответа клипы остаются непроверенными.
3. **Письмо в архив NASA:** одобряете отправку? Текст в `docs/openmontage/FOOTAGE_QUALITY.md`.
4. **Источник для CID-13:** без второго подтверждения фраза S8 («присадка не помогла») не выйдет. Это главная мысль ролика, поэтому её стоит добить следующим шагом.
5. Решения из `OWNER_ACTIONS.md`: эмблемы NASA, монетизация и родитель, Kaggle (телефон).

Батарея телефона на 20%, поставьте на зарядку. Если хотите, следующим промптом дам поиск второго источника для CID-13 в первичных документах (FAA-отчёт и TM-89642).

## [human] 2026-10-18T07:01:28.069887Z
Видео не открывается нужно скачать или в порту открыть а вот это остальное

## [assistant] 2026-10-18T07:01:43.950521Z
**Как открыть видео (два способа)**

Сначала узнайте, где лежит свежий файл. Папки `f3` и `f4` на скриншоте как раз его версии, а `final_slice.mp4` в корне может быть старым. В терминале (вкладка рядом с Kilo, кнопка «+»):

```bash
ls -la --time=birth -t /workspaces/OpenMontage/projects/slice_cid_v0/f4 /workspaces/OpenMontage/projects/slice_cid_v0/*.mp4 | head -20
```

**Способ 1, скачать.** В проводнике откройте `projects → slice_cid_v0 → f4`, долгое нажатие на самый новый `final_slice.mp4` (или правая кнопка), пункт **Download** («Скачать»). Потом откройте файл в галерее телефона.

**Способ 2, через порт** (если Download нет):

```bash
cd /workspaces/OpenMontage/projects/slice_cid_v0/f4 && python3 -m http.server 8000
```

Откройте вкладку **«Порты»**, найдите порт 8000, нажмите значок глобуса или «Открыть в браузере» и коснитесь файла. После просмотра остановите сервер (Ctrl+C) и не делайте порт публичным.

**По остальным экранам**

1. **`FOOTAGE_QUALITY.md` и `OWNER_ACTIONS.md` устарели.** Там написан результат F3 (FAILED) и срез на 48.93 с с 12/12 PASS. Актуален F4: QC общий PASS, с REVIEW только на титульных карточках. Агент эти файлы после F4 не обновил, поэтому не ориентируйтесь на них.
2. **Моя поправка по качеству фото.** Я писал про фото в 3000×2670. Это были копии на стороннем зеркале. На официальной странице NASA они до 1040×816, и агент скачал именно их. Это тоже невысокое разрешение, на весь экран 1080p они мягкие. Более крупные версии могут быть в старой галерее dfrc.nasa.gov, их надо искать отдельно.
3. **Черновик письма в NASA нужно исправить.** В нём написано «non-commercial, educational», а канал планируется монетизировать. Так писать нельзя, это неправда. Замените на честную формулировку: «video for a YouTube documentary channel, with attribution per NASA media guidelines». Подпись «OpenMontage Factory» тоже лучше заменить на ваше имя или оставить на решение родителя.
4. **Подписи к фото безопасны:** агент отметил, что на ECN-28307 манекены, а не люди, и логотипы в подписях не упомянуты. Но пиксели смотрите вы сами.

Телефон на 19%, поставьте на зарядку. Когда посмотрите видео, ответьте на два вопроса: стало ли чётче, и видели ли узнаваемого человека крупным планом.

## [human] 2026-10-18T07:08:18.968998Z
В порту открылся f4.mp4 и качество футажей хорошое но здесь только фото и ещё никаких людей нету

## [assistant] 2026-10-18T07:08:33.879932Z
**Это хорошая новость.** Вы посмотрели новый `f4`: качество устраивает, людей и логотипов не видно. Значит, по клипам и фото вопросы про людей и эмблемы закрыты вашим просмотром. Запишем это как решение владельца с датой, а не «на словах».

Оговорка: вы проверили итоговое видео, а не каждый кадр исходных клипов. Для среза этого достаточно, для полного ролика просмотр надо будет повторить.

**Про «только фото».** Так вышло намеренно: фото чёткие, а плёнка 320×240. Но для документалки удар и пожар должны быть движущимися. Решение: оставить фото для подготовки и контекста, а момент удара и огненного шара показать видео с разных камер (у нас их около девяти, `NIX-LV-1998-00090…00098`, это один удар с разных ракурсов). Видео-вставки можно сделать длиннее, в рамке 2×. Правило «клип без пояснения не дольше 20 с» остаётся.

Промпт:

```text
MILESTONE F5. Roles inline: say so. No installs, no new network downloads except archive.org metadata/files already identified (max 15 requests, curl -L).
1. Record owner review in docs/openmontage/audit/REVIEW_QUEUE.md for the 4 slice clips and 5 stills: reviewer=owner, date=2026-10-18, scope="viewed in final f4 video only, not every source frame", identifiable_persons=no, logo_visible=no, third_party_credit=no. Update rights_records.json accordingly (gitignored) and mark the 4 clips USABLE_FOR_SLICE; full video still needs full-clip review.
2. Rebuild the slice so the impact and fire sequence is told with MOVING footage: use the multi-camera CID clips (NIX-LV-1998-00090..00098 and NIX-EM-0004-01/02) as 6-10 s framed 2x inserts from different angles for the approach, impact and fireball beats; keep stills for preparation/context and the two graphics cards. Target mix roughly: video 40-45%, stills 35-40%, graphics >=15%. Skip any clip with a static title card (trim to motion). Voice (Kokoro S1-S7), finish_audio, subtitles unchanged. S8 stays omitted.
3. Run tools/qa/qc.py with all inputs (static_by_design cards declared). Do not change thresholds. Report real statuses.
4. Fix stale docs: update OWNER_ACTIONS.md and FOOTAGE_QUALITY.md to the F4/F5 state. In FOOTAGE_QUALITY.md correct the NASA email draft: replace "non-commercial, educational" with "for a YouTube documentary channel (monetization possible), with attribution per NASA media guidelines"; sign as a placeholder [owner name], and note official NASA stills are max ~1040x816.
5. Commit docs/code only (no media), push non-force.
Final report max 12 lines: Status, Commit, Done, Failed, Owner decision, Next action.
```

После выполнения откройте новый `final_slice.mp4` тем же способом через порт 8000 и скажите, хватает ли теперь движения.

Что остаётся вам после этого: родитель и AdSense, решение по эмблемам NASA (на вашем просмотре их не видно), и второй источник для CID-13.

## [human] 2026-10-18T07:26:14.689632Z


## [assistant] 2026-10-18T07:26:28.483113Z
**F5 готов (коммит `cb4ea57`, запушен).** Удар и пожар теперь показаны движущимся видео с трёх камер, фото и две графики остались, озвучка Kokoro на месте, 46 с. QC общий PASS, громкость −15.3 LUFS, REVIEW только на статичных карточках. Устаревшие документы обновлены, в письме NASA исправлена формулировка. Ваш просмотр клипов записан как решение владельца, но только для среза.

**Срочно: письмо от GitHub.** Вы использовали 90% бесплатных часов Codespaces ($9.79 из $10.80). Агент работал часами, это главный расход. Что сделать сейчас:

1. **Код не пропадёт:** всё запушено в GitHub, ветка `factory/business-documentary-pilot`.
2. **Видео и аудио НЕ в GitHub.** Папка `projects/` в gitignore. Пока не кончился лимит, скачайте `final_slice.mp4` (вы уже умеете, через порт 8000 или пункт «Download»).
3. **Остановите Codespace, когда не работаете:** github.com/codespaces, «…» рядом с вашим, **Stop codespace**. Простой тоже тратит часы, пока он не остановился сам.
4. **Проверьте, что не спишутся деньги:** github.com/settings/billing, раздел Spending limits, у Codespaces лимит должен быть **$0**. Тогда при исчерпании он просто остановится, а не начнёт брать оплату. Часы обновляются каждый месяц.
5. **Запускайте агента только на коротких задачах.** Одна веха в день хватит до конца месяца. Остальное, что не требует Codespace (решения владельца, письмо, проверка источника через меня), делайте вне него.

Если лимит кончится, Codespace не запустится. Тогда рабочая копия останется на GitHub, а медиа, возможно, будет потеряно, поэтому скачайте сейчас.

**Что решить по существу:**
- **ИИ-улучшение плёнки: я бы отказался.** Фото и обработка дали приемлемое качество, а это четвёртый компонент и спорный приём.
- Просмотр всех исходных клипов для полного ролика и решение по эмблемам NASA пока в очереди.
- Письмо в архив NASA можно отправить с вашей почты, текст в `FOOTAGE_QUALITY.md`, подпись впишете сами.

Дальше без Codespace я могу сам найти второй источник для CID-13 (поиском по FAA-отчёту и TM-89642), чтобы разблокировать S8. Хотите?

## [human] 2026-10-18T07:27:31.663709Z
Давай сделаем максимально всё что можно за 2 часа и потом в другом аккаунте доделаем

## [assistant] 2026-10-18T07:28:17.601164Z
Пока агент будет работать, я сам закрою второй источник для CID-13, он не требует Codespace. Ищу.
```
This block is not supported on your current device yet.
```

```
This block is not supported on your current device yet.
```


**Второй источник для CID-13 найден, но формулировку S8 надо смягчить.**

- **NASA Facts** пишет, что модифицированное топливо не снизило ни распространение, ни интенсивность огня. Это наш единственный источник.
- **Отчёт FAA/DOT (DOT/FAA/CT-87/10)** в резюме говорит, что испытание «прошло не так, как планировалось», а данные по пожарной безопасности почти потеряны из-за сильного пожара. Прямую фразу про топливо я в доступном фрагменте не видел. Её надо прочитать в самом PDF (раздел про AMK, около 20-й страницы): `rosap.ntl.bts.gov/view/dot/92854/dot_92854_DS1.pdf`.
- **Независимые вторичные подтверждения:** Википедия со ссылкой на тот же отчёт FAA (присадка недостаточно снижала риск пожара), Smithsonian Air & Space и редакционная статья Christian Science Monitor от 4 декабря 1984 года (на испытании был огненный шар и упорное горение).
- **Расхождение:** FAA-версия добавляет, что меньшую интенсивность *начального* пожара приписывали присадке, а сторонники присадки утверждали, что без неё пожар был бы ещё сильнее. Поэтому слова «не снизило интенсивность» из NASA Facts использовать нельзя.

**Новая безопасная формулировка S8:** «Присадка, помогавшая в малых тестах, на полном масштабе не предотвратила огромный пожар, и после этого FAA отказалось требовать её от авиакомпаний.» Это подтверждается NASA Facts и FAA-версией. Статус CID-13: два источника, один пока вторичный.

**Про второй аккаунт.** Второй личный бесплатный аккаунт GitHub нарушает правила сервиса (один человек, один бесплатный аккаунт). Нормальные варианты: аккаунт родителя (он всё равно нужен для AdSense), подождать обновления часов в начале месяца, либо проверить GitHub Education для школьников. Проект переносится любым из них одинаково.

**Перед запуском (3 минуты):**
1. Скачайте `final_slice.mp4` с телефона (порт 8000 или «Download»).
2. Убедитесь, что лимит расходов Codespaces стоит $0.
3. Зарядите телефон.

**Промпт на всё, что успеет за ~100 минут** (по приоритету, коммит после каждой фазы, остановка по таймеру):

```text
MILESTONE G — 100-minute session, then the owner continues in another account. Roles inline: say so. No installs of new components, no downloads except archive.org/NASA files already identified, no AI upscaling, no paid routes, no secrets printed. HARD STOP: after ~100 minutes wall time or if free disk < 800 MB, write state to docs/openmontage/MASTER_RUN_STATE.md and finish. Commit and push non-force after EACH phase. Final report max 12 lines (Status, Commit, Done, Failed, Owner decision, Next action).
G1 PORTABILITY (do first, essential): media is gitignored, so make the project rebuildable elsewhere.
 - Write scripts/rebuild_slice_assets.sh (+ docs/openmontage/HANDOFF_NEW_ACCOUNT.md): from the committed manifests (source URLs, archive.org file names, sha256) re-download every clip and still used in the slice with curl -L, verify sha256, rebuild the slice. List every non-git dependency to reinstall (kokoro + misaki versions, espeak-ng, ffmpeg/ffprobe versions, Kokoro weights ~313 MB from Hugging Face, kaggle CLI 2.2.4) and the secrets the new account must recreate (KAGGLE_API_TOKEN as Codespaces secret; name only, never values).
 - Make sure manifests with URLs+sha256+rights fields are COMMITTED (small json/csv in docs/ or a tracked data dir, not media). Add the exact steps for: branch name, repo fork/clone, git log hashes of milestones, how to resume the MASTER_RUN_STATE.
 - Dry-run the script logic for 1 small file only; report PASS/FAIL.
G2 EVIDENCE (CID-13): update docs/openmontage/evidence/CID_CLAIM_LEDGER.md. CID-13 becomes: "At full scale the modified fuel did not prevent a massive fuel-fed fire, and the FAA ended its attempts to require the additive." Sources: NASA Facts FS-2009-02-003-DFRC (AGENT_VERIFIED_TEXT if the PDF is reachable once) + DOT/FAA/CT-87/10 summary report (https://rosap.ntl.bts.gov/view/dot/92854/dot_92854_DS1.pdf; if reachable, read the AMK section and quote nothing long; else mark EXTERNALLY_VERIFIED_METADATA: Claude web search 2026-10-18, secondary confirmations: Wikipedia citing FAA/CT-87/10, Smithsonian Air & Space, Christian Science Monitor 1984-12-04 editorial). Add a CONTRADICTION note: NASA Facts says no reduction in "propagation or intensity"; the FAA-based summary says the reduced intensity of the initial fire was attributed to AMK and proponents argued the fire would have been worse without it. Do NOT use any intensity claim in the script. Status: TWO_SOURCES (one pending direct read of the FAA PDF).
 - Update script S8 to the new wording with claim_id CID-13, unblock S8 ONLY IF the FAA PDF was actually read; otherwise keep it DRAFT with the owner-sign-off note. Run the QC claim_ids check and show the real output.
G3 SLICE v2 (only if G1 and G2 are done and time remains): if S8 is unblocked, synthesize the extra sentence with Kokoro (CPU), rebuild the slice with S1-S8, add one on-screen source card for the FAA report, re-run finish_audio and tools/qa/qc.py (all inputs, static_by_design declared, thresholds unchanged). If S8 stays blocked, skip G3.
G4 PACKAGING DRAFT (docs only, cheap): docs/openmontage/package/CID_PACKAGE_DRAFT.md with 3 title options (truthful, no clickbait), a description with chapters, a complete credits/attribution block generated from rights_records (NASA credits, no logo use, no endorsement language), and a pre-publish checklist (owner review of clips, voice decision, guardian/AdSense, insignia decision, synthetic-voice disclosure to evaluate against current YouTube rules). Mark everything NOT_PUBLISHABLE.
G5 CLOSE: update OWNER_ACTIONS.md, MASTER_RUN_STATE.md and CHANGELOG.md; print the exact commands for the owner to stop the Codespace.
```

**Что делать, пока он работает:** ничего ресурсоёмкого не запускайте параллельно. В конце остановите Codespace (github.com/codespaces → «…» → Stop).

**В новом аккаунте** (после `HANDOFF_NEW_ACCOUNT.md`): открыть репозиторий, добавить секрет Kaggle, запустить `scripts/rebuild_slice_assets.sh` и прислать мне скриншот. Дальше остаются те же решения за вами: родитель и AdSense, эмблемы NASA, полный просмотр клипов для длинной версии, Kaggle-тест голосов.

## [human] 2026-10-18T08:10:23.300403Z


## [assistant] 2026-10-18T08:10:44.988502Z
**Сессия G закрыта: DONE, коммит `830a1d9`, запушен.** Всё нужное сделано за 27 минут, часы Codespaces потрачены меньше, чем боялись.

**Что готово**
- **Переносимость:** есть скрипт `scripts/rebuild_slice_assets.sh`, манифест с URL и sha256 всех 8 материалов и `HANDOFF_NEW_ACCOUNT.md`. Пробный прогон на одном файле прошёл. В новом аккаунте медиа пересоберётся из манифестов.
- **CID-13:** агент прочитал и NASA Facts, и FAA-отчёт (стр. 32). Статус `TWO_SOURCES`, противоречие про «интенсивность» записано, в сценарии такой фразы нет. S8 разблокирована с новой формулировкой, `claim_ids` 9/9.
- **Срез v2:** озвучка S1–S8, 56 с, движущиеся вставки, две графики, карточка источника FAA. QC общий PASS, громкость −15.2 LUFS, REVIEW только на статичных карточках.
- **Упаковка:** три варианта названия, описание с главами, блок авторов и чек-лист перед публикацией. Всё помечено `NOT_PUBLISHABLE`.

**Две оговорки**
1. Отчёт говорит «Kokoro-82M license UNKNOWN». Это расхождение: по нашим проверкам лицензия весов Apache-2.0, неизвестно только происхождение части обучающих данных. Скорее всего, агент сократил формулировку. Решение по голосу вы приняли на слух, но риск данных надо записать вместе с родителем.
2. Проверку делал тот же агент, независимого ревью нет. Чтобы это исправить, в новой сессии напишите: `@qa-reviewer Review docs/openmontage/GLOBAL_CHECK_2026-10-17.md and projects/slice_cid_v0/qa_report.json, read-only.`

**Сейчас сделайте по порядку**
1. Скачайте новый `final_slice.mp4` (папка среза v2, способ как раньше) и посмотрите: S8 звучит, кадры на месте?
2. **Остановите Codespace**: `gh codespace stop -c <имя>` в терминале или github.com/codespaces → «…» → Stop.
3. Перенос: откройте `docs/openmontage/HANDOFF_NEW_ACCOUNT.md` (он есть на GitHub в ветке) и следуйте ему на аккаунте родителя или после обновления лимитов.

**Что остаётся вам, и это единственное, что блокирует публикацию:**
- решение по риску голоса вместе с родителем;
- эмблемы NASA (вы их в видео не увидели, но формально нужен ответ);
- полный просмотр всех исходных клипов, если делать длинную версию;
- монетизация и AdSense: не оценивались;
- решение, как раскрывать синтетическую озвучку по правилам YouTube. Это надо проверить в актуальной справке YouTube перед загрузкой, я не буду утверждать правила по памяти.

Когда посмотрите видео, напишите впечатления: звук, плавность, нужны ли правки по тексту. Дальше решим, делать ли длинную версию на 6–8 минут или сначала выложить срез как непубличный тест.

## [human] 2026-10-18T08:11:36.420254Z
А что можно дальше делать агенту без меня

## [assistant] 2026-10-18T08:11:59.525059Z
**Агент может без вас всё, что не требует решений, прослушивания, просмотра картинки владельцем и публикации.** Вот список по пользе, с учётом того, что часы Codespaces почти кончились (всё это лучше запускать уже в новом аккаунте).

**Полезное и безопасное для автономной работы**
1. **Сценарий и план полного ролика на 6–8 минут.** Из уже прочитанных документов (NASA Facts, TM-4084, FAA/CT-87/10 стр. 32) вынуть больше утверждений с двумя источниками, составить сюжетные блоки (подготовка, дистанционное управление, подлёт, удар, огонь, итоги) и к каждому блоку привязать, какие кадры реально есть.
2. **Поиск недостающих кадров по блокам:** ещё фото NASA Armstrong и видео NIX, с оценкой прав по метаданным (без скачивания лишнего).
3. **Укрепление фабрики:** тесты для скрипта пересборки, запуск контрольных задач из `EVALS.md`, проверка, что ссылки на источники в сториборде валидируются (баг с придуманными `f1/f2`), `ruff`.
4. **Обложка собственной графикой** (без логотипа NASA и без людей) через HTML-в-PNG, плюс варианты названий уже есть.
5. **Независимая проверка** отдельным запуском: новая сессия агента `qa-reviewer`, только чтение, видит только отчёты и первичные документы. Это ближе к настоящей независимости.
6. **Запасные темы** (X-15, XB-70) для следующих роликов: только проверка кадров и документов, без спроса и конкуренции (их измерить без YouTube-данных нельзя).

**Что агент не может и не должен**
- принимать решения про голос, эмблемы и риск вместе с родителем;
- слушать и смотреть качество, подтверждать людей и логотипы в кадрах;
- верифицировать телефон в Kaggle, работать с AdSense, публиковать.

**Один промпт на всё сразу** (запускать в новом аккаунте, после `rebuild_slice_assets.sh`):

```text
MILESTONE H — autonomous batch, no owner input. Time-box 100 min; HARD STOP if time or free disk < 800 MB. Roles inline: say so. No installs of new components, no publishing, no AI upscaling, no secrets printed, curl -L, max 40 network requests. Commit and push non-force after EACH phase. Final report max 12 lines (Status, Commit, Done, Failed, Owner decision, Next action).
H1 FULL-VIDEO PLAN: from docs/openmontage/evidence (NASA Facts, TM-4084, FAA/CT-87/10 which is reachable via rosap.ntl.bts.gov), extend CID_CLAIM_LEDGER.md with up to 20 more claims; mark TWO_SOURCES / SINGLE_SOURCE honestly; no facts from memory; paraphrase only. Write docs/openmontage/slice/CID_FULL_SCRIPT_v0.md: 6-8 min script in 6 narrative beats (preparation, remote piloting, approach, impact, fire, aftermath/lessons), every sentence with claim_ids; single-source sentences flagged; run the QC claim_ids check.
H2 FOOTAGE COVERAGE: map every beat to available assets (11 NIX clips + NASA Armstrong stills). Search images.nasa.gov and archive.org keyless for additional CID video/stills for beats with no coverage; apply RIGHTS_MODEL.md (third-party credit = REJECT); write docs/openmontage/footage/CID_BEAT_COVERAGE.md with counts per beat and gaps; propose the viability-gate wording based on beats covered. Download nothing new beyond 3 test files.
H3 HARDENING (test-first): tests for scripts/rebuild_slice_assets.sh logic (hash mismatch => fail, missing file => fail); verify storyboard/script validation rejects unknown source or claim IDs (add a regression test if missing); run all EVALS.md tasks and record results in EVALS.md; run ruff if available else py_compile; run the full fast test suite; report exact commands and exit codes.
H4 THUMBNAIL: generate 3 thumbnail candidates (1280x720 PNG) from own graphics and a NASA still without logos/persons; no NASA emblem, no misleading imagery, large readable text; save to gitignored projects/ and describe them in docs/openmontage/package/THUMBNAIL_NOTES.md.
H5 TOPIC BACKLOG: read-only viability probe (video count by beat, rights_basis, primary docs reachable) for X-15 and XB-70 using keyless sources only; docs/openmontage/audit/TOPIC_BACKLOG.md. No demand claims.
H6 CLOSE: update OWNER_ACTIONS.md, MASTER_RUN_STATE.md, CHANGELOG.md; list the owner's remaining decisions; print stop-Codespace commands.
```

**Отдельно, независимая проверка** (новая вкладка Kilo, после H, только чтение):

```text
@qa-reviewer Read-only. Review docs/openmontage/GLOBAL_CHECK_2026-10-17.md, the latest projects/slice_cid_v0 qa_report.json, CID_CLAIM_LEDGER.md and CID_FULL_SCRIPT_v0.md. Check: claims vs ledger, counts that do not add up, any PASS hiding NOT_RUN, rights flags. Report PASS/REVIEW/BLOCKED with evidence per check.
```

**Ваша часть, пока агент работает:** письмо родителю про аккаунт AdSense и голос, письмо в архив NASA (с вашей почты) и просмотр нового среза. Это параллельно и бесплатно.

## [human] 2026-10-18T08:49:26.585613Z
Всё сохрани всё и переносим в другой акк чтобы там продолжить

## [assistant] 2026-10-18T08:49:55.098086Z

```
This block is not supported on your current device yet.
```


```
This block is not supported on your current device yet.
```


```
This block is not supported on your current device yet.
```

Всё, что агент закоммитил, уже на GitHub (последний коммит `df2af76`). Но **не всё лежит в git**, поэтому перед переносом проверьте три вещи, иначе они пропадут вместе с Codespace.

**1. Незакоммиченное (главное)**

В терминале:

```bash
cd /workspaces/OpenMontage && git status --short | head -30
```

Там почти наверняка:
- `M AGENTS.md`: ваши правки, агент их намеренно не трогал. Посмотрите `git diff AGENTS.md | head -40` и, если там нет ничего секретного, закоммитьте отдельно.
- `?? .kilo/skills/...`: скиллы из мастер-файла (например, `video-pipeline-ffmpeg`, `video-rendering-remotion`), они не закоммичены.

```bash
git add AGENTS.md .kilo/skills
git commit -m "chore: save owner AGENTS.md changes and installed skills"
git push origin factory/business-documentary-pilot
```

Если `git status` показывает ещё что-то непонятное, пришлите мне вывод.

**2. Видео и звук** (в git их нет, `projects/` в gitignore)

Скачайте через порт 8000 или «Download»: `final_slice.mp4` из папки среза v2 и три обложки (1280×720 PNG, `projects/`). Если не успеете, они пересоберутся скриптом, но обложки лучше сохранить: в манифесте их нет.

**3. Секреты**

Токен Kaggle в новом аккаунте создаётся заново (Settings → API → Create New Token → Codespaces Secret `KAGGLE_API_TOKEN`). Старый токен после переноса лучше отозвать на kaggle.com. Весы Kokoro (~313 МБ) скачаются снова.

**Перенос на новый аккаунт (аккаунт родителя или после обновления лимита)**

1. На GitHub нового аккаунта: форк `sora73636-stack/OpenMontage` (или добавьте этот аккаунт как collaborator в старый репозиторий и откройте ветку `factory/business-documentary-pilot`).
2. Откройте Codespace на этой ветке (Code → Codespaces → New).
3. Откройте `docs/openmontage/HANDOFF_NEW_ACCOUNT.md` и выполните шаги. Затем `scripts/rebuild_slice_assets.sh`: он скачает 8 материалов и сверит sha256.
4. Запустите Kilo и дайте агенту короткий стартовый промпт:

```text
Read docs/openmontage/HANDOFF_NEW_ACCOUNT.md and docs/openmontage/MASTER_RUN_STATE.md. Run a read-only preflight (git status, HEAD, df -h, kilo agent list, ls .kilo/skills). Run scripts/rebuild_slice_assets.sh and verify hashes. Do not start new milestones. Report in max 12 lines: what rebuilt, what failed, exact next action.
```

5. Остановите старый Codespace (`gh codespace stop -c <имя>` или github.com/codespaces), чтобы часы больше не тратились.

**Контекст для меня в новом чате:** я сохранил в память состояние проекта (ниша, ветка, коммит, решение по голосу, открытые вопросы), так что после переноса просто скажите, где вы остановились. Скриншот отчёта агента из нового аккаунта пришлёте, и я проверю.

## [human] 2026-10-18T08:52:10.069909Z


## [assistant] 2026-10-18T08:52:20.549958Z
Коммит `a5d7d4` запушен: AGENTS.md и 8 скиллов сохранены. **Но не всё.** В том же `git status` были ещё четыре неотслеживаемые папки, а вы добавили только `AGENTS.md` и `.kilo/skills`:

- `.agents/skills/audio-edit/` (скилл звука из нашей работы, терять его не стоит)
- `docs/agent-improvement/BACKLOG.md`
- `docs/architecture/`
- `templates/`

Сохраните их тоже:

```bash
cd /workspaces/OpenMontage
git add .agents/skills docs/agent-improvement docs/architecture templates
git status --short | head
git commit -m "chore: save remaining skills, backlog, architecture docs, templates"
git push origin factory/business-documentary-pilot
```

Если после этого `git status --short` пустой, код сохранён полностью.

**Про видео.** Список файлов на втором экране это папка `f4`: там `final_f4.mp4` с озвучкой S1–S7 на 46 секунд. Свежая версия на 56 секунд с S8 и источником FAA лежит в другой папке (после этапа G). Найти её и скачать:

```bash
ls -lt $(find /workspaces/OpenMontage/projects -name "*.mp4" -size +3M) | head -8
```

Самый новый файл по времени и есть последний срез. Запустите сервер в его папке (`cd <папка> && python3 -m http.server 8000`), откройте через «Порты» и скачайте. Обложки лежат там же, где `projects`: найдите их так:

```bash
find /workspaces/OpenMontage/projects -name "*.png" -newer /workspaces/OpenMontage/README.md | head
```

Скачайте `final_f4.mp4` тоже, как запасной вариант, и по возможности `narration_finished.wav` и `subtitles.srt`.

Когда всё скачано и `git status` чистый, остановите Codespace (`gh codespace stop` или github.com/codespaces → Stop) и переходите в новый аккаунт по шагам из прошлого сообщения. Если команды выше что-то выведут не так, пришлите скриншот.

## [human] 2026-10-18T08:53:38.934216Z
Так что в порте скачивать

## [assistant] 2026-10-18T08:53:48.254245Z
**Скачивайте всё одной пачкой.** Сначала соберём нужное в одну папку (файл `final_slice.mp4` и `f5/final_g3.mp4` одинакового размера, это и есть последняя версия, 56 с):

```bash
S=/workspaces/OpenMontage/projects/slice_cid_v0
mkdir -p /tmp/export && cd /tmp/export
cp $S/final_slice.mp4 .
cp $S/f4/final_f4.mp4 .
cp $S/thumbnails/*.png .
cp $S/credits.txt $S/rights_records.json $S/qa_report.json $S/subtitles.srt . 2>/dev/null
ls -lh
```

Затем запустите сервер:

```bash
cd /tmp/export && python3 -m http.server 8000
```

Дальше:
1. Вкладка **«Порты»** → строка с портом **8000** → значок глобуса («Открыть в браузере»).
2. В браузере откроется список файлов. Нажмите на каждый и сохраните: у видео и картинок через долгое нажатие «Скачать» или меню ⋮ → «Скачать».
3. Обязательно: `final_slice.mp4`, три картинки `thumb_*.png`, `credits.txt`, `rights_records.json`. Остальное (`final_f4.mp4`, `qa_report.json`, `subtitles.srt`) по желанию.
4. Когда всё скачано, вернитесь в терминал и нажмите **Ctrl+C**, чтобы остановить сервер. Порт не делайте публичным.

Файлы `credits.txt` и `rights_records.json` в git не попали, поэтому их стоит сохранить. Манифест с источниками и sha256 уже на GitHub, но подробные записи прав лежат только тут.

Код сохранён полностью: коммит `0eaba04` запушен, `git status` теперь чистый. После скачивания остановите Codespace и переходите в новый аккаунт по шагам из `HANDOFF_NEW_ACCOUNT.md`.

## [human] 2026-10-18T08:55:53.237154Z
Дай код чтобы открыть порт 8080 а 8000 уже занято

## [assistant] 2026-10-18T08:55:55.796774Z
Тот же сервер, только на порту 8080:

```bash
cd /tmp/export && python3 -m http.server 8080
```

Если порт 8080 тоже занят, пишет `Address already in use`, возьмите любой другой, например 8090:

```bash
cd /tmp/export && python3 -m http.server 8090
```

Дальше вкладка **«Порты»**: нужная строка появится сама (если нет, нажмите «Перенаправить порт» и введите номер). Откройте глобус рядом с ним.

Проверить, что именно занимает 8000 и мешает:

```bash
lsof -i :8000 | head
```

Старый сервер можно остановить, если он вам больше не нужен: `pkill -f "http.server 8000"`.

## [human] 2026-10-18T08:59:34.125899Z
Дай мне ник этого драконгода

## [assistant] 2026-10-18T08:59:40.750403Z
Ник: **`dragongod73584-design`**. Вы его видите в списке «Switch account» (вторая строка).

Чтобы перенести проект на этот аккаунт:
1. Войдите в `dragongod73584-design` и откройте `github.com/sora73636-stack/OpenMontage`.
2. Нажмите **Fork**, затем откройте форк и выберите ветку `factory/business-documentary-pilot` (ветка копируется вместе с форком).
3. **Code → Codespaces → New codespace** на этой ветке.
4. Дальше по `docs/openmontage/HANDOFF_NEW_ACCOUNT.md`.

Либо без форка: в старом репозитории **Settings → Collaborators → Add people** и добавьте `dragongod73584-design`, тогда он сможет открыть Codespace прямо на этой ветке.

Одно замечание по правилам: GitHub разрешает одному человеку только один бесплатный аккаунт, и у вас в списке их пять. Если новые Codespaces нужны только чтобы обойти лимит часов, аккаунт может быть заблокирован вместе с кодом. Безопаснее использовать аккаунт, который принадлежит родителю или другому человеку с его согласия, либо подождать обновления лимита в начале месяца. Строка `f3114521-max` выглядит как чужой аккаунт с настоящим именем, его без разрешения владельца использовать не стоит.

## [human] 2026-10-18T09:04:29.357205Z
Перенос успешно прошёл?

## [assistant] 2026-10-18T09:04:36.835379Z
**Код перенёсся, это видно на скриншоте.** Новый Codespace «scaling spoon» открыт на ветке `factory/business-documentary-pilot`, в дереве есть `.kilo`, `.agents`, `docs`, `tools`, `tests`, `scripts`, `templates`. Но «успешно» пока только по внешнему виду, проверим по-настоящему. Терминал ещё пустой.

Выполните в терминале:

```bash
cd /workspaces/OpenMontage
git log --oneline -3
git status --short | head
ls docs/openmontage | head -40
ls docs/openmontage/HANDOFF_NEW_ACCOUNT.md scripts/rebuild_slice_assets.sh docs/openmontage/assets/CID_SLICE_MANIFEST.json
ls .kilo/skills .kilo/agents
df -h /workspaces | tail -1
```

Ожидаемо: верхний коммит `0eaba04`, `git status` пустой, все файлы на месте, в `.kilo/agents` четыре агента (`editor`, `qa-reviewer`, `evidence-checker`, `footage-scout`), диска несколько ГБ.

Если всё так, дальше по `HANDOFF_NEW_ACCOUNT.md`:
1. **Секрет Kaggle** (по желанию, нужен только для GPU-теста голосов): в новом аккаунте GitHub → Settings → Codespaces → Secrets → `KAGGLE_API_TOKEN`, потом перезапустить Codespace.
2. **Пересборка медиа:** `bash scripts/rebuild_slice_assets.sh` (скачает 8 материалов и сверит sha256).
3. **Kilo:** откройте его панель, подключите модель (она тут не сохранилась, это настройка аккаунта) и дайте агенту стартовый промпт, который я писал раньше (read-only preflight, пересборка, отчёт в 12 строк).

Что могло не перенестись и это нормально: весы Kokoro, пакеты Python, `ffmpeg`, настройки Kilo и модели, медиа из `projects/`. Всё это восстанавливается инструкциями из handoff. Пришлите скриншот вывода команд, и я скажу, чего не хватает.

## [human] 2026-10-18T09:05:26.389002Z


## [assistant] 2026-10-18T09:05:34.487047Z
**Перенос прошёл успешно.** Проверка по скриншоту:

- Верхний коммит `0eaba04`, совпадает с последним запушенным.
- `git status` пустой, значит, рабочая копия чистая.
- Все ключевые файлы на месте: `HANDOFF_NEW_ACCOUNT.md`, `CID_SLICE_MANIFEST.json`, `rebuild_slice_assets.sh`, `OWNER_ACTIONS.md`, `GLOBAL_CHECK`, `RIGHTS_MODEL` и остальные документы.
- Четыре агента на месте: `editor`, `evidence-checker`, `footage-scout`, `qa-reviewer`.
- Скиллы на месте, включая те, что мы сохраняли отдельным коммитом (`audio-edit`, `kilo-self-improvement` и YouTube-набор).
- Диск: **19 ГБ свободно**, намного лучше, чем было (раньше оставалось около 3 ГБ).
- Аккаунт `dragongod73584-design`, Codespace «scaling spoon».

**Чего ещё нет** (и это ожидаемо): папки `projects/` с видео и озвучкой, весов Kokoro, пакетов Python, секрета Kaggle и настроенной модели в Kilo. Всё это восстанавливается.

**Дальше по порядку:**

1. Пересобрать медиа и проверить хеши:
```bash
cd /workspaces/OpenMontage && bash scripts/rebuild_slice_assets.sh
```
Скрипт скачает 8 материалов (около 20 МБ) и сверит sha256. Пришлите последние строки вывода.

2. Проверить окружение для озвучки и сборки (только чтение):
```bash
which ffmpeg ffprobe espeak-ng; python3 --version; python3 -c "import kokoro" 2>&1 | tail -1
```
Если `kokoro` не найден, это нормально: установку и скачивание весов (~313 МБ) должен сделать агент по handoff.

3. Откройте панель Kilo, подключите модель (в новом аккаунте её надо выбрать заново) и дайте стартовый промпт:

```text
Read docs/openmontage/HANDOFF_NEW_ACCOUNT.md and docs/openmontage/MASTER_RUN_STATE.md. Read-only preflight first (git status, HEAD, df -h, kilo agent list). Then run scripts/rebuild_slice_assets.sh and verify all sha256. Install ONLY what the handoff lists (kokoro/misaki pinned versions, espeak-ng, CPU torch not CUDA) and download the Kokoro weights into a gitignored cache; report free disk before each heavy step. Rebuild the 56 s slice (S1-S8 narration + stills + clips + graphics + subtitles) per the committed manifests and edit_decisions, run finish_audio and tools/qa/qc.py. Do not start new milestones. Report in max 12 lines: Status, Commit, Done, Failed, Owner decision, Next action.
```

Так в новом аккаунте получится то же состояние, что было в старом, и можно будет продолжать. Пришлите скриншот после первой команды.

## [human] 2026-10-18T09:06:38.467304Z


## [assistant] 2026-10-18T09:06:55.043472Z
**Перенос кода прошёл, но пересборка выдала ложный успех, и это надо исправить.** Вот что видно в выводе.

1. **Скрипт сказал `DONE: all assets present and sha256-verified`, хотя упал с `JSONDecodeError (char 0)`.** Это значит, что манифест прочитался пустым, ни один материал не проверялся, а итог всё равно «успех». Скрипт нарушает наше главное правило: при сбое он должен падать, а не сообщать об успехе. Доверять этому `DONE` нельзя.
2. **`which ffmpeg ffprobe espeak-ng` ничего не вывела.** Значит, `ffmpeg`, `ffprobe` и `espeak-ng` в новом Codespace не установлены.
3. **Python здесь 3.14.2.** Старый Codespace, скорее всего, был на другой версии (в репозитории есть `.python-version`). Библиотеки Kokoro и torch на 3.14 могут не поставиться.
4. `kokoro` не установлен, это ожидаемо.

**Сначала диагностика манифеста** (30 секунд):

```bash
cd /workspaces/OpenMontage
wc -c docs/openmontage/assets/CID_SLICE_MANIFEST.json
head -c 300 docs/openmontage/assets/CID_SLICE_MANIFEST.json; echo
git log --oneline -3 -- docs/openmontage/assets/CID_SLICE_MANIFEST.json
cat .python-version; ls projects/slice_cid_v0 2>/dev/null | head
```

Если размер 0 байт, манифест при коммите оказался пустым. Тогда в старом Codespace ещё можно исправить, если он не удалён: данные манифеста лежат в `projects/slice_cid_v0/rights_records.json`. Если старый Codespace остановлен, но не удалён, откройте его снова с аккаунта `sora73636-stack` и скопируйте этот файл. Если размер не нулевой, а файл вроде бы нормальный, пришлите мне вывод `head`.

**Установка нужных программ** (быстро, 1–2 минуты):

```bash
sudo apt-get update -y && sudo apt-get install -y ffmpeg espeak-ng
ffmpeg -version | head -1
```

Без `sudo` не получится, но в Codespace он обычно есть.

**Затем промпт агенту** (чинит скрипт по правилу fail-closed, не пропуская ошибок):

```text
MILESTONE R1 — fix rebuild_slice_assets.sh false success. Roles inline: say so. No new components. Report in max 12 lines.
1. Preflight read-only: wc -c and head of docs/openmontage/assets/CID_SLICE_MANIFEST.json, git log for that file, python3 --version, cat .python-version, which ffmpeg ffprobe espeak-ng.
2. Reproduce: run scripts/rebuild_slice_assets.sh and show that it prints DONE after a JSONDecodeError. Test-first: add tests in tests/tools/test_rebuild_slice_assets.py that FAIL for: empty manifest, invalid JSON, manifest with zero assets, missing asset, sha256 mismatch. Show red.
3. Fix the script fail-closed: set -euo pipefail; any parse error, zero assets, missing file or hash mismatch => non-zero exit and "FAILED", never "DONE". The summary must print the number of assets verified and must equal the manifest asset count. Show green and run the fast suite.
4. If the committed manifest is empty or corrupt, DO NOT invent data: report it as BLOCKED and rebuild it only from docs/openmontage/slice and rights records that exist in git; if source URLs/sha256 are not in git, list exactly what the owner must copy from the old codespace (projects/slice_cid_v0/rights_records.json, credits.txt).
5. Install only what HANDOFF_NEW_ACCOUNT.md lists, picking a Python version compatible with the pinned kokoro/misaki (python 3.14 may be unsupported: check, and if so create a venv with 3.11/3.12 via uv or pyenv if available, else report BLOCKED). Report free disk before each heavy step. Do not download Kokoro weights until the manifest is fixed and verified.
6. Commit code/tests/docs only (no media), push non-force.
```

Пришлите вывод диагностики манифеста (первая команда), и по нему станет ясно, что именно сломалось.

## [human] 2026-10-18T09:09:04.351983Z


## [assistant] 2026-10-18T09:09:22.129561Z
**Диагноз найден.** Манифест не пустой (7270 байт), но файл начинается со строк-комментариев `# CID Slice Asset Manifest ...`. Это не валидный JSON, поэтому скрипт падает на первом символе. В старом Codespace это не вылезло, потому что пробный прогон шёл по одному файлу другим путём. Это двойная ошибка: плохой формат манифеста и скрипт, который при сбое всё равно пишет `DONE`.

Данные при этом целы. Исправьте файл прямо сейчас (комментарии убираем, JSON сохраняем):

```bash
cd /workspaces/OpenMontage
python3 - <<'PY'
import json
p='docs/openmontage/assets/CID_SLICE_MANIFEST.json'
lines=open(p).read().splitlines()
hdr=' '.join(l.lstrip('# ').strip() for l in lines if l.startswith('#'))
m=json.loads('\n'.join(l for l in lines if not l.startswith('#')))
if isinstance(m,dict):
    m={'_comment':hdr, **m}
else:
    m={'_comment':hdr,'assets':m}
json.dump(m,open(p,'w'),indent=2,ensure_ascii=False)
a=m.get('assets',m)
print('OK, assets:', len(a) if hasattr(a,'__len__') else '?')
PY
python3 -c "import json;json.load(open('docs/openmontage/assets/CID_SLICE_MANIFEST.json'));print('valid JSON')"
```

Если скрипт напечатает ошибку или число активов не 8, пришлите вывод. Если всё хорошо, запустите пересборку ещё раз:

```bash
sudo apt-get update -y && sudo apt-get install -y ffmpeg espeak-ng
bash scripts/rebuild_slice_assets.sh
```

Теперь `DONE` можно считать честным, только если в итоге написано, что проверено 8 из 8 материалов. Если снова «failures=0» без числа, не верьте ему.

**Ещё два замечания по скриншоту**
- Вы установили `@kilocode/cli` 7.8.12, это хорошо. npm предупредил, что его postinstall-скрипт не выполнен. Если Kilo не запустится или не найдёт модель, выполните `npm install -g --allow-scripts=@kilocode/cli @kilocode/cli`.
- В репозитории `.python-version` = 3.10, а в Codespace стоит Python 3.14.2. Библиотеки озвучки (Kokoro, torch) на 3.14 могут не установиться. Агент должен создать окружение с подходящей версией, а не ставить пакеты в системный Python.

Когда пересборка заработает, отправьте агенту короткий промпт, где уже учтена найденная причина (вместо моего прошлого R1):

```text
MILESTONE R1 (revised). Roles inline: say so. No new components. Max 12-line final report.
Known cause: docs/openmontage/assets/CID_SLICE_MANIFEST.json had '#' comment lines before the JSON (the owner just converted it to valid JSON with a "_comment" field), and scripts/rebuild_slice_assets.sh printed "DONE" after a JSONDecodeError.
1. Test-first in tests/tools/test_rebuild_slice_assets.py: failing tests for invalid JSON, '#'-prefixed manifest, empty manifest, zero assets, missing file, sha256 mismatch, and summary count != manifest count. Show red, fix, show green; run the fast suite.
2. Fix the script fail-closed: set -euo pipefail, validate JSON before use, exit non-zero with "FAILED" on any error; print "verified N/N assets" and refuse DONE unless N equals the manifest count.
3. Check python: .python-version says 3.10 but the host has 3.14.2. Create an isolated venv with a compatible Python (uv/pyenv if available, else report BLOCKED), install only the pinned kokoro/misaki/torch(CPU) from HANDOFF_NEW_ACCOUNT.md there, never into system python. Report free disk before each heavy step.
4. Run the rebuild and show the real N/N output. Do not download Kokoro weights yet.
5. Commit code/tests/docs only (no media), push non-force.
```

Пришлите скриншот после исправления манифеста и повторного запуска.

## [human] 2026-10-18T09:11:16.201173Z


## [assistant] 2026-10-18T09:11:21.596786Z
**Всё прошло хорошо.**

- Манифест исправлен: `OK, assets: 8`, `valid JSON`. Это ровно те 8 материалов, что нужны.
- `ffmpeg 7.1.1` и `espeak-ng 1.51` установлены (последние строки: `Setting up espeak-ng`, `Setting up ffmpeg`). Ошибок нет.

Теперь запустите пересборку ещё раз и внимательно смотрите последнюю строку:

```bash
cd /workspaces/OpenMontage
bash scripts/rebuild_slice_assets.sh 2>&1 | tail -20
```

Читайте результат так:
- Должно быть написано, что проверены **8 из 8** материалов, и нет никаких `Traceback`.
- Если вместо этого снова `DONE` без числа или с ошибкой, скрипт всё ещё врёт, и нужен промпт R1 (исправление по правилу fail-closed), который я давал выше.

После успеха проверьте, что файлы реально скачались:

```bash
ls -lh projects/slice_cid_v0 | head -20
git status --short
```

Манифест изменился (появилось поле `_comment`), поэтому сохраните исправление в git, иначе при следующем переносе поломка вернётся:

```bash
git add docs/openmontage/assets/CID_SLICE_MANIFEST.json
git commit -m "fix: make slice manifest valid JSON (move comments into _comment)"
git push origin factory/business-documentary-pilot
```

Пришлите скриншот вывода пересборки. Если 8/8, дальше отправляем агенту промпт R1 (тесты на скрипт и fail-closed, виртуальное окружение под Kokoro), потом установку озвучки и пересборку среза.

## [human] 2026-10-18T09:11:37.857205Z
Изучи все модели free и по бенчмарком и агентных задачам и сделай топ

## [assistant] 2026-10-18T09:12:31.123393Z
Ищу независимые бенчмарки и отзывы по каждой модели из списка, в первую очередь по агентному кодингу.
```
This block is not supported on your current device yet.
```

```
This block is not supported on your current device yet.
```

```
This block is not supported on your current device yet.
```

```
This block is not supported on your current device yet.
```

```
This block is not supported on your current device yet.
```





Сразу оговорка: почти все цифры ниже опубликованы самими разработчиками моделей, на разных тестовых оболочках, поэтому сравнивать их между собой можно только грубо. Независимо подтверждены лишь отдельные пункты. Ещё одно: рядом с каждой бесплатной моделью в вашем списке стоит пометка **«May train»**, то есть ваши запросы могут использоваться для обучения. Секреты и токены в чат агента не вставляйте (мы и так этого не делаем).

**Топ для агентных задач (кодинг, терминал, длинные цепочки)**

1. **Poolside Laguna S 2.1.** Лучшие опубликованные цифры среди бесплатных. Poolside сообщает 70.2% на Terminal-Bench 2.1, 78.5% на SWE-Bench Multilingual и 59.4% на SWE-Bench Pro. Часть результатов (Terminal-Bench 2.1 и DeepSWE) подтверждена через Artificial Analysis, но замеры шли с включённым «мышлением» и очень длинными таймаутами. Модель создана для долгих задач, и в Kilo она входит в тройку по расходу токенов. Минус: примерно 41 токен/с, то есть неспешная.
2. **NVIDIA Nemotron 3.5 Super VL.** NVIDIA пишет, что Super 3.5 при в 4.6 раза меньшем числе активных параметров обходит Ultra по SWE-bench Pro и Terminal-Bench 2.1. По общему индексу интеллекта это самая сильная бесплатная модель (26.5 балла). Колонки цифр в выдаче не подписаны, поэтому точные числа беру с осторожностью, а замеры сделаны на текстовой версии. Для вас это лучший практический выбор: у неё есть зрение (контакт-листы, кадры), и на ней агент прошёл все наши вехи с честными отчётами. Это наш опыт, а не бенчмарк.
3. **Nemotron 3 Ultra.** SWE-Bench Verified 70.7 и Terminal-Bench 2.1 56.4. Тяжёлая, и по этим числам уступает Super 3.5. Берите как запасную.
4. **Laguna XS 2.1** (лёгкая версия). SWE-bench Verified около 70.9, SWE-Bench Pro около 47.6, Terminal-Bench 2.0 около 37.5. Быстрая, хороша для мелких правок.
5. **Cohere North Mini Code.** Громкая цифра 80.2% относится к pass@10, а честный результат с одной попытки 61.0%. Небольшая и быстрая, подойдёт для простых задач.
6. **Dots3-Note Preview.** Очень популярна у пользователей Kilo (около 80.6 млрд токенов за сутки), контекст 512K и около 59 токенов/с. Но подтверждённых агентных бенчмарков я не нашёл, общий балл у агрегатора только оценочный.
7. **Inkling / Inkling Small.** В таблице конкурентов у Inkling указан SWE-Bench Verified 77.6, но это чужая сводка, не проверка. У Small цифр нет.

**Наблюдать, но не полагаться**
- **Reflection Beam 1.0.** Самая многообещающая, но совсем свежая. Веса вышли 16 октября, все результаты самоотчётные, независимая оценка ещё не готова, и по Terminal-Bench 2.1 она не лидирует. Попробуйте на одной задаче.
- **Glyph Cluster.** «Стелс»-модель без бенчмарков. Заявлена для кодинга и анализа больших входов, но не поддерживает структурированный вывод. При проверке в сообществе один раз вернула ошибку 503. Её используют много, но личность поставщика и данные неясны.

**Пропускать для агентной работы:** Auto Free (это роутер, непредсказуемо, какая модель ответит), Xing4.0 29B, Nemotron 3 Nano Omni, Nemotron 3.5 Lightning, LFM2.5-2.6B и старая Nemotron 3 Super. Данных для агентных задач нет или модель слишком мала. Пункты без пометки «(free)» (Gemini, Step 5 Preview, Ember-1) могут быть платными, а Gemini 2.5 Flash уже снят с поддержки 20 октября.

**Как я бы расставил по вашим задачам**
- Планы, проверка источников, разбор скриншотов: Nemotron 3.5 Super VL.
- Код с тестами (скрипты пересборки, QC): Laguna S 2.1.
- Мелкие правки: Laguna XS 2.1 или North Mini Code.

**Проверка на практике вместо бенчмарков.** У нас есть готовая задача: промпт R1 (починить `rebuild_slice_assets.sh` по правилу fail-closed). Запустите его по очереди на Nemotron 3.5 Super VL и Laguna S 2.1 и сравните: нашёл ли ошибку, написал ли тесты сначала, не соврал ли в отчёте. Это покажет лучше любого рейтинга. Сначала проверьте, что пересборка проходит 8/8, затем запускайте R1.

## [human] 2026-10-18T09:14:08.583244Z
Хорошо дай мне пожалуйста все промпты что ты отправлял после переноса теперь можно всё начать

## [assistant] 2026-10-18T09:14:33.935660Z
Вот полный набор в порядке запуска. Промпты G и H (этапы в старом аккаунте) повторять не нужно: результаты уже в git.

**Одно важное замечание.** Файл `edit_decisions.json` (монтажный список), манифест озвучки и субтитры лежали в `projects/`, которая в gitignore, и в новый аккаунт не попали. Поэтому срез не «пересоберётся один в один», а будет собран заново по сценарию и манифесту. В промпте 3 я заставил агента на этот раз закоммитить эти небольшие файлы, чтобы это больше не повторялось.

**Шаг 0. Терминал (вы сами, 2 минуты)**

```bash
cd /workspaces/OpenMontage
bash scripts/rebuild_slice_assets.sh 2>&1 | tail -20
ls -lh projects/slice_cid_v0 | head -20
git add docs/openmontage/assets/CID_SLICE_MANIFEST.json
git commit -m "fix: make slice manifest valid JSON (move comments into _comment)"
git push origin factory/business-documentary-pilot
```

Если пересборка ещё пишет `DONE` с ошибкой или без «8/8», сразу идите к промпту 2.

**Промпт 1. Стартовая проверка (read-only)**

```text
Read docs/openmontage/HANDOFF_NEW_ACCOUNT.md and docs/openmontage/MASTER_RUN_STATE.md. Run a read-only preflight first: git status, HEAD, df -h /workspaces, kilo agent list, ls .kilo/skills, python3 --version, cat .python-version, which ffmpeg ffprobe espeak-ng. Do not start new milestones and do not install anything. Report in max 12 lines: Status, Commit, Done, Failed, Owner decision, Next action. Say "roles inline, not independent".
```

**Промпт 2. R1: починить скрипт пересборки (с тестами и окружением)**

```text
MILESTONE R1 (revised). Roles inline: say so. No new components. Max 12-line final report.
Known cause: docs/openmontage/assets/CID_SLICE_MANIFEST.json had '#' comment lines before the JSON (the owner converted it to valid JSON with a "_comment" field), and scripts/rebuild_slice_assets.sh printed "DONE" after a JSONDecodeError.
1. Test-first in tests/tools/test_rebuild_slice_assets.py: failing tests for invalid JSON, '#'-prefixed manifest, empty manifest, zero assets, missing file, sha256 mismatch, and summary count != manifest count. Show red, fix, show green; run the fast suite.
2. Fix the script fail-closed: set -euo pipefail, validate JSON before use, exit non-zero with "FAILED" on any error; print "verified N/N assets" and refuse DONE unless N equals the manifest count.
3. Check python: .python-version says 3.10 but the host has 3.14.2. Create an isolated venv with a compatible Python (uv/pyenv if available, else report BLOCKED), install only the pinned kokoro/misaki/torch(CPU) from HANDOFF_NEW_ACCOUNT.md there, never into system python. Report free disk before each heavy step.
4. Run the rebuild and show the real N/N output. Do not download Kokoro weights yet.
5. Commit code/tests/docs only (no media), push non-force.
```

(Если хотите сравнить модели, запустите этот промпт сначала на Nemotron 3.5 Super VL, потом откатите `git reset --hard` до коммита перед ним и запустите на Laguna S 2.1. Сравните: тесты написаны сначала? отчёт честный?)

**Промпт 3. R2: озвучка и пересборка среза**

```text
MILESTONE R2 — Kokoro narration + slice rebuild. Roles inline: say so. No new components beyond what HANDOFF_NEW_ACCOUNT.md lists; no AI upscaling; no secrets printed. Report free disk before each heavy step; stop if free < 800 MB. Commit and push non-force after each phase. Final report max 12 lines.
1. Download the Kokoro-82M weights (~313 MB) into a gitignored cache inside the venv from R1. Synthesize S1-S8 from docs/openmontage/slice/CID_FULL_SCRIPT_v0.md / CID_SLICE_SCRIPT_v0.md (S1-S8 only, same voice as before), word timestamps for subtitles. Run tools/audio finish_audio and tools/qa/qc.py on the narration. Report RTF and loudness.
2. Rebuild the 56 s slice from the verified assets in projects/slice_cid_v0 and the committed manifest: NASA stills with slow zoompan (max 1.15x), 3 archive clips as 2x framed inserts (640x480 on dark background, thin frame, source card), 2 original graphics cards (flight-path/timeline, key numbers with claim_ids), FAA source card for S8. The old edit_decisions.json was NOT committed, so recreate the EDL with a written rationale per cut, and DECLARE static title cards as static_by_design.
3. Run tools/qa/qc.py with all inputs (duration_vs_script, subtitle_sync, claim_ids, rights_basis, credits_complete, added_value) on the FINAL MP4. Do not change thresholds. Report real statuses.
4. Commit the SMALL project files that were lost last time (edit_decisions.json, narration_manifest.json, subtitles.srt, credits.txt, rights_records.json, qa_report.json) into docs/openmontage/slice/artifacts/ so the next move does not lose them. Never commit mp4/wav/png media.
5. Update MASTER_RUN_STATE.md and CHANGELOG.md. Report: Status, Commit, Done, Failed, Owner decision, Next action.
```

**Промпт 4. Независимая проверка (в отдельной вкладке Kilo, после R2, только чтение)**

```text
@qa-reviewer Read-only. Review docs/openmontage/GLOBAL_CHECK_2026-10-17.md, the latest qa_report.json for the slice, docs/openmontage/evidence/CID_CLAIM_LEDGER.md and docs/openmontage/slice/CID_FULL_SCRIPT_v0.md. Check: claims vs ledger, counts that do not add up, any PASS hiding NOT_RUN, rights flags, and whether the rebuild script and tests are fail-closed. Report PASS/REVIEW/BLOCKED with evidence per check. If you cannot run as a separate agent, say "inline, not independent".
```

**Если окажется, что Kilo в новом аккаунте не видит модель или пишет про скрипт:** выберите модель (меню «Select model», например Nemotron 3.5 Super VL или Laguna S 2.1) и при необходимости выполните `npm install -g --allow-scripts=@kilocode/cli @kilocode/cli`.

**Что остаётся вам параллельно:** письмо родителю про AdSense и голос, письмо в архив NASA с вашей почты, повторный просмотр нового среза и решение по эмблемам NASA. Скриншот отчёта после промпта 2 мне пришлите, посмотрю, и тогда запускайте промпт 3.

## [human] 2026-10-18T10:32:38.258587Z
Изучи в форумах про кило какой модель люди говорять что самые лучший

## [assistant] 2026-10-18T11:13:23.675393Z
Ищу, что пишут сами пользователи Kilo: Reddit, обсуждения, блог Kilo, отзывы.
```
This block is not supported on your current device yet.
```

```
This block is not supported on your current device yet.
```

```
This block is not supported on your current device yet.
```

```
This block is not supported on your current device yet.
```




Прямых обсуждений этих конкретных моделей на Reddit я не нашёл. Поиск выдаёт в основном рейтинги использования, блог самого Kilo и агрегаторы, то есть уверенного «мнения форумов» нет. Что удалось собрать:

**Что реально выбирают пользователи (это расход токенов, а не качество)**
- По рейтингу Kilo, во «Code» лидирует Step 5 Preview, затем Nemotron 3 Ultra и Laguna S 2.1. Step 5 Preview занимает около 32% использования, Nemotron 3 Ultra около 15%, Laguna S 2.1 около 11%, Nemotron 3.5 Super VL около 7%. В другом срезе за сутки первое место по объёму у Nemotron 3.5 Super VL, и Kilo называет его лучшим по реальному использованию.
- Но Step 5 Preview уже не вариант: он был бесплатным в Kilo всего около недели, а обычная цена $1.00 за миллион входных и $2.70 за выходных токенов. В вашем списке у него нет пометки «(free)», так что бесплатная неделя кончилась.
- Важное по Laguna S 2.1: в рейтинге Kilo он указан как «retires Oct 31», то есть его скоро могут убрать. Строить на нём процесс нельзя.

**Что говорят о качестве**
- Блог Kilo (это промо самой платформы) отмечает, что Nemotron 3.5 Super VL хорошо правит интерфейс по скриншотам и держит длинные агентные сессии в больших репозиториях без потери нити.
- Один разработчик измерил свои задачи по выделению цитат: Step 5 Preview прошёл 10 из 10 примерно за 4 секунды, а Dots3-Note оказался медленнее и подошёл как запасной.
- Пользователи Laguna осторожны: модель новая, и перед боевым кодом её советуют сильно проверить на запутанных репозиториях и нестабильных тестах.
- Старая, но показательная жалоба в сообществе Cursor: модели часто срываются при исполнении и уходят в бесконечные циклы, особенно DeepSeek и MiniMax через OpenRouter. Там же упрекают Kilo в том, что он больше рекламирует новые модели, чем проверяет, как они работают. К нашим моделям это прямо не относится, но напоминает: рейтинг использования не равен надёжности.

**Приватность (важно для всех бесплатных)**
- Стелс-модели Kilo и бесплатные эндпоинты NVIDIA могут хранить запросы или обучаться на них, поэтому конфиденциальные данные не отправляйте. Про Glyph Cluster отдельно: запросы и ответы могут использоваться для обучения.
- Auto Free может направить запрос провайдерам, которые логируют запросы и ответы.

**Что бы я выбрал для вас с этим знанием**
1. **Nemotron 3.5 Super VL** по умолчанию: он первый по использованию, у него есть зрение для контакт-листов и скриншотов, и на нём у нас прошли все вехи с честными отчётами.
2. **Laguna S 2.1** для задач с кодом и тестами, пока он доступен (проверьте дату снятия 31 октября).
3. **Dots3-Note** как запасной: контекст 512K, но по каталогу лимит около 200 запросов в час.
4. Не используйте Step 5 Preview (платный) и Glyph Cluster для чувствительных задач.

Для окончательного выбора всё равно полезен наш собственный тест на промпте R1: запустить его на Nemotron 3.5 Super VL и на Laguna S 2.1 и сравнить, кто написал тесты первыми, нашёл причину и не соврал в отчёте.

## [human] 2026-10-18T12:28:08.157984Z
А opencode free модели

## [assistant] 2026-10-18T12:30:43.271798Z
Проверяю, какие бесплатные модели сейчас есть в OpenCode (Zen) и что о них пишут.
```
This block is not supported on your current device yet.
```

```
This block is not supported on your current device yet.
```

```
This block is not supported on your current device yet.
```







================================================================================
# ФАЙЛ: PART5_CHAT_2026-10-18_to_2026-10-20_FACTORY_RUN.md
================================================================================

# Часть 5. Чат «Фабрика в Codespaces: Kilo + OpenCode» (18-20 окт 2026)

**Период:** вечер 18 окт 2026 (23:10 Asia/Almaty) → 20 окт 2026 (22:12).
**Источники этой части:** переписка в этом чате и ~50 скриншотов терминала Kilo/OpenCode, Kaggle, YouTube, а также три документа, которые вы приложили: журнал `youtube-niche-finder-project-notes.md` (18 окт), отчёт Perplexity «Bottom line» и русский бизнес-анализ «25 ниш» (20 окт).
**Важная оговорка:** я (Claude) не подключался к Codespace и не проверял репозиторий. Все статусы, коммиты и цифры ниже взяты из отчётов агентов Kilo и OpenCode на скриншотах. Это не независимый аудит. Роли агентов в большинстве вех работали inline, без независимого ревью.
**Секреты:** ни ключи, ни токены, ни содержимое `.env` сюда не записаны.

---

## 5.0 Как читать эту часть

1. 5.1 Где мы сейчас (самое важное).
2. 5.2 Хронология по вехам.
3. 5.3 Эволюция решения по нише (таблица).
4. 5.4 Измеренные данные спроса (всё, что мерил OpenCode).
5. 5.5 Права, политика YouTube, риски.
6. 5.6 Технические находки (Kaggle-мост, голос, блокировки, диск).
7. 5.7 Ошибки и исправления (реестр честности).
8. 5.8 Ваши открытые решения и задачи.
9. 5.9 Что делать дальше (порядок).
10. 5.10 Индекс промптов + полный текст главных промптов (Приложение 5A).
11. 5.11 Короткий промпт для нового чата.

---

## 5.1 Где мы сейчас (на 20 окт 2026, 22:12)

### Среда
- Codespace «scaling spoon» на аккаунте `dragongod73584-design`, ветка `factory/business-documentary-pilot`, remote `sora73636-stack/OpenMontage`.
- Kaggle-аккаунт `forts845`, мост работает с GPU T4 и интернетом (раннер `forts845/of-bridge-runner`, ядро бейкоффа `forts845/g2-image-bakeoff`).
- **Диск `/workspaces`: 2,1 ГБ свободно (94% занято)** при полу 800 МБ. Это ближайшая опасность. Чистить кэши и медиа до следующих тяжёлых шагов.
- В выводе Kilo повторяется `cannot pull with rebase: You have unstaged changes`: push проходит, но rebase не выполняется. Незакоммиченный файл: `docs/openmontage/image_gen/LICENSE_EVIDENCE.md` (изменён, не в коммите). Нужно закоммитить или `git stash`, потом `git pull --rebase`.

### Последние коммиты ветки (по порядку)
`0eaba04` (старт) → `3c0b450` (R2) → `3d5865b` (починка пересборки) → `6e2a221` (H) → `f1b4b2f` (демо-отчёт OpenCode) → `16f2b31` (I) → `8e96cda` (K: космос) → `a943d51` (T1-T5) → `31c9bf9` (yt-shorts) → `6396d38`, `7cd32df` (отчёты Apollo 9) → `579ba4c` (Z) → `d5b2da0` (kokoro-onnx + Apollo 9 озвучка) → `ab4d9a3` (Y) → `cde548d` (X) → `917dd86` (W: ISS) → `50faafd` (G1: ИИ-картинки) → `718baf5` (G2 + ISS v2) → `2a52fdf` (M: M1-M9).

### Готовность (моя оценка, не замер)
- Фабрика как конвейер: около 65-70% (права, QC, claim_id, озвучка, мост на GPU, режим глав, обобщённый рендер).
- Как работающий канал: около 30%. Ни одного опубликованного видео, реакции аудитории нет.
- Новые модули из вехи M (иллюстрации, музейные адаптеры, разнообразие движения, упаковка, импорт аналитики, ревью-пакет) есть в коде и тестах, но на реальном эпизоде не прогонялись.

### Что готово и подтверждено агентами
- QC `tools/qa/qc.py` с `qa_report.json`, проверка `claim_id` по реестру (а не только наличие), гейт ИИ-иллюстраций (метка «Illustration», доля времени), тесты проходят (в M9 «CI fast suite»).
- Конвейер `scripts/run_episode.py` (10 стадий, 6 тестов на заглушках), режим глав, `LONGFORM_SPEC.md`, `SERIES_PLAN.md` (12 тем), `REVIEW_PACK.md`.
- Озвучка Kokoro через `kokoro-onnx` (обход блокировки Hugging Face).
- Три собранных черновика, все NOT_PUBLISHABLE: CID (срез, 320x240), Apollo 9 (слайдшоу из 2 фото и карточек), ISS (HD, 1280x720, но один клип NASA).
- Kaggle-мост: GPU, интернет, multi-image manifest, проверка sha256.
- Исследования OpenCode: спрос по космосу, авиации, Apollo, ISS, иллюстрированной истории, 40 ниш.

### Что не подтверждено или провалено
- **G2 (сравнение моделей Z-Image Turbo / FLUX.2 klein / SDXL-Lightning): ПРОВАЛЕН.** v1 ядра дал 0 картинок (модели не загрузились в fp16, в образе Kaggle нет `bitsandbytes`, ошибка была проглочена); v2 после одной правки упал (CPU TypeError, FLUX OOM). Причины записаны в `docs/openmontage/image_gen/G2_STATE.md`. Сравнения качества моделей нет.
- G1 (только SDXL-Lightning): 10 картинок 1024x1024 получены, 3,9 с на картинку, вердикт агента USEFUL, но агент картинок не смотрит. Вы сами видели одну картинку (абстрактные линии на тёмном фоне) и сказали, что **артефактов много**.
- Отчёты OpenCode по иллюстрированным нишам, истории, пересмотру ниш лежат в `youtube-niche-finder/reports/` (не в git нашей ветки). **Не подтверждено, что вы скопировали их в `docs/openmontage/audit/demand/`.** Если нет, скопировать (команды ниже).
- Папка `youtube-niche-finder/` это клон чужого репозитория `pandich93/youtube-niche-finder`: push туда даёт 403. Её нельзя коммитить в нашу ветку целиком, только копировать отчёты.

---

## 5.2 Хронология по вехам

### 18 окт, вечер: перенос в новый аккаунт и починка пересборки
- Старт: Codespace «scaling spoon», коммит `0eaba04`, 19 ГБ диска. Срез CID на 56 с (озвучка Kokoro S1-S8, фото, три клипа в рамке 2x, две графики, источник FAA) прошёл QC. Причина прежнего сбоя: манифест начинался со строк `# ...` и ломал JSON; `rebuild_slice_assets.sh` печатал `DONE` после `JSONDecodeError`.
- Промпты R1/R2: скрипт стал fail-closed (`3d5865b`), срез пересобран (52,8 с), QC 11/12 PASS, REVIEW только на статичной карточке S8. Коммит R2: `3c0b450`.
- Модели: Nemotron 3.5 Super VL по умолчанию, Laguna S 2.1 для кода. OpenCode Zen free-модели: ответ остался неполным.
- Запущены параллельно два агента с разделением по папкам: Kilo (фабрика: `docs/ tools/ scripts/ tests/ .kilo/`) и OpenCode (только `youtube-niche-finder/`). Это правило действует до сих пор.

### 19 окт, ночь-утро: вехи H, I; первый замер спроса
- **Веха H (Kilo, `6e2a221`):** реестр утверждений CID вырос до 50 (CID-31..50), полный сценарий 6 блоков и 40 предложений, QC `claim_ids` 52/52. Все новые утверждения SINGLE_SOURCE (TM-4084 и NTRS агенту недоступны). Покрытие кадров: 8 видеоклипов NIX и 5 фото NASA; блок B6 «последствия» без кадров; 4 ресурса отклонены (чужие кредиты); 3 обложки; X-15 и XB-70 получили оценку LOW. Не проверены: E5 (классификатор кадров), разрешение `claim_id` по реестру.
- **Первый замер OpenCode:** ветка `aviation-test-history-demand`, коммит `0a4c184` только локально (push 403). Схема БД в порядке (`video_stat_snapshots`, 1252 снимка). `collect_niche` работает через `scripts/mcp-host.sh`, штатная обёртка OpenCode ломается с `Unexpected token`. 6 запросов × 2 периода × 15 видео.
- **Вердикт: DEMAND_SIGNAL_PRESENT, но с оговоркой.** 14 уникальных видео >100k просмотров у каналов <50k подписчиков за 12 мес. 13 из 14 это Shorts. Длинных два: «Aerospace, Casually» (9:51, 137 569 просмотров, 327 подписчиков) и «Supernova» (8:12, 678k). Один выброс (419x) не доказывает вывод.
- **True crime отвергнут** для нашей фабрики: нет законных кадров по конкретным делам, риск клеветы и этики, ограничения рекламы, перенасыщение. Оценка 83/100 у OpenCode оценивала спрос на видео, а не возможность собрать честный визуал.
- Отчёты скопированы в `docs/openmontage/audit/demand/` (коммит `f1b4b2f`).
- Выбор угла подачи: я сначала предложил угол 2 («покадровый разбор»), потом угол 1 («что они на самом деле тестировали») по заголовкам. Затем OpenCode проверил: **угол 1 не подтверждён (WEAK)**, медианы просмотров 1 694 против 1 308 (шум), «интриги» у каналов с медианой 250 подписчиков против 5 220. Длинных видео ≥6 мин с >50k просмотров у каналов <50k подписчиков за год всего 8. Shorts 36%, длинные 38%. Я признал рекомендацию преждевременной.
- Риски по тяжести (OpenCode `niche-pitfalls`): 1) повторно использованный/неоригинальный контент (высокий); 2) Content ID на кадрах NASA (высокий); 3) неприятие ИИ-голоса; 4) обязанность раскрытия синтетического голоса; 5) качество архива 320x240.
- **Веха I (Kilo, `16f2b31`):** FAA-отчёт (92 стр.) прочитан, CID-06, 10, 15 стали TWO_SOURCES, найдено новое противоречие CID-20 против CID-25; проверка `claim_id` по реестру (52/52); тест классификатора кадров E5; B6 закрыт только графикой; исправлена лицензия Kokoro (Apache-2.0, неизвестно лишь происхождение части синтетических обучающих данных); I5 заблокирован (Kokoro не установлен).
- **Вы попросили сменить нишу.** Замер трёх ниш (OpenCode `niche-compare-v2`): A космос/астрономия на HD NASA/ESA/Hubble: STRONG (13 прорывов, 0 длинных 8-15 мин); B наука и природа: MIXED (8); C философия/психология: WEAK (44 прорыва, 4 длинных, высокий риск reused и ИИ-голоса). Тревожный общий вывод: в формате 8-15 минут у малых каналов прорывов не найдено, выстреливают Shorts и очень короткие ролики.

### 19 окт, день: веха K, оценка готовности, длинный формат
- **Веха K (Kilo, `8e96cda`):** профиль ниши «space and astronomy on HD public-domain footage», CID остаётся тестовым роликом (320x240 ниже планки HD ≥720p). Проверено 10 тем; три скачанных клипа реально HD: Artemis 4K, Hubble 1080p, Perseverance 4K. Лучшие темы по числу клипов: Artemis/SLS 672, Hubble 152, Perseverance 117. Реестр Artemis 12 утверждений, сценарий 3,5-4 мин на 19 предложений, план Shorts 45 с, QC `claim_ids` 21/21, парсер `qc.py` обобщён с CID на любые ID (регрессия CID 52/52). Не проверено: права ESA/Hubble по каждому ролику, HD для тем 4-10, `nasa.gov` отдал 429.
- Оценка фабрики 65% / канала 30%. Про ключи API для футажей: почти ничего не нужно (NASA, Internet Archive, Wikimedia, LoC, NARA работают без ключа). Свой бесплатный ключ NASA API (api.nasa.gov) стоит положить в Codespaces Secret, в чат и агенту не давать.
- План лестницы длины: 3-4 → 8-10 → 15-20 → 40-50 мин, переход только по метрикам YouTube Studio (CTR, удержание первых 30 с, средняя длительность), без выдуманных порогов. Для 40-50 минут нужны 150-250 утверждений, 40-60 минут визуала, сборка по главам.
- **Вы попросили «супер-промпт на всё».** Я выдал Milestone Z (возобновляемый, с `Z_STATE.md`) для Kilo и пять задач T1-T5 для OpenCode.
- **OpenCode T1-T5 (коммит `a943d51`):** T2 LONG_FORM_VIABLE (24 видео по 25-60 мин от малых каналов с >30k просмотров, из них 5 за последние 24 мес, вывод слабый); T1: 30 тем, 5 прорывов у малых каналов с 8+ мин; T4: рабочих шаблонов названий и обложек нет (шум); T5: NASA в общественном достоянии хватает (ISS, Apollo, Artemis, JWST, New Horizons), SpaceX Starship и Crew Dragon не берём (частное авторское право), эмблемы NASA ограничены (14 CFR 1221).
- Затем T6-T12 (Apollo, анатомия длинных, комментарии, рост каналов, ключевые слова, терпимость к ИИ-голосу, проверка кадров). Результаты сохранены по тем же командам `cp` в `docs/openmontage/audit/demand/`.

### 19 окт: навыки, YouTube-канал, AdSense
- Из 11 навыков `youtube-agent-skill` установлен только `yt-shorts` (коммит `31c9bf9`, закреплён commit `a2feb21`; установил OpenCode, а не Kilo; добавлен `claim_id` на каждое предложение, без обещаний «вирусности», без загрузки и OAuth). Остальные: yt-script, yt-package, yt-chapters, yt-seo уже стоят; yt-retention и yt-audit позже (нужны данные Studio); yt-viral пропустить (замер T4 показал шум); yt-edit дублирует наш монтаж; yt-comment пишет от имени канала, запрещено.
- Канал YouTube к Codespace не подключаем: канала с видео ещё нет, OAuth-токен доступен агентам (риск prompt injection), правило «ноль секретов», публикация вручную в Studio.
- **AdSense:** вы спросили, зачем родитель. Ответ: AdSense требует совершеннолетия, выплаты привязаны к имени и документам владельца. Варианты: аккаунт родителя/опекуна, канал на родителя, а вы менеджер с ролью доступа в Studio; либо расти без монетизации. Вы решили: **«пока забудем AdSense, продолжаем фабрику, потом посмотрим получу ли я монетизацию»**. Принятая логика: синтетический голос и источники раскрываем в любом случае.
- Принято читать на странице AdSense: принимает ли выплаты в Казахстан, какой возрастной порог. Я не знаю, проверить на support.google.com/adsense.

### 19 окт: Apollo-исследование
- **T10 (ключевые слова, квота 41 из 100):** самая низкая конкуренция у Apollo 9 (стыковка), Apollo 10 (ближайшее сближение с Луной), Apollo 11 (первая прогулка: старых видео >100k много, свежих за год нет). Самые занятые: Artemis III и II (конкуренция 51 и 47). Я рекомендовал первым роликом Apollo 9.
- T13-T18 (Apollo 9 глубоко, Apollo 10/11 пробелы, карта первичных источников NTRS/Apollo Flight Journal/Lunar Surface Journal, вопросы зрителей: 1 022 комментария, 449 вопросов, лидирует развенчание мифов; Shorts против длинных: у Shorts в 2,5 раза выше отношение просмотров к подписчикам; названия: паттерн по одному примеру N=1).
- **Три канала со скриншота** («Built On You», «RenderFit», «James Whitfield»): моя оценка: №1 (истории компаний, мультяшная анимация, ~20 мин, канал 4,65K подписчиков, ролики 25K-141K) возможен только при очень сильной графике и строгом реестре утверждений; №2 (3D-тренировки) требует 3D-анимации и более строгой модерации здоровья; №3 (бывший заключённый, лицо в кадре) это личность, не повторить, риск AI-персоны. Урок: у выстреливающих малых каналов есть единый узнаваемый визуальный стиль и обложка.
- **Веха OZ (OpenCode):** факт-пакеты Apollo 9 (42 утверждения: 25 TWO_SOURCES, 17 SINGLE), Apollo 10 (30), Apollo 11 (33), структура на 9 глав (~17 мин) с крючком-развенчанием мифа, 12 Shorts, реестр рисков из 6 пунктов, разбор 8 конкурентов. **Кадры по OZ5:** Apollo 9 около 23 мин HD (оценка, потом опровергнута), у Apollo 10 HD нет, у Apollo 11 около 1 минуты.
- **Вехи A и B (OpenCode):** A: факт-пакет Apollo 9 v2, 42 утверждения «подтверждены» (17 стали двумя источниками, часть вторых источников вторичные), сценарий ~2300 слов, 3 Shorts. B: агент сначала повторил A, потом выполнил B: 15 из 17 бывших одиночных получили два первичных источника NASA, по одному: A9-036 PRIMARY_ONE и A9-038 SECONDARY_ONLY; 4 неверные атрибуции в сценарии исправлены; 9 новых Shorts; `apollo9-chapters.json` (9 глав). Коммиты отчётов: `6396d38` и `7cd32df`; отдельный `apollo9-footage-map` не создан, данные в `t05-footage-inventory`, `t12-footage-fit`, `t5-footage-crawl`.
- **Вы вставили текст промпта в терминал bash** вместо окна агента (ошибки `syntax error`). Безвредно, но промпты идут только в окно агента.

### 19-20 окт: веха Z, блокировка Hugging Face, kokoro-onnx
- **Веха Z (Kilo, до `579ba4c`):** Z1-Z9 выполнены кроме дымовых тестов: пакет весов Kokoro недоступен (HF xet CAS и CDN недоступны из сети Codespace, `huggingface.co` отвечал 200, но `cdn-lfs.huggingface.co` и `cas-server.xethub.hf.co` пусто). Готовы: Artemis черновик (QC PASS, NOT_PUBLISHABLE), конвейер + 6 тестов на заглушках, режим глав + 5 тестов + `LONGFORM_SPEC.md`, `SERIES_PLAN.md` (12 тем), сценарии/реестры/Shorts для 3 тем, упаковка, `REVIEW_PACK.md`, 29 быстрых тестов с кодом 0.
- **Обход (коммит `d5b2da0`):** Kilo нашёл `kokoro-onnx==0.6.1` (PyPI, MIT) и веса Kokoro-82M ONNX с GitHub Releases (`thewh1teagle/kokoro-onnx`, `model-files-v1.1`): `kokoro-v1.0.onnx` 310 МБ (Apache-2.0 по README) и `voices-v1.0.bin` 27 МБ. Python 3.12 venv, `onnxruntime==1.20.1`, `espeakng-loader`, `phonemizer`. Проба 10 с (RTF 1,0), `finish_audio` PASS, `qc.py` PASS (−15,8 LUFS). Зависимости закреплены в `z1_voice_venv.requirements.txt`. Apollo 9: реестр 42 утверждения (все TWO_SOURCES), сценарий 13 предложений, озвучка 421 с, субтитры 1005 слов.

### 20 окт, утро: вехи Y, X, W (Apollo 9 не проходит, ISS проходит)
- **Y (`ab4d9a3`):** рендер обобщён (EDL и пути кадров на эпизод, без привязки к Artemis). Y2: **чистого HD Apollo 9 в общественном достоянии нет**: ролик splashdown под CC BY-NC-ND, 16 мм только через ИИ-апскейл (запрещено), скачаны только 2 фото NASA. Сценарий исправлен (3 правки `claim_id` по ревью), озвучка 428,6 с, EDL 19 склеек, 1920x1080, QC PASS (12 PASS + 1 REVIEW), NOT_PUBLISHABLE.
- **X (`cde548d`): Apollo 9 как первая тема не проходит.** 100 фото NASA, 59 чистых по правам (порог 60), главы 4-7 (внутри LM, выход в открытый космос, Spider, S-IVB) без кадров; видео 0 минут (splashdown CC BY-NC-ND; 16 мм в апскейле; «Space Duet» в SD; «three-to-make-ready» с чужим кредитом); из 13 видео NASA API ни одного архивного Apollo 9. Оценка OpenCode «23 минуты HD» оказалась **завышенной**. Рекомендация: ISS (100 HD-видео NASA, центры GRC/JSC/HQ, без NC/ND). Apollo откладываем, сценарий и реестр Apollo 9 не пропали.
- **W (`917dd86`): ISS «Earth view / cupola».** Конкуренция 0,5 (самая низкая в T10). Кадры: NASA «Earth Views from the ISS» (`NHQ_2019_0626`), 1280x720 родное HD, 44:00, общественное достояние, без NC/ND, без апскейла (776 МБ, sha256 записан). Реестр 4 утверждения (ISS-003 TWO_SOURCES, три SINGLE_SOURCE), сценарий 8 глав, озвучка 195,7 с (~3 мин), 16 склеек, 9 графических карточек. QC 12 PASS + 1 REVIEW. NOT_PUBLISHABLE (раскрытие синтетического голоса, эмблемы, один клип).
- **Ваш просмотр видео ISS:** «Неплохо, но один футаж на всё видео, а карточки это объяснительная». Я заметил: в кадре Земли виден водяной знак «Earth from the Space Station» с эмблемой станции (нужно кадрировать), из 44 минут используется один клип.

### 20 окт, день: ИИ-картинки, Google Flow, Kaggle
- **Google Flow:** не подходит. Нужно 18+, API нет (только Veo через платные Gemini API/Vertex AI), бесплатно 50 кредитов в день, водяной знак и SynthID, условия коммерческого использования неясны. Автоматизировать вход в Google-аккаунт нельзя. Связи Codespace ↔ Flow нет; допустим только ручной перенос.
- **SDXL-Lightning на Kaggle:** подходит только для иллюстраций, не для «фото событий». Промпт G1. Перед запуском нужны подтверждение телефона в Kaggle и секрет `KAGGLE_API_TOKEN`.
- Агент ждал очередь Kaggle около 16 минут (`QUEUED`, потом `RUNNING`); потом G1 занял ~8 минут.
- **G1 (`50faafd`):** лицензии (SDXL-Lightning и базовый SDXL OpenRAIL++, коммерческое использование разрешено, FLUX.1-schnell Apache-2.0 но веса закрыты на HF), 10 картинок SDXL-Lightning 1024x1024, **3,9 с на картинку, 0,70 минуты GPU всего, пик VRAM 10 457,9 МБ**, хеши и размеры сверены, мост расширен, QC-гейт `ai_illustration_label` (красный-зелёный), `AI_IMAGE_POLICY.md` (метка «Illustration», не более 10-15% времени, `rights_basis=ai_generated_illustration`), тесты: мост 21, qc-ai 4, qc-tool 13.
- Вы: **«Артефактов много, найди другую модель с меньшим числом артефактов, качеством и скоростью, сравнивай на форумах».** Я нашёл: кандидаты Z-Image Turbo (6B, Apache-2.0, 8 шагов, <16 ГБ, обсуждается как «лучший открытый фотореалист»), FLUX.2 klein 4B (4 шага, ~13 ГБ, **лицензия противоречива: Википедия пишет Apache-2.0, другие блоги пишут «нужна коммерческая лицензия»**, решать по официальной карточке), FLUX.1 schnell (Apache-2.0, медленнее на 16 ГБ), Qwen-Image (Apache-2.0, медленная, сильна в тексте), SD 3.5 (Community до $1 млн дохода). Оговорки: T4 не умеет bf16 и имеет 16 ГБ; рейтинги отчасти маркетинг; часть ваших артефактов вероятно от 4 шагов и абстрактных промптов («линии»).
- **Kaggle MCP:** официальный удалённый MCP (`kaggle.com/mcp`, OAuth) и сторонние (`safe-kaggle-mcp`, `kaggle-mcp-server`) оборачивают тот же API; очередь на стороне Kaggle, ускорения не даст. Решение: «отправил и ушёл», состояние в файле, без `sleep` и циклов опроса.
- **Промпт G2+V2** (Kilo никогда не простаивает): параллельно сабмит бейкоффа, апгрейд ISS (8-10 клипов, 25-40 сцен с кадрированием водяного знака, анимированные диаграммы, 20-30 утверждений, пересборка), потом обработка результата.
- **Результат G2+V2 (`718baf5`):** ISS Phase 1 готов: 2 дополнительных HD-клипа NASA (`iss_earth_views_medium` 1280x720, `step_inside4k_clean_medium` 1080x608), 25 сцен из `NHQ_2019_0626` с кадрированием водяного знака/эмблемы (сверху 50 + снизу 90 px, масштаб обратно) в `edit_decisions.json` + `FOOTAGE_INVENTORY.md` с sha256 (~266 МБ), 3 анимированных диаграммы (orbit_path ISS-001, cupola_geometry ISS-002, daynight_timeline ISS-001; 1280x720/30fps/12 с; статичные карточки `static_by_design`), реестр 24 утверждения (2 источника NASA: nasa.gov/station и nasa.gov cupola; **ISS-020 TWO_SOURCES, остальные SINGLE_SOURCE**), сценарий 37 предложений (`claim_ids resolve` 37/37), повторная озвучка + `finish_audio` (−15,1 LUFS), видео 1280x720/30fps/298 с, QC все входы PASS, **NOT_PUBLISHABLE по творческим причинам**: длительность 298 с < цели 6-8 мин, анимированные диаграммы не вставлены в таймлайн, титры/кредиты не вжжены.
- **G2 (бейкофф): фаза 2 заблокирована, потом закончилась провалом.** v1 ядра: 0 картинок (bitsandbytes отсутствует в образе Kaggle, ошибка проглочена); v2 перепушена с CPU float32 запасным путём (512 px, 2 шага). В итоге (по отчёту M1): G2 FAILED, причины в `G2_STATE.md` (CPU TypeError, FLUX OOM). Нужно переделать: fp16 без `bitsandbytes` (или `pip install` внутри ядра), без запасного CPU-пути на таких моделях, одна модель за запуск.

### 20 окт, день-вечер: новая ниша, иллюстрированные форматы
- **Вопрос «можно сменить нишу, раз ИИ-картинки решают нехватку материала»:** частично. Остаются: политика про массовый шаблонный контент, раскрытие синтетики, конкуренция, единый стиль на 100+ картинках, факты. ИИ-картинки честны там, где реальных кадров не существует (вымысел, гипотеза, «что если»). Зрители хвалят «NO AI» в исторических нишах.
- **OpenCode, замер иллюстрированных ниш** (8 вызовов поиска + 4 видео + 4 канала; MEASURED): B история в иллюстрированном стиле **STRONG** (n=14, 84,9% длинные, прорыв 1,8 млн у канала <50k: Chris Explains, 30,4k подписчиков, «Most Wanted People», 22:46); A истории компаний MIXED (n=16, прорывы до 893k, но каналы-гиганты); C наука/инженерия WEAK (n=9); D мифология/психология MIXED (n=17, перехвачена шаблонным «Mythological Man» ×5).
- **Подтемы истории (18 измерено, 12 пустых = NOISE):** Древний Египет STRONG (n=9), Средневековая Европа STRONG (n=5), Османская империя MIXED (n=5, Shorts больше, чувствительно), Рим WEAK (n=4), Британская империя WEAK (n=3). Прорывы: Chris Explains (1,81 млн), «Most Devastating Tragedies» (1,36 млн), Animated History Russia «Israel» (16,3k/822k/35:59), Barely Accurate «British Colonize India» (24k/540k/10:01), Serious History (1,37 млн, формат для сна, не наш). Зрители хвалят «NO AI» рисованные иллюстрации; русскоязычные комментарии указывают на пробел английского контента. Вывод: формат «Most X in History Explained» с главами; риск живых людей низкий; чувствительные: Крестовые походы (высокий), Османская империя (средне-высокий), Британская империя (средний).
- **Ваш запрос «дай промпты для ChatGPT и Perplexity, найти faceless-нишу».** Составлены три промпта (Perplexity Deep Research, ChatGPT Deep Research, OpenCode `niche-rediscovery`). Текст ниже в Приложении 5A.
- **Perplexity («Bottom line»):** честно написал, что требование «10 ниш × 5+ каналов <10k с 50k+ длинными просмотрами за 12 мес.» проверить не смог (**UNKNOWN**). Подтверждено: политика YouTube. Июль 2025: «повторяющийся контент» переименован в «неаутентичный контент»; ИИ-канал монетизируем при оригинальной сути; примеры нарушений: «AI-generated content made with generic or unoriginal templates», «image slideshows, templated storylines, or scrolling text with minimal or no narrative»; ИИ-персоны с медицинскими/юридическими/финансовыми/политическими советами не монетизируются; требуется раскрытие реалистичного синтетического контента. Топ-10 (оценки, не измерения): 1 космос/инженерная история (8,4), 2 геология и катастрофы (8,1), 3 история бытовых технологий (7,9), 4 карты и границы (7,8), 5 история искусства (7,6), 6 инженерные аварии, 7 как устроены системы, 8 древняя инженерия, 9 бизнес-история закрытых компаний, 10 биографии учёных. RPM только из сторонних источников (противоречивы). Рекомендация: сначала длинный формат, Shorts как тизеры. Тест трёх рисков: дешёвая проверка спроса вручную, A/B озвучка, визуальная доска из 30 активов (минимум 15 чистых).
- **Русский бизнес-анализ «25 ниш»:** 25 идей, 10 кандидатов, топ по ESTIMATE: География (8,40), история бытовых предметов (8,30), геология (8,25), научные инструменты (8,12), глубокий океан (7,92), системы письма (7,82), материальная культура древних (7,67), археологические методы (7,54), инженерия (7,48), палеонтология (7,28). Анализ чувствительности весов: топ почти не меняется. Три пилота на нишу, окно оценки 14 дней, порог ~1 000 показов (ESTIMATE, не официальный). Начать с географии и истории предметов, геологию следующей. Библиотека источников: Natural Earth, USGS, NOAA, Smithsonian, Met, Wikimedia, LoC, NASA, NPS. Я сопоставил и вывел пересечение: **искусство и материальная культура** и (геология, предметы, карты) совпали в обоих отчётах.
- **OpenCode niche-rediscovery (40 сидов, 40 вызовов поиска; визуальная доступность ESTIMATE, потому что поиск по Internet Archive вернул 0):** топ: **история искусства STRONG** (9 прорывов, Shorts 24%, медиана 22 мин, визуалы Tier A (EST), риск низкий), мифология анимированная STRONG (8; Shorts 10%; 16 мин; Tier B), глубоководные существа STRONG (5; 20%; 15 мин; Tier B); ранги 4-10 (физика, древние битвы, математика, история технологий, железные дороги, WW2) WEAK/NOISE (n<5). Только топ-3 проходят порог n≥5.
- **Моё решение (вы не возражали):** пилотная ниша **история искусства и материальная культура** (настоящие работы из открытых музейных коллекций как основной визуал, ИИ только подложки с меткой, до 10-15%); космос/ISS оставляем вторым треком (инфраструктура готова); мифологию не берём (шаблонные каналы); географию и геологию откладываем до замера.
- **Поиск более глубоких инструментов ниш:** `pandich93/youtube-niche-finder` (уже есть), `bangermap-mcp` (npm, выбросы относительно базы канала, малоизвестный: проверять код перед установкой), OutlierKit (платный, MCP), TubeLab/Apify (платные). Правило «максимум 3 компонента» сохраняется, новых репозиториев не ставим. Улучшение метода: `scripts/outlier_v2.py` (база = медиана последних 20 длинных загрузок канала без самого видео и роликов моложе 7 дней, `outlier_multiple`, `views_per_day`, uploads playlist вместо `search.list` по 1 единице квоты вместо 100; повторяемость = ≥3 разных канала <50k подписчиков с кратностью ≥5 и просмотрами ≥30k за 12 мес.).
- **Мастер-план «100% фабрики»** (10 слоёв с долями готовности и распределением Kilo/OpenCode) и **ниша только на ИИ-картинках** (рассматривались: гипотетическая наука/«что если» с проверенными фактами №1, оригинальные фантастические истории, мифы из текстов общественного достояния, концепты будущего; исключены реалистичные «фото» событий и людей, детский контент, новости). Спрос на такой формат **не измерен**.
- **Веха M (Kilo, `2a52fdf`): M1-M9 завершены** (G2 при этом FAILED): иллюстрации (style bible, batch QC: размытие по Лапласу, p-hash дубликаты, размер/аспект, признаки текста; метка «Illustration»; 9 тестов), профили ниш `space_iss`, `art_history`, `speculative_science` (YAML; допустимые источники, правила утверждений, по 3 шаблона эпизодов), музейные адаптеры Met/Smithsonian/Rijksmuseum/NGA/Wikimedia (только явный CC0/PD, `asset_record` с sha256/кредитом/URL; 4 теста; только фикстуры, без сети), разнообразие движения (pan/zoom, параллакс, карты/таймлайны, lint без двух одинаковых движений подряд; 8 тестов), упаковка (миниатюры без эмблем и людей, метаданные и блок кредитов, ссылки на страницы YouTube; 3 теста), `review_pack.py` + `run_evals` E1-E5 (3 теста), импорт CSV YouTube Studio и точки падения удержания по главам (3 теста), CI-набор и dry-run переносимости (3 теста). Диск 2,1 ГБ. Незакоммичен `LICENSE_EVIDENCE.md`. Медиа не коммитились.

---

## 5.3 Эволюция решения по нише (сводная таблица)

| Дата | Решение | Основание | Статус |
|---|---|---|---|
| 16-17 окт | «Скрытый бизнес за обычными вещами»; логистика и др. | Perplexity подтвердил частично (Часть 1) | Закрыто ранее |
| 18 окт | Авиационные и космические испытания на архивных NASA/USAF кадрах, пилот CID (1984 Boeing 720) | Права NASA, готовый срез | Тестовый ролик, 320x240 ниже планки HD |
| 18 окт (журнал notes) | True Crime Cold Cases (83/100), запас Space Mysteries (83), Stoicism (81) | OpenCode, неподтверждённо | **Отвергнуто** (кадры, клевета, реклама) |
| 19 окт | Угол 1 «что они на самом деле тестировали» | Заголовки в выборке | **Не подтверждён** (WEAK), снят |
| 19 окт | Космос/астрономия на HD NASA/ESA (замер `niche-compare-v2`: STRONG, 0 длинных 8-15 мин) | Кадры HD, права | Принято как основная |
| 19 окт | Apollo 9 как первая тема (пустая полка длинных роликов) | T6, T10 | **Не прошла** по кадрам (X) |
| 20 окт | ISS «Earth view / cupola» | Конкуренция 0,5, 44 мин HD | Первый честный HD-ролик, NOT_PUBLISHABLE |
| 20 окт | Иллюстрированная история (STRONG n=14), Древний Египет, Средневековая Европа | OpenCode замер | Рассмотрено; зрители хвалят «NO AI» |
| 20 окт | **История искусства и материальная культура** (9 прорывов, 22 мин, Shorts 24%) | niche-rediscovery + оба внешних отчёта (пересечение) | **Пилот, выбран мной, ждёт вашего подтверждения** |
| 20 окт | ИИ-только ниша (гипотетическая наука и т.д.) | Теоретически возможна | Только замер, не запускали |

---

## 5.4 Измеренные данные (MEASURED через YouTube API, если не указано ESTIMATE)

- **Авиация/CID (замер 1):** 14 видео >100k просмотров у каналов <50k подписчиков за год; 13 из 14 Shorts; длинные: Aerospace Casually 9:51 / 137k / 327 подписчиков; Supernova 8:12 / 678k. Крупные каналы доминируют по просмотрам за всё время (NASA, Mark Rober, Real Engineering). Три угла из отчёта: «что они на самом деле тестировали», «покадровый разбор», «лётчики».
- **Угол 1 против обычных:** медианы 1 694 / 1 308, шум. Длинных ≥6 мин с >50k из каналов <50k за год: 8. Shorts 36%, длинные 38%. Миниатюры «text only» не проверены (NOT_CHECKED).
- **3 ниши v2:** A космос STRONG (13 прорывов, 0 длинных 8-15 мин), B наука/природа MIXED (8), C философия WEAK (44 прорыва, 4 длинных).
- **T2 длинный формат:** 24 видео 25-60 мин (>30k просмотров, каналы <100k подписчиков), 5 за 24 мес.
- **T10 конкуренция (0-51):** Apollo 9 стыковка, Apollo 10 сближение, Apollo 11 прогулка: около 0,0; Artemis III 51, Artemis II 47; ISS cupola 0,5. Выборки по темам 3-4 видео, шум.
- **T16 вопросы зрителей:** 1 022 комментария, 449 вопросов; лидируют мифы/«почему они…».
- **T18:** у Shorts в 2,5 раза выше отношение просмотров к подписчикам; публиковать оба формата, Shorts первыми (выборка мала).
- **Иллюстрированные ниши:** B история STRONG n=14, A компании MIXED n=16, C наука WEAK n=9, D мифология MIXED n=17.
- **Подтемы истории:** Египет n=9 STRONG; Средневековье n=5 STRONG; Османы n=5 MIXED; Рим n=4; Британская империя n=3; из 30 подтем порог n≥5 прошли 3.
- **Rediscovery (40 сидов):** история искусства 9 прорывов; мифология 8; глубоководные 5; остальные n<5.
- **Квота YouTube API:** 41/100 на момент T10; затем 8+18+40 поисковых вызовов в следующих задачах (суммарно примерно 26-40 за задачу, кэш).
- **Ограничения всех замеров:** выборки 3-17 видео; один выброс (419x; 1,8 млн) не доказывает формат; визуальная доступность в `niche-rediscovery` оценочная; RPM и доходы не заявлялись.

---

## 5.5 Права, политика YouTube, риски

### Политика YouTube (страницы приводили OpenCode и Perplexity)
- Неаутентичный/повторно используемый контент: `support.google.com/youtube/answer/1311392`; FAQ: `.../community-guide/271248162`.
- Раскрытие синтетического контента: `.../answer/14328491`; «как создан контент»: `.../answer/15447836`.
- Суть: ИИ как инструмент разрешён, массовый шаблонный контент (шаблонные слайдшоу, нет повествования) не монетизируется; реалистичный синтетический контент раскрывать. Нужно ли раскрытие для явно нереалистичных иллюстраций, проверять на официальной странице. Перед публикацией читать эти страницы глазами.

### Права на кадры
- NASA: в общественном достоянии, но часть материалов сторонняя; нельзя подразумевать одобрение NASA; эмблемы ограничены (14 CFR 1221). Водяной знак/эмблема внутри клипа «Earth from the Space Station» нужно кадрировать.
- Отклонять: чужие кредиты (A/V Geeks и др.), CC BY-NC-ND (splashdown Apollo 9), частные кадры SpaceX (Starship, Crew Dragon), ИИ-апскейл 16 мм (запрещён нашим правилом).
- Музеи: Met (Open Access), Smithsonian (CC0), Rijksmuseum, NGA, Wikimedia Commons (у каждого файла своя лицензия), LoC (free-to-use наборы). Проверять объект: фото 3D-предметов и работы XX века могут быть защищены.
- Content ID: возможен на ресурсах общественного достояния, хранить кредиты и права по каждому клипу.

### ИИ-картинки
- SDXL-Lightning и базовый SDXL: OpenRAIL++, коммерческое использование разрешено (по картам моделей, читал агент).
- Z-Image Turbo: Apache-2.0 (источники сходятся). FLUX.2 klein: лицензия спорная, проверять официальную карточку. FLUX.1-schnell: Apache-2.0, веса закрыты на HF (нужно принять условия).
- Политика канала: метка «Illustration», не более 10-15% времени, не выдавать за реальные кадры, не изображать реальные события, людей и эмблемы, `rights_basis=ai_generated_illustration`.
- Права на чисто ИИ-картинки у вас, скорее всего, нет охраны авторского права (позиция Бюро авторских прав США), это не защищает и вас.

### Голос
- Kokoro-82M: код/веса Apache-2.0 (доказательства в `VOICE_DECISION.md`), остаточный риск: происхождение части синтетических обучающих данных неизвестно. Раскрытие синтетического голоса в описании и Studio обязательно.

### AdSense
- Отложено. Возрастной порог AdSense и выплаты в Казахстан не проверены.

---

## 5.6 Технические находки

- **Kaggle-мост:** `tools/kaggle_bridge/kaggle_bridge.py` умеет GPU и интернет, multi-image manifest, `KernelWorkerStatus` парсинг. Очередь GPU бывает 10-20 минут; опрашивать раз в 5 минут, без `sleep`-циклов; правило «отправил и записал состояние в `G*_STATE.md`». Образ Kaggle не содержит `bitsandbytes`; fp16 на T4 для больших моделей может упираться в память или вести к CPU-откату, который падает.
- **Hugging Face из Codespace:** основной сайт работает, `cdn-lfs` и `xethub` заблокированы. Запасные пути: GitHub Releases (так был получен Kokoro ONNX), PyPI, ручная загрузка файла с телефона через проводник VS Code. Попытка `HF_HUB_DISABLE_XET=1` не помогла.
- **Kokoro ONNX:** `kokoro-onnx==0.6.1`, `onnxruntime==1.20.1`, Python 3.12 venv; RTF 1,0 на CPU (озвучка 7 мин ≈ 7 мин синтеза).
- **Системный Python 3.14.2** не подходит под Kokoro/torch; нужен изолированный venv 3.12.
- **ffmpeg 7.1.1, espeak-ng** установлены.
- **Рендер:** `scripts/run_episode.py` (10 стадий: claim ledger → валидация → манифест и права → озвучка → субтитры → EDL → рендер → `finish_audio` → `qc` → упаковка), `cmd_render` читает `render_manifest.json` (asset_id → {kind, path}); графические карточки циклятся как PNG; HD приводится к 1080p/720p с рамкой (pillarbox), без апскейла.
- **OpenCode-обёртка `collect_niche`** ломается с `Unexpected token (1:3)`; рабочий путь через `scripts/mcp-host.sh`. Починка не подтверждена.
- **Папка `youtube-niche-finder/`** чужой клон; пушить туда нельзя; в git нашей ветки не добавлять (`.opencode/` тоже).
- **Диск:** держать ≥800 МБ; сейчас 2,1 ГБ; удалить кэши весов, исходные клипы (776 МБ) и промежуточные рендеры, после того как sha256 записаны.
- **Батарея и Codespace:** часы Codespaces ограничены; останавливать `gh codespace stop -c <name>` при простое.
- **Google Flow, Colab, Kaggle:** Flow недоступен (18+, нет API); Kaggle работает; Colab не использовался.

---

## 5.7 Ошибки и исправления (реестр честности)

1. **Угол 1 («что они на самом деле тестировали») я назвал победителем по заголовкам.** OpenCode не подтвердил (WEAK, шум). Рекомендация снята.
2. **Оценка кадров Apollo 9 («23 минуты HD») от OpenCode оказалась неверной.** Гейт добавленной ценности в Y/X остановил публикацию слайдшоу до публикации.
3. **Apollo 9 как первая тема мной рекомендовалась** по пробелу в длинных роликах, но без кадров тема не стартовала. Ошибка в том, что я принял оценку кадров без проверки.
4. **OpenCode дважды повторил вехи:** A вместо B; потом B состоялось. Нужен явный «Do NOT redo; ignore *_STATE.md».
5. **OpenCode сам правил `.kilo/skills` для установки `yt-shorts`:** допустимо один раз, но правило разделения папок остаётся.
6. **Агенты ставят «inline, not independent»:** независимой проверки ни разу не было.
7. **G1 «USEFUL» поставил агент без просмотра картинок;** вы посмотрели одну и увидели много артефактов. Вердикт неподтверждён.
8. **G2 провален без сравнения моделей:** v1 проглотил ошибку загрузки; нужно всегда проверять число картинок и фиксировать ошибки.
9. **Я не знал точной лицензии FLUX.2 klein:** источники противоречат. Решать по официальной карточке.
10. **Вы вставляли промпты в терминал bash:** появились `syntax error` и `command not found`. Безвредно.
11. **Приложение `cp` с фигурными скобками и `2>/dev/null`** скрывало ошибки; часть отчётов не скопировалась с первого раза.
12. **Незакоммиченные изменения блокируют `git pull --rebase`:** push проходит, rebase нет. Нужно коммитить или stash.
13. **Perplexity и русский отчёт не смогли подтвердить спрос;** все баллы ниш там ESTIMATE. Измерение только у OpenCode.

---

## 5.8 Ваши открытые решения и задачи

1. **Подтвердить нишу:** история искусства и материальная культура (пилот) + ISS второй трек.
2. **Раскрытие синтетического голоса** и формулировка в описании (чек-лист в `packaging`).
3. **Эмблемы NASA:** в клипах «Earth from the Space Station» водяной знак с эмблемой: кадрировать (сделано в ISS v2 по отчёту Kilo, проверить глазами).
4. **Просмотр кадров** на людей и логотипы (особенно ISS v2, 25 сцен).
5. **Просмотр ИИ-картинок G1:** годятся ли как подложки; без решения ИИ-картинки не масштабируем.
6. **Родитель/AdSense:** отложено. Письмо в архив NASA (текст в `FOOTAGE_QUALITY.md`, подпись ваша).
7. **Ключ NASA API:** получить на api.nasa.gov, положить в Codespaces Secret, не в чат.
8. **Закоммитить `LICENSE_EVIDENCE.md`** и сохранить отчёты OpenCode в `docs/openmontage/audit/demand/` (команды в 5.9).
9. **Диск:** освободить место, сейчас 2,1 ГБ.
10. **Независимое ревью:** новая сессия без доступа к нашим отчётам по `REVIEW_PACK.md`, только чтение.
11. **Первая публикация:** вручную, непубличным видео в Studio, с аккаунта родителя/опекуна или своего без монетизации; сначала Shorts, потом длинное.

---

## 5.9 Что делать дальше (порядок)

1. Сохранить отчёты OpenCode (из корня репозитория, когда Kilo на паузе):
```bash
cd /workspaces/OpenMontage
mkdir -p docs/openmontage/audit/demand
cp youtube-niche-finder/reports/{illustrated-*,history-*,niche-rediscovery*,rediscover-*,niche-pitfalls*,apollo*,a4-*,b6-*,t*-*,OZ_SUMMARY.md,A_SUMMARY.md,B_SUMMARY.md} docs/openmontage/audit/demand/ 2>/dev/null; ls docs/openmontage/audit/demand | wc -l
git add docs/openmontage/audit/demand docs/openmontage/image_gen/LICENSE_EVIDENCE.md
git commit -m "docs: save OpenCode illustrated-niche and rediscovery reports; license evidence"
git pull --rebase origin factory/business-documentary-pilot && git push origin factory/business-documentary-pilot
```
2. Запустить **R (OpenCode)**: `outlier_v2.py`, повторный замер 5 ниш, ИИ-кандидаты, политика, фактпаки для двух пилотных тем, музейный инвентарь (текст в 5A).
3. Запустить **N (Kilo)** по плану ниже (нужна доработка G2: fp16 без bitsandbytes, одна модель за запуск, проверка числа картинок), параллельно собрать ролик «история искусства» по профилю ниши и музейным адаптерам.
4. Вы смотрите ISS v2 и картинки G1, решаете по голосу/эмблемам/подложкам.
5. Независимое ревью, потом выкладка Shorts + длинный ролик непубличным.
6. Метрики Studio (CSV) в `M8` (импорт аналитики), решение GO/HOLD/NO-GO по правилам из русского анализа (14 дней, ~1 000 показов, ≥2 пилота выше медианы когорты).
7. Только после 3 ступеней и устойчивого удержания идти к 15-20 и 40-50 мин.

---

## 5.10 Индекс промптов (кто, что, результат)

| Веха | Кому | Суть | Результат |
|---|---|---|---|
| R1/R2 | Kilo | починка пересборки, озвучка среза | `3d5865b`, `3c0b450` |
| H | Kilo | сценарий CID, покрытие кадров, тесты, обложки, X-15/XB-70 | `6e2a221` |
| (спрос) | OpenCode | замер спроса авиации/CID | DEMAND_SIGNAL_PRESENT, коммит 0a4c184 локально |
| I | Kilo | вторые источники FAA, claim_id resolve, B6, лицензия Kokoro | `16f2b31` |
| J | Kilo | сценарий угла 1, названия, Shorts | заменён (угол 1 WEAK) |
| (pitfalls) | OpenCode | стресс-тест ниши, риски | `niche-pitfalls`: угол 1 WEAK |
| (niche v2) | OpenCode | сравнение 3 ниш (космос/наука/философия) | A STRONG |
| K | Kilo | профиль ниши космос, 10 тем, Artemis | `8e96cda` |
| L | Kilo | venv Kokoro, озвучка Artemis | поглощён в Z |
| Z | Kilo | полная сборка (Z1-Z9), возобновляемая | `579ba4c` |
| T1-T5, T6-T12 | OpenCode | замеры космоса, длинный формат, политика, Apollo | `a943d51` и далее |
| yt-shorts | OpenCode | установка навыка | `31c9bf9` |
| T13-T18, OZ, A, B | OpenCode | Apollo 9/10/11 исследования и фактпаки | отчёты в audit/demand |
| Y, X, W | Kilo | рендер, проверка кадров, ISS | `ab4d9a3`, `cde548d`, `917dd86` |
| G1 | Kilo | SDXL-Lightning на Kaggle, лицензии, QC-гейт | `50faafd` |
| G2+V2 | Kilo | бейкофф моделей + апгрейд ISS | `718baf5`, G2 провален |
| (illustrated) | OpenCode | замер иллюстрированных ниш | B STRONG |
| (history) | OpenCode | подтемы истории | Египет STRONG |
| (rediscovery) | OpenCode | 40 ниш | история искусства STRONG |
| M | Kilo | модули фабрики M1-M9 | `2a52fdf` |
| R | OpenCode | outlier_v2, ИИ-ниши, политика, фактпаки | выдан, ждёт запуска |

Полный текст главных актуальных промптов см. Приложение 5A.

---

## 5.11 Короткий промпт для нового чата (скопировать в Claude/агент)

> Прочитай `OpenMontage_ALL_IN_ONE.md`, особенно Часть 5 (чат 18-20 окт 2026). Контекст: faceless англоязычный YouTube, фабрика в Codespaces (Kilo = `docs/ tools/ scripts/ tests/ .kilo/`; OpenCode = только `youtube-niche-finder/`), бюджет $0, ноль секретов, каждый факт с `claim_id` и источником, права по каждому клипу, QC fail-closed. Текущее: основная ниша для пилота: история искусства и материальная культура (настоящие музейные изображения CC0/PD, ИИ-иллюстрации до 10-15% с меткой «Illustration»); второй трек ISS (HD NASA). Apollo 9 отложен (нет кадров), CID тестовый (320x240), true crime отвергнут, угол «что они на самом деле тестировали» не подтверждён. G2 (сравнение моделей картинок) провален, G1 (SDXL-Lightning) работает, но артефактов много. Не повторять сделанное, не доверять оценкам без измерения, помечать MEASURED/ESTIMATE/UNKNOWN. Проверь `git status`, место на диске (≥800 МБ), `git check-ignore .env`. Монетизация AdSense отложена; синтетический голос и источники раскрываем.

---

# Приложение 5A. Полный текст главных актуальных промптов

## 5A.1 MILESTONE Z (Kilo), полная сборка, возобновляемая

```text
MILESTONE Z (Kilo) - full build, no time limit, resumable.
Scope: docs/, tools/, scripts/, tests/, .kilo/. NEVER touch youtube-niche-finder/ or the owner's .env.example/AGENTS.md. Roles inline: say "inline, not independent". No publishing, no secrets printed, no AI upscaling, no paid routes, no new runtime components, curl -L, max 60 requests per phase.
STATE: keep docs/openmontage/Z_STATE.md. At start read it and RESUME at the first phase not DONE. After each phase: update it, commit only your own paths, git pull --rebase, push non-force. Blocked phase = record exact blocker + owner action, continue with independent phases. Max 2 fix attempts per blocker. Stop everything if free disk < 800 MB. Test-first for code. Never claim anything not observed. Final report max 12 lines.

Z1 VOICE ENV: isolated venv (compatible Python, not system 3.14), pinned kokoro/misaki + CPU torch per HANDOFF_NEW_ACCOUNT.md, weights into gitignored cache. Verify with a 10 s sample, qc.py and finish_audio.
Z2 ARTEMIS DRAFT (3-4 min): synthesize narration, word timestamps, subtitles; build video from HD clips (frame only if <1080p), original graphics with claim_ids, source cards; EDL with a rationale per cut, static cards declared static_by_design; credits.txt; run finish_audio and qc.py with ALL inputs, thresholds unchanged. Commit small artifacts to docs/openmontage/slice/artifacts/, never media. Mark NOT_PUBLISHABLE with reasons.
Z3 ONE-COMMAND PIPELINE (test-first): scripts/run_episode.py <topic_id> chaining: claim ledger check -> script validation -> footage manifest + rights check -> narration -> subtitles -> EDL -> render -> finish_audio -> qc -> package draft. Per-stage checkpoint, resume, idempotency, wall-time and disk logging in stage_checkpoint, fail-closed (any unverified stage = BLOCKED). Tests with fake stages for: resume, failure mid-chain, unknown claim_id, rights unknown, hash mismatch.
Z4 CHAPTER MODE for long-form (test-first): split a script into chapters (<=6 min each), build, QC and checkpoint each chapter separately, then concatenate with crossfades and run a final loudness pass on the FINAL file; per-chapter resume; disk budget check before each chapter. Dry-run on Artemis cut into 2 chapters; then write docs/openmontage/LONGFORM_SPEC.md for 40-50 min: claim count targets, footage-minutes needed vs available per topic, added-value gate per chapter (narration share, original graphics per 90 s, no archive clip >20 s unannotated, still-only <=15 s), step ladder 3-4 -> 8-10 -> 15-20 -> 40-50 min with go/no-go driven by owner's YouTube Studio metrics (no invented thresholds).
Z5 SERIES PLAN: from OpenCode/K reports in docs/openmontage/audit/demand/ and TOPIC probes, write docs/openmontage/SERIES_PLAN.md: 12 topics ranked (space niche), per topic: HD clip count by beat, rights_basis, primary docs reachable, estimated minutes of usable visuals, max feasible length. No demand claims beyond measured data.
Z6 SCRIPTS: write full scripts + claim ledgers for the top 3 topics after Artemis (3-5 min each, two sources per load-bearing claim from NASA/ESA primary pages reachable here; single-source flagged) plus a 45 s Shorts plan each; run claim_ids resolve check.
Z7 PACKAGING: per episode 3 truthful titles, thumbnail text options, 1280x720 PNG thumbnails from own graphics/NASA stills (no emblem, no people), description with chapters and credits block, synthetic-voice disclosure checklist (verify wording on the current official YouTube help page, cite URL, paraphrase).
Z8 INDEPENDENT REVIEW PACK: write docs/openmontage/REVIEW_PACK.md listing exactly which files a fresh session with NO prior chat context should read, plus the paste-ready prompt for a read-only reviewer. Run all EVALS.md tasks, ruff or py_compile, full fast suite with exit codes.
Z9 CLOSE: update OWNER_ACTIONS.md, MASTER_RUN_STATE.md, CHANGELOG.md, LESSONS.md; print stop-Codespace commands.
```

## 5A.2 MILESTONE G1 (Kilo), SDXL-Lightning на Kaggle

```text
MILESTONE G1 (Kilo). Scope: docs/, tools/, scripts/, tests/. NEVER touch youtube-niche-finder/, owner's .env.example/AGENTS.md. Roles inline: say so. No secrets printed (KAGGLE_API_TOKEN: report set yes/no only), no paid routes, no voice cloning, curl -L. Stop if free disk < 800 MB. Commit own paths only, pull --rebase, push non-force. Final report max 12 lines (Status, Commit, Done, Failed, Owner decision, Next action).

0. PREFLIGHT: git status, HEAD, df -h, `[ -n "$KAGGLE_API_TOKEN" ]`, `kaggle kernels list --mine --page-size 5`. If auth fails or the runner kernel cannot enable GPU/internet (phone verification), STOP and report BLOCKED with the exact error and owner action.
1. LICENSE EVIDENCE (docs/openmontage/image_gen/LICENSE_EVIDENCE.md): from the OFFICIAL Hugging Face model cards read license fields and use restrictions for ByteDance/SDXL-Lightning, stabilityai/stable-diffusion-xl-base-1.0 (base model it needs) and black-forest-labs/FLUX.1-schnell. Table: component, license, commercial use, restrictions, evidence URL, retrieved date, UNKNOWN where unstated. Exclude non-commercial (e.g. FLUX.1-dev, SDXL-Turbo). If SDXL-Lightning or its base is not clearly commercial-OK, mark BLOCKED.
2. BRIDGE JOB (test-first for any new code, reuse tools/kaggle_bridge): one GPU job (accelerator NvidiaTeslaT4, internet on), pinned diffusers/torch versions recorded. Generate 10 images 1024x1024 with SDXL-Lightning (4-step) from 10 prompts for NON-photoreal illustration only: abstract orbit-diagram backdrop, stylized cupola window sketch, dark starfield gradient, blueprint-style station schematic, minimal flat-vector Earth curve, etc. No real people, no logos or NASA emblem, no real vehicles presented as photos, no text in the image. Record seed, steps, guidance, model revision per image, seconds per image, peak VRAM, total GPU minutes. If time allows, 4 images with FLUX.1-schnell (only if license evidence is clear) for comparison.
3. OUTPUT: images + manifest.json (sha256, bytes, prompt, seed, params, model, license, generator=AI) downloaded via the bridge, hashes verified, into gitignored projects/image_gen/. Build a contact sheet (ffmpeg tile). Add rights_basis=ai_generated_illustration to the records and a required on-screen label "Illustration" rule in docs/openmontage/image_gen/AI_IMAGE_POLICY.md: max 10-15% of runtime, never presented as real footage, never of real events/people/emblems, synthetic-content disclosure checklist (cite and paraphrase the current official YouTube help page URL).
4. QC GATE (test-first): extend tools/qa/qc.py (or the rights check) so any clip with generator=AI that lacks the "Illustration" label or exceeds the runtime share FAILS. Show red then green, run the fast suite with exit codes.
5. REPORT in docs/openmontage/image_gen/G1_REPORT.md: measured seconds per image, VRAM, GPU minutes, observed quality problems (blur, artifacts, text, anatomy), verdict USEFUL | MARGINAL | NOT_USEFUL for our channel. State what is observed vs assumed.
```

## 5A.3 G2 (бейкофф моделей) — переделанная версия (рекомендация после провала)

```text
MILESTONE G3 (Kilo). Scope docs/, tools/, scripts/, tests/. No secrets, no paid routes. Never loop on Kaggle status: submit, record G3_STATE.md, move on. Commit own paths, pull --rebase (commit or stash first), push non-force, never commit images. Final report max 12 lines.
Context: G2 FAILED (v1: bitsandbytes missing in Kaggle image, 0 images, error swallowed; v2: CPU TypeError and FLUX OOM). Fix design: ONE model per kernel run; fp16 only, no bitsandbytes, no CPU fallback; fail loudly (non-zero exit) if fewer images than prompts; log every exception with traceback to the output.
1. LICENSE: read OFFICIAL cards for Tongyi-MAI/Z-Image-Turbo and black-forest-labs/FLUX.2-klein-4B (license, gating, commercial terms). Disagreeing sources on klein: mark BLOCKED unless explicit.
2. Run Z-Image-Turbo first (T4, internet on, pinned diffusers/torch, fp16, 8 steps) on the SAME 10 specific non-photoreal illustration prompts with fixed seeds as SDXL-Lightning (G1 baseline). Record seconds/image, peak VRAM, GPU minutes. Then, only if license clear and memory fits, FLUX.2-klein-4B.
3. Verify manifest job_id, sha256, bytes. Build one contact sheet per model with neutral names A/B/C and a separate mapping file for blind owner comparison. Write G3_REPORT.md: observed vs assumed, visible artifacts (blur, broken geometry, text, anatomy), verdict USEFUL|MARGINAL|NOT_USEFUL per model. The owner judges visually.
```

## 5A.4 MILESTONE M (Kilo), фабричный поток

```text
MILESTONE M (Kilo) - factory lane, resumable, never idle.
Scope: docs/ tools/ scripts/ tests/ .kilo/. NEVER touch youtube-niche-finder/, owner's .env.example/AGENTS.md. Roles inline. No secrets, no paid routes, no AI upscaling, curl -L, stop if disk <800 MB. Never sleep/poll Kaggle in a loop: submit, record in state file, move on. State: docs/openmontage/M_STATE.md (resume at first phase not DONE). Commit own paths, pull --rebase, push non-force after each phase, never commit media. Test-first for code. Final report max 12 lines.
M1 Finish G2 (image bake-off) and ISS v2 per existing prompts if not done.
M2 AI illustration module: niche-level style bible (palette, line style, prompt templates, seed policy), batch generation through the Kaggle bridge with manifest, auto image QC (blur via Laplacian variance, perceptual-hash duplicates, aspect/size checks, flag text-like artifacts), "Illustration" label overlay, runtime-share gate already in qc.py.
M3 Niche profiles: docs/openmontage/niches/{space_iss,art_history,speculative_science}.yaml (allowed sources, visual mix limits, claim rules, episode templates >=3 structures).
M4 Museum adapters: keyless Met, Smithsonian, Rijksmuseum, National Gallery of Art, Wikimedia; rights check accepts only explicit CC0/public-domain, rejects third-party credit; asset_record with sha256, credit, URL. Tests with recorded fixtures.
M5 Motion variety module: slow pan/zoom with different easing, detail crops, parallax on still images, animated map/timeline cards, chapter cards, subtitle styles; per-segment variation lint (no two consecutive identical moves).
M6 Packaging module: thumbnail generator (own graphics, no emblems/people), titles/description/credits block, disclosure checklist from the official YouTube pages (cite URLs).
M7 Independent review harness: scripts/review_pack.py that bundles only reports + qa_report + ledger for a fresh read-only session; run all EVALS.md tasks.
M8 Analytics import: parse YouTube Studio CSV exports into docs/openmontage/analytics/, compute retention drop points per chapter; no OAuth.
M9 Ops: CI-style fast suite script, portability dry-run on a clean venv, disk/time logging, MASTER_RUN_STATE and OWNER_ACTIONS update. Report in the 12-line format.
```

## 5A.5 MILESTONE R (OpenCode), исследовательский поток

```text
MILESTONE R (OpenCode) - research lane, resumable.
Scope ONLY youtube-niche-finder/. `git check-ignore .env` first; no secrets; no commits. No facts from memory: only retrieved pages with URLs. Label MEASURED (API) or ESTIMATE; no RPM claims. Use scripts/mcp-host.sh if the wrapper fails. State: reports/R_STATE.md. Final report max 12 lines; end with cp commands into docs/openmontage/audit/demand/.
R1 Build scripts/outlier_v2.py (tests first): baseline = median of the channel's last 20 long-form uploads excluding the video; outlier_multiple, views_per_day, uploads playlist instead of search.list; replication = >=3 distinct channels <50k subs with multiple>=5 and views>=30k in 12 months.
R2 Re-measure 5 niches with R1: art history and material culture, space/ISS explainers, illustrated ancient history, geology, deep sea.
R3 AI-ONLY candidates: speculative science and "what if", speculative biology/alien worlds, original fantasy/sci-fi story narration, mythology retellings from public-domain texts, future cities/concept worlds. Per candidate: replication verdict, Shorts share, median length, how many top results use AI imagery, comment sentiment about AI (counts of praise vs complaints, no usernames), template/mass-production signals, 3 closest incumbents.
R4 Policy tracker: official YouTube help pages (inauthentic/reused 1311392, synthetic disclosure 14328491, how content was made 15447836, made-for-kids rules): paraphrase what is required for clearly unrealistic illustrations vs realistic ones; list do/don't for our channel.
R5 For the best two niches from R2/R3: competitor teardown of 5 breakouts (hook, structure, chapters, visual style, cadence), top-comment requests, 10 things to do better.
R6 Fact packs for 2 pilot topics per best niche: 35-45 claims each with source URLs, TWO_SOURCES vs SINGLE_SOURCE, contradictions; museum/archive image inventory (CC0 counts, resolution) for the art niche.
R7 R_SUMMARY.md: ranked niches with n, noise warnings, unknowns and a go/no-go proposal (owner decides).
```

## 5A.6 Промпт для Perplexity (Deep Research)

```text
Act as an independent YouTube strategy analyst. Today is October 20, 2026. Use only verifiable current sources; cite every claim with URL and access date. Label every number VERIFIED / ESTIMATE / UNKNOWN. Cross-check; never rely on one source.

GOAL: find the 10 best FACELESS English-language long-form (8-25 min) YouTube niches for a NEW channel with zero audience, made by one person with AI narration, an original script and licensed or original visuals. Do not limit yourself to a preset list.

HARD CONSTRAINTS
- Budget $0: free/open tools only, no paid footage or APIs.
- Visuals must be legal: public-domain/open-license archives (NASA, Library of Congress, Internet Archive, Wikimedia, museum open-access collections, government sources), original graphics/animation, or clearly labeled stylized AI illustrations. NO fake photoreal AI images of real events or real people. Penalize niches that depend on licensed film clips, sports leagues, celebrities, brands, music, or anything needing paid stock.
- Must comply with current YouTube policies on inauthentic/mass-produced content, reused content, synthetic-content disclosure and advertiser-friendliness (quote key wording briefly with URLs and explain how an AI-assisted faceless channel stays compliant). Penalize niches where audiences visibly reject AI voice or AI images.
- Every factual claim needs a primary source; penalize defamation risk (living people, companies), health/finance/legal advice (AI-persona rules), graphic violence, politics, religion.
- Creator is a minor in Kazakhstan: monetization is deferred; treat as a risk note only.
- Avoid saturated templated AI-slideshow niches unless a clear small-channel breakout pattern exists.

FOR EACH NICHE PROVIDE
1) demand evidence: real example videos with title, channel, date, views, subscribers (views vs channel median);
2) 5+ real examples of channels under 10k subscribers with a long-form video above 50k views in the last 12 months (not Shorts);
3) share of Shorts vs long-form among recent breakouts;
4) visual sourcing: exactly which free legal sources cover 10-20 minutes of visuals per episode, with license pages;
5) evergreen vs time-sensitive; room for an original angle;
6) policy/demonetization/defamation risk;
7) automation fit and factual-error risk;
8) RPM only from named sources with date and method (separate RPM from CPM); otherwise UNKNOWN.

OUTPUT
1. Ranked top-10 table with weighted scores (state weights) and sensitivity analysis.
2. For the top 3: 15 specific video ideas with search intent, primary sources and visual sources, plus an 8-10 chapter episode structure.
3. The 3 riskiest assumptions and a cheap test for each.
4. Contradictions between sources and what could not be verified.
Be skeptical; explicitly say if no niche clearly passes all constraints.
```

## 5A.7 Промпт для ChatGPT (Deep Research / Thinking с поиском)

```text
You are a skeptical business analyst for a solo faceless YouTube operation. Use web search; cite sources with URLs and dates; mark every number MEASURED / ESTIMATE / UNKNOWN.

CONTEXT: One person (minor, Kazakhstan, monetization deferred), $0 budget, English long-form 8-25 min, AI narration, original scripts with a claim-by-claim source ledger, an automated production pipeline (script, TTS, edit, QC). Tested so far: space/aviation history on NASA public-domain footage (demand measured, but archival video is often low-resolution or rights-restricted); illustrated history (ancient Egypt, medieval Europe) shows small-channel breakouts but audiences praise "no AI" hand-drawn art. Rejected: true crime, celebrities, finance advice, health/fitness, company histories (defamation, no footage).

TASK
1. Brainstorm 25 faceless niches not limited to the above, then filter with these gates: legal visuals available for 10-20 min per episode at $0; low defamation/policy risk; evergreen; small-channel breakouts plausible; production can be automated with fact checking.
2. For the 10 survivors give: the angle, 3 sample titles, the exact free legal visual sources (with license pages), the typical competitor profile, and the main failure mode.
3. Score each 1-10 on: visual availability, policy risk, competition, demand evidence, originality room, automation fit. Show weights and what changes under different weights.
4. Name 3 niches where the unfair advantage is our pipeline (verified claims, strict rights tracking, fast production) and explain why competitors cannot copy it cheaply.
5. List what a human must still do by hand and what would make you reject each niche.
6. Output a final shortlist of 5 niches with a one-paragraph test plan each: 3 pilot videos, which metrics from YouTube Studio decide go/no-go (CTR, first-30s retention, average view duration, returning viewers) and which benchmarks are context-dependent.
Do not invent statistics. If evidence is thin, say UNKNOWN and propose a cheap test.
```

## 5A.8 Промпт OpenCode: пересмотр ниш (niche-rediscovery)

```text
TASK (OpenCode). Scope ONLY youtube-niche-finder/. `git check-ignore .env` first; no secrets; no commits. Label numbers MEASURED (API) or ESTIMATE; no RPM or earnings claims. Reuse existing CSVs first; use scripts/mcp-host.sh if the wrapper fails. Final report max 12 lines.
GOAL: find the best FACELESS niche for English long-form (8-25 min) with legal visuals, AI narration, original scripts. Do NOT assume the current niche; rediscover.
1. Candidate generation: take 40 niche/sub-niche seeds across the categories: science explainers, engineering, nature/wildlife (public-domain footage), geography/maps, archaeology, art history, architecture, mythology, philosophy, linguistics, economics-explained, technology history, medicine history, military history (deceased events), mathematics, space, weather/climate, ocean, transport history, music theory, etc.
2. Measurement via YouTube Data API (budget ~60 search calls, cache results): for each seed, last 12 months, English, long-form >=8 min: count videos >50k views from channels <50k subs; Shorts share; duration median; number of near-identical titles (template/mass-production signal); top 3 incumbents. Mark n<5 as NOISE.
3. Visual availability, keyless (curl -L, max 40 requests): for the top 10 seeds count public-domain/open-license video or image items per 5 sample topics on NASA, Internet Archive, Wikimedia Commons, Library of Congress, Smithsonian/Met open access; reject third-party credits and NC/ND; estimate usable minutes per topic.
4. Policy and fact risk: reused/inauthentic content, synthetic disclosure (official YouTube help URLs, paraphrase); flag living persons, health/finance advice, graphic violence.
5. Output reports/niche-rediscovery.md and CSV: ranked top 10 with columns breakouts, n, Shorts share, visual-availability tier A/B/C, risk, verdict STRONG|MIXED|WEAK, plus a noise warning and a list of unknowns. Do not recommend anything without the measured numbers.
```

## 5A.9 Промпт OpenCode: пилот «Древний Египет» (если вернёмся к иллюстрированной истории)

```text
TASK (OpenCode). Scope ONLY youtube-niche-finder/. `git check-ignore .env` first; no secrets; no commits. No facts from memory: only retrieved pages with URLs. Final report max 12 lines.
Pilot brief for "Ancient Egypt" (illustrated-style explainer, 12-18 min, English, faceless).
1. IMAGE INVENTORY (keyless, max 40 requests, curl -L): Met Museum Open Access API, Wikimedia Commons, Library of Congress, Internet Archive, Smithsonian, British Museum open data. For 8 sample topics (pyramid construction, daily life, mummification, Nile and agriculture, pharaohs, hieroglyphs, trade, decline) count images with CC0/public-domain rights and clear credit; record id, URL, license text, resolution. Third-party credit, NC/ND = REJECT. Estimate usable images per topic and whether 12-18 min can be covered with 1 image per 6-10 s plus graphics.
2. FACT PACK: 35-45 candidate claims on one angle chosen from the breakout patterns ("Most X ... Explained" listicle with chapters), each paraphrased with source URL and section, status TWO_SOURCES or SINGLE_SOURCE; primary/academic or museum pages only; contradictions listed.
3. OUTLINE: 8-10 chapters with claim ids, image types and graphics needed; hook; 3 truthful titles.
4. DIFFERENTIATOR: from the comments data, how to answer the "NO AI" preference honestly (real museum images + disclosed illustrations + original script).
Write reports/egypt-pilot-brief.md, claims CSV, image-inventory CSV, and cp commands into docs/openmontage/audit/demand/.
```

## 5A.10 Промпт OpenCode: проверка ниши «история искусства» (следующий шаг)

```text
TASK (OpenCode). Scope ONLY youtube-niche-finder/. `git check-ignore .env` first; no secrets; no commits. No facts from memory: only retrieved pages with URLs. Label MEASURED (API) or ESTIMATE; no RPM or earnings claims. Max ~45 YouTube search calls (reuse rediscover-*.csv/json first; use scripts/mcp-host.sh if the wrapper fails). Final report max 12 lines.
Goal: validate the niche "art history and material culture explained" (English, 12-25 min, faceless, real public-domain artwork images + original graphics).
1. DEMAND: from rediscover data plus new queries list the 9 measured breakouts (title, channel, subs, views, duration, date) and analyse them: style (real artwork vs animation vs hand-drawn), title pattern, chapters, upload cadence, top-comment praise/complaints (counts, no usernames), AI-voice reactions. Add 20 art-history sub-topics (painting techniques, provenance and forgeries, pigments and materials, restoration, medieval manuscripts, ceramics, textiles, architecture, museum mysteries, etc.): per sub-topic top 10 videos, breakouts, Shorts share, n; mark n<5 NOISE.
2. IMAGE INVENTORY (keyless, curl -L, max 40 requests): Met Museum Open Access API, Smithsonian Open Access, Rijksmuseum, National Gallery of Art, Art Institute of Chicago, Cleveland Museum of Art, Wikimedia Commons. For 8 sample topics count objects with explicit CC0/public-domain rights and resolution >= 2000 px; record id, URL, license text, credit. Reject anything without an explicit open-access statement (3D objects photographed, 20th-century works, third-party photo credits). Estimate how many distinct images a 15-minute episode needs (1 per 6-10 s) and whether each topic reaches that.
3. DIFFERENTIATION: what do the breakouts NOT do that our pipeline can (per-claim sources, provenance tables, technique diagrams, detail zooms, timelines, maps)? List 10 concrete things.
4. RISK: attribution rules of each museum, Content ID risk for museum-published reproductions, YouTube reused/inauthentic and synthetic-disclosure pages (official URLs, paraphrase), living-artist and forgery/defamation cases to avoid.
5. Write reports/art-history-niche.md + CSVs: verdict STRONG|MIXED|WEAK with sample sizes, top 5 pilot topics with image counts, unknowns, and cp commands for docs/openmontage/audit/demand/.
```

## 5A.11 Промпт Kilo: ISS и другие эпизоды (шаблон «никогда не простаивать»)

```text
MILESTONE (Kilo) - never idle, parallel work while Kaggle queues.
Scope: docs/, tools/, scripts/, tests/. NEVER touch youtube-niche-finder/, owner's .env.example/AGENTS.md. Roles inline. No secrets, no paid routes, no AI upscaling, no AI-generated photoreal images, curl -L, cap 1.5 GB downloads, stop if disk < 800 MB. Commit own paths only, pull --rebase (commit or stash first), push non-force after each phase, never commit media. Final report max 12 lines.
RULES AGAINST WAITING: never sleep and never loop on `kaggle kernels status`; check status with ONE quick call between work phases. Keep a state file with kernel slug, submit time, last known status, next steps.
Phases: submit GPU job -> in parallel upgrade the episode (more clips, 25-40 scenes with varied crops and speeds, crop out watermark/emblem and document it in edit_decisions.json, animated diagrams with claim_ids, extend the ledger with two primary sources for load-bearing claims, rewrite the script to 6-8 min with claim_ids, re-narrate, rebuild, qc.py with ALL inputs, thresholds unchanged, NOT_PUBLISHABLE with reasons, 12-frame contact sheet) -> when the kernel is COMPLETE fetch output, verify job_id/sha256/bytes, contact sheets with neutral names and mapping file, report with observed vs assumed.
```

## 5A.12 Шаблон перехода между агентами и правила разделения

- Kilo: `docs/ tools/ scripts/ tests/ .kilo/`. OpenCode: только `youtube-niche-finder/`. Передача через ваш `cp` в `docs/openmontage/audit/demand/`.
- Не коммитить `youtube-niche-finder/` и `.opencode/` в нашу ветку (чужой клон, 403).
- Перед коммитом: `git status --short | head`; не добавлять чужие правки; `git add <paths>`, никогда `git add -A`.
- После каждой вехи: коммит своих путей, `git pull --rebase`, push non-force, итоговый отчёт ≤12 строк.
- Промпты вставлять в окно агента, не в bash-терминал.
- По окончании работы: `gh codespace stop -c <имя-codespace>`.

---

*Конец Части 5. Составлено 21 окт 2026 по переписке и скриншотам; независимой проверки репозитория не было.*

================================================================================
# ФАЙЛ: PART6_CHAT_2026-10-21_to_2026-10-22_AI_PHOTO_GENERATION_NICHE.md
================================================================================

# Часть 6. Чат «AI photo generation niche» (21–22 окт 2026)

**Чат:** «AI photo generation niche» · 70 сообщений · создан 2026-10-21T05:11:07.443988Z · последнее обновление 2026-10-22T12:13:00.313292Z.
**Первое сообщение:** «Где мы остановились» + прикреплён файл `OpenMontage_ALL_IN_ONE(1).md` (это Части 1–5 выше).
**Что включено ниже:** сводка чата, затем полная переписка по порядку: ваши сообщения, ответы Claude, текст всех приложенных документов, запросы и источники веб-поиска, полный текст созданного `FACTORY_100_SPEC.md`. Скриншоты и фото (13 шт.) в текстовом файле показаны пометками `[изображение]`; их содержимое видно только по ответам Claude на них. Внутренние «размышления» модели и служебные системные вставки не включены.

## 6.0 Сводка чата (составлена автоматически системой по этому чату)

**Conversation overview**

The person is building "OpenMontage," a solo, $0-budget faceless YouTube documentary channel project, operating from Codespaces and coordinating two coding agents (Kilo and OpenCode) across separate repository scopes to avoid file conflicts. The conversation picked up mid-project, reviewing prior milestones (project is a minor; monetization/AdSense is deliberately deferred). Claude provided a status recap showing the factory pipeline roughly 65-70% built but with zero published videos and three unpublishable drafts (CID, Apollo 9, ISS). Claude proposed a "speculative evolution / alien ecosystems" niche (AI-illustrated creatures with fixed anatomy specs, claim-sourced science) after the person rejected a prior "art history" suggestion and instead asked for prompts to research any viable all-AI-image niche via Perplexity and ChatGPT Deep Research. Claude wrote dual research prompts, then synthesized the conflicting-but-overlapping results to recommend the speculative-evolution niche, which the person approved.

Claude then wrote parallel milestone prompts for Kilo (image generation, style bible, pilot script) and OpenCode (demand measurement via YouTube API, later reassigned to prompt-tooling since quota was exhausted), carefully separating file ownership to prevent overlap. When the person asked for research on best-performing open-weights image models for T4 GPUs, Claude produced another dual Perplexity/ChatGPT prompt, then reconciled results into a shortlist: SDXL Base, Z-Image Turbo, FLUX.2 klein 4B. Claude researched model-specific prompting conventions (SDXL uses structured tags + negative prompts; Z-Image/klein use prose with no negative-prompt support) and built this into subsequent agent instructions. A multi-round bake-off was run (S1 through S7 milestones): Z-Image repeatedly failed (dependency conflicts, then NaN/black images from an fp16/bf16 mismatch) and was marked BLOCKED; SDXL and FLUX.2 klein 4B both completed 10-image runs with recorded speed/VRAM data, packaged into a blind-scoring pack (neutral-ID contact sheets, CSV template, tally script) for the person to judge image quality personally. The person asked whether MiniMax M3.1 Flash was better than the agent model then in use (Nemotron 3.5 Super VL) by benchmarks; Claude searched and found no direct comparable benchmark, advised not to swap mid-milestone, and recommended a controlled side-by-side test instead. The agents later ran milestones on different free models (MiniMax M3.1 Flash, DeepSeek V4.1 Flash) without issues. The person asked Claude to research up-to-date GitHub/image-gen model alternatives; Claude found several candidates (Ideogram 4.0, Boogu-Image-0.1 Turbo, Cosmos3-Super, Sana-Sprint, FLUX.3 klein) but recommended not expanding the active 3-model test until it concluded.

At the person's request, Claude authored a comprehensive `FACTORY_100_SPEC.md` document defining what a fully complete version of the factory pipeline should look like (ten architectural layers, hard rules on budget/secrets/rights/sourcing, role/ownership boundaries, directory layout, build-order milestones F0-F7, and an explicit "definition of 100% done"), explicitly marking agent-reported "current state" claims as unverified. This was handed to the agents; a resulting "F0 reality audit" milestone found 0 of 10 layers fully passing spec (expected, since spec describes the target state), and surfaced five concrete pipeline defects (QC not reading threshold config, claim_id resolution checking only the last ID per line instead of all, EDL command hardcoded to one episode, two failing chapter-mode tests, and a test-collection crash from a nested directory). The person's agents fixed all five with test-first red/green evidence. Throughout, Claude consistently separated "observed/measured" facts from agent self-reports and its own inferences, flagged when agent claims were unverified, caught a timezone/quota-reset time it had stated incorrectly, and repeatedly reminded the person that image-quality and model-choice decisions are the person's to make via blind review, not the agents' or Claude's.

**Tool knowledge**

Claude did not use integrations/MCP tools directly in this conversation; all coordination was done by writing prompts for the person to paste into separate Kilo and OpenCode

---

## 6.1 Полная переписка

### [01] ВЫ · 2026-10-21 05:11 UTC

*[приложен файл OpenMontage_ALL_IN_ONE(1).md — это Части 1–5 выше]*

Где мы остановились

---

### [02] CLAUDE · 2026-10-21 05:11 UTC

**Где остановились (на 21 окт, 10:11):** последняя завершённая веха — **M (Kilo, коммит `2a52fdf`)**, M1–M9 выполнены. Диск 2,1 ГБ (порог 800 МБ). Все статусы взяты из отчётов агентов, независимой проверки репозитория не было.

**Что готово**
- Фабрика как конвейер примерно на 65–70%: права, QC, claim_id, озвучка Kokoro (ONNX), мост на Kaggle с GPU, режим глав, `run_episode.py`.
- Новые модули из M: иллюстрации с меткой «Illustration», музейные адаптеры, разнообразие движения, упаковка, импорт аналитики, review-пакет. На реальном эпизоде они ещё не прогонялись.
- Три черновика, все NOT_PUBLISHABLE: CID (320x240), Apollo 9 (слайдшоу), ISS (HD, но почти один клип, 298 с вместо 6–8 мин).

**Что провалено или не подтверждено**
- **G2** (сравнение моделей картинок): провален, сравнения нет. Причины: нет `bitsandbytes` в образе Kaggle, ошибка проглочена, CPU-откат упал.
- **G1** (SDXL-Lightning): картинки получены, но вы видели много артефактов, вердикт агента USEFUL не подтверждён.
- Apollo 9 как первая тема не прошла (нет пригодных кадров). True crime отвергнут. Угол «что они на самом деле тестировали» не подтвердился.
- Ни одного опубликованного видео, реакции аудитории нет.

**Ниша:** я предложил пилот **«история искусства и материальная культура»** (настоящие музейные изображения CC0/PD, ИИ-иллюстрации до 10–15% с меткой). Вторым треком идёт ISS. **Это ждёт вашего подтверждения.**

**Что сделать сейчас**
1. Закоммитить `docs/openmontage/image_gen/LICENSE_EVIDENCE.md` (он блокирует `git pull --rebase`).
2. Скопировать отчёты OpenCode в `docs/openmontage/audit/demand/` (команды в 5.9 файла), если ещё не сделали.
3. Освободить диск (кэши весов, исходные клипы, промежуточные рендеры).
4. Запустить **R (OpenCode)** и **N/G3 (Kilo)**. Для G3 — одна модель за запуск, fp16 без bitsandbytes, падать при нехватке картинок.
5. Посмотреть ISS v2 и картинки G1, решить по голосу, эмблемам и подложкам.
6. Независимое ревью по `REVIEW_PACK.md` и первая публикация вручную, непубличным видео. AdSense отложен.

Подтверждаете нишу «история искусства» с ISS вторым треком? Если да, дам короткий промпт для запуска.

---

### [03] ВЫ · 2026-10-21 05:20 UTC

Нет нужно искать нишу где можно делать видео только ИИ фото можно на любую тему дай промп для чат гпт, перплексити чтобы искали везде и нашли самый лучший

---

### [04] CLAUDE · 2026-10-21 05:20 UTC

Принято. Важная оговорка: ниша «только ИИ-картинки» самая рискованная по политике YouTube (шаблонные слайдшоу не монетизируются), поэтому я заставил оба промпта проверять именно это. Монетизацию вы отложили, но политика влияет и на охват.

**Промпт для Perplexity (доказательства и реальные каналы)**

```text
Act as an independent YouTube analyst. Today is October 21, 2026. Cite every claim with URL + access date. Label every number VERIFIED / ESTIMATE / UNKNOWN. Cross-check; never rely on one source. If evidence is thin, say UNKNOWN.

GOAL: find the best niche for a NEW faceless English long-form (8-25 min) YouTube channel where ALL visuals are AI-generated images (plus simple motion: pan/zoom, parallax, animated text/maps). Any topic is allowed; do not limit yourself to a preset list.

CONSTRAINTS
- $0 budget: open-weights image models only (e.g. SDXL, Z-Image Turbo, FLUX schnell), AI voice, one person.
- No fake photoreal images of real events or real people; no logos/brands; no news; no health/finance/legal advice; no kids' content.
- Must comply with YouTube's CURRENT policies: inauthentic/mass-produced content, reused content, synthetic-content disclosure, advertiser-friendliness. Quote key wording briefly with official URLs and explain exactly what makes an AI-image channel compliant vs demonetized.
- Creator is a minor; monetization deferred (risk note only).

TASKS
1. Find 15+ niches where channels already succeed mostly with AI images (e.g. speculative science / "what if", sci-fi and fantasy storytelling, mythology, speculative biology, future worlds, historical reconstructions, sleep/ambient explainers, etc.), and niches nobody serves yet.
2. For each: 5+ real channels under 10k subscribers with a long-form video above 50k views in the last 12 months (title, channel, date, views, subs, duration, link). Report Shorts vs long-form share. If you cannot find 5, say so.
3. Audience attitude to AI images: viewer comment sentiment (praise vs complaints, with examples and counts), signs of mass-produced template saturation, any demonetization/removal cases of AI-image channels in 2025-2026 with sources.
4. Evidence of what makes winners different: style consistency, storytelling, voice quality, chapters, cadence.
5. RPM only from named sources with date and method; otherwise UNKNOWN.

OUTPUT: ranked top-10 table with weighted scores (state weights) and sensitivity analysis; for the top 3: 15 video ideas, a chapter structure, the 3 riskiest assumptions with a cheap test each; a contradictions list; and an explicit statement if NO niche clearly passes (then say what is the least bad option and why).
```

**Промпт для ChatGPT (Deep Research / Thinking с поиском)**

```text
You are a skeptical strategist for a solo faceless YouTube operation. Use web search; cite URLs and dates; mark numbers MEASURED / ESTIMATE / UNKNOWN. No invented statistics.

CONTEXT: One person, $0, English long-form 8-25 min, AI narration, automated pipeline (script with per-claim sources, TTS, edit, QC). Visuals must be ONLY AI-generated images (open-weights models on a free T4 GPU, ~4-8 s per image) plus motion effects and animated graphics. Already rejected: true crime, celebrities, finance/health advice, company histories, realistic fake photos of real events. Already tested without success: aviation/space archive footage (low-res, rights issues).

TASK
1. Brainstorm 40 niches/formats that work well with AI images (fiction, speculation, mythology, concept worlds, explainers with illustrated metaphors, history shown as clearly labeled illustrations, bedtime/ambient, educational "what if", etc.).
2. Filter by gates: policy-safe (YouTube inauthentic/reused/synthetic-disclosure rules, check the current official pages), low defamation/factual risk, a consistent visual style is achievable with 100+ images per episode without obvious artifacts, evergreen, small-channel breakouts plausible, production is automatable.
3. For the 10 survivors: the angle, 3 titles, visual style bible (palette, line style, prompt template), how many images per 15 min episode, typical failure modes of AI images (hands, text, geometry) and how to avoid them, 3 closest competitors, why viewers might reject it.
4. Score 1-10: demand evidence, competition/saturation, policy risk, visual feasibility, originality room, automation fit, viewer acceptance of AI visuals. Show weights and a sensitivity analysis.
5. Pick 3 niches where our pipeline gives an unfair advantage (verified claims, consistent style, fast production) and explain why competitors can't copy it cheaply.
6. Final shortlist of 3 with a test plan: 3 pilot videos each, YouTube Studio metrics for go/no-go (CTR, first-30s retention, average view duration, returning viewers), which benchmarks are context-dependent.
Say clearly if no niche passes all gates.
```

Когда оба отчёта придут, пришлите их файлами. Я сверю между собой и с замерами OpenCode (мне нужны только те ниши, которые подтверждены реальными каналами, а не баллами). После выбора дам промпт для OpenCode на проверку через YouTube API и для Kilo на стиль и картинки.

---

### [05] ВЫ · 2026-10-21 05:26 UTC

**Вложение: ai_only_youtube_niche_strategy.md** (58865 байт)

<<<НАЧАЛО ВЛОЖЕНИЯ>>>
# AI-Only Visuals YouTube Strategy: Niche Screen and Pilot Plan

**Research snapshot:** 21 October 2026.  
**Operating constraints:** solo creator; $0 cash budget; English long-form videos, roughly 8–25 minutes; AI narration; automated research/script/TTS/edit/QC pipeline; visuals limited to AI-generated still images, motion effects, and animated graphics; images generated with open-weight models on a free T4-class GPU in roughly 4–8 seconds per successful generation (creator-provided estimate, not independently measured here).

## Executive decision

**No niche passes every gate with certainty.** Several are good *conditional bets*, but actual audience demand, the audience's tolerance for AI stills, and YouTube's treatment of a new channel cannot be established from public research alone. The best test candidates are:

1. **Source-led mythology and folklore field guides** — clearest existing audience signal and an unusually useful fit for claim-by-claim sourcing, but competition is real.
2. **Speculative evolution / alien ecosystem field guides** — excellent fit for AI-created imagery and a clear way to combine real biology with explicitly labelled speculation; smaller demand signals are less certain.
3. **Science-based “what if?” scenarios** — strong format-level audience evidence, but very competitive; win by being unusually transparent about assumptions, sources, and what is speculative.

The score table gives **original anomaly files** and an **original world atlas** the highest modelled operational fit. They are not the top *first tests* because public demand evidence for a new proprietary universe is less direct. This distinction matters: operational fit is not demand.

### The policy line that shapes the strategy

YouTube's official channel monetization policy says that, from **15 July 2025**, its former “repetitious content” policy was renamed **“inauthentic content”** to make clear that repetitive or mass-produced work is ineligible; the policy already required original, authentic content. The guidance names generic template content and image slideshows with little narrative, commentary, or educational value among examples of material that may not monetize. AI use itself is not a blanket ban; the substance and originality of the finished work matter. [Official YouTube Help, policy note dated 15 July 2025; accessed 21 Oct 2026](https://support.google.com/youtube/answer/1311392).

YouTube's current synthetic-content help says disclosure is required for AI-generated or meaningfully altered content that appears realistic, including realistic scenes that did not happen, altered real events/places, and fabricated depictions of real people. It says non-realistic/fantastical content and routine production assistance do not generally need this disclosure; it also says disclosure itself does not limit monetization eligibility. For this operation, **avoid photorealistic fake-event imagery by design**, use clearly illustrated worlds, and answer the upload disclosure question honestly. [Official YouTube Help, accessed 21 Oct 2026](https://support.google.com/youtube/answer/14328491?hl=en-GB).

**Important:** satisfying the synthetic-content disclosure rule does **not** guarantee YPP approval. Monetization review also looks at whether the channel delivers original value and is not mass-produced or repetitive. [Official channel monetization policy](https://support.google.com/youtube/answer/1311392).

## How to read the evidence labels

- **[MEASURED]**: a public counter or an official/publisher-published figure captured on the stated date. Publisher-reported figures are not independently audited unless stated otherwise.
- **[ESTIMATE]**: my score, target, production range, or operational forecast. It is a hypothesis to test, not a platform statistic.
- **[UNKNOWN]**: not verifiable from public sources, or too little data to infer confidently. This includes competitors' CTR, retention, returning viewers, revenue per thousand views, production costs, and whether an AI-only channel will be accepted by a new audience.

The creator-provided “4–8 seconds per image” is treated as a **[USER-PROVIDED ESTIMATE]** and not as a benchmark for every GPU, model, sampler, image size, or queue. At that assumed rate, **100 successful images would take about 6.7–13.3 minutes [ESTIMATE] of raw generation time** before retries, failed generations, prompt setup, downloading, review, and editing. Total accepted-image throughput is **[UNKNOWN]** until measured on the actual pipeline.

---

# 1) Forty format ideas

**KEEP** means it survives the first idea screen as one of the shortlisted formats or a close variant. **CONDITIONAL** means it can work only with clear labelling, sourcing, or a narrow premise. **CUT** means poor fit for the current constraints, excessive factual/policy risk, or likely to look like low-value AI filler.

| # | Niche / format | First screen | Main reason |
|---:|---|---|---|
| 1 | Science-based “what if?” scenarios | KEEP | Strong curiosity hook; assumptions and calculations can be shown as graphics. |
| 2 | Mythology and folklore field guides | KEEP | Public-domain stories and documented variants suit illustrated dossiers. |
| 3 | Speculative evolution / alien ecosystems | KEEP | Image-led by nature; science can anchor the speculation. |
| 4 | Original fictional world atlas | KEEP | Creates reusable places, maps, species, and recurring lore. |
| 5 | Illustrated “how everyday systems work” | KEEP | Diagrams/metaphors reduce dependence on photorealism. |
| 6 | History of ordinary daily life, with labelled illustrations | KEEP / CONDITIONAL | Sources can be strong, but visual details must not be presented as photographic evidence. |
| 7 | Philosophy thought experiments visualized as worlds | KEEP | Original narrative and visual metaphors are achievable. |
| 8 | Original anomaly / cosmic mystery case files | KEEP | Recurring fictional format; must have distinct story substance, not interchangeable templates. |
| 9 | Cozy fantasy bedtime stories | KEEP | Strong image mood; challenge is differentiation and keeping narration genuinely original. |
| 10 | Alternate history / counterfactual timelines | CONDITIONAL | Must mark the branch point and separate known history from invented outcomes. |
| 11 | Comparative mythology: the same motif across cultures | CONDITIONAL | Good research moat; avoid asserting false universal patterns. |
| 12 | Illustrated public-domain epic or myth retellings | CONDITIONAL | Source and edition choices matter; avoid copying modern translations/adaptations. |
| 13 | Mythical-creature field guide | CONDITIONAL | Good visual fit; cite cultural variants and avoid flattening traditions into “monster facts.” |
| 14 | Forgotten inventions and how they worked | CONDITIONAL | Good evergreen topic; requires careful source checking and no fake “archive” visuals. |
| 15 | Historical objects with a documented provenance trail | CONDITIONAL | Source-led but can be narrow; never invent provenance or archaeological context. |
| 16 | Trade routes and historical geography using animated maps | CONDITIONAL | Strong graphics fit; maps and boundaries require source notes. |
| 17 | Ancient food and dining customs | CONDITIONAL | Can be compelling; distinguish textual evidence, archaeology, and reconstruction. |
| 18 | Prehistoric ecosystems and animal behavior | CONDITIONAL | Strong visuals; palaeobiology uncertainties need explicit labels. |
| 19 | Deep-sea biology explainer | CONDITIONAL | Real facts work, but avoid invented “real footage” presentation and sensational claims. |
| 20 | “Could this sci-fi technology work?” | CONDITIONAL | Clear known/plausible/speculative labels; avoid becoming generic futurism. |
| 21 | Fictional cities and speculative architecture | KEEP / CONDITIONAL | Graphics, maps, and constraints are central; strong worldbuilding opportunity. |
| 22 | Future cities and urban systems | CONDITIONAL | Must distinguish forecasts from facts; current planning/politics can date quickly. |
| 23 | Infrastructure explained by visual metaphor | KEEP / CONDITIONAL | Useful and automatable if the metaphor remains accurate. |
| 24 | How the internet, cables, routing, and data centres work | CONDITIONAL | Good visual metaphor fit; source-sensitive technical details. |
| 25 | “One failure chain” engineering explainers | CONDITIONAL | High curiosity; avoid graphic disaster recreation and unsupported blame. |
| 26 | Physics paradoxes as short visual stories | CONDITIONAL | Excellent illustration fit; mathematics and caveats must be checked. |
| 27 | Mathematical paradoxes told as fictional puzzles | CONDITIONAL | Low factual-risk if proof is correct; audience may be narrower. |
| 28 | Ecology, food webs, and ecosystem balance | CONDITIONAL | Strong diagram format; environmental claims must be sourced. |
| 29 | Fictional alien civilizations under physical constraints | KEEP / CONDITIONAL | Good originality; label all civilization claims as invented extrapolation. |
| 30 | “A planet with one extreme rule” worldbuilding | KEEP / CONDITIONAL | Reusable episode engine; must show causal consequences, not just pretty images. |
| 31 | Original cosmic horror stories | CONDITIONAL | Good visual style fit; generic AI narration/monster imagery is a rejection risk. |
| 32 | Liminal-space / uncanny-place fiction | CONDITIONAL | Easy to generate, but highly vulnerable to repetitive slideshow feel. |
| 33 | Sleep-friendly fictional travelogue | CONDITIONAL | Could work as a format within bedtime fiction, but the audio must carry the experience. |
| 34 | Illustrated language evolution and etymology | CONDITIONAL | Needs reputable linguistic sources; avoid folk-etymology myths. |
| 35 | Constructed languages for original cultures | CONDITIONAL | Original IP and repeatability; can become too niche without story stakes. |
| 36 | Philosophy and ethics through moral dilemmas | KEEP / CONDITIONAL | Distinct perspective needed; don't pretend contested arguments have one settled answer. |
| 37 | Cognitive-bias explainers using characters/metaphors | CONDITIONAL | Educational, but avoid mental-health diagnosis or advice framing. |
| 38 | Modern celebrity/real-person alternate lives | CUT | Raises synthetic-depiction, defamation, and misinformation risk; already rejected by brief. |
| 39 | True-crime cases recreated with AI visuals | CUT | Real victims, accusations, and realistic synthetic reconstructions are high-risk; already rejected. |
| 40 | Ambient “AI scenery” with little narrative or educational value | CUT | Easy to mass-produce but weak originality signal, low narrative value, and poor moat. |

---

# 2) The ten conditional survivors in detail

The image counts below are **[ESTIMATE]** for a roughly **15-minute** episode. The goal is not to hit a quota: it is to use enough visual changes to support the narration while avoiding repetitive stills. A still changing roughly every **8–12 seconds [ESTIMATE]** implies around **75–110 distinct visual beats [ESTIMATE]** in a **15-minute [ESTIMATE]** episode. A “beat” can be a new image, crop, pan/zoom, overlay, map, diagram, or a carefully reused establishing image with a different animation—not necessarily a wholly new successful generation each time.

All prompt templates intentionally say **no legible text**. Render labels, dates, legends, UI, map names, equations, and captions in the editor, not inside the image model. Never rely on image generation to produce precise text, hands, mechanical details, scientific charts, or geographically accurate maps.

## A. Science-based “what if?” scenarios

**Angle:** Start with one well-defined change to Earth's environment or physical rules, state the assumptions, work through the causal chain, and separate known physics from inference. Keep it away from personal advice, celebrity scenarios, current political claims, or deceptively realistic disaster images.

**Three title candidates**
- “What If Earth Had Two Moons? The Consequences Nobody Mentions”
- “What If Earth's Day Lasted 48 Hours?”
- “What If Gravity Were Half as Strong? A Physics-Led Thought Experiment”

**Style bible**
- **Palette:** midnight navy, ice cyan, warm amber for causal links, off-white for labels.
- **Line style:** clean editorial illustration; silhouettes; clear light direction; occasional flat vector diagrams.
- **Prompt template:** `Editorial science illustration for a clearly hypothetical educational video, [single consequence/scene], physically plausible environmental cues, simplified readable silhouette, navy/cyan/amber palette, crisp graphic-novel linework, layered composition with empty space for editor-added labels, coherent scale, no text, no watermark, not photorealistic, no disaster-news aesthetic.`
- **Images per episode:** **90–120 [ESTIMATE]** visual beats; use diagram overlays for the causal chain instead of generating every explanatory object.

**Common AI failures and prevention**
- Gravity/scale looks wrong: define one scale reference per scene and use overlays for comparisons.
- Planet/moon geometry changes between shots: reuse a reference composition and maintain a written world-state sheet.
- Generated charts contain gibberish: generate blank axes/backgrounds only; draw numbers and curves as graphics.
- The scenario drifts into a generic disaster montage: require every image to illustrate a specific narrated consequence; reject any image that adds an unsupported claim.

**Closest competitors**
- [What If (Underknown)](https://underknown.com/shows/what-if/) — direct format competitor.
- [Kurzgesagt](https://kurzgesagt.org/what-we-do) — research-first, illustrated science benchmark.
- [RealLifeLore](https://www.youtube.com/@RealLifeLore) — geography and large-scale hypotheticals.

**Why viewers might reject it:** the category is crowded; viewers may expect professional animation or visual calculations rather than stills; the title can promise a bigger answer than a **15-minute [ESTIMATE]** script can deliver. The answer needs to progress through several non-obvious consequences, not merely list obvious effects.

## B. Mythology and folklore field guides

**Angle:** Cover an underexplained figure, creature, ritual, or story variant using primary texts, translations, museum/university sources, and reputable reference works. Make geographical and historical variation explicit. Do not present one source's version as the only “true” version.

**Three title candidates**
- “The Yokai Born From an Ordinary Object: What the Sources Actually Say”
- “Why This Underworld Guide Appears in More Than One Greek Story”
- “The Folklore Creature That Was More Warning Than Monster”

**Style bible**
- **Palette:** parchment cream, ink black, rust red, muted jade.
- **Line style:** illustrated natural-history plates blended with woodcut-inspired shapes; no fake archival photography.
- **Prompt template:** `Museum-quality folklore illustration of [named mythic figure or symbolic scene] as a clearly interpretive drawing, culturally researched clothing and objects, parchment/ink/rust/jade palette, textured hand-inked linework, non-photorealistic, respectful and non-caricatured, uncluttered silhouette, no letters or labels, no watermark.`
- **Images per episode:** **80–110 [ESTIMATE]** beats; an individual creature dossier can reuse one designed silhouette for multiple details, provided the sequence adds information.

**Common AI failures and prevention**
- Cultural blending: include a “source culture + period + version” field in every prompt; do not mix regions to get a more spectacular image.
- Costumes/religious symbols become generic: use source-reference notes and a human approval checklist.
- Creature anatomy changes: generate a canonical front/side silhouette and use it as a reference; favor iconic shapes over intricate joints.
- Image model adds random writing: never ask it to make a scroll with readable text; add labels in the edit.

**Closest competitors**
- [Mythology & Fiction Explained](https://www.youtube.com/@MythologyFictionExplained) — direct folklore coverage.
- [Overly Sarcastic Productions](https://www.overlysarcasticproductions.com/what-we-do) — mythology, literature, history, and humour.
- [The Exploring Series](https://www.youtube.com/@TheExploringSeries) — lore-heavy long-form explanations and mythology playlists.

**Why viewers might reject it:** viewers who know the tradition may spot false details; a slow catalogue of names can feel like an audiobook over portraits; some stories are culturally sensitive. Build each episode around a question, conflict, or surprising source comparison—not a listicle alone.

**Demand evidence:** Third-party channel tracker vidIQ showed Mythology & Fiction Explained at about **1.55 million subscribers [MEASURED as a third-party counter snapshot, 19 Aug 2026; rounded]** and roughly **155.49 million lifetime views [MEASURED as a third-party counter snapshot, 19 Aug 2026]**. These are public-counter observations, not a forecast for a new channel. [vidIQ channel snapshot](https://vidiq.com/youtube-stats/channel/UCH4Bz5Swatl5iHSuCT_Hlxg/), snapshot dated 19 Aug 2026 in its page metadata.

## C. Speculative evolution / alien ecosystem field guides

**Angle:** Design an organism or ecosystem from environmental constraints. Begin with a real biological principle (energy, pressure, temperature, locomotion, reproduction, competition), then label the extrapolation. Explain why a design would—or would not—work instead of offering random “cool alien” images.

**Three title candidates**
- “How Could Life Survive Beneath a Frozen Alien Ocean?”
- “A Planet With No Land: The Ecosystem That Could Evolve in an Endless Ocean”
- “Could a Flying Food Web Evolve on a Low-Gravity World?”

**Style bible**
- **Palette:** deep teal, bioluminescent lime, basalt charcoal, pale bone.
- **Line style:** scientific field-guide plates; strong silhouette; restrained surface texture; scale bars added in edit.
- **Prompt template:** `Speculative xenobiology field-guide illustration of [organism], adapted to [environment constraint], explicit functional anatomy, coherent limb count and body plan, deep teal/charcoal with limited bioluminescent accents, natural-history plate composition, non-photorealistic, plain background and room for editor-added scale bar, no text, no watermark.`
- **Images per episode:** **80–115 [ESTIMATE]** beats; use a small number of hero organisms, then vary habitat, scale, food-web diagram, anatomy callouts, and life-stage illustrations.

**Common AI failures and prevention**
- Limbs/mouths mutate: design a labelled written anatomy spec (not in-image text) and keep the same count across prompts; use silhouettes and cropped details.
- “Biology” is just visual decoration: every anatomy feature must map to a sentence explaining function or a clear “speculative” label.
- Scale is inconsistent: add editor-drawn scale bars and one consistent reference organism in different shots.
- The design is too complex to repeat: constrain each species to a stable silhouette, **2–3 [ESTIMATE]** dominant features, and a fixed palette.

**Closest competitors**
- [Curious Archive](https://www.youtube.com/@CuriousArchive) — speculative creatures/ecosystems and worldbuilding.
- [Biblaridion](https://www.youtube.com/@Biblaridion) — speculative evolution and alien-life projects.
- [PBS Eons](https://www.youtube.com/@pbseons) — evidence-led evolution and deep-time biology (more factual than speculative).

**Why viewers might reject it:** scientifically minded viewers can reject hand-wavy biology; fiction viewers can find the explanations too technical; a generic monster slideshow has no reason to earn trust. Give each organism constraints, costs, reproduction, energy source, and an ecological niche. Be explicit about what is an established principle versus the creator's invented extrapolation.

## D. Original fictional world atlas

**Angle:** Build an original world with consistent geography, climate, trade, ecology, technology, and cultural constraints. Each video answers one concrete question about the world rather than presenting disconnected “beautiful fantasy” pictures. This gives you reusable IP and returning-viewer hooks.

**Three title candidates**
- “The City That Can Only Exist for 90 Days a Year”
- “How Would Civilization Work on a Planet With One Continent?”
- “Why the Most Powerful Kingdom in This World Has No Army”

**Style bible**
- **Palette:** slate blue, oxidized copper, bone white, one accent colour for each region.
- **Line style:** atlas/cartographic illustration plus painterly environmental scenes; all labels, map symbols, and borders added in the editor.
- **Prompt template:** `Original fictional atlas illustration of [place/region], world-bible constraints: [climate, materials, technology level, architecture rule], slate/copper/bone palette, coherent architectural language, atmospheric but readable composition, stylized concept art rather than photorealism, no letters, no labels, no watermark.`
- **Images per episode:** **75–105 [ESTIMATE]** beats; map animations, diagrams, and reuses of canonical landmarks can reduce the number of distinct generations.

**Common AI failures and prevention**
- Architecture changes between scenes: maintain a world bible with a few architectural rules and a fixed reference board.
- Maps are geographically nonsensical: generate a blank aesthetic map, then build coastlines, labels, routes, and legends in editor graphics.
- The story invents consequences that contradict earlier lore: use a structured continuity database for geography, resources, distances, governance, and prior canon.
- Images look like unrelated fantasy art: the same colour accents, materials, roofline, symbols, and climate cues must recur in every image.

**Closest competitors**
- [Hello Future Me](https://www.youtube.com/@HelloFutureMe) — worldbuilding craft and systems.
- [Artifexian](https://www.youtube.com/@Artifexian) — maps, cultures, and worldbuilding constraints.
- [Alt Shift X](https://www.youtube.com/@AltShiftX) — lore explanation and cohesive fictional worlds.

**Why viewers might reject it:** unlike an established franchise, a new fictional world has no built-in search demand. Viewers may not care about the setting until the story gives them stakes. Lead with a legible question (“How does this city survive?”), not “Here is my world.”

## E. Illustrated “how everyday systems work” explainers

**Angle:** Explain one invisible system—routing, supply chains, water systems, power grids, standards, queues, or data flow—using an accurate metaphor that is then connected back to the real system. The moat is clarity and research, not image volume.

**Three title candidates**
- “What Actually Happens After You Type a Website Address?”
- “Why One Shipping Container Changed the Shape of the World”
- “How a Power Grid Balances Millions of Moving Demands”

**Style bible**
- **Palette:** cobalt, white, safety orange, graphite.
- **Line style:** modular vector shapes, cutaway diagrams, isometric-but-consistent geometry, simple characters only when needed.
- **Prompt template:** `Stylized editorial system diagram background showing [one real system component as a visual metaphor], cobalt/white/orange/graphite, consistent flat-vector forms, top-down or side cutaway view, clear negative space for editor-added arrows and labels, no text, no numbers, no logos, no watermark.`
- **Images per episode:** **70–100 [ESTIMATE]** beats; animated arrows, paths, and callouts should do more explanatory work than constant scene changes.

**Common AI failures and prevention**
- Diagram geometry is wrong: generate atmospheric background plates only; draw all functional connections with vector graphics.
- The metaphor misleads: add a “metaphor ends here” beat and explain the actual mechanism immediately.
- Random brand marks or interface text appear: exclude logos/screens and make all labels in post.
- Long static explanations feel like slides: animate flows, state changes, and before/after comparisons; every diagram should prove one specific sentence.

**Closest competitors**
- [Wendover Productions](https://www.youtube.com/@Wendoverproductions) — systems, logistics, transport, and geography.
- [Practical Engineering](https://www.youtube.com/@PracticalEngineeringChannel) — engineering explanations.
- [The Infographics Show](https://www.youtube.com/@TheInfographicsShow) — broad illustrated explainers and a relevant packaging competitor.

**Why viewers might reject it:** viewers may prefer real demonstrations, diagrams, or expert on-camera credibility; AI art can feel less precise than an engineering drawing. Prioritise vector graphics for the mechanism and AI illustrations only for metaphors, context, or transitions.

## F. History of ordinary life, illustrated and labelled

**Angle:** Focus on one everyday question in a narrow place and period: heating, sleeping, food storage, travel, work, or shopping. Use a source ledger and label visuals as “illustrative reconstruction.” Do not invent “photographs” or imply that a generated scene depicts a documented person or event.

**Three title candidates**
- “What an Ordinary Winter Day Looked Like in a Medieval City”
- “How People Kept Food Before Refrigerators”
- “What Archaeology Can—and Cannot—Tell Us About an Ancient Home”

**Style bible**
- **Palette:** earth ochre, linen, soot brown, faded indigo.
- **Line style:** illustrated reconstruction with visible ink/paint texture; no photorealistic documentary framing.
- **Prompt template:** `Clearly labelled-as-illustration historical reconstruction of [ordinary daily-life scene] in [place and narrow date range], based only on documented objects/materials from the source ledger, earth-ochre/linen/soot/indigo palette, storybook history illustration, no famous real person, no text, no modern objects unless historically appropriate, no watermark.`
- **Images per episode:** **90–125 [ESTIMATE]** beats because objects, rooms, and routines need distinct views.

**Common AI failures and prevention**
- Anachronisms: every prompt inherits a period/place checklist; reject details not supported by a source.
- Generated people look like modern cosplay: show more objects, rooms, food, and silhouettes; use character shots sparingly.
- False precision: use “representative reconstruction” wording and say where the evidence is uncertain.
- Buildings and clothes jump between shots: lock period-specific material and silhouette references.

**Closest competitors**
- [Told in Stone](https://www.youtube.com/@toldinstone) — ancient daily life and material culture.
- [Simple History](https://www.youtube.com/@SimpleHistory) — illustrated history.
- [History Hit](https://www.youtube.com/@HistoryHit) — broad historical documentaries and expert-led history.

**Why viewers might reject it:** historians may reject unsupported reconstructions; general audiences may see “daily life” as low-stakes. Open with a concrete problem or surprise, then explain evidence quality and what remains unknown.

## G. Philosophy thought experiments visualized as worlds

**Angle:** Turn a thought experiment into a tangible visual world, use the story to expose the tension, and end with competing interpretations rather than pretending there is a universally settled answer. Avoid pseudo-therapy or personal mental-health claims.

**Three title candidates**
- “A World Where Nobody Can Lie: Would It Become More Honest?”
- “The City That Remembers Every Choice You Ever Made”
- “If You Could Copy Your Mind, Which Copy Would Be You?”

**Style bible**
- **Palette:** charcoal, ivory, muted violet, a single vivid red or gold accent.
- **Line style:** surreal editorial illustration; clear silhouettes; symbolic compositions; limited recurring character design.
- **Prompt template:** `Surreal philosophical illustration of [thought experiment], one clear visual metaphor, charcoal/ivory/muted-violet palette with one gold accent, editorial graphic-novel linework, emotionally legible but not melodramatic, simple anatomy, no text, no watermark, avoid photorealism.`
- **Images per episode:** **75–100 [ESTIMATE]** beats; reuse a protagonist and motifs to create continuity, not a parade of unrelated images.

**Common AI failures and prevention**
- Abstract scenes become generic: tie each visual to a specific decision, cost, or contradiction.
- Character identity drifts: use a canonical character sheet and references; make faces stylized, not realistic.
- The narration overstates a philosophical position: cite primary texts when applicable and represent counterarguments fairly.
- Slow opening: begin with the dilemma and its consequence before naming the philosopher or theory.

**Closest competitors**
- [Pursuit of Wonder](https://www.youtube.com/@PursuitofWonder) — narrative philosophy and psychological questions.
- [Einzelgänger](https://www.youtube.com/@Einzelganger) — philosophy explained through narrated essays.
- [The School of Life](https://www.youtube.com/@theschooloflifetv) — illustrated philosophy and human behaviour.

**Why viewers might reject it:** the audience may want more rigorous argument than an AI visual essay provides, or may dislike vague “deep” narration. Make the argument concrete, steelman at least one objection, and do not replace reasoning with mood.

## H. Original anomaly / cosmic mystery case files

**Angle:** Build a proprietary fictional universe with a precise incident report, observable rules, limitations, failed hypotheses, and consequences. It should feel like an authored story-world, not cloned SCP entries, stock AI monsters, or an endless template. Do not repurpose SCP text/art unless fully understanding and following its license; creating an original universe is cleaner.

**Three title candidates**
- “Case File 07: The Door That Opens Only in Abandoned Buildings”
- “The Observatory Recorded a Star That Wasn’t There”
- “Every Map of the Town Adds One Street After Midnight”

**Style bible**
- **Palette:** black-green, oxidized grey, warning amber, pale paper.
- **Line style:** stylized archival dossier, schematic line drawings, atmospheric but clearly fictional artwork.
- **Prompt template:** `Original fictional anomaly case-file illustration of [anomaly], internally consistent rules [rule set], black-green/grey/amber palette, restrained graphic-novel or technical-illustration style, ambiguous but readable silhouette, intentional negative space for case labels added in post, no readable text, no real agency insignia, no watermark, not photorealistic.`
- **Images per episode:** **70–100 [ESTIMATE]** beats; use recurring locations and rule diagrams, with new visuals only when the case reveals something new.

**Common AI failures and prevention**
- The anomaly changes properties from scene to scene: define immutable rules and add a continuity check to script and image QC.
- It looks like a derivative of an existing franchise: avoid borrowed acronyms, numbering conventions, logos, iconic monsters, and signature phrasing.
- It becomes a generic horror slideshow: reveal information progressively and make every visual an evidentiary beat in the fictional case.
- Real-world emergency signals create confusion: no fake news lower-thirds, real agency logos, or realistic depictions of current locations/events.

**Closest competitors**
- [SCP Explained](https://www.youtube.com/@SCP) — large-scale anomaly-lore and animation format.
- [The Exploring Series](https://www.youtube.com/@TheExploringSeries) — long-form lore and fictional universe explanations.
- [The Volgun](https://www.youtube.com/@TheVolgun) — narrated anomalous-fiction presentation.

**Why viewers might reject it:** a new universe has no pre-existing lore search demand; viewers may view still art as lower effort than animation; an episodic template may be judged repetitive. The case must vary structurally and have real writing craft. Public demand for SCP-related lore is evidence for the broad appetite, not proof that a new setting will work.

## I. Cozy fantasy bedtime stories

**Angle:** Original low-conflict stories in a consistent fantasy setting with slow movement, soft sound design, limited visual changes, and no jump-scare pacing. This is not just a generic TTS reading; the script, characters, prose, and atmosphere must be original.

**Three title candidates**
- “The Night Train to a Village That Appears Only in Winter”
- “A Quiet Evening at the Last Inn Before the Moonlit Sea”
- “The Lighthouse Keeper Who Collected Lost Constellations”

**Style bible**
- **Palette:** dusk blue, moon silver, warm amber windows, plum shadows.
- **Line style:** soft painterly storybook illustration, low contrast, limited details, gentle haze.
- **Prompt template:** `Calm original fantasy storybook scene of [place/action], dusk-blue and moon-silver palette with warm amber lights, painterly soft edges, low contrast, uncluttered composition, comforting rather than dramatic, consistent world and character references, no text, no watermark, no photorealism.`
- **Images per episode:** **45–75 [ESTIMATE]** beats; each image may remain on screen longer with slow parallax, camera drift, subtle particles, or gentle lighting effects.

**Common AI failures and prevention**
- The visuals are too bright/busy for bedtime: use a low-contrast palette and review at phone brightness.
- Character/place consistency drifts: keep a small canon, recurring character sheet, and limited shot types.
- The narration sounds synthetic or monotonous: test TTS prosody and manually revise sentence length; a natural voice track cannot be assumed from automation alone.
- It resembles interchangeable AI sleep content: a distinctive setting, original prose, and recurring details are necessary.

**Closest competitors**
- [Get Sleepy](https://www.youtube.com/@GetSleepy) — long-form sleep stories.
- [The French Whisperer](https://www.youtube.com/@TheFrenchWhisperer) — calm narrated history and educational sleep content.
- [Sleep Cove](https://www.youtube.com/@SleepCove) — sleep stories and relaxation narration.

**Why viewers might reject it:** people may listen without caring about the visuals, or dislike AI narration/audio artifacts; recommendations may be difficult without a distinctive promise. Retention, returning listeners, audio quality, and repeat sessions matter more than image count.

## J. Alternate history / counterfactual timelines

**Angle:** Pick one clearly defined branch point, keep real history up to that point accurate, and then label every subsequent consequence as a counterfactual scenario. Avoid current elections, living public figures, or fabricated evidence.

**Three title candidates**
- “What If the Printing Press Had Arrived in Europe Much Later?”
- “What If the Mongol Empire Had Fragmented Earlier? A Counterfactual Map”
- “What If One Major Trade Route Had Never Opened?”

**Style bible**
- **Palette:** archival cream, deep blue, brick red, charcoal.
- **Line style:** illustrated historical atlas, schematic maps, non-photorealistic character silhouettes.
- **Prompt template:** `Clearly labelled counterfactual historical illustration of [branch-point scenario], source-accurate material culture only up to [date], cream/blue/brick-red palette, illustrated atlas style rather than fake archival photo, room for editor-added timeline and labels, no text, no watermark, no photorealism.`
- **Images per episode:** **85–115 [ESTIMATE]** beats; map and timeline animation carry the branching logic.

**Common AI failures and prevention**
- Viewers confuse fiction with actual history: show “COUNTERFACTUAL” and the branch point on screen; repeat the label in description and narration.
- The scenario claims too much certainty: give more than one plausible branch when causality is underdetermined.
- Maps create factual errors: draw borders and dates in post from a researched base map or a hand-built schematic.
- Real historical people are depicted inaccurately: make the art plainly illustrative; avoid false quotes and photorealistic deepfakes.

**Closest competitors**
- [AlternateHistoryHub](https://www.youtube.com/@AlternateHistoryHub) — direct counterfactual-history format.
- [Possible History](https://www.youtube.com/@PossibleHistory) — counterfactual and alternate-history scenarios.
- [RealLifeLore](https://www.youtube.com/@RealLifeLore) — geography- and history-led hypotheticals.

**Why viewers might reject it:** historically literate viewers may dislike shallow causality; other viewers may mistake the scenario for fact; politics or national identity can make comments contentious. Strong labels and sourced “known history / invented branch” separation are non-negotiable.

---

# 3) Scorecard and sensitivity analysis

## Method

Scores are **[ESTIMATE]** on a **1–10 scale [ESTIMATE]**, and they are strategic judgments—not measured market statistics. Every criterion is scored so that **10 is favourable**:

- **Demand evidence**: public evidence that comparable formats have audiences, not proof of demand for a new channel.
- **Competition / saturation**: **10 = more whitespace / less saturation**; **1 = heavily contested**.
- **Policy and factual risk**: **10 = lower risk** when executed as specified.
- **Visual feasibility**: style consistency and ability to fill a full episode with AI stills/graphics.
- **Originality room**: scope to create a distinct angle/world/style.
- **Automation fit**: ease of turning research, script, images, narration, edit, and QC into a repeatable workflow without generic output.
- **AI-visual acceptance**: likelihood that still illustrations feel natural for the format; **[UNKNOWN]** until tested with actual viewers.

### Weights

| Criterion | Weight |
|---|---:|
| Demand evidence | **20% [ESTIMATE]** |
| Competition / saturation | **15% [ESTIMATE]** |
| Policy / factual risk | **15% [ESTIMATE]** |
| Visual feasibility | **15% [ESTIMATE]** |
| Originality room | **10% [ESTIMATE]** |
| Automation fit | **15% [ESTIMATE]** |
| Acceptance of AI visuals | **10% [ESTIMATE]** |
| **Total** | **100% [ESTIMATE]** |

### Scores

All cell ratings and the weighted total below are **[ESTIMATE]**. “Comp.” is favourable competition/whitespace, so a higher score means less saturation.

| Niche | Demand | Comp. | Low risk | Visual | Originality | Automation | AI acceptance | Weighted total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Original anomaly / cosmic mystery files | 7 | 6 | 9 | 9 | 10 | 9 | 9 | **8.25** |
| Original fictional world atlas | 6 | 7 | 10 | 9 | 10 | 8 | 9 | **8.20** |
| Speculative evolution / alien ecosystems | 7 | 7 | 9 | 9 | 9 | 8 | 9 | **8.15** |
| Cozy fantasy bedtime stories | 7 | 5 | 10 | 9 | 9 | 8 | 9 | **8.00** |
| Philosophy thought experiments | 7 | 5 | 9 | 9 | 8 | 9 | 8 | **7.80** |
| Illustrated systems explainers | 8 | 4 | 9 | 9 | 7 | 9 | 7 | **7.65** |
| Mythology / folklore field guides | 8 | 5 | 8 | 8 | 8 | 8 | 8 | **7.55** |
| Science-based “what if?” | 9 | 3 | 8 | 8 | 7 | 8 | 8 | **7.35** |
| Alternate history / counterfactuals | 8 | 4 | 6 | 8 | 7 | 8 | 8 | **7.00** |
| History of ordinary life | 7 | 4 | 6 | 8 | 6 | 7 | 7 | **6.45** |

### What the scores do—and do not—say

- The **original anomaly** and **world atlas** formats win on controllability, repeatability, and distinctiveness, but their new-channel demand is **[UNKNOWN]**. Good operational fit can still produce few clicks.
- The **what-if** format has stronger public demand evidence but weaker whitespace, so packaging and differentiated research matter disproportionately.
- **Mythology** is a useful middle ground: proven audience for the broad category, many source-led subtopics, and visual variety without needing a proprietary franchise.
- **History of ordinary life** is lower-ranked because the factual verification burden is high and the reconstruction can be criticized if it looks too certain.

## Sensitivity analysis

Two alternate weight sets test whether the decision is just an artifact of the base weights. All resulting totals are **[ESTIMATE]**.

1. **Demand-heavy model**: demand **35%**, competition **20%**, low risk **10%**, visual feasibility **10%**, originality **5%**, automation **10%**, AI acceptance **10%**. This gives more weight to visible audience evidence and the competitive landscape.
2. **Originality / production-fit model**: demand **10%**, competition **10%**, low risk **15%**, visual feasibility **20%**, originality **20%**, automation **15%**, AI acceptance **10%**. This rewards a distinctive format that a solo AI-image pipeline can execute well.

| Niche | Base model | Demand-heavy | Originality / production-fit |
|---|---:|---:|---:|
| Original anomaly files | 8.25 | 7.75 | 8.70 |
| Original world atlas | 8.20 | 7.60 | 8.70 |
| Speculative evolution | 8.15 | 7.80 | 8.45 |
| Cozy fantasy bedtime | 8.00 | 7.50 | 8.40 |
| Philosophy thought experiments | 7.80 | 7.35 | 8.10 |
| Illustrated systems explainers | 7.65 | 7.35 | 7.80 |
| Mythology / folklore | 7.55 | 7.40 | 7.70 |
| Science-based “what if?” | 7.35 | 7.30 | 7.40 |
| Alternate history | 7.00 | 6.95 | 7.10 |
| History of ordinary life | 6.45 | 6.35 | 6.55 |

**Interpretation:** the fictional formats remain strong when you emphasize originality and production fit. They lose a little ground under demand-heavy weights because public demand for a *new* fictional universe is not directly measurable. That is why the pilot shortlist below intentionally includes both proven categories and one more differentiated visual niche.

---

# 4) Three pipeline advantages—and the limits of each

## Advantage 1: Claim-level source ledger + script audit

For factual niches, store each claim as a row with: claim text, source URL, source type, publication date, relevant passage/page, confidence, counterevidence, wording allowed in narration, and the scene that will visualize it. Automated checks can flag unsupported numbers, source/date mismatches, unqualified causal claims, and scripts that present speculation as fact.

**Where it helps most:** folklore variations, history of daily life, science-based what-if, and speculative evolution. The pipeline can automatically create a “known / inference / speculation” structure and make sourcing visible without turning every video into a bibliography reading.

**Why competitors may not copy it cheaply:** the code is not a moat; another creator can implement a ledger. The compounding asset is the curated source database, annotation rules, reliable fact-checking, and a track record of corrections. This advantage is only durable if quality control is real, not a script-generated list of links.

## Advantage 2: Consistent art direction as data, not ad-hoc prompts

Create a visual bible for each series: palettes, silhouette rules, camera angles, material language, character/creature sheets, background motifs, scale references, and negative prompts. Save canonical reference images and re-use model reference features where available. Lock the intended shot type before generating; don't ask the model to invent a new composition in every scene.

Automated QC should flag: duplicated images, inconsistent species anatomy, changed costume/materials, wrong aspect ratio, text-like artifacts, extra limbs, and scenes that do not match the narration. A human approval pass remains important. **[UNKNOWN]** how many retries the particular free GPU environment will need; do not assume the nominal **4–8 seconds per image [USER-PROVIDED ESTIMATE]** equals the accepted-image production time.

**Why competitors may not copy it cheaply:** prompts are easy to copy; a tested style system plus a library of approved recurring assets, negative examples, and stable series design takes sustained iteration. It's an operational advantage, not a permanent technical barrier.

## Advantage 3: Fast “constraint → consequence → visual proof” production

Each episode starts with a structured premise:

1. What is known or sourced?
2. What single assumption/branch point changes?
3. What consequences follow, and through what mechanism?
4. Which image or animated graphic proves each step?
5. What remains uncertain?

This reduces empty images and generic narration. For speculative biology it means environment → available energy → body plan → behavior → food web; for what-if science it means baseline → changed variable → first-order effects → second-order effects; for mythology it means source version → motive/conflict → variant comparison → why interpretation differs.

**Why competitors may not copy it cheaply:** the framework itself is simple, but consistently connecting claims to useful visuals and editing the result for narrative clarity is work. If every video uses the same opening, same cadence, same generic montage, and same conclusion, the production system becomes the exact mass-produced look YouTube's inauthentic-content guidance warns about.

**Skeptical note:** there is no true moat in “AI images + AI voice + automated edit.” The durable assets are original writing, a recognisable visual language, a searchable source/continuity database, and viewers who return for the creator's point of view.

---

# 5) Final shortlist and nine-pilot test plan

## Shortlist rationale

### Pilot A — Source-led mythology and folklore
Best for a test where real category demand has visible evidence, but the differentiation must be source depth, cultural specificity, and clear separation between documented tradition and interpretation.

### Pilot B — Speculative evolution / alien ecosystems
Best fit for the image-generation pipeline: visual change is inherent to the subject, and a consistent illustrated style feels more natural than attempting realistic fake footage. The scientific constraint framework differentiates it from random creature galleries.

### Pilot C — Science-based “what if?”
Best format-level demand signal, but the toughest competitive environment of these three. Test whether a transparent, source-led approach earns clicks and retention without relying on fake photorealism.

**Testing architecture:** for cleanest audience signals, use a separate channel per niche for the pilot period. Three unrelated content promises on one new channel can make returning-viewer data hard to interpret. This adds channel-management overhead, so keep branding and automation templates shared while keeping each channel's audience promise focused. If you choose one unified channel instead, make the umbrella promise explicit (e.g., “science-led illustrated thought experiments, myths, and imagined ecosystems”) and understand that it is a less controlled test.

## Pilot list

### Channel A: Mythology / folklore field guides

1. **“The Yokai Born From an Ordinary Object: What the Sources Actually Say”** — narrow scope; compare source versions; avoid generic monster compilation.  
2. **“Why This Underworld Guide Appears in More Than One Greek Story”** — a source comparison with a clear question; no claim that traditions are identical.  
3. **“The Folklore Creature That Was More Warning Than Monster”** — tie each interpretation to specific source evidence.

### Channel B: Speculative evolution

1. **“How Could Life Survive Beneath a Frozen Alien Ocean?”** — real energy/ecology constraints first, invented ecosystem clearly labelled.  
2. **“A Planet With No Land: The Ecosystem That Could Evolve in an Endless Ocean”** — one strong visual premise and a food-web payoff.  
3. **“Could a Flying Food Web Evolve on a Low-Gravity World?”** — set gravity, atmosphere, energy, and flight assumptions explicitly; explain uncertainty.

### Channel C: Science-based “what if?”

1. **“What If Earth Had Two Moons? The Consequences Nobody Mentions”** — build a causal chain instead of merely listing tidal effects.  
2. **“What If Earth's Day Lasted 48 Hours?”** — separate rotational effects, climate effects, and long-term adaptation.  
3. **“What If Gravity Were Half as Strong? A Physics-Led Thought Experiment”** — state which assumptions are held constant; label the scenario as hypothetical.

All nine pilots should use the same production controls: target length **12–16 minutes [ESTIMATE]**, source ledger, coherent art bible, no text generated inside images, visual QC, captions, a clean first **30 seconds [MEASURED POLICY METRIC DEFINITION]**, and no long generic intro. “MEASURED” here refers to YouTube's defined intro metric: the share of viewers still watching after the first **30 seconds [MEASURED platform metric definition]**—not to any predicted retention result.

## YouTube Studio go / no-go criteria

These are proposed operating thresholds, not published universal standards. All target values are **[ESTIMATE]**. YouTube explicitly says CTR varies by topic, audience, and traffic source; half of channels/videos can fall anywhere in the **2%–10% [MEASURED official aggregate range, YouTube Help accessed 21 Oct 2026]** band. It also warns against making decisions with too little data. Compare like with like and use your own channel's similar-length videos when enough history exists. [YouTube CTR FAQ](https://support.google.com/youtube/answer/7628154?hl=en-AU).

| Metric | Green / continue testing | Yellow / revise | Red / reconsider | Notes |
|---|---|---|---|---|
| **Impressions CTR** | **5%+ [ESTIMATE]** after at least **1,000 impressions [ESTIMATE]** per pilot | **3%–5% [ESTIMATE]** | **Below 3% [ESTIMATE]** after sufficient impressions | Context-dependent by Browse/Search/Suggested, niche, thumbnail, and impression scale. Do not interpret tiny samples as a verdict. |
| **First-30-second retention** | **60%+ [ESTIMATE]** | **50%–60% [ESTIMATE]** | **Below 50% [ESTIMATE]** across the pilots | YouTube highlights intros and says **50%+ [MEASURED official guidance threshold in a Studio tips page]** can appear in “above typical intros”; still compare with similar-length videos and actual graph shape. [YouTube retention help](https://support.google.com/youtube/answer/9314415). |
| **Average view duration (AVD)** | **4:30+ [ESTIMATE]** on a **15-minute [ESTIMATE]** episode (about **30% [ESTIMATE]** viewed) | **3:00–4:30 [ESTIMATE]** | **Below 3:00 [ESTIMATE]** | This is a working threshold, not an official benchmark. Compare at similar duration and inspect dips, rewatch spikes, and whether the promised payoff arrives too late. |
| **Returning viewers** | Clear upward direction from pilot **1 to 3 [ESTIMATE]**, plus recognizable repeat viewers/comments | Some repeat audience but no clear direction | No evidence of return after all **3 pilots [ESTIMATE]** *and* weak retention | Numeric cutoffs are **[UNKNOWN]** until the channel has enough active viewers; tiny-channel returning-viewer data is too noisy for a hard percentage target. Treat it as directional, not a single-number gate. |
| **Demand / reach** | At least one pilot earns materially more impressions/views than the channel's other pilots without worse retention | Views and retention are similar across pilots | All pilots remain low-impression and no clear audience signal | Public stats cannot tell you whether a new channel will be recommended. If reach is tiny, topic demand remains **[UNKNOWN]**, not automatically “bad.” |

### Practical decision rule

- **Continue a niche** if at least **2 of its 3 pilots [ESTIMATE]** meet the CTR and first-30-second retention green/yellow bands and the median AVD is not red.
- **Revise before killing** if CTR is strong but retention weak: likely mismatch between title/thumbnail and opening, or the answer arrives too late.
- **Revise packaging first** if retention is decent but CTR is weak: test a clearer premise and a thumbnail with one focal subject, not more visual clutter.
- **Pause the niche** if all three pilots have weak CTR *and* weak retention after enough impressions, and comments show little desire for another episode.
- **Do not claim a breakout** from one outlier alone. Check whether the format repeats across the next upload, whether the traffic source changed, and whether returning viewers grow.

The exact green/red thresholds are intentionally provisional. YouTube itself recommends comparing retention with other videos of similar length and cautions that CTR is affected by audience and traffic source. [Audience-retention help](https://support.google.com/youtube/answer/9314415) and [CTR FAQ](https://support.google.com/youtube/answer/7628154?hl=en-AU), accessed 21 Oct 2026.

---

# 6) Recommended production guardrails

1. **Source gate before script:** every factual claim has a source and confidence tag; if no source exists, rewrite as opinion, remove it, or label it as speculation.
2. **Script gate before images:** each scene has one job (claim, emotional beat, example, transition, or visual proof). If a scene does not serve the story, remove it.
3. **Visual gate:** no generated text; avoid close-up hands and intricate machinery unless essential; prefer clear silhouettes; use editing graphics for numbers, arrows, maps, and labels.
4. **Continuity gate:** species, characters, world geography, clothing, architectural materials, and colour palette must match the visual bible.
5. **Originality gate:** each episode must have a unique question, meaningful narrative progression, specific reasoning, and a non-interchangeable conclusion. A common intro/outro is fine; a common script skeleton that produces substantially interchangeable episodes is not.
6. **Disclosure gate:** if an image or scene is photorealistic and could mislead viewers about an actual person, place, event, or realistic occurrence, use YouTube's disclosure setting. The better production choice under this brief is to keep imagery unmistakably illustrative.
7. **Rights gate:** use original writing and generated art; when relying on public-domain myth/literature, the underlying story may be old but translations, commentary, illustrations, editions, and modern adaptations can still be protected. Keep a source/license record.
8. **Human QC gate:** automation can flag obvious errors but cannot reliably judge cultural sensitivity, narrative satisfaction, factual nuance, or whether an image subtly claims something unsupported. Keep a final human pass.

## Final conclusion

A solo creator can plausibly build a differentiated AI-image long-form channel, but **there is no guaranteed niche and none clears every gate before testing**. The weakest plan is “generate lots of images, narrate generic text, publish at scale.” That is exactly where both audience rejection and the inauthentic-content policy risk compound. The strongest plan is a small, highly recognizable series where each episode has a sourced question, a distinctive visual system, and a payoff viewers cannot get from a generic AI slideshow.

**Recommended order for the first test:** mythology/folklore (best evidence for audience demand), speculative evolution (best visual-production fit), then science-based what-if (strong demand but heavy competition). Keep original anomaly files/world atlas as second-wave options if you discover that viewers respond more strongly to recurring fictional worlds than sourced topics.

---

# Source log

All pages accessed **21 October 2026**, except where a publication/snapshot date is explicitly noted.

1. **YouTube channel monetization policies** — official guidance; note dated **15 July 2025** renamed repetitious content to inauthentic content and clarified mass-produced/repetitive output. https://support.google.com/youtube/answer/1311392
2. **Disclosing use of GenAI content** — official disclosure rules for realistic synthetic content; explains non-realistic/fantastical content, upload disclosure, and that disclosure itself does not restrict monetization eligibility. https://support.google.com/youtube/answer/14328491?hl=en-GB
3. **Impressions & click-through-rate FAQs** — official CTR context; reports an aggregate **2%–10%** range for half of channels/videos and stresses source/audience variation. https://support.google.com/youtube/answer/7628154?hl=en-AU
4. **Measure key moments for audience retention** — official definition of intro retention after the first **30 seconds**, comparison with similar-length videos, and interpretation of dips/spikes. https://support.google.com/youtube/answer/9314415
5. **Content tab analytics tips** — official tips page with a **50%+** first-30-second example for “above typical intros.” https://support.google.com/youtube/answer/12942217
6. **What If (Underknown)** — producer's own format page. It reports **140 million average monthly watched minutes**, **9 billion watched minutes**, and **45 million followers/subscribers across platforms**, describing this as a snapshot associated with **June 2022**. These are **[MEASURED—publisher-reported, not independently audited]** format-level signals, not current channel forecasts. The page does not clearly date every “by the numbers” figure; for the undated figures, the observation date is **[UNKNOWN]**, so treat them only as category-level evidence, not current demand. https://underknown.com/shows/what-if/
7. **Kurzgesagt: What we do** — official description of research-led science storytelling, sourcesheets, visual metaphors, and illustration process. https://kurzgesagt.org/what-we-do
8. **Mythology & Fiction Explained — vidIQ stats page** — third-party public channel snapshot; page metadata shows update **19 August 2026**. Subscriber and total-view figures are rounded third-party counter values, not a demand forecast. https://vidiq.com/youtube-stats/channel/UCH4Bz5Swatl5iHSuCT_Hlxg/
9. **Overly Sarcastic Productions — What we do** — official channel mission and coverage of mythology, literature, and history. https://www.overlysarcasticproductions.com/what-we-do
10. **SCP Explained — public channel stats (third-party)** — illustrates the existing market for lore/anomaly explainers, but does not establish demand for a new proprietary fictional universe. https://open.subsub.io/channels/scp/view
11. **Get Sleepy video page** — an example of long-form narrated sleep-story programming; public views change over time and are not used as a quantitative forecast here. https://www.youtube.com/watch?v=xu84bbTu7ak

<<<КОНЕЦ ВЛОЖЕНИЯ>>>

*[приложен файл: DOC-20261021-WA0061.pdf]*

---

### [06] CLAUDE · 2026-10-21 05:26 UTC

**Оба отчёта сходятся: ни одна ниша не проходит все гейты, но выбор у них почти совпадает.** Оговорка: ни один отчёт не нашёл реальных каналов с 50k+ просмотров у малых каналов (Perplexity прямо пишет UNKNOWN). Все баллы это оценки, не измерения.

**Где они совпадают**
- Топ: спекулятивная эволюция и инопланетные экосистемы, «что если» с научной базой, вымышленные миры.
- Политика: шаблонные слайдшоу с одинаковой озвучкой не монетизируются. Спасают оригинальный сюжет на каждое видео, движение (параллакс, карты, графики), метка «вымысел» и никаких фотореалистичных фейков реальных людей и событий.
- Монетизацию у вас отложена, так что это риск охвата, а не блокер.

**Где расходятся**
- ChatGPT ставит первым вымышленные «досье аномалий» и атлас мира. Но он сам признаёт: спрос на новую вселенную без готовой аудитории неизвестен.
- Perplexity ставит первым «что если» с серийным миром, вторым спекулятивную биологию.
- ChatGPT рекомендует начать с мифологии (видимая аудитория), но у неё высокая конкуренция и риск культурных ошибок.

**Моё решение: стартовая ниша «спекулятивная эволюция и инопланетные экосистемы»**
- Лучше всего подходит картинкам: можно делать иллюстрированные «полевые справочники», а не псевдо-фото.
- Умеренная конкуренция у обоих отчётов (7/10).
- Научная основа даёт то, чего нет у слайдшоу: ограничения среды, функция каждой анатомической детали, метка «известное / вывод / вымысел».
- Фабрика уже умеет claim_id и QC: утверждения про реальные принципы биологии получат источники.
- Запасной трек: «что если» (спрос высокий, но самая жёсткая конкуренция).

**Что это не снимает**
- Ваши картинки G1 дали много артефактов. Для этой ниши это критично (анатомия существ). G3 (Z-Image Turbo, одна модель за запуск, fp16) теперь важнее всего. Нужны фиксированные силуэты, 2–3 ключевые черты на существо и никакого текста в картинках.
- Спрос по-прежнему не измерен. Нужен замер OpenCode через YouTube API: малые каналы с длинными видео >50k за год в speculative evolution и «what if».
- Тестовый план из отчётов разумен: 3 видео на нишу, решение по CTR, удержанию первых 30 секунд и средней длительности просмотра. Пороги там оценочные.

**Следующий шаг (одним сообщением могу выдать два промпта):**
1. **OpenCode:** замер спроса по двум нишам (speculative evolution, science what-if) плюс мифология как контроль, с пометками MEASURED/NOISE.
2. **Kilo:** G3 (бейкофф Z-Image Turbo), стиль-библия существ и пилотный сценарий «Как жизнь выживет под ледяным океаном» с реестром утверждений.

Подтверждаете эту нишу? Если да, пишу оба промпта.

---

### [07] ВЫ · 2026-10-21 05:51 UTC

Хорошо дай промп для кило и опенкод чтобы строить с двух сторон

---

### [08] CLAUDE · 2026-10-21 05:51 UTC

Два промпта по разделённым папкам (Kilo: `docs/ tools/ scripts/ tests/ .kilo/`, OpenCode: только `youtube-niche-finder/`). Перед запуском закоммитьте `LICENSE_EVIDENCE.md` и освободите диск (сейчас около 2 ГБ).

**Промпт для KILO (Milestone S1: картинки, стиль, пилот)**

```text
MILESTONE S1 (Kilo) - niche "speculative evolution / alien ecosystems", AI stills only. Resumable, never idle.
Scope: docs/ tools/ scripts/ tests/ .kilo/. NEVER touch youtube-niche-finder/, owner's .env.example/AGENTS.md. Roles inline: say "inline, not independent". No secrets printed (KAGGLE_API_TOKEN: yes/no only), no paid routes, no photoreal fake events/people, no text inside images. Stop if free disk < 800 MB (first delete caches/old renders you created, never git or projects/ review files). Commit own paths only (never git add -A), commit or stash LICENSE_EVIDENCE.md first, pull --rebase, push non-force after each phase, never commit media. Test-first for code. Never sleep or loop on Kaggle status: submit, record in docs/openmontage/S1_STATE.md, do other phases, check status with one call between phases. Resume at the first phase not DONE. Final report max 12 lines (Status, Commit, Done, Failed, Owner decision, Next action).

S1-1 IMAGE MODEL (replaces failed G2). ONE model per kernel run, fp16 only, NO bitsandbytes, NO CPU fallback, non-zero exit if images < prompts, full tracebacks saved to output. Read OFFICIAL cards first: Tongyi-MAI/Z-Image-Turbo and black-forest-labs/FLUX.2-klein-4B (license, gating, commercial terms; if sources disagree or terms unclear => BLOCKED for that model). Run Z-Image-Turbo first on 12 fixed prompts with fixed seeds (same prompts for SDXL-Lightning G1 baseline): 4 single-creature silhouettes, 3 habitat scenes, 2 anatomy-detail crops, 2 food-web background plates, 1 planet-surface wide. Record seconds/image, peak VRAM, GPU minutes, seeds, params, model revision. Then FLUX.2-klein only if license clear and memory fits. Verify manifest job_id/sha256/bytes via the bridge.
S1-2 BLIND COMPARISON: contact sheets with neutral names A/B/C and a separate mapping file in projects/ (owner picks by eye). Automatic QC on all images (Laplacian blur, perceptual-hash duplicates, aspect/size, text-like artifacts, limb/anatomy flagged for HUMAN review only: do not claim automatic anatomy judgment). Write docs/openmontage/image_gen/G3_REPORT.md observed vs assumed, verdict USEFUL|MARGINAL|NOT_USEFUL per model.
S1-3 STYLE BIBLE: docs/openmontage/niches/speculative_evolution/STYLE_BIBLE.md and the niche YAML: palette (deep teal, bioluminescent lime, basalt charcoal, pale bone), field-guide plate style, prompt template with "no text, no watermark, not photorealistic", rule: every creature has a written anatomy spec (limb count, 2-3 dominant features) and a canonical silhouette reused across shots; labels, scale bars, arrows, maps, numbers are drawn in the editor, never by the image model; all images get the "Illustration" label rule from AI_IMAGE_POLICY.md (AI share is 100% here: adapt the gate to require a persistent "Speculative illustration" label at start + description, and a motion-variety lint; do not weaken other gates; show red then green tests).
S1-4 PILOT SCRIPT + LEDGER: topic "How could life survive beneath a frozen alien ocean?" 10-12 min. Claim ledger with TWO sources for every real-science claim (reachable NASA/ESA/peer-reviewed or university pages; no facts from memory), each sentence tagged KNOWN / INFERENCE / SPECULATION; invented design choices marked SPECULATION with the constraint that justifies them (energy source, pressure, temperature, locomotion, reproduction). Script with claim_ids, 8-10 chapters, hook, 3 truthful titles. Run the claim_ids resolve check.
S1-5 BUILD (only after S1-1 gives at least one USEFUL model, else stop and report): generate ~80 images for the pilot through the bridge, pick by QC + contact sheets, animated diagrams (energy flow, food web, depth/pressure scale) as editor graphics with claim_ids, motion variety (pan/zoom with differing easing, detail crops, parallax, no two identical moves in a row), Kokoro ONNX narration, subtitles, EDL with rationale per cut, finish_audio, qc.py with ALL inputs, thresholds unchanged. NOT_PUBLISHABLE with reasons. 12-frame contact sheet. Commit small artifacts to docs/openmontage/slice/artifacts/.
S1-6 CLOSE: update OWNER_ACTIONS.md, CHANGELOG.md, LESSONS.md, S1_STATE.md; print stop-Codespace commands.
```

**Промпт для OPENCODE (Milestone S2: замер спроса)**

```text
MILESTONE S2 (OpenCode) - demand measurement. Scope ONLY youtube-niche-finder/. Run `git check-ignore .env` first; no secrets printed; no commits; do not touch docs/ or .kilo/. Use scripts/mcp-host.sh if the wrapper fails. Reuse cached CSVs first. Label every number MEASURED (API) or ESTIMATE; no RPM or earnings claims; n<5 = NOISE. State file reports/S2_STATE.md; resume at first unfinished task; do NOT redo completed tasks. Quota cap ~60 search calls (use uploads playlists where possible). Final report max 12 lines, ending with cp commands into docs/openmontage/audit/demand/.
Niches to measure (English, long-form >=8 min, last 12 months): A speculative evolution / alien ecosystems; B science-based "what if" scenarios; C speculative worldbuilding (fictional worlds/planets); D mythology and folklore explainers (control); E original anomaly/lore case files.
For each niche:
1. Breakouts: videos >50k views from channels <50k subs (also report >=30k views from channels <10k subs). Per video: title, channel, subs, views, duration, date, link, outlier multiple vs the channel's median of its last 20 long uploads (excluding the video, and excluding videos younger than 7 days).
2. Replication: count DISTINCT channels with outlier multiple >=5. Verdict STRONG (>=3 channels), MIXED, WEAK, NOISE.
3. Shorts share among breakouts, median duration, upload cadence of the breakout channels.
4. AI-visuals signal: for the top 5 breakouts per niche, sample up to 100 comments each and COUNT (no usernames) praise vs complaints about AI images/voice; flag whether the channel appears to use AI stills; template/mass-production signals (near-identical titles, same thumbnail layout).
5. Whitespace: top 10 incumbents with subs and median views; 10 subtopics with few long videos but good views (from your data only).
6. Policy snapshot: fetch the current official YouTube help pages (inauthentic/reused content 1311392, synthetic disclosure 14328491), paraphrase what applies to illustrated, clearly fictional AI-image channels; cite URLs and access date.
7. Write reports/s2-demand-summary.md: ranked niches with n, noise warnings, unknowns, and a proposal (owner decides). Do not recommend any niche without measured numbers.
```

Порядок: запускайте оба одновременно. Kilo упрётся в очередь Kaggle, а OpenCode считает спрос в это время. Когда придут отчёты, пришлите скриншоты, сверю результаты замера со стартовой нишей и решим, идти ли дальше или менять.

---

### [09] ВЫ · 2026-10-21 05:56 UTC

Дай промп для перплексити и чат гпт чтобы они нашли самый лучший ИИ модель с качественным генераций фото с маленьком количеством артефактов и быстро генерировать

---

### [10] CLAUDE · 2026-10-21 05:56 UTC

Один промпт на оба сервиса (в ChatGPT включите Deep Research или Thinking с поиском). Он заставляет сравнивать модели именно по нашим условиям: T4 16 ГБ, без bf16, $0, коммерческая лицензия.

```text
Act as a skeptical ML engineer. Today is October 21, 2026. Use web search; cite every claim with URL + access date. Label every number VERIFIED (official card/paper/benchmark with method) / ESTIMATE / UNKNOWN. Never rely on one source; separate vendor claims from independent tests and community reports.

GOAL: find the best open-weights text-to-image model for a solo creator generating 100+ consistent ILLUSTRATIONS per YouTube video (stylized creature/world art, not photoreal fakes of real people), with FEW ARTIFACTS and FAST generation.

HARD CONSTRAINTS
- Hardware: free Kaggle/Colab-class NVIDIA T4 (16 GB VRAM, no bfloat16 support, fp16 only, ~30 GB system RAM, no bitsandbytes preinstalled). Also check Kaggle's dual T4 option.
- $0: open weights, no paid API. License must allow COMMERCIAL use (monetized YouTube). Quote the exact license text/terms from the official model card; flag gated access, revenue caps, output restrictions, and any contradictory sources.
- Must run with diffusers or ComfyUI on fp16 on T4 without OOM (or with documented offload/GGUF/quantized variants and their quality loss).

COMPARE at least 10 models/variants, e.g. Z-Image Turbo, FLUX.2 klein 4B, FLUX.1 schnell, FLUX.1 Krea/dev (license check), SDXL base + LoRAs, SDXL-Lightning, Hyper-SD, SD 3.5 Medium/Large Turbo, Playground v2.5, Kolors, HiDream, Qwen-Image (incl. quantized/GGUF), PixArt-Sigma/Sana, and any newer 2026 releases I did not list.

FOR EACH MODEL REPORT
1. License and commercial-use status (with quote and URL); gating; restrictions.
2. VRAM need in fp16 and in quantized variants; does it fit T4 16 GB; known T4/fp16 problems (NaN/black images, bf16 requirement, OOM).
3. Real measured speed on T4 or similar (seconds per 1024x1024 image, steps, sampler), with source and method; if no T4 data, say UNKNOWN and give nearest GPU data.
4. Artifact profile from independent tests and community reports (not vendor demos): hands/limbs/anatomy errors, broken geometry, text garbling, texture mush, repeated patterns, prompt adherence, style consistency across a series; side-by-side comparisons with links.
5. Consistency tools: seed control, LoRA/style training on T4, IP-Adapter/reference images, ControlNet, img2img for fixed creature silhouettes.
6. Best settings for low artifacts (steps, guidance, resolution, sampler, upscaling/refiner/face-detail fix) as reported by users.
7. Benchmarks: independent leaderboards (Artificial Analysis image arena, LMArena, GenEval, DPG-Bench etc.) with dates and caveats; note which scores are self-reported.

OUTPUT
1. Ranked table of all models with weighted score (state weights: artifact rate 30, T4 feasibility 20, speed 20, license 15, consistency tooling 10, prompt adherence 5) and a sensitivity analysis.
2. Top 3 recommendations for "stylized creature/ecosystem illustration" with an exact reproducible recipe each (library versions, code outline, parameters).
3. A cheap 30-minute test protocol on Kaggle: 12 fixed prompts and seeds, how to count artifacts objectively, how to compare blind.
4. Known pitfalls on Kaggle T4 (fp16 black images, memory, install issues, internet, session limits) and workarounds.
5. Contradictions between sources and everything you could not verify.
Be explicit if the best model for quality does not fit T4, and give the best option that does.
```

Когда придут отчёты, пришлите файлами. Сверю их друг с другом и с провалом G2 (там упали из-за `bitsandbytes` и fp16/OOM), и выберем одну модель для бейкоффа, а не три сразу.

---

### [11] ВЫ · 2026-10-21 06:07 UTC

**Вложение: open_weights_t2i_t4_audit_2026-10-21.md** (70578 байт)

<<<НАЧАЛО ВЛОЖЕНИЯ>>>
# Open-weights text-to-image for a T4-based illustration pipeline
## Skeptical engineering audit — snapshot dated 2026-10-21

**Target workload:** a solo creator generating 100+ stylized creature/world illustrations per long-form YouTube episode, with consistent art direction, zero API spend, commercial/monetized use, and free Kaggle/Colab-class NVIDIA T4 GPUs.

**Bottom line:** there is no proven, universally best model that simultaneously wins on local T4 speed, low artifact rate, series consistency, licensing simplicity, and reproducibility. The strongest *operational* starting point is **SDXL Base plus a self-trained or carefully licensed style LoRA**; the most interesting fast newer candidate is **FLUX.2 klein 4B**, subject to an actual fp16 T4 smoke test; **SDXL Lightning** is the mature speed baseline. **Z-Image Turbo** deserves a head-to-head test, but its published sub-second claim is for an H800-class GPU, not a T4. Treat all rankings below as test-prioritization aids, not as a substitute for a local benchmark.

**Access date for the URLs in this report:** 2026-10-21. Model cards and live leaderboards may change; save the cited cards, license files, and exact commit hashes alongside the experiment before making a production commitment.

---

## Evidence labels and how to read the numbers

- **VERIFIED** — directly stated in an official model card/license, an official paper or official benchmark methodology, or calculated transparently from those values. A vendor speed claim is still labelled VERIFIED *as a vendor claim*, not as independently measured performance.
- **ESTIMATE** — engineering judgement, relative score, suggested starting parameter, or projected behavior not established by a controlled test on the exact setup.
- **UNKNOWN** — I did not find a reproducible measurement/source adequate to support the value. Unknown does not mean impossible; it means do not plan around it without testing.
- **Hardware assumptions supplied in the request:** T4 **16 GB VRAM [VERIFIED for the specified hardware class]**, fp16 only, approximately **30 GB system RAM [ESTIMATE / environment-dependent]**, no preinstalled bitsandbytes. Exact Kaggle resource availability is session- and account-dependent.
- The score table uses ratings **1–10 [ESTIMATE]**. Composite scores are weighted arithmetic scores **out of 10 [ESTIMATE]**, not published benchmarks. License score is about whether the *specific weights* appear viable for monetized use at $0; hard legal gates override the score.
- No reliable, standardized, apples-to-apples set of **seconds per 1024×1024 image on a T4 [UNKNOWN for almost all candidates]** was found. This report does **not** invent those numbers. Model step counts and vendor speed claims are reported separately from measured local time.

## Executive recommendations

1. **Most repeatable production workflow: SDXL Base + your own small style LoRA.** The SDXL ecosystem has mature LoRA, ControlNet, IP-Adapter, img2img, and ComfyUI paths; the base is a practical T4 target. Use the same art bible, style LoRA, seed policy, composition references, and subject sheets. This is the conservative choice when matching hundreds of images matters more than winning a single-image contest. (Official base card and license: https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0; accessed 2026-10-21.)
2. **Best new-model challenger: FLUX.2 klein 4B.** Apache-2.0 and a vendor claim of approximately **8 GB VRAM [VERIFIED as vendor claim, not independent T4 proof]** make it promising. It is not yet safe to promise T4 speed or zero OOM: the official pipeline example uses bf16 in some contexts, while the target T4 should use fp16. Confirm load, first render, finite output, and sustained batch generation on the actual notebook. (Official card: https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/tree/main; vendor statement: https://github.com/black-forest-labs/flux2/blob/main/README.md; accessed 2026-10-21.)
3. **Fast baseline: SDXL Lightning, 4-step checkpoint.** It is a distilled SDXL route with mature ecosystem compatibility. Four steps are the checkpoint’s intended configuration, **not a guarantee of best quality for every illustration**. Compare it with normal SDXL and the 8-step model variant if 4-step outputs show texture or anatomy problems. (Official card: https://huggingface.co/ByteDance/SDXL-Lightning; accessed 2026-10-21.)
4. **Also test Z-Image Turbo.** Apache-2.0 is attractive, and the official Diffusers documentation advertises 8 NFEs and sub-second inference on H800-class hardware. That is not T4 evidence. The official flow has historically shown bf16 examples; for T4, start with the documented Turing/fp16 or quantized Nunchaku path, then check artifacts and numerical finiteness. (https://huggingface.co/Tongyi-MAI/Z-Image-Turbo/tree/main; https://github.com/huggingface/diffusers/blob/main/docs/source/en/api/pipelines/z_image.md; https://huggingface.co/nunchaku-ai/nunchaku-z-image-turbo; accessed 2026-10-21.)

### Models to exclude from a $0 commercial pipeline unless licensing changes

- **FLUX.1 dev and FLUX.1 Krea/dev:** their actual linked FLUX.1 [dev] license is non-commercial, despite potentially confusing output-use wording in model-card text. A separate commercial license may require fees or revenue share. (Krea card: https://github.com/black-forest-labs/flux/blob/main/model_cards/FLUX.1-Krea-dev.md; license: https://github.com/black-forest-labs/flux/blob/main/model_licenses/LICENSE-FLUX1-dev; accessed 2026-10-21.)
- **FLUX.2 klein 9B:** gated and under a non-commercial license, so not a $0 monetization-safe choice as reviewed here. (https://huggingface.co/black-forest-labs/FLUX.2-klein-9B; accessed 2026-10-21.)
- **Qwen-Image 2.1:** the official license explicitly bars commercial use without a separate commercial license. Community reports of difficulty contacting the licensor are not permission to ignore that term. (License: https://github.com/QwenLM/Qwen-Image-2.1/blob/main/LICENSE; community issue: https://github.com/QwenLM/Qwen-Image-2.1/issues/10; accessed 2026-10-21.)
- **Sana weights:** the code and weights have a possible license mismatch; verify the *exact checkpoint’s* license rather than relying on the repository’s Apache-2.0 badge. (Code repo: https://github.com/NVlabs/Sana; candidate weights/license listing: https://huggingface.co/Efficient-Large-Model/SANA1.5_1.6B_1024px_diffusers/blob/main/LICENSE.txt; accessed 2026-10-21.)

---

## Hardware and benchmark reality

### Kaggle / Colab

- Kaggle’s notebook documentation describes bounded sessions, storage, RAM and accelerator availability; these may change. At this snapshot, the documented notebook session ceiling is **12 hours [VERIFIED as documentation, not a guarantee that an individual session will last that long]**, and the commonly documented autosaved notebook storage is **20 GB [VERIFIED as documentation; quotas can change]**. Source: https://www.kaggle.com/docs/notebooks (accessed 2026-10-21).
- Kaggle’s **T4 ×2 [VERIFIED option label]** means two GPU devices, **not one pooled 32 GB VRAM GPU [VERIFIED behavior per Kaggle staff/community product note]**. One model normally lives on one T4 unless the software explicitly shards it; each GPU still has its own **16 GB VRAM [VERIFIED for the T4 hardware class]**. Source: https://www.kaggle.com/product-feedback/361104 (accessed 2026-10-21). Two T4s are useful for independent parallel jobs or supported model parallelism—not for assuming an otherwise-too-large model will load on one card.
- Colab’s official FAQ warns that free GPU access is not guaranteed and usage limits fluctuate without fixed published quotas. Do not use “Colab has a T4 today” as a reproducible hardware guarantee. Source: https://research.google.com/colaboratory/faq.html?authuser=8 (accessed 2026-10-21).
- Check the runtime at execution time, record `torch.__version__`, `torch.version.cuda`, GPU name, VRAM, package versions and the exact model revision. “T4-class” is not a full reproducibility record.

### What counts as a fair speed comparison?

The Artificial Analysis image leaderboard is useful as a *human-preference signal*, but its published speed figures are **provider/API timings**, not local T4 runtimes. Its methodology describes default model settings, square outputs, seed control, downscaling to a common canvas for evaluation, and blind preference judgments. API latency can include provider-side serving and image delivery; it is not equivalent to loading open weights on Kaggle. Sources: https://artificialanalysis.ai/methodology/image and https://artificialanalysis.ai/image/leaderboard/text-to-image/ (accessed 2026-10-21). Scores/ranks are dynamic; record the retrieval date if you use them.

GenEval is a useful reminder that object count, attribute binding, and spatial relations are separate failure modes from general aesthetic quality. GenEval 2 discusses benchmark drift for newer models, so an older benchmark score cannot be treated as a timeless ranking. Sources: https://arxiv.org/abs/2310.11513 (published 2023-10-17; accessed 2026-10-21), https://arxiv.org/abs/2512.16853 (published 2025-12-18; accessed 2026-10-21), https://github.com/facebookresearch/GenEval2 (accessed 2026-10-21). This report does not fabricate a single unified GenEval/DPG score where there is no directly comparable result for all candidates.

---

## Licensing: official terms, practical reading, and the traps

**This section is not legal advice.** “Commercial use allowed” often means *allowed subject to the license*, not “unrestricted.” Review the license at the exact model/revision and preserve it with the production record. Short quotes below are deliberately short; the linked official license is authoritative.

| Model / weights | Official wording or term (short exact quote) | $0 monetized YouTube verdict | Gates / notable restrictions | Source (accessed 2026-10-21) |
|---|---|---|---|---|
| Z-Image Turbo | Official card marks **Apache-2.0**. | **Plausibly allowed**, subject to Apache terms and other applicable law. | Open weights; verify any adapter/dependency license separately. | https://huggingface.co/Tongyi-MAI/Z-Image-Turbo/tree/main |
| FLUX.2 klein 4B | Official card marks **Apache-2.0**. | **Plausibly allowed**, subject to Apache terms. | Vendor claims fit in about **8 GB VRAM [VERIFIED as vendor claim]**; hardware support is not a license term. | https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/tree/main; https://github.com/black-forest-labs/flux2/blob/main/README.md |
| FLUX.1 schnell | Official card marks **Apache-2.0**. | **Plausibly allowed**, subject to Apache terms. | Its full fp16 parameters are too large for a single T4 before runtime overhead; not a licensing issue. | https://github.com/black-forest-labs/flux/blob/main/model_cards/FLUX.1-schnell.md |
| FLUX.1 dev / Krea-dev | The linked license identifies itself as **“FLUX.1 [dev] Non-Commercial License.”** The Krea card directs users to that license. | **Do not use for monetization at $0** unless separately licensed for commercial use. | License defines non-commercial use narrowly; commercial permission may require a separate agreement/fee/royalty/revenue share. Card text about output use must not be read independently of the license. | https://github.com/black-forest-labs/flux/blob/main/model_cards/FLUX.1-Krea-dev.md; https://github.com/black-forest-labs/flux/blob/main/model_licenses/LICENSE-FLUX1-dev |
| FLUX.2 klein 9B | Card lists a **non-commercial license**. | **No** for this use without separate commercial permission. | Gated model access / agreement. | https://huggingface.co/black-forest-labs/FLUX.2-klein-9B |
| SDXL Base | Card identifies **CreativeML Open RAIL++-M**. | **Generally suitable for commercial use subject to the license’s use restrictions**; review the terms. | Usage restrictions remain; check LoRAs/ControlNets separately. | https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0 |
| SDXL Lightning | SDXL-derived weights; card identifies **Open RAIL++-M**. | **Generally suitable subject to license restrictions**, if used with compatible SDXL components. | Preserve checkpoint/card notices; check component license. | https://huggingface.co/ByteDance/SDXL-Lightning |
| Hyper-SD | The repository distributes adapters for multiple bases, including SDXL and FLUX.1-dev-family files. | **Conditional**: choose the SDXL adapter/base path and verify its actual license; do **not** assume FLUX-dev-based artifacts are commercial-safe. | The base model license continues to matter. A repository-wide badge is not enough for mixed distributions. | https://huggingface.co/ByteDance/Hyper-SD; FLUX-dev license above |
| SD 3.5 Medium / Large Turbo | Stability AI Community License provides free commercial use for qualifying users below **US$1 million annual revenue [VERIFIED as license threshold]**; larger entities require an enterprise agreement. | **Conditional yes** for an eligible individual/organization following the terms and any applicable commercial registration process. | Revenue threshold, acceptable-use provisions, and model/product restrictions. | https://huggingface.co/stabilityai/stable-diffusion-3.5-medium; https://huggingface.co/stabilityai/stable-diffusion-3.5-large-turbo; https://stability.ai/news-updates/license-update (published 2024-07-05) |
| Playground v2.5 | License states it is **“free for research and commercial use”** (the full terms add restrictions). | **Conditional yes** for typical channel use; examine the MAU clause and use restrictions. | If image generation/editing is core to a product/business **and** monthly unique users exceed **1 million [VERIFIED license threshold]**, request a separate license; additional model/output restrictions apply. | https://huggingface.co/playgroundai/playground-v2.5-1024px-aesthetic; https://huggingface.co/playgroundai/playground-v2.5-1024px-aesthetic/blob/af20e72b66505bf5f453a3b52e715f6203065777/LICENSE.md |
| Kolors | The official custom license says commercial users should **“please submit questionnaire”**. | **Conditional / do not treat the Apache badge alone as sufficient**; follow the custom license/registration process. | License says questionnaire/registration terms apply and sets an MAU condition; output use and AUP restrictions also apply. | https://github.com/Kwai-Kolors/Kolors/blob/master/MODEL_LICENSE; https://huggingface.co/Kwai-Kolors/Kolors/blob/be5610d7b3811e76de18bd9a43ebd2e7bb0159a9/MODEL_LICENSE |
| HiDream-I1 Full | The transformer is listed as **MIT**, but the assembled pipeline also incorporates separately licensed components, including a Llama-family text encoder. | **Conditional**; assess *all* included components and their terms, not just the transformer license. | Component licenses and their requirements may differ. | https://huggingface.co/HiDream-ai/HiDream-I1-Full/blob/main/README.md |
| Qwen-Image / Qwen-Image-2512 | Official cards identify **Apache-2.0**. | **Plausibly allowed**, subject to Apache terms. | The full-precision model is not a practical single-T4 fit; quantized community repos have their own packaging/code licenses and quality trade-offs. | https://huggingface.co/Qwen/Qwen-Image; https://huggingface.co/Qwen/Qwen-Image-2512 |
| Qwen-Image 2.1 | Official license: **“You shall not use the Materials for any commercial purpose without obtaining a separate commercial license from us.”** | **No** for a $0 monetized channel unless a commercial license is actually granted. | Community claims that a contact address may be difficult to reach do not waive the license. | https://github.com/QwenLM/Qwen-Image-2.1/blob/main/LICENSE; https://github.com/QwenLM/Qwen-Image-2.1/issues/10 |
| PixArt-Sigma | Card identifies **CreativeML Open RAIL++-M**. | **Generally suitable subject to use restrictions**, after checking exact checkpoint/dependencies. | Its text encoder and memory use must be included in T4 planning. | https://huggingface.co/PixArt-alpha/PixArt-Sigma-XL-2-1024-MS |
| Sana 1.5 / Sana Diffusers weights | The code repo and weight license indications are not clear enough here to conclude the same license applies to both. | **UNKNOWN / hold until the exact weights license is verified**. | Do not infer the weights license from the code repository’s badge. | https://github.com/NVlabs/Sana; https://huggingface.co/Efficient-Large-Model/SANA1.5_1.6B_1024px_diffusers/blob/main/LICENSE.txt |
| ERNIE-Image-Turbo | Official model card marks **Apache-2.0**. | **Plausibly allowed**, subject to Apache terms. | Its bf16-centric examples and model size make a T4 fp16 deployment unproven. | https://huggingface.co/baidu/ERNIE-Image-Turbo |

---

## Candidate comparison: hardware, speed, artifacts, controls, and settings

**General rule:** “fits” below distinguishes full fp16 weights loaded on the GPU from *running the pipeline with CPU offload or quantization*. Offload can save VRAM but costs host-to-device transfers and may harm throughput. Diffusers explains model CPU offload versus sequential CPU offload here: https://github.com/huggingface/diffusers/blob/main/docs/source/en/optimization/memory.md (accessed 2026-10-21). Exact peak T4 memory and seconds-per-image remain **UNKNOWN** unless the linked evidence gives a reproducible method.

### Compact model matrix

| Candidate | License / commercial signal | 16 GB T4 fp16 feasibility | Speed evidence for 1024×1024 | Artifact / style-consistency assessment | First setting to test |
|---|---|---|---|---|---|
| **FLUX.2 klein 4B** | Apache-2.0; likely viable. Official vendor says about **8 GB VRAM [VERIFIED as vendor claim]** and generation under **1 second [VERIFIED as vendor claim, not T4 measurement]**. https://github.com/black-forest-labs/flux2/blob/main/README.md (accessed 2026-10-21). | **Likely testable**, fp16 conversion and/or model CPU offload; not independently validated here on T4. | **T4 seconds: UNKNOWN.** Vendor “under 1 second” is not a T4 result. | Strong candidate for prompt adherence and attractive world art, but sequence consistency and defect rate for stylized anatomy are **UNKNOWN until blind test**. Use fixed prompts + reference pipeline; native editing/reference support varies by pipeline revision. | **4 steps [VERIFIED official distilled setting]**, square **1024×1024 [ESTIMATE test canvas]**, `float16`, fixed seed; guidance beginning at **1.0 [ESTIMATE—verify the current card]**. Do smoke test first. |
| **SDXL Base 1.0 + own/verified LoRA** | CreativeML Open RAIL++-M; broadly commercial-usable subject to restrictions. https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0 (accessed 2026-10-21). | **Best-established T4 fit** among these options at **1024×1024 [VERIFIED model target resolution]** with fp16 and sensible VRAM settings; peak memory is hardware/config dependent. | **T4 seconds: UNKNOWN here.** Step count is a configuration, not a published speed claim. | Base model is not magically consistent. Strength is ecosystem: LoRA, ControlNet, IP-Adapter, img2img, ComfyUI, and inpainting can lock look and silhouette. Prompt errors, fused anatomy, and repeated textures still occur. | **28–35 steps [ESTIMATE]**, DPM++ 2M Karras, CFG **5.0–6.5 [ESTIMATE]**, fp16 VAE fix if NaNs; custom style LoRA at a conservative weight. |
| **SDXL Lightning (4-step)** | Open RAIL++-M/SDXL-derived; commercial use subject to restrictions. https://huggingface.co/ByteDance/SDXL-Lightning (accessed 2026-10-21). | **Good T4 fit** by SDXL-family design; monitor peak memory. | **T4 seconds: UNKNOWN.** Official card offers **1/2/4/8-step [VERIFIED checkpoint variants]**; not seconds. | Strong output speed but very-low-step distillation can trade micro-detail, edge structure or prompt adherence; not proven universally worse. Use same seeds against base SDXL. A style LoRA can help if compatible. | **4 steps [VERIFIED intended checkpoint setting]**, EulerDiscreteScheduler with `timestep_spacing="trailing"`, CFG **0 [ESTIMATE/official examples; verify checkpoint-specific card]**. Try 8-step checkpoint if quality matters more than speed. |
| **Z-Image Turbo** | Apache-2.0. https://huggingface.co/Tongyi-MAI/Z-Image-Turbo/tree/main (accessed 2026-10-21). | **Conditional**: official Diffusers has shown bf16 usage; standard fp16 T4 success is not established here. A Nunchaku/Turing path advertises fp16/quant options. https://huggingface.co/nunchaku-ai/nunchaku-z-image-turbo (accessed 2026-10-21). | Official Diffusers describes **8 NFEs [VERIFIED model setting]** and sub-second inference on **H800 [VERIFIED vendor claim, not T4 timing]**. T4 seconds: **UNKNOWN**. https://github.com/huggingface/diffusers/blob/main/docs/source/en/api/pipelines/z_image.md (accessed 2026-10-21). | Community reports mention repetitive composition/subject interpretation, anatomy issues, and blotchy/banded textures. Anecdotal, not a measured incidence rate. Sources dated **2025-11-28**, **2025-12-04**, **2025-12-08 [VERIFIED publication dates in the cited threads]**: https://www.reddit.com/r/StableDiffusion/comments/1p94upi/z_image_flaws/ ; https://www.reddit.com/r/StableDiffusion/comments/1pdr11d/z_image_turbo_can_be_quite_good_except_for_the/ ; https://www.reddit.com/r/StableDiffusion/comments/1ph12vj/some_recent_zimage_gens/ (all accessed 2026-10-21). | Start at **8 steps [VERIFIED official setting]**, guidance **0 [ESTIMATE/official examples]**, deterministic seeds; if fp16 errors, use the documented Turing-friendly Nunchaku path rather than silently changing multiple precision settings. |
| **Hyper-SD (SDXL adapter)** | Adapter repo contains multiple base-model variants; FLUX-dev variants inherit non-commercial issue. Verify exact SDXL path. https://huggingface.co/ByteDance/Hyper-SD (accessed 2026-10-21). | **Good**, if using SDXL base and an SDXL-compatible adapter. | T4 seconds: **UNKNOWN**; intended **1–8-step [VERIFIED family of adapter examples/settings]** speedup is not a measured T4 benchmark. | Faster than full SDXL in intended few-step setup, but can lose fine texture/shape at very low step counts. Adapter strength and scheduler pairing are sensitive; series consistency still benefits from style/silhouette control. | Use SDXL-compatible Hyper-SD with **8 steps [ESTIMATE conservative starting point]** for first quality test; test **4 steps [ESTIMATE]** separately only after settings are correct. Do not mix FLUX-dev adapters into the monetized pipeline without separate terms. |
| **Playground v2.5 1024px** | Custom license: commercial use allowed subject to conditions. MAU gate at **1 million [VERIFIED license threshold]** for image generation/editing as a core product/business. https://huggingface.co/playgroundai/playground-v2.5-1024px-aesthetic/blob/af20e72b66505bf5f453a3b52e715f6203065777/LICENSE.md (accessed 2026-10-21). | **Likely SDXL-like fit**, but actual peak VRAM depends on pipeline. | T4 seconds: **UNKNOWN**. | SDXL-family ecosystem advantage and aesthetic tuning; model-specific stylized creature consistency has no controlled evaluation in the evidence gathered. | **1024×1024 [VERIFIED checkpoint target]**, around **25–35 steps [ESTIMATE]**, CFG and scheduler from the official example first; compare against plain SDXL at matched canvas/seeds. |
| **SD 3.5 Medium** | Stability AI Community License; free commercial use for qualifying entities below **US$1M annual revenue [VERIFIED license term]**, with terms/registration to follow. https://stability.ai/news-updates/license-update (published 2024-07-05; accessed 2026-10-21). | **Borderline/conditional**: full pipeline may need model CPU offload; exact T4 fp16 peak memory not verified. | T4 seconds: **UNKNOWN**. | Can provide strong prompt interpretation, but multiple text encoders increase load time/memory and make operational throughput less predictable. No apples-to-apples artifact incidence for this art workload found. | Start with official Diffusers pipeline, fp16, model CPU offload; use official recommended scheduler/steps before optimizing. Treat any all-GPU memory claim as **UNKNOWN** until measured. |
| **SD 3.5 Large Turbo** | Stability AI Community License; same **US$1M annual revenue [VERIFIED license threshold]** condition. https://huggingface.co/stabilityai/stable-diffusion-3.5-large-turbo (accessed 2026-10-21). | **Not a dependable full-fp16 single-T4 fit**; quant/offload may work at major speed cost. Official SD3 docs note the large text-encoder stack is difficult below **24 GB [VERIFIED official guidance]** even with fp16. https://github.com/huggingface/diffusers/blob/main/docs/source/en/api/pipelines/stable_diffusion/stable_diffusion_3.md (accessed 2026-10-21). | T4 seconds: **UNKNOWN**. | Quality can be competitive but the T4 deployment complexity defeats a “fast, many images for free” objective. No comparable independent defect-rate evidence found. | Don’t put it into the first production shortlist; only test with offload/quantization after smaller options lose blind quality tests. |
| **FLUX.1 schnell** | Apache-2.0. https://github.com/black-forest-labs/flux/blob/main/model_cards/FLUX.1-schnell.md (accessed 2026-10-21). | **Full fp16 weights do not fit**: model card describes **12B parameters [VERIFIED official spec]**; at 2 bytes/parameter this is about **24 GB [VERIFIED transparent arithmetic estimate, excluding other tensors/overhead]**. Quantization or CPU offload needed. | Vendor says **1–4 steps [VERIFIED vendor setting]**; actual T4 seconds **UNKNOWN**. | Strong general image quality, but with quant/offload it may be too slow for 100+ images. Style-consistency tooling less mature/easy than SDXL’s specific LoRA/ControlNet stack. | Test only quantized/offloaded version if available; compare output quality against klein and SDXL before accepting the extra setup cost. |
| **Qwen-Image / Qwen-Image-2512** | Apache-2.0. https://huggingface.co/Qwen/Qwen-Image-2512 (accessed 2026-10-21). | **Full fp16 not viable on a single 16 GB T4**: model card lists **20B parameters [VERIFIED official spec]**, implying approximately **40 GB [VERIFIED arithmetic at 2 bytes/parameter, weights alone]**, before extra encoders/overhead. Quantized/CPU offload may load, but is not verified here. | T4 seconds: **UNKNOWN**; do not map cloud API speed to a local GGUF run. | Potentially strong prompt/text rendering per model/vendor descriptions, but the exact quality loss and artifact profile of quantized GGUF on a T4 is **UNKNOWN**. | Not a first-choice T4 route. If tested, pin the quantization repo and record quant format, bits/group size, offload plan and image quality separately. |
| **Sana 1.5 1.6B** | **Weight license unclear/contradictory**, so commercial pass is **UNKNOWN**. https://github.com/NVlabs/Sana and https://huggingface.co/Efficient-Large-Model/SANA1.5_1.6B_1024px_diffusers/blob/main/LICENSE.txt (accessed 2026-10-21). | Official Sana docs claim **12 GB inference for 1.6B [VERIFIED vendor claim; test hardware is A100]**; 4-bit is claimed under **8 GB [VERIFIED vendor claim]**. T4 fp16 performance is not verified. https://github.com/NVlabs/Sana/blob/main/docs/sana.md (accessed 2026-10-21). | Actual T4 seconds: **UNKNOWN**. Official page says tests were on A100s, not T4. | Likely fast for its size but ecosystem/control coverage and series consistency are less proven here than SDXL. | Don’t monetize until weights license is clear. For technical-only test, use official current recipe, exact dtype compatible with T4, and compare only after license is resolved. |
| **PixArt-Sigma XL-2 1024** | CreativeML Open RAIL++-M. https://huggingface.co/PixArt-alpha/PixArt-Sigma-XL-2-1024-MS (accessed 2026-10-21). | **Possible with offload**, but model plus T5 text encoder increases memory demand. Repo total size is about **21.8 GB [VERIFIED repository listing, not GPU VRAM]**. | T4 seconds: **UNKNOWN**. | Older/open ecosystem, decent candidate for comparison, but no current standard quality test establishes it beats current distilled models for creature art. | Test official defaults at its recommended resolution; enable model offload and log the cost. Use external line-art/pose control if anatomy and composition matter. |
| **Kolors** | Actual custom license calls for commercial questionnaire/registration; repository’s Apache-looking metadata is not enough. https://github.com/Kwai-Kolors/Kolors/blob/master/MODEL_LICENSE (accessed 2026-10-21). | **Uncertain / likely needs quant/offload** for practical T4 fp16 generation; exact peak VRAM unknown. | T4 seconds: **UNKNOWN**. | No reliable side-by-side artifact evidence found for stylized world art; licensing and hardware friction make it low priority. | Only include after the exact weight and commercial permissions are confirmed. |
| **HiDream-I1 Full** | Transformer is MIT, but the full pipeline includes separately licensed components. https://huggingface.co/HiDream-ai/HiDream-I1-Full/blob/main/README.md (accessed 2026-10-21). | **Poor single-T4 choice**: repository totals about **47.2 GB [VERIFIED repo listing, not VRAM]**; full fp16 likely requires offload/quantization. Exact minimum VRAM unknown. | T4 seconds: **UNKNOWN**. | Candidate for quality-max testing on larger hardware, but the T4 may spend more time moving weights than generating images. No directly comparable 100-image series benchmark found. | Exclude from initial Kaggle pipeline; only test if quantized implementation and full-component license matrix are clearly documented. |
| **FLUX.2 klein 9B** | Non-commercial license, gated; not legal for monetized $0 use without new license. https://huggingface.co/black-forest-labs/FLUX.2-klein-9B (accessed 2026-10-21). | Full fp16 **not a safe 16 GB fit**; card weight file itself is about **18.2 GB [VERIFIED file listing]**, before runtime overhead. | T4 seconds: **UNKNOWN**. | Irrelevant to final shortlist until commercial permission and hardware path are solved. | Exclude. |
| **FLUX.1 Krea/dev** | Non-commercial FLUX.1-dev license; see licensing section. | Full fp16 not a safe T4 fit; quant/offload does not resolve license issue. | T4 seconds: **UNKNOWN**. | Human-preference leaderboards may rank aesthetics well, but such quality evidence cannot override license restrictions. | Exclude from monetized production unless separately licensed. |
| **FLUX.1 dev** | Non-commercial FLUX.1-dev license. | 12B-class architecture, full fp16 too large for T4. | T4 seconds: **UNKNOWN**. | Quality may be strong; irrelevant if the license doesn’t permit this use. | Exclude for current stated budget/use. |
| **ERNIE-Image-Turbo** | Apache-2.0 model card. https://huggingface.co/baidu/ERNIE-Image-Turbo (accessed 2026-10-21). | Model card marks **8B parameters [VERIFIED card spec]**, repository is about **31.6 GB [VERIFIED listing total, not VRAM]**; common official recipe is bf16. T4 fp16 compatibility/peak memory is **UNKNOWN**. | T4 seconds: **UNKNOWN**. | Interesting newer candidate, but there is not enough independent T4 evidence to prioritize it over a known SDXL workflow. | Wait for a clear T4-compatible fp16/quant recipe or test as an exploratory candidate; do not assume 8B means it fits. |
| **Qwen-Image 2.1** | Commercial use expressly requires separate license; $0 commercial gate fails. https://github.com/QwenLM/Qwen-Image-2.1/blob/main/LICENSE (accessed 2026-10-21). | Card describes **7B visual-generation component [VERIFIED official card statement]**; exact all-component fp16 T4 peak memory **UNKNOWN**, but it is not cleared for this purpose anyway. | T4 seconds: **UNKNOWN**. | Early user issue reports mention hand errors and dirty/noisy outputs; anecdotes, not benchmark incidence. https://github.com/QwenLM/Qwen-Image-2.1/issues/6 and https://github.com/QwenLM/Qwen-Image-2.1/issues/13 (issues opened in Sep 2026; accessed 2026-10-21). | Exclude unless the license changes or a commercial grant is obtained. |

### Important negative result on artifact “benchmarks”

I did **not** find a trustworthy independent public study that measures, for all the candidates above, a common artifact rate covering hands/limbs, geometry, texture mush, broken text, repeated patterns, and cross-image style consistency on the same prompts/hardware. Therefore the artifact evaluations here are qualitative, and numeric artifact-risk ratings in the ranking are **ESTIMATE**, not “tested error percentages.” Community reports are useful to generate adversarial prompts, not to estimate population-wide defect rates.

- Z-Image Turbo reports: repetition/composition issues (thread date **2025-11-28 [VERIFIED thread date]**), banding/blotchy art textures (**2025-12-04 [VERIFIED thread date]**), anatomy/scene issues (**2025-12-08 [VERIFIED thread date]**). These are single-user reports, not generalizable statistics. https://www.reddit.com/r/StableDiffusion/comments/1p94upi/z_image_flaws/ ; https://www.reddit.com/r/StableDiffusion/comments/1pdr11d/z_image_turbo_can_be_quite_good_except_for_the/ ; https://www.reddit.com/r/StableDiffusion/comments/1ph12vj/some_recent_zimage_gens/ (accessed 2026-10-21).
- Qwen-Image 2.1 community reports from **September 2026 [VERIFIED issue dates]** mention hands and noisy/dirty output. This is not enough to compare defect frequency across architectures. https://github.com/QwenLM/Qwen-Image-2.1/issues/6 ; https://github.com/QwenLM/Qwen-Image-2.1/issues/13 (accessed 2026-10-21).

---

## Weighted ranking

### Weights

The requested weights sum to **100 [VERIFIED arithmetic from the user’s specification]**:

- Artifact risk / visual defect resistance: **30% [VERIFIED user-specified weight]**
- T4 feasibility: **20% [VERIFIED user-specified weight]**
- Speed: **20% [VERIFIED user-specified weight]**
- License: **15% [VERIFIED user-specified weight]**
- Consistency tooling: **10% [VERIFIED user-specified weight]**
- Prompt adherence: **5% [VERIFIED user-specified weight]**

The six component ratings below are **ESTIMATE, 1–10**, using architecture/workflow maturity, available evidence, and practical viability. Speed scores are relative estimates only; no seconds-per-image are inferred from API/provider timings. A low license score means a serious $0 commercial-use blocker; it is not legal probability.

| Rank | Model / workflow | Artifact (30) [EST.] | T4 (20) [EST.] | Speed (20) [EST.] | License (15) [EST.] | Consistency tools (10) [EST.] | Prompt adherence (5) [EST.] | Weighted score /10 [EST.] |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | FLUX.2 klein 4B | 8.0 | 8.0 | 8.5 | 10.0 | 7.0 | 8.0 | **8.30** |
| 2 | SDXL Lightning 4-step | 6.5 | 9.5 | 9.0 | 8.5 | 9.5 | 6.5 | **8.20** |
| 3 | SDXL Base + own/verified LoRA | 7.5 | 9.5 | 6.5 | 9.0 | 10.0 | 7.0 | **8.15** |
| 4 | Z-Image Turbo | 7.0 | 8.0 | 9.0 | 10.0 | 6.5 | 8.0 | **8.05** |
| 5 | Hyper-SD (SDXL path) | 6.5 | 9.5 | 8.0 | 8.5 | 9.5 | 6.5 | **8.00** |
| 6 | Playground v2.5 | 7.0 | 9.0 | 7.0 | 8.5 | 8.5 | 7.0 | **7.78** |
| 7 | SD 3.5 Medium | 8.0 | 7.0 | 5.0 | 8.0 | 7.0 | 8.0 | **7.10** |
| 8 | PixArt-Sigma | 6.5 | 7.0 | 6.5 | 8.5 | 6.5 | 7.0 | **6.92** |
| 9 | FLUX.1 schnell | 8.0 | 4.5 | 4.5 | 10.0 | 6.0 | 8.5 | **6.72** |
| 10 | ERNIE-Image-Turbo | 8.0 | 3.0 | 6.0 | 10.0 | 6.0 | 8.5 | **6.72** |
| 11 | Sana 1.5 1.6B | 6.5 | 8.0 | 7.5 | 5.0 | 5.5 | 7.0 | **6.70** |
| 12 | Qwen-Image-2512 (quantized) | 8.5 | 4.0 | 3.0 | 10.0 | 7.5 | 9.0 | **6.65** |
| 13 | SD 3.5 Large Turbo | 8.0 | 4.0 | 6.0 | 8.0 | 6.0 | 8.5 | **6.62** |
| 14 | Kolors | 7.0 | 5.0 | 5.5 | 5.0 | 7.0 | 8.0 | **6.05** |
| 15 | FLUX.2 klein 9B | 8.5 | 3.0 | 7.0 | 1.0 | 7.5 | 8.5 | **5.88** |
| 16 | HiDream-I1 Full | 8.0 | 2.0 | 3.0 | 8.0 | 7.0 | 8.5 | **5.72** |
| 17 | FLUX.1 Krea/dev | 8.0 | 4.5 | 4.5 | 1.0 | 6.5 | 8.5 | **5.42** |
| 18 | Qwen-Image 2.1 | 8.5 | 3.0 | 4.0 | 1.0 | 8.0 | 9.0 | **5.35** |
| 19 | FLUX.1 dev | 8.0 | 3.5 | 4.0 | 1.0 | 6.5 | 8.5 | **5.12** |

**Interpretation:** FLUX.2 klein 4B tops the *default weighted hypothesis*, but its lead over SDXL Lightning and SDXL+LoRA is small relative to the uncertainty of the ratings. For the actual task—consistent, controlled hundreds of images—the SDXL+LoRA ecosystem can be the practical winner even with a lower relative speed rating. The table is a prioritization model, not proof that klein has the lowest real artifact rate.

### Sensitivity analysis

I reweighted the same **ESTIMATE component ratings** under three alternative priorities. Scores below are **ESTIMATE /10**; only the leading positions are shown because lower ranks are not useful for the decision.

| Scenario | Weights (artifact / T4 / speed / license / consistency / adherence) | Top results | What changes |
|---|---|---|---|
| Base (requested) | **30 / 20 / 20 / 15 / 10 / 5 [VERIFIED weights from user]** | FLUX.2 klein 4B **8.30**; SDXL Lightning **8.20**; SDXL+LoRA **8.15**; Z-Image Turbo **8.05** | Four finalists are tightly clustered. |
| Quality-first | **45 / 20 / 10 / 15 / 5 / 5 [ESTIMATE scenario weights]** | FLUX.2 klein 4B **8.30**; SDXL+LoRA **8.12**; Z-Image Turbo **7.88**; SDXL Lightning **7.80**; Hyper-SD SDXL **7.70** | LoRA control improves SDXL’s relative case; speed matters less. |
| Throughput-first | **20 / 20 / 35 / 15 / 5 / 5 [ESTIMATE scenario weights]** | FLUX.2 klein 4B **8.43**; SDXL Lightning **8.43**; Z-Image Turbo **8.38**; Hyper-SD SDXL **8.07**; SDXL+LoRA **7.88** | Distilled routes move up, but T4 timings remain unmeasured. |
| Consistency-first | **25 / 20 / 10 / 15 / 25 / 5 [ESTIMATE scenario weights]** | SDXL+LoRA **8.62**; SDXL Lightning **8.40**; Hyper-SD SDXL **8.30**; FLUX.2 klein 4B **8.10**; Playground v2.5 **8.00** | Mature SDXL controls become the clear preference. |

**Sensitivity takeaway:** the “winner” changes with plausible weights. Licensing and minimum-hardware requirements should also be hard gates rather than merely weighted categories: a high quality score does not make a non-commercial model legal for monetized videos, and an attractive theoretical weight size does not prove stable T4 generation.

---

## Top three: reproducible T4 recipes

These are **starting recipes, not claims that I executed them on a Kaggle GPU**. The code intentionally measures local reality and fails loudly on unsupported dtype/OOM. Use a fresh notebook, download/cache models before timing, record GPU/package versions, and pin model revisions or commit hashes for production. Current Diffusers release page lists **0.41.0 [VERIFIED release listing at the time this report was researched]**, released **2026-10-06 [VERIFIED release date]**: https://github.com/huggingface/diffusers/releases (accessed 2026-10-21). Package ecosystem compatibility can move, so a working notebook must be saved as an environment snapshot.

### Recipe A — SDXL Base + self-trained/verified style LoRA (recommended for consistency)

**Why:** mature controls and the easiest path to repeatedly render a named creature or visual style. Use a LoRA trained on your own legally usable reference images or a LoRA with a clear commercial license. Do not download a random style LoRA and assume it shares SDXL Base’s license.

**Install (keep Kaggle’s torch build unless it is demonstrably broken):**

```python
# Run in a clean Kaggle notebook. Do not blindly reinstall torch/CUDA.
!pip -q install "diffusers==0.41.0" "transformers" "accelerate" "safetensors" "peft"
```

**Generation outline:**

```python
import os, time, torch
from diffusers import DiffusionPipeline, DPMSolverMultistepScheduler
from diffusers import AutoencoderKL

assert torch.cuda.is_available(), "No CUDA GPU attached"
print("GPU:", torch.cuda.get_device_name(0))
print("Torch:", torch.__version__, "CUDA:", torch.version.cuda)
print("VRAM GiB:", round(torch.cuda.get_device_properties(0).total_memory / 2**30, 2))

model_id = "stabilityai/stable-diffusion-xl-base-1.0"
pipe = DiffusionPipeline.from_pretrained(
    model_id,
    torch_dtype=torch.float16,
    variant="fp16",
    use_safetensors=True,
)
# Optional numerical-stability workaround for SDXL VAE. Keep it documented in the run manifest.
vae = AutoencoderKL.from_pretrained(
    "madebyollin/sdxl-vae-fp16-fix",
    torch_dtype=torch.float16,
)
pipe.vae = vae
pipe.scheduler = DPMSolverMultistepScheduler.from_config(
    pipe.scheduler.config,
    algorithm_type="dpmsolver++",
    use_karras_sigmas=True,
)
pipe.to("cuda")
pipe.enable_vae_slicing()

# Optional: for a LoRA you trained yourself or independently verified as commercially licensed.
# pipe.load_lora_weights("/kaggle/working/my_style_lora")
# pipe.fuse_lora(lora_scale=0.7)  # test several scales; do not assume one works for every LoRA

prompt = (
    "field-guide illustration of a six-legged mossback grazer on an alien wetland, "
    "full body, readable silhouette, three-quarter view, limited shapes, "
    "hand-painted gouache, crisp contour, restrained texture, muted jade and ochre, "
    "single subject, clean negative space, no lettering"
)
negative = "text, watermark, extra limbs, fused legs, duplicate subject, cropped body, photorealism"
seed = 731902  # ESTIMATE: fixed experiment seed, not a best seed

g = torch.Generator(device="cuda").manual_seed(seed)
torch.cuda.reset_peak_memory_stats()
t0 = time.perf_counter()
img = pipe(
    prompt=prompt,
    negative_prompt=negative,
    width=1024, height=1024,        # ESTIMATE test canvas; SDXL card target is 1024 px
    num_inference_steps=30,          # ESTIMATE starting point
    guidance_scale=5.5,              # ESTIMATE starting point
    generator=g,
).images[0]
elapsed = time.perf_counter() - t0
img.save("sdxl_test.png")
print("seconds/image:", round(elapsed, 3))
print("peak allocated GiB:", round(torch.cuda.max_memory_allocated() / 2**30, 2))
```

**Settings to tune:** start around **30 steps [ESTIMATE]** and CFG **5.5 [ESTIMATE]**; change one variable at a time. If repeated-series consistency is the priority, use an identity/shape LoRA plus a reference-image/ControlNet workflow, not just the same seed. For style data, aim for a clean, narrowly scoped set of examples; avoid changing the palette, camera, medium and silhouette all at once in the training set. LoRA training time, final rank, and T4 quality are **UNKNOWN** until tested on the dataset and installed trainer.

**Important:** the public SDXL fp16 VAE fix is a separate model file and dependency; preserve its license and revision: https://huggingface.co/madebyollin/sdxl-vae-fp16-fix (accessed 2026-10-21). It is a workaround, not proof that all black/NaN image failures are caused by the VAE.

### Recipe B — FLUX.2 klein 4B (new-model quality/speed challenger)

**Why:** it has a much more attractive public commercial license than FLUX-dev and a vendor claim of low VRAM. But standard reference snippets may use bf16; T4 fp16 behavior is an explicit test gate.

```python
import time, torch
from diffusers import Flux2KleinPipeline

assert torch.cuda.is_available()
print("GPU:", torch.cuda.get_device_name(0))
print("Torch:", torch.__version__, "CUDA:", torch.version.cuda)

pipe = Flux2KleinPipeline.from_pretrained(
    "black-forest-labs/FLUX.2-klein-4B",
    torch_dtype=torch.float16,
)
# If direct .to("cuda") OOMs, keep the model on CPU and use supported offload.
pipe.enable_model_cpu_offload()

prompt = (
    "stylized natural-history concept art of a colossal lantern-backed grazer in a bioluminescent "
    "salt forest, clear four-legged anatomy, one head, complete silhouette, eye-level wide shot, "
    "illustrated speculative ecology, painterly shapes, limited palette of indigo, mint and amber, "
    "intentional negative space, no typography"
)
seed = 731902  # ESTIMATE experiment seed

torch.cuda.reset_peak_memory_stats()
t0 = time.perf_counter()
img = pipe(
    prompt=prompt,
    height=1024, width=1024,       # ESTIMATE starting canvas
    num_inference_steps=4,         # VERIFIED as the distilled Klein setting in the official family documentation
    guidance_scale=1.0,            # ESTIMATE initial value; confirm with the current card/pipeline
    generator=torch.Generator(device="cpu").manual_seed(seed),
).images[0]
print("seconds/image:", round(time.perf_counter() - t0, 3))
print("peak allocated GiB:", round(torch.cuda.max_memory_allocated() / 2**30, 2))
img.save("klein_test.png")
```

If the installed `Flux2KleinPipeline` rejects fp16 or produces non-finite/black outputs, **do not paper over the failure** by repeatedly changing unrelated settings. Record the traceback, diffusers/transformers/torch versions, GPU type and model revision. Test the current upstream example in the official card, then test its documented CPU-offload path; if no supported fp16 T4 recipe exists for the pinned commit, classify the candidate as **not reproducible on this runtime** and use SDXL until proven otherwise. Offload can materially reduce speed; there is no verified T4 seconds/image value in this report.

Sources: https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/tree/main ; https://github.com/black-forest-labs/flux2/blob/main/README.md ; Diffusers documentation/release page at https://github.com/huggingface/diffusers/releases (accessed 2026-10-21).

### Recipe C — SDXL Lightning, full 4-step UNet checkpoint

**Why:** fast baseline from the same general SDXL tool ecosystem. Use the *correct checkpoint file for the number of steps*; a **4-step checkpoint [VERIFIED variant]** should not be judged using a mismatched scheduler setup.

```python
import time, torch
from diffusers import StableDiffusionXLPipeline, EulerDiscreteScheduler

ckpt = "ByteDance/SDXL-Lightning"
pipe = StableDiffusionXLPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    torch_dtype=torch.float16,
    variant="fp16",
    use_safetensors=True,
)
pipe.load_lora_weights(ckpt, weight_name="sdxl_lightning_4step_lora.safetensors")
pipe.fuse_lora()
pipe.scheduler = EulerDiscreteScheduler.from_config(
    pipe.scheduler.config,
    timestep_spacing="trailing",
)
pipe.to("cuda")
pipe.enable_vae_slicing()

prompt = (
    "editorial fantasy field-guide illustration of a glass-antlered marsh stag, full body, "
    "four clear legs, side three-quarter view, central silhouette, soft gouache and ink, "
    "controlled cel-like shading, consistent muted teal and copper palette, no text"
)
seed = 731902  # ESTIMATE experiment seed
start = time.perf_counter()
img = pipe(
    prompt=prompt,
    num_inference_steps=4,        # VERIFIED intended step count for this LoRA/checkpoint
    guidance_scale=0.0,            # ESTIMATE/common Lightning default; check the current official example
    width=1024, height=1024,
    generator=torch.Generator(device="cuda").manual_seed(seed),
).images[0]
print("seconds/image:", round(time.perf_counter() - start, 3))
img.save("lightning_test.png")
```

If using the **full Lightning UNet checkpoint** instead of the LoRA, follow the exact alternate loading instructions in the model card. Do not combine the LoRA snippet and the full-UNet snippet. Source and checkpoint filenames: https://huggingface.co/ByteDance/SDXL-Lightning (accessed 2026-10-21). For the first comparison, do not add a face-detailer or high-res fix to one model but not the others; it confounds the comparison. If production needs them, test a second, equally configured pass across the finalists.

---

## Thirty-minute Kaggle screening protocol

This is a **30-minute evaluation block [ESTIMATE protocol duration]**, not a promise that all candidates can generate every test image in that time. Weight downloads and first-load compilation can consume the budget; cache models before starting the clock if the goal is generation speed. If the first pass exceeds the limit, record that fact and resume the same pre-registered test later. Do not label a timeout as a model quality failure.

### Test structure

1. **Hardware and versions (first 2 minutes [ESTIMATE]):** print GPU name/count, torch/cuda versions, free/total VRAM, package versions and model commit hashes. Kaggle T4 ×2 is two separate GPUs, not pooled memory; run each model on one card for comparable speed or write down any distribution strategy. (Sources: https://www.kaggle.com/docs/notebooks and https://www.kaggle.com/product-feedback/361104; accessed 2026-10-21.)
2. **Warm-up (up to 3 minutes [ESTIMATE]):** load one model at a time. Make one discarded warm-up render and only then start timing. Record load/download time separately from per-image steady-state time.
3. **Fixed test set:** use the **12 prompts [VERIFIED as the test-set design]** below. Pin seed `731902` for all candidates; then, if time permits, repeat the hardest prompts with a second fixed seed `419087`. Both seeds are **ESTIMATE test identifiers**, not special seeds. Keep prompt strings byte-for-byte identical across models, only adapt model-specific required formatting, and save JSON metadata with every image.
4. **Fair resource limits:** use each candidate’s official intended settings first (e.g., Lightning’s intended step count; Z-Image Turbo’s official step count; Klein’s distilled step count). For a separate *quality-normalized* pass, spend a second test on the finalist with higher steps/quality settings. Never mix these two questions: “fast at its intended setup?” and “best-looking after tuning?”
5. **Blind review:** save images with random IDs such as `R04`, strip model/seed details from file names and contact sheets, shuffle presentation order, and ask at least **2 reviewers [ESTIMATE minimum for a small screening, not statistical power]** to score images without knowing the source model. If only one reviewer is available, wait **24 hours [ESTIMATE]** before re-scoring without labels to reduce first-impression anchoring.
6. **Do not overclaim from the sample:** a dozen prompts are a cheap screen, not a statistically robust defect-rate estimate. Keep the same protocol for future model/LoRA updates so results remain comparable.

### Twelve fixed prompts (stylized concepts; no real people or real-event fakes)

Use these exact strings to stress different failure types. The seed for the primary pass is `731902` (**ESTIMATE test seed**).

1. **Four-legged anatomy:** “A complete full-body natural-history illustration of one six-legged velvet grazer, three legs clearly visible on each side, one head, four horns, standing in a fern meadow, side three-quarter view, flat gouache and ink, clear silhouette, no text.”
2. **Many limbs / occlusion:** “A small nine-legged crystal crab on a black volcanic rock, all legs separated and countable, overhead three-quarter angle, stylized museum illustration, crisp line art, simple background, no lettering.”
3. **Creature/prop spatial relation:** “One tiny winged lizard perched on the top rim of a giant ceramic bowl, lizard clearly much smaller than bowl, side view, storybook illustration, clean shapes, no text.”
4. **Repeated pattern:** “A single long ribbon-tailed desert serpent crossing a dune, body forms one continuous S-curve, one head and one tail, no duplicate bodies, graphic novel concept art, restrained orange and violet palette.”
5. **Architecture geometry:** “A small impossible library built into a cliff, one main staircase leading to a single arched doorway, repeated windows aligned evenly, wide establishing shot, illustrated fantasy atlas, no people, no text.”
6. **Perspective / scale:** “A giant mushroom forest seen from ground level, tiny river and small deer-like creatures at the base for scale, strong foreground/midground/background, painterly natural history plate, no typography.”
7. **Text temptation:** “A whimsical potion shop with blank unlabelled glass bottles, no signs, no writing, legible simple shelves, colored-pencil and gouache illustration, front view.”
8. **Texture / gradient:** “A translucent jellyfish-like sky grazer floating above lavender clouds, smooth translucent bell with fine internal filaments, subtle gradients and crisp edges, no speckled noise, science-fantasy concept illustration.”
9. **Palette consistency:** “A three-winged nocturnal moth with a crescent-shaped body on a dark blue branch, limited palette of indigo, mint and amber only, complete subject, inked field-guide plate, no caption.”
10. **Subject count:** “Exactly three different tiny amphibian species beside a pond: one round red frog, one slender blue salamander, one green tree frog, each fully visible and separated, flat educational illustration, no extra animals.”
11. **Silhouette / distant scene:** “A lone six-legged caravan beast with a wide shell crossing a salt flat toward a distant floating island, readable silhouette against dawn haze, stylized adventure matte painting, no text.”
12. **Consistency stress:** “A glass-antlered marsh stag, full-body side three-quarter view, four clear legs, one head and two antlers made of translucent glass, muted teal and copper color scheme, storybook natural-history illustration, no lettering.”

### Artifact-count rubric

Review at native size first; then view a reduced-size thumbnail to see whether defects actually matter in a video frame. Record image ID, model hidden label, prompt number, and each category. Apply the same criteria to each model.

| Category | Score | Operational definition |
|---|---:|---|
| Anatomy / limb integrity | **0–2 [ESTIMATE rubric]** | **0:** coherent; **1:** minor ambiguity; **2:** obvious fused/extra/missing limb, duplicate head, broken joint. |
| Geometry / perspective | **0–2 [ESTIMATE rubric]** | **0:** coherent enough for illustration; **1:** small inconsistency; **2:** major impossible connection, melted building/object. |
| Count / relation adherence | **0–2 [ESTIMATE rubric]** | **0:** requested counts and spatial relation mostly honored; **1:** one small miss; **2:** clear count/scale/relation failure. |
| Texture / edge defects | **0–2 [ESTIMATE rubric]** | **0:** clean; **1:** mild mush/banding/repetition; **2:** distractingly blotchy, noisy, broken, or repeated texture. |
| Text / watermark | **0–2 [ESTIMATE rubric]** | **0:** no unwanted text; **1:** tiny stray mark; **2:** obvious gibberish or watermark-like artifact. |
| Prompt usefulness | **0–2 [ESTIMATE rubric]** | **0:** good enough for intended video; **1:** salvageable with crop/inpainting; **2:** needs reroll or manual repair. |

Calculate two measures per model:

- **Severe-artifact rate [ESTIMATE measurement from your test]** = number of images with any category scored **2 [ESTIMATE rubric threshold]** divided by images reviewed. Report numerator and denominator, not only a percentage.
- **Repair burden [ESTIMATE measurement]** = mean count of categories scoring **1 or 2 [ESTIMATE rubric threshold]**, plus the share needing a reroll. Log rerolls separately from first attempts; only reporting the best image hides real cost per usable image.

Also record: first-attempt seconds/image (warm cache), load seconds, peak CUDA memory, OOM/NaN/black-image failures, and usable-images-per-minute. The last is the meaningful production metric; pure render throughput is not.

### Go/no-go gates for your particular use

Treat the values below as **ESTIMATE internal thresholds**, not universal standards or published research results:

- Keep a candidate only if it can render **all 12 prompts [VERIFIED test design]** with no recurring crash/black-image pattern, and its severe-artifact rate is no worse than the current baseline in the same test.
- For first-pass screening, aim for at least **9 of 12 images [ESTIMATE]** judged “usable after normal crop/motion effects, no manual repainting.” If none reaches that, do not force a winner; improve prompt/controls or lower the intended visual complexity.
- In production, run a larger batch before commitment: a few dozen image samples are still a small test compared with **100+ images per episode [VERIFIED user workload requirement]**. Estimate episode cost using observed *usable* outputs, not render count.
- Do not accept model A as better because its best image beats model B’s best image. Compare per-prompt pairs, count all failed attempts, and show reviewers the same size/crop.

---

## Consistency toolkit for a 100+ image episode

No single prompt or seed makes a sequence consistent. Use layers of control.

1. **Visual style bible:** fixed medium, line weight, palette, light direction, level of detail, camera vocabulary, background complexity and “no typography” instruction. Keep a short canonical suffix. Do not append a new art style to every prompt.
2. **Creature design sheet:** make a front/side/three-quarter turnaround and several silhouette poses for each recurring creature. If a model supports image reference or IP-Adapter/reference conditioning, use these as reference inputs. The effect varies by model/extension; don’t assume identical IP-Adapter support between SDXL, FLUX, Z-Image and Qwen pipelines.
3. **Own style LoRA:** SDXL currently has the lowest workflow uncertainty here. Train on a consistent, legally usable set of your own outputs/references; keep model/checkpoint/trigger token/rank/learning rate/dataset manifest. Exact training time and quality on a free T4 are **UNKNOWN** and may be constrained by memory/session time.
4. **Composition control:** use ControlNet (pose/depth/lineart where the model-compatible implementation exists), silhouettes, sketches and img2img to preserve layout; inpaint local defects rather than rerolling the whole scene. Ensure adapter/control model licenses permit the intended use.
5. **Seed policy:** use seeds for debugging/reproducibility, not as an identity lock. Prompt changes, different aspect ratios, scheduler changes and different checkpoint versions alter the result even with the same seed.
6. **Prompt budget:** one main subject, one action, one viewpoint, two or three critical details, a palette, and a style suffix. Overloaded prompts create more competing relations and increase the manual QC burden.
7. **Motion graphics:** use pan/zoom, parallax layers, labels, map overlays and simple animated vector diagrams to create editorial movement without asking the image model to depict tiny text or mechanically precise details. Generate labels in the editor, not inside the image.

Relevant tools/doc links: Diffusers memory optimizations https://github.com/huggingface/diffusers/blob/main/docs/source/en/optimization/memory.md ; SDXL Base https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0 ; SDXL Lightning https://huggingface.co/ByteDance/SDXL-Lightning ; Z-Image pipeline docs https://github.com/huggingface/diffusers/blob/main/docs/source/en/api/pipelines/z_image.md (all accessed 2026-10-21). Specific extension compatibility changes over time; verify the selected extension’s current model card and supported base family before designing a pipeline around it.

---

## Kaggle T4 pitfalls and workarounds

### 1) fp16, bf16, NaNs and black images

- The target T4 should be treated as **fp16-capable, not natively bf16-capable [VERIFIED hardware premise]**. Some newer cards/examples default to `torch.bfloat16`; casting everything to fp16 is not proof that every pipeline supports it stably. Confirm the official supported dtype and run a tiny smoke test before a batch.
- For SDXL, the fp16 VAE can produce NaNs/black or corrupted outputs in some configurations. The SDXL fp16-fix VAE is a known workaround; record it as a changed component rather than silently applying it to just one candidate. Source: https://huggingface.co/madebyollin/sdxl-vae-fp16-fix (accessed 2026-10-21).
- Diffusers bug reports describe NaN cases for specific pipelines/configurations, but the issues are not evidence that every black image on a T4 has the same cause. Sources: https://github.com/huggingface/diffusers/issues/7765 and https://github.com/huggingface/diffusers/issues/7188 (accessed 2026-10-21). A black-image issue associated with attention slicing and model CPU offload on **MPS** is platform-specific and should not be cited as a T4 bug: https://github.com/huggingface/diffusers/issues/14438 (accessed 2026-10-21).
- Check `torch.isfinite` on intermediate/final tensors if you have access to them, save the first suspect output, and record dtype/scheduler/step count. Try the official precision path and VAE fix one change at a time. Don’t lower precision repeatedly without documenting it.

### 2) VRAM and offload

- Model file size is not peak VRAM. Text encoders, VAE, attention workspace, temporary tensors, allocator fragmentation and resolution all matter. A model whose weights are **8 GB [VERIFIED only where the official claim says so]** may still peak above that.
- `enable_model_cpu_offload()` can retain most inactive components on CPU and load them sequentially. Sequential CPU offload can reduce memory further but is often much slower. Follow current docs: https://github.com/huggingface/diffusers/blob/main/docs/source/en/optimization/memory.md (accessed 2026-10-21).
- Lowering resolution may make an OOM go away but changes the benchmark. If the intended output is **1024×1024 [ESTIMATE workload canvas]**, test at that size and report if you can only run a smaller canvas.
- Clear references and tensors between models (`del pipe, image; torch.cuda.empty_cache()`), but remember this does not release memory still held by live references.

### 3) Two T4s are not a 32 GB card

Kaggle’s T4 ×2 option exposes separate devices; model weights and per-device activations are not automatically combined. Use two GPUs to run independent image jobs in parallel only after verifying both devices are visible, and measure throughput on the same workload. The notebook quota and GPU availability are not guaranteed. Sources: https://www.kaggle.com/product-feedback/361104 and https://www.kaggle.com/docs/notebooks (accessed 2026-10-21).

### 4) pip / transformers / extensions

- Keep the platform’s existing PyTorch/CUDA combination unless the official pipeline requires a different one. Installing a generic latest torch wheel can mismatch the notebook CUDA build.
- Install Diffusers and only the minimum additional packages; save `pip freeze` and `pip check` output. A current Diffusers release exists at **0.41.0 [VERIFIED release page at research snapshot]**; older cached notebooks may import a different pipeline class. Source: https://github.com/huggingface/diffusers/releases (accessed 2026-10-21).
- bitsandbytes is not preinstalled under the stated constraint. If a proposed quantization recipe requires it, explicitly install and validate a compatible build; do not treat “GGUF,” “4-bit,” or “Nunchaku” as interchangeable. They are different formats/runtime paths and can change quality, speed, compatibility, and licensing.
- Custom CUDA packages and ComfyUI nodes are moving parts. Pin commit SHAs for node repos, log model hashes/revisions, and save a known-good notebook. Do not let unpinned auto-updates change the model halfway through a 100-image episode.

### 5) Downloads and time limits

- A first run may spend much of its allotted session downloading multi-GB model files, compiling kernels or initializing encoders. Report **download/load time**, **warm render time**, and **usable image rate** separately.
- If internet/download restrictions prevent fetching weights, don’t mark that as poor model quality; it is an environment/access failure. Kaggle and Colab access limitations should be checked on the actual account/session. Sources: https://www.kaggle.com/docs/notebooks and https://research.google.com/colaboratory/faq.html?authuser=8 (accessed 2026-10-21).

---

## Contradictions, unknowns, and what would change the decision

1. **FLUX.1 Krea/dev wording versus operative license:** the model card has commercial-sounding language about generated output, but also points to the FLUX.1-dev non-commercial license; the linked license requires separate permission for commercial activity. This report treats the operative linked license as controlling, and excludes it from a $0 monetized workflow. Sources: https://github.com/black-forest-labs/flux/blob/main/model_cards/FLUX.1-Krea-dev.md and https://github.com/black-forest-labs/flux/blob/main/model_licenses/LICENSE-FLUX1-dev (accessed 2026-10-21).
2. **Sana code versus weight license:** an Apache-looking code repository does not establish that a separately published weights checkpoint is Apache-2.0. The exact commercial status is therefore **UNKNOWN** pending direct inspection of the selected weights’ license file. Sources: https://github.com/NVlabs/Sana and https://huggingface.co/Efficient-Large-Model/SANA1.5_1.6B_1024px_diffusers/blob/main/LICENSE.txt (accessed 2026-10-21).
3. **Vendor speed claims versus local speed:** Z-Image’s sub-second claim is tied to H800-class hardware; FLUX.2 klein’s under-second/low-VRAM statements are vendor claims on their stated setup. Neither is a measured T4 1024×1024 result. Sources: https://github.com/huggingface/diffusers/blob/main/docs/source/en/api/pipelines/z_image.md and https://github.com/black-forest-labs/flux2/blob/main/README.md (accessed 2026-10-21).
4. **Image Arena quality is not a local throughput benchmark:** Artificial Analysis uses hosted providers and blind preference evaluation; scores/ranks change. It is relevant as a broad quality signal but cannot prove the open-weight checkpoint’s T4 speed or episode-wide style consistency. https://artificialanalysis.ai/methodology/image (accessed 2026-10-21).
5. **Community artifact reports are anecdotes:** reports about repetitive composition, hands, and texture are useful prompts for adversarial tests but cannot be transformed into an error percentage without a controlled sample. Example sources listed in the artifact section (all accessed 2026-10-21).
6. **Unknowns still material to this decision:** exact warmed-up seconds/image on a Kaggle T4; OOM behavior of every current Diffusers pipeline revision in fp16; true failure probability on the twelve prompt categories; output-quality penalty for specific quantized/GGUF builds; style-LoRA training convergence/time on free T4; and the precise weights license for the Sana candidate. These need runtime verification, not extrapolation.

---

## Decision and test order

For the first production experiment, compare these in this order:

1. **SDXL Base + own/verified style LoRA** — baseline for controlled art direction and series consistency.
2. **SDXL Lightning 4-step** — same ecosystem, speed-vs-detail baseline.
3. **FLUX.2 klein 4B** — attractive license and claimed low VRAM, but gate on fp16 T4 reproducibility.
4. **Z-Image Turbo** — Apache-2.0 and promising throughput claim, gate on T4-compatible fp16/quant runtime and repetition/texture review.

A sensible decision rule is: choose the fastest pipeline whose *usable-image rate*, severe artifact rate, consistency review, license and runtime stability beat your threshold. Do not choose by one showcase prompt or an unverified “images per second” claim. If the quality-best model requires more memory than one T4 can realistically supply, label that fact plainly and pick the best model that *actually completes the fixed workload* on one T4—not the model with the prettiest demo image.

### Source register (accessed 2026-10-21)

- Official Diffusers releases and memory docs: https://github.com/huggingface/diffusers/releases ; https://github.com/huggingface/diffusers/blob/main/docs/source/en/optimization/memory.md
- Z-Image official card/docs/quant route: https://huggingface.co/Tongyi-MAI/Z-Image-Turbo/tree/main ; https://github.com/huggingface/diffusers/blob/main/docs/source/en/api/pipelines/z_image.md ; https://huggingface.co/nunchaku-ai/nunchaku-z-image-turbo
- FLUX model cards/licenses: https://github.com/black-forest-labs/flux/blob/main/model_cards/FLUX.1-schnell.md ; https://github.com/black-forest-labs/flux/blob/main/model_cards/FLUX.1-Krea-dev.md ; https://github.com/black-forest-labs/flux/blob/main/model_licenses/LICENSE-FLUX1-dev ; https://github.com/black-forest-labs/flux2/blob/main/README.md ; https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/tree/main ; https://huggingface.co/black-forest-labs/FLUX.2-klein-9B
- SDXL / Lightning / Playground / Hyper-SD: https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0 ; https://huggingface.co/ByteDance/SDXL-Lightning ; https://huggingface.co/ByteDance/Hyper-SD ; https://huggingface.co/playgroundai/playground-v2.5-1024px-aesthetic ; https://huggingface.co/playgroundai/playground-v2.5-1024px-aesthetic/blob/af20e72b66505bf5f453a3b52e715f6203065777/LICENSE.md
- Other model cards: https://huggingface.co/stabilityai/stable-diffusion-3.5-medium ; https://huggingface.co/stabilityai/stable-diffusion-3.5-large-turbo ; https://huggingface.co/PixArt-alpha/PixArt-Sigma-XL-2-1024-MS ; https://huggingface.co/Qwen/Qwen-Image ; https://huggingface.co/Qwen/Qwen-Image-2512 ; https://huggingface.co/HiDream-ai/HiDream-I1-Full/blob/main/README.md ; https://huggingface.co/baidu/ERNIE-Image-Turbo ; https://github.com/NVlabs/Sana ; https://github.com/Kwai-Kolors/Kolors/blob/master/MODEL_LICENSE
- Qwen-Image 2.1 license/community issues: https://github.com/QwenLM/Qwen-Image-2.1/blob/main/LICENSE ; https://github.com/QwenLM/Qwen-Image-2.1/issues/6 ; https://github.com/QwenLM/Qwen-Image-2.1/issues/10 ; https://github.com/QwenLM/Qwen-Image-2.1/issues/13
- Benchmarks: https://artificialanalysis.ai/methodology/image ; https://artificialanalysis.ai/image/leaderboard/text-to-image/ ; https://arxiv.org/abs/2310.11513 ; https://arxiv.org/abs/2512.16853 ; https://github.com/facebookresearch/GenEval2
- Runtime / free GPU constraints: https://www.kaggle.com/docs/notebooks ; https://www.kaggle.com/product-feedback/361104 ; https://research.google.com/colaboratory/faq.html?authuser=8
- SDXL fp16 VAE fix / relevant Diffusers issue reports: https://huggingface.co/madebyollin/sdxl-vae-fp16-fix ; https://github.com/huggingface/diffusers/issues/7765 ; https://github.com/huggingface/diffusers/issues/7188 ; https://github.com/huggingface/diffusers/issues/14438

**Final verdict:** no candidate has been proven to pass every gate on a free T4 in this audit. Start with the mature SDXL controlled pipeline, and use the fixed-prompt protocol to earn the right to switch to a newer model. The evidence gap is not a reason to avoid testing; it is the reason not to believe unmeasured speed and quality claims.

<<<КОНЕЦ ВЛОЖЕНИЯ>>>

*[приложен файл: DOC-20261021-WA0081.pdf]*

---

### [12] CLAUDE · 2026-10-21 06:07 UTC

**Оба отчёта сходятся: ни одна модель не доказана на T4, скорости на T4 нет ни у кого (UNKNOWN).** Но список финалистов и лицензии совпадают, а отличаются в деталях.

**Совпадение**
- Допустимы для монетизации: Z-Image Turbo (Apache-2.0), FLUX.2 klein 4B (Apache-2.0), SDXL (+LoRA), SDXL Lightning, FLUX.1 schnell, SD 3.5 (до $1 млн дохода).
- Исключить: Qwen-Image-2.1, FLUX.1 dev/Krea, FLUX.2 klein 9B (некоммерческие).
- Артефакты у всех не измерены: есть только отдельные жалобы, а не доля ошибок.
- Главный подводный камень: T4 не поддерживает bf16, нужен fp16. Это вероятная причина провала G2.

**Расхождения**
- Perplexity ставит первым Z-Image Turbo, ChatGPT ставит первым FLUX.2 klein 4B. Разница в баллах 1-2 из 100, это шум.
- Perplexity не проверил глубоко Hyper-SD, PixArt, Playground и некоторые лицензии. Ссылкам на блоги верить меньше, чем официальным карточкам ChatGPT.
- Параметры: Perplexity советует Z-Image `steps=9, guidance=0`, ChatGPT `8 шагов`. Это одно и то же (9 шагов дают 8 вычислений).
- Сам Kaggle: Perplexity пишет, что T4 ×2 это две отдельные карты, не 32 ГБ. Совпадает с ChatGPT.

**Мой выбор для бейкоффа (по одной модели за запуск, fp16, без bitsandbytes)**
1. **SDXL Base + style LoRA** как надёжная база: лучшая экосистема для постоянства существ (LoRA, ControlNet, IP-Adapter), точно влезает в T4.
2. **Z-Image Turbo** как претендент по качеству и скорости. Нужен fp16 или `enable_model_cpu_offload`.
3. **FLUX.2 klein 4B** третьим, если fp16 пойдёт.
SDXL Lightning держать как запасной быстрый вариант. Остальных не тестируем.

**Тест (в обоих отчётах одинаковый и я его принимаю):** 12 фиксированных промптов, одинаковые seed, слепые файлы A/B/C, счёт артефактов по рубрике 0-2. Отдельно считать «сколько годных кадров в минуту», а не только секунды на картинку.

**Правки к моему промпту S1 (Kilo), коротко:**
- Порядок моделей: SDXL Base (VAE fp16-fix) → Z-Image Turbo → klein 4B, по одной за запуск.
- Для каждой: fp16, `enable_model_cpu_offload` если OOM, при NaN/чёрных картинках записать трассировку и остановиться, не менять сразу несколько настроек.
- Использовать 12 промптов и рубрику из отчёта ChatGPT (файл `open_weights_t2i_t4_audit_2026-10-21.md`, раздел про 30-минутный протокол). Положите его в `docs/openmontage/image_gen/`.
- Лицензии читать из официальных карточек, не из блогов.

Хотите, перепишу S1-1 и S1-2 в готовый промпт с этими правками?

---

### [13] ВЫ · 2026-10-21 06:09 UTC

Нет я уже дал эти промпты подождём ответ и потом эти 3 модели проверим и изучи в интернете как лучше давать промпты для этих моделей чтобы посмотреть какой самый лучший

---

### [14] CLAUDE · 2026-10-21 06:09 UTC

Ищу официальные рекомендации и отзывы пользователей по промптингу каждой из трёх моделей.

> 🔎 Веб-поиск (standard): Z-Image Turbo prompting guide best practices prompt structure

> 🔎 Веб-поиск (standard): FLUX.2 klein prompting guide official docs prompt structure

> 🔎 Веб-поиск (standard): SDXL prompting best practices illustration style LoRA negative prompt consistent character

> Найденные источники:
>   - gist.github.com — https://gist.github.com/illuminatianon/c42f8e57f1e3ebf037dd58043da9de32
>   - Z-Image Turbo Prompting Guide: 25 Style Presets, Realism Secrets & 30 Examples — https://fliki.ai/blog/z-image-turbo-prompting-guide
>   - Back to Blogs & News — https://qubrid.com/blog/how-to-write-better-prompts-for-z-image-turbo
>   - Run models all in one Sandbox 🏖️ — https://fal.ai/learn/devs/z-image-turbo-prompt-guide
>   - how to write better prompts for z image turbo — https://www.qubrid.com/blog-news/how-to-write-better-prompts-for-z-image-turbo
>   - z image turbo prompting guide formula tips and 5 example prompts — https://deapi.ai/blog/z-image-turbo-prompting-guide-formula-tips-and-5-example-prompts
>   - gist.github.com — https://gist.github.com/osirismqz/2a306336c1e32ad55d28420f36dec185

> Найденные источники:
>   - > ## Documentation Index — https://docs.bfl.ai/flux_2/flux2_overview.md
>   - flux 2 klein prompt guide — https://fal.ai/learn/devs/flux-2-klein-prompt-guide
>   - how to use flux — https://fal.ai/learn/tools/how-to-use-flux
>   - flux prompts — https://www.dreampixelforge.com/blog/flux-prompts
>   - FLUX.2 [klein] - Fast Generation Guide — https://help.bfl.ai/articles/8642316687-flux-2-klein-fast-generation-guide
>   - docs.bfl.ai — https://docs.bfl.ai/guides
>   - flux best practices — https://skillselion.com/skills/calesthio/openmontage/flux-best-practices

> Найденные источники:
>   - Multimodal Models — https://skills.sh/eyadsibai/ltk/multimodal-models
>   - Writing a Good Prompt for SDXL and LoRA Models — https://www.scenario.com/post/writing-a-good-prompt-for-sdxl-and-lora-models
>   - Prompting People: How to Write Strong Prompts & Negative Prompts — https://zencreator.featurebase.app/en/help/articles/12021250-prompting-people-how-to-write-strong-prompts-and-negative-prompts
>   - writing a good prompt for sdxl and lora models — https://help.scenario.com/writing-a-good-prompt-for-sdxl-and-lora-models
>   - sdxl prompt — https://stable-diffusion-art.com/sdxl-prompt/
>   - getting started with obsession illustriousxl v10 mastering anime semi realistic — https://aiindigo.com/tutorials/getting-started-with-obsession-illustriousxl-v10-mastering-anime-semi-realistic
>   - getting started with obsession illustriousxl v10 mastering anime semi realistic — https://aiindigo.com/tutorials/getting-started-with-obsession-illustriousxl-v10-mastering-anime-semi-realistic-

Вывод: **один и тот же текст промпта на трёх моделях давать нельзя**, иначе тест будет нечестным. Правила у них разные. Почти всё ниже взято из блогов и гайдов (fal.ai, Qubrid, deAPI и других). Единственный официальный источник это документация Black Forest Labs по FLUX.2. Поэтому считайте советы гипотезами для проверки.

**Как их правильно промптить**

| | SDXL | Z-Image Turbo | FLUX.2 klein 4B |
|---|---|---|---|
| Стиль текста | структурированные фразы, теги допустимы | связный описательный текст, длинный (сотни слов допустимы) | художественная проза, как «романист», а не список тегов |
| Негативный промпт | работает и помогает, но короткий | **не работает** в официальном конвейере, `guidance=0` | в API нет; для локального klein **проверить** по карточке |
| Порядок | субъект, детали, стиль | 6 частей: субъект, сцена, свет, стиль, камера, настроение | **главное в начале**, модель сильнее смотрит на первые слова |
| Ограничения «без X» | в негативе | только внутри позитивного промпта | то же |
| Разрешение | родные SDXL (1024x1024 и т. п.) | 1024 | 1024 |
| Особенность | LoRA до 0,6-0,9, ControlNet | по умолчанию тянет к «глянцевому стоковому фото», стиль надо задавать явно; лучше 3-5 ключевых образов | нет автоулучшения промпта, всё пишете сами; поддерживает 1-4 референсных картинки |

**Что это значит для нашего проекта**
1. **Наш шаблон («no text, no watermark, not photorealistic») нужно переписать под каждую модель.** Для Z-Image и klein отрицания внутри позитивного текста могут сработать наоборот (модель видит слово «text»). Это мой вывод по логике, в источниках прямо не подтверждено, поэтому проверить в тесте: один вариант с отрицаниями, один с позитивной формулировкой («clean unlabelled surfaces, plain background»).
2. **Z-Image по умолчанию склонен к фотореализму.** Для иллюстраций стиль («gouache field-guide plate, ink contour, flat colors») ставим в начало, а не в конец.
3. **Для SDXL анатомию лучше ловить негативом** («extra limbs, fused legs, duplicate subject, text, watermark») и стилевой LoRA.
4. **Постоянство существ:** SDXL через LoRA/IP-Adapter, klein через референсные картинки, Z-Image через img2img от «эталонного» кадра. У Z-Image в источниках упоминается ControlNet, но T4-рецепта нет.

**Тест промптов (добавить к бейкоффу)**
Одно существо, три формулировки на модель, все с одинаковым seed и 12 сценами:
- **A, теги:** `field guide illustration, six-legged grazer, side view, gouache, teal and bone palette` + негатив (только SDXL).
- **B, проза:** «A natural-history plate showing a six-legged moss-backed grazer in profile, painted in flat gouache with ink contours, muted teal and pale bone palette, plain parchment background.»
- **C, проза с ключевым в первых словах:** то же, но анатомия (шесть ног, одна голова, два рога) первой фразой.
Считать по той же рубрике артефактов 0-2. Победитель выбирается по связке «модель + стиль промпта», а не по модели отдельно.

**Чего не знаю:** ни один источник не сравнивал эти три модели на иллюстрациях существ с подсчётом ошибок. Все советы «длинный промпт лучше» это опыт отдельных авторов. Решит ваш тест и ваш глаз.

Когда придёт ответ агента по S1, пришлите отчёт. Дам готовый промпт для Kilo на тест формулировок A/B/C.

---

### [15] ВЫ · 2026-10-21 06:14 UTC

*[приложен файл: 1000265156.jpg]*

*[изображение: скриншот/фото от пользователя]*

---

### [16] CLAUDE · 2026-10-21 06:14 UTC

**OpenCode (S2) сработал честно, но замера спроса нет: YouTube API исчерпал дневную квоту поиска.** Агент не стал выдумывать цифры и записал все 5 ниш как «NOT_MEASURED, n=0». Это правильно: n=0 не означает «спроса нет».

**Что подтверждено**
- Ошибка 429 `quotaExceeded` для `Search queries per day` (проект Google, 21 окт). Локальный счётчик показывал 0/100 и не отражал реальную квоту Google. Та же блокировка уже была 20 окт.
- Политика YouTube прочитана агентом с официальных страниц: шаблонные ИИ-картинки без оригинального содержания рискуют монетизацией; явно нереалистичные иллюстрации раскрытия не требуют, фотореалистичные требуют. Это совпадает с двумя отчётами.
- Секреты не печатались, коммитов нет, `docs/` и `.kilo/` не тронуты.

**Что делать**
1. **Квота сбросится в полночь по тихоокеанскому времени.** У вас это примерно 13:00-14:00 по Алматы, то есть уже скоро (сегодня, не завтра). После этого перезапустить S2 с тем, что собрано.
2. **Экономьте квоту:** `search.list` стоит 100 единиц, а дневной лимит 10 000, то есть около 100 поисков. Агент уже использует плейлисты загрузок (1 единица), но кандидатов находит именно поиск. Для S2 хватит 50-60 поисков на 5 ниш, если больше ничто не расходует ту же квоту параллельно.
3. **Можно запросить увеличение квоты** в Google Cloud (форма аудита), но это долго и для вас не нужно.

**Промпт для перезапуска после сброса квоты (в окно OpenCode):**

```text
S2 resume. Quota should have reset. Do NOT redo completed work (policy snapshot S6 is done). Read reports/S2_STATE.md first. Run ONE test search; if 429 again, stop and report, do not retry. If OK, run the collection with a hard cap of 50 search.list calls total (10 per niche), cache everything, use uploads playlists for channel history. Then redo S1-S5 and S7 from real data only, mark n<5 NOISE, no recommendation without measured numbers. Final report max 12 lines, end with cp commands for docs/openmontage/audit/demand/.
```

**Параллельно:** Kilo всё это время строит картинки (S1), ему квота YouTube не нужна. Когда он отчитается, пришлите скриншот.

На скриншоте также видно `docs/openmontage/slice/apollo9/renders/*.mp4` и `.wav` как неотслеживаемые файлы (`??`). Это крупные медиа, которые нельзя коммитить, а они занимают диск. Если место заканчивается, это первое, что стоит удалить (после проверки, что манифесты сохранены).

---

### [17] ВЫ · 2026-10-21 06:15 UTC

Дай тогда промп чтобы опенкод вместе с кило код стороил фабрику

---

### [18] CLAUDE · 2026-10-21 06:15 UTC

Раньше OpenCode был ограничен папкой `youtube-niche-finder/`. Чтобы он строил фабрику вместе с Kilo, даём ему **свои отдельные папки в репозитории**, которые Kilo не трогает. Так они не будут править одни файлы. Квоту YouTube он не тратит.

**Распределение**
- **Kilo (S1):** `tools/kaggle_bridge`, `tools/qa`, `tools/audio`, `scripts/run_episode.py`, генерация картинок, стиль-библия, пилотный сценарий №1, `.kilo/`.
- **OpenCode (новое):** `tools/prompting/`, `scripts/score_rubric.py`, `docs/openmontage/niches/speculative_evolution/creatures/`, `docs/openmontage/evidence/spec_evo/`, его отчёты в `youtube-niche-finder/reports/`.

**Промпт для OPENCODE (вставлять в окно OpenCode)**

```text
MILESTONE S3 (OpenCode) - build alongside Kilo. Niche: speculative evolution / alien ecosystems, AI stills only. Do NOT redo completed work; read reports/S2_STATE.md and docs/openmontage/S1_STATE.md (read-only) first. Do NOT use YouTube search calls today (quota exhausted).
OWNERSHIP (hard rule): you may create/edit ONLY: tools/prompting/, tests/prompting/, scripts/score_rubric.py, tests/test_score_rubric.py, docs/openmontage/niches/speculative_evolution/creatures/, docs/openmontage/evidence/spec_evo/, docs/openmontage/image_gen/PROMPT_TEST_PLAN.md, and youtube-niche-finder/reports/. NEVER touch tools/kaggle_bridge, tools/qa, tools/audio, scripts/run_episode.py, .kilo/, AGENTS.md, .env*, or any file Kilo is editing. If you need a change there, write it as a request in docs/openmontage/OPENCODE_REQUESTS.md instead.
GIT: commit only your own paths (never git add -A), git pull --rebase (stash if dirty), push non-force, never commit media or secrets. Roles inline: say "inline, not independent". No secrets printed, no paid routes. Stop if free disk < 800 MB. State file: reports/S3_STATE.md; resume at first unfinished task. Test-first for code. Final report max 12 lines (Status, Commit, Done, Failed, Owner decision, Next action).

S3-1 PROMPT BUILDER (test-first): tools/prompting/ renders one creature/scene spec (YAML: subject, anatomy spec with limb/eye/horn counts, environment, light, style, palette, camera, constraints) into model-specific prompts for three targets:
 - sdxl: structured phrases + SEPARATE negative prompt (extra limbs, fused legs, duplicate subject, text, watermark, photorealism).
 - zimage: descriptive prose, style stated FIRST (model defaults to glossy stock-photo look), 3-5 key visual concepts, NO negative prompt, constraints phrased positively inside the prompt; guidance 0, 9 steps.
 - klein: narrative prose, most important content (subject + anatomy) in the FIRST sentence, no negative prompt, constraints phrased positively; 4 steps.
 Each target supports 3 variants: A tags, B prose, C prose with anatomy first, plus a negation-style vs positive-style switch for the "no text" constraint. Tests: determinism, word order (anatomy first in C), no negative_prompt emitted for zimage/klein, anatomy counts always present, no real people/brands/logos allowed, output length bounds. Source notes with URLs (official BFL prompting guide docs.bfl.ai; Z-Image/SDXL guides) in tools/prompting/SOURCES.md; label vendor-official vs blog claims.
S3-2 PROMPT TEST PLAN: docs/openmontage/image_gen/PROMPT_TEST_PLAN.md: 12 fixed scenes x 3 models x variants A/B/C, same seeds, blind naming scheme (neutral IDs + separate mapping file), run matrix as a JSON file that Kilo's bridge job can read (document the schema; do not edit Kilo's code).
S3-3 RUBRIC SCORER (test-first): scripts/score_rubric.py ingests a CSV of owner/reviewer scores (anatomy, geometry, count/relation, texture, text, usefulness, each 0-2), outputs per model x variant: severe-artifact rate (numerator/denominator), repair burden, usable share, and a winner table; handles two reviewers, flags disagreement >1, never declares a winner with <24 images per cell (prints "INSUFFICIENT").
S3-4 CREATURE SPECS: docs/openmontage/niches/speculative_evolution/creatures/ - 6 YAML specs for the pilot "life beneath a frozen alien ocean" (3 species, 2 habitats, 1 food-web plate): written anatomy (counts), function of each feature, energy source, pressure/temperature constraint, canonical silhouette description, KNOWN/INFERENCE/SPECULATION tag per trait. Real-science principles only from retrieved pages with URLs (NASA/ESA/university/peer-reviewed), no facts from memory.
S3-5 FACT PACKS for pilots 2 and 3 (Kilo does pilot 1): docs/openmontage/evidence/spec_evo/pilot2_no_land_ocean_world.md and pilot3_low_gravity_flying_food_web.md: 25-30 claims each, source URL + section, TWO_SOURCES vs SINGLE_SOURCE, contradictions, paraphrase only.
S3-6 CLOSE: update reports/S3_STATE.md, append your commit hashes and open requests to docs/openmontage/OPENCODE_REQUESTS.md, print the exact commands the owner should run (none destructive).
```

**Что сказать Kilo (одной строкой в его окно, чтобы учёл):**

```text
Note from owner: OpenCode now owns tools/prompting/, scripts/score_rubric.py, niches/speculative_evolution/creatures/ and evidence/spec_evo/. Do not edit them. When S1-1/S1-2 are ready, read docs/openmontage/image_gen/PROMPT_TEST_PLAN.md and use its run matrix and tools/prompting for the A/B/C prompt variants if it exists; otherwise continue as planned. Requests for you appear in docs/openmontage/OPENCODE_REQUESTS.md.
```

**Что ещё нужно от вас**
1. Перед запуском проверьте диск (`df -h /workspaces`). Если меньше 1,5 ГБ, удалите медиа `docs/openmontage/slice/apollo9/renders/` и промежуточные рендеры (они не в git).
2. Квота YouTube сбросится в полдень-вечер по Алматы. Тогда отдельно перезапустите S2 (промпт я давал выше).

---

### [19] ВЫ · 2026-10-21 06:32 UTC

*[приложен файл: 1000265165.jpg]*

*[приложен файл: 1000265166.jpg]*

*[изображение: скриншот/фото от пользователя]*

*[изображение: скриншот/фото от пользователя]*

---

### [20] CLAUDE · 2026-10-21 06:32 UTC

**Оба агента отчитались честно: Z-Image на Kaggle ещё считается, а OpenCode закончил всё, что мог без GPU.**

**Kilo (S1, коммит `8fb4b95`)**
- **S1-1:** Z-Image-Turbo запущен на Kaggle, это уже 4-я отправка. Первые три упали на конфликтах версий (transformers и hub). Результата пока нет.
- **Готово:** стиль-библия, YAML ниши и метка «Speculative illustration» (6 тестов). Пилотный сценарий «жизнь под ледяным океаном»: 13 утверждений (8 известных, у каждого два источника NASA/NOAA/Smithsonian; 5 спекуляций с обоснованием), `claim_ids` 48/48. Каркас сборки с тестами, всего 16 проходят.
- **Не сделано:** S1-2 (слепое сравнение) и S1-5 (сборка ~80 картинок) ждут результата Kaggle.
- **Риск:** установка «diffusers main» не закреплена на конкретном коммите, поэтому завтра этот же ноутбук может сломаться. Попросите зафиксировать версии.

**OpenCode (S3, коммит `7fe8d10`)**
- Построил генератор промптов под SDXL, Z-Image и klein (19 тестов), план теста 12 сцен × 3 модели × 3 варианта = 108 задач с слепыми ID, скорер по рубрике (9 тестов), 6 спецификаций существ, два пакета фактов (27 и 26 утверждений). Всего 28 тестов проходят.
- Папки Kilo не трогал, работает по правилу разделения.

**Одна ошибка в плане, которую надо исправить:** 108 задач дают всего 12 картинок на ячейку, а скорер требует минимум 24 и напишет «INSUFFICIENT». Нужно 2 seed на сцену, то есть 216 задач. Для Z-Image на T4 это терпимо по времени, но проверим после первого замера скорости.

**Ещё два замечания**
- `git pull --rebase` пропущен из-за грязного файла Kilo, так что проверьте `git status` и что коммиты запушены.
- Квота YouTube сбросится в полночь по тихоокеанскому времени, это около **12:00 по Алматы** (раньше я назвал неверное время). Тогда можно запускать S2.

**Что сделать сейчас**
1. Ничего не запускайте на Kaggle параллельно, пока Z-Image идёт.
2. Одобрить матрицу, но увеличить до 24 на ячейку.

Короткое сообщение для Kilo (когда он освободится):

```text
Owner: approve OpenCode's prompt-test matrix but change it to 2 seeds per scene (216 jobs, 24 images per cell) so the scorer is not INSUFFICIENT. Order of runs, one model per kernel: Z-Image-Turbo (running), then SDXL Base with madebyollin/sdxl-vae-fp16-fix, then FLUX.2 klein 4B. Pin exact versions of diffusers/transformers/huggingface_hub (commit hash for diffusers) in the kernel and record them in the manifest. fp16 only, fail loudly if images < prompts. One status call between phases, no polling loops.
```

Когда придёт результат Z-Image, пришлите скриншот и контакт-лист. Вы смотрите картинки глазами, это главный критерий.

---

### [21] ВЫ · 2026-10-21 06:39 UTC

*[приложен файл: 1000265173.jpg]*

*[изображение: скриншот/фото от пользователя]*

Дай промп для кило код чтобы он проверил те 3 моделей и изучил как им давать промпты и проверил

---

### [22] CLAUDE · 2026-10-21 06:39 UTC

Z-Image у Kilo сейчас на 6-й попытке. Промпт ниже не прерывает его, а продолжает после результата. Добавлено правило остановки: после 2 неудачных попыток на модель она получает статус BLOCKED, чтобы не тратить часы Codespaces на борьбу с зависимостями.

```text
MILESTONE S4 (Kilo) - test the 3 models and verify how to prompt them. Do NOT redo completed work. Read docs/openmontage/S1_STATE.md, docs/openmontage/OPENCODE_REQUESTS.md, docs/openmontage/image_gen/PROMPT_TEST_PLAN.md, tools/prompting/SOURCES.md first. Do NOT resubmit the Z-Image kernel while it is RUNNING: one status call, then work on other phases.
Scope: docs/ tools/ (except tools/prompting/ and scripts/score_rubric.py, which OpenCode owns: use them, do not edit; write change requests to docs/openmontage/OPENCODE_REQUESTS.md) scripts/ tests/ .kilo/. No secrets printed, no paid routes, never loop on Kaggle status, stop if free disk < 800 MB. Commit own paths only, never media. Roles inline. State file docs/openmontage/S4_STATE.md; resume at first unfinished phase. Final report max 12 lines (Status, Commit, Done, Failed, Owner decision, Next action).
STOP RULE: max 2 fix attempts per model; after that mark the model BLOCKED with the exact error, versions and traceback path, and move on. Do not chase dependency conflicts for hours.

S4-1 VERIFY PROMPTING CLAIMS FROM OFFICIAL SOURCES: read the official cards/docs (Tongyi-MAI/Z-Image-Turbo card and the diffusers z_image docs; docs.bfl.ai prompting guide for FLUX.2 and the FLUX.2-klein-4B card; stabilityai SDXL card). Table in docs/openmontage/image_gen/PROMPTING_FACTS.md: per model, official recommended steps, guidance, negative prompt supported (yes/no/UNKNOWN), prompt length limits, word-order advice, with URL and access date. Mark blog-only claims as UNVERIFIED. Specifically check whether FLUX.2-klein-4B (local diffusers pipeline) honours guidance_scale and negative prompts.
S4-2 RUN ORDER (one model per kernel, fp16 only, no bitsandbytes, no CPU fallback, non-zero exit if images < prompts, tracebacks saved, versions pinned and written into the manifest): 1) Z-Image-Turbo (running), 2) SDXL Base + madebyollin/sdxl-vae-fp16-fix, 3) FLUX.2-klein-4B. Each uses the run matrix from OpenCode (tools/prompting renders the prompts) with the owner's change: 2 seeds per scene so each cell has 24 images (12 scenes x 2 seeds x 3 prompt variants A/B/C = 72 images per model). Record per model: load time, steady seconds/image, peak VRAM, OOM/NaN/black-image count, usable images per minute.
S4-3 PROMPT-RULE EXPERIMENTS (small, on the same seeds, 6 scenes): (a) Z-Image: with vs without a negative_prompt argument (confirm it is ignored); negation phrasing ("no text") vs positive phrasing ("clean unlabelled surfaces, plain background"); style-first vs style-last. (b) klein: anatomy-first vs anatomy-last; guidance 1.0 vs the value the official card recommends if different. (c) SDXL: with vs without the short negative prompt. Report only objective counts: images with visible text-like artifacts via the QC detector, image-hash duplicates, blur score. Do NOT judge anatomy or beauty yourself; the owner judges.
S4-4 BLIND PACK FOR THE OWNER: contact sheets with neutral IDs (R001...), shuffled, one sheet per 12 images at readable size, plus a separate mapping file in projects/ (not committed). Create the CSV template for scores (header: render_id,model,variant,reviewer,anatomy,geometry,count_relation,texture,text,usefulness; mapping columns filled only after scoring) compatible with scripts/score_rubric.py. Run the scorer on a dummy CSV to prove the pipeline works.
S4-5 REPORT docs/openmontage/image_gen/MODEL_BAKEOFF_REPORT.md: observed vs assumed, speed/VRAM table, which prompt rules were confirmed or refuted with the counts, BLOCKED models with causes, and what the owner must do (score the sheets). No winner declared by the agent.
S4-6 CLOSE: update S4_STATE.md, CHANGELOG, LESSONS (include the dependency-conflict lesson and the pinning rule); print stop-Codespace commands.
```

**Что делать вам, пока он работает**
- Ничего тяжёлого на Codespace не запускайте. Следите за диском (сейчас около 2,8 ГБ).
- Когда придут контакт-листы, смотрите их сами и ставьте оценки 0-2 по шести пунктам. Если оценивать вручную 216 картинок слишком много, начните с 12 сцен × 1 вариант промпта на модель, а остальное оставьте на потом.

---

### [23] ВЫ · 2026-10-21 06:48 UTC

*[приложен файл: 1000265174.jpg]*

*[приложен файл: 1000265175.jpg]*

*[изображение: скриншот/фото от пользователя]*

*[изображение: скриншот/фото от пользователя]*

Жёлтый это кило а второй опенкод и скажи какой самый лучший модел

---

### [24] CLAUDE · 2026-10-21 06:48 UTC

Да, жёлтая подсветка это Kilo (список с пометками «May train»), второй экран это OpenCode.

**Лучшая модель сейчас: Nemotron 3.5 Super VL (free), и в Kilo, и в OpenCode.** Менять её не советую, и вот почему:
- На ней агенты прошли все наши вехи (S1, S2, S3) с честными отчётами: остановились на блокере, не выдумали цифры, не вышли за свои папки.
- Она единственная из списка с поддержкой изображений. Это нужно для проверки контакт-листов и скриншотов.
- Это мой практический вывод, а не бенчмарк. Для сравнения моделей на агентных задачах у меня есть только самоотчёты разработчиков.

**Что видно в списках**
- **Laguna S 2.1** пригодна для кода и тестов, но по данным рейтинга Kilo её уберут около 31 октября. Строить на ней процесс нельзя.
- **Seed 1.6 Flash** в Kilo помечена «retires Nov 11».
- **Auto Free** это роутер: непонятно, какая модель ответит, для длинных вех не годится.
- **Reflection Beam 1.0** (в OpenCode просто «Beam») совсем свежая, независимых оценок я не нашёл.
- Про **GLM-5.3-Flash, MiMo-V2.6-Flash, DeepSeek V4.1 Flash, LongCat 2.5 Preview** в OpenCode у меня нет проверенных данных. Рейтинг по ним я бы выдумал, поэтому не буду.
- У всех бесплатных моделей в Kilo стоит «May train»: запросы могут использоваться для обучения. Секреты и токены агентам не давайте (мы и так этого не делаем).

**Что делать**
1. Сейчас идёт Z-Image на Kaggle, а Kilo выполняет S4. Модель посреди вехи не меняйте, иначе станет непонятно, что сломалось.
2. Если хотите выбрать лучшую по-настоящему, сделайте тест после S4: одну небольшую задачу (например, «исправь баг по описанию и напиши тесты сначала») дайте по очереди Nemotron 3.5 Super VL и одной из новых (DeepSeek V4.1 Flash или GLM-5.3-Flash). Сравните: тесты написаны первыми? отчёт честный? вышла ли модель за свои папки?
3. Если хотите, я отдельно найду в интернете отзывы и бенчмарки по этим четырём новым моделям. Скажите, и я посмотрю.

---

### [25] ВЫ · 2026-10-21 07:19 UTC

*[приложен файл: 1000265194.jpg]*

*[изображение: скриншот/фото от пользователя]*

---

### [26] CLAUDE · 2026-10-21 07:19 UTC

**Z-Image заблокирован ошибкой установки, а не качеством модели. SDXL сейчас идёт на Kaggle, klein следующий.**

**Что в отчёте Kilo (коммит `e8ff692`)**
- **Готово:** проверенные по официальным источникам правила промптинга (`PROMPTING_FACTS.md`), матрица на 216 задач (по 24 на ячейку), универсальный раннер с pinned-версиями, проверка правил промптов 12/12, скорер проверен на пробном CSV.
- **Z-Image: BLOCKED.** 5+ попыток, ошибка `Failed to import diffusers.pipelines.z_image.pipeline_z_image`. Причина: конфликт `transformers 5.x` и `diffusers` из git main. Трассировка сохранена.
- **SDXL:** запущен на Kaggle с релизной версией diffusers (вторая попытка).
- **Картинок пока нет**, поэтому S4-2, S4-4 и S4-5 ждут.

**Моя гипотеза по Z-Image (не проверена):** ChatGPT-отчёт ссылается на `ZImagePipeline` в официальной документации diffusers, а релиз 0.41.0 вышел 6 октября. Скорее всего, git main был не нужен, и Z-Image заработает на том же релизном diffusers, что и SDXL. Попробуйте это перед тем, как сдаваться.

**Что сделать**
1. Внизу экрана «Отключено, повторное подключение». Нажмите «Перезагрузить окно». Задачи на Kaggle это не прерывает, а сессия агента может оборваться.
2. После перезагрузки спросите Kilo статус и дайте ему этот промпт:

```text
Resume S4. Read docs/openmontage/S4_STATE.md. One Kaggle status call for SDXL; do not resubmit it. Do not poll. When SDXL is COMPLETE: fetch output, verify job_id/sha256/bytes, make blind contact sheets. Then submit FLUX.2-klein-4B on the released diffusers (same pinned versions as the SDXL run). THEN retry Z-Image-Turbo ONCE with the same RELEASED diffusers and a matching transformers version (check that diffusers.ZImagePipeline exists in the released package before submitting: python -c "from diffusers import ZImagePipeline"). If it fails again, keep it BLOCKED and do not spend more attempts. Same rules as S4: fp16 only, no bitsandbytes, no CPU fallback, versions in manifest, stop if disk < 800 MB. Final report max 12 lines.
```

3. В `git status` видны неотслеживаемые `.opencode/`, `apollo_11.json`, `artemis_sls.json`, `cassini_saturn.json`, `dart_asteroid.json` в корне репозитория. Это, скорее всего, мусор от OpenCode или старых вех. В git их не добавляйте, пока не поймёте, откуда они (`git log -- apollo_11.json` ничего не покажет, если файл не отслеживается).
4. Диск проверьте (`df -h /workspaces`): сейчас около 2,8 ГБ, а картинки и кэши весов его съедят.

Когда придут картинки SDXL, пришлите скриншот или контакт-лист. Оценивать будете вы.

---

### [27] ВЫ · 2026-10-21 07:54 UTC

Почему модели блокнули?

---

### [28] CLAUDE · 2026-10-21 07:54 UTC

**Z-Image заблокировал не Kaggle, не лицензия и не владелец модели. Его заблокировал сам Kilo по нашему правилу остановки.**

**Что произошло**
- В промпте S4 я задал правило: максимум 2 попытки исправления на модель, потом статус BLOCKED, чтобы агент не тратил часы Codespaces на зависимости.
- Z-Image падал каждый раз с одной и той же ошибкой: `Failed to import diffusers.pipelines.z_image.pipeline_z_image`.
- Причина по отчёту: библиотеки несовместимы. `transformers 5.x` не работает с `diffusers` из git main, а Z-Image Kilo ставил именно из main.
- Агент исчерпал попытки и остановился. Трассировка сохранена в `/tmp/kilo/s1_output/s1-z-image-turbo-1`.

**Что это не значит**
- Это не значит, что модель плохая или не работает на T4. Мы её вообще ещё не запустили.
- Лицензия в порядке: Apache-2.0, проверено по официальной карточке в S1.
- SDXL и FLUX.2 klein не заблокированы. SDXL сейчас идёт на Kaggle, klein ждёт очереди.

**Что сделать**
Одна повторная попытка на релизной версии diffusers (не из git main). Если в релизе есть `ZImagePipeline`, должно заработать. Это моя гипотеза, не проверенный факт. Промпт для этого я дал в прошлом сообщении (блок «Resume S4»). Если и он провалится, Z-Image остаётся заблокированным, и мы сравниваем два оставшихся: SDXL и klein.

Если вы имели в виду другие заблокированные модели (например, из G2: FLUX уходил в нехватку памяти, SDXL-Lightning работал), напишите, какие именно.

---

### [29] ВЫ · 2026-10-21 07:55 UTC

Скажи minimax m3.1 flash лучше модели который мы используем сейчас по бенчмаркам

---

### [30] CLAUDE · 2026-10-21 07:55 UTC

Проверяю независимые бенчмарки обеих моделей.

> 🔎 Веб-поиск (standard): MiniMax M3.1 Flash benchmarks SWE-bench Terminal-Bench

> 🔎 Веб-поиск (standard): MiniMax M3.1 Flash vs Nemotron 3.5 Super comparison Artificial Analysis intelligence index

> Найденные источники:
>   - minimax m3 1 flash vs swe 1 7 — https://benchlm.ai/compare/minimax-m3-1-flash-vs-swe-1-7
>   - minimax m3 1 flash preview vs swe 1 7 — https://benchlm.ai/compare/minimax-m3-1-flash-preview-vs-swe-1-7
>   - minimax m3 1 flash release — https://www.marktechpost.com/2026/10/19/minimax-m3-1-flash-release/
>   - MiniMax M3vsStep 3.7 Flash — https://www.datalearner.com/en/ai-models/compare/minimax-m3/vs/step-3-7-flash
>   - Model comparison — https://benchlm.ai/compare/gemini-3-flash-vs-minimax-m3
>   - # DeepSeek V4.1 Flash vs MiniMax M3 — https://benchlm.ai/md/compare/deepseek-v4-1-flash-vs-minimax-m3.md
>   - # Gemini 3 Flash vs MiniMax M3 — https://benchlm.ai/md/compare/gemini-3-flash-vs-minimax-m3.md
>   - # Gemini 3.5 Flash-Lite vs MiniMax M3 — https://benchlm.ai/md/compare/gemini-3-5-flash-lite-vs-minimax-m3.md
>   - # Gemini 3.6 Flash vs MiniMax M3 — https://benchlm.ai/md/compare/gemini-3-6-flash-vs-minimax-m3.md
>   - # MiniMax M3 vs Qwen3.8-Omni-Flash — https://benchlm.ai/md/compare/minimax-m3-vs-qwen3-8-omni-flash.md

> Найденные источники:
>   - Compare AI models: MiniMax-M3.1-Flash-Preview vs Nemotron 3.5 Super VL 120B A12B — https://opencode.ai/data/compare/minimax/minimax-m3-1-flash-preview/nvidia/nemotron-3-5-super-vl-120b-a12b
>   - All Models — https://artificialanalysis.ai/models/comparisons/nemotron-3-5-super-vl-vs-minimax-m3
>   - Compare AI models: MiniMax-M3.1-Flash-Preview vs Nemotron 3.5 Lightning 30B A3B — https://opencode.ai/data/compare/minimax/minimax-m3-1-flash-preview/nvidia/nemotron-3-5-lightning
>   - Compare AI models: MiniMax-M3.1-Flash vs Nemotron 3.5 Lightning 30B A3B — https://opencode.ai/data/compare/minimax/minimax-m3-1-flash/nvidia/nemotron-3-5-lightning
>   - Compare AI models: MiniMax-M3.1-Flash vs nemotron-3-ultra — https://opencode.ai/data/compare/minimax/minimax-m3-1-flash/nvidia/nemotron-3-ultra
>   - The AI arena is free today — https://llm-stats.com/models/compare/minimax-m3.1-flash-vs-nemotron-3.5-super-vl-120b-a12b
>   - MiniMax-M3とNemotron 3 Super 120B A12B (Reasoning) — https://artificialanalysis.ai/ja/models/comparisons/minimax-m3-vs-nvidia-nemotron-3-super-120b-a12b
>   - MiniMax-M3 vs. Nemotron 3 Super 120B A12B (Reasoning) — https://artificialanalysis.ai/ko/models/comparisons/minimax-m3-vs-nvidia-nemotron-3-super-120b-a12b
>   - The AI arena is free today — https://llm-stats.com/models/compare/minimax-m3.1-flash-vs-nemotron-3.5-bolt-74b-a9b-24gb
>   - MiniMax-M3とGemini 3.5 Flash (minimal) — https://artificialanalysis.ai/ja/models/comparisons/minimax-m3-vs-gemini-3-5-flash-minimal

**Коротко: по бенчмаркам нельзя сказать, что MiniMax M3.1 Flash лучше Nemotron 3.5 Super VL. Прямого сравнения этих двух я не нашёл.**

**Что известно про M3.1 Flash**
- Выпущена около 19 окт. Цифры публикует сам MiniMax (MarkTechPost пересказывает их таблицу), независимых замеров не нашёл.
- Лучший результат по их данным: Automation-Bench 62.2 и LOCA-Bench 256K 60.3.
- Слабое место: Terminal Bench 4.0 всего 38.1 (у Opus 5 51.8), SWE Refactor Bench 23.0 против 31.0. Terminal Bench это как раз ближе всего к работе нашего агента в терминале.
- Принимает текст, изображения и видео, контекст 1M токенов.
- В самой таблице MiniMax есть расхождение (62.2 против 62.8 на графике), так что к цифрам осторожно.

**Что известно про Nemotron 3.5 Super VL**
- Оценки Nemotron в моих прошлых ответах тоже в основном от NVIDIA (самоотчёты) и по другим версиям тестов (Terminal-Bench 2.1, SWE-Bench Pro).
- На сайтах сравнения (benchlm, OpenCode data) для пары M3.1 Flash и Nemotron 3.5 Super VL стоят нейтральные заглушки «no comparable benchmark». То есть данных для вывода нет.

**Почему сравнение невозможно**
- Версии тестов разные: у Flash Terminal Bench 4.0, у Nemotron 2.1. Цифры из разных версий сравнивать нельзя.
- Независимый индекс Artificial Analysis показывает, что обычная MiniMax-M3 умнее старой Nemotron 3 Super. Но это не Flash и не 3.5 Super VL, так что к нашему вопросу не относится.

**Практически важное**
- В Kilo Flash отмечена «(free)» и «May train», как и остальные. Платный API стоит $0.15 за миллион входных токенов, поэтому проверьте, что в вашем меню она действительно бесплатная, иначе нарушим режим $0.
- Для нашей работы важнее не бенчмарки, а три вещи: тесты написаны первыми, честный отчёт и выход за рамки папок. Nemotron это показала на трёх вехах, у Flash у нас пока нет ни одного прогона.

**Что делать**
Не менять модель посреди S4. Когда Kilo закончит, дайте одну и ту же небольшую задачу двум моделям по очереди (например, «добавь в `score_rubric.py` проверку на дубликаты render_id, тесты первыми») и сравните: красные тесты показаны, отчёт честный, чужих файлов не тронуто, сколько времени ушло. Для OpenCode можно так же проверить Flash, но по тому же принципу, не на длинной вехе.

---

### [31] ВЫ · 2026-10-21 08:05 UTC

Дай промп чтобы агент всё 3 модели проверил на генераций 10 фото и без остановки проверяют мне нужен самый лучший вариант

---

### [32] CLAUDE · 2026-10-21 08:05 UTC

Важное уточнение: «без остановки» я понимаю так, что агент **не ждёт вас между моделями и не бросает весь прогон из-за одной упавшей модели**. Лимит на попытки оставляю (2 исправления на модель), иначе он снова сожжёт часы Codespaces на зависимостях. И агент сам лучшую не выберет: качество картинок оцениваете вы по слепому листу.

```text
MILESTONE S5 (Kilo) - 10-image bake-off of the 3 models, run end to end WITHOUT waiting for the owner. Do NOT redo completed work. Read docs/openmontage/S4_STATE.md, docs/openmontage/image_gen/PROMPTING_FACTS.md, tools/prompting/ (OpenCode-owned: use, do not edit). Reuse the SDXL job if it already COMPLETED (fetch its output instead of resubmitting).
Scope: docs/ tools/ (not tools/prompting/, not scripts/score_rubric.py) scripts/ tests/ .kilo/. No secrets printed, no paid routes, no bitsandbytes, no CPU fallback, fp16 only, versions pinned in each manifest, never loop on Kaggle status (one status call between phases, do other work meanwhile), stop only if free disk < 800 MB. Commit own paths only, never media. Roles inline. State file docs/openmontage/S5_STATE.md; resume at first unfinished phase. Final report max 12 lines.
NEVER-STOP RULE: if one model fails, mark it BLOCKED with the exact error and continue with the next model. Max 2 fix attempts per model. The run ends only when all 3 models are DONE or BLOCKED and the blind pack exists.

S5-1 FIXED TEST SET: 10 scenes (from the 12 in PROMPT_TEST_PLAN.md drop 2 easiest), 1 seed each (same seed per scene across models), 1024x1024, one prompt variant per model = the best variant per official PROMPTING_FACTS (SDXL: structured + short negative prompt; Z-Image: prose, style first, no negative; klein: prose, anatomy first, no negative). Render prompts with tools/prompting. Also save the neutral variant "same text for all" for 3 scenes as a fairness check if time allows.
S5-2 RUN ORDER (one model per kernel, submit back-to-back, one status call between phases): SDXL Base + madebyollin/sdxl-vae-fp16-fix (reuse if done); FLUX.2-klein-4B (released diffusers, fp16, enable_model_cpu_offload if OOM); Z-Image-Turbo (check python -c "from diffusers import ZImagePipeline" in the kernel BEFORE generating; use the RELEASED diffusers with a matching transformers; if import fails after 2 attempts => BLOCKED). Per model record: load time, seconds/image steady state, peak VRAM, black/NaN/OOM count, exact versions.
S5-3 OBJECTIVE CHECKS (no aesthetic judgement): Laplacian blur score, text-like artifact detector, perceptual-hash duplicates, resolution; flag only. Anatomy and beauty are judged by the owner.
S5-4 BLIND PACK in projects/s5_blind/ (gitignored): (a) per-scene comparison sheets: for each of the 10 scenes one image with 3 panels labelled A/B/C in random order per scene (mapping saved separately in projects/s5_blind/mapping.json, never shown); (b) a CSV template (scene, best_panel A|B|C, worst_panel, comment, anatomy_ok_A/B/C yes|no) the owner fills by tapping through the sheets on a phone. Make images readable on a phone (max 1600 px wide).
S5-5 RESULT HELPER script (test-first, small): scripts/s5_tally.py reads the filled CSV + mapping, prints per model: wins, losses, anatomy-ok count out of 10, plus speed/VRAM table, and says "TIE" if the best two differ by <=1 win. It prints the recommended model ONLY from the owner's CSV, never from its own opinion.
S5-6 REPORT docs/openmontage/image_gen/BAKEOFF_S5.md: observed vs assumed, speed/VRAM table, BLOCKED causes, owner instructions (open the sheets, fill the CSV, run the tally). Update S5_STATE.md, LESSONS.md; print stop-Codespace commands.
```

**Что делать вам, когда агент закончит**
1. Откройте листы `projects/s5_blind/` (через порт 8080, как раньше видео).
2. Для каждой из 10 сцен выберите лучшую панель A/B/C и отметьте, где анатомия сломана. Это около 5-10 минут.
3. Передайте CSV агенту, он покажет итог по вашим же оценкам.

**Чего ждать честно:** 10 картинок на модель это быстрый отсев, а не доказательство. Если две модели близки (разница в одну победу), агент напишет «TIE», и нужно будет дотестировать ещё 24 картинки на ячейку по большой матрице.

---

### [33] ВЫ · 2026-10-21 09:01 UTC

Давай Ты изучил в интернете особенно в гитхабе ИИ модели для генерации фото которые быстрые и качественные и обновил топ 3

---

### [34] CLAUDE · 2026-10-21 09:02 UTC

Ищу свежие модели (2026) на GitHub и Hugging Face, которые я мог пропустить.

> 🔎 Веб-поиск (extended): best open source text-to-image model October 2026 fast Apache-2.0 new release

> 🔎 Веб-поиск (standard): Artificial Analysis text-to-image open weights leaderboard small model consumer GPU 16GB

> 🔎 Веб-поиск (standard): github new few-step image generation model 2026 Apache-2.0 T4 fp16 illustration

> Найденные источники:
>   - Best Open-Source Image Generation Models — https://www.thundercompute.com/blog/best-open-source-image-generation-models
>   - Boogu Image 0.1 Base fp8 — https://huggingface.co/Yanlis/Boogu-Image-0.1-Base-fp8
>   - LTX-2 — https://en.wikipedia.org/wiki/LTX-2
>   - The Best Open-Source Image Generation Models in 2026 — https://www.bentoml.com/blog/a-guide-to-open-source-image-generation-models
>   - Ideogram (text-to-image model) — https://en.wikipedia.org/wiki/Ideogram_(text-to-image_model)
>   - Boogu Image 0.1 Edit — https://huggingface.co/Nishant2414/Boogu-Image-0.1-Edit
>   - Boogu Image 0.1 Turbo fp8 — https://huggingface.co/Boogu/Boogu-Image-0.1-Turbo-fp8
>   - - Text-to-Speech (TTS) Models — https://github.com/0xSojalSec/free-voice-clone
>   - Flux (text-to-image model) — https://en.wikipedia.org/wiki/Flux_(text-to-image_model)
>   - Best Text-to-Image AI Models in 2026: 7 Tools Compared — https://futureagi.com/blog/text-to-photo-llm-2025/

> Найденные источники:
>   - Text to Image Leaderboard (Open Weights)Artificial Analysis — https://artificialanalysis.ai/image/leaderboard/text-to-image/open-weights
>   - text to image ai models — https://www.swiftask.ai/blog/text-to-image-ai-models
>   - best ai image models — https://techsy.io/nl/blog/best-ai-image-models
>   - Z-Image Turbo Review 2026: High-Quality AI on a 16GB VRAM GPU — https://saascrmreview.com/z-image-turbo-review/
>   - stable diffusion — https://howaiworks.ai/models/stable-diffusion.md
>   - best ai image models — https://techsy.io/en/blog/best-ai-image-models
>   - Z-Image Turbo Review 2026: High-Quality AI on a 16GB VRAM GPU — https://saascrmreview.com/?p=8069
>   - Jul 14, 2026 · 11:18 AM — https://startupfortune.com/open-weights-image-models-are-narrowing-the-quality-gap-with-paid-frontier-apis-and-the-founder-build-versus-buy-calculus-is-shifting-faster-than-most-roadmaps-assume/
>   - best free open source ai image generators to self host — https://pinggy.io/blog/best_free_open_source_ai_image_generators_to_self_host/

> Найденные источники:
>   - PixArt LCM XL 2 1024 MS — https://huggingface.co/PixArt-alpha/PixArt-LCM-XL-2-1024-MS
>   - 🌊 FluidAI-0.7B: The Fluidic Wave Architecture — https://huggingface.co/Jershone/FluidAI-0.7B_Gen1
>   - pinhole m — https://huggingface.co/nuhmanpk/pinhole-m
>   - license: apache-2.0 — https://huggingface.co/segmind/Segmind-Vega/blob/main/README.md
>   - license: apache-2.0 — https://huggingface.co/segmind/Segmind-Vega/blob/6041734f578752a9b40aa3ec20075251254a366b/README.md
>   - iris-image-gen / README.md — https://huggingface.co/asdf98/iris-image-gen/blob/main/README.md
>   - github.com — https://github.com/huggingface/diffusers/pull/5723/files

**Топ-3 я не меняю, потому что для новых моделей нет данных про T4 и лицензию. Но нашёл 4 новых кандидата, которых надо проверить до замены.** Всё ниже из блогов, Википедии и карточек на Hugging Face, официальные карточки я не открывал.

**Текущий топ-3 (без изменений)**
1. SDXL Base + стилевой LoRA: самый надёжный на T4, лучшие инструменты постоянства.
2. Z-Image Turbo: Apache-2.0, быстрый. Но у нас пока не запустился (конфликт версий).
3. FLUX.2 klein 4B: Apache-2.0, около 8-13 ГБ по заявлению производителя.

**Новые кандидаты**
- **Ideogram 4.0** (июнь 2026): по Википедии открыт под Apache-2.0, в рейтинге Artificial Analysis есть варианты «Fast» и «Instant». Размер и работа на T4 неизвестны. Версия 4.5 вышла 30 сентября, открыта ли она, не проверено.
- **Boogu-Image-0.1 Turbo** (июнь 2026): Apache-2.0, 4 шага, есть fp8. Авторы пишут, что это исследовательский проект, а не официальный релиз. Ориентироваться можно только на их собственные оценки.
- **Cosmos3-Super (NVIDIA)**: лидер среди открытых моделей по рейтингу Artificial Analysis (Elo около 1226 в июле). Модель «агентная» и, скорее всего, тяжёлая для T4. Лицензию не проверял.
- **Sana-Sprint 0.6B/1.6B**: очень быстрая (по NVIDIA, около секунды на 16 ГБ), но у веса Sana ранее была неясная лицензия, качество деталей ниже.
- **FLUX.3 klein** (по Википедии вышла 15 октября): подробностей, лицензии и требований к памяти нет. Не знаю, подходит ли она.

**Что остаётся неизвестным у всех:** реальная скорость на T4, частота артефактов на иллюстрациях существ. Рейтинги Artificial Analysis это человеческие предпочтения, а не доля артефактов, и они усреднены по общим картинкам.

**Моё предложение:** не расширять тест из трёх моделей, пока он не дал результат. После S5, если победитель не устроит вас глазами, подключим Ideogram 4.0 Fast и Boogu Turbo. Чтобы не тратить на это время потом, можно сейчас дать Kilo проверку без GPU, пока идёт Kaggle:

```text
MILESTONE S6 (Kilo) - read-only candidate check, NO Kaggle submissions, NO downloads of weights. Do not touch running jobs. Read OFFICIAL Hugging Face / GitHub cards only (no blogs) for: Ideogram 4.0 (Fast/Instant variants, and whether 4.5 is open), Boogu-Image-0.1-Turbo, FLUX.3 [klein] (small variant released 2026-10-15), Cosmos3-Super-Text2Image-4Step, Sana-Sprint. Per model: license text (quote, URL, date), gated yes/no, parameter count and total weight size, official dtype (bf16 vs fp16), stated VRAM, whether a diffusers pipeline exists in the RELEASED diffusers package (pip show / docs, not git main), any T4/fp16 reports. Write docs/openmontage/image_gen/CANDIDATES_S6.md with verdict per model: FITS_T4 | NEEDS_OFFLOAD | TOO_BIG | LICENSE_BLOCKED | UNKNOWN. Do not recommend a winner. Commit docs only; final report max 12 lines.
```

Что-то из этого я мог не найти: рынок моделей меняется каждые 4-6 недель (по отчёту StartupFortune). Если вы видели название модели в обсуждении, которого здесь нет, напишите его, проверю отдельно.

---

### [35] ВЫ · 2026-10-21 09:03 UTC

Дай промп чтобы агент запускал те топ 3 моделей до победного по очереди и потом в конце сам оценил скорость, качество и артефакты и потом я тоже сам оценю

---

### [36] CLAUDE · 2026-10-21 09:04 UTC

Две поправки к вашей идее, иначе прогон может сжечь часы Codespaces:
- **«До победного» с потолком.** Вместо 2 попыток даю 4 на модель, но после каждой неудачи агент обязан сменить подход (другие версии библиотек, offload, меньший шаг), а не повторять то же самое. Общий потолок по времени: 90 минут на модель. Если не вышло, BLOCKED с причиной, и он идёт дальше.
- **Оценка агента не заменяет вашу.** У Nemotron 3.5 Super VL есть зрение, поэтому он может смотреть картинки, но оценка будет помечена как «мнение агента, не независимо», и итог решаете вы. Объективные числа (скорость, память, размытие, дубликаты, артефакты текста) он считает сам.

```text
MILESTONE S7 (Kilo) - run the top 3 models in sequence until each produces 10 valid images, then self-assess, then hand over to the owner. This SUPERSEDES S5: if S5_STATE.md shows completed jobs (e.g. SDXL), reuse their outputs, do not resubmit. Do NOT redo completed work.
Scope: docs/ tools/ (not tools/prompting/, not scripts/score_rubric.py) scripts/ tests/ .kilo/. No secrets printed, no paid routes, no bitsandbytes, no CPU fallback, fp16 only, versions pinned in every manifest. Never loop on Kaggle status: submit, do other work, one status call between phases. Stop everything only if free disk < 800 MB. Commit own paths only, never media. Roles inline. State file docs/openmontage/S7_STATE.md; resume at first unfinished phase. Final report max 12 lines.

MODELS IN ORDER (one model per kernel, back-to-back): 1) SDXL Base + madebyollin/sdxl-vae-fp16-fix; 2) FLUX.2-klein-4B; 3) Z-Image-Turbo. Test set: 10 fixed scenes, same seed per scene across models, 1024x1024, best prompt variant per model from PROMPTING_FACTS.md rendered with tools/prompting (SDXL: structured + short negative; Z-Image: prose, style first, no negative; klein: prose, anatomy first, no negative).

PERSISTENCE RULE ("until success", bounded): per model up to 4 attempts, total cap 90 minutes wall time per model. After EACH failure: save the full traceback, write a one-line diagnosis in S7_STATE.md, and CHANGE something concrete before retrying (examples: use released diffusers instead of git main; match transformers to diffusers; add enable_model_cpu_offload; lower to 768 only as a LAST resort and record it; verify the import with python -c in the kernel before generating; check the official card for the required versions). Never repeat an identical attempt. After the cap, mark BLOCKED with exact error, versions and traceback path, and continue with the next model. The run ends only when all 3 are DONE or BLOCKED.
SUCCESS = 10 images saved, none black/NaN, manifest job_id/sha256/bytes verified via the bridge.

MEASURE per model (objective, saved in JSON): load time, steady seconds/image (exclude first warm-up), usable images per minute, peak VRAM, black/NaN/OOM count, attempts needed, exact versions.
OBJECTIVE QC per image: Laplacian blur score, text-like artifact detector, perceptual-hash duplicates, resolution, saturation/contrast outliers. Flag only.

AGENT SELF-ASSESSMENT (advisory, label it "agent opinion, not independent, vision model can miss anatomy errors"): view each image (use the image Read capability) and for each of the 30 images note in a table: visible anatomy problems (extra/missing/fused limbs, duplicate heads), broken geometry, texture mush, garbled text, prompt mismatch (count/relations), style fit with STYLE_BIBLE.md (palette, field-guide look). Score with the OpenCode rubric (0-2 per category). Then rank the models by: severe-artifact count, usable share, seconds/image, and say which model the agent would pick and why, plus how confident it is (low/medium/high) and which scenes are the weakest per model. State plainly that the owner's blind scoring decides.

OWNER PACK (blind, in projects/s7_blind/, gitignored): per-scene sheets with 3 panels A/B/C in random order per scene (mapping in a separate mapping.json), phone-readable (max 1600 px wide); a CSV template (scene, best_panel, worst_panel, anatomy_ok_A/B/C, comment). Do NOT show the agent's ranking inside the sheets. scripts/s5_tally.py (or s7_tally.py, test-first, small) reads the owner's CSV + mapping and prints wins, anatomy-ok counts and the speed/VRAM table, and prints "AGENT vs OWNER agree/disagree" comparing with the agent's pick; "TIE" if the best two differ by <=1 win.
REPORT docs/openmontage/image_gen/BAKEOFF_S7.md: observed vs assumed, attempts log per model (what changed each time), speed/VRAM table, objective QC table, the agent's advisory ranking, BLOCKED causes, and exact owner steps. Update S7_STATE.md, LESSONS.md; print stop-Codespace commands. No model is declared the winner until the owner's CSV is tallied.
```

**Ваши шаги после отчёта (10 минут)**
1. Откройте `projects/s7_blind/` через порт 8080 и пролистайте 10 листов.
2. В каждой сцене отметьте лучшую и худшую панель и где анатомия сломана.
3. Отдайте CSV агенту, он покажет итог и сравнит его со своим выбором. Если ваши выводы разойдутся с его мнением, верим вам.

**Диск:** перед запуском проверьте `df -h /workspaces`. Для трёх моделей нужны только вывод и логи, весы лежат на Kaggle, но кэши и старые рендеры (apollo9) стоит удалить заранее.

---

### [37] ВЫ · 2026-10-21 10:43 UTC

Сделай файл как должен быть выглядеть фабрика 100 процентов и потом этот файл я дам агенту и он начнет строить

---

### [38] CLAUDE · 2026-10-21 10:44 UTC

> 📄 Claude создал файл `/workspaces/OpenMontage/FACTORY_100_SPEC.md` (полный текст в разделе 6.2)

> 📎 Файл отправлен пользователю: /workspaces/OpenMontage/FACTORY_100_SPEC.md — «Спецификация фабрики на 100% для агентов»

Файл `FACTORY_100_SPEC.md` готов: это описание того, как должна выглядеть фабрика на 100%. Внутри короткое резюме для вас по-русски, остальное на английском для агентов.

**Что в нём**
- Жёсткие правила: бюджет $0, никаких секретов, права по каждому кадру, `claim_id` на каждое утверждение, ИИ-картинки только с меткой, публикация вручную, качество картинок и голоса оцениваете вы.
- Роли: кто за какие папки отвечает (Kilo, OpenCode, независимый ревьюер, вы).
- 10 слоёв с критериями «готово»: выбор темы, факты и сценарий, источники и права, ИИ-картинки на Kaggle, озвучка, монтаж, проверка качества, упаковка, ваш просмотр, эксплуатация.
- Текущее состояние с пометкой, что это слова агентов и их надо перепроверить.
- Порядок работ от F0 до F7 и определение «100% готово».

**Как использовать:** положите файл в корень репозитория (`/workspaces/OpenMontage/`). Я записал его туда же, но если вы работаете в другом Codespace, загрузите вручную. Потом дайте агенту это:

```text
Read FACTORY_100_SPEC.md fully, then docs/openmontage/*_STATE.md and docs/openmontage/OPENCODE_REQUESTS.md. Do not redo completed work. Start with milestone F0 (read-only reality audit): write docs/openmontage/FACTORY_GAP_AUDIT.md with PASS/FAIL/NOT_CHECKED per layer, with evidence from the repository, no code changes. Do not edit FACTORY_100_SPEC.md; propose changes in docs/openmontage/SPEC_CHANGE_REQUESTS.md. Commit only your own paths, push non-force. Final report max 12 lines.
```

**Что нужно знать**
- Ниша в файле не утверждена окончательно: основной кандидат «спекулятивная эволюция», ISS остаётся вторым треком. Решение за вами.
- Проценты готовности я нигде не ставил: только чекбоксы, потому что честно измерить «сколько процентов» нельзя.
- Если агент будет слишком долго выполнять S7, F0 запускайте после него, чтобы не делать два прогона одновременно.

---

### [39] ВЫ · 2026-10-21 12:22 UTC

*[приложен файл: 1000265464.jpg]*

*[изображение: скриншот/фото от пользователя]*

---

### [40] CLAUDE · 2026-10-21 12:22 UTC

**F0 выполнен честно: из 10 слоёв ни один пока не соответствует спецификации (0 PASS, 7 FAIL, 2 NOT_CHECKED).** Это ожидаемо: спецификация описывает 100%, а FAIL здесь значит «ещё не построено или сломано». Это не катастрофа. Но агент нашёл несколько конкретных дефектов, которые надо чинить.

**Что подтверждено отчётом (коммит `c126830`, запушен, код не менялся)**
- Работал OpenCode на DeepSeek V4.1 Flash Free (внизу видно модель). Это первый прогон на другой модели, и отчёт получился дельным, с доказательствами по файлам и строкам.
- Тесты: 1030 прошло, 29 пропущено, 3 xfail, быстрый CI-набор 10/10. Диск 2,6 ГБ.
- Спецификация не тронута, предложения изменений лежат в `SPEC_CHANGE_REQUESTS.md` (SCR-01 … SCR-10), ждут вашего решения.

**Реальные дефекты (все со слов агента, надо проверить)**
1. **QC игнорирует `config/qc_thresholds.json`**: пороги, по-видимому, зашиты в код. Это нарушает правило «пороги в конфиге».
2. **`claim_ids_resolve` проверяет только последний ID** в строках с несколькими ID. Значит, неизвестный claim_id в середине строки может пройти. Это серьёзный пробел в проверке фактов.
3. **`cmd_edl` жёстко привязан к Artemis**, не работает на других эпизодах.
4. **2 красных теста режима глав** на текущем HEAD.
5. **Нет кода измерения ниш и теста жизнеспособности темы**, а модули упаковки, гейт спекулятивных иллюстраций и учёт стоимости не подключены к конвейеру.
6. **Полный сбор тестов падает** из-за вложенной папки `youtube-niche-finder` (нужен `psycopg2`). Надо исключить её из pytest.

**На что обратить внимание**
- Агент сделал `git merge` и пуш в вашу ветку, поэтому в пуш попало и то, что Kilo уже закоммитил локально (было «ahead 35»). Проблемы нет, но проверьте, что Kilo S7 не потерял работу (`git log --oneline -5`).
- В `git status` остаются изменённые файлы Kilo (`S5_STATE.md`, `s5_bakeoff_run.py`) и мусор (`.opencode/`, `apollo_11.json` и другие). Не добавляйте их в коммит.
- Отчёт сам написан одной моделью без независимой проверки. Фразу «0 PASS, 7 FAIL» принимайте как гипотезу.

**Что делать дальше (порядок)**
1. Пусть Kilo закончит S7 (модели, слепой пакет). Это следующий шаг самого агента.
2. Прочитайте `docs/openmontage/SPEC_CHANGE_REQUESTS.md` и ответьте по каждому из 10 пунктов: принять, отклонить или отложить. Если хотите, пришлите мне скриншот, разберу вместе.
3. После S7 дайте Kilo починку дефектов (тесты первыми):

```text
MILESTONE F1-fix (Kilo). Do NOT redo completed work. Read docs/openmontage/FACTORY_GAP_AUDIT.md and the owner's decisions on docs/openmontage/SPEC_CHANGE_REQUESTS.md (apply only approved ones). Test-first, show red then green, run the fast suite with exit codes. Fix in this order: (1) qc.py must load thresholds from config/qc_thresholds.json (fail-closed if the file is missing or malformed; add a test that changing the config changes the verdict); (2) claim_ids_resolve must check EVERY claim_id on a line (test: unknown id in the middle of a mixed row must FAIL); (3) cmd_edl must work for any episode id, not only Artemis (test with two fake episodes); (4) the 2 red chapter-mode tests: diagnose, fix or document with evidence; (5) exclude youtube-niche-finder/ from pytest collection (pytest config), confirm full collection works. Scope: docs/ tools/ scripts/ tests/ config/ .kilo/. Commit own paths only (never git add -A), no media, no secrets, one status call for any Kaggle job. Final report max 12 lines.
```

Проверьте батарею: 29% и идёт зарядка, это хорошо. Остановите Codespace, когда не работаете.

---

### [41] ВЫ · 2026-10-21 15:40 UTC

*[приложен файл: 1000265486.jpg]*

*[приложен файл: 1000265483.jpg]*

*[изображение: скриншот/фото от пользователя]*

*[изображение: скриншот/фото от пользователя]*

---

### [42] CLAUDE · 2026-10-21 15:40 UTC

**Оба отчёта сильные и честные. Картинки готовы к вашей оценке, победителя пока нет, и решать будете вы.**

**S7: бейкофф (Kilo, модель MiniMax M3.1 Flash)**
- **SDXL:** 10/10 картинок, 41,4 с на картинку, 9,2 ГБ памяти. Перепрогон воспроизвёл результат бит в бит.
- **FLUX.2 klein 4B:** 10/10, 24,7 с на картинку, 8 ГБ с `enable_model_cpu_offload`.
- **Z-Image Turbo: BLOCKED.** После 4 попыток все 10 кадров чёрные (NaN в fp16). Карточка модели требует bf16, а наше правило запрещает bf16 на T4. Это решение за вами (см. ниже).
- **Скорость сильно хуже моей оценки.** Я называл 4-8 с на картинку, на деле 25-41 с (для SDXL-Lightning было 3,9 с). Для 100 картинок на эпизод это примерно 41 минута GPU на klein и 69 минут на SDXL.
- **Мнение агента (не независимое):** klein лучше. У него 6 грубых артефактов и 5 из 10 годных против 20 и 1 из 10 у SDXL. SDXL уходит в фотореализм и придумывает текст. Klein держит плоский стиль, но путает мелочи (4 ноги вместо 6, глаз у «безглазого»).
- **Оговорка:** автоматический детектор текста пропустил худший плакат SDXL и ложно сработал на чистом кадре klein. Агент сам пишет, что решает визуальная оценка. Его мнение о картинках тоже оценка модели, а не истина.
- Слепой пакет готов (10 листов, панели A и B, Z-Image исключён), в git медиа нет.

**F1-fix (коммит `5dd325b`, запушен)**
Починены все 5 дефектов из аудита с красными и зелёными тестами: пороги QC теперь из конфига, `claim_ids_resolve` проверяет каждый ID в строке, `cmd_edl` не привязан к Artemis, 2 красных теста глав исправлены, pytest больше не падает на `youtube-niche-finder` (собирает 2491 тест). Не проверено: полный прогон всех тестов и реальный рендер на новом EDL.

**Что вам сделать (10-15 минут)**
1. Откройте листы `projects/s7_blind/` через порт 8080 (`cd projects/s7_blind && python3 -m http.server 8080`). Инструкция лежит в `INSTRUCTIONS.txt`.
2. В каждой из 10 сцен выберите лучшую панель, отметьте, где анатомия сломана, и заполните `results.csv`.
3. Запустите `python scripts/s7_tally.py`. Он покажет итог, при разнице в одну победу напишет «TIE», и сравнит ваш выбор с выбором агента.
4. Ответьте на `docs/openmontage/SPEC_CHANGE_REQUESTS.md` (SCR-01…10). Агент не применил SCR-01-04 и 08-10 без вашего решения.

**Решение по Z-Image (ваше)**
Моя рекомендация: не тратить на него больше попыток сейчас. Для проверки нужен bf16 (который на T4 только эмулируется и нужен больше памяти) или другая видеокарта. Это нарушает правило «fp16 only» и может стоить ещё часов GPU. Сначала посмотрите, хватает ли вам klein. Если картинки klein вас устроят, Z-Image можно оставить на потом.

**Про модели агентов:** это первый заметный прогон на MiniMax M3.1 Flash (Kilo) и DeepSeek V4.1 Flash (OpenCode). Оба отчитались с блокерами, тестами и без выдумок, так что на этих двух задачах разницы с Nemotron я не вижу. Выводов по качеству кода из одного прогона делать нельзя.

**Когда закончите:** остановите Codespace командой `gh codespace stop`, которая напечатана в конце отчёта S7 (там уже подставлено имя вашего Codespace). Батарея 50% и идёт зарядка, это нормально.

---

### [43] ВЫ · 2026-10-22 00:53 UTC

Как тебе этот список 
Обработка заняла 1m 4s

* [Z-Image-Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo?utm_source=chatgpt.com)

* [FLUX.2 Klein 4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B?utm_source=chatgpt.com)

* [SDXL-Lightning](https://huggingface.co/ByteDance/SDXL-Lightning?utm_source=chatgpt.com)

* [DreamShaper XL Lightning](https://huggingface.co/Lykon/dreamshaper-xl-lightning?utm_source=chatgpt.com)

* [FLUX.1 Schnell](https://huggingface.co/black-forest-labs/FLUX.1-schnell?utm_source=chatgpt.com)

* [Sana Sprint 1.6B](https://huggingface.co/Efficient-Large-Model/Sana_Sprint_1.6B_1024px?utm_source=chatgpt.com)

* [Krea 2 Turbo](https://huggingface.co/krea/Krea-2-Turbo?utm_source=chatgpt.com)

* [Stable Diffusion XL Base 1.0](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0?utm_source=chatgpt.com)

* [Qwen-Image-2512](https://huggingface.co/Qwen/Qwen-Image-2512?utm_source=chatgpt.com)

* [Qwen-Image](https://huggingface.co/Qwen/Qwen-Image?utm_source=chatgpt.com)

* [PixArt-Sigma](https://huggingface.co/PixArt-alpha/PixArt-Sigma-XL-2-1024-MS?utm_source=chatgpt.com)

* [Stable Diffusion 3.5 Medium](https://huggingface.co/stabilityai/stable-diffusion-3.5-medium?utm_source=chatgpt.com)

* [SDXL-Turbo](https://huggingface.co/stabilityai/sdxl-turbo?utm_source=chatgpt.com)

* [LCM DreamShaper v7](https://huggingface.co/SimianLuo/LCM_Dreamshaper_v7?utm_source=chatgpt.com)

* [Juggernaut XL v9](https://huggingface.co/RunDiffusion/Juggernaut-XL-v9?utm_source=chatgpt.com)

* [Illustrious XL v1.1](https://huggingface.co/OnomaAIResearch/Illustrious-XL-v1.1?utm_source=chatgpt.com)

* [Animagine XL 4.0](https://huggingface.co/cagliostrolab/animagine-xl-4.0?utm_source=chatgpt.com)

* [Pony Diffusion V6 XL](https://huggingface.co/AstraliteHeart/pony-diffusion-v6?utm_source=chatgpt.com)

* [Kolors](https://huggingface.co/Kwai-Kolors/Kolors?utm_source=chatgpt.com)

* [HunyuanImage 2.1](https://huggingface.co/tencent/HunyuanImage-2.1?utm_source=chatgpt.com)

---

### [44] CLAUDE · 2026-10-22 00:53 UTC

**Как список: это набор названий без доказательств, а не рейтинг.** Он собран за минуту (в ссылках метка `utm_source=chatgpt.com`), без проверки лицензий, памяти T4 и скорости. Для решения его использовать нельзя, но как источник идей он полезен.

**Уже протестировано нами (4 из 19)**
- Z-Image Turbo: чёрные кадры в fp16, ждёт вашего решения.
- FLUX.2 klein 4B и SDXL Base: готовы, ждут вашей слепой оценки.
- SDXL-Lightning: 3,9 с на картинку, но вы видели много артефактов.

**Остальные по группам (лицензии и пригодность из моих прошлых проверок или по памяти, проверять по карточкам)**
- **Подходят по размеру, стоит рассмотреть:** DreamShaper XL Lightning (на базе SDXL, быстрый, влезает в T4; стиль может быть чище, чем у SDXL-Lightning). Лицензию проверить.
- **Слишком тяжёлые для одной T4:** Qwen-Image и Qwen-Image-2512 (около 20B параметров), HunyuanImage 2.1 (большая модель, по моей памяти лицензия Tencent ограничивает территории; не проверял), FLUX.1 Schnell (12B, нужен квант или offload).
- **Лицензионные риски:** SDXL-Turbo (по моей памяти, некоммерческая лицензия Stability, проверить), Kolors (нужна регистрация для коммерческого использования), Pony V6, Illustrious, Animagine (у каждой своя особая лицензия, не Apache), Juggernaut XL (условия RunDiffusion). Я эти пять лицензий не читал.
- **Не подходят по стилю:** Illustrious, Animagine, Pony это аниме-модели, а нам нужен «полевой справочник» существ. LCM DreamShaper v7 это старая SD 1.5, качество низкое.
- **Не знаю:** Krea 2 Turbo (не встречал данных о лицензии и размере), Sana Sprint 1.6B (скорость заявлена высокая, лицензия весов ранее была неясной).
- **Можно отложить:** PixArt-Sigma и SD 3.5 Medium (рабочие, но у них нет явного преимущества перед нашими тремя).

**Что я бы сделал**
1. **Не расширять тест, пока вы не оценили картинки klein и SDXL.** Если klein вас устроит, остальные 15 не нужны.
2. Если не устроит, следующий шаг это SDXL-вариант с чистым стилем (DreamShaper XL Lightning) или стилевой LoRA на SDXL. Они влезают в T4 и работают с нашим пайплайном.
3. Заранее ничего не качать. Проверку по карточкам (лицензия, размер, dtype, поддержка в релизной diffusers) можно дать Kilo как S6, он уже готов (я давал промпт). Могу добавить в него DreamShaper XL Lightning и Krea 2 Turbo.

**Главное:** узкое место сейчас не выбор модели, а ваша слепая оценка и скорость (25-41 с на картинку против моих ожиданий 4-8 с). Если скорость критична, быстрее всех из проверенных SDXL-Lightning, но качество у него хуже. Покажите агенту результат вашей оценки, тогда решим, нужны ли новые модели.

---

### [45] ВЫ · 2026-10-22 00:53 UTC

**Вложение: (файл без имени: вставленный текст/результат исследования)** (30320 байт)

<<<НАЧАЛО ВЛОЖЕНИЯ>>>
Обработка заняла 5m 51s

### 20 моделей для генерации качественных иллюстраций: подробный разбор

Дата проверки: 21 октября 2026 года.

Я отобрал модели, которые заслуживают тестирования для твоего YouTube-конвейера: фантастические существа, вымышленные миры, атмосферные сцены и сотни иллюстраций на видео. Приоритет — высокая визуальная детализация, скорость, меньше заметных дефектов и возможность коммерческого использования.

Важное уточнение: не существует одной модели, у которой одновременно доказаны лучшее качество, максимальная скорость и минимальное число артефактов на всех типах изображений. Я сравнивал документацию, лицензии, пользовательские оценки и обсуждения Reddit/GitHub/ComfyUI. Это не единый лабораторный тест всех 20 моделей на одной NVIDIA T4, поэтому там, где сопоставимых замеров нет, я не буду придумывать время генерации.

### Что выяснилось в первую очередь

![详细介绍：当想象力成为生产力，AI视频生成如何重塑2026年的创作世界 - ljbguanli - 博客园](https://images.openai.com/static-rsc-4/0zJLiX6pCG_nB4rwINH6SxZqFDWapifWTfMry0OrzPgPd4MHazYdV5EK-HMYqKvelrgP4Xt2P7Rp7_d09va89xddsSLBMl25aepNJDzXLzDFPKi_-PBPup23tIAnkI9vFUZEAF9RF4vidWS-8NRTegd_LwmIVp7hC_G8GXHbwJ8gJXGEiWFZaeYFf1bWYg2H?purpose=fullsize)

1\. Z-Image-Turbo — один из первых кандидатов для проверки

Модель интересна сочетанием детализации, скорости и относительно небольшого размера активной модели. Владельцы GPU хвалят реалистичность, но встречаются замечания о недостаточном разнообразии результатов и зависимости скорости от конкретной реализации. Официальный пример использует BF16, поэтому для твоей T4 потребуется совместимый FP16- или квантованный вариант.

![Create Fantasy Portraits with AI - Join Postcrest](https://images.openai.com/static-rsc-4/RhZOabIy7DFPWKLHbCY-8-F7SIEZ9XddH_Fmd8opUO-3J94GEnT7Y4n01YwTVYWfduRFTOflq8HQd92RZOnczvnXcQoteEyo2gyOGlyNsfle-6Y8IiZnwQB8g0pm5BkXJBjQjZ4KmCt5wpx9V_TNDeZoflDM1qB3otS6fPxwZ2dJZDtHOGmxNXduAz5KDI99?purpose=fullsize)

2\. FLUX.2 Klein 4B — сильный кандидат для массовой генерации

Версия 4B создана для быстрой генерации и редактирования изображений, а 9B-вариант распространяется на других условиях — некоммерческая лицензия. В обсуждениях хвалят скорость и внешний вид, но также жалуются на анатомические ошибки и нежелательные изменения при редактировании. Заявления о генерации за доли секунды относятся к подходящему современному оборудованию, а не гарантируют такую скорость на T4.

![Juggernaut XL Lightning模型4step出高质量图片 | AI绘画教学 | 草凡博客](https://images.openai.com/static-rsc-4/agcTYWQPsmA_RJzI64m5jeSFjy3b0lQ5ulplNtybCHZTOhADwM5r4xXcXSd0VN4Y2XozQuThIJfBfCu2mTOPpQaO40zz9CulaVj3_rwgteRRk6E-VmV5_jb91DUH007DqeN7h7WO88iYA9LBFRRVsj4nUFy6gdCNWFCJnfFvgdcuCuzWt_97bT2I9vAU1TeS?purpose=fullsize)

3\. SDXL-Lightning — надёжная отправная точка для T4

Позволяет быстро генерировать изображения на базе SDXL. Важно: низкое число шагов ускоряет генерацию, но иногда снижает разнообразие композиции и качество переходов света и теней. В сравнительном тесте одного из пользователей Lightning уступал обычной SDXL по гибкости композиции, но оставался быстрее. Для качества стоит начинать с четырёх- или восьмишагового варианта, а не с экспериментального однокадрового режима.

![ostris/krea2_turbo_style_reference · Hugging Face](https://images.openai.com/static-rsc-4/3Y_YP34ePh724mYvmLJUEKNoleHLl7TNSudLwaC7SHD2UkSJzG7srfaTsDnpHDZGUPc00hVbOQNsF6NLJmvI-pp13ukD42o5JHlxeUEw40CvFsPlAMnCLJv78xuWYykdCkP0aynUKi_sSwDNguRPBNhRwYXzAqOczMtQpHcItNIoeXm3Ib-sfp9zbDZ0b1Vv?purpose=fullsize)

4\. Krea 2 Turbo — интересен качеством, но есть ограничения

Лицензия с условиями

Модель ориентирована на выразительные результаты и быструю генерацию. Однако обсуждения сообщества содержат сообщения о пятнистом шуме на плавных фонах и неровных линиях. Коммерческое использование по Community License зависит в том числе от годовой выручки: при выручке менее $1 млн условия допускают коммерческое использование, а при достижении порога нужна enterprise-лицензия. Для T4 пригодность конкретного квантованного варианта нужно проверять отдельно.

Также я сверил пользовательский Image Arena. В срезе открытых моделей, опубликованном в октябре 2026 года, высоко оценивались Qwen-Image-2.1, Krea 2 Turbo, Z-Image-Turbo и FLUX.2 Klein. Но этот рейтинг показывает человеческие предпочтения, а не скорость, количество артефактов или совместимость с T4. Особенно показателен Qwen-Image-2.1: высокий рейтинг не отменяет ограничения его лицензии на некоммерческое использование.

### Подробный список из 20 моделей

Оценки скорости и качества ниже — ориентировочная экспертная оценка для твоей задачи, а не результаты единого бенчмарка на T4. «Средняя скорость» не означает плохой результат: иногда дополнительные шаги дают более чистую иллюстрацию, которую не нужно перегенерировать.

### Группа A. С чего я бы начинал тестирование

![Z-Image Turbo & ControlNet: The Essentials | Scenario Help Center | Scenario](https://images.openai.com/static-rsc-4/WobyKmgY3qqgDcLPC9QZyeHOy7iztkiE3AzXz-Og1xYpfKHbWkZd-CkWZidNaDBOTTALvsk1qVP7IGkMY2F9LCgeNK60PGOwzwEY3ermxpZ6NiiBpxDAiYtGGFXZ0zQY_FtYImVLCeNQkVrmqsNpbqXvPPCPkn5Ippez9_iUN6zX81aAF8PWgytxNiB8F38H?purpose=fullsize)

1\. Z-Image-Turbo

Качество: высокое · Скорость: высокая · T4: возможен совместимый вариант

Хороший кандидат для атмосферных окружений, существ и реалистичных материалов. Основные риски — недостаточное разнообразие при многократной генерации похожих промптов, а также разница в скорости из-за версии ComfyUI, типа точности и оптимизаций. Apache 2.0 разрешает коммерческое использование модели при соблюдении условий лицензии. Для T4 проверяй FP16/квантованный путь, поскольку официальный пример использует BF16.

![The Mage and the Ancient Beast | Story.com](https://images.openai.com/static-rsc-4/D0Z4gukVmTVh-9aE7xEOvK6OVXhe6VGVRm5pX-DouGZQm0Yo4VMUefEQBzJLnMyDjOs2yFHzB9BOPYs62aJrZzc-GuTmqWp5hx9ZSTNucUiWNbkAKPB-Gwl5K-JJRcib-BBPoGSCsMgrJG3e1iOe_VCWdVqZ5wOy2tdL_MhRTiQZH66tU82uY0U9IC0za2Rk?purpose=fullsize)

2\. FLUX.2 Klein 4B

Качество: высокое · Скорость: высокая · T4: тестировать с экономией памяти

Подходит для большого количества кадров, если устраивают результаты конкретного стиля. Поддерживает генерацию и редактирование с референсами, что потенциально полезно для сохранения внешности существа. Пользовательские сообщения предупреждают, что редактирование может менять детали, которые хотелось бы оставить прежними, а анатомические ошибки всё ещё встречаются. Версия 4B распространяется под Apache 2.0; не путай её с 9B.

![Raijuro: The Stormfang Titan Legend | AI Art Generator | Easy-Peasy.AI](https://images.openai.com/static-rsc-4/OcOo-44ma9t8TwAMp-t3bTfOBB1S35nYHGragYVGOVbO800UEypsQJxksWXmMwwNcUdgEzjh0OYLDLRtHsmxq4shPXgPuLTD3O57E29XuWUiBhafWzKKXhkqbf1zeFT67gfWafD3fpJRsGH8nQW22n4y9RE33UccPf9mux14het9XalhFl6s-L98UEutazAh?purpose=fullsize)

3\. SDXL-Lightning (4- или 8-шаговая версия)

Качество: хорошее–высокое · Скорость: очень высокая · T4: один из лучших вариантов

Сильный выбор, если важнее всего количество готовых кадров в час. Официально предоставляются варианты UNet и LoRA на разное число шагов. Четыре шага — хорошая отправная точка; восемь шагов стоит проверить, если на быстрых вариантах появляются странные контуры, потеря деталей или слишком похожие композиции. В одном сравнении пользователь предпочёл Lightning модели Hyper-SD за лучшую гибкость изображения.

4\. DreamShaper XL Lightning

Качество: высокое для стилизованного арта · Скорость: высокая · T4: перспективно

Особенно интересно тестировать для концепт-арта, фантастических существ и драматического света. Сообщество хвалило детализацию освещения, но некоторые пользователи сталкивались с повторяющимися узорами и артефактами, вызванными в том числе tiled VAE/MultiDiffusion, а не только самой моделью. Проверяй лицензию конкретной версии и не включай ненужные улучшатели тайлинга в первую проверку.

![Dark Fantasy (Flux.1D) - v1.0 - Flux.1 D | Diffus](https://images.openai.com/static-rsc-4/wtRQlyeT45j2SkWqYctIiwOCCgXcxWtIDDk9tXSutnE1rV4yJTECbtCR7Q5ZcoOI_CSUvKPRB6mu4fvw6prEiAdGn5BsPY-u30ezjwIBpdJdWbtT5A3apdaHkZG0dS_eRMR2IrJQ4ithE8xq7Pg1RrAvBqMo9twUWLv4CJgf9urzpud6DnVChNLgyszbMLXr?purpose=fullsize)

5\. FLUX.1 Schnell

Качество: высокое · Скорость: высокая относительно FLUX Dev · T4: нужна оптимизация памяти

Модель ориентирована на малое число шагов и доступна под Apache 2.0. Для сцены с существом и сложной средой может дать хорошие результаты, но это более тяжёлый вариант, чем Klein 4B: на T4 может понадобиться квантование или выгрузка части модели в RAM. Пользователи также замечают «пластиковый» вид лиц после некоторых усилителей резкости — это не обязательно дефект самой модели, иногда виноват постпроцессинг.

![Free Text to Fantasy Art AI Generator | CGDream](https://images.openai.com/static-rsc-4/k4MDNwdGNJtkrdfidGADM2OuTM9RCUOFVXJ1jH_DEpx01M03XIoM1g3Udis1zsvSxKZiJCUKrKy-0_yJxDDRkvKOcNt12cjpgsSQKLJrwOZX8GHjokZB7xJ0Q2CNIhEk2ptcILUBS3UXmYm1vJP0JFouqnSu6z-5Xgi-h57u2A3jhtuggoJmmqk8OOrSjZsS?purpose=fullsize)

6\. Sana Sprint 1.6B

Качество: среднее–хорошее · Скорость: очень высокая по задумке · T4: проверять точность и реализацию

Небольшая модель, предназначенная для генерации за 1–4 шага. Это потенциально полезно для сотен картинок, но официальная карточка указывает ограничения в сложном тексте и точной прорисовке пальцев. Опубликованные авторами высокие показатели задержки нельзя переносить на T4 без отдельного замера; стандартный пример использует BF16.

![A gentle hill giant tending to Character Art](https://images.openai.com/static-rsc-4/0rjGT-FHIi7-y4y5Lazm2IfD_SqzQBn00fEQpafzn2N-V6Xy7fzE-ACAU_pGhPelDJPx6wk6Cw5mgWSKzVafOkOj8VB5IcblFC-zhVx4HgOBnaa0Fa-szgA0FMtJKxQVKcY5Mw1ibYAGGtW2HeN-jtxVZoBb23dL70p28m85BDbRrUkNjMJHyYuEXy90W-qu?purpose=fullsize)

7\. Krea 2 Turbo

Качество: потенциально очень высокое · Скорость: высокая в подходящей конфигурации · T4: условно

Стоит проверить, если результат важнее максимальной простоты запуска. Turbo — быстрый вариант семейства, но пользовательские обсуждения фиксируют пятнистые текстуры на гладких градиентах и артефакты на прямых линиях. Ещё раз: лицензия ограничивает коммерческое использование условием о годовой выручке; перед монетизацией нужно читать её актуальный текст.

### Группа B. Более управляемые модели и варианты для доработки

![Images of Theme: A mysterious tower that beckons. | Deep Dream Generator](https://images.openai.com/static-rsc-4/s5b2WIvOcER8ZpokXQXfMZv48c2xCOVzrMzpt4NVUjGbYmtwX6LDZoGy1JPsFXNyDKIo7o_Hww09GFBSVGPckbzw4tuSIaIzLOyfCgVbjwxS_jTdo0a10igCw1L4P_yhELFGX-KgMy3wpN24aIxfdwvUCLrg54y_edAJ7dN_2tAfMuf6X0rgjF_d9qPexLhX?purpose=fullsize)

8\. Stable Diffusion XL Base 1.0

Качество: хорошее · Скорость: средняя · T4: подходит для обычного FP16-воркфлоу

У базовой SDXL не самая высокая скорость из списка, зато развитая экосистема LoRA, ControlNet, IP-Adapter и img2img даёт больше вариантов для управления сценой. Это важно, если в ролике много повторяющихся героев или нужно сохранять стиль между кадрами. Для ускорения можно подключать Lightning, но следует помнить, что низкое число шагов может снижать визуальное разнообразие. Лицензия OpenRAIL++ содержит собственные условия использования.

![Imaginative art, showcasing (masterpiece:1.3), (hires, high resolution - SeaArt AI](https://images.openai.com/static-rsc-4/dQVz-htAAFIDaqQTKeHOTcL5vG2uvQ3FRgNc3Ng3LR7M8YYMbJwHGnDyW6wuUTz5HaGYedL-RIp5mkthRIhR2H0tp3yrEDUJQ-kgCyZkLld1FX-CkE--erP2lCAUthox1Df1FpNWAxAKkV2PdcKrxkoMvKrh2WpaI4kU8-nJkUOeeBfTtxCuGa3v89nL13vj?purpose=fullsize)

9\. Qwen-Image-2512

Качество: высокое · Скорость: низкая–средняя на ограниченной GPU · T4: тяжёлая

Интересен качеством деталей, интерпретацией сложных промптов и работой с текстом внутри изображений. Пользователи с 16 ГБ VRAM сообщали о хороших результатах, но отмечали необходимость аккуратного управления памятью. Полный репозиторий модели очень большой — 57,7 ГБ; это общий размер материалов модели, а не обязательный объём VRAM, однако запуск на T4 потребует квантования и/или offload и может быть медленнее практичных вариантов. Лицензия модели указана как Apache 2.0.

![Super Cheese Monster Delights | AI Art Generator | Easy-Peasy.AI](https://images.openai.com/static-rsc-4/GhbnaKPMEKYiL_Cuj0Z6opYlrJLdq2DON_Go-Fsxehd7-1M7RHthswufkLmlxaC5B6Xnmfwd1quw9tA6-1L832ZlTund-szjr3AaPkalaS4Izt6REOpiOsRKxe1NLFAVks46GYdL7LmhNI7qA7XvRW5nnp2l_ywnqymeDCUgwcMApnNqreNmALpZatY2_6eS?purpose=fullsize)

10\. Qwen-Image-2.1-Turbo

Качество: очень высокое по пользовательским предпочтениям · Скорость: улучшена Turbo-режимом · T4: сложный запуск

Модель получила сильные пользовательские оценки, а Turbo-вариант ориентирован на восемь шагов. Но здесь есть две оговорки. Во-первых, в обсуждениях оценки смешанные: одни хвалят детализацию, другие отмечают искусственную текстуру, ошибки анатомии и визуальные дефекты. Во-вторых, опубликованная лицензия Qwen Research License разрешает только некоммерческое использование без отдельной лицензии, поэтому для коммерчески монетизируемого YouTube я не рекомендую её использовать без письменного разрешения правообладателя.

![Enchanted Forest Guardian](https://images.openai.com/static-rsc-4/FD81OXEwy9mjilQo0EFlArriPKavEsDtDYIwvhgIYtdB2nlMOtp2NkHviMqduYmO83EZkDtYClH0lbkO2uHbHu0UO6tyomqnSGKsuGCTo1CV7Yuz5u3EwcGMvc2xnxT3twYE2lP-xQnut0MEl69khzhhz2JJrzUUKO5RmIh85axPP7THdO4V2PrmKL4EwFAR?purpose=fullsize)

11\. PixArt-Sigma

Качество: хорошее · Скорость: средняя · T4: потребуется управление памятью

В обсуждениях пользователи выделяют хорошее соответствие длинным промптам, но отмечают, что эстетика может уступать удачным SDXL-файнтюнам, а анатомические дефекты не исчезают полностью. Полный Diffusers pipeline указан примерно как 21,8 ГБ материалов — это не требование к VRAM, но сигнал, что беспроблемный запуск на T4 не гарантирован. Лицензия — OpenRAIL++. Полезнее рассматривать PixArt как альтернативу для сравнения композиции, а не как безусловную замену SDXL.

![The Best 25 Stable Diffusion Prompts for Concept Art](https://images.openai.com/static-rsc-4/ktLkpwaRxkK9gjCRLTOE82awcO0jeYhUVaPoDsAaWX6_uld-A_fLFvoNBtmXKtQvSUwa2R9GTNex1q_LQ5wj86FYzy6GcyFDR9GewuxsczZTCDJV126-GPialj6ErDIBOrWDZl2XB6z-3Ium-QWmJwag7QGCk5t_lBch1L7co9-qRtqBC4VMruVViQiagnef?purpose=fullsize)

12\. Stable Diffusion 3.5 Medium

Качество: хорошее–высокое · Скорость: средняя или низкая на T4 · T4: ограничение памяти

Авторы заявляют улучшения в качестве, типографике и интерпретации сложных описаний. Однако модель использует несколько текстовых энкодеров, а стандартный пример задействует BF16, поэтому на T4 нужен проверенный вариант загрузки и точности. Коммерческая лицензия Stability AI Community разрешает бесплатное коммерческое использование при годовой выручке ниже $1 млн; при достижении порога требуется enterprise-лицензия.

![A painting of a giant monster with a huge head and a huge body - SeaArt AI](https://images.openai.com/static-rsc-4/j67yYHS5IcGfwHPiu-sM5HWxjTtP8IgYOophlLQRLdk0T-TgXxOBQlWgnkMiIOxr1jYRAAcuNgR7LA_Cy3BdZ48Vl06-iID2UWXlc5DQSVqhYcuA6cWRhGnq6EP8y_C1W0tG_ejiRxmmNtDD5dmDIuGvR-VGsWqMtrlU8C_Z-mnDCTuqBWE_MyV4Lp40Foxd?purpose=fullsize)

13\. SDXL-Turbo

Качество: среднее–хорошее · Скорость: очень высокая · T4: перспективно

Преимущество — быстрая генерация за малое число шагов. Минусы заметны в сравнении с полноценными SDXL-моделями: меньше деталей, более мягкое изображение и риск ухудшения качества при неподходящих шагах или guidance. Форумные рекомендации часто советуют не завышать число шагов и аккуратно подобрать CFG. Лицензия Stability AI Community позволяет коммерческое применение в пределах условий, включая порог выручки в $1 млн.

![- Free AI Art by Schattenjäger | Tensor.Art](https://images.openai.com/static-rsc-4/SnIzTgWc7OQ54eTsD-2WcXbxOI795cMB1Zpm7MNus1EqUjLS-8kQhtipNDymgS1YbbeOJqNS9PS3BAhsNZopgA6Zr1YKw1qkClvtS5fvaZtliUgXkpXCHSc_4QBanAo-4X5gXEdQwKdlQ7I2MbB2uO35XMnAeghck4JqSShDA-jhp4FcwKzjXNTHxwR4EN3a?purpose=fullsize)

14\. LCM DreamShaper v7

Качество: среднее–хорошее · Скорость: высокая · T4: подходит для тестов

Это вариант семейства DreamShaper, адаптированный для ускоренной генерации Latent Consistency. Он полезен для быстрых черновиков и отбора композиции, но я бы не выбирал его вслепую как финальный источник всех иллюстраций: у быстрых вариантов обычно меньше гибкости по деталям и композиции, чем у более медленного базового чекпойнта. Карточка на Hugging Face указывает MIT; перед коммерческим использованием всё равно проверь условия для конкретных весов, которые скачиваешь.

### Группа C. Специализированные и более тяжёлые варианты

![The Princess and the Monster | Story.com](https://images.openai.com/static-rsc-4/myo_b6YdYXZB5jD9jJEThBW-GxtIJwzBnKqBuSN9sJKi7x8jpCx9pgtpGdOPtYzMRr0fIlLPptM6W03F-WjQPxICaoKkCJroOHcJ1-0SfoVPMDLlAODgcm8MriALX93noolWN2ejewomKAE5UlmKruJzLbJlMD9zoxyau0hX9prXZ6SBwOVLmP92ppgBFG-8?purpose=fullsize)

15\. Juggernaut XL

Качество: хорошее–высокое · Скорость: средняя · T4: обычно реалистичнее с обычным SDXL-воркфлоу

Рассматривай его как альтернативный SDXL-чекпойнт для детализированных сцен, материалов и драматического света. Скорость зависит от версии, шага, разрешения и подключённых LoRA. На форумах встречаются жалобы на артефакты и ореолы при слишком большом количестве шагов или неудачных настройках; это хороший пример того, почему модель нужно тестировать на одинаковых промптах. Условия лицензии следует проверять на странице конкретной версии чекпойнта, а не выводить по названию семейства.

![Laeticia Aucerius レティシア・オーシディアス | STAR OCEAN: The Divine Force - AI Art Model | PixAI](https://images.openai.com/static-rsc-4/Gz0kNGDjarKuzuTd9dmVvZydT5rYESIw_G4G0pAwdAi7GLWbS3DCnUpxNJAN44HNPCspEGA5e0TqRpnjVOcNGFNlFAhLaWU5kyOgVHc8sXON4mF267UcOK78QCcUTPrizpNq_aeYoDkmH3VSQOPtUY08OKy4OUEVtCiNAFJEL_dF5QtebwARjM5weYHooe_z?purpose=fullsize)

16\. Illustrious XL v1.1

Качество: высокое для аниме/иллюстраций · Скорость: средняя · T4: подходит с SDXL-настройками

Имеет смысл, если визуальный стиль ролика ближе к аниме или выразительной рисованной иллюстрации. Версия v1.1 описана авторами как стабилизированная, с некоторыми улучшениями понимания персонажей. Пользовательский форумный кейс показывает, что генерация при 512×512 может давать абстрактные результаты — XL-моделям обычно нужно разрешение около миллиона пикселей и подходящий промпт. Лицензия наследует условия SDXL, поэтому коммерческое использование не следует считать безусловным только из-за доступных весов.

![Bringing A2UI to Google Workspace with Gemini | by Kanshi Tanaike | Google Cloud - Community | Medium](https://images.openai.com/static-rsc-4/DFGUlEc56Ld4Ay9l_3MSZH78jq3xize1EKm7tz4cowtomsQnH0A1j6PF-BLlvU1AK07l4PI2p-GHRP1IAvZf_sSX1dA5c2tnLChC-HrZbClAcWFp6XSsEAWNrSgxl6l9---LRWnnAlPrmUDgNkXysBKsf0m0K5E4_YkhjHTF-7VrzN5F9ZZMrV-V46zv88eW?purpose=fullsize)

17\. Animagine XL 4.0 Opt

Качество: высокое для аниме · Скорость: средняя · T4: реалистично для SDXL-класса

Лучше подходит для иллюстрированных персонажей, стилизованных существ и визуала с аниме-эстетикой, чем для нейтрального фотореализма. В одной опубликованной таблице сравнения ComfyUI указаны генерации на 28 шагах и около 18 секунд, но это результат той конкретной конфигурации, а не гарантированное время на T4. Преимущество — относительно удобный SDXL-экосистемный запуск; недостаток — в первую очередь специализированный стиль.

![Crowned Beast — Yodayo](https://images.openai.com/static-rsc-4/jlC12WhBz7tpt078q0qvPybvcU_OvfY3eMmzpeIoGfhaFiDsHxpv2FmJZ_HsxJW4NalOiL3PTfGSVpE-bnqqq-ZGmB1tmHO3Pr7ZAaZrrjFu5jRQHbGv0uHcDabIsf28mobf-3B8PY0fxcMA1EtCFIU-65GPYFEPed9w2f6e6xicazCSfsxul4z36opOxmpk?purpose=fullsize)

18\. Pony Diffusion V6 XL

Качество: высокое для стилизованных персонажей · Скорость: средняя · T4: подходит для XL-воркфлоу

Модель интересна персонажами, фантастическими существами и стилизованными композициями, но требует промптов, соответствующих её обучению. На Reddit пользователи получали плохие результаты из-за разрешения 512×512 и неподходящих тегов; другие отмечают случаи размытых глаз. Это не обязательно доказывает слабо
<<<КОНЕЦ ВЛОЖЕНИЯ>>>

---

### [46] CLAUDE · 2026-10-22 00:53 UTC

**Этот список полезнее первого (с названиями без пояснений), но выводов для выбора модели он не меняет.** Файл обрезан на 18-й модели из 20, последние две я не видел.

**Что в нём хорошо**
- Честная оговорка: единого теста на T4 нет, времена генерации не выдуманы.
- Совпадает с нашим опытом: у Z-Image официальный пример на bf16, для T4 нужен другой путь. Именно так и вышло, у нас чёрные кадры.
- Правильно разделяет Klein 4B (Apache-2.0) и 9B (некоммерческая) и предупреждает про лицензию Qwen-Image-2.1.
- Хорошее замечание про SDXL-Lightning: 4 шага быстрее, но композиции менее разнообразны, 8 шагов стоит проверить.
- Полезная мысль, что часть дефектов даёт постобработка (tiled VAE, усилители резкости), а не сама модель. Это надо учесть в нашем тесте: без апскейлов и улучшателей.

**Что вызывает сомнения**
1. **Картинки в тексте не результаты этих моделей.** Это стоковые иллюстрации из поиска с подписями других сервисов (CGDream, Story.com и т. п.). Как доказательство качества использовать нельзя.
2. **Лицензии местами расходятся с тем, что я находил раньше.** Пример: SDXL-Turbo здесь назван под Stability Community License с порогом $1 млн, а я помнил про некоммерческую. Кто прав, не знаю, нужна официальная карточка. То же с LCM DreamShaper v7 («MIT»), Krea 2 Turbo (порог выручки), DreamShaper XL Lightning и Juggernaut. Не доверяйте ни ChatGPT, ни мне, пока Kilo не прочитает карточки (промпт S6).
3. **Оценки «качество высокое, скорость высокая» это мнение модели.** У нас замер показал 25-41 с на картинку для SDXL и klein, а такие ярлыки скорости скрывают это.
4. **Аниме-модели** (Illustrious, Animagine, Pony) не подходят нашему стилю «полевой справочник существ». Модель сама пишет, что они для аниме-эстетики.
5. **Тяжёлые** (Qwen-Image-2512 57,7 ГБ, PixArt 21,8 ГБ, SD 3.5 Medium с несколькими энкодерами) для одной T4 неудобны.

**Что из списка стоит проверить по карточкам (в S6)**
- DreamShaper XL Lightning: быстрый, на базе SDXL, влезает в T4, лицензия неизвестна.
- Krea 2 Turbo: хорошие отзывы, но заявлены пятна на гладких фонах и ограничение по выручке. Для вас с нулевой выручкой порог $1 млн не помеха, но условия читать полностью.
- Sana Sprint 1.6B: быстрая, но лицензия весов раньше была неясной.

**Что делать**
Ничего не менять в тесте, пока вы не оценили слепые листы klein и SDXL. Если klein устроит, список закрыт. Если нет, Kilo проверит три модели выше по карточкам, и мы проведём второй бейкофф. Если пришлёте хвост списка (модели 19 и 20), посмотрю и их.

---

### [47] ВЫ · 2026-10-22 00:54 UTC

Дай промп чтобы проверить самые лучшие по твоему мнению 5 моделей

---

### [48] CLAUDE · 2026-10-22 00:55 UTC

Мой выбор пяти, с учётом ограничений T4 (fp16, без bitsandbytes), лицензии и стиля «полевой справочник существ»:

1. **FLUX.2 klein 4B**: уже готов в S7, переиспользуем.
2. **SDXL Base + VAE-fix**: уже готов в S7, база для сравнения.
3. **SDXL-Lightning, 8 шагов** (UNet или LoRA): быстрый вариант на SDXL; в G1 мы пробовали 4 шага и вы видели артефакты, поэтому проверяем 8.
4. **DreamShaper XL Lightning**: SDXL-файнтюн с хорошими отзывами по стилизованному арту, влезает в T4.
5. **Krea 2 Turbo**: сильные отзывы, но возможны пятна на гладких фонах и условия лицензии. Идёт условно, после чтения карточки.

Z-Image оставлен в запасе (чёрные кадры в fp16). Sana Sprint тоже запасной (неясная лицензия весов).

```text
MILESTONE S8 (Kilo) - extend the bake-off to 5 models. Do NOT redo completed work: reuse the S7 outputs for FLUX.2-klein-4B and SDXL Base (same 10 scenes, same seeds, same prompt variants; verify their sha256 from the S7 manifests). Do NOT submit anything for Z-Image. Read docs/openmontage/S7_STATE.md, BAKEOFF_S7.md, PROMPTING_FACTS.md, tools/prompting/ (OpenCode-owned, use only).
Scope: docs/ tools/ (not tools/prompting/, not scripts/score_rubric.py) scripts/ tests/ .kilo/. No secrets printed, no paid routes, no bitsandbytes, no CPU fallback, fp16 only, released library versions pinned in each manifest (no git main), never loop on Kaggle status (one status call between phases; do other work meanwhile), stop if free disk < 800 MB. Commit own paths only, never media. Roles inline. State file docs/openmontage/S8_STATE.md; resume at first unfinished phase. Final report max 12 lines.

S8-1 LICENSE AND FIT GATE FIRST (read-only, official Hugging Face cards only, no blogs, no weight downloads): for SDXL-Lightning (ByteDance), Lykon/dreamshaper-xl-lightning, krea/Krea-2-Turbo, and as backups Sana_Sprint_1.6B_1024px and the 3 others you find fastest to check. Per model: license text quote + URL + date, gated yes/no, parameters and total weight size, official dtype, any stated VRAM, pipeline class available in RELEASED diffusers, fp16 on T4 reports. Verdict FITS_T4 | NEEDS_OFFLOAD | TOO_BIG | LICENSE_BLOCKED | UNKNOWN in docs/openmontage/image_gen/CANDIDATES_S8.md. Anything LICENSE_BLOCKED or UNKNOWN on commercial use is NOT run; tell the owner. If Krea 2 Turbo is blocked, replace it with the best-fitting backup (Sana Sprint) only if its weights license is explicitly commercial-OK.
S8-2 RUN the new models (up to 3) one per kernel, back-to-back, same 10 scenes/seeds, 1024x1024, best prompt variant per model from tools/prompting (SDXL-family: structured + short negative prompt; Krea/Sana: follow the official card; if the official card says nothing, prose with subject/anatomy first and no negative prompt). SDXL-Lightning 8-step: official scheduler settings from the card (Euler, trailing timestep spacing, guidance as stated). Persistence rule: up to 4 attempts per model, 90 minutes cap, change something concrete after each failure (released versions, matching transformers, enable_model_cpu_offload, VAE fp16-fix for SDXL-family), never repeat an identical attempt; after the cap mark BLOCKED with traceback path and continue. SUCCESS = 10 images, none black/NaN, manifest job_id/sha256/bytes verified. No upscalers, tiled VAE, face detailers or sharpeners (they confound the comparison).
S8-3 MEASURE per model: load time, steady seconds/image (exclude warm-up), usable images per minute, peak VRAM, black/NaN/OOM count, attempts, versions. Objective QC flags per image (blur, text-like artifacts, pHash duplicates); note that the text detector was unreliable in S7 and say so.
S8-4 AGENT SELF-ASSESSMENT (advisory only, label "agent opinion, not independent, a vision model can miss anatomy errors"): 0-2 rubric per image for anatomy, geometry, count/relation, texture, text, usefulness, plus style fit with STYLE_BIBLE.md; ranking and which scenes are weakest per model.
S8-5 OWNER PACK (blind, projects/s8_blind/, gitignored): for each of the 10 scenes one sheet with up to 5 panels labelled A-E in a random order per scene (mapping.json separate, agent ranking NOT shown), max 1600 px wide for phones; results.csv template (scene, best_panel, second_best, worst_panel, anatomy_ok per panel, comment). Extend the tally script (test-first) to 5 models: wins, second places, anatomy-ok counts, speed/VRAM table, "TIE" if the top two differ by <=1 win, and "AGENT vs OWNER agree/disagree". If the owner already scored S7, import those scores as a second pass but do not mix them silently.
S8-6 REPORT docs/openmontage/image_gen/BAKEOFF_S8.md: observed vs assumed, license table, attempts log, speed/VRAM table, objective QC, advisory ranking, BLOCKED causes, owner steps. No winner declared by the agent. Update S8_STATE.md and LESSONS.md; print stop-Codespace commands.
```

**Что делать вам**
- Если ещё не оценили слепой пакет S7, оцените его (10 минут). Это не пропадёт: агент использует ваши оценки как вторую выборку.
- 5 панелей на телефоне читаются хуже, чем 2. Если неудобно, оцените только «лучшая панель» и «худшая».
- Время: три новые модели по 25-40 с на картинку дадут около часа GPU. Проверьте, что квота Kaggle (около 30 часов в неделю) не исчерпана.

Что не знаю: подходят ли карточки DreamShaper XL Lightning и Krea 2 Turbo по лицензии. Агент прочитает их до запуска, и если лицензия закрыта для коммерции, модель не запустится.

---

### [49] ВЫ · 2026-10-22 00:58 UTC

И ещё промп чтобы за один промп достроить фабрику до 100 процентов и мне всё равно сколько это часов займет нужно именно за один промп и исползуй свой мастер план

---

### [50] CLAUDE · 2026-10-22 00:59 UTC

Честная оговорка: полностью автоматически до 100% довести нельзя. Часть пунктов спецификации требует вас (слепая оценка картинок, права, публикация, метрики YouTube). Поэтому промпт устроен так: агент делает всё, что возможно без вас, на спорных местах берёт безопасный вариант по умолчанию и помечает `OWNER_GATED`, а не ждёт и не выдумывает. Если сессия оборвётся, он продолжит с места остановки по файлу состояния.

```text
MILESTONE MEGA (Kilo) - build the factory toward the "100%" definition in FACTORY_100_SPEC.md in ONE resumable run. Runtime is unlimited; correctness and honesty matter more than speed.

SOURCE OF TRUTH: FACTORY_100_SPEC.md (master plan; do NOT edit it; propose changes in docs/openmontage/SPEC_CHANGE_REQUESTS.md). Also read first: docs/openmontage/FACTORY_GAP_AUDIT.md, all docs/openmontage/*_STATE.md, OPENCODE_REQUESTS.md, BAKEOFF_S7.md / BAKEOFF_S8.md if present, LESSONS.md, AGENTS.md. Do NOT redo completed work; verify it quickly (tests, hashes) and move on.

STATE: docs/openmontage/MEGA_STATE.md. At start read it and RESUME at the first phase not in {DONE, OWNER_GATED, BLOCKED}. After EVERY phase: update it (status, evidence, commit hash), commit own paths only (never git add -A, never AGENTS.md, .env*, media, secrets), git pull --rebase (commit or stash your own files first), push non-force.

SCOPE (ownership): docs/ tools/ (EXCEPT tools/prompting/) scripts/ (EXCEPT scripts/score_rubric.py) tests/ config/ .kilo/. Never touch youtube-niche-finder/ or tools/prompting/ (OpenCode owns them; write change requests to OPENCODE_REQUESTS.md). Roles inline: say "inline, not independent".

HARD RULES (from the spec, never relax): $0, no paid routes, no secrets printed (KAGGLE_API_TOKEN yes/no only), rights fail-closed, claim_id resolution on every factual sentence, AI illustrations always labelled and never as real footage, no AI upscaling of footage, no voice cloning, no music without stored license evidence, manual publishing only, no OAuth to YouTube, fail-closed QC (cannot run => BLOCKED/NOT_RUN, never PASS), never loosen QC thresholds silently, never claim a command/test/commit/push/Kaggle run you did not observe. Code is test-first (show red, then green); run the new tests AND the existing fast suite with exit codes after every phase. Never loop or sleep on Kaggle status: submit, record in state, work on other phases, one status call between phases. Stop the WHOLE run only if free disk < 800 MB after you delete caches/old renders YOU created (never delete git, projects/ review packs, or owner files).

PERSISTENCE RULE: per blocker up to 4 attempts, and after each failed attempt CHANGE something concrete (versions, approach, scope); never repeat an identical attempt; cap 90 minutes wall time per blocker; then BLOCKED with exact error + traceback path and continue with independent phases.

OWNER-GATED RULE: you never wait for the owner. For anything needing a human decision (blind image scoring, SCR approvals, voice sign-off, emblem policy, guardian/AdSense, disclosure wording, publication, YouTube metrics) use the SAFEST DEFAULT, implement the machinery so the decision is a one-line config change, mark the item OWNER_GATED in MEGA_STATE.md and OWNER_ACTIONS.md with exact steps, and continue. Never pretend a gated item is done.

PHASES (execute in order; skip any already DONE and verified):
G0 PREFLIGHT: git status, HEAD, df -h, tests baseline (pytest --collect-only count, CI fast suite), read-only audit refresh: list which spec layers L1-L10 are PASS/FAIL/NOT_CHECKED now with evidence (update FACTORY_GAP_AUDIT.md as an appendix, do not delete history). Apply the owner's decisions on SPEC_CHANGE_REQUESTS.md ONLY where the owner marked them approved; otherwise leave them.
G1 QC AND CONTRACTS (L7, L2): finish any QC gaps from the audit: thresholds from config everywhere (verified), claim_ids_resolve on every ID, SINGLE_SOURCE blocking rule, rights_basis/credits/added-value/AI-illustration/speculative-label gates all wired and tested, NOT_RUN handling, qa_report schema validated by a test. Add EVALS.md fixed tasks as an executable script (scripts/run_evals.py) and run it.
G2 EPISODE PIPELINE (L6, L10): scripts/run_episode.py <episode_id> runs ALL stages for any episode (no Artemis/ISS hardcoding), per-stage checkpoint/resume/idempotency, wall-time and disk logging, fail-closed; unit tests with fake stages plus one integration test on a tiny synthetic episode (generated with ffmpeg lavfi, no network). Wire packaging, speculative-illustration gate, cost/zero-cost accounting, and review_pack into the pipeline (the audit said they were unwired).
G3 IMAGE ENGINE (L4): use the owner's blind scoring from projects/s7_blind/results.csv or s8_blind/results.csv ONLY if the files are filled (tally script); otherwise default model = the one the S7/S8 reports rank first as ADVISORY and mark "model choice OWNER_GATED". Implement tools/illustration: batch generation via the Kaggle bridge from creature/scene YAML specs, manifest verification, retries per rules, image QC (blur, pHash, aspect, text-like flags), "Illustration"/"Speculative illustration" label overlay, per-episode image budget (e.g. images per minute), caching so reruns do not regenerate approved images. Runs of 80-100 images must be submitted as ONE kernel job per model with batching; record real seconds/image.
G4 VISUAL SOURCES (L3): adapters on recorded fixtures (no network in tests): NASA Image & Video Library, Internet Archive (curl -L, real file lists, never guessed names), Wikimedia Commons, Library of Congress, NARA, DVIDS, Met, Smithsonian, Rijksmuseum, National Gallery of Art. Rights classifier regression tests: third-party credit => REJECT, missing rights => unknown, NC/ND => REJECT, emblem-as-main-picture => REJECT. SOURCE_REGISTRY.md refreshed from official terms pages (cite URL + date). Live probes at most 30 requests, only for fixtures.
G5 AUDIO AND VOICE (L5): TTS tool with license gate (Piper lessac refused), Kokoro ONNX path, word timestamps, subtitles, finish_audio with loudness verified on the FINAL MP4, music policy enforced in code (no music without license record). Test a 10-minute synthetic script end to end (CPU) and record real-time factor.
G6 EDITING AND RENDER (L6): EDL with per-cut rationale for any episode; motion-variety lint (no two identical moves in a row, shot-length variation, still-only limit); animated diagram generators (timeline, food web/energy flow, depth/scale bar, key-number cards with claim_ids) as reusable components rendered with ffmpeg/PIL (HyperFrames only if already proven); chapter mode for >6 min with per-chapter resume; crossfade concat; final loudness pass. Draft-render mode and contact-sheet generator.
G7 NICHE AND TOPIC LAYER (L1): niche profile loader + validator for the three YAML profiles; topic viability gate as a tested function (min legal visuals / sources); measurement reader that ingests OpenCode CSV/JSON demand reports (do NOT call the YouTube API; if no fresh data, status NOT_MEASURED and the gate refuses to recommend). Episode template engine with >=3 structures per niche so episodes are not interchangeable.
G8 PILOT EPISODE A (speculative evolution, 10-12 min): "How could life survive beneath a frozen alien ocean?" End to end through run_episode.py: claim ledger from the existing S1-4 work (extend to two sources per real-science claim, only from retrieved pages with URLs), script 10-12 min with claim_ids, creature/scene specs (use OpenCode's YAML specs in docs/openmontage/niches/speculative_evolution/creatures/ read-only), ~80-100 illustrations via G3, animated diagrams, narration, subtitles, EDL, render, finish_audio, qc.py with ALL inputs, package draft. Status NOT_PUBLISHABLE with reasons (owner review, SINGLE_SOURCE items, voice sign-off, disclosure, model choice if gated). If the image engine is BLOCKED, build the episode with the best available verified model and say so.
G9 PILOT EPISODE B (real-footage track, ISS/space): upgrade the existing ISS episode to 6-8 min: more HD NASA clips (rights-checked), watermark/emblem cropping recorded in edit_decisions, animated diagrams in the timeline, credits burned in, ledger with two sources on load-bearing claims. NOT_PUBLISHABLE with reasons.
G10 PACKAGING AND SHORTS (L8): per episode 3 truthful titles, thumbnail candidates (own graphics/illustrations, no emblems/people), description with chapters and credits block generated from rights records, synthetic-content disclosure checklist citing the CURRENT official YouTube help pages (fetch, paraphrase, URL + access date), Shorts plan <=45 s with claim_ids.
G11 REVIEW AND VERIFICATION (L9): scripts/review_pack.py bundles reports only; owner checklists and contact sheets per episode; blind-scoring tally for images; independent-reviewer prompt in REVIEW_PACK.md (a fresh read-only session must be able to review from those files alone). Run the full EVALS and the full test suite (pytest with the youtube-niche-finder exclusion) and record exact exit codes.
G12 OPERATIONS AND PORTABILITY (L10): rebuild script verified fail-closed with "verified N/N assets" on a clean venv dry run; committed manifests (URLs, sha256, rights) for every episode; CI-style fast suite; disk/time logs; analytics importer for YouTube Studio CSV (parse, per-chapter retention drops, CTR/AVD/first-30s tables, go/no-go summary; test on a synthetic CSV only, real metrics are OWNER_GATED); update LESSONS.md/CHANGELOG.md/OWNER_ACTIONS.md.
G13 FINAL 100% SCORECARD: write docs/openmontage/FACTORY_100_SCORECARD.md mapping every line of spec section 7 ("Definition of 100% done") to PASS / FAIL / BLOCKED / OWNER_GATED with evidence (file, test, commit, command + exit code). Be strict: no item is PASS without observed evidence. List the exact remaining owner actions in priority order and the exact next agent milestone for anything FAIL/BLOCKED. Do NOT claim "100%" unless every item is PASS; the real-world items (published episode, Studio metrics, independent review, owner approvals) will normally remain OWNER_GATED and must be reported as such.

FINAL REPORT (max 12 lines, no tables): Status (DONE / PARTIAL / BLOCKED), Commit, Phases DONE count vs OWNER_GATED vs BLOCKED, Done (3 bullets), Failed/NOT_CHECKED (3 bullets), Owner decisions needed (3 bullets), Next action (1 sentence), and the exact stop-Codespace command. Never shorten honesty: say it first if something failed.
```

**Что нужно знать перед запуском**
- **Диск:** сейчас около 2,5 ГБ. Перед стартом удалите старые рендеры и кэши вне git (`projects/` для apollo9, `/tmp` кэши). Агент остановится при менее 800 МБ.
- **Часы Codespaces:** такой прогон идёт много часов, и лимит GitHub может кончиться на середине. Состояние пишется после каждой фазы, поэтому продолжить можно в любом аккаунте через `HANDOFF_NEW_ACCOUNT.md`.
- **Если сессия оборвётся**, отправьте агенту только это:

```text
Resume MEGA. Read docs/openmontage/MEGA_STATE.md and continue at the first unfinished phase. Do not redo completed work. Same rules as before. Final report max 12 lines.
```

- **Что вы делаете параллельно (не блокирует агента):** слепая оценка картинок S7/S8 (если сделаете до фазы G3, агент использует её), ответы на SCR-01…10, письмо родителю про голос и AdSense.
- **Одновременно запускать OpenCode не нужно**, но если запустите его замеры спроса (после сброса квоты YouTube), отчёты агент подхватит из `docs/openmontage/audit/demand/`.
- **Что не получится «за один промпт»:** реальная публикация, метрики YouTube, ваша оценка картинок и голоса, независимое ревью. Они останутся в списке `OWNER_GATED`, и это правильно.

---

### [51] ВЫ · 2026-10-22 04:43 UTC

*[приложен файл: 1000266149.jpg]*

*[изображение: скриншот/фото от пользователя]*

---

### [52] CLAUDE · 2026-10-22 04:43 UTC

**S8 выполнен честно. Картинки четырёх моделей готовы к вашей слепой оценке, победителя пока нет.** Батарея 15%, поставьте телефон на зарядку.

**Результат (отчёт Kilo, MiniMax M3.1 Flash)**
- **SDXL-Lightning:** 10/10 картинок, **3,9 с на картинку**, 9,2 ГБ памяти.
- **DreamShaper XL Lightning:** 10/10, 5,1 с на картинку, 10 ГБ.
- **SDXL Base и klein:** взяты из S7 (41 и 25 с на картинку), хеши сверены.
- **Для 100 картинок:** Lightning около 7 минут, DreamShaper около 9, klein около 41, SDXL Base около 69. Разница в 6 раз по скорости.
- **Krea 2 Turbo помечена LICENSE_BLOCKED**, но причина шаткая: карточка с гейтом, PDF лицензии агент не смог прочитать, вес около 25,6 ГБ. Это «не проверено», а не «запрещено». Для T4 она всё равно тяжёлая.
- **SDXL-Turbo заблокирована** из-за порога выручки $1 млн. При нулевой выручке это не помеха, но агент был осторожен, и я не считаю это потерей.
- **SANA-Sprint заблокирована:** в fp16 все кадры чёрные, нужен bf16, а на T4 его нет. Я бы её отбросил, а не разрешал bf16.

**Мнение агента (не независимое, модель с картинками ошибается):** klein лучше (7 грубых артефактов, 5 из 10 годных), SDXL-Lightning 22 грубых артефакта и 1 годная, SDXL 25 и 0, DreamShaper 28 и 0. Агент сам отмечает, что Lightning дал лучшие картинки пищевых цепей, а скорость говорит в его пользу. Автоматический детектор текста снова ненадёжен.

**Что делать сейчас (10 минут, это решает всё)**
1. Откройте листы `projects/s8_blind/` через порт 8080 (в папке `python3 -m http.server 8080`).
2. На каждой из 10 сцен выберите лучшую панель, вторую и худшую, отметьте сломанную анатомию, заполните `results.csv`.
3. Команда из отчёта: `python scripts/s7_tally.py --csv projects/s8_blind/results.csv --mapping projects/s8_blind/mapping.json --agent docs/openmontage/image_gen/S8_AGENT_ASSESSMENT.json --title "S8 blind-pack tally"`. Она покажет итог по вашим оценкам и «TIE», если разрыв в одну победу.
4. Если оценки S7 у вас не заполнены, S7-пакет тоже можно оценить, он быстрее (2 панели).

**Как будет выглядеть решение:** если вас устроит качество klein, выбираем его (дороже по времени, лучше по анатомии). Если вас устроит Lightning или DreamShaper, выигрываем в 6 раз скорости. Дополнительно можно улучшать Lightning стилевым LoRA.

**Два предупреждения**
1. **Внизу ветка уже `kilo/mega-100`, а не `factory/business-documentary-pilot`, и `0↓ 15↑`.** Значит, MEGA запущен на новой ветке и имеет 15 коммитов, которые ещё не отправлены. Следите, чтобы агент выполнил `git push` в конце, иначе потеряете работу при остановке Codespace. По коммитам MEGA уже сделал части G2-G6.
2. **Остановите Codespace** после оценки (`gh codespace stop -c scaling-spoon-wv7wq975xwqjhgqgx`, команда в отчёте) и проверьте остаток часов GitHub. При 15% батареи не запускайте ничего тяжёлого.

---

### [53] ВЫ · 2026-10-22 06:16 UTC

Тогда берём самый лучший модель и строим фабрику вокруг ИИ фото видео дай сразу 10-20 промптов и последний чтобы сделал отчёт прошлых промптов что сделано что нужно сделать и так далее

---

### [54] CLAUDE · 2026-10-22 06:17 UTC

Сначала одна важная поправка: **победителя выбираете вы, а не я и не агент.** Вы ещё не заполнили `results.csv`. Поэтому в промптах модель берётся из вашей оценки, а если файл пуст, по умолчанию стоит **klein** (мнение агента, помечено как «ждёт владельца»), и смена модели это одна строка в конфиге. Так вам не придётся переделывать фабрику после оценки.

«ИИ-видео» я понимаю так: видео, собранное из ИИ-картинок с движением (наезд, параллакс, анимированные схемы). Настоящие ИИ-видеоклипы на T4 я не проверял, поэтому для них есть отдельный разведочный промпт с ответом по умолчанию «нет».

Запускайте **по очереди**: следующий после отчёта предыдущего. Все промпты опираются на `RUN_RULES.md`, который создаёт P0.

**P0. Общие правила и порядок в git**
```text
P0 (Kilo). Read FACTORY_100_SPEC.md, docs/openmontage/MEGA_STATE.md, all *_STATE.md. Do not redo completed work. 1) git status/branch: work is on branch kilo/mega-100 with unpushed commits; push it non-force to origin and report the result; list stray untracked files (.opencode/, apollo_11.json etc.) without adding them. 2) Create docs/openmontage/RUN_RULES.md (commit it): scope = docs/ tools/ (not tools/prompting/) scripts/ (not scripts/score_rubric.py) tests/ config/ .kilo/; never edit FACTORY_100_SPEC.md, AGENTS.md, .env*; never commit media/secrets; commit own paths only; pull --rebase, push non-force; test-first with red then green and exit codes; no paid routes; fail-closed QC; no silent threshold changes; never loop/sleep on Kaggle (submit, record state, one status call between phases); persistence rule: up to 4 attempts per blocker, change something concrete each time, 90 min cap, then BLOCKED; owner-gated items use a safe default and are marked OWNER_GATED, never waited on; stop if free disk < 800 MB after deleting caches you created; final report max 12 lines (Status, Commit, Done, Failed/NOT_CHECKED, Owner decision, Next action); never claim what you did not observe; roles inline, not independent. 3) State file docs/openmontage/PIPE_STATE.md listing prompts P0-P14 as PENDING. Final report max 12 lines.
```

**P1. Закрепление модели картинок**
```text
P1 (Kilo). Follow docs/openmontage/RUN_RULES.md. Lock the image model as CONFIG: config/image_engine.json {model, scheduler, steps, guidance, dtype, seed_policy, prompt_variant, status}. Logic: if projects/s7_blind/results.csv or s8_blind/results.csv is filled, run the tally and set the model to the OWNER's winner (status OWNER_CONFIRMED); otherwise set klein (agent advisory pick, status OWNER_GATED) and also record SDXL-Lightning as the declared FAST FALLBACK for drafts. Build a model-adapter interface so every model (klein, SDXL-Lightning, DreamShaper XL Lightning, SDXL Base) is a config entry with its verified versions, prompt rules from tools/prompting (read-only), and measured seconds/image from the S7/S8 manifests. Changing the model must need only the JSON edit (test: swap model, same pipeline runs on a fake generator). Report real measured speeds and the projected GPU minutes for 100 images per model.
```

**P2. Система стиля и постоянство существ**
```text
P2 (Kilo). Follow RUN_RULES.md. For each niche profile (space_iss, art_history, speculative_science, speculative_evolution) finalize STYLE_BIBLE.md + a machine-readable style file (palette, line style, camera vocabulary, negative-style constraints written positively where the model has no negative prompt, label rule). Build a consistency kit with the LOCKED model: canonical creature sheet generation (front/side/3-4 view per creature from OpenCode's YAML specs, read-only), seed/reference policy, img2img or reference-image workflow ONLY if the locked model's official card supports it (cite it), otherwise seed + prompt-anchoring. Read-only feasibility note for LoRA training on a Kaggle T4 for the locked model family (time, memory, license of adapters) in docs/openmontage/image_gen/LORA_FEASIBILITY.md; do NOT train anything yet. Tests: spec -> prompt -> deterministic job file; anatomy counts always present in the prompt. No generation unless it is a 4-image smoke job through the bridge.
```

**P3. Генерация целого эпизода**
```text
P3 (Kilo). Follow RUN_RULES.md. Harden tools/illustration for episode scale: one Kaggle kernel per run, batches of 40-100 prompts, resumable (skip images already verified by sha256), per-image seed log, retry only failed prompts, hard fail if images < prompts, budget per episode (images per minute of video, default 6-8), cache of approved images (owner-approved list file) so reruns never regenerate them, manifest with versions/params/model. Add an "image brief" step: from a script, derive one image prompt per visual beat using tools/prompting (read-only), tagged KNOWN/INFERENCE/SPECULATION. Test-first with a fake bridge: partial failure, resume, hash mismatch, unknown beat. Then ONE live job of 24 images with the locked model; record real seconds/image and usable share; no judging of beauty.
```

**P4. Контроль качества картинок**
```text
P4 (Kilo). Follow RUN_RULES.md. Improve image QC without new runtime components unless one is already installed (check pip list, which tesseract; if a better text detector needs a new dependency, write the request to OPENCODE_REQUESTS.md/SPEC_CHANGE_REQUESTS.md and use the existing method). Fix the known weakness: the text-like heuristic missed lettering and over-fired on flat art. Test-first on a fixture set you generate (synthetic images with and without text-like marks), report precision/recall honestly. Add: near-duplicate detection across an episode, palette-drift check against the style file, aspect/size checks, and a REVIEW queue builder that sorts images by objective flags for the owner. Anatomy stays OWNER-judged. Add "owner approved/rejected" ledger (csv) read by P3 cache.
```

**P5. Движок движения (ИИ-видео из картинок)**
```text
P5 (Kilo). Follow RUN_RULES.md. Build the motion engine for stills: pan, push-in/out, diagonal drift with different easing, detail crops, split-screen comparisons, slow parallax with 2-3 layers cut from the image (simple foreground/background separation using masks you derive from the generator's seeds/prompts or manual crop regions defined in the beat spec; use a depth/segmentation model ONLY if its official license is permissive and it runs on CPU/T4 within the rules, otherwise skip and say so), light flicker/bioluminescence pulse overlays, grain, vignette. Each move parameterised in edit_decisions.json; lint: no two identical moves in a row, shot-length variation, max still duration. Render with ffmpeg/PIL; draft mode at lower resolution. Test-first (motion plan generation, lint failures, deterministic output hash on a synthetic image). Produce a 30 s demo from 8 existing images (reuse S7/S8 images in projects/), with contact sheet, NOT_PUBLISHABLE.
```

**P6. Разведка: настоящие ИИ-видеоклипы (только чтение)**
```text
P6 (Kilo). Follow RUN_RULES.md. READ-ONLY feasibility study of open-weights image-to-video / text-to-video for a free Kaggle T4 (16 GB, fp16 only, no bf16). Read ONLY official Hugging Face/GitHub cards for the 4 most recent open models you can find (check the Artificial Analysis open-weights video leaderboard and Hugging Face trending for 2026; include LTX-family if present). Per model: license quote + URL + date, commercial use, gated, parameters/weights size, required dtype, stated VRAM, clip length/resolution/fps, pipeline in the RELEASED diffusers, any T4 reports. Write docs/openmontage/video_gen/VIDEO_FEASIBILITY.md with verdict FITS_T4 | NEEDS_OFFLOAD | TOO_BIG | LICENSE_BLOCKED | UNKNOWN. Estimate GPU minutes for 5 s of clip only if a measured source exists, otherwise UNKNOWN. Default decision: NO AI video clips in v1; motion comes from P5. Do not download weights, do not submit Kaggle jobs. Note the YouTube disclosure implications of realistic synthetic video (cite the official help page).
```

**P7. Библиотека анимированных схем**
```text
P7 (Kilo). Follow RUN_RULES.md. Build reusable animated graphic components rendered with ffmpeg/PIL (no new runtime components): timeline, depth/pressure scale, energy-flow diagram, food-web graph, comparison bars, map with route (from simple coordinates), key-number card (shows claim_id and source), chapter card, source card, credits roll, "Speculative illustration" label. Each component takes a small JSON spec and outputs frames/clip at 1080p30; palette from the niche style file; labels drawn in the editor (never inside AI images). Test-first: spec validation, deterministic output hash on fixtures, text fits the safe area, claim_id mandatory on factual cards. Contact sheet of every component in projects/ (gitignored).
```

**P8. Сценарные шаблоны и привязка кадров**
```text
P8 (Kilo). Follow RUN_RULES.md. Build the episode template engine for AI-image niches: >=3 distinct structures per niche (e.g. "constraint -> consequence -> design", "field guide dossier", "what-if chain"), a script format where each sentence has claim_ids and a KNOWN/INFERENCE/SPECULATION tag, and an automatic beat plan: every sentence/beat maps to a visual (illustration, animated graphic, real-footage slot) with the image brief from P3. Gates (test-first): SPECULATION sentences must carry the on-screen speculative label, single-source load-bearing claims are flagged, no sentence without a visual, no two consecutive identical visual types beyond the niche limit, runtime split (illustration/graphic/footage) within niche limits. Use OpenCode's fact packs (docs/openmontage/evidence/spec_evo/ read-only) as sample ledgers.
```

**P9. Озвучка и звук длинных эпизодов**
```text
P9 (Kilo). Follow RUN_RULES.md. Make narration robust for 10-20 minute episodes: Kokoro ONNX CPU, chunking by sentence, pauses by punctuation, per-chapter synthesis with resume, word timestamps -> subtitles (<=2 lines, drift check), finish_audio on the FINAL MP4 (loudness verified after AAC), license gate (Piper lessac refused), music policy enforced (no music without license record). Add an owner A/B listening pack for pacing (2 speeds, 2 voices from Kokoro's own list) as OWNER_GATED. Test a 12-minute synthetic script end to end and report real-time factor and disk use. Owner voice sign-off stays OWNER_GATED.
```

**P10. Пилот A: сборка целого эпизода**
```text
P10 (Kilo). Follow RUN_RULES.md. Build pilot episode A through scripts/run_episode.py with the LOCKED model: "How could life survive beneath a frozen alien ocean?", 10-12 min. Use the existing ledger/script (S1-4), extend to two retrieved sources per real-science claim, structure from P8, creature sheets from P2, ~80-100 illustrations from P3 (one kernel, resume-safe), QC from P4, motion from P5, graphics from P7, narration from P9, subtitles, EDL, render, finish_audio, qc.py with ALL inputs, package draft. NOT_PUBLISHABLE with reasons (owner review, voice sign-off, disclosure, model choice if OWNER_GATED, SINGLE_SOURCE items). Commit small artifacts to docs/openmontage/<episode>/artifacts/. 12-frame contact sheet and final video path in projects/ (gitignored).
```

**P11. Пилот B: проверка повторяемости**
```text
P11 (Kilo). Follow RUN_RULES.md. Build a SECOND episode with a different structure and niche profile to test repeatability: use the OpenCode fact pack docs/openmontage/evidence/spec_evo/pilot3_low_gravity_flying_food_web.md (read-only) or pilot2, 6-8 min. Count manual fixes needed versus pilot A and list every place the pipeline needed hand edits; fix the generic causes test-first. Same gates and NOT_PUBLISHABLE rules.
```

**P12. Упаковка, Shorts, обложки**
```text
P12 (Kilo). Follow RUN_RULES.md. For both pilots: 3 truthful titles each, thumbnail candidates from the locked model's illustrations (1280x720, large readable text drawn in the editor, no emblems/people, high contrast at phone size), description with chapters and a credits/attribution block generated from rights records (AI illustrations credited as generated with model name + license), 3 Shorts per episode <=45 s (vertical 9:16 render from the same assets, each sentence with claim_id), synthetic-content disclosure checklist citing the CURRENT official YouTube help pages (fetch, paraphrase, URL + access date; note which parts of our content count as realistic vs clearly fictional). Everything NOT_PUBLISHABLE; the owner publishes manually.
```

**P13. Проверка, тесты, переносимость**
```text
P13 (Kilo). Follow RUN_RULES.md. Verification pass: run scripts/run_evals.py (add any missing fixed tasks: qc fails a bad MP4; finish_audio hits loudness/true peak; TTS refuses Piper lessac; claim_ids fails on unknown id in the middle of a line; third-party-credit clip -> REJECT; rebuild script fails on hash mismatch; image gate fails an unlabelled AI image), the full pytest suite with the youtube-niche-finder exclusion, the CI fast suite, rebuild_slice_assets.sh dry-run on a clean venv ("verified N/N assets"), and portability: every episode has committed manifests (URLs, sha256, prompts, seeds, rights). Build REVIEW_PACK.md so a fresh READ-ONLY session with no chat context can review the pilots from reports only; print the paste-ready reviewer prompt. Record exact commands and exit codes. Fix defects test-first; anything you cannot fix is BLOCKED with evidence.
```

**P14. Итоговый отчёт по всем прошлым промптам**
```text
P14 (Kilo). Follow RUN_RULES.md. Read-only except one report file. Read FACTORY_100_SPEC.md, FACTORY_GAP_AUDIT.md, MEGA_STATE.md, PIPE_STATE.md and every *_STATE.md, all BAKEOFF reports, OWNER_ACTIONS.md, SPEC_CHANGE_REQUESTS.md, git log since the F0 audit commit. Write docs/openmontage/FACTORY_PROGRESS_REPORT.md (commit it): 1) per prompt P0-P13 and the earlier milestones (F0, F1-fix, S1-S8, MEGA G0-G13): status DONE / PARTIAL / BLOCKED / OWNER_GATED / NOT_STARTED with evidence (commit, test, command + exit code), 2) the 100% scorecard: every line of spec section 7 as PASS / FAIL / BLOCKED / OWNER_GATED, strict, no PASS without observed evidence, 3) what is verified vs only agent-reported, 4) measured numbers (seconds/image per model, GPU minutes per episode, wall time per stage, test counts, disk), 5) known defects and risks, 6) the exact remaining work as an ordered backlog for the agents (next 5 milestones with acceptance tests), 7) the owner action list in priority order (blind scoring of S7/S8 if not done, SCR approvals, voice sign-off with a guardian, emblem policy, disclosure wording, first manual upload, Studio metrics export), 8) a one-paragraph honest estimate of readiness that distinguishes "factory as a pipeline" from "channel as a business" (the latter is unproven until audience data exists). Final report max 12 lines plus the stop-Codespace command.
```

**Что нужно от вас**
1. **Оцените слепые листы S7/S8**, иначе P1 поставит klein с пометкой «ждёт владельца». Это 10 минут.
2. **Диск и часы:** около 2,5 ГБ и ограниченные часы Codespaces. Перед стартом удалите старые рендеры. После каждого промпта проверяйте, что ветка запушена (`git status -sb`).
3. **Не запускайте два промпта подряд без отчёта**: P3, P10 и P11 используют Kaggle, и параллельные заявки сломают очередь.
4. **OpenCode** в этой серии не занят. Когда сбросится квота YouTube, дайте ему перезапуск S2 (замер спроса), иначе фабрика будет строиться вокруг ниши без измеренного спроса.
5. Разведка по видео (P6) может подсказать, что настоящие ИИ-клипы на T4 нереальны. Это нормальный результат.

---

### [55] ВЫ · 2026-10-22 06:18 UTC

Дай промп для опенкод чтобы он изучил нишу лимит уже сбросился

---

### [56] CLAUDE · 2026-10-22 06:18 UTC

Квота YouTube обновляется в полночь по тихоокеанскому времени. Сейчас это около **12:00 по Алматы**, то есть у вас на часах 11:18, и сброс мог ещё не произойти (или уже был вчера, но вчерашние вызовы потратили новую квоту). Поэтому в промпте стоит один пробный запрос: если вернётся 429, агент остановится и сообщит, а не будет долбить API.

```text
MILESTONE S9 (OpenCode) - demand measurement for the AI-still niches. Resume S2; do NOT redo completed work (S6 policy snapshot is done, S3 prompt/fact work is done). Read reports/S2_STATE.md, reports/s2-policy.md and your cached CSV/JSON first and reuse them.
SCOPE: ONLY youtube-niche-finder/ (reports/, scripts/). Never touch docs/, tools/, .kilo/, AGENTS.md, .env*. Run `git check-ignore .env` first. No secrets printed, no commits. Use scripts/mcp-host.sh if the OpenCode wrapper fails. Label every number MEASURED (API) or ESTIMATE. No RPM or earnings claims. n<5 = NOISE. Quota failure = NOT_MEASURED (never zero, never NOISE).

QUOTA GUARD: make ONE test search first. If it returns 429/quotaExceeded, STOP, write the exact error and timestamp to reports/S9_STATE.md and tell the owner to rerun after the reset (midnight Pacific = 12:00 Almaty). Never retry a failing search. Hard cap 50 search.list calls in total (about 10 per niche), cache every response on disk before using it, prefer uploads playlists / videos.list / channels.list (cheap units) for channel history.

NICHES (English, long-form >= 8 min, last 12 months): A speculative evolution / alien ecosystems; B science-based "what if" scenarios; C speculative worldbuilding (invented worlds/planets); D mythology and folklore explainers (control); E original anomaly / lore case files. Seeds from the owner's two external reports: ChatGPT audit (field-guide dossiers, what-if chains, world atlas) and Perplexity (serialized invented worlds, alien ecosystems, deep-time futures).

FOR EACH NICHE:
1. Breakouts: videos >50k views from channels <50k subscribers; also >=30k views from channels <10k subs. Per video: title, channel, subs, views, duration, publish date, link, outlier multiple = views / median of the channel's last 20 long uploads (exclude the video itself and uploads younger than 7 days).
2. Replication: count DISTINCT channels with multiple >= 5. Verdict STRONG (>=3 channels), MIXED, WEAK, NOISE, or NOT_MEASURED.
3. Shorts share among breakouts, median duration, upload cadence, how many breakouts look like AI-still channels (judge only from title/thumbnail/description/visible metadata; say ESTIMATE).
4. AI tolerance: for the top 5 breakouts per niche sample up to 100 comments each and COUNT (no usernames) praise vs complaints about AI images/voice/slop; list the most frequent complaint themes in your own words.
5. Template saturation: near-identical title patterns, identical thumbnail layouts among top results.
6. Whitespace: top 10 incumbents (subs, median views); 10 sub-topics with good views but few long videos (from your data only).
7. Packaging patterns of the breakouts: title patterns, thumbnail style (descriptive words only), chapter use, typical length.

Also write reports/s9-compare-niches.md: ranked niches with n, noise warnings, unknowns, and a proposal (owner decides). Do not recommend any niche without measured numbers. Include a section "what the evidence cannot tell us" and cheap tests for it. Update reports/S9_STATE.md. Final report max 12 lines (Status, Done, Failed/NOT_MEASURED, Owner decision, Next action), ending with cp commands copying the reports into docs/openmontage/audit/demand/ (the owner runs them).
```

**Что сделать до запуска**
- Если сомневаетесь, прошёл ли сброс, подождите до 12:05 по Алматы. Пробный запрос защитит квоту, но лучше не тратить попытку впустую.
- Перед запуском закоммитьте или спрячьте изменения в `docs/` (Kilo работает над MEGA), чтобы `git pull` не конфликтовал. OpenCode коммитов не делает, поэтому конфликтов быть не должно.
- Параллельно с Kilo запускать можно: у них разные папки.

**Что ожидать честно:** 50 поисков на 5 ниш это немного. Если выборка будет меньше 5 видео, отчёт покажет NOISE, и нужно будет ждать следующего дня. Один выброс (как 1,8 млн просмотров раньше) формат не доказывает.

---

### [57] ВЫ · 2026-10-22 09:22 UTC

Как думаешь есть другая ниша или интернет заработок как Ютуб но можно было с 16 лет

---

### [58] CLAUDE · 2026-10-22 09:22 UTC

Проверю актуальные возрастные ограничения платформ и правила для 16-летних в Казахстане, чтобы не говорить по памяти.

> 🔎 Веб-поиск (standard): Казахстан работа с 16 лет Трудовой кодекс несовершеннолетние заработок онлайн фриланс самозанятость возраст

> 🔎 Веб-поиск (standard): minimum age 18 Fiverr Upwork Etsy Patreon Ko-fi Gumroad 16 year old parent account requirements 2026

> Найденные источники:
>   - Школьники Казахстана могут заработать летом до 150 000 тенге – где искать работу с 14 лет — https://digitalbusiness.kz/2026-05-21/shkolniki-kazahstana-mogut-zarabotat-letom-do-150-000-tenge-gde-iskat-rabotu-s-14-let/amp/
>   - Школьники Казахстана могут заработать летом до 150 000 тенге – где искать работу с 14 лет — https://digitalbusiness.kz/2026-05-21/shkolniki-kazahstana-mogut-zarabotat-letom-do-150-000-tenge-gde-iskat-rabotu-s-14-let/
>   - Работа и несовершеннолетние — https://kazpravda.kz/n/rabota-i-nesovershennoletnie/
>   - Подростки Казахстана все чаще подрабатывают летом — https://24.kz/ru/news/social/769973-podrostki-kazakhstana-vse-chashche-podrabatyvayut-letom
>   - 2379600 gde kazahstanskie shkolniki mogut nayti rabotu na leto i skolko mozhno zarabotat — https://www.nur.kz/society/2379600-gde-kazahstanskie-shkolniki-mogut-nayti-rabotu-na-leto-i-skolko-mozhno-zarabotat/
>   - kargoo.kz — https://kargoo.kz/loader/load/14074
>   - trudovye otnosheniya s nesovershennoletnimi rabotnikami pravovye i bukhgalterskie aspekty — https://cdb.kz/sistema/biblioteka-bukhgaltera/articles/trudovye-otnosheniya-s-nesovershennoletnimi-rabotnikami-pravovye-i-bukhgalterskie-aspekty
>   - Подработка с 16 лет с гражданством РФ в городе Астана? — https://harant.ru/questions/q-212138/
>   - Какие условия заключения Трудового Договора с 16 летними? — https://dogovor24.kz/questions/kakie-usloviya-zaklyucheniya-trudovogo-dogovora-s-16letnimi-22320.html

> Найденные источники:
>   - Young Founder Reference — https://bigideasdb.com/side-hustle-age-requirements
>   - May 28, 2020 06:12:32 PM by Alec T — https://community.upwork.com/t5/Freelancers/Freelancer-is-under-the-age-of-18-What-steps-do-I-need-to-take/m-p/756562
>   - Als minderjarige Fiverr gebruiken: hoe je veilig blijft en de regels naleeft — https://help.fiverr.com/hc/nl/articles/37554848507665-Als-minderjarige-Fiverr-gebruiken-hoe-je-veilig-blijft-en-de-regels-naleeft
>   - Richtlijnen voor de community: beleid met betrekking tot minderjarigen — https://help.fiverr.com/hc/nl/articles/37333186324625-Richtlijnen-voor-de-community-beleid-met-betrekking-tot-minderjarigen
>   - Community Standards: Minors policy — https://help.fiverr.com/hc/en-us/articles/32243570935313-Minors-policy
>   - How to Make Money Online as a Teen — https://www.nerdwallet.com/article/finance/make-money-online-teenager?lv=true
>   - Standard della community: politica sui minori — https://help.fiverr.com/hc/it/articles/37333186324625-Standard-della-community-politica-sui-minori
>   - How to Make Money Online as a Teenager — https://www.nerdwallet.com/article/finance/make-money-online-teenager
>   - Normes communautaires : politique à l'égard des mineurs — https://help.fiverr.com/hc/fr/articles/32243570935313-Normes-communautaires-politique-%C3%A0-l-%C3%A9gard-des-mineurs

---

### [59] ВЫ · 2026-10-22 11:50 UTC

Продолжаем

---

### [60] CLAUDE · 2026-10-22 11:50 UTC

Продолжаю ответ про другие способы заработка с 16 лет. Это не юридическая консультация, и часть сведений из новостей и справочных сайтов, поэтому их надо проверить.

**Что разрешает закон в Казахстане (по найденным источникам)**
- С 16 лет можно самостоятельно заключать трудовой договор, до 18 лет не больше 36 часов в неделю и 7 часов в день.
- По Гражданскому кодексу сделки в 14-18 лет совершают с согласия родителей. С 16 лет можно заниматься предпринимательством, но с согласия родителей.
- Про налоги и регистрацию самозанятого для несовершеннолетних я не нашёл надёжных данных. Узнайте у юриста или на портале Enbek.

**Что разрешают платформы (источники сторонние, проверьте условия сами)**
- **Fiverr и Etsy:** от 13 до 17 лет только через аккаунт родителя или опекуна.
- **Upwork и eBay:** 18 лет, обходного пути нет.
- **Freelancer.com:** по одному обзору с 16 лет, а с 16-17 лет иногда через взрослый аккаунт. Это надо перепроверить.
- **Выплаты в Казахстан** я не проверял: какие способы вывода работают для вас, неизвестно. Это может решить всё.

**Что подходит именно вам (у вас уже есть навыки)**
1. **Услуги клиентам:** монтаж видео и Shorts, обложки, ИИ-иллюстрации, озвучка, автоматизация на Python. Даёт деньги быстрее YouTube, потому что не зависит от алгоритма. Работать через прямые контакты, письменный договор или Fiverr на аккаунте родителя.
2. **Работа по трудовому договору:** SMM-помощник, модератор, помощник по контенту. Растёт спрос на подростков в digital, но часы ограничены законом.
3. **Цифровые продукты:** шаблоны для монтажа, пакеты промптов, наборы иллюстраций. Для ИИ-картинок права и правила площадок неясны, лицензию читать обязательно.
4. **YouTube оставить параллельно** как долгий проект без монетизации. Монетизация потребует аккаунта родителя, и это уже было отложено.

**Чего избегать**
- «Заработок» с вложением денег вперёд, «сигналы», арбитраж, крипто-схемы.
- Предложения принять и переслать деньги на вашу карту («дропы»): это путь к уголовной ответственности, даже если вы не знали.
- Чужие аккаунты без согласия владельца и несколько аккаунтов для обхода лимитов.

**Моё мнение:** YouTube с нуля это долгая лотерея без гарантий, а у нас даже спрос не измерен. Услуги дают первые деньги за недели, а портфолио из фабрики (ролики, картинки, озвучка) сами станут доказательством. Но «заработок без усилий» не существует, и первые заказы будут дешёвыми.

Если хотите, составлю план на 30 дней: какие 3 услуги предлагать, портфолио, цены для старта, шаблон сообщения клиенту и список вопросов для родителя про аккаунт и выплаты.

---

### [61] ВЫ · 2026-10-22 11:51 UTC

Не хочу что-то по типу ютуба

---

### [62] CLAUDE · 2026-10-22 11:51 UTC

Понял. Оставляем формат «создаёшь один раз, аудитория растёт сама», без работы на клиентов. Главное ограничение везде одно: **платформы платят людям от 18 лет или через аккаунт родителя.** Поэтому честная стратегия такая: растить аудиторию сейчас, а деньги подключать через родителя или после 18.

**Варианты, похожие на YouTube (условия платформ я не перепроверял, проверьте)**

| Вариант | Что это | Возраст и деньги | Подходит вам |
|---|---|---|---|
| **TikTok / Shorts / Reels** | короткие ролики из той же фабрики | по одному обзору, у TikTok Creator Rewards нет подростковой схемы; рост аудитории возможен без выплат | быстрая проверка спроса, те же видео и картинки |
| **Telegram-канал** | авторский канал в нише (факты, подборки, ИИ-арт) | создать можно самому, заработок позже (реклама, платные посты) | почти ничего не стоит, но монетизацию надо изучать отдельно |
| **Twitch** | стримы и записи | по обзору, Affiliate доступен подросткам при согласии родителя | если вам интересны игры или стримы, но это формат «лицом» |
| **Roblox / игры (DevEx)** | свои игры и предметы | по обзору, подросткам доступно при согласии родителя | если хочется делать игры, это отдельный навык |
| **Цифровые продукты** (Etsy, Gumroad) | наборы иллюстраций, шаблоны, промпты | Etsy: 13-17 через аккаунт родителя | пассивнее услуг, но права на ИИ-картинки надо читать |
| **Блог / рассылка** | тексты с поиском в Google | рекламные сети обычно 18+ | медленно, но без лица и камеры |

**Что я бы выбрал**
1. **Оставить YouTube-фабрику, но добавить Shorts и TikTok из тех же роликов.** Это почти бесплатно (ролики и картинки уже есть), и вы быстрее узнаете, смотрят ли такой контент. Измерять показы и удержание, а не гадать.
2. **Родитель как владелец аккаунта AdSense, когда набежит аудитория.** Пока монетизация не включается (нужны 1000 подписчиков и часы просмотра), вопрос не срочный.
3. **Второй поток, когда фабрика заработает:** набор иллюстраций или шаблонов на Etsy через аккаунт родителя. Это тот же ИИ-арт, но продаётся как товар.

**Честно о ставках**
- Ни один из вариантов не гарантирует доход. В нише ИИ-картинок политика YouTube жёсткая, а спрос мы ещё не измерили (OpenCode ждёт квоту).
- Если вам важен быстрый результат, это услуги (монтаж, обложки). Вы их отвергли, ваше право. Тогда нужен запас терпения на месяцы.

Какой формат вам ближе: короткие видео, Telegram-канал, игры или цифровые товары? Скажите, и я проверю условия именно этой платформы для Казахстана (выплаты, возраст, налоги) по официальным страницам, не по обзорам.

---

### [63] ВЫ · 2026-10-22 11:52 UTC

Тикток Ютуб и ВК видео туда заливать видео хорошо думаешь

---

### [64] CLAUDE · 2026-10-22 11:52 UTC

Проверю условия VK Видео и TikTok для Казахстана и возраста, чтобы не гадать.

> 🔎 Веб-поиск (standard): VK Видео монетизация условия возраст 18 подписчики просмотры выплаты Казахстан

> 🔎 Веб-поиск (standard): TikTok Creator Rewards Program eligibility Kazakhstan age 18 1000 followers monetization 2026

> Найденные источники:
>   - Pull to refresh — https://habr.com/en/news/844272
>   - ppc.world — https://ppc.world/news/vk-video-rasshirit-programmu-monetizacii-s-1-sentyabrya/amp/
>   - «VK Видео» запускает новую программу монетизации для блогеров — https://mobile-review.com/all/?p=152596
>   - Новостной поток — https://fomag.ru/news-streem/vk-video-sdelaet-programmu-monetizatsii-dostupnee/
>   - «VK Видео» запускает новую программу монетизации для блогеров — https://mobile-review.com/all/news/vk-video-zapuskaet-novuyu-programmu-monetizaczii-dlya-blogerov/
>   - «VK Видео» запустила новую программу монетизации для блогеров и авторов контента — https://habr.com/ru/amp/publications/844272
>   - Порог монетизации VK Видео снизится до 1000 подписчиков — https://ppc.world/news/vk-video-rasshirit-programmu-monetizacii-s-1-sentyabrya/
>   - Pull to refresh — https://habr.com/en/articles/403021/comments
>   - Сколько VK платит за просмотры видео и как работает монетизация — https://vc.ru/social/2688037-monetizaciya-video-vkontakte

> Найденные источники:
>   - TikTok Monetization Requirements in 2026: Every Program Explained — https://postfa.st/blog/tiktok-monetization-requirements
>   - TikTok Monetization Requirements: Complete 2026 Eligibility Guide — https://ttcalculator.net/learn/tiktok-monetization-requirements/
>   - TikTok Monetization Requirements: Complete 2026 Eligibility Guide — https://ttcalculator.net/guides/tiktok-monetization-requirements/
>   - TikTok announces major expansion to creator monetization program — https://searchengineland.com/tiktok-expands-effect-creator-rewards-438353
>   - tiktok creator rewards program how organic monetization works in 2026 — https://www.makeinfluence.com/en/academy/tiktok-creator-rewards-program-how-organic-monetization-works-in-2026
>   - Insights from creatorsAbout usApply now — https://www.toptal.com/creator/post/how-to-join-the-tiktok-creator-rewards-program
>   - TikTok Creator Rewards Program: Eligibility, Pay, Setup — https://socialrevver.com/blog/tiktok-creator-rewards-program
>   - TikTok launches new Creator Rewards Program — https://www.phonearena.com/news/TikTok-launches-new-Creator-Rewards-Program_id156432
>   - TikTok Creator Fund Countries 2026 — Eligibility by Region — https://ttcalculator.net/data/reference/creator-fund-countries/
>   - Creator Fund Eligibility Requirements 2026 — https://ttcalculator.net/learn/creator-fund-eligibility-2026/

**Да, идея хорошая: один и тот же ролик на трёх площадках стоит почти ничего, а аудиторию вы узнаете быстрее.** Но деньги с этих площадок вам до 18 лет почти недоступны, это надо знать заранее.

**Что я нашёл по условиям (сторонние источники и новости, официальные страницы не открывал)**

| Площадка | Условия монетизации | Для вас |
|---|---|---|
| **TikTok** | Creator Rewards: 18+, 10 000 подписчиков, 100 000 просмотров за 30 дней, только в некоторых странах. Список стран я не видел, Казахстан в нём или нет, неизвестно | до 18 выплат нет. По одному обзору, подписчики и просмотры засчитываются сразу после 18 лет |
| **VK Видео** | с 1 сентября 2026: 1000 подписчиков, 30 000 минут просмотров за 90 дней, оригинальный контент, ролики от 3 минут | возрастное ограничение и выплаты в Казахстан не нашёл. Надо читать официальные правила |
| **YouTube** | 1000 подписчиков и 4000 часов, аккаунт родителя | уже обсуждали, пока отложено |

**Как это использовать**
- **Одна фабрика, три формата:** длинный ролик на YouTube и в VK Видео, вертикальные Shorts на YouTube, TikTok и VK Клипы. Из одних картинок и озвучки это делается автоматически (в P12 уже есть план Shorts).
- **Цель первых месяцев не деньги, а данные:** где удержание выше, где смотрят дольше, какая тема заходит. Это и есть замер спроса, которого у нас пока нет.
- **Не выкладывайте одинаковый ролик в одну и ту же минуту везде.** Для YouTube повтор своего оригинального контента допустим, но короткие версии лучше немного переделать (другой хук, другие первые 3 секунды).

**Осторожно**
1. **Метка ИИ.** Реалистичные ИИ-картинки на всех площадках надо помечать. Правила TikTok и VK по этому поводу я не читал, проверьте официальные страницы. У нас иллюстрации стилизованные и подписаны «Illustration», это помогает.
2. **Права на кадры и музыку одинаковы везде.** Что запрещено на YouTube, будет проблемой и в TikTok. Музыку не добавляем.
3. **VK:** условия выплат нерезидентам РФ я не проверял. Если выплаты идут через российские банки и системы, у вас они могут не работать. Не рассчитывайте на деньги оттуда, пока не прочитаете официальные правила.
4. **Силы.** Три площадки это три аккаунта и три источника комментариев. Начните с YouTube и TikTok, VK добавьте, когда формат заработает.
5. **Ваша безопасность:** не указывайте возраст, город и школу в профилях. Лицо в кадре не нужно, и это плюс вашего формата.

**Что делать дальше**
- Фабрика готовит ролики и Shorts. Публикуете вы сами вручную, первые 3-5 видео непубличным тестом для знакомых.
- Через 2-3 недели смотрите статистику: просмотры первых 30 секунд, средняя длительность, какая площадка дала больше. По этим данным решаем, куда вкладываться.
- Деньги подключаем через родителя или после 18, когда будет что монетизировать.

Если хотите, проверю официальные правила VK Видео по возрасту и выплатам для Казахстана и правила меток ИИ на TikTok. Скажите, и я найду страницы поддержки.

---

### [65] ВЫ · 2026-10-22 11:54 UTC

*[приложен файл: 1000266482.jpg]*

*[изображение: скриншот/фото от пользователя]*

Кстати ещё что это почему Стил и визуал ИИ генераций не нравится найди в интернете для Ютуба какой самый лучший визуальный стил

---

### [66] CLAUDE · 2026-10-22 11:55 UTC

Вижу ваши картинки: однотонный бирюзовый фон, чёрные силуэты существ с тонкими ногами, мало деталей и почти одинаковая композиция. Ваша оценка понятна. Теперь ищу, какие стили реально работают на YouTube.

> 🔎 Веб-поиск (standard): best art style for faceless YouTube explainer channels 2026 visual style that retains viewers AI images consistent style examples

> 🔎 Веб-поиск (standard): speculative evolution YouTube channel art style Kurzgesagt flat vector vs painterly concept art viewer reaction AI slop complaints stylized illustration

> Найденные источники:
>   - how to build a faceless youtube channel with ai in 2026 — https://www.atlabs.ai/blog/how-to-build-a-faceless-youtube-channel-with-ai-in-2026
>   - how to build a faceless youtube channel with ai in 2026 — https://www.atlabs.ai/es/blog/how-to-build-a-faceless-youtube-channel-with-ai-in-2026
>   - how to build a faceless youtube channel with ai in 2026 — https://www.atlabs.ai/ko/%EB%B8%94%EB%A1%9C%EA%B7%B8/how-to-build-a-faceless-youtube-channel-with-ai-in-2026
>   - ← AI Video Generation — https://www.clipspeed.ai/blog/faceless-channel-ai-video.html
>   - how to start a faceless youtube channel using ai — https://www.atlabs.ai/blog/how-to-start-a-faceless-youtube-channel-using-ai
>   - how to start a faceless youtube channel using ai — https://www.atlabs.ai/ko/%EB%B8%94%EB%A1%9C%EA%B7%B8/how-to-start-a-faceless-youtube-channel-using-ai
>   - how to choose an art style for your faceless series 2026 — https://kineclip.com/blog/how-to-choose-an-art-style-for-your-faceless-series-2026/
>   - Back to Resources — https://adwave.com/resources/explainer-video-styles
>   - Are AI-Generated Visuals Good Enough for Faceless YouTube? (Quality Guide) — https://subscribr.ai/p/ai-generated-visuals-youtube-quality
>   - Are AI-Generated Visuals Good Enough for Faceless YouTube? (Quality Guide) — https://subscribr.ai/youtube-strategy/ai-generated-visuals-youtube-quality

> Найденные источники:
>   - how does kurzgesagt animation — https://face.meei.harvard.edu/how-does-kurzgesagt-animation
>   - news ai art better artists best work twitch streamer xqc comments slop trend amid ongoing studio ghibli style row — https://soapcentral.com/pop-culture/news-ai-art-better-artists-best-work-twitch-streamer-xqc-comments-slop-trend-amid-ongoing-studio-ghibli-style-row
>   - scribe.disroot.org — https://scribe.disroot.org/post/8959786
>   - lemmy.mariusdavid.fr — https://lemmy.mariusdavid.fr/post/530139
>   - lemmy.mariusdavid.fr — https://lemmy.mariusdavid.fr/post/530139/1576072
>   - lemmy.mariusdavid.fr — https://lemmy.mariusdavid.fr/post/530139/1574878
>   - lemmy.mariusdavid.fr — https://lemmy.mariusdavid.fr/post/530139/1574929
>   - news ai art better artists best work twitch streamer xqc comments slop trend amid ongoing studio ghibli style row — https://ww4.soapcentral.com/pop-culture/news-ai-art-better-artists-best-work-twitch-streamer-xqc-comments-slop-trend-amid-ongoing-studio-ghibli-style-row
>   - lemmy.mariusdavid.fr — https://lemmy.mariusdavid.fr/post/530139/1575999
>   - How Does Kurzgesagt Animation — https://api-legacy.ingeniusprep.com/how-does-kurzgesagt-animation

**Почему вам не нравится: это не только модель, это наш стиль.** Я смотрю на ваш экран Kaggle и вижу четыре причины:
- Почти одинаковый бирюзовый фон во всех картинках, без смены цвета и настроения.
- Существа это чёрные силуэты с тонкими ногами, без текстуры и деталей, поэтому они выглядят как «палочные» фигурки.
- Много пустого места (мы сами просили «plain background» и «negative space для подписей»).
- Одна и та же композиция из кадра в кадр. Зритель на телефоне заскучает за 10 секунд.

**Что говорят источники (оговорка: почти всё это блоги производителей ИИ-инструментов, они продают свои сервисы)**
- Выбор стиля один раз и держать его на 20+ видео: это самое частое правило. Стиль заменяет лицо канала.
- Стиль должен выдерживать белые субтитры поверх картинки. Если картинка пёстрая или тусклая, читать плохо.
- Стиль выбирают по настроению темы (ужас, доверие, масштаб), а не по теме.
- Для науки и истории советуют иллюстрацию с кинематографичным видом, для объяснялок плоскую яркую 2D-графику. Это общие советы, а не измерение.
- Единого «лучшего стиля на YouTube» никто не доказал. Выстрелившие каналы имеют узнаваемый стиль, а не конкретный вид. Kurzgesagt выигрывает плоской вектор-графикой плюс сильной подачей, но копировать их стиль не стоит: он узнаваем и защищён, нужен свой.
- Реакция аудитории: в обсуждениях ИИ-картинок часто ругают расплывчатые фоны, шумные отражения и отсутствие цельности (глубина и цвет). Ссылка на исследование Nature 2024 в форуме: люди меньше любят искусство, когда узнают, что оно ИИ. Я исходное исследование не открывал.

**Три стиля, которые стоит сравнить на ваших существах**
1. **Плоская яркая вектор-иллюстрация** (своя палитра, насыщенные градиенты, толстые контуры, цветной фон). Чисто читается на телефоне, хорошо держит субтитры. Риск: может выглядеть как у всех.
2. **Рисованная «гуашь» в духе старых атласов** (текстура бумаги, тёплая палитра, детали на анатомии, подписи рисуем сами). Теплее и «ручнее», зрители лучше относятся. Риск: модели сложнее держать единство.
3. **Бумажный диорама-стиль с слоями** (передний, средний, задний план). Идеально для параллакса и движения. Риск: нужна проверка, получится ли у наших моделей.

**Критерии выбора (по ним решаете вы, смотря на телефоне)**
- Читается ли существо за 1 секунду.
- Видны ли субтитры поверх.
- Выдерживает ли серию из 80 картинок без скуки.
- Мало ли артефактов.
- Можно ли дать движение (параллакс).

**Тест, который это решит (промпт для Kilo, короткий и дешёвый)**

```text
MILESTONE S10 (Kilo) - visual style test. Follow docs/openmontage/RUN_RULES.md if present, else the usual rules (scope docs/ tools/ (not tools/prompting/) scripts/ tests/ config/; commit own paths only; no media in git; one Kaggle status call between phases; fp16 only; no bitsandbytes; max 4 attempts per blocker, change something each time). Do NOT redo completed work. Use the LOCKED image model from config/image_engine.json if it exists, else SDXL-Lightning (fast, 4 s/img).
Goal: compare 3 visual styles on the same 6 scenes (frozen alien ocean: 2 creatures, 2 habitats, 1 food-web plate, 1 wide scene), same seeds, 1024x1024, 3 images per style per scene = 54 images in ONE kernel run. Style prompts (rendered via tools/prompting, read-only; positive phrasing, no "plain background"; varied backgrounds and colour per scene; creature detail required):
 S-A flat vector illustration: saturated colour, bold contours, gradients, rich coloured background, readable shapes, no texture noise.
 S-B natural-history gouache field-guide plate: warm paper texture, visible brush strokes, detailed anatomy, muted-but-varied palette.
 S-C layered paper-cut diorama: foreground/midground/background layers, soft drop shadows, depth.
Each creature must have a written anatomy spec (counts) in the prompt. Do not copy any specific artist, channel or franchise style by name.
Build a blind pack projects/s10_blind/ (gitignored): per scene one sheet with 3 panels A/B/C in random order, plus a version of each sheet with burned-in white subtitle text at the bottom (phone-readable, max 1600 px wide) to test caption legibility; mapping.json separate; results.csv (scene, best_panel, worst_panel, readable_with_captions yes/no per panel, comment). Objective flags only (blur, hash duplicates, contrast of the caption area, colour histogram spread to detect monotone images). Do not judge beauty. Report in docs/openmontage/image_gen/STYLE_TEST_S10.md and update the STYLE_BIBLE.md ONLY after the owner fills results.csv (mark OWNER_GATED until then). Final report max 12 lines.
```

**Что делать вам**
1. Запустите S10, он займёт около 4-5 минут GPU на SDXL-Lightning.
2. Выберите стиль на листах с субтитрами через телефон, это важнее любых рекомендаций.
3. Пока идёт тест, не меняйте существующие картинки: из того, что вы показали на экране Kaggle, 45 штук, и они пригодятся как пример «чего избегать».

**Почему я не выбираю за вас:** у меня нет данных, какой стиль лучше удерживает зрителей именно в вашей нише. Любая рекомендация без теста была бы выдумкой.

---

### [67] ВЫ · 2026-10-22 11:57 UTC

Тогда давай промп для чат гпт

---

### [68] CLAUDE · 2026-10-22 11:57 UTC

Промпт для ChatGPT (включите Deep Research или Thinking с поиском). Он заставляет искать реальные каналы, а не рекламные блоги, и выдать готовые рецепты стилей под наши модели.

```text
You are a skeptical visual-direction researcher for a solo faceless YouTube operation. Today is October 22, 2026. Use web search. Cite every claim with URL + access date. Label every number MEASURED / ESTIMATE / UNKNOWN. Do not rely on AI-tool vendor blogs as evidence (they sell tools); prefer real channels, creator interviews, viewer comments, art/design sources, and platform data. Say UNKNOWN when evidence is thin.

CONTEXT
- English long-form (8-25 min) science/speculative content (alien ecosystems, "what if" scenarios, invented worlds, mythology). One person, $0 budget, AI narration.
- Visuals: ONLY AI-generated stills made with open-weights models on a free T4 GPU (SDXL-family, FLUX.2 klein 4B), plus motion (pan/zoom, parallax) and animated diagrams drawn in the editor (text and labels are never generated inside images).
- My current style (deep teal, flat dark silhouettes, empty backgrounds, same composition repeated) looks boring, flat and "AI-generic". Viewers' main complaints about AI-image channels are vague backgrounds, noisy reflections, no cohesion, repeated compositions.
- Hard limits: no real people, no brands/logos, no copying a specific artist, channel or franchise style by name (I want my OWN style), clearly stylized (not photorealistic fakes).

TASKS
1. Find 15-20 real YouTube channels (any size, English) in science explainers, speculative biology, worldbuilding, mythology, history or documentary-style narration whose visuals are illustrations or AI-assisted stills. For each: channel, link, subscribers, a video with views/date, the visual style in 1-2 plain words, whether the art is AI/human/mixed, and why it keeps attention (composition variety, colour, motion, overlays). Include at least 5 small channels (<50k subs) with a long video above 50k views in the last 12 months, if they exist. If you cannot find 5, say so.
2. Classify the styles that actually work into 6-8 families (e.g. flat vector, painterly gouache field guide, layered paper-cut/diorama, comic/graphic-novel inks, retro sci-fi poster, blueprint/technical drawing, low-poly, dark cinematic concept art, etc.). For each family give: what makes it readable on a phone, how it survives burned-in white captions, how well it hides typical AI artifacts (hands, limbs, geometry), how well it supports motion/parallax, and what the audience says about it (praise vs "AI slop" complaints, with counts or quoted examples under 15 words each).
3. Research what makes AI-image videos feel "premium" vs "slop": composition variety (wide/close/overhead), colour scripts per chapter, depth layers, lighting, grain/texture overlays, consistent recurring character design, motion variety, editing rhythm, sound design. Give evidence, not opinions.
4. For my open models (SDXL Base/Lightning/DreamShaper XL, FLUX.2 klein 4B) which style families are known to render well and which fail? Look at Hugging Face, CivitAI-style discussions, Reddit r/StableDiffusion and model cards. Note which need a LoRA.
5. For the 3 best style families for MY use, write a ready-to-use "style recipe": palette (hex codes), line/texture rules, camera vocabulary (10 shot types), lighting rules, a prompt template for SDXL (structured + negative prompt) and one for FLUX.2 klein (prose, subject first, no negative prompt), 10 example scene prompts for an alien-ocean creature video, and 5 things to NEVER put in a prompt. No artist or franchise names.
6. A cheap blind test design: 6 scenes x 3 styles, how to score (readability at phone size, caption legibility, artifact count, "would I keep watching" 1-5), and what result would make me reject a style.
7. Brief policy note (official YouTube pages, URL + date): what disclosure applies to clearly stylized AI illustrations vs realistic ones.

OUTPUT: (a) channel table; (b) style-family comparison table with scores 1-10 and stated weights + sensitivity analysis; (c) top 3 recommendation with the recipes; (d) the riskiest assumptions and the cheapest test for each; (e) contradictions between sources and what could not be verified. Be explicit if no style is clearly better and say how I should decide.
```

**Как использовать результат**
- Пришлите отчёт файлом, я сверю его с тем, что я нашёл, и с вашим тестом S10.
- Рецепты стилей из пункта 5 можно сразу дать Kilo вместо моих трёх стилей в S10, если они окажутся лучше обоснованы.
- Если ChatGPT не найдёт 5 малых каналов, не принимайте его слова на веру, это тот же пробел, что у Perplexity раньше.

---

### [69] ВЫ · 2026-10-22 12:11 UTC

*[приложен файл: 1000266487.webp]*

*[изображение: скриншот/фото от пользователя]*

А это ниша лучше чем наша?

---

### [70] CLAUDE · 2026-10-22 12:13 UTC

**Не знаю, лучше ли эта ниша нашей: по одному скриншоту это сказать нельзя. Но стиль и подача на скриншоте объясняют, почему ваши картинки кажутся скучными.**

**Что видно на скриншоте (я его только читаю, не проверяю)**
- Канал «Day One Films»: 12,8 тыс. подписчиков, 7 видео, мотивационные анимированные короткие фильмы на 2-4 минуты.
- Просмотры: 1,1 млн, 118 тыс., 46 тыс., 38 тыс., 31 тыс., 22 тыс., 19 тыс. при возрасте видео от 1 до 9 дней. Для нового канала это сильный разброс в плюс, и даже слабые видео набрали 19-46 тыс.
- Внизу подпись другого аккаунта (`@ytablueprint01`) и ссылка на skool.com в описании канала. Скорее всего, это реклама курса. Такие скриншоты показывают удачу, а не метод. Сколько каналов с этой схемой не выстрелили, мы не видим.

**Чем они отличаются от нас (и это важно)**
1. **Один узнаваемый персонаж** на каждой обложке и в каждом видео. Простая лысая фигурка с выразительным лицом: злость, усталость, страх. У нас безликие чёрные силуэты.
2. **Эмоция крупным планом** и один главный образ на кадр (штанга, рука к таблеткам, бумага с оценкой F). Фон тёмный, свет тёплый, акцент на предмете.
3. **Крупная короткая надпись на обложке** из одного-двух слов.
4. **Короткая длина** (2-4 мин), один настрой, один смысл.
5. Единый стиль на всех 7 роликах, поэтому канал узнаётся в ленте.

**Лучше ли эта ниша**
- **Плюсы:** простой повторяемый персонаж решает проблему постоянства (не надо рисовать анатомию каждого существа), эмоция держит внимание, короткий формат дешевле в производстве.
- **Минусы и риски:**
  - Ниша мотивации и самосовершенствования очень переполнена, а успех одного канала её спрос не доказывает.
  - Тема таблеток на обложке «One Last Time» намекает на зависимость или самоповреждение. Такой контент опасен и для зрителей, и для рекламы, и для вас. Я бы его не делал.
  - Темы про дофамин, дисциплину и психику это «советы по здоровью». По двум нашим отчётам YouTube не монетизирует ИИ-персон с советами по здоровью, финансам и праву. Мотивационная художественная история это не обязательно такой совет, но граница размытая.
  - Анимация здесь, по всей видимости, настоящая (движение персонажа). Наша фабрика делает картинки с наездом и параллаксом, это скромнее.
- **Не знаю:** кто делает этот канал и чем (ИИ-голос, ИИ-картинки или ручная анимация), каковы удержание и доход. Скриншот этого не показывает.

**Что я бы взял из этого без копирования**
- Персонаж-«талисман» на весь канал, но свой, а не копия лысой фигурки.
- Обложки: один образ, крупный текст из 1-2 слов, контрастный свет.
- Короткие ролики 2-5 минут как первый формат.
- Любую нашу нишу (наука, «что если», существа) можно подать через персонажа-проводника: учёный-робот, существо-рассказчик, маленький исследователь.

**Что делать**
Добавим эту нишу в замер спроса, чтобы решить цифрами, а не по одному ролику. Промпт для OpenCode (квота YouTube сбросилась):

```text
MILESTONE S11 (OpenCode). Scope ONLY youtube-niche-finder/. `git check-ignore .env` first; no secrets; no commits; do not touch docs/, tools/, .kilo/. Reuse caches; label MEASURED/ESTIMATE; n<5 = NOISE; quota failure = NOT_MEASURED. ONE test search first: on 429 STOP and write reports/S11_STATE.md. Cap 40 search.list calls.
Measure the niche "animated short films with a recurring simple character" (motivation/self-improvement/story, 2-6 min, English, last 12 months) and compare with our niches (speculative evolution, what-if science, worldbuilding) using your existing data. Seed channel: Day One Films (@dayonefilmsofficial) as ONE data point only.
1. Breakouts: videos >50k views from channels <50k subs; per video title, channel, subs, views, duration, date, link, outlier multiple vs the channel's median of its last 20 uploads (exclude the video and uploads younger than 7 days; for channels with <10 uploads say so). Replication = distinct channels with multiple >=5. Verdict STRONG/MIXED/WEAK/NOISE/NOT_MEASURED.
2. Survivorship check: for 10 channels that started with this format in the last 12 months, how many have median views below 5k (found via search), to estimate how many fail.
3. Production signals from public metadata only: AI voice/AI images likely? (ESTIMATE), video length, cadence, thumbnail pattern (descriptive words only), whether the character is a recurring design.
4. Audience reaction to AI: sample up to 100 comments on the top 5 breakouts, COUNT praise vs complaints about AI/slop (no usernames).
5. Policy and risk: from official YouTube help pages (URL + date) summarise rules on sensitive topics (self-harm, addiction, health advice, AI personas) and ad suitability; list which story themes in this niche are risky and which are safe.
6. Write reports/s11-character-niche.md with a head-to-head table against our niches, noise warnings, unknowns, and what the evidence cannot tell us. No recommendation without measured numbers. Final report max 12 lines ending with cp commands for docs/openmontage/audit/demand/.
```

**И ещё одно, спокойно:** тема «таблетки, зависимость, одиночество» в роликах для подростков, если будете их смотреть для вдохновения, может давить. Если когда-нибудь станет тяжело, поговорите с родителем или близким человеком. Для канала такие темы я брать не советую.

---

## 6.2 Полный текст файла FACTORY_100_SPEC.md (создан Claude в этом чате)

<<<НАЧАЛО FACTORY_100_SPEC.md>>>
# FACTORY 100% SPEC — what "finished" means for the OpenMontage faceless-video factory

Audience: the coding agents (Kilo, OpenCode) and the owner. Language: English for agents; owner summary in Russian right below.
Status of this file: TARGET DESIGN. Everything under "Current state" is taken from agent reports and has NOT been independently verified. Agents must re-verify from the repository before relying on it.

## 0. Кратко по-русски (для владельца)
Фабрика на 100% = одна команда превращает проверенную тему в готовое к ручной публикации видео: исследование с источниками, сценарий где каждое утверждение привязано к источнику, озвучка, картинки/кадры с подтверждёнными правами, монтаж, автоматическая проверка качества, упаковка (название, описание, обложка, кредиты), пакет для вашего просмотра, и разбор метрик YouTube после выхода. Публикацию делаете вы вручную. Человеческие решения (голос, права, слепая оценка картинок, публикация) остаются за вами, агенты их не принимают.

## 1. Mission and hard rules (never relax)
1. Faceless English long-form YouTube documentaries/explainers. Target length ladder: 3-4 min -> 8-10 -> 15-20 -> 40-50, a step up only after the owner reports YouTube Studio metrics (no invented thresholds).
2. Budget $0: free/open tools only, no paid APIs or footage, no paid fallbacks. Unknown price = forbidden until verified.
3. Zero secrets in v1 code and docs. Tokens only as Codespaces secrets; never printed, logged, committed or sent to chat. Exception: KAGGLE_API_TOKEN (name only is ever shown).
4. Rights are fail-closed: every visual asset has a record (rights_basis, source URL, credit, sha256). unknown = not usable. Third-party credit, NC/ND licenses, emblem-as-main-picture = REJECT even if the owner reviews it.
5. Every factual sentence in a script carries a claim_id that resolves in the claim ledger. Load-bearing claims need TWO independent sources; otherwise flagged SINGLE_SOURCE and blocked from publication until resolved.
6. AI-generated images: always labelled, never presented as real footage or real events, never real people/brands/logos/emblems, no text rendered inside images (labels/maps/numbers are drawn in the editor).
7. Publishing is manual in YouTube Studio only. No OAuth to YouTube, no auto-upload, no comment posting. Synthetic voice/content disclosure follows the current OFFICIAL YouTube help pages (agents cite URL + access date, paraphrase).
8. Agents report only what they observed. Never claim a test, commit, push, download, Kaggle run or subagent run that did not happen. Roles executed by one agent are labelled "inline, not independent". Quality of images/audio is judged by the OWNER, not by agents.
9. Fail-closed QC: a check that cannot run is BLOCKED or NOT_RUN, never PASS.
10. Resumable and bounded: state files, checkpoint after every phase, max retry counts, stop if free disk < 800 MB.

## 2. Roles and ownership (no two agents write the same file)
- Owner: decisions (niche, voice acceptance, rights flags, blind image scoring, emblem policy, parent/AdSense, publishing), reviews contact sheets and final video.
- Kilo (factory lane): docs/ tools/ scripts/ tests/ .kilo/ (except OpenCode-owned paths). Builds pipeline, bridge, QC, audio, render, packaging.
- OpenCode (research lane): youtube-niche-finder/ (never committed to this repo; reports copied by the owner into docs/openmontage/audit/demand/), plus tools/prompting/, scripts/score_rubric.py, niches/*/creatures/, evidence/spec_evo/ and OPENCODE_REQUESTS.md. Requests for changes elsewhere go to docs/openmontage/OPENCODE_REQUESTS.md.
- Independent reviewer: a fresh read-only session fed only docs/openmontage/REVIEW_PACK.md files (no chat history). Required before any publication.
- Git: commit own paths only (never `git add -A`), `git pull --rebase`, push non-force, never commit media/secrets. Large media lives in gitignored projects/; small artifacts (manifests, edit_decisions, subtitles, credits, qa_report) are committed under docs/openmontage/<episode>/artifacts/.

## 3. Target architecture (ten layers; each has acceptance criteria)

### L1 Niche and topic intelligence
- Niche profiles as config (YAML): allowed sources, visual-mix limits, claim rules, >=3 episode templates, excluded content.
- Demand measurement with YouTube Data API using uploads playlists (cheap) and a hard cap on search.list calls (~50/day); outlier = views / median of the channel's last 20 long uploads (excluding the video and uploads younger than 7 days); replication = >=3 distinct channels <50k subs with multiple >=5. n<5 = NOISE; never recommend without measured numbers. Quota exhausted = NOT_MEASURED, not zero.
- Topic viability gate (stage 0): enough legal visuals for the planned length AND >=3 primary sources (or, for speculative niches, >=2 sources per real-science claim) BEFORE scripting.
- Done when: `scripts/measure_niche.py` (or OpenCode equivalent) + reports reproducible from cached data; viability gate is a tested function.

### L2 Evidence and scripting
- Claim ledger per episode (markdown or YAML): claim_id, paraphrase, source URL + section, status TWO_SOURCES | SINGLE_SOURCE | OCR_UNVERIFIED | SPECULATION, KNOWN/INFERENCE/SPECULATION tag for speculative niches, contradictions field. No facts from memory; only retrieved pages.
- Script: one sentence per line with claim_ids, hook, chapters, 3 truthful titles (no clickbait lies), chapter list for the description.
- Footage-aware scripting: storyboard consults the asset inventory before narration is final; slots without valid assets are rewritten or BLOCKED.
- QC gate: claim_ids resolve against the ledger (not just present); unknown id = FAIL.
- Done when: an episode script passes `claim_ids_resolve`, every SINGLE_SOURCE sentence is listed in a "needs second source" table.

### L3 Visual sources and rights
- Source registry (docs/openmontage/footage/SOURCE_REGISTRY.md + yaml): per source rights page URL, default rights_basis, attribution, keyless search method, adapter present/missing.
- Adapters (keyless): NASA Image & Video Library, Internet Archive (curl -L; use the REAL file list from metadata, never guessed names), Wikimedia Commons, Library of Congress, NARA, DVIDS, Met Open Access, Smithsonian Open Access, Rijksmuseum, National Gallery of Art. Each adapter: transport errors surface (never "0 clips success"), rights check, asset_record with sha256, credit, URL, license text.
- asset_record fields: asset_id, kind (video|still|ai_illustration|graphic), source_url, file_url, creator/credit, license text + URL, rights_basis (explicit_license | source_policy_us_gov | ai_generated_illustration | unknown), flags (identifiable_persons, logo_visible, third_party_credit, nc_nd), resolution, duration, sha256, access date, owner_review {reviewer, date, scope}.
- Resolution rule: video below the niche minimum (default 720p) may be used only as framed inserts (integer 2x scale, centered on dark background with thin frame, source card), never stretched; no AI upscaling of footage.
- Done when: 3 adapters tested with recorded fixtures (no network in tests) and the rights classifier has regression tests for: third-party credit => REJECT, missing rights field => unknown, NC/ND => REJECT.

### L4 AI illustration engine (Kaggle GPU bridge)
- tools/kaggle_bridge: submit, poll with backoff and total timeout, fetch, verify (job_id, sha256, bytes), fail-closed; GPU T4, internet on, one model per kernel run; manifest records exact library versions (pin released diffusers/transformers/huggingface_hub; avoid git main), seeds, prompts, params.
- Rules: fp16 only on T4 (no bf16), no bitsandbytes, no CPU fallback, non-zero exit if images < prompts, full tracebacks saved, a failed attempt must change something before retrying.
- Model selection by the owner's BLIND scoring (see L9), not by agents. Candidates: SDXL Base + style LoRA, FLUX.2 klein 4B, Z-Image Turbo (Apache-2.0 each; verify each license from the official card). Others only after an official-card check (license, gating, size, dtype, released-diffusers pipeline).
- Prompt builder (tools/prompting): per-model prompt rules (SDXL structured + negative; Z-Image prose, style first, no negative prompt; klein prose, subject/anatomy first, no negative). Rules are tested and cite sources, vendor-official vs blog claims labelled.
- Style system per niche: STYLE_BIBLE.md (palette, line style, prompt template, camera vocabulary), written anatomy spec per creature (limb/eye/horn counts, 2-3 dominant features), canonical silhouette reused across shots; consistency via fixed seeds + LoRA/reference images/img2img.
- Image QC (flags only): Laplacian blur, text-like artifacts, pHash duplicates, aspect/size. Anatomy/beauty = owner.
- Done when: one command produces N labelled illustrations for an episode from creature/scene YAML specs, with verified manifest, and the owner has picked the model by blind scoring.

### L5 Voice and audio
- TTS: Kokoro-82M via kokoro-onnx (Apache-2.0 weights; residual risk: provenance of part of the training data; the owner accepted by listening, parent sign-off pending). Piper en_US-lessac voices are REFUSED in code. License gate in the TTS tool: unknown/blocked license = refuse.
- Word timestamps -> subtitles (<=2 lines, drift check). Narration >= 90% of runtime.
- finish_audio: voice-first mix, two-pass loudnorm, limiter; target configured in config (starting I=-14..-16 LUFS narration-only, TP<=-1.5 dBTP; secondary-source guesses, owner confirms); loudness verified on the FINAL MP4 after AAC encode.
- Music: none unless license evidence is stored (source URL, license text, author, date, sha256). Content ID risk is UNKNOWN.
- Done when: narration for a 10-minute script synthesizes unattended, passes QC, and the owner confirms the voice on listening.

### L6 Editing and render
- EDL (edit_decisions.json): every cut has a written rationale; static cards declared static_by_design; segment metadata for pan/zoom type, easing, source card, claim_id.
- Motion variety lint: no two identical moves in a row; shot-length variation; J/L split edits where applicable; still-only sequence <= configured limit.
- Render: ffmpeg is the base assembler (1920x1080 30fps H.264/AAC; draft mode lower res); HyperFrames/HTML-to-video only for original graphic layers after measured stability; Remotion not used. Original graphics: animated diagrams (energy flow, food web, timeline, map), key-number cards with claim_ids, chapter cards, source cards, credit roll.
- Chapter mode for long-form: <=6 min per chapter, per-chapter QC/checkpoint/resume, crossfade concat, final loudness pass, disk check before each chapter.
- Done when: `scripts/run_episode.py <episode_id>` runs all stages with checkpoint/resume/idempotency and logs wall time + disk per stage.

### L7 Quality gates (tools/qa/qc.py -> qa_report.json)
Required checks: ffprobe stream facts; full decode errors; blackdetect; freezedetect (declared static_by_design exempt with REVIEW + reason); silencedetect; ebur128 loudness + true peak; duration vs script; subtitle sync/overlap; claim_ids resolve; rights_basis known for every asset; credits.txt complete; added-value metrics (narration share, original graphics per 90 s, no unannotated archive clip > 20 s, still-only <= 15 s unless motion-lint passes); AI illustration gate (label present, share of runtime within niche limit, never as real footage); speculative-label gate for speculative niches. Statuses: PASS | REVIEW | BLOCKED | FAILED | NOT_RUN. Release verdict treats NOT_RUN/BLOCKED as not passed. Threshold changes only by owner decision, documented with reason; tools never loosen thresholds silently.

### L8 Packaging
- Titles (truthful), thumbnail candidates (1280x720, own graphics/NASA stills/illustrations, no emblems, no people, large readable text), description with chapters, credits/attribution block from rights records, synthetic-content disclosure checklist (official YouTube pages cited), Shorts plan (<=45 s, each sentence with claim_id).
- Done when: package draft is generated from the episode artifacts with zero manual copy-paste of credits.

### L9 Owner review and independent verification
- Review pack (scripts/review_pack.py): contact sheets, blind image sheets (neutral IDs, shuffled, mapping in a separate file), CSV templates, tally script that prints winners only from the OWNER's scores and flags agent-vs-owner disagreement, "INSUFFICIENT" below the minimum sample.
- Independent read-only reviewer session using only REVIEW_PACK.md files. Required before publication.
- Owner checklist per episode: people in frame? logos/emblems? third-party credit? voice OK? S-lines with SINGLE_SOURCE resolved? disclosure answered?

### L10 Operations and learning loop
- State files per milestone, resume instructions, CHANGELOG, LESSONS (observation -> evidence -> cause -> change), EVALS.md fixed tasks (qc fails a bad MP4; finish_audio hits loudness/true peak; TTS refuses Piper lessac; claim_ids fails on unknown id; third-party-credit clip classifies REJECT; rebuild script fails on hash mismatch).
- CI-style fast test script; portability: scripts/rebuild_slice_assets.sh must fail closed and print "verified N/N assets"; manifests (URLs, sha256, rights) committed; media gitignored.
- Disk discipline: delete caches/old renders you created, keep >= 800 MB free; downloads capped per milestone.
- Analytics loop (after publication): owner exports YouTube Studio CSV -> scripts import, per-chapter retention drops, CTR/AVD/first-30s tables, go/no-go summary; no OAuth.
- Codespaces hygiene: stop the codespace when idle; Codespaces usage is limited, one account per person (no extra accounts to bypass limits).

## 4. Directory layout (target)
```
docs/openmontage/
  FACTORY_100_SPEC.md (this file), RIGHTS_MODEL.md, QA_SPEC.md, EDITING_DOCTRINE.md, VOICE_DECISION.md
  niches/<niche>/{profile.yaml, STYLE_BIBLE.md, creatures/*.yaml}
  evidence/<episode>/CLAIM_LEDGER.md
  <episode>/{script.md, artifacts/{edit_decisions.json, subtitles.srt, credits.txt, rights_records.json, qa_report.json}}
  footage/SOURCE_REGISTRY.md, image_gen/{PROMPTING_FACTS.md, LICENSE_EVIDENCE.md, AI_IMAGE_POLICY.md, BAKEOFF_*.md}
  audit/demand/*  (reports copied from OpenCode by the owner)
  package/<episode>/  analytics/
tools/{kaggle_bridge,qa,audio,illustration,prompting,adapters}/  scripts/run_episode.py review_pack.py rebuild_slice_assets.sh  tests/
projects/  (gitignored media)   .kilo/{agents,skills}
```

## 5. Current state (agent-reported, UNVERIFIED by the owner/Claude; re-verify first)
Built and reportedly tested: qc.py + qa_report schema, claim_ids resolve check, finish_audio, TTS tool with license gate (Kokoro ONNX), Kaggle bridge (GPU, internet, multi-image manifest), run_episode.py (10 stages on fakes), chapter mode + LONGFORM_SPEC, SDXL-Lightning generation (10 images, owner saw many artifacts), speculative-illustration gate, prompt builder (19 tests), rubric scorer (9 tests), museum adapters/motion variety/packaging/analytics import modules (fixtures only, never run on a real episode).
Drafts (all NOT_PUBLISHABLE): CID (320x240 archive), Apollo 9 (insufficient legal footage), ISS (HD, single main clip).
Failed/blocked: G2 image bake-off (dependency and memory failures), Z-Image on Kaggle (diffusers/transformers import conflict), niche demand measurement for the speculative niches (YouTube search quota exhausted).
Open owner decisions: niche confirmation (speculative evolution / alien ecosystems proposed; art-history and ISS tracks as alternatives), blind image-model choice, voice-risk sign-off with a guardian, emblem policy, AdSense/guardian (deferred), disclosure wording.

## 6. Build order (milestones; each resumable, bounded, 12-line final report)
1. **F0 Reality audit (read-only)**: git status, tests, disk, state files, list what truly exists vs this spec; write docs/openmontage/FACTORY_GAP_AUDIT.md with PASS/FAIL/NOT_CHECKED per layer. No code changes.
2. **F1 Image engine decision**: finish the 3-model bake-off (S7), tally the owner's blind scores, record the chosen model + prompt rules.
3. **F2 Episode vertical slice, niche A**: 10-12 min speculative-evolution pilot ("How could life survive beneath a frozen alien ocean?") end to end via run_episode.py: ledger (two sources per real-science claim), ~80-100 illustrations, animated diagrams, narration, EDL with motion variety, QC all inputs, package draft. NOT_PUBLISHABLE until owner review.
4. **F3 Real-footage track (ISS/space)**: upgrade the ISS episode (more clips, cropped watermark/emblems, diagrams in timeline, credits burned in, 6-8 min).
5. **F4 Adapter hardening**: museum + NASA + Internet Archive adapters on recorded fixtures, rights classifier regressions.
6. **F5 Review and verification**: independent read-only reviewer, owner checklists, EVALS run, CI script green, portability rebuild N/N.
7. **F6 Analytics loop** after the first manual upload: CSV import, retention-by-chapter report, ladder decision proposal (owner decides).
8. **F7 Scale**: only after >=3 published episodes and measured retention: longer formats via chapter mode, series plan, Shorts pipeline.

## 7. Definition of "100% done"
- One command builds an episode from a approved topic to a publish-ready package, resumable after interruption, with unattended runtime logged.
- All hard rules in section 1 are enforced by code/tests, not by prose.
- QC gates pass on a real 8-10 minute episode with all inputs supplied (no NOT_RUN), thresholds unchanged.
- Owner-approved: voice, image model (blind scored), rights flags, disclosure answer.
- Independent read-only review returned PASS/REVIEW with evidence and every REVIEW item resolved.
- Two further episodes built with <= 1 manual fix each, proving repeatability.
- Rebuild on a clean account from the repo + manifests verifies N/N assets and re-renders the same episode.
- At least one episode manually uploaded by the owner and its Studio metrics imported (CTR, first-30 s retention, AVD, returning viewers) — this measures the BUSINESS, which the factory alone cannot prove.

## 8. Non-goals and known unknowns
- No automatic publishing, no monetization automation, no voice cloning, no music generation until a license policy exists, no photoreal fake imagery, no news, no health/finance/legal advice content, no true crime, no celebrity content.
- Unknown until measured: audience demand and competition for the chosen niche, viewer tolerance of AI stills, Content ID behavior, real T4 speed per model, YouTube's treatment of a new AI-illustrated channel, AdSense eligibility for the owner. The factory must make these cheap to test, not assume them.
- Policy and model landscapes change every few weeks: agents re-read official pages/cards before relying on any stored claim and record URL + access date.

## 9. Standing instructions for agents using this file
Read this file, then docs/openmontage/*_STATE.md and OPENCODE_REQUESTS.md. Start with F0 unless a later milestone is already DONE in the state files. Do not redo completed work. Do not edit this file; propose changes in docs/openmontage/SPEC_CHANGE_REQUESTS.md. Final report format (max 12 lines): Status, Commit, Done, Failed/NOT_CHECKED, Owner decision, Next action.

<<<КОНЕЦ FACTORY_100_SPEC.md>>>

*Конец Части 6. Собрано 22 окт 2026 из экспорта чата «AI photo generation niche».*
