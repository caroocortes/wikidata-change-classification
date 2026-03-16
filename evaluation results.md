### TIME

| Percentage of FP | Label | 
| ---------- | ----- |
| 9 / 98 | unrefinement |
| 4 / 100 | refinement |
| 5 / 99 | re_formatting |
| 0 / 94 | property_value_update |

### QUANTITY
| Percentage of FP | Label | 
| ---------- | ----- |
| 0 / 100 | property_value_update |
| 3 / 91 | unrefinement |
| 2 / 102 | re-formatting |
| 17 / 98 | refinement |

### TEXT
| Percentage of FP | Label | 
| ---------- | ----- |
|  24 / 90 | property_value_update |
|  12 / 86 | unrefinement |
|  12 / 82 | re-formatting |
|  23 / 95 | refinement |
|  17 / 39 | rewording | 
|  12 / 72 | textual_change |

### ENTITY
| Percentage of FP | Label | 
| ---------- | ----- |
|  5 / 74 | property_value_update |
|  1 / 87 | unrefinement |
|  6 / 71 | refinement | 
|  8 / 92 | link_change | 

### GLOBECOORDINATE
| Percentage of FP | Label | 
| ---------- | ----- |
|  47 / 150 | property_value_update |
|  3 / 17 | unrefinement |
|  3 / 31 | re-formatting |
|  7 / 42 | refinement |

**Note:** 
```
select count(*)
from sampled_evaluation_<datatype>
where label = 'label' and correct_label != 'label'
```