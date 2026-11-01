"""GeoChronos time utilities: the stored value vs. its display representations.

Stored value (see DATA_MODEL.md §4):
    astronomical years (1 BCE = 0, 2 BCE = -1, ...), four inclusive bounds,
    plus an optional Julian Day Number (JDN) for day-precise dates.

This module converts authoring input to that value and renders it in several
calendars/eras without ever changing it:
    * civil      - "c. 2600-2500 BCE", "24 August 79 CE (Julian)"
    * BP         - years before 1950 ("cal BP" for calendar dates)
    * hebrew     - Anno Mundi year(s); full day/month/year when a JDN is known

Hebrew calendar arithmetic follows Reingold & Dershowitz, "Calendrical
Calculations" (fixed-date / R.D. approach). Stdlib only.
"""
import math

# ---------------------------------------------------------------- years ----

def hist_to_astro(year):
    """Historical year (negative = BCE, no year 0) -> astronomical year."""
    if year == 0:
        raise ValueError("historical numbering has no year 0")
    return year + 1 if year < 0 else year


def astro_to_hist(year):
    """Astronomical year -> (abs_year, 'BCE'|'CE')."""
    y = int(math.floor(year))
    return (1 - y, "BCE") if y <= 0 else (y, "CE")


# ------------------------------------------------------ fixed dates (R.D.) ---
# R.D. 1 = 1 January 1 CE (proleptic Gregorian). JDN = RD + 1721425.
JDN_OFFSET = 1721425


