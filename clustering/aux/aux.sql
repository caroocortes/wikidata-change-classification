WITH property_replacements AS (
    SELECT 
        cte1.revision_id as replaced_revision_id, 
        cte1.property_id as replaced_property_id, 
        cte1.value_id as replaced_value_id,
        cte2.revision_id as replacement_revision_id, 
        cte2.property_id as replacement_property_id, 
        cte2.value_id as replacement_value_id,
        cte1.entity_id
    FROM 
        change_timestamp_entity cte1 
        JOIN change_timestamp_entity cte2 ON 
            cte1.entity_id = cte2.entity_id AND 
            cte1.old_value = cte2.new_value
    WHERE 
        cte1.change_target = '' AND
        cte2.change_target = '' AND
        cte1.timestamp <= cte2.timestamp AND
        cte1.property_id != cte2.property_id AND
        cte1.action = 'DELETE' AND
        cte2.action = 'CREATE'
)
-- Get replaced changes
SELECT 
    'replaced' as change_type,
    pr.replaced_revision_id as pair_replaced_revision_id,
    pr.replacement_revision_id as pair_replacement_revision_id,
    r.revision_id, 
    r.entity_id,
    r.entity_label,
    vc.value_id,
    vc.property_id,
    vc.change_target,
    vc.property_label,
    vc.old_value,
    vc.old_value_label,
    vc.new_value,
    vc.new_value_label,
    vc.datatype
FROM property_replacements pr
JOIN revision r ON r.revision_id = pr.replaced_revision_id
JOIN value_change vc ON vc.revision_id = pr.replaced_revision_id 
    AND vc.property_id = pr.replaced_property_id 
    AND vc.value_id = pr.replaced_value_id

UNION ALL

-- Get replacement changes
SELECT 
    'replacement' as change_type,
    pr.replaced_revision_id as pair_replaced_revision_id,
    pr.replacement_revision_id as pair_replacement_revision_id,
    r.revision_id, 
    r.entity_id,
    r.entity_label,
    vc.value_id,
    vc.property_id,
    vc.change_target,
    vc.property_label,
    vc.old_value,
    vc.old_value_label,
    vc.new_value,
    vc.new_value_label,
    vc.datatype
FROM property_replacements pr
JOIN revision r ON r.revision_id = pr.replacement_revision_id
JOIN value_change vc ON vc.revision_id = pr.replacement_revision_id 
    AND vc.property_id = pr.replacement_property_id 
    AND vc.value_id = pr.replacement_value_id

ORDER BY pair_replaced_revision_id, pair_replacement_revision_id, change_type;


select r.revision_id, property_id, property_label, old_value, new_value, comment, timestamp, action, target, old_hash, new_hash
from value_change vc join revision r on vc.revision_id = r.revision_id
where r.timestamp <= (select timestamp from revision where revision_id = 1283751128)
and entity_label = 'Earth'
order by timestamp asc
limit 300

select 
	r.revision_id, 
	entity_id,
	entity_label,
	value_id,
	property_id,
	change_target,
	property_label,
	old_value,
	old_value_label,
	new_value,
	new_value_label,
	'reverted_edit' as label,
	datatype
