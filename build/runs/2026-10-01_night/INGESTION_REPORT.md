# INGESTION_REPORT — ריצת לילה 2026-10-01

אזור זמן: Asia/Jerusalem (IDT, UTC+03:00). כל הזמנים כאן לקוחים מ־manifests או מ־run logs.

## 1. מבנה התהליך (מה מומש)

```
fetch (scripts/ingest.py)  →  data/raw/<source>/<snapshot_id>/   (בלתי משתנה, MANIFEST.json עם checksums ותנאי שימוש)
                           →  data/staging/<source>/<snapshot_id>.jsonl   (ניתן לשחזור מ־raw)
mapping (scripts/build_db.py, MAPPING_VERSION = 2026-10-01.night.1)
                           →  claims + claim_evidence (locator כולל snapshot id)
report                     →  build_report.md + curation_queue_auto.csv
```

| דרישה בתדריך | מימוש | איך נבדק |
|---|---|---|
| manifest לכל snapshot | `MANIFEST.json`: source, endpoint/query, `started_at` / `completed_at` עם אזור זמן, sha256 לכל קובץ, `terms_status`, targets. גרסת ה־mapping רשומה בדוח הבנייה. | קבצים ב־`data/raw/**/MANIFEST.json` |
| raw בלתי משתנה | snapshot חדש = תיקייה חדשה. `--resume` מסרב להמשיך snapshot שהושלם. ה־snapshot הישן (`wikidata_2026-09-30.json`) לא נגע; נוסף לצידו manifest. | `ingest.py status` |
| caching | `data/cache/http/<sha256>.json` (164 רשומות). המטמון אינו provenance. | שדה `from_cache` ב־`*.request.json` |
| בקשות בקבוצות | SPARQL עם `VALUES` בקבוצות של 50 QIDs | 18 בקשות (snapshot 1), 30 בקשות (snapshot 2) |
| timeout | 120 שניות | קוד |
| retries מוגבלים + backoff | עד 4 ניסיונות, backoff מעריכי, כיבוד `Retry-After`, לכל היותר 60 שניות המתנה | **בפועל**: HTTP 502 אחד בכל אחת משתי ריצות Wikidata, שהצליח בניסיון השני (`retry_log` ב־manifests) |
| resume | קבצי batch קיימים מדולגים | קוד; לא נדרש בפועל הלילה |
| dry-run | `ingest.py wikidata --dry-run` מדפיס את תוכנית הבקשות בלי רשת | הורץ: "82 QIDs, 2 batch(es) x 9 queries" ובהמשך "122 QIDs, 3 batch(es) x 10 queries" |
| תור מועמדים לא מותאמים | `curation_queue_auto.csv` (קישורי Wikidata שלא הותאמו; תקופות Pleiades כמועמדים) | `build/runs/2026-10-01_night/CURATION_QUEUE.csv` |
| בדיקת idempotence אמיתית | 4 בדיקות על עותקי staging זמניים (סעיף 4) | `tests/test_provenance_identity.py` — עוברות |

## 2. Snapshots שנוצרו או נרשמו הלילה

| snapshot | מקור | קבצים / רשומות | זמן (manifest) | הערות |
|---|---|---|---|---|
| `wikidata_2026-09-30.json` (legacy) | WDQS | 7 שאילתות → 862 רשומות staging | אוחזר 2026-09-30 22:… UTC (כפי שנרשם אז) | נרשם הלילה (`wikidata_2026-09-30.MANIFEST.json`); הקובץ עצמו לא שונה |
| `wikidata/2026-10-01T222038+0300` | WDQS | 36 קבצים (18 תשובות + 18 request), 950 רשומות | 22:20:38–22:22:52 | 9 שאילתות כולל חדשות: `labels_he`, `findspots`; HTTP 502 ×1 → retry הצליח |
| `wikidata/2026-10-01T225416+0300` | WDQS | 60 קבצים, 1,556 רשומות | 22:54:16–22:55:41 | 122 QIDs (בסיס + הרחבה + מקומות/ארגונים), 10 שאילתות כולל `sitelinks_he`; HTTP 502 ×1 → retry הצליח |
| `pleiades/2026-10-01T222258+0300` | Pleiades per-place JSON | 33 מקומות, 0 שגיאות | 22:22:58 | מזהים רק מ־Wikidata P1584 |
| `pleiades/2026-10-01T225549+0300` | Pleiades | 45 מקומות, 0 שגיאות | 22:55:49–22:56:17 | 33 מתוכם קיימים במטמון; **פער:** סקריפט Pleiades לא רושם `from_cache` לכל קובץ |
| `wikidata_entitydata_2026-10-01` | Special:EntityData JSON | 13 קבצים | 22:16–22:33 (manifest עודכן 22:40) | לכיול מספור השנים (סעיף 5) ולבדיקת זהות Caral; נוצר ידנית (לא ב־ingest.py), עם manifest |
| `hebcal/2026-10-01T223012+0300` | Hebcal converter | 9 המרות | 22:30 | test fixtures בלבד |
| `openalex/2026-10-01T223612+0300` | OpenAlex `/works?search=` | 10 חיפושים | 22:36 | מטא־דאטה ו־abstracts כראיה מסומנת "ABSTRACT ONLY" |

