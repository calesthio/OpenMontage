# FACTORY COMPLETE V12

**Научная документалистика | соло-канал | английский язык | закадровый голос | NASA/archive + AI-реконструкции**  
**Приоритет:** достоверность и художественное качество > скорость и объём.  
**Бюджет:** $0. Бесплатные загрузки разрешены.  
**Владелец — единственный, кто публикует и подтверждает решения канала.**

> V12 заменяет V11 только в явно указанных ниже местах. Все исходные ограничения S0–S8 и три закреплённых научных факта сохранены. Исполняемые правила S0–S8 находятся до разделителя «СПРАВОЧНОЕ ПРИЛОЖЕНИЕ» и занимают менее 350 строк. Приложения S9+ — спецификации, методы проверки и источники.

# ИСПОЛНЯЕМАЯ ЧАСТЬ

## S0. Нерушимые границы

1. **Бюджет $0.** Не покупать, не подписывать платные планы, не вызывать платные API. Бесплатные загрузки NASA, Archive.org, Wikimedia, моделей, `apt` и `pip` разрешены. Любая загрузка более 3 ГБ за одну сессию предварительно записывается в `manifests/download_log.jsonl` (URL, файл, ожидаемый/фактический размер, лицензия, дата, причина). Перед загрузкой — `df -h` и проверка доступного места.
2. Агент **не публикует** на YouTube, не меняет настройки канала, не принимает условия/лицензии от имени владельца. Публикацию выполняет только владелец. Агент готовит пакет и чек-лист, но не нажимает Publish и не загружает unlisted-видео от имени владельца.
3. Не удалять файлы без `deletion_manifest.json` с `path,size,reason,sha256,approved_by`. Перед удалением проверить, что файл не защищён. Защищены: `.git`, `~/.npm`, venv, веса моделей, gflow-данные, `assets/music`, утверждённые baseline manifests+hashes, `backups/`, текущие/предыдущие master-файлы и исходники пилота.
4. Никакой подгонки метрик: шум, grain, jitter, искусственные дубли кадров и незаметные изменения timestamps ради прохождения detector = FAIL.
5. `DONE` разрешён только если все REQUIRED-гейты пройдены и приложены сырые числа/логи. Иначе статус `PARTIAL`, `BLOCKED` или `NOT READY`.
6. Каждое числовое утверждение в отчёте сопровождается сырым выводом команды/JSON, версией инструмента и путём к артефакту.
7. Диск: перед тяжёлой стадией `df -h`. При свободном месте <15% — остановить новые загрузки/рендеры и очистить только безопасные кэши после проверки. При <10% — STOP с отчётом; исходники и защищённые папки не удалять.
8. REQUIRED-шаги (voice, claim ledger, rights ledger, assembly, required QC) — до 3 попыток, затем соответствующая стадия `NOT READY`; независимые безопасные стадии могут продолжаться. OPTIONAL/DEGRADABLE (SFX, необязательная музыка/превью) — до 3 попыток, затем пропустить с явной пометкой.
9. При нехватке RAM/CPU завершать только процессы, созданные текущим run и записанные в его PID/process manifest. Не завершать процессы владельца, Codespaces, gflow/browser или системы по одному лишь признаку высокой нагрузки.
10. Любые удалённые/квотируемые операции (Google Flow, hosted inference) защищены `budget_guard`: не повторять неопределённый вызов, пока не проверен remote job ID/status. Не расходовать кредит ради автоматического retry.

## S1. Спецификация видео

