-- Project info module: extend sub_projects + milestones / tasks / team_members

ALTER TABLE sub_projects
  ADD COLUMN description TEXT NULL AFTER name,
  ADD COLUMN key_goal VARCHAR(200) NULL AFTER description,
  ADD COLUMN automation_rate_goal VARCHAR(50) NULL AFTER key_goal,
  ADD COLUMN planned_start_date DATE NULL AFTER automation_rate_goal,
  ADD COLUMN planned_end_date DATE NULL AFTER planned_start_date,
  ADD COLUMN actual_start_date DATE NULL AFTER planned_end_date,
  ADD COLUMN actual_end_date DATE NULL AFTER actual_start_date;

CREATE TABLE milestones (
  id INT AUTO_INCREMENT PRIMARY KEY,
  sub_project_id INT NOT NULL,
  name VARCHAR(200) NOT NULL,
  planned_date DATE NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  description TEXT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (sub_project_id) REFERENCES sub_projects(id) ON DELETE CASCADE,
  INDEX idx_milestone_sub_project (sub_project_id),
  INDEX idx_milestone_status (status)
);

CREATE TABLE tasks (
  id INT AUTO_INCREMENT PRIMARY KEY,
  sub_project_id INT NOT NULL,
  name VARCHAR(200) NOT NULL,
  phase VARCHAR(50) NOT NULL,
  assignee VARCHAR(100) NULL,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  progress INT NOT NULL DEFAULT 0,
  sort_order INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (sub_project_id) REFERENCES sub_projects(id) ON DELETE CASCADE,
  INDEX idx_task_sub_project (sub_project_id),
  INDEX idx_task_phase (phase)
);

CREATE TABLE team_members (
  id INT AUTO_INCREMENT PRIMARY KEY,
  sub_project_id INT NOT NULL,
  name VARCHAR(100) NOT NULL,
  team_column_id INT NOT NULL,
  role VARCHAR(50) NOT NULL,
  participation VARCHAR(20) NOT NULL DEFAULT '核心成员',
  remark TEXT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (sub_project_id) REFERENCES sub_projects(id) ON DELETE CASCADE,
  FOREIGN KEY (team_column_id) REFERENCES manpower_columns(id) ON DELETE RESTRICT,
  INDEX idx_team_sub_project (sub_project_id),
  INDEX idx_team_column (team_column_id)
);
