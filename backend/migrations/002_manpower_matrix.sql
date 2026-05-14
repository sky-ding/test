-- 人力复合表：表头（一级分组 + 二级列）+ 单元格事实表（见 docs/项目管理登记系统数据库设计文档.md）
-- 约定（评审基线）：
--   * API：GET/PUT /api/v1/manpower-allocations?year=&period= ，载荷含 dept_groups + cells
--   * 列 ID：manpower_columns.id 为单元格稳定外键；按年隔离（year 与 sub_projects.year 一致）
--   * allocation：DECIMAL(6,2)，与 ORM Numeric(6,2) 对齐
-- MySQL 8+；风格与 001_relational_schema.sql 一致（TIMESTAMP、utf8mb4）。

CREATE TABLE IF NOT EXISTS `manpower_department_groups` (
    `id`         INT AUTO_INCREMENT PRIMARY KEY,
    `year`       SMALLINT      NOT NULL COMMENT '所属年份',
    `name`       VARCHAR(100)  NOT NULL COMMENT '一级部门分组名称',
    `sort_order` INT           DEFAULT 0 COMMENT '展示顺序',
    `created_at` TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_manpower_group_year_name` (`year`, `name`),
    KEY `idx_manpower_group_year` (`year`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='人力表一级部门表头';

CREATE TABLE IF NOT EXISTS `manpower_columns` (
    `id`         INT AUTO_INCREMENT PRIMARY KEY,
    `group_id`   INT           NOT NULL COMMENT '所属一级部门分组',
    `year`       SMALLINT      NOT NULL COMMENT '所属年份（冗余）',
    `name`       VARCHAR(100)  NOT NULL COMMENT '二级部门/角色/职能列名称',
    `sort_order` INT           DEFAULT 0 COMMENT '展示顺序',
    `created_at` TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_manpower_column_group_name` (`group_id`, `name`),
    KEY `idx_manpower_column_year` (`year`),
    KEY `idx_manpower_column_group` (`group_id`),
    CONSTRAINT `fk_manpower_column_group` FOREIGN KEY (`group_id`) REFERENCES `manpower_department_groups`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='人力表二级部门列';

CREATE TABLE IF NOT EXISTS `manpower_cells` (
    `id`             INT AUTO_INCREMENT PRIMARY KEY,
    `sub_project_id` INT           NOT NULL COMMENT '子项目 ID',
    `period`         VARCHAR(7)    NOT NULL COMMENT 'YYYY-MM',
    `column_id`      INT           NOT NULL COMMENT '人力列 ID',
    `allocation`     DECIMAL(6,2)  NOT NULL DEFAULT 0.00 COMMENT '人力投入值',
    `created_at`     TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    `updated_at`     TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_manpower_cell` (`sub_project_id`, `period`, `column_id`),
    KEY `idx_manpower_cell_period` (`period`),
    KEY `idx_manpower_cell_column` (`column_id`),
    CONSTRAINT `fk_manpower_cell_project` FOREIGN KEY (`sub_project_id`) REFERENCES `sub_projects`(`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_manpower_cell_column` FOREIGN KEY (`column_id`) REFERENCES `manpower_columns`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='人力单元格事实表';
