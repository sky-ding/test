-- 项目信息登记新增：项目负责人、项目经理
ALTER TABLE sub_projects
  ADD COLUMN project_lead VARCHAR(100) NULL COMMENT '项目负责人',
  ADD COLUMN project_manager VARCHAR(100) NULL COMMENT '项目经理';