## 3. מיפוי (mapping) ו־attribution

- **מיפוי אוטומטי רק לפי מזהה חיצוני מאומת:**
  - QIDs מוגדרים ב־`wikidata_targets*.json`, ונבדקו מול Wikipedia pageprops או תוויות ותיאורי Wikidata.
  - Pleiades ממופה רק דרך P1584 של Wikidata.
  - שמות תקופות של Pleiades (למשל `roman`, `hellenistic-republican`) **לא** ממופים אוטומטית. הם נכנסים לתור (176 שורות 'candidate').
- **כללי מיפוי שנוספו הלילה:**
  - P149 → `has_style` (סגנונות נוצרים כ־concepts מ־Wikidata).
  - P138 → `named_after` (רק אם היעד קיים).
  - P2596 כשהיעד הוא תקופה → `period`.
  - P361 כשהיעד הוא תרבות → `culture`.
  - P361 כשהיעד הוא concept → ה־facet של אותו concept.
- **Overrides של אוצר (`wd_review`)** ממופים לשלושה סטטוסים:
  - `rejected`: הטענה נשמרת לביקורת או נסגרת בתור.
  - `needs_verification`: לא מיובא, נשאר בתור.
  - `disputed`: מיובא ומסומן.
- **Attribution** נשמר בטבלת `source`, וכל ראיה נושאת URL, locator ו־retrieved_at:
  - Wikidata: CC0.
  - Pleiades: CC BY 3.0 (נדרש קרדיט ל־AWMC ו־ISAW).
  - Hebcal: CC BY 4.0 (fixtures בלבד).
  - OpenAlex: CC0 לפי עמוד עזרה.
  - Wikipedia: CC BY-SA. רק ציטוט revision, ללא העתקת טקסט.
  - דפי מוסדות: עובדות וקישור בלבד, תנאי שימוש `needs_verification`.
- **תנאי שימוש שנבדקו הלילה במקור הרשמי:**
  - Wikidata Licensing.
  - Pleiades downloads + credits.
  - OpenAlex authentication.
  - Hebcal developer page (נבדק בסשן הקודם ושוב שימש).

## 4. Idempotence — תוצאות אמיתיות

| בדיקה | תוצאה |
|---|---|
| אותו staging נבנה פעמיים → טביעת אצבע זהה של כל הטבלאות | עברה |
| אותו snapshot ב־staging פעמיים (קובץ כפול) → אין כפילויות | עברה (snapshot מזוהה לפי `snapshot_id`) |
| snapshot חדש עם תוכן זהה → אין שורות עובדה כפולות; נוספת שורת ראיה אחת לכל טענה שאושרה מחדש | עברה |
| ערך שהשתנה (שינוי סינתטי של קואורדינטה) → הטענה הישנה נשארת כ־`deprecated` עם הערה, והחדשה `normal` | עברה |
| בין ה־snapshots האמיתיים של הלילה | 0 ערכים הוחלפו: לא היו שינויים בערכי Wikidata בין 2026-09-30 ל־2026-10-01 לפריטים המשותפים |

## 5. כיול Wikidata (ממצא מהותי)

Special:EntityData JSON הושווה מול WDQS ב־11 ערכים. הקבצים שמורים.

- **דיוק שנה, חודש או יום:** WDQS מחזיר מספור אסטרונומי (JSON `-1274` → RDF `-1273`). ימים מנורמלים לגרגוריאני: Titus, יוליאני 30.12.39 → גרגוריאני 28.12.39.
- **דיוק עשור, מאה או אלף:** WDQS מחזיר את השנה ההיסטורית **בלי** הזזה (Stonehenge `-3000` זהה ב־JSON וב־RDF).
- **שני מסמכים רשמיים סותרים:** RDF Dump Format אומר "1 BCE as +0000"; Help:Dates אומר "2 BCE is exported as -0002".
- **הכרעה אמפירית:** לפי הנתונים בפועל, ממומשת ב־`wd_value_bounds` ונבדקת ב־`tests/test_calendars.py`.

## 6. שגיאות ומגבלות גישה

- **HTTP 403, לא נעקף:**
  - whc.unesco.org
  - britishmuseum.org (EA24)
  - researchgate.net (Ahu Tongariki)
  - קודם לכן גם Europeana, Smithsonian, Historic England
- **HTTP 404 על כתובות שניחשתי:** דף פרויקט DAI, עמוד Giza ב־egymonuments. הדפים הנכונים נמצאו בחיפוש.
- **HTTP 429 בעבר** (Wikipedia, wbsearchentities). הלילה נשמר קצב של כ־6 שניות לבקשה מול Wikipedia, ללא 429.
- **Wikidata EntitySearch החזיר תוצאות ריקות לכמה חיפושים.** פתרון: Wikipedia pageprops (כותרת ערך → QID).
- **Getty AAT לא שולב** (תנאי השימוש ודף הנתונים לא נקראו במלואם). נשאר מחקר ומיפוי בלבד.
- **PeriodO לא שולב הלילה.** נבחרו Wikidata ו־Pleiades בלבד: התאמה ישירה ל־seed דרך מזהים מאומתים, ותנאי השימוש אומתו. הוספת PeriodO מחייבת מיפוי תקופות ידני (תור).
