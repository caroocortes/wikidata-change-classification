CREATE TABLE revision_sample_50 AS
SELECT *
FROM revision
WHERE file_path IN (
    'wikidatawiki-20250601-pages-meta-history1.xml-p1p154.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p155p284.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p285p366.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p367p411.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p412p461.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p462p703.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p704p1002.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p1003p1106.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p1107p1209.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p1210p1330.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p1331p1461.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p1462p2110.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p2111p3493.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p3494p5244.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p5245p7050.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p7051p8649.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p8650p10215.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p10216p11794.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p11795p13802.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p13803p15595.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p15596p17970.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p17971p21200.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p21201p25122.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p25123p28276.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p28277p30529.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p30530p33924.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p33925p37667.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p37668p40447.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p40448p43436.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p43437p45326.bz2',
    'wikidatawiki-20250601-pages-meta-history1.xml-p45327p47532.bz2',
'wikidatawiki-20250601-pages-meta-history1.xml-p47533p50184.bz2',
'wikidatawiki-20250601-pages-meta-history1.xml-p50185p54071.bz2',
'wikidatawiki-20250601-pages-meta-history1.xml-p54072p58467.bz2',
'wikidatawiki-20250601-pages-meta-history1.xml-p58468p61949.bz2',
'wikidatawiki-20250601-pages-meta-history1.xml-p61950p65142.bz2',
'wikidatawiki-20250601-pages-meta-history1.xml-p65143p69897.bz2',
'wikidatawiki-20250601-pages-meta-history1.xml-p69898p74952.bz2',
'wikidatawiki-20250601-pages-meta-history1.xml-p74953p79351.bz2',
'wikidatawiki-20250601-pages-meta-history1.xml-p79352p82609.bz2',
'wikidatawiki-20250601-pages-meta-history1.xml-p82610p85791.bz2',
'wikidatawiki-20250601-pages-meta-history1.xml-p85792p92981.bz2',
'wikidatawiki-20250601-pages-meta-history1.xml-p92982p100230.bz2',
'wikidatawiki-20250601-pages-meta-history1.xml-p100231p106805.bz2',
'wikidatawiki-20250601-pages-meta-history1.xml-p106806p111631.bz2',
'wikidatawiki-20250601-pages-meta-history1.xml-p111632p118889.bz2',
'wikidatawiki-20250601-pages-meta-history1.xml-p118890p125389.bz2',
'wikidatawiki-20250601-pages-meta-history1.xml-p125390p130847.bz2',
'wikidatawiki-20250601-pages-meta-history1.xml-p130848p134087.bz2',
'wikidatawiki-20250601-pages-meta-history1.xml-p134088p138225.bz2'
);
ALTER TABLE revision_sample_50
ADD PRIMARY KEY (revision_id);

CREATE TABLE value_change_sample_50 AS
SELECT * FROM value_change
WHERE revision_id IN (SELECT revision_id FROM revision_sample_50);

ALTER TABLE value_change_sample_50
ADD PRIMARY KEY (revision_id, property_id, value_id, change_target),
ADD FOREIGN KEY (revision_id) REFERENCES revision_sample_50(revision_id);

CREATE TABLE value_change_metadata_sample_50 AS
SELECT cm.*
FROM value_change_metadata cm
JOIN value_change_sample_50 c
  ON cm.revision_id = c.revision_id
 AND cm.property_id = c.property_id
 AND cm.value_id = c.value_id
 AND cm.change_target = c.change_target;

ALTER TABLE value_change_metadata_sample_50
ADD PRIMARY KEY (revision_id, property_id, value_id, change_target, change_metadata),
ADD FOREIGN KEY (revision_id, property_id, value_id, change_target)
    REFERENCES value_change_sample_50(revision_id, property_id, value_id, change_target);

CREATE TABLE reference_change_sample_50 AS
SELECT * FROM reference_change
WHERE revision_id IN (SELECT revision_id FROM revision_sample_50);

ALTER TABLE reference_change_sample_50
ADD PRIMARY KEY (revision_id, property_id, value_id, change_target, ref_property_id, ref_hash, value_hash),
ADD FOREIGN KEY (revision_id) REFERENCES revision_sample_50(revision_id);

CREATE TABLE qualifier_change_sample_50 AS
SELECT * FROM qualifier_change
WHERE revision_id IN (SELECT revision_id FROM revision_sample_50);

ALTER TABLE qualifier_change_sample_50
ADD PRIMARY KEY (revision_id, property_id, value_id, change_target, qual_property_id, value_hash),
ADD FOREIGN KEY (revision_id) REFERENCES revision_sample_50(revision_id);