1. **Язык канала — английский.** Основной голос — Kokoro `af_heart`, как в пилоте. Piper — fallback только после проверки лицензии конкретного голосового checkpoint и всей известной цепочки датасета. Русская версия — отдельное решение владельца; её не запускать автоматически.
2. Пилот конвейера: 2:30–3:00. Первый публичный эпизод: 7–10 минут (цель 8–9), без ведущего, закадровый голос.
3. Цель текста: 130–150 слов на минуту **готового ролика, включая паузы**. Для 8 минут это 1 040–1 200 слов; для 9 минут — 1 170–1 350. Это производственная оценка объёма сценария, не обещание скорости произнесения. Фактическое время определяется WAV.
4. Повествование: hook 0–8 с (вопрос/парадокс, обещанный названием) → promise до 15 с → stakes до 45 с → 4–6 циклов «вопрос → доказательство → вывод → новый вопрос» → финал «что известно / предполагается / не доказано» → один короткий CTA. Хук не обещает того, чего нет в видео.
5. Визуальные события: ориентир каждые 20–40 с; смысловой блок обычно меняется каждые 60–90 с. Это редакторские ориентиры проекта, а не универсальный норматив YouTube. Движение камеры не заменяет новый смысловой визуальный факт.
6. Основные `visual_class`: `REAL_ARCHIVE`, `DIAGRAM_DATA`, `MAP`, `AI_RECONSTRUCTION`, `AI_STYLIZED`, `TEXT_CARD`. `IMAGE_TO_VIDEO` сохранить для совместимости со старыми манифестами, но в новых данных записывать как `production_method=IMAGE_TO_VIDEO` вместе с underlying `visual_class`; это способ производства, а не самостоятельный тип доказательства.
7. `visual_claim`: `REAL_FOOTAGE`, `ARCHIVE`, `DIAGRAM`, `AI_RECONSTRUCTION`, `AI_STYLIZED`. AI-кадр с `visual_claim=REAL_FOOTAGE` = FAIL.
8. Ориентиры долей (не квоты; при выходе — пересмотреть сюжет, не добирать плохие кадры): `REAL_ARCHIVE` 35–55%; `DIAGRAM_DATA+MAP` 20–35%; AI 15–30%; `IMAGE_TO_VIDEO` 0–10% как доля техники производства; `TEXT_CARD` 0–10%. Основные визуальные классы считать по длительности на экране, не по количеству файлов/сцен. `IMAGE_TO_VIDEO` считать отдельно, чтобы не складывать одну сцену дважды.
9. Каждая сцена обязана иметь: `scene_id,text,claim_ids,visual_class,visual_claim,asset_id,source_type(existing|newly_generated),motion_type,music_cue,why_this_image`. Дополнительно хранить `asset_origin`, `source_url`, `asset_sha256`, `disclosure_required`, `static_meaningful_reason` при необходимости. Кадр, не относящийся к фразе/claim, = FAIL.
10. Сцена >4 с без `motion_type` = FAIL. `motion_score>=1.0` для сцен >4 с обязателен только для откалиброванного legacy-профиля S9. Для вертикального/квадратного/иного профиля без калибровки — `NOT_CALIBRATED` и `NEEDS_REVIEW`, не фиктивный PASS. Исключения: осмысленная `TEXT_CARD`; сцена <=4 с; `static_meaningful` не более 10% сцен, с записанной причиной и review. Архивный кадр может оставаться статичным, если он является доказательством/историческим свидетельством; не анимировать ради цифры.
11. Запрещено: noise/grain/jitter ради метрики; одинаковый zoompan на каждом кадре; RIFE как «фикс» статики; повтор одного и того же кадра ради detector.
12. **Звук:** Kokoro + установленный `espeak-ng`; Piper fallback после проверки voice license. `narration_master` строится из фактических длительностей и sample counts WAV-блоков. ASR используется для проверки текста и word timestamps, но не как источник длительности аудиофайла. Цель мастера `-16 LUFS-I` (допуск ±1.5 LU), true peak `<= -1.5 dBTP`, 1–2 аудиоканала.
13. Под речью музыка: стартовая проектная настройка `L_music,ST - L_voice,ST = -14 LU ±3 LU`, измерять отдельные стемы на одном и том же окне; это настройка для теста и прослушивания владельцем, не стандарт YouTube. Во время паузы соотношение «от голоса» не определено — задавать отдельную музыкальную автоматизацию/огибающую и утверждать на слух, не вычислять бессмысленный ratio. Музыкальные фазы: intro, question, tension, reveal, resolution.
14. Паузы >1.5 с допускаются только с `intentional_pause=true` и объяснённой функцией. Непредусмотренная тишина >1.5 с = FAIL.
15. Субтитры YouTube — `.srt`, синхронизированные и проверенные по речи. Реплики субтитров соответствуют произнесённому тексту. Научные подписи/термины/цифры могут быть короче, но не должны противоречить голосу и должны иметь связанные `claim_id`. На экране: не более 2 строк, высота текста не выше 8% высоты кадра, нижний край не ближе 10% к низу, боковые поля 5%.
16. Экранная подпись `AI-generated visualization` — редакторская подсказка зрителю при первом релевантном появлении реалистичной реконструкции; не заменяет платформенную настройку `AI use`. Нельзя откладывать обязательное YouTube disclosure ради hook. Короткая бренд-заставка 10–15 с из V11 — **не обязательный технический gate**; применять только если она не вытесняет promise/stakes и утверждена владельцем. Это редакторское решение (МНЕНИЕ), а не правило YouTube.
17. Достоверность: каждый фактический **clause**, не только каждое предложение, должен иметь `claim_id`. Claim fields: `claim_id,text,status(MEASURED|ESTIMATE|UNKNOWN),source_type(PRIMARY|SECONDARY|MODEL),source_url,doi,authors,year,quote_or_paraphrase,uncertainty,conflicting_sources,accessed_at`.
18. `MEASURED` означает прямое инструментальное наблюдение/измерение/спектральный сигнал/подсчёт, указанное в первичном источнике. `ESTIMATE` означает расчёт, модельный вывод, косвенную интерпретацию или величину с допущениями; указывать модель, допущения и интервал неопределённости. Первичная статья может подтверждать `ESTIMATE`. `UNKNOWN` означает, что вопрос по доступным данным не установлен. Не превращать `UNKNOWN` в факт.
19. Примеры классификации: спектральный сигнал H₂ в данных Cassini — MEASURED; его вероятное образование в гидротермальных реакциях — ESTIMATE/интерпретация. Спектральные признаки фосфатов в ледяных зёрнах — MEASURED; концентрация фосфора океана «не менее ~100× земной» — вывод авторов/ESTIMATE. Толщина проводящего ледяного слоя Европы `~29±10 км` при модели чистого водяного льда — ESTIMATE, не точная общая толщина оболочки.
20. Запрещено утверждать «нашли жизнь», точную глубину океана без модели/источника, «NASA подтвердила» без URL, выдавать AI-кадр за доказательство. Допустимы точные формулировки: «условия, совместимые с жизнью», «ингредиенты/органические соединения обнаружены, жизнь не обнаружена», «оценка в рамках модели…».
21. Научная база, переданная владельцем и сохранённая без изменения сути:
   - **Европа:** Levin et al., *Nature Astronomy* 10, 84–91 (2026), опубликовано 17.12.2025, DOI `10.1038/s41550-025-02718-0`. Оценка около 29 км (±10 км) для холодного жёсткого проводящего слоя чистого водяного льда в районе пролёта Juno 29.09.2022; соль могла бы уменьшить эту оценку примерно на 5 км; более тёплый конвективный слой означает, что вся ледяная оболочка может быть толще. Общая толщина оболочки точно не известна. Источники: https://doi.org/10.1038/s41550-025-02718-0 ; https://science.nasa.gov/jupiter/juno/.
   - **Europa Clipper:** запуск 14.10.2024; Mars gravity assist 01.03.2025; Earth gravity assist 03.12.2026; Jupiter orbit insertion 11.04.2030; первый пролёт Европы 07.03.2031; 49 пролётов Европы. Аппарат выходит на орбиту Юпитера, не Европы; посадка на Европу не планируется. Для точного первого пролёта: EPSC-DPS2025 abstract https://meetingorganizer.copernicus.org/EPSC-DPS2025/EPSC-DPS2025-1031.html и JPL mission trajectory paper https://www.issfd.org/ISSFD_2024/ISSFD2024_19-3.pdf; NASA timeline подтверждает месяц/год и ключевые даты https://science.nasa.gov/mission/europa-clipper/mission-timeline/.
   - **Энцелад:** Postberg et al., *Nature* 618, 489–493 (2023), DOI `10.1038/s41586-023-05987-9`: натрий-фосфаты выявлены в ледяных зёрнах Cassini; авторы оценивают содержание фосфора в океане как минимум примерно в 100 раз выше земного океана. Это спектральные данные зёрен и геохимический вывод, не прямая проба жидкой воды; доказательств жизни нет. Источник: https://doi.org/10.1038/s41586-023-05987-9.