def _gregorian_leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def fixed_from_gregorian(y, m, d):
    """y is astronomical."""
    corr = 0 if m <= 2 else (-1 if _gregorian_leap(y) else -2)
    return (365 * (y - 1) + (y - 1) // 4 - (y - 1) // 100 + (y - 1) // 400
            + (367 * m - 362) // 12 + corr + d)


def fixed_from_julian(y, m, d):
    """y is astronomical (Julian leap years: y % 4 == 0)."""
    corr = 0 if m <= 2 else (-1 if y % 4 == 0 else -2)
    return -2 + 365 * (y - 1) + (y - 1) // 4 + (367 * m - 362) // 12 + corr + d


def gregorian_from_fixed(date):
    d0 = date - 1
    n400, d1 = divmod(d0, 146097)
    n100, d2 = divmod(d1, 36524)
    n4, d3 = divmod(d2, 1461)
    n1 = d3 // 365
    year = 400 * n400 + 100 * n100 + 4 * n4 + n1
    if n100 != 4 and n1 != 4:
        year += 1
    prior = date - fixed_from_gregorian(year, 1, 1)
    corr = 0 if date < fixed_from_gregorian(year, 3, 1) else (1 if _gregorian_leap(year) else 2)
    month = (12 * (prior + corr) + 373) // 367
    day = date - fixed_from_gregorian(year, month, 1) + 1
    return year, month, day


def julian_from_fixed(date):
    approx = (4 * (date + 1) + 1464) // 1461
    year = approx
    prior = date - fixed_from_julian(year, 1, 1)
    corr = 0 if date < fixed_from_julian(year, 3, 1) else (1 if year % 4 == 0 else 2)
    month = (12 * (prior + corr) + 373) // 367
    day = date - fixed_from_julian(year, month, 1) + 1
    return year, month, day


def jdn_from_date(y_astro, m, d, calendar="gregorian"):
    f = fixed_from_julian if calendar == "julian" else fixed_from_gregorian
    return f(y_astro, m, d) + JDN_OFFSET


# -------------------------------------------------------------- Hebrew ----
HEBREW_EPOCH = fixed_from_julian(-3760, 10, 7)  # 7 Oct 3761 BCE (Julian) = 1 Tishrei AM 1
TISHRI, NISAN = 7, 1


def hebrew_leap_year(y):
    return (7 * y + 1) % 19 < 7


def _last_month(y):
    return 13 if hebrew_leap_year(y) else 12


def _elapsed_days(y):
    months = (235 * y - 234) // 19
    parts = 12084 + 13753 * months
    days = 29 * months + parts // 25920
    return days + 1 if (3 * (days + 1)) % 7 < 3 else days


def _year_length_correction(y):
    ny0, ny1, ny2 = _elapsed_days(y - 1), _elapsed_days(y), _elapsed_days(y + 1)
    if ny2 - ny1 == 356:
        return 2
    if ny1 - ny0 == 382:
        return 1
    return 0


def hebrew_new_year(y):
    return HEBREW_EPOCH + _elapsed_days(y) + _year_length_correction(y)


def _days_in_year(y):
    return hebrew_new_year(y + 1) - hebrew_new_year(y)


def _last_day_of_month(y, m):
    n = _days_in_year(y)
    if (m in (2, 4, 6, 10, 13) or (m == 12 and not hebrew_leap_year(y))
            or (m == 8 and n not in (355, 385)) or (m == 9 and n in (353, 383))):
        return 29
    return 30


def fixed_from_hebrew(y, m, d):
    date = hebrew_new_year(y) + d - 1
    if m < TISHRI:
        date += sum(_last_day_of_month(y, mm) for mm in range(TISHRI, _last_month(y) + 1))
        date += sum(_last_day_of_month(y, mm) for mm in range(NISAN, m))
    else:
        date += sum(_last_day_of_month(y, mm) for mm in range(TISHRI, m))
    return date


def hebrew_from_fixed(date):
    approx = int((date - HEBREW_EPOCH) // (35975351 / 98496)) + 1
    year = approx if hebrew_new_year(approx) <= date else approx - 1
    start = NISAN if date >= fixed_from_hebrew(year, NISAN, 1) else TISHRI
    month = start
    while date > fixed_from_hebrew(year, month, _last_day_of_month(year, month)):
        month += 1
    return year, month, date - fixed_from_hebrew(year, month, 1) + 1


HEBREW_MONTHS_EN = {1: "Nisan", 2: "Iyyar", 3: "Sivan", 4: "Tammuz", 5: "Av", 6: "Elul", 7: "Tishrei",
                    8: "Heshvan", 9: "Kislev", 10: "Tevet", 11: "Shevat", 12: "Adar", 13: "Adar II"}
HEBREW_MONTHS_HE = {1: "ניסן", 2: "אייר", 3: "סיוון", 4: "תמוז", 5: "אב", 6: "אלול", 7: "תשרי",
                    8: "חשוון", 9: "כסלו", 10: "טבת", 11: "שבט", 12: "אדר", 13: "אדר ב׳"}


def hebrew_month_name(y, m, lang="en"):
    if m == 12 and hebrew_leap_year(y):
        return "Adar I" if lang == "en" else "אדר א׳"
    return (HEBREW_MONTHS_EN if lang == "en" else HEBREW_MONTHS_HE)[m]


_GEMATRIA = [(400, "ת"), (300, "ש"), (200, "ר"), (100, "ק"), (90, "צ"), (80, "פ"), (70, "ע"), (60, "ס"),
             (50, "נ"), (40, "מ"), (30, "ל"), (20, "כ"), (10, "י"), (9, "ט"), (8, "ח"), (7, "ז"),
             (6, "ו"), (5, "ה"), (4, "ד"), (3, "ג"), (2, "ב"), (1, "א")]


def gematria(n, drop_thousands=True):
    """Hebrew numeral with geresh/gershayim, e.g. 5785 -> 'תשפ״ה' (or 'ה׳תשפ״ה'), 15 -> 'ט״ו'."""
    prefix = ""
    if n >= 1000:
        if not drop_thousands:
            prefix = gematria(n // 1000)          # e.g. 5 -> 'ה׳'
            if not prefix.endswith("׳"):
                prefix += "׳"
        n %= 1000
        if n == 0:
            return prefix
    letters = []
    while n > 0:
        if n % 100 in (15, 16):
            letters += ["ט", "ו" if n % 100 == 15 else "ז"]
            n -= n % 100
            continue
        for v, ch in _GEMATRIA:
            if v <= n:
                letters.append(ch)
                n -= v
                break
    s = "".join(letters)
    return prefix + (s + "׳" if len(s) == 1 else s[:-1] + "״" + s[-1])


# ---------------------------------------------------------- formatters ----

def _fmt_year(y_astro, coarse=False):
    n, era = astro_to_hist(y_astro)
    if coarse and n >= 100:
        n = int(round(n, -1))
    return f"{n:,} {era}" if n >= 10000 else f"{n} {era}"


def format_civil(ext):
    """ext: dict with earliest_start, latest_start, earliest_end, latest_end,
    precision, qualifier, jdn_start, jdn_end, source_calendar."""
    prec = ext.get("precision")
    if prec in ("ka", "Ma"):
        return format_bp(ext, deep=True)
    if prec == "day" and ext.get("jdn_start") is not None:
        cal = ext.get("source_calendar") or "gregorian"
        conv = julian_from_fixed if cal == "julian" else gregorian_from_fixed
        months = ["January", "February", "March", "April", "May", "June", "July", "August",
                  "September", "October", "November", "December"]
        tag = " (Julian)" if cal == "julian" else ""
        y, m, d = conv(ext["jdn_start"] - JDN_OFFSET)
        text = f"{d} {months[m - 1]} {_fmt_year(y)}"
        jdn_end = ext.get("jdn_end")
        if jdn_end is not None and jdn_end != ext["jdn_start"]:
            y2, m2, d2 = conv(jdn_end - JDN_OFFSET)
            text = (f"{d}–{d2} {months[m - 1]} {_fmt_year(y)}" if (y, m) == (y2, m2)
                    else f"{d} {months[m - 1]} – {d2} {months[m2 - 1]} {_fmt_year(y2)}" if y == y2
                    else f"{text} – {d2} {months[m2 - 1]} {_fmt_year(y2)}")
        prefix = {"after": "after ", "before": "before ", "circa": "c. "}.get(ext.get("qualifier"), "")
        return f"{prefix}{text}{tag}"
    es, ls, ee, le = (ext.get(k) for k in ("earliest_start", "latest_start", "earliest_end", "latest_end"))
    start = es if es is not None else ls
    end = le if le is not None else ee
    circa = "c. " if ext.get("qualifier") == "circa" else ""
    if ext.get("qualifier") == "before" and end is not None:
        return f"before {_fmt_year(end + 1)}"
    if ext.get("qualifier") == "after" and start is not None:
        return f"after {_fmt_year(start - 1)}"
    if start is None and end is None:
        return "date unknown"
    coarse0 = bool(circa) and prec in ("century", "millennium")
    if start is None:
        return f"{circa}? – {_fmt_year(end, coarse0)}"
    if end is None:
        return f"{circa}{_fmt_year(start, coarse0)} – ?"
    coarse = bool(circa) and prec in ("century", "millennium")
    if start == end:
        return f"{circa}{_fmt_year(start, coarse)}"
    s_n, s_era = astro_to_hist(start)
    e_n, e_era = astro_to_hist(end)
    if coarse:
        s_n, e_n = (int(round(v, -1)) if v >= 100 else v for v in (s_n, e_n))
    if s_era == e_era:
        return f"{circa}{s_n:,}–{e_n:,} {e_era}" if max(s_n, e_n) >= 10000 else f"{circa}{s_n}–{e_n} {e_era}"
    return f"{circa}{_fmt_year(start, coarse)} – {_fmt_year(end, coarse)}"


def format_bp(ext, deep=False):
    """Years before present (1950). For calendar-derived values this is 'cal BP'.
    If the source said 'X years ago' (time_basis='years_before_source') the output says so instead of
    claiming BP: the 1950 anchor is a POC conversion assumption, not the source's statement."""
    text = _format_bp(ext, deep)
    if ext.get("time_basis") == "years_before_source":
        text = text.replace(" cal BP", " BP").replace(" BP", " years ago (source wording; stored relative to 1950)")
        text = text.replace("ka years ago", "ka ago").replace("Ma years ago", "Ma ago")
    return text


def _format_bp(ext, deep=False):
    start = ext.get("earliest_start") if ext.get("earliest_start") is not None else ext.get("latest_start")
    end = ext.get("latest_end") if ext.get("latest_end") is not None else ext.get("earliest_end")
    if start is None and end is None:
        return "date unknown"

    def bp(y):
        v = 1950 - y
        if deep or v >= 10000:
            return f"{v / 1000:,.1f} ka" if v < 1_000_000 else f"{v / 1_000_000:,.2f} Ma"
        return f"{v:,.0f}"
    circa = "c. " if ext.get("qualifier") == "circa" else ""
    first = start if start is not None else end
    if first > 1950:
        return "after 1950 (BP not applicable)"
    if end is not None and end > 1950:
        return f"{circa}{bp(first)} cal BP – after 1950"
    if start is None or end is None or start == end:
        v = start if start is not None else end
        return f"{circa}{bp(v)} BP" if (deep or 1950 - v >= 10000) else f"{circa}{bp(v)} cal BP"
    unit = "BP" if (deep or 1950 - start >= 10000) else "cal BP"
    return f"{circa}{bp(start)}–{bp(end)} {unit}"


FIXED_CALENDAR_COMPLETE = 1178   # 'Between 70 and 1178 CE, the observation-based calendar was gradually replaced by a
                                 #  mathematically calculated one' (English Wikipedia, 'Hebrew calendar', rev. cited in
                                 #  data/seed/wikipedia_evidence.json). Earlier renderings are proleptic.


def format_hebrew(ext, lang="en", proleptic_note=True):
    """Wrapper adding an explicit note when the date precedes the fully fixed Hebrew calendar."""
    text = _format_hebrew(ext, lang)
    end = ext.get("latest_end") if ext.get("latest_end") is not None else ext.get("earliest_end")
    start = ext.get("earliest_start") if ext.get("earliest_start") is not None else ext.get("latest_start")
    ref = end if end is not None else start
    if proleptic_note and ref is not None and ref < FIXED_CALENDAR_COMPLETE and "before AM 1" not in text:
        text += " [computed proleptically]" if lang == "en" else " [חישוב לאחור]"
    return text


def _format_hebrew(ext, lang="en"):
    """Anno Mundi representation of the same stored value.
    Day precision -> full Hebrew date. Year/coarser -> AM year span.
    Before AM 1 (autumn 3761 BCE) the Hebrew era is undefined -> explicit note."""
    if ext.get("precision") == "day" and ext.get("jdn_start") is not None:
        def one(jdn):
            y, m, d = hebrew_from_fixed(jdn - JDN_OFFSET)
            if lang == "he":
                return f"{gematria(d)} ב{hebrew_month_name(y, m, 'he')} {gematria(y)}"
            return f"{d} {hebrew_month_name(y, m)} {y} AM"
        text = one(ext["jdn_start"])
        if ext.get("jdn_end") is not None and ext["jdn_end"] != ext["jdn_start"]:
            text = f"{text} – {one(ext['jdn_end'])}"
        prefix = {"after": "after ", "before": "before "}.get(ext.get("qualifier"), "")
        return prefix + text
    start = ext.get("earliest_start") if ext.get("earliest_start") is not None else ext.get("latest_start")
    end = ext.get("latest_end") if ext.get("latest_end") is not None else ext.get("earliest_end")
    if start is None and end is None:
        return "date unknown"
    open_end = end is None
    start = start if start is not None else end
    end = end if end is not None else start
    # A civil (astronomical) year Y overlaps AM Y+3760 (until Tishrei) and Y+3761 (from Tishrei).
    am_start, am_end = int(math.floor(start)) + 3760, int(math.floor(end)) + 3761
    circa = "c. " if ext.get("qualifier") == "circa" else ""
    if am_end < 1:
        if open_end or am_end - am_start <= 1:
            return f"before AM 1 (≈{1 - am_start:,} years before the Anno Mundi epoch" + (", end unknown)" if open_end else ")")
        return f"before AM 1 (≈{1 - am_start:,}–{1 - am_end:,} years before the Anno Mundi epoch)"
    if am_start < 1:
        return f"{circa}before AM 1 – AM {am_end:,}"
    if lang == "he":
        return f"{circa}{gematria(am_start, False)}–{gematria(am_end, False)}"
    return f"{circa}AM {am_start:,}–{am_end:,}"


def self_test():
    """Known reference points (all well-established calendar facts)."""
    g = fixed_from_gregorian
    # 1 Tishrei 5785 = 3 Oct 2024; 15 Nisan 5784 = 23 Apr 2024; 23 Tevet 5760 = 1 Jan 2000
    assert hebrew_from_fixed(g(2024, 10, 3)) == (5785, 7, 1)
    assert hebrew_from_fixed(g(2024, 4, 23)) == (5784, 1, 15)
    assert hebrew_from_fixed(g(2000, 1, 1)) == (5760, 10, 23)
    # JDN of 1 Jan 2000 (Gregorian) = 2451545; 1 Jan 4713 BCE (Julian) = JDN 0
    assert jdn_from_date(2000, 1, 1) == 2451545
    assert jdn_from_date(-4712, 1, 1, "julian") == 0
    # Gregorian reform: 4 Oct 1582 (Julian) is followed by 15 Oct 1582 (Gregorian)
    assert fixed_from_julian(1582, 10, 4) + 1 == fixed_from_gregorian(1582, 10, 15)
    assert gregorian_from_fixed(g(-2499, 3, 1)) == (-2499, 3, 1)
    assert julian_from_fixed(fixed_from_julian(79, 8, 24)) == (79, 8, 24)
    assert hist_to_astro(-2500) == -2499 and astro_to_hist(-2499) == (2500, "BCE")
    assert gematria(5785) == "תשפ״ה" and gematria(15) == "ט״ו"
    assert gematria(5785, drop_thousands=False) == "ה׳תשפ״ה"
    return True


if __name__ == "__main__":
    print("timefmt self-test:", "OK" if self_test() else "FAILED")
