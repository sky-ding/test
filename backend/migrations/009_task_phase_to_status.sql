-- 009: tasks 表 phase 字段改为 status（对齐里程碑 status 可选值）
-- phase 是 VARCHAR(50)，status 用 VARCHAR(20) 与 milestones.status 一致

ALTER TABLE tasks
  CHANGE COLUMN phase status VARCHAR(20) NOT NULL DEFAULT 'pending';

-- 更新旧数据的 phase 值到对应的 status
-- 需求与设计 → pending, 开发实施 → in-progress, 测试验证 → pending, 部署上线 → pending
-- 保守映射：只有 开发实施 → in-progress，其余统一 → pending（待人工确认）
UPDATE tasks SET status = 'in-progress' WHERE status = '开发实施';
UPDATE tasks SET status = 'pending'
  WHERE status IN ('需求与设计', '测试验证', '部署上线');

-- 更新索引名
ALTER TABLE tasks
  DROP INDEX idx_task_phase,
  ADD INDEX idx_task_status (status);