22. Дополнительные факты, ранее помеченные CHECK, закрыты как подтверждённые с корректной оговоркой:
   - Cassini обнаружил молекулярный водород H₂ в шлейфе Энцелада; гидротермальное происхождение — наиболее вероятное объяснение авторов, а не прямое наблюдение процесса. Waite et al., *Science* 356 (2017), DOI `10.1126/science.aai8703`: https://doi.org/10.1126/science.aai8703.
   - В свежих ледяных зёрнах Энцелада, непосредственно собранных в пролёте Cassini E5, выявлены органические фрагменты/моieties; некоторые N- и O-содержащие идентификации обозначены авторами как tentative. Khawaja et al., *Nature Astronomy* 9, 1662–1671 (2025), DOI `10.1038/s41550-025-02655-y`: https://doi.org/10.1038/s41550-025-02655-y.
   - Оценка «около двух объёмов океанов Земли» относится к океану **Европы**, не Энцелада; NASA JPL описывает океан Европы как содержащий более чем вдвое больше воды, чем все океаны Земли вместе взятые: https://www.jpl.nasa.gov/press-kits/europa-clipper/quick-facts/.
23. Не возвращать опровергнутые формулировки из V11: «облёт Земли 02.03.2026» (Mars flyby был 01.03.2025); «исследование Juno о льде опубликовано в Science» (статья опубликована в *Nature Astronomy*).

## S2. YouTube, права, деньги

1. **AI use:** YouTube требует выбрать Yes при загрузке, если AI-generated/meaningfully altered content выглядит реалистично (реалистичный человек/место/событие, которого не было, либо существенное изменение реального события). AI для идей, сценария, субтитров, заголовков, инфографики и не вводящие в заблуждение косметические правки обычно не требуют disclosure. Для реалистичных `AI_RECONSTRUCTION` V12 сохраняет консервативное правило: Yes. Для очевидной стилизации/полностью анимированного условного материала — по официальным примерам disclosure может не требоваться; владелец принимает финальное решение при загрузке. Источник: https://support.google.com/youtube/answer/14328491.
2. Платформенное disclosure и экранная подпись — разные вещи. YouTube может автоматически добавлять AI-label по использованию собственных GenAI-инструментов, сигналам C2PA или другим внутренним сигналам; это не отменяет обязанность автора указывать `AI use` при необходимости. Источник/объявление: https://support.google.com/youtube/blog/424874071/updates-to-ai-content-disclosure-and-labels.
3. `Inauthentic content`: YouTube 15.07.2025 уточнил, что repetitious content включает repetitive/mass-produced content, и переименовал политику в `inauthentic content`; reused-content policy отдельно и без изменения. Риск — массовость/повторяемость/шаблонное производство без оригинальной ценности, а не само использование AI. Оригинальный сценарий, доказательства, разнообразные структуры и редактура снижают риск, но не гарантируют YPP. Источник: https://support.google.com/youtube/answer/1311392.
4. **YPP с 01.02.2027 для новых заявителей на ads/Premium revenue:** 1 000 подписчиков и один из двух порогов: 8 000 qualified public watch hours за последние 365 дней **или** 20 млн qualified Shorts views за последние 90 дней. Уже состоящие в YPP не исключаются из-за нового порога. Обновлённые условия соответствующих модулей нужно принять в YouTube Studio до 31.01.2027, чтобы продолжить полную монетизацию по ним. Источник: https://support.google.com/youtube/answer/12843009.
5. Не смешивать другие уровни: ранний доступ к fan funding / Creator Partnerships / Shopping сохраняет 500 подписчиков + 3 000 часов либо 3 млн qualified Shorts views; ежемесячный доход из Shorts Creator Pool с 01.02.2027 отдельно требует 10 млн Shorts views за 90 дней, и падение ниже этого не удаляет канал из YPP и не отменяет long-form доходы. В YPP с 01.02.2027 новый activity criterion: минимум один из `1,000 qualified hours / 365d`, `1M Shorts views / 90d`, `2 long-form uploads / 90d` или `5 Shorts uploads / 90d`; restore window — 90 дней по одному из первых двух activity criteria. Источник: та же официальная справка выше.
6. Для входа в YPP нужны: страна/регион, где доступен YPP; отсутствие активных **Community Guidelines strikes**; 2-Step Verification; доступ к advanced features; один активный AdSense for YouTube account. Не называть copyright claims/strikes тем же самым, что Community Guidelines strikes. Страна из списка не доказывает статус конкретного канала — владелец проверяет в Studio. Справки: https://support.google.com/youtube/answer/72851 ; https://support.google.com/youtube/answer/7101720 ; https://support.google.com/youtube/answer/2802032.
7. До 01.02.2027 применяются действующие прежние ads thresholds: 1 000 подписчиков + 4 000 valid public watch hours / 365d либо 10 млн valid public Shorts views / 90d. При изменении правил владелец сверяет Studio и официальную справку; агент не меняет цель автоматически.
8. **NASA:** большинство материалов NASA не защищены авторским правом в США, но сторонние материалы/авторы могут иметь отдельные ограничения; логотип NASA не считать public domain/свободным товарным знаком; не подразумевать endorsement; узнаваемые лица/личные права проверять отдельно. Источник: https://www.nasa.gov/nasa-brand-center/images-and-media/.
9. **Archive.org/Wikimedia:** права проверять на уровне каждого файла. Сам факт размещения в архиве не является лицензией. Музыка Public Domain не гарантирует отсутствие Content ID claim; при неясном статусе трек заменить.
10. `rights_ledger` обязателен для каждого опубликованного актива: `asset_id,source,url,license,license_url,credit_line,has_identifiable_person,has_logo,third_party_copyright,embedded_music,commercial_use_allowed,status(CLEAR|NEEDS_REVIEW|BLOCKED),evidence_path,checked_at`. `CLEAR` нельзя ставить без сохранённого свидетельства лицензии/права использования.
11. AI asset хранит `prompt,seed,model,model_version,date,terms_url,remote_job_id,original_download_sha256`. Если seed или job ID провайдер не показывает — записать `null` и `not_exposed`/причину; не придумывать значения. В описании видео — источники со ссылками и `Not affiliated with NASA`.

## S3. Конвейер и проверяемые гейты G0–G9

Все гейты запускаются из `scripts/release_checklist.py`. Каждый формирует `gate.json` с `status,required,checks,raw_outputs,artifacts,sha256,tool_versions,started_at,completed_at`. Проверять реальные файлы и содержимое, а не только JSON-флаг от предыдущей стадии.

