-- Member-level monthly allocations; rollup to manpower_cells from project info.

CREATE TABLE team_member_allocations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  team_member_id INT NOT NULL,
  period VARCHAR(7) NOT NULL COMMENT 'YYYY-MM',
  allocation DECIMAL(6,2) NOT NULL DEFAULT 0.00 COMMENT '人月',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_team_member_period (team_member_id, period),
  INDEX idx_tma_period (period),
  FOREIGN KEY (team_member_id) REFERENCES team_members(id) ON DELETE CASCADE
);
