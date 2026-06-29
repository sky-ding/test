-- 010_merge_milestones_into_tasks.sql
-- 合并里程碑到任务表：里程碑作为任务的特殊标记
-- 
-- 用法:
--   USE `ipd-pmo`;
--   SOURCE /path/to/010_merge_milestones_into_tasks.sql;

-- ============================================================
-- 1. tasks 表增加 is_milestone 和 parent_id 字段
-- ============================================================
ALTER TABLE tasks
  ADD COLUMN is_milestone TINYINT(1) NOT NULL DEFAULT 0 AFTER progress,
  ADD COLUMN parent_id INT NULL AFTER is_milestone,
  ADD INDEX idx_task_parent (parent_id),
  ADD CONSTRAINT fk_task_parent FOREIGN KEY (parent_id) REFERENCES tasks(id) ON DELETE SET NULL;

-- ============================================================
-- 2. 迁移 milestones 数据到 tasks
--    planned_date → end_date（里程碑的"达成日期"）
--    start_date 设为与 end_date 相同
-- ============================================================
INSERT INTO tasks (sub_project_id, name, status, assignee, start_date, end_date, progress, is_milestone, sort_order, created_at, updated_at)
SELECT 
    sub_project_id,
    name,
    status,
    NULL AS assignee,
    planned_date AS start_date,
    planned_date AS end_date,
    CASE WHEN status = 'completed' THEN 100 ELSE 0 END AS progress,
    1 AS is_milestone,
    sort_order,
    created_at,
    updated_at
FROM milestones;

-- ============================================================
-- 3. 更新 goal_links: 把 target_type='milestone' 的记录指向新 task ID
--    策略：因为 milestones 数据已迁移到 tasks，且新 task 的 (sub_project_id, name, created_at) 
--    与旧 milestone 一致，通过 sub_project_id + name + created_at 匹配
-- ============================================================
UPDATE goal_links gl
JOIN milestones m ON gl.target_type = 'milestone' AND gl.target_id = m.id
JOIN tasks t ON t.sub_project_id = m.sub_project_id AND t.name = m.name AND t.created_at = m.created_at AND t.is_milestone = 1
SET gl.target_type = 'task', gl.target_id = t.id;

-- ============================================================
-- 4. 删除 milestones 表
-- ============================================================
DROP TABLE IF EXISTS milestones;

-- ============================================================
-- 5. 验证
-- ============================================================
SELECT 'tasks with is_milestone=1' AS check_name, COUNT(*) AS cnt FROM tasks WHERE is_milestone = 1;
SELECT 'goal_links target_type distribution' AS check_name, target_type, COUNT(*) AS cnt FROM goal_links GROUP BY target_type;