- **G0 BRIEF:** `brief.md` + title/promise + 3 разных hooks. `test -s`; JSON/schema validation. Проверить, что каждый hook действительно отличается по формулировке и драматургической точке, а обещание подтверждается содержанием. Машинная similarity может пометить REVIEW, но не выдаёт художественный PASS сама.
- **G1 RESEARCH:** `claim_ledger.json`. Нет factual clause без валидного `claim_id`; нет `UNKNOWN` в качестве утверждения. DOI existence проверять через Crossref, например: `curl -fsSL "https://api.crossref.org/works/$DOI" | jq -e '.message.title[0] != null'`. Проверять title/authors/year/DOI совпадение и доступность URL. URL/DOI existence не доказывает, что источник поддерживает claim: quote/page/figure/table и человеческая сверка обязательны.
- **G2 SCRIPT:** `script.md/json`, draft `.srt`; word count по S1; каждый факт clause с claim_id; hook честный; все narrative loops закрыты. Проверить, что SRT и narration соответствуют речи; не путать screen labels с дословными subtitle lines.
- **G3 STORYBOARD:** `storyboard.json`; schema validation; поля S1 заполнены; visual-class shares посчитаны по длительности; все asset/claim refs существуют. Не требовать отсутствия `NEEDS_REVIEW` в rights ledger до G4: G3 может только проверить, что rights check запланирован, G4 обязан закрыть права. Нет сцены >4 с без `motion_type`; `why_this_image` заполнено.
- **G4 SOURCING:** assets + `rights_ledger` + `asset_manifest`. Каждый asset имеет SHA-256, bytes>0, `file`-type, `source_url`, `credit_line`, rights status; AI — prompt/model/date/terms/job ID если доступен. Проверка: `find assets -type f -size 0c -print`; `file ...`; `sha256sum -c assets.sha256`; для видео/аудио полный decode `ffmpeg -v error -i "$f" -f null -`. Изображения дополнительно проверять Pillow `Image.verify()` и dimensions. Собирать contact sheets. Exact duplicates — SHA/framemd5; near-duplicates — perceptual hash/visual review; повторы не FAIL автоматически, если обоснованы. Новый asset считается `newly_generated` только при подтверждённом source job/output; старый asset всегда `existing`.
- **G5 VOICE:** TTS blocks, WAV, ASR transcript для каждого блока, narration master; `WER <10%` по нормализованному сравнению с approved script и critical-term omissions = 0. Критические термины прослушивает владелец. Длительность WAV = `samples / sample_rate` из ffprobe; ASR duration не сравнивать с WAV как равные длительности с точностью 200 мс (удалённый/ошибочный тест V11). Word timestamps должны лежать внутри длительности соответствующего WAV и быть монотонными/не выходить за границы. Сохранять ASR model ID/revision и JSON raw output.
- **G6 ASSEMBLY (REQUIRED):** `ffprobe` + полный decode финального MP4; A/V end-duration difference <=0.1 с; проверить start_time/PTS streams и локальное совпадение визуального события/слова на выборочных границах, а не только общую длительность. Не требовать `number_of_segments == number_of_scenes`: каждая сцена должна ссылаться хотя бы на один render item, а каждый render item — на валидный scene_id, transition или asset_id; каждый narration block покрыт timeline. Субтитры сопоставить с word timestamps/речью, допустимая погрешность границ <=0.1 с как проектный gate. Проверить motion по S9, freezedetect — только вторичная проверка; нет непредусмотренных black frames; no unlabeled silence >1.5s; true peak <=-1.5 dBTP; loudness -16 LUFS-I ±1.5; 1–2 channels; текст в safe zones. Сырые отчёты — обязательны.
- **G7 OWNER REVIEW:** машинные проверки пройдены, но статус остаётся `NEEDS_OWNER`, пока владелец реально не посмотрит ролик целиком или минимум 10 минут и не подтвердит hook, факты, визуал, звук и subtitles. Агент не вправе сам записать просмотр/одобрение. Если требуется машинная проверка подписи — owner-signed approval file проверяется pinned public key (`gpg --verify`); без настроенного ключа ручное подтверждение владельца остаётся отдельным невыполненным gate.
- **G8 PUBLISH-PREP:** title, description, sources, chapters, tags, 2–3 thumbnails, SRT, напоминания `AI use` и `Not affiliated with NASA`. Проверить `test -s` для обязательных файлов, `ffprobe` финала, размеры/формат/читаемость thumbnails на уменьшенных копиях. A/B test owner-only; загрузка/публикация только владельцем. Unlisted не гарантирует отсутствие будущего Content ID.
- **G9 LEARN:** анализировать только CSV/экспорт из YouTube Studio, переданный владельцем: CTR, AVD/APV, удержание 0–30 с, retention graph, largest drop timestamp, traffic sources. Записать период, видео ID и SHA экспорта. Если реального экспорта нет — `NOT_AVAILABLE`, не выдумывать значения. Следующий эпизод меняется по наблюдениям, не по одному CTR.

## S4. Код и восстановление

1. Сохранить существующие модули и тесты; не переписывать рабочее без доказанной причины: `research_ledger,script_tools,storyboard,sourcing,image_gen,tts_engine,asr_check,audio_master,motion_director,color_match,subtitles,assemble,qc,rights_ledger,budget_guard,state_store,review_package,publish_prep,recovery`.
2. Сохранить исходный контракт `status(success|fallback_used|failed),failure_class(REQUIRED|OPTIONAL|DEGRADABLE|MANUAL_REVIEW),raw_data,artifacts,hash`; дополнить runtime statuses `PASSED,DEGRADED,FAILED,BLOCKED,NEEDS_OWNER,NEEDS_REVIEW,SKIPPED,NOT_APPLICABLE,PARTIAL`. Не превращать FAILED в PASS.
3. State machine + `state.sqlite` — источник текущего состояния; `BUILD_LOG` — человекочитаемая сводка; manifests — описание артефактов; `events.jsonl` — append-only событие. State transitions фиксировать атомарно.
4. Для каждой стадии строить fingerprint из input SHA-256 + config/code/model version. Если fingerprint совпал и output проходит checksum + format + QC — не повторять. Запись результата: temp path → QC → atomic rename → state commit.
5. Git содержит код, конфиги, schemas, docs и небольшие test fixtures; большие media не добавлять в обычную Git-историю. Никаких force-push/переписывания истории.
6. RESUME: после обрыва читать `state.sqlite`, последние BUILD_LOG/events, проверять SHA существующих артефактов. Незавершённое — PARTIAL; валидное — переиспользовать; битое — quarantine/NOT READY. Не удалять автоматически.

