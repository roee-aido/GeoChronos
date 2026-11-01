# Semantic diff of the base seed (pre-night backup → night)

The night run re-serialised `items.json` and `vocabulary.json` (formatting only changed by a patch script); this JSON-level diff shows the actual content changes.

## items.json

### `items`: 0 added, 0 removed, 12 changed

- changed `item:caral`: wd_review
- changed `item:dead-sea-scrolls`: wd_review
- changed `item:gobekli-tepe`: time
- changed `item:great-pyramid-of-giza`: attrs, time
- changed `item:great-sphinx-of-giza`: links, time, wd_review
- changed `item:masada`: attrs, wd_review
- changed `item:mausoleum-of-qin-shi-huang`: wd_review
- changed `item:qumran-caves`: pov
- changed `item:rock-hewn-churches-lalibela`: wd_review
- changed `item:rosetta-stone`: attrs, time
- changed `item:stonehenge`: time, wd_review
- changed `item:tower-of-jericho`: pov, time

### `events`: 0 added, 0 removed, 0 changed


### `persons`: 0 added, 0 removed, 0 changed


## vocabulary.json

### `predicates`: 2 added, 0 removed, 0 changed

- added `has_style`
- added `named_after`

### `entities`: 2 added, 0 removed, 2 changed

- added `concept:function:storage`
- added `concept:function:water-management`
- changed `period:neolithic`: crosswalk_note, wikidata
- changed `place:locality:rashid`: wd_review

