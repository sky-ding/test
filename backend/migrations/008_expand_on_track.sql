-- 008_expand_on_track.sql
-- 将 on_track 列从 VARCHAR(10) 扩展为 VARCHAR(20)
-- 以容纳 on_track / at_risk / behind / not_started 等新值

ALTER TABLE phase_assessments
  MODIFY COLUMN on_track VARCHAR(20) NULL;