## S5. Хранилище и ресурсные лимиты

1. Codespaces около 32 GB диска — это предел окружения, не объём, который можно целиком занять. Перед стадией проверять `df -h`, `du -xhd1`, RAM и ожидаемый размер входов/outputs; оставлять рабочий запас, выполнять S0 thresholds.
2. Тяжёлые ассеты, WAV и рендеры — вне Git; в Git только манифесты, hashes, URLs, код и configs. Копия каждого утверждённого asset + SHA-256 должна существовать вне `/tmp`/ephemeral workspace.
3. Hugging Face Free user/org: до 100 GB private storage по текущей официальной странице; public storage best-effort. Один файл: hard limit 500 GB, рекомендуемый размер <200 GB; для моделей/датасетов нет отдельного per-repository total-size cap, но всё учитывается в общей квоте. Перед загрузкой проверять страницу: https://huggingface.co/docs/hub/storage-limits.
4. Cloudflare R2 Standard free tier: 10 GB-month storage, 1M Class A operations, 10M Class B operations в месяц; egress free. Infrequent Access не входит в free tier. Превышение оплачивается; для $0 проекта запрещено создавать billable overage. Официально: https://developers.cloudflare.com/r2/pricing/.
5. Не загружать Wan2.2 крупные веса в Codespaces: TI2V-5B repo ~34.2 GB и I2V-A14B ~126 GB — превышают/съедают диск ещё до временных кадров. Только Kaggle/другое бесплатное GPU окружение при наличии квоты, без гарантии доступности. Предел V11 experiment ≤2 GPU-hours сохранить.
6. Токены — только env/secrets, не Git/logs. Backup считается успешным только после `sha256sum -c` и тестового восстановления в отдельную директорию. Внешнее хранилище должно оставаться в бесплатной квоте; никаких платных overages.

## S6. Правила агента

1. Не подгонять метрики.
2. Любое число в отчёте сопровождается сырым выводом.
3. Перед удалением понять назначение; подготовить `deletion_manifest`.
4. `$0` не запрещает бесплатные загрузки в рамках S0.
5. Субтитры соответствуют речи; подписи не противоречат фактам.
6. Не ставить DONE при провале REQUIRED gate.
7. Каждый asset имеет проверяемую копию и hash.
8. При нехватке ресурсов завершать только процессы текущего pipeline run; затем повторять с ограниченным retry.
9. Один производственный проход = один отчёт с таблицей до/после.
10. Термин TTS = независимый ASR + человеческое прослушивание владельцем.
11. Сбой gate не обходить: записать причину и предложить владельцу изменение порога, не менять его самому.
12. Не принимать/опровергать научный факт без первоисточника с URL; если источник не найден, сохранить user-supplied VERIFIED статус, пометив только факт независимой проверки как NOT_RECHECKED.
13. Не выдавать файл за созданный заново: сохранять `source_type=existing|newly_generated`; дополнительно `asset_origin=existing|downloaded_archive|newly_generated|procedural`.

## S7. Дорожная карта

- **Фаза 0 — стабилизация:** G6 QC, возврат исходников пилота, storage/backup, Kokoro + espeak-ng, manifest эталонов, repair S9 detector.
- **Фаза 1 — пилот V12:** hook, voice/subtitles, кадры строго по тексту, движение, review_package, просмотр владельцем, `PUBLISH_DRY_RUN` (без загрузки агентом).
- **Фаза 2 — первый публичный эпизод:** один вопрос: `Could Europa's hidden ocean support life, and what will Europa Clipper measure?`; 7–10 минут; 3 заголовка и 2 превью на выбор владельца; корректные подписи Earth gravity assist 03.12.2026 и first Europa flyby 07.03.2031.
- **Фаза 3:** ориентир 1 эпизод в 1–2 недели только при сохранении качества; запуск G9.
- **Фаза 4:** Shorts из лучших 20–40 с; не рассчитывать на них как обязательный путь к YPP.

## S8. Эксперименты и первая сессия

Эксперименты выполняются по одному, с записанным критерием приёмки и сохранением baseline: E1 ASR/espeak; E2 strict gates; E3 Wan2.2 image-to-video в Kaggle ≤2 GPU-hours (при наличии бесплатной квоты, только если не искажает научные детали); E4 read-only repo review; E5 TTS A/B только если голос плоский; E6 DepthFlow только после проверки LICENSE/AGPL условий. Не менять модель, голос и стиль без владельца.

Первая сессия: T1 `df -h`, процессы текущего pipeline, gflow auth, `pytest tests/lib -q`; T2 вернуть исходники пилота, manifests, hashes и rights ledger; T3 G6 QC на `final.mp4` и `final_v8_experiment.mp4` (сохранить заявленное ожидание V11: оба должны быть проверены и ожидаемо fail по baseline S9; не подгонять результат); T4 espeak-ng + ASR по voice blocks; T5 storage/backup; T6 собрать `final_v11` только после required gates; T7 review_package + `END_OF_DAY_SUMMARY_V12.md`. Если исходники/файлы отсутствуют, остановиться с `NOT_AVAILABLE`, не создавать фиктивные placeholders.

---

# СПРАВОЧНОЕ ПРИЛОЖЕНИЕ (не входит в лимит исполняемых строк)

## S9. Motion score: ограничения, независимая проверка и калибровка

### S9.1 Сохранить legacy-метрику, уточнить область действия

Исходный метод V11 (не выбрасывать калибровку): 2 fps, 320×180, grayscale, блоки 8×6 пикселей (40×30 = 1 200 block means), средняя абсолютная разность между кадрами, отстоящими на 1 секунду (`f[2:] - f[:-2]`). Старые эталоны: static 0.002; static + strong noise 0.38; slow zoom 1.00→1.08 over6s 2.9; lateral drift 7.7; порог 1.0. Legacy `final.mp4` reported 60% seconds below0.35; `final_v8_experiment` 94%. Считать эти числа исходной калибровкой только для 16:9 landscape, этого preprocessing и этого класса материала; не переносить на другие aspect ratios без новой калибровки.

### S9.2 Дефекты реализации в V11