from value_change vc join revision r on vc.revision_id = r.revision_id
where revision_id in (
-- Taylor Swift
10874142,
31889836,
32570654,
32570742,
32571250,
32571371,
41244638,
41947397,
50086874,
69518632, -- this &
69519638, -- this are not lineal
72814272,
73682514,
88264956,
93330631,
129408356,
129408356,
169850376,
182171609, -- this & 
182171910, -- this are not lineal
184398707,
-- pizza
48754132,
51621413,
67275779,
67275856,
193894310,
216497800,
274996857,
289069735,
302532016, -- this &
302532185, -- this are not lineal
332721621, -- this &
332722025, -- this are not lineal
339500590,
618991584,
803232241,
803232182,
803231898,
803233736,
933681563,
933681790,
-- Earth
6271,
11221611,
22176515,
22181622,
22181888,
54636922,
142524126,
156531596,
158279691,
-- Barack Obama
6847575,
7375872,
7376023,
8215723,
8480508,
9896714,
11384556,
11385407,
15142503,
18694410,
26324701,
26325525,
32421703,
32785659,
33446126,
7720368,
10288949, -- this &
10289489, -- this are not lineal
10636269,
12025931,
13836044,
15062820,
15099244,
48854728,
48871670, -- this one reverts the previous revision and it's also reverted
16486914,
40076529,
48977958,
56570397,
79356972,
91723469,
91723597,
91723639,
91723676,
91723821,
91723901,
91723948,
113901523,
119134769,
129034152,
130246463,
152027574,
152027588,
126392460,
192803526,
196383326,
199609595,
207774126,
207774132,
212604544,
221707840,
126729452,
16614661,
34037431,
55229408,
68591488, -- this &
68591574, -- this are not lineal
70120105,
71210632,
82718888,
86103888,
107355586,
110652822,
110652868,
119838967,
119838975,
120108319,
120728949,
150551206,
152202428,
189531781,
189532051,
208468137,
215206089,
215206644,
225156917,
236865153,
270924571,
278973536,
283990941,
352552677,
352552681,
361034584,
361036021,
37465649,
37467290,
69817402,
70702541,
78713053,
173561757,
188473903,
180107703,
199535909,
199536031,
204970622,
241416566,
258901532,
285458028,
377205605,
377205620,
377205627,
377205642,
377205661,
413198407,
412989918,
504683268,
575458802,
612985833,
727279019,
886744271,
911308910,
1069057572,
1108086882,
1260050274,
1307994410,
1321568819,
1429200779,
1429600535,
186041914, -- & also textual_change
458911583,
526426523,
526427132,
526427312,
543472730,
552208351,
561468227,
570710592,
577493646,
577493750,
1145080321,
376835933,
376837749,
471293564,
680691740,
941903414,
1032360058,
1032360468,
1303716837,
1308293786,
1319985443, -- this &
1320009841, -- this are not lineal
1321897747,
1476147053,
1491357074,
1491357279,
1521677394
)

select 
	r.revision_id, 
	entity_id,
	entity_label,
	value_id,
	property_id,
	change_target,
	property_label,
	old_value,
	old_value_label,
	new_value,
	new_value_label,
	'reverted_edit' as label,
	datatype
from value_change vc join revision r on vc.revision_id = r.revision_id
where vc.revision_id in (
1138665545,
69906727,
1304990286,
622505481,
1494216952,
594020844,
1362580438,
1413434391,
1316807218,
809299456,
1105689906,
1036929732,
863505939,
753171837,
790754791,
1115992814,
1725382220,
921041621,
346924285,
1481741728,
790721131,
1177628857,
616455527,
790908102,
150130476,
752435001,
62762858,
62762901,
150150656,
1004660984,
1316807209,
1316821210,
359793498,
359793498,
1316804460,
675046581,
1004656017,
1316817828
)


-- ENTITY reverted edits
select 
	r.revision_id, 
	entity_id,
	entity_label,
	value_id,
	property_id,
	change_target,
	property_label,
	old_value,
	old_value_label,
	new_value,
	new_value_label,
	'reverted_edit' as label,
	datatype
from value_change vc join revision r on vc.revision_id = r.revision_id
where vc.revision_id in (
414759982,
414759992,
1538415485,
1846185278,
1957439855,
453188211, -- this & 
453190052, -- this are not lineal
664156016,
843856539,
870544378,
594576924, -- may be a property replacement (?)
594576930, -- prop replace
621014586,
630833977,
871005100,
871005115,
106138385,
106138541,
870631306,
104480866,
374516918,
857099889,
871451545,
871687690,
159046098,
812917426,
812917440,
1581114946,
11984152,
12402888,
15339511,
14230524,
51536833,
105094587,
105095036,
143862962,
171072972,
171073642,
163498777,
207945483,
207945842,
207946187,
322587883,
871974915,
872191119,
11060711,
11538396,
24942272,
60649741,
65065815,
65999340,
66542480,
135575915,
136097036,
136896594,
137076688,
137076634
)

-- globe coord rev edit

select 
	r.revision_id, 
	entity_id,
	entity_label,
	value_id,
	property_id,
	change_target,
	property_label,
	old_value,
	old_value_label,
	new_value,
	new_value_label,
	'reverted_edit' as label,
	datatype
