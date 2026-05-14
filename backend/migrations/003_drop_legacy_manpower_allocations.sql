-- 全面数据库改造：字段约束对齐与人力旧行存表停用清理。
-- 仅在已确认不再需要旧 manpower_allocations 数据或已完成备份/迁移后执行。

ALTER TABLE `phase_assessments`
    MODIFY COLUMN `on_track` VARCHAR(10) COMMENT '是否符合计划';

ALTER TABLE `project_risks`
    MODIFY COLUMN `risk_category` VARCHAR(50) NOT NULL COMMENT '风险类别',
    MODIFY COLUMN `risk_source` VARCHAR(50) NOT NULL COMMENT '风险来源',
    MODIFY COLUMN `level` VARCHAR(10) NOT NULL DEFAULT '中' COMMENT '级别',
    MODIFY COLUMN `assignee` VARCHAR(100) NOT NULL COMMENT '跟进人',
    MODIFY COLUMN `status` VARCHAR(20) NOT NULL DEFAULT 'Open' COMMENT 'Open/Hold/Close';

DROP TABLE IF EXISTS `manpower_allocations`;