1. Код не исключает cut windows: есть только комментарий `# cut-окна исключить сверху`, но detection/mask нет. Значит заявленное поведение отсутствует в референсной реализации.
2. `scale=320:180` принудительно деформирует vertical/square кадры. Для portrait использовать профиль 180×320 с сеткой 30×40 блоков; для square/других aspect ratios — отдельный профиль с сохранением DAR и корректной valid-pixel mask. Не использовать legacy threshold 1.0 до калибровки профиля.
3. Для очень короткого сегмента недостаточно пар с шагом1s; `mean()` по пустому массиву даёт NaN. Проверять `ffmpeg returncode`, число полных кадров и `valid_window_count`. Если сцена <=4s — возвращать `NOT_APPLICABLE_SHORT` по S1, не 0/NaN. Если данных недостаточно по иной причине — `INSUFFICIENT_DATA`, не PASS.
4. Fade/dissolve — не обычный hard cut; изменение яркости может повысить pixel difference, хотя план остаётся практически неподвижным. Запланированные transition intervals брать из timeline manifest; незапланированные — отдельно flagged для review, а не молча смешивать с motion score.
5. Намеренно статичный архив, карта, таблица или `TEXT_CARD` могут быть правильным решением. Статика — не автоматический FAIL, если сцена размечена `static_meaningful`, объяснена и утверждена в рамках <=10% сцен. Нельзя «оживлять» доказательство ради счётчика.
6. Текст/субтитры/оверлеи могут создавать pixel change без движения изображения. Маскировать известные UI/text overlays для базового visual-motion analysis или отдельно сохранять `overlay_motion_score`.
7. Зум менее4% не покрыт старой эталонной парой (проверялся зум8%). Не назначать ему произвольный numeric threshold.

### S9.3 Требуемая реализация

- `motion_score` остаётся pixel-difference indicator для обратной совместимости. Сохранять score каждого 1s окна, среднее по сцене, P10/median/P90, долю окон <0.35, `valid_window_count`, `coverage_ratio`, число исключённых transition/cut windows.
- Planned cuts/transitions исключать из score по scene/timeline manifest. Unplanned hard cuts искать `scdet` FFmpeg и подтверждать контактным листом/логом. Пример проверки:

```bash
ffmpeg -hide_banner -i input.mp4 \
  -vf "scdet=threshold=10,metadata=print:file=scdet_metadata.txt" \
  -an -f null -
```

`scdet` записывает `lavfi.scd.mafd`, `lavfi.scd.score`, `lavfi.scd.time`; документация указывает стандартный threshold10 и типичный диапазон8–14. Не считать 10 магической истиной: сохранять сырой список кандидатов и проверять реальные false positives/negatives. Источник: https://ffmpeg.org/ffmpeg-filters.html#scdet.

- Добавить независимый показатель **camera/local optical flow**: Shi–Tomasi features → LK optical flow → `estimateAffinePartial2D` с RANSAC для глобального сдвига/масштаба/поворота; dense optical flow residual — для локального движения (дым, струи, частицы, водные потоки). Записывать `global_scale_delta`, `translation_px`, `rotation_deg`, `inlier_fraction`, `local_flow_median`, `local_flow_p90`, `valid_tracks`. Это отчётные величины; threshold не устанавливать, пока не откалиброван. Согласованное глобальное движение отличает slow pan/zoom от flicker; локальный residual помогает найти движение внутри кадра.

### S9.3A Legacy reference implementation from V11 (сохранена без изменения)

```python
import subprocess, numpy as np
def motion(path, ss=0, t=None, w=320, h=180):
    c=["ffmpeg","-v","error","-ss",str(ss),"-i",path]+(["-t",str(t)] if t else [])
    c += ["-an","-vf",f"fps=2,scale={w}:{h},format=gray","-f","rawvideo","-"]
    raw=subprocess.run(c,capture_output=True).stdout
    n=len(raw)//(w*h)
    f=np.frombuffer(raw[:n*w*h],np.uint8).reshape(n,h,w).astype(np.float32)
    f=f.reshape(n,h//6,6,w//8,8).mean(axis=(2,4))
    return np.abs(f[2:]-f[:-2]).mean(axis=(1,2))  # окна 1 с; cut mask должен быть применён отдельно
```

Эта legacy-функция только вычисляет вектор разностей. Она не реализует cut exclusion, не проверяет ffmpeg return code, не проверяет пустой результат и предполагает размеры, кратные 8×6. Для воспроизведения исторического baseline оставить её неизменной; для production использовать расширенный wrapper с проверками из S9.2–S9.4.

- Два показателя не сливать в одно число без калибровки. Pixel difference чувствителен к яркости/fade; optical flow ошибается на текстурах без деталей, шуме, движущемся фоне/параллаксе и перекрытиях. Они дополняют, а не доказывают художественную ценность.

### S9.4 Профили и калибровка

1. Создать labeled calibration suite с представителями: неподвижный NASA-кадр; намеренно статичный документ/текст; 1–4% zoom; 8% zoom; lateral pan; parallax; локальные частицы/шлейф; fade; dissolve; cut; noise/codec artifacts; низкотекстурный космос; vertical; square; сцены <2s и 2–4s.
2. Для каждого эталона вручную задать label: `INTENTIONAL_STATIC`, `GLOBAL_CAMERA_MOTION`, `LOCAL_MOTION`, `TRANSITION`, `CUT`, `FLICKER/NOISE`, `INSUFFICIENT_DURATION` и обосновать expected behavior.
3. Разделить calibration и holdout наборы. Подобрать threshold на calibration, затем отчитать confusion matrix, false accept, false reject, precision/recall на holdout. Владелец заранее выбирает допустимый риск false PASS. Не фиксировать произвольный минимальный размер набора или пороги без данных.
4. Для vertical/square/нового размера держать `NOT_CALIBRATED`, пока не пройдёт собственная калибровка. Не сравнивать численно разные profiles как будто они идентичны.
5. Cut/fade/dissolve intervals брать из timeline; незапланированные переходы — `NEEDS_REVIEW`, не исключать автоматически, иначе агент сможет спрятать дефект в «переход».

## S10. Лицензии и совместимость — проверять отдельно code, checkpoint, voice, dataset