from value_change vc join revision r on vc.revision_id = r.revision_id
where vc.revision_id in (
413692990,
416176751,
416830570,
423193730,
13927849,
221915118,
202647161,
44090693,
381487072,
425213211,
434302019,
353375407,
383769771,
443216686,
443461556,
439313476,
416696202,
334978596,
329124520,
259347575,
208036562,
447908481,
563510336,
573714324,
574175598,
575560271,
575558467,
583707936,
591673860,
47770824,
47771051,
645287683,
134827985,
147544192,
207149374,
475531262,
647970207,
283701104,
410002806,
486732843,
486732860,
497103365,
633350857,
765513619,
775784229,
779330641,
785692767,
794155385,
803950708,
804766806,
806540681,
950390187,
951065052,
951065220,
833988465,
834215584,
834219395,
840126539,
200908715,
189532718,
497208449,
518334592,
518438885,
519611839,
519611494,
518257188,
518369720,
520930095,
87534751,
518336255,
513514384,
513719108,
513313609,
513995245,
515454343
)


-- QUANTITY

select 
	r.revision_id, 
	entity_id,
	entity_label,
	value_id,
	property_id,
	change_target,
	property_label,
	old_value,
	old_value_label,
	new_value,
	new_value_label,
	'reverted_edit' as label,
	datatype
from value_change vc join revision r on vc.revision_id = r.revision_id
where vc.revision_id in (
933890234,
901072109,
936579882,
938705073,
935588527,
874309196,
941750466,
941750435,
942092580,
765072717,
622835119,
175000366,
942157375,
884903355,
884904555,
888213605,
841989629,
839939656,
834569410,
637469705,
627636522,
623153319, -- this
623376748, -- & this are not lineal
942618103,
759315297,
944485131,
952182444,
832392183, -- this &
832392532, -- this are not lineal
832897459,
834872936, -- this &
834873037,-- this are not linela
801562435,
814953915, -- this 
814961393, -- this not lineal
840008579,
812680484,
839000220,
839000762,
844176440,
844176014,
844174243,
845534427,
845534598,
846941283,
846764461,
844788478,
847190508,
848120661,
849369512,
850895723,
830068876,
847190508,
851501471,
850707055,
853022562,
834722448,
1136644108,
861155938,
861828059,
835503198,
726020249,
708275832,
661533752,
863187812,
862892291,
867402039,
813149414,
797941937,
752027460,
667122026,
869077641,
869516017,
871333489,
871324023
)




WITH property_replacements AS (
    SELECT 
        cte1.revision_id as replaced_revision_id, 
        cte1.property_id as replaced_property_id, 
        cte1.value_id as replaced_value_id,
        cte2.revision_id as replacement_revision_id, 
        cte2.property_id as replacement_property_id, 
        cte2.value_id as replacement_value_id,
        cte1.entity_id
    FROM 
        change_timestamp_entity cte1 
        JOIN change_timestamp_entity cte2 ON 
            cte1.entity_id = cte2.entity_id AND 
            cte1.old_value = cte2.new_value
    WHERE 
        cte1.change_target = '' AND
        cte2.change_target = '' AND
        cte1.timestamp <= cte2.timestamp AND
		cte2.timestamp - cte1.timestamp <= INTERVAL '1 month' AND
        cte1.property_id != cte2.property_id AND
        cte1.action = 'DELETE' AND
        cte2.action = 'CREATE' AND 
		cte2.property_id not in (-1, -2) AND
		cte1.property_id not in (-1, -2)
)
-- Get replaced changes
SELECT 
    'replaced' as change_type,
    pr.replaced_revision_id as pair_replaced_revision_id,
    pr.replacement_revision_id as pair_replacement_revision_id,
    r.revision_id, 
    r.entity_id,
    r.entity_label,
    vc.value_id,
    vc.property_id,
    vc.change_target,
    vc.property_label,
    vc.old_value,
    vc.old_value_label,
    vc.new_value,
    vc.new_value_label,
    vc.datatype,
	'' as label
FROM property_replacements pr
JOIN revision r ON r.revision_id = pr.replaced_revision_id
JOIN value_change vc ON vc.revision_id = pr.replaced_revision_id 
    AND vc.property_id = pr.replaced_property_id 
    AND vc.value_id = pr.replaced_value_id

UNION ALL

-- Get replacement changes
SELECT 
    'replacement' as change_type,
    pr.replaced_revision_id as pair_replaced_revision_id,
    pr.replacement_revision_id as pair_replacement_revision_id,
    r.revision_id, 
    r.entity_id,
    r.entity_label,
    vc.value_id,
    vc.property_id,
    vc.change_target,
    vc.property_label,
    vc.old_value,
    vc.old_value_label,
    vc.new_value,
    vc.new_value_label,
    vc.datatype,
	'' as label
