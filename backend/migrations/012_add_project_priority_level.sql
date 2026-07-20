-- 项目信息登记新增：项目优先级别
ALTER TABLE sub_projects
  ADD COLUMN priority_level VARCHAR(20) NOT NULL DEFAULT '第三优先级' COMMENT '项目优先级：第一优先级/第二优先级/第三优先级';