| Компонент | Что подтверждено первичным источником | Production-решение |
|---|---|---|
| Kokoro | Код `hexgrad/kokoro` — Apache-2.0: https://github.com/hexgrad/kokoro/blob/main/LICENSE. Используемая модель `hexgrad/Kokoro-82M` имеет отдельную model card; зафиксировать её revision: https://huggingface.co/hexgrad/Kokoro-82M. | Оставить основной TTS; в lockfile хранить repo commit/model revision и license snapshot. `af_heart` — идентификатор встроенного голоса, не отдельный voice repo с отдельной карточкой; не распространять утверждения на все варианты Kokoro.
| faster-whisper | Код — MIT: https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE. Проверенная модель `Systran/faster-whisper-large-v3` имеет отдельную model card/license: https://huggingface.co/Systran/faster-whisper-large-v3. | Разрешить при фиксации точного repo ID и revision модели. MIT кода не заменяет проверку checkpoint.
| Piper runtime | Официальный активный репозиторий `OHF-Voice/piper1-gpl`; `setup.py` объявляет `GPL-3.0-or-later`: https://github.com/OHF-Voice/piper1-gpl/blob/main/setup.py. Документация говорит проверять `MODEL_CARD` каждого голоса: https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/VOICES.md. | Runtime может использоваться локально, но учитывать GPL при распространении модифицированного приложения. Voice weights проверять отдельно.
| Piper voices | Коллекция HF показывает общую card badge MIT, но официальная документация прямо говорит, что voice MODEL_CARD содержит собственную лицензию и некоторые голоса могут быть ограничены. Примеры русских голосов: https://huggingface.co/rhasspy/piper-voices/tree/main/ru/ru_RU ; пример `dmitri medium`: https://huggingface.co/rhasspy/piper-voices/blob/main/ru/ru_RU/dmitri/medium/MODEL_CARD ; English `lessac medium`: https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/lessac/medium/MODEL_CARD. | В V11 точный fallback voice ID не выбран, поэтому лицензия именно будущего fallback не установлена. Дмитрий указан как finetuned from Lessac; Lessac model card ссылается на Blizzard 2013 dataset licence. Для коммерческого использования не считать CC0 датасет fine-tune автоматическим разрешением на исходный голос; полная цепочка прав не подтверждена. Голос не допускать в коммерческий fallback, пока owner не выберет конкретный ID и не сохранит evidence полной лицензии.
| Chatterbox | Код MIT: https://github.com/resemble-ai/chatterbox/blob/master/LICENSE. Репозиторий README сообщает, что исследовательский проект retired в августе2026 и больше не поддерживается: https://github.com/resemble-ai/chatterbox. `ResembleAI/chatterbox-nano` model card — MIT: https://huggingface.co/ResembleAI/chatterbox-nano. | Не core dependency; optional эксперимент только с точным checkpoint/revision, локальным тестом качества и сохранением карточки.
| Wan 2.2 | GitHub license file Apache-2.0: https://github.com/Wan-Video/Wan2.2/blob/main/LICENSE.txt. TI2V-5B model card — Apache-2.0, repo 34.2 GB: https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B. I2V-A14B — Apache-2.0, repo 126 GB: https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B. | Лицензия не отменяет hardware/disk constraints. Не скачивать на Codespaces 32GB. Experiment только в бесплатном GPU окружении с доступной квотой ≤2 GPU-hours; фактическая доступность Kaggle не гарантируется.
| DepthFlow | PyPI metadata `AGPL-3.0`: https://pypi.org/project/depthflow/ ; GitHub `pyproject.toml`: https://github.com/BrokenSource/DepthFlow/blob/main/pyproject.toml. Readme/PyPI призывает к commercial use, но SPDX license остаётся AGPL-3.0; подтверждённой отдельной коммерческой MIT dual-license в просмотренных первичных материалах не найдено. | Считать AGPL-3.0. AGPL не означает автоматического запрета коммерческого использования; до интеграции/распространения проверить обязанности по лицензии и юристом при необходимости. Не заявлять, что generated MP4 сам по себе автоматически становится AGPL.
| Depth Anything V2 | Код LICENSE Apache-2.0: https://github.com/DepthAnything/Depth-Anything-V2/blob/main/LICENSE. Checkpoint Small — Apache-2.0: https://huggingface.co/depth-anything/Depth-Anything-V2-Small. Base — CC-BY-NC-4.0: https://huggingface.co/depth-anything/Depth-Anything-V2-Base. Large — CC-BY-NC-4.0: https://huggingface.co/depth-anything/Depth-Anything-V2-Large. | Для монетизируемого проекта разрешать только Small при зафиксированном checkpoint revision. Base/Large не использовать коммерчески на условиях NC. Другие/будущие checkpoints — отдельная проверка.
| Remotion | Free License для individuals и teams до3 людей; включена коммерческая деятельность и automation согласно официальным terms/pricing: https://www.remotion.dev/docs/license/pricing ; https://www.remotion.dev/docs/terms. | Подходит соло-проекту за $0 в указанных условиях. Это не OSI open-source лицензия; не называть Remotion open-source. При росте команды пересмотреть условия.

