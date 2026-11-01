# GeoChronos expansion validation report

DB: `geochronos.sqlite` (profile full)


**20/20 expansion checks passed.**

### PASS — Item count within the night's ceiling (≤150)

95 Items

### PASS — No Wikidata QID mapped to two entities

0 duplicates

## Deep time

### PASS — 4–3 million years ago (Ma precision)

2 result(s)

| canonical_name | role | label | civil | bp | hebrew | status | open_ended |
|---|---|---|---|---|---|---|---|
| Laetoli footprints | deposition | footprints dated to 3.7 million years ago | c. 3.70 Ma ago (source wording; stored relative to 1950) | c. 3.70 Ma ago (source wording; stored relative to 1950) | before AM 1 (≈3,694,291 years before the Anno Mundi epoch) | accepted | False |
| Lucy (AL 288-1) | life | lived around 3.2 million years ago | c. 3.20 Ma ago (source wording; stored relative to 1950) | c. 3.20 Ma ago (source wording; stored relative to 1950) | before AM 1 (≈3,194,291 years before the Anno Mundi epoch) | accepted | False |

### PASS — 70–60 million years ago

1 result(s)

| canonical_name | role | label | civil | bp | hebrew | status | open_ended |
|---|---|---|---|---|---|---|---|
| Chicxulub crater | event | formed slightly over 66 million years ago | 66.00 Ma ago (source wording; stored relative to 1950) | 66.00 Ma ago (source wording; stored relative to 1950) | before AM 1 (≈65,994,291 years before the Anno Mundi epoch, end unknown) | accepted | True |

### PASS — 80,000–70,000 years ago (events)

1 result(s)

| canonical_name | role | label | civil | bp | hebrew | status | open_ended |
|---|---|---|---|---|---|---|---|
| Youngest Toba eruption | event | occurred around 74,000 years ago | c. 74.0 ka ago (source wording; stored relative to 1950) | c. 74.0 ka ago (source wording; stored relative to 1950) | before AM 1 (≈68,291 years before the Anno Mundi epoch) | accepted | False |

## Rejected vs disputed claims

### PASS — Tiwanaku is NOT placed in 1600–1500 BC (the 1580 BC date is rejected)

7 result(s)

| canonical_name | role | label | civil | bp | hebrew | status | open_ended |
|---|---|---|---|---|---|---|---|
| Stonehenge | construction | phases from about 3100 BC to about 1600 BC | c. 3150–1500 BCE | c. 5,099–3,449 cal BP | c. AM 611–2,262 [computed proleptically] | accepted | False |
| Tel Megiddo | occupation | occupied continuously from the early Bronze Age (c. 3000 BCE) to the Persian period (c. 332 BCE) | c. 3050–330 BCE | c. 4,999–2,281 cal BP | c. AM 711–3,430 [computed proleptically] | accepted | False |
| Babylon | occupation | from the earliest mention to the last known habitation (11th century AD) | 2217 BCE – 1100 CE | 4,166–850 cal BP | AM 1,544–4,861 [computed proleptically] | accepted | False |
| Karnak Temple Complex | construction | from the reign of Senusret I (1971–1926 BCE) into the Ptolemaic Kingdom (305–30 BCE) | 1971–30 BCE | 3,920–1,979 cal BP | AM 1,790–3,732 [computed proleptically] | accepted | False |
| Knossos | use | palace: first built c. 1900 BC; major destruction conventionally c. 1350 BC | c. 1950–1300 BCE | c. 3,899–3,249 cal BP | c. AM 1,811–2,462 [computed proleptically] | accepted | False |
| Nebra sky disc | creation | dated by archaeologists to c. 1800–1600 BC (Early Bronze Age) | c. 1800–1600 BCE | c. 3,749–3,549 cal BP | c. AM 1,961–2,162 [computed proleptically] | accepted | False |
| Akrotiri (Bronze Age settlement) | destruction | most probably 1620–1530 BC (radiocarbon) | 1620–1530 BCE | 3,569–3,479 cal BP | AM 2,141–2,232 [computed proleptically] | disputed | False |

### PASS — …but the rejected claim is kept for audit

1 rejected claim(s) on Tiwanaku

### PASS — Serpent Mound: two disputed construction dates kept (300 BCE / c. 1070 CE)

built in 300 BCE by the Adena peoples (2014 radiocarbon, corroborated 2019); two charcoal samples dated ca. 1070 CE (1991)

### PASS — Tel Dan stele: three competing author attributions, none preferred

person:hazael, person:ben-hadad-iii, person:jehu

## POV-First on new facets

### PASS — Show mosques (function, incl. time-scoped function)

2 result(s)

| canonical_name | via |
|---|---|
| Great Mosque of Djenné | has_function:mosque |
| Hagia Sophia | has_function:mosque |

### PASS — Hagia Sophia 'museum' function carries its period (1935–2020) as a qualifier

{"from": 1935, "to": 2020}

### PASS — Theme: inscriptions and the Hebrew Bible

3 result(s)

| canonical_name | via |
|---|---|
| Mesha Stele | theme:inscriptions and the Hebrew Bible |
| Siloam inscription | theme:inscriptions and the Hebrew Bible |
| Tel Dan stele | theme:inscriptions and the Hebrew Bible |

### PASS — Architectural style imported from Wikidata P149 (Doric order)

1 result(s)

| canonical_name | via |
|---|---|
| Parthenon | has_style:Doric order |

### PASS — Combined: Levant + text + 1000–500 BCE

3 result(s)

| canonical_name | civil | status |
|---|---|---|
| Mesha Stele | c. 850–830 BCE | accepted |
| Siloam inscription | 800–701 BCE | accepted |
| Tel Dan stele | 900–801 BCE | accepted |

## GEO: political vs geographic placement

### PASS — Taputapuātea reaches 'Europe' only on a political basis (France) — basis is visible

political (modern state, Wikidata P17),administrative (Wikidata P131)

### PASS — Africa now includes the new African Items

18 result(s)

| canonical_name |
|---|
| Abu Simbel temples |
| Blombos Cave |
| Great Mosque of Djenné |
| Great Pyramid of Giza |
| Great Sphinx of Giza |
| Great Zimbabwe |
| Karnak Temple Complex |
| Kilwa Kisiwani |
| Laetoli footprints |
| Leptis Magna |
| Lucy (AL 288-1) |
| Mask of Tutankhamun |
| Obelisk of Aksum |
| Pyramid of Djoser |
| Pyramids of Meroë |
| Rock-hewn Churches of Lalibela |
| Rosetta Stone |
| Tomb of Tutankhamun (KV62) |

## Time representation edge cases

### PASS — 70 CE Temple destruction: month of Av / 10 Av (Josephus) / 9 Av (commemoration) kept, no Julian day computed

in the month of Av (July/August) the Romans captured the Temple Mount and destroyed the Second Temple; 10 Av: a Roman soldier set fire to the Temple (Josephus); commemorated in Judaism on Tisha B'Av (9 Av)

### PASS — Hebrew rendering before 1178 CE is flagged as proleptic; modern dates are not

6 Nisan 3565 AM [computed proleptically] | 9 Elul 5700 AM

### PASS — Explicit 'BP' sources render as BP; 'years ago' sources do not

18.5 ka–14.5 ka BP | 101.0 ka–70.0 ka ago (source wording; stored relative to 1950)

### PASS — AI-supplied Hebrew names are never presented as verified

112 entities have Hebrew names; 0 unflagged AI names