FROM property_replacements pr
JOIN revision r ON r.revision_id = pr.replacement_revision_id
JOIN value_change vc ON vc.revision_id = pr.replacement_revision_id 
    AND vc.property_id = pr.replacement_property_id 
    AND vc.value_id = pr.replacement_value_id

ORDER BY pair_replaced_revision_id, pair_replacement_revision_id, change_type
LIMIT 1000

-- PROP REPLACEMENT

SELECT *
FROM value_change
where 
(revision_id, property_id, value_id, change_target) 
(5910749, 'q77$1CB1FFA3-F3D6-4CA9-8AFB-D2FA9ED0AF95', 46, '')
(5910760, 'q77$6DEEA34E-705A-49B8-A80C-1E8064679BA2', 35, '')

(5816029, 'q16597$DA942C89-67A0-4E41-ABDC-6CD6C4393687', 17, '')
(5816030, 'q16597$175FAF73-D67A-4693-9908-9DC82B8C9AD2', 27, '')

(5816664, 'q10132$57815A40-8ABF-4C12-82A0-A7C81099EA47', 17, '')
(5816667, 'q10132$31B979EC-BCBE-43FD-B8AC-939DBA2CE126', 27, '')

(5820150, 'q11959$BE379BB3-9F06-412D-A927-CEEC5A3A2C26', 32, '')
(7602522, 'q11959$94170C20-3323-4AFF-955F-E5754F507220', 131, '')

-- They are pretty far apart so which one is it?
--
(5820240, 'q235884$6290958A-BB43-43D6-A4F6-AE8BD4DAC2D1', 83, '')
(5820318, 'q235884$4B7E7BFF-C7EB-46E6-9B42-F7825F7C4E67', 33, '')
--
(5820240, 'q235884$6290958A-BB43-43D6-A4F6-AE8BD4DAC2D1', 83, '')
(7583371, 'q235884$85C41E4F-E7FD-47EC-9E51-738BBAB2911B', 131, '')

-- looks accurate
(5820316, 'q235884$54553BAC-F553-4818-BECF-6670905D5F72', 83, '')
(5820318, 'q235884$4B7E7BFF-C7EB-46E6-9B42-F7825F7C4E67', 33, '')

(5821671, 'q1218$3C4B1449-566D-4B9B-96B1-0FC8E4885096', 36, '')
(5821883, 'q1218$665800D3-C43D-4FAA-BCBB-A9A1B274445A', 83, '')

(5822197, 'q40$77329E01-FF4C-4906-9C4B-47A6AC7CF7F1', 48, '')
(5920939, 'q40$87B0BB40-9FDA-4641-8487-5E0BA5315ABB', 85, '')

(5826317, 'q155571$F4BCDE53-F647-47D8-9552-5E2684EAA478', 60, '')
(5909675, 'q155571$9733C49B-7B32-410C-B431-CE926CAEBD5C', 31, '')

(5833859, 'q76$7B7E4C3E-D219-4848-ADFD-2A8119A8DFE9', 90, '')
(6902480, 'q76$464382F6-E090-409E-B7B9-CB913F1C2166', 69, '')

(5842391, 'q10520$CCAD46AF-925B-4782-AB1F-8D357008F35C', 55, '')
(8383631, 'q10520$8C729951-7404-4033-B139-7C167795FC54', 54, '')

(5889203, 'q54936$E5C9BE0C-BBD3-4FB5-B896-9765779800F1', 12, '')
(5889232, 'q54936$8D124BEC-0D68-4DB7-BA2C-81836C91C1E3', 32, '')

(5889203, 'q54936$E5C9BE0C-BBD3-4FB5-B896-9765779800F1', 12, '')
(7686041, 'q54936$0D74BCD8-0F14-42B1-95DA-2122CBA421AC', 131, '')

(5889275, 'q54939$58881ABE-0B6E-4EB8-983C-6559C6F706BB', 12, '')
(5889308, 'q54939$D255618F-6745-4799-8139-CB9C36E361E5', 32, '')

(5911394, 'q440000$F08F89C1-DF1F-4E35-B273-7132CAC8E113', 31, '')
(5911396, 'q440000$A23DCB09-E416-465D-ACAA-512F4C4A927B', 21, '')