**Хранилище:** Hugging Face free private quota 100GB; single-file hard limit 500GB, recommended <200GB; no per-repository total limit for model/dataset beyond account quota (verify current page at https://huggingface.co/docs/hub/storage-limits). Cloudflare R2 free tier 10GB-month, 1M ClassA, 10M ClassB, egress free; Standard only, not Infrequent Access; https://developers.cloudflare.com/r2/pricing/.

## S11. Пробелы и дополнительные QC

### 11.1 Scientific accuracy

- Claim-level audit: источник должен поддерживать именно формулировку и степень уверенности. Сохранять DOI, author/year, page/figure/table/paragraph, quote/paraphrase, access date и SHA скачанного PDF/HTML snapshot где законно.
- `MEASURED` vs `ESTIMATE` см. S1. Не делать модельный результат «измерением»; не считать обнаружение элемента доказательством жизни. Для конфликтующих моделей сохранять обе оценки, assumptions и range.
- `MEASURED` допускается только при primary source; `ESTIMATE` может ссылаться на primary source с описанием модели/допущений. Source URL existence не заменяет содержательную сверку.

### 11.2 AI visual QC / provenance

- Каждый AI кадр: contact sheet в нативном размере и after-encoding; просмотреть topology/геометрию аппарата, повторяющиеся структуры, невозможные тени/рефлексы, линии горизонта, текст/символы, частицы, scale consistency, deformation и scene-to-scene continuity.
- AI video: contact sheet sampling 1 fps plus continuous playback; проверить morphing объектов, frame-to-frame identity, временную непрерывность, физически невозможное движение. Один красивый frame не доказывает хороший clip.
- SynthID: указывать `positive|negative|not_supported|not_checked` и URL/дата проверки. Водяной знак обнаруживает определённое происхождение от Google/партнёров; отсутствие watermark не доказывает, что медиа не AI. https://deepmind.google/models/synthid/ и https://synthid.com/.
- C2PA/Content Credentials: проверять подпись/manifest, сохранять оригинальный asset и исходный provenance manifest; montage/export может потерять или не сохранить ingredient metadata. C2PA подтверждает provenance/целостность утверждений в manifest, но не фактологическую истинность изображения. Спецификация: https://spec.c2pa.org/specifications/.
- YouTube может применять автоматические labels по собственным GenAI tools/C2PA signals/internal signals. Это не заменяет явный `AI use` владельца при необходимости. Не считать SynthID/C2PA детектором научной истинности.

### 11.3 Thumbnail/title/analytics

- Готовить 2–3 title/thumbnail candidates; проверять thumbnail в малом размере на контрасте и читаемости, не делать ложный научный claim.
- YouTube Studio A/B tests позволяют сравнить до3 title/thumbnail combinations; выбирается вариант с наибольшим watch time, функция desktop/advanced features, и некоторые типы видео исключены. Тест инициирует владелец. Официально: https://support.google.com/youtube/answer/16391400.
- Анализировать CTR вместе с impressions и traffic source; CTR сам по себе не цель и может меняться по мере расширения аудитории. Смотреть AVD/APV, 30s retention, retention dips/spikes, traffic source, new/returning viewers. Источник: https://support.google.com/youtube/answer/9314415.

### 11.4 Accessibility

- Предоставлять синхронизированные captions для всей заранее записанной речи/аудиоконтента; важные неречевые звуки указывать, если они несут смысл. WCAG 2.2 SC1.2.2 Level A: https://www.w3.org/WAI/WCAG22/Understanding/captions-prerecorded.html.
- Для текстовых элементов проверять контраст минимум 4.5:1 для обычного текста, 3:1 для крупного (WCAG 2.2 SC1.4.3 AA): https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html.
- Избегать миганий >3 в секунду; учитывать WCAG 2.2 SC2.3.2 (AAA) и как минимум правила уровня A 2.3.1: https://www.w3.org/WAI/WCAG22/Understanding/three-flashes.html.

### 11.5 Backup/recovery

- Backup содержит assets, audio master, approved script, scene/claim/rights manifests, exact model/version and config manifests, QC evidence, owner-approved outputs. Не хранить единственную копию в `/tmp`, ephemeral Codespaces или Git-only.
- После backup запускать `sha256sum -c`; выполнить тестовое восстановление в другую директорию и ещё раз проверить SHA. Только после этого помечать `backup_verified=true`.
- После interruption сверить SQLite journal, remote generation task statuses, output hashes и resource capacity. Если неизвестно, завершилась ли операция Flow, сначала выяснить job status; не слать duplicate generation request.

## S12. Основные первоисточники

### Mission science
- Levin et al., Europe ice shell/conductive layer: https://doi.org/10.1038/s41550-025-02718-0
- NASA Europa Clipper timeline: https://science.nasa.gov/mission/europa-clipper/mission-timeline/
- EPSC-DPS2025 explicit first flyby 7 March 2031: https://meetingorganizer.copernicus.org/EPSC-DPS2025/EPSC-DPS2025-1031.html
- JPL trajectory analysis paper: https://www.issfd.org/ISSFD_2024/ISSFD2024_19-3.pdf
- Europa Clipper 49 flybys / overview: https://www.jpl.nasa.gov/press-kits/europa-clipper/quick-facts/
- Postberg et al. phosphate ice grains: https://doi.org/10.1038/s41586-023-05987-9
- Waite et al. H2 detection: https://doi.org/10.1126/science.aai8703
- Khawaja et al. fresh organics: https://doi.org/10.1038/s41550-025-02655-y

### Official product/license documentation
- Kokoro: https://github.com/hexgrad/kokoro/blob/main/LICENSE ; https://huggingface.co/hexgrad/Kokoro-82M
- faster-whisper: https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE ; https://huggingface.co/Systran/faster-whisper-large-v3
- Piper source/license: https://github.com/OHF-Voice/piper1-gpl/blob/main/setup.py ; voices policy: https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/VOICES.md
- Chatterbox: https://github.com/resemble-ai/chatterbox/blob/master/LICENSE ; https://github.com/resemble-ai/chatterbox ; https://huggingface.co/ResembleAI/chatterbox-nano
- Wan 2.2: https://github.com/Wan-Video/Wan2.2/blob/main/LICENSE.txt ; https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B ; https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B
- DepthFlow: https://github.com/BrokenSource/DepthFlow/blob/main/pyproject.toml ; https://pypi.org/project/depthflow/
- Depth Anything V2: https://github.com/DepthAnything/Depth-Anything-V2/blob/main/LICENSE ; https://huggingface.co/depth-anything/Depth-Anything-V2-Small ; https://huggingface.co/depth-anything/Depth-Anything-V2-Base ; https://huggingface.co/depth-anything/Depth-Anything-V2-Large
- Remotion: https://www.remotion.dev/docs/license/pricing ; https://www.remotion.dev/docs/terms
- Hugging Face storage: https://huggingface.co/docs/hub/storage-limits
- Cloudflare R2 pricing: https://developers.cloudflare.com/r2/pricing/

### YouTube/policy/quality
- AI disclosure: https://support.google.com/youtube/answer/14328491
- AI labels update: https://support.google.com/youtube/blog/424874071/updates-to-ai-content-disclosure-and-labels
- YPP thresholds update: https://support.google.com/youtube/answer/12843009
- YPP requirements and country list: https://support.google.com/youtube/answer/72851 ; https://support.google.com/youtube/answer/7101720
- Inauthentic content policy: https://support.google.com/youtube/answer/1311392
- YouTube retention: https://support.google.com/youtube/answer/9314415
- A/B title/thumbnail: https://support.google.com/youtube/answer/16391400
- FFmpeg scdet: https://ffmpeg.org/ffmpeg-filters.html#scdet
- SynthID: https://deepmind.google/models/synthid/
- C2PA: https://spec.c2pa.org/specifications/
- WCAG captions/contrast/flashes: https://www.w3.org/WAI/WCAG22/Understanding/captions-prerecorded.html ; https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html ; https://www.w3.org/WAI/WCAG22/Understanding/three-flashes.html

**Ограничения проверки:** правила и лицензии меняются; перед каждым реальным использованием фиксировать exact revision, текущую LICENSE/MODEL_CARD/terms snapshot и date. Указанные источники не заменяют юридическое заключение.
