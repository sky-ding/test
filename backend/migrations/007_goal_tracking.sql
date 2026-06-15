-- 007_goal_tracking.sql
-- 目标跟踪功能:新增 goals / goal_links 两张表
-- 依赖: 001_relational_schema.sql(sub_projects 表)+ 004(milestones / tasks 表)
--
-- 用法:
--   USE `ipd-pmo`;
--   SOURCE /path/to/007_goal_tracking.sql;

-- ============================================================
-- 1. 目标定义表
-- ============================================================
CREATE TABLE IF NOT EXISTS goals (
  id INT AUTO_INCREMENT PRIMARY KEY,
  sub_project_id INT NOT NULL,
  name VARCHAR(200) NOT NULL,
  metric_unit VARCHAR(50) NULL,
  initial_target VARCHAR(200) NOT NULL,
  mid_term_target VARCHAR(200) NULL,
  current_value VARCHAR(200) NULL,
  direction VARCHAR(20) NOT NULL DEFAULT 'higher_better',
  sort_order INT NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  FOREIGN KEY (sub_project_id) REFERENCES sub_projects(id) ON DELETE CASCADE,
  INDEX idx_goals_sub_project (sub_project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 2. 目标-里程碑/任务关联表
-- ============================================================
CREATE TABLE IF NOT EXISTS goal_links (
  id INT AUTO_INCREMENT PRIMARY KEY,
  goal_id INT NOT NULL,
  target_type VARCHAR(20) NOT NULL,
  target_id INT NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE CASCADE,
  INDEX idx_goal_links_goal (goal_id),
  UNIQUE INDEX idx_goal_links_target (goal_id, target_type, target_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 3. 验证
-- ============================================================
SHOW TABLES LIKE 'goals';
SHOW TABLES LIKE 'goal_links';
