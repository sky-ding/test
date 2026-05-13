-- 项目管理工具：人力登记复合表结构升级（MySQL 8+）
-- 旧表 manpower_allocations 使用 department/role 字符串直接表达列，无法保存前端复合表的列定义与顺序。
-- 新结构：
--   manpower_department_groups：一级部门分组（复合表头第一层）
--   manpower_columns：二级部门/人力列（复合表头第二层）
--   manpower_cells：按 子项目 × 月份 × 部门列 存储数值

CREATE TABLE IF NOT EXISTS `manpower_department_groups` (
    `id`         INT AUTO_INCREMENT PRIMARY KEY,
    `year`       SMALLINT      NOT NULL COMMENT '所属年份',
    `name`       VARCHAR(100)  NOT NULL COMMENT '一级部门分组/复合表头第一层',
    `sort_order` INT           DEFAULT 0,
    `created_at` TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_mp_group_year_name` (`year`, `name`),
    KEY `idx_year` (`year`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='人力登记部门分组（列头第一层）';

CREATE TABLE IF NOT EXISTS `manpower_columns` (
    `id`         INT AUTO_INCREMENT PRIMARY KEY,
    `group_id`   INT           NOT NULL COMMENT '所属部门分组',
    `year`       SMALLINT      NOT NULL COMMENT '所属年份（冗余，便于查询）',
    `name`       VARCHAR(100)  NOT NULL COMMENT '二级部门/人力列名（复合表头第二层）',
    `sort_order` INT           DEFAULT 0,
    `created_at` TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_mp_column_group_name` (`group_id`, `name`),
    KEY `idx_group` (`group_id`),
    KEY `idx_year` (`year`),
    CONSTRAINT `fk_mp_column_group` FOREIGN KEY (`group_id`) REFERENCES `manpower_department_groups`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='人力登记部门列定义（列头第二层）';

CREATE TABLE IF NOT EXISTS `manpower_cells` (
    `id`             INT AUTO_INCREMENT PRIMARY KEY,
    `sub_project_id` INT           NOT NULL COMMENT '子项目 ID（复合表左侧行）',
    `period`         VARCHAR(7)    NOT NULL COMMENT 'YYYY-MM',
    `column_id`      INT           NOT NULL COMMENT '部门列 ID（复合表上方列）',
    `allocation`     DECIMAL(5,2)  NOT NULL DEFAULT 0.00 COMMENT '投入人力',
    `created_at`     TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    `updated_at`     TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_mp_cell_project_period_column` (`sub_project_id`, `period`, `column_id`),
    KEY `idx_period` (`period`),
    KEY `idx_column` (`column_id`),
    CONSTRAINT `fk_mp_cell_project` FOREIGN KEY (`sub_project_id`) REFERENCES `sub_projects`(`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_mp_cell_column` FOREIGN KEY (`column_id`) REFERENCES `manpower_columns`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='人力登记月度单元格事实表';

-- 可选：把旧 manpower_allocations 中已有数据迁入新结构。
-- 适用于旧表存在且 sub_projects.year 可用的线上库；迁移完成并验证后，旧表可由 DBA 备份后删除。
INSERT IGNORE INTO `manpower_department_groups` (`year`, `name`, `sort_order`)
SELECT
    t.`year`,
    t.`department`,
    ROW_NUMBER() OVER (PARTITION BY t.`year` ORDER BY t.`department`) - 1 AS `sort_order`
FROM (
    SELECT DISTINCT sp.`year`, ma.`department`
    FROM `manpower_allocations` ma
    JOIN `sub_projects` sp ON sp.`id` = ma.`sub_project_id`
    WHERE ma.`department` IS NOT NULL AND ma.`department` <> ''
) t;

INSERT IGNORE INTO `manpower_columns` (`group_id`, `year`, `name`, `sort_order`)
SELECT
    g.`id`,
    t.`year`,
    t.`role`,
    ROW_NUMBER() OVER (PARTITION BY t.`year`, t.`department` ORDER BY t.`role`) - 1 AS `sort_order`
FROM (
    SELECT DISTINCT sp.`year`, ma.`department`, ma.`role`
    FROM `manpower_allocations` ma
    JOIN `sub_projects` sp ON sp.`id` = ma.`sub_project_id`
    WHERE ma.`department` IS NOT NULL AND ma.`department` <> ''
      AND ma.`role` IS NOT NULL AND ma.`role` <> ''
) t
JOIN `manpower_department_groups` g
  ON g.`year` = t.`year` AND g.`name` = t.`department`;

INSERT IGNORE INTO `manpower_cells` (`sub_project_id`, `period`, `column_id`, `allocation`)
SELECT
    ma.`sub_project_id`,
    ma.`period`,
    c.`id`,
    ma.`allocation`
FROM `manpower_allocations` ma
JOIN `sub_projects` sp ON sp.`id` = ma.`sub_project_id`
JOIN `manpower_department_groups` g
  ON g.`year` = sp.`year` AND g.`name` = ma.`department`
JOIN `manpower_columns` c
  ON c.`group_id` = g.`id` AND c.`name` = ma.`role`;
