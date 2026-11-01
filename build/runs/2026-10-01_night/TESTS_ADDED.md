# בדיקות שנוספו בריצת הלילה ולמה

הרצה: `python -m unittest discover -s tests -v`. 40 בדיקות, כולן עוברות. הריצה האחרונה: `final_after_docs/tests.stderr.txt`, 23:09:03–23:09:32.

הבדיקות בונות מסדים זמניים בתיקיות temp, ואינן נוגעות ב־`build/`.

| קובץ | מה נבדק | למה (סעיף בתדריך) |
|---|---|---|
| `tests/test_claim_filters.py` (9) | `rejected`/`deprecated` לא מופיעים בתוצאות רגילות: מיקום, ירושת מיקום (`part_of`), הכלה גאוגרפית, היררכיית מושגים, שאילתה משולבת, טענת זמן. `disputed`/`alternative` נשמרים ומסומנים (`uncertain_only`, `uncertain`). | §2.1. בבדיקה נמצא שה־views של GEO וההיררכיה סיננו רק `deprecated` ולא `rejected`. תוקן. |
| `tests/test_time_semantics.py` (7) | סדר ארבעת הגבולות נאכף ב־schema (שני CHECK חדשים); possible מול certain; קצה פתוח וקצה התחלה פתוח (evidence מול unbounded); תפקידי זמן (discovery מוחרג כברירת מחדל); `time_unknown`; גבול שנת אפס (1 BCE = 0). | §2.2. נמצאו ותוקנו: "certain" הניח סוף ידוע גם כשלא היה, והתחלה לא ידועה נקראה כמינוס אינסוף גם במצב "evidence". |
| `tests/test_calendars.py` (8) | המרה היסטורי ↔ אסטרונומי; כיול מספור Wikidata מול JSON אמיתי (≥8 ערכים); מרווחי מאה, אלף ועשור לפי Help:Dates; JDN ויוליאני/גרגוריאני (עוגן Titus מ־Wikidata); המרה עברית מול 9 fixtures של Hebcal; BP בבסיס 1950; "years ago" לא מוצג כ־BP. | §2.3. נמצא באג אמיתי: ערכי Wikidata בדיוק של מאה ומעלה פורשו עם הזזת שנה. בנוסף, ציפייה שגויה שלי (סימן ההפרש יוליאני/גרגוריאני) נתפסה ותוקנה בבדיקה, לא בקוד. |
| `tests/test_provenance_identity.py` (14) | **מיקום אובייקטים:** נקודה מאומתת או בירושה בלבד; `reported_point` לעולם לא נקודת מפה; `held_by` ≠ הכלה. **Provenance:** לכל טענה יש ראיה; אין תאריך או מיקום על בסיס עריכה בלבד; לכל external_id יש מקור; אין 'high' אוטומטי לייבוא; locator של Wikidata כולל snapshot. **זהות:** QID ייחודי. **Idempotence:** אותו staging פעמיים; snapshot כפול; snapshot חדש עם תוכן זהה; ערך שהשתנה נשמר כ־deprecated. | §2.4–2.6 + §4. |
| `tests/test_query_examples.py` (2) | כל בלוק SQL ב־QUERY_EXAMPLES.md עם `-- test:` מורץ על מסד base ועל full, ומחזיר בדיוק את הקבוצה של הפונקציה המקבילה ב־geoquery.py. בלוקים של PostGIS חייבים להיות מסומנים NOT EXECUTED. | §2.2: דוגמאות SQL חייבות להציג אותה סמנטיקה כמו geoquery.py. |

## חבילות אימות (לא unittest)

- **`scripts/validate.py`:** 37 הבדיקות הקיימות, **ללא שינוי בציפיות**. רצות על מסד הבסיס ועוברות 37/37. הורצו גם על המסד המלא (מידע בלבד) ועברו 37/37 גם שם.
- **`scripts/validate_expansion.py` (חדש, 20 בדיקות):** תקרת 150; ייחודיות QID; זמן עמוק (Ma); טענה שנדחתה (Tiwanaku); מחלוקות (Serpent Mound, Tel Dan); facets חדשים (מסגד עם תקופות, סגנון, מקרא וכתובות); שיוך פוליטי מול גאוגרפי (Taputapuātea); חורבן הבית ללא JDN; סימון "proleptic" עברי; BP מול "years ago"; שמות AI.
