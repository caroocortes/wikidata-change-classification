# Dataset Labeling Rules

## Overview
todo: Brief description of the dataset and labeling objective.

---

## Label Definitions

| Label | Description |
|-------|-------------|
| `re_formatting` | ... |
| `refinement` | ... |

---

## [TIME]

### Re-formatting

**Sign changes:**
| Revision Id | Field | Value | Label |
|-------|-------|-------|-------|
| 1337270153 | `+1720-00-00T00:00:00Z` | `-1720-00-00T00:00:00Z` | `re_formatting` |


**Changes from 01 to 00:** Our intuition is that some editors are unaware of the possibility of using mm-dd as 00-00 for stating a date with only a year. Therefore, we classify these changes as ``re-formatting``

| Revision Id | Field | Value | Label |
|-------|-------|-------|-------|
| 1198631412 |  `+1941-01-01T00:00:00Z` | `+1941-00-00T00:00:00Z` | `re_formatting` |
| 630903684 | `+2017-12-01T00:00:00Z`| `+2017-12-00T00:00:00Z` | re_formatting

### Refinement

| Revision Id | Field | Value | Label |
|-------|-------|-------|-------|
| 1093707754 | `+1906-00-00T00:00:00Z` | `+1906-12-04T00:00:00Z` | `refinement` |
| 2203434956 | `+1955-01-01T00:00:00Z` | `+1955-03-25T00:00:00Z` | `refinement` |
| 165299259 | `+1682-00-00T00:00:00Z` | `+1682-01-01T00:00:00Z` | `refinement` |

### Property value update:
| Revision Id | Old | New | Label |
|-------|-------|-------|-------|
| 2254042698 | `+19-00-00T00:00:00Z` | `+1850-00-00T00:00:00Z` | `property_value_update` |

### Unrefinement:
| Revision Id | Old | New | Label |
| 1149239784 | `+1930-01-01T00:00:00Z` | `+1930-01-00T00:00:00Z` | `unrefinement` |


---