-- 项目管理工具：规范化表（与 app.models_relational 一致；MySQL 8+）
-- 应用亦通过 SQLAlchemy create_all 建表；此文件供 DBA 审阅与手工执行。

CREATE TABLE IF NOT EXISTS `programs` (
    `id`         INT AUTO_INCREMENT PRIMARY KEY,
    `year`       SMALLINT      NOT NULL COMMENT '所属年份',
    `name`       VARCHAR(100)  NOT NULL COMMENT '项目集名称',
    `sort_order` INT           DEFAULT 0,
    `created_at` TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_year_name` (`year`, `name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='项目集（按年隔离）';

CREATE TABLE IF NOT EXISTS `sub_programs` (
    `id`         INT AUTO_INCREMENT PRIMARY KEY,
    `program_id` INT           NOT NULL COMMENT '所属项目集',
    `year`       SMALLINT      NOT NULL COMMENT '所属年份（冗余）',
    `name`       VARCHAR(100)  NOT NULL COMMENT '子项目集名称',
    `sort_order` INT           DEFAULT 0,
    `created_at` TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_prog_year_name` (`program_id`, `year`, `name`),
    KEY `idx_year` (`year`),
    CONSTRAINT `fk_sp_program` FOREIGN KEY (`program_id`) REFERENCES `programs`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='子项目集';

CREATE TABLE IF NOT EXISTS `sub_projects` (
    `id`             INT AUTO_INCREMENT PRIMARY KEY,
    `sub_program_id` INT           NOT NULL COMMENT '所属子项目集',
    `year`           SMALLINT      NOT NULL COMMENT '所属年份（冗余）',
    `name`           VARCHAR(200)  NOT NULL COMMENT '子项目名称',
    `status`         VARCHAR(20)   DEFAULT 'active' COMMENT 'active/archived',
    `sort_order`     INT           DEFAULT 0,
    `created_at`     TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    `updated_at`     TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_spg_year_name` (`sub_program_id`, `year`, `name`),
    KEY `idx_year` (`year`),
    CONSTRAINT `fk_spj_sub_program` FOREIGN KEY (`sub_program_id`) REFERENCES `sub_programs`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='子项目';

CREATE TABLE IF NOT EXISTS `phase_assessments` (
    `id`                 INT AUTO_INCREMENT PRIMARY KEY,
    `sub_project_id`     INT           NOT NULL COMMENT '子项目 ID',
    `period`             VARCHAR(7)    NOT NULL COMMENT 'YYYY-MM',
    `delivery_target`    TEXT          COMMENT '阶段交付目标',
    `on_track`           VARCHAR(10)   COMMENT '是否符合计划',
    `actual_delivery`    TEXT          COMMENT '实际交付评估',
    `execution_analysis` TEXT          COMMENT '执行过程分析',
    `problem_analysis`   TEXT          COMMENT '问题分析',
    `improvement_plan`   TEXT          COMMENT '改进计划',
    `created_at`         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at`         TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_project_period` (`sub_project_id`, `period`),
    KEY `idx_period` (`period`),
    CONSTRAINT `fk_pa_project` FOREIGN KEY (`sub_project_id`) REFERENCES `sub_projects`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='项目阶段状态（月度）';

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

CREATE TABLE IF NOT EXISTS `project_risks` (
    `id`              INT AUTO_INCREMENT PRIMARY KEY,
    `sub_project_id`  INT           NOT NULL COMMENT '关联子项目',
    `risk_category`   VARCHAR(50)   NOT NULL COMMENT '风险类别',
    `risk_source`     VARCHAR(50)   NOT NULL COMMENT '风险来源',
    `description`     TEXT          NOT NULL COMMENT '问题与影响',
    `solution`        TEXT          COMMENT '解决方案',
    `level`           VARCHAR(10)   NOT NULL DEFAULT '中' COMMENT '级别',
    `assignee`        VARCHAR(100)  NOT NULL COMMENT '跟进人',
    `resolution_date` DATE          COMMENT '计划解决日期',
    `status`          VARCHAR(20)   NOT NULL DEFAULT 'Open' COMMENT 'Open/Hold/Close',
    `closed_at`       TIMESTAMP     NULL COMMENT '关闭时间',
    `created_at`      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at`      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY `idx_project` (`sub_project_id`),
    KEY `idx_status` (`status`),
    CONSTRAINT `fk_risk_project` FOREIGN KEY (`sub_project_id`) REFERENCES `sub_projects`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='项目风险';

CREATE TABLE IF NOT EXISTS `users` (
    `id`               INT AUTO_INCREMENT PRIMARY KEY,
    `username`         VARCHAR(64)  NOT NULL COMMENT '登录名',
    `password_hash`    VARCHAR(255) NULL COMMENT '密码哈希',
    `role`             VARCHAR(16)  NOT NULL DEFAULT 'viewer' COMMENT 'admin/viewer',
    `is_active`        TINYINT(1)   NOT NULL DEFAULT 1,
    `external_subject` VARCHAR(256) NULL,
    `auth_source`      VARCHAR(32)  NOT NULL DEFAULT 'local',
    `created_at`       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `ix_users_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='登录用户';
