-- 关键目标支持多行、多条登记
ALTER TABLE sub_projects
  MODIFY COLUMN key_goal TEXT NULL;
