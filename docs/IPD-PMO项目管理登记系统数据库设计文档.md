# IPD-PMO 项目管理登记系统数据库设计文档

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | IPD-PMO 项目管理登记系统数据库设计文档 |
| 适用系统 | ipd-pmo / ProjectGuard |
| 适用模块 | 项目阶段状态、部门项目人力登记、项目风险登记、用户与权限管理 |
| 设计重点 | 部门项目人力登记复合表的数据建模 |
| 文档状态 | 评审稿 |
| 编写目的 | 供研发、DBA、测试同学评审数据库设计及后续实现参考 |

---

## 2. 背景说明

IPD-PMO 项目管理登记系统当前主要包含以下功能模块：

1. 项目阶段状态登记
2. 部门项目人力登记
3. 项目风险登记
4. 用户与权限管理

其中「部门项目人力登记」页面是一个典型的复合表结构：

- 左侧为项目结构：
  - 项目集
  - 子项目集
  - 子项目
- 上方为部门结构：
  - 一级部门分组
  - 二级部门 / 角色 / 职能列
- 中间单元格为：
  - 某年月
  - 某子项目
  - 某部门列
  - 对应的人力投入值
- 右侧包含：
  - 小计
  - 人力占比

因此，该页面不能简单按普通列表表单建模，也不适合将前端表格直接做成数据库宽表。

---

## 3. 当前问题

### 3.1 前端保存后刷新数据丢失

用户在前端编辑人力数据并保存后，刷新页面数据没有被正确还原。

主要原因可能包括：

- 前端单元格与数据库记录之间缺少稳定映射关系；
- 数据库只记录了 `department` / `role` 字符串，没有保存完整的列定义；
- 前端无法根据数据库数据还原复合表头结构。

### 3.2 DBA 在数据库中修改的数据前端无法正常展示

DBA 直接在数据库中修改人力数据后，前端仍无法正确展示。

主要原因是：

- 数据库没有独立保存部门表头结构；
- 前端不知道数据库中有哪些一级部门、二级部门列；
- 数据库中的人力记录无法稳定映射到前端具体列；
- 列顺序、列归属、列 ID 等信息缺失。

### 3.3 原 `manpower_allocations` 设计不完整

当前类似如下结构：

```text
manpower_allocations
- id
- sub_project_id
- period
- department
- role
- allocation
```

该结构可以表达：

```text
某月、某项目、某部门、某角色的人力值
```

但无法完整表达前端复合表结构：

```text
项目结构 × 部门分组 × 部门列 × 月份 = 人力单元格
```

尤其缺少：

- 一级部门分组定义；
- 二级部门列定义；
- 列顺序；
- 列 ID；
- 部门名称变更后的历史数据稳定性。

因此建议重新设计人力登记相关表结构。

---

## 4. 设计目标

本次数据库设计目标如下：

1. 支持前端复合表结构的完整还原；
2. 支持 DBA 直接维护数据库后，前端可以正确展示；
3. 支持按年月查询人力数据；
4. 支持月度录入、季度汇总、年度汇总；
5. 避免存储小计、人力占比等可计算字段；
6. 保证项目结构、部门列结构、人力单元格数据之间关系清晰；
7. 支持未来部门列调整、排序、重命名；
8. 保持项目阶段状态、风险登记、人力登记之间的项目主数据一致。

---

## 5. 总体设计原则

### 5.1 项目结构单独建模

项目结构作为业务主数据，不应散落在人力表、风险表、阶段表中。

统一使用：

```text
programs
sub_programs
sub_projects
```

表达：

```text
项目集 -> 子项目集 -> 子项目
```

### 5.2 人力表头结构单独建模

部门项目人力登记的表头是可维护的业务数据，应独立存储。

使用：

```text
manpower_department_groups
manpower_columns
```

表达：

```text
一级部门分组 -> 二级部门列
```

### 5.3 人力数值按单元格存储

每个人力数字本质上是一个事实值：

```text
某年月 + 某子项目 + 某部门列 = 人力投入
```

使用：

```text
manpower_cells
```

存储单元格事实数据。

### 5.4 汇总字段不入库

以下字段不建议入库：

- 小计
- 人力占比
- 季度汇总
- 年度汇总

原因：

- 这些字段可以由基础数据实时计算；
- 入库后容易产生数据不一致；
- 后续修改单元格后需要同步更新冗余字段，增加复杂度。

---

## 6. 核心实体关系

整体关系如下：

```text
programs
  └── sub_programs
        └── sub_projects
              ├── phase_assessments
              ├── project_risks
              └── manpower_cells
                       └── manpower_columns
                              └── manpower_department_groups
```

业务含义：

- 一个项目集下有多个子项目集；
- 一个子项目集下有多个子项目；
- 一个子项目可以有多个月度阶段状态；
- 一个子项目可以有多条风险记录；
- 一个子项目在某个月、某个人力列上有一个人力值；
- 一个二级人力列属于一个一级部门分组。

---

## 7. 数据表设计

### 7.1 项目集表：`programs`

#### 表说明

用于存储项目集，即前端左侧项目结构中的一级分类。

示例：

```text
稳定性
业务提效
基础设施稳定性
```

#### 字段设计

| 字段名 | 类型 | 是否必填 | 说明 |
|---|---|---:|---|
| id | INT | 是 | 主键，自增 |
| year | SMALLINT | 是 | 所属年份 |
| name | VARCHAR(100) | 是 | 项目集名称 |
| sort_order | INT | 否 | 展示顺序 |
| created_at | DATETIME | 是 | 创建时间 |
| updated_at | DATETIME | 是 | 更新时间 |

#### 约束建议

```sql
UNIQUE(year, name)
```

含义：同一年份下，项目集名称不能重复。

---

### 7.2 子项目集表：`sub_programs`

#### 表说明

用于存储项目集下的子项目集。

示例：

```text
容灾
业务稳定性
基础设施稳定性
```

#### 字段设计

| 字段名 | 类型 | 是否必填 | 说明 |
|---|---|---:|---|
| id | INT | 是 | 主键，自增 |
| program_id | INT | 是 | 所属项目集 ID |
| year | SMALLINT | 是 | 所属年份，冗余字段，便于查询 |
| name | VARCHAR(100) | 是 | 子项目集名称 |
| sort_order | INT | 否 | 展示顺序 |
| created_at | DATETIME | 是 | 创建时间 |
| updated_at | DATETIME | 是 | 更新时间 |

#### 约束建议

```sql
UNIQUE(program_id, year, name)
```

---

### 7.3 子项目表：`sub_projects`

#### 表说明

用于存储具体子项目。

这是阶段状态、人力登记、风险登记共同引用的核心项目实体。

示例：

```text
大数据容灾
企业IT容灾
站外广告容灾
稳定性演练体系建设1.0
```

#### 字段设计

| 字段名 | 类型 | 是否必填 | 说明 |
|---|---|---:|---|
| id | INT | 是 | 主键，自增 |
| sub_program_id | INT | 是 | 所属子项目集 ID |
| year | SMALLINT | 是 | 所属年份 |
| name | VARCHAR(200) | 是 | 子项目名称 |
| status | VARCHAR(20) | 否 | 状态，如 `active`、`archived` |
| sort_order | INT | 否 | 展示顺序 |
| created_at | DATETIME | 是 | 创建时间 |
| updated_at | DATETIME | 是 | 更新时间 |

#### 约束建议

```sql
UNIQUE(sub_program_id, year, name)
```

---

## 8. 部门项目人力登记表设计

这是本次设计的重点。

### 8.1 一级部门分组表：`manpower_department_groups`

#### 表说明

用于存储人力登记表的复合表头第一层。

例如截图中可能出现：

```text
平台与架构
运维中心
企业服务与生产运营
数据智能
```

或原型中的：

```text
技术部
市场部
```

#### 字段设计

| 字段名 | 类型 | 是否必填 | 说明 |
|---|---|---:|---|
| id | INT | 是 | 主键，自增 |
| year | SMALLINT | 是 | 所属年份 |
| name | VARCHAR(100) | 是 | 一级部门分组名称 |
| sort_order | INT | 否 | 前端展示顺序 |
| created_at | DATETIME | 是 | 创建时间 |
| updated_at | DATETIME | 是 | 更新时间 |

#### 约束建议

```sql
UNIQUE(year, name)
```

#### 示例数据

| id | year | name | sort_order |
|---:|---:|---|---:|
| 1 | 2026 | 平台与架构 | 1 |
| 2 | 2026 | 运维中心 | 2 |
| 3 | 2026 | 数据智能 | 3 |

---

### 8.2 二级部门列定义表：`manpower_columns`

#### 表说明

用于存储人力登记表的复合表头第二层。

例如：

```text
平台与架构
  ├── 大模型
  ├── 架构
  ├── 产品
  ├── 前端开发
  └── 云平台

运维中心
  ├── SRE
  ├── DBA
  └── 监控中心
```

#### 字段设计

| 字段名 | 类型 | 是否必填 | 说明 |
|---|---|---:|---|
| id | INT | 是 | 主键，自增 |
| group_id | INT | 是 | 所属一级部门分组 ID |
| year | SMALLINT | 是 | 所属年份，冗余字段，便于查询 |
| name | VARCHAR(100) | 是 | 二级部门、角色或职能列名称 |
| sort_order | INT | 否 | 当前分组下的展示顺序 |
| created_at | DATETIME | 是 | 创建时间 |
| updated_at | DATETIME | 是 | 更新时间 |

#### 约束建议

```sql
UNIQUE(group_id, name)
```

#### 示例数据

| id | group_id | year | name | sort_order |
|---:|---:|---:|---|---:|
| 1 | 1 | 2026 | 大模型 | 1 |
| 2 | 1 | 2026 | 架构 | 2 |
| 3 | 1 | 2026 | 产品 | 3 |
| 4 | 1 | 2026 | 前端开发 | 4 |
| 5 | 2 | 2026 | SRE | 1 |
| 6 | 2 | 2026 | DBA | 2 |

---

### 8.3 人力单元格表：`manpower_cells`

#### 表说明

用于存储人力登记表中的实际数值。

一条记录表示：

```text
某个月，某个子项目，在某个人力列上的人力投入。
```

例如：

```text
2026-01，大数据容灾，平台与架构 / 大模型，1.00
```

#### 字段设计

| 字段名 | 类型 | 是否必填 | 说明 |
|---|---|---:|---|
| id | INT | 是 | 主键，自增 |
| sub_project_id | INT | 是 | 子项目 ID |
| period | VARCHAR(7) | 是 | 年月，格式 `YYYY-MM` |
| column_id | INT | 是 | 人力列 ID |
| allocation | DECIMAL(6,2) | 是 | 人力投入值 |
| created_at | DATETIME | 是 | 创建时间 |
| updated_at | DATETIME | 是 | 更新时间 |

#### 约束建议

```sql
UNIQUE(sub_project_id, period, column_id)
```

含义：同一个子项目、同一个月份、同一个人力列，只能有一个人力值。

#### 示例数据

| id | sub_project_id | period | column_id | allocation |
|---:|---:|---|---:|---:|
| 1 | 101 | 2026-01 | 1 | 1.00 |
| 2 | 101 | 2026-01 | 2 | 0.50 |
| 3 | 102 | 2026-01 | 5 | 2.00 |

---

## 9. 项目阶段状态表设计

### 9.1 表名：`phase_assessments`

#### 表说明

用于存储某子项目在某年月的阶段状态信息。

阶段状态不是矩阵数据，而是：

```text
某个月 + 某个子项目 + 一组文本字段
```

#### 字段设计

| 字段名 | 类型 | 是否必填 | 说明 |
|---|---|---:|---|
| id | INT | 是 | 主键，自增 |
| sub_project_id | INT | 是 | 子项目 ID |
| period | VARCHAR(7) | 是 | 年月，格式 `YYYY-MM` |
| delivery_target | TEXT | 否 | 阶段交付目标 |
| on_track | VARCHAR(10) | 否 | 是否符合计划 |
| actual_delivery | TEXT | 否 | 实际交付评估 |
| execution_analysis | TEXT | 否 | 执行过程分析 |
| problem_analysis | TEXT | 否 | 问题分析 |
| improvement_plan | TEXT | 否 | 改进计划 |
| created_at | DATETIME | 是 | 创建时间 |
| updated_at | DATETIME | 是 | 更新时间 |

#### 约束建议

```sql
UNIQUE(sub_project_id, period)
```

---

## 10. 项目风险表设计

### 10.1 表名：`project_risks`

#### 表说明

用于存储项目风险登记信息。

风险登记是列表型数据，不是复合矩阵，一条风险对应数据库一行。

#### 字段设计

| 字段名 | 类型 | 是否必填 | 说明 |
|---|---|---:|---|
| id | INT | 是 | 主键，自增 |
| sub_project_id | INT | 是 | 关联子项目 ID |
| risk_category | VARCHAR(50) | 是 | 风险类别 |
| risk_source | VARCHAR(50) | 是 | 风险来源 |
| description | TEXT | 是 | 问题与影响 |
| solution | TEXT | 否 | 解决方案 |
| level | VARCHAR(10) | 是 | 风险等级 |
| assignee | VARCHAR(100) | 是 | 跟进人 |
| resolution_date | DATE | 否 | 计划解决日期 |
| status | VARCHAR(20) | 是 | 状态，如 Open / Hold / Close |
| closed_at | DATETIME | 否 | 实际关闭时间 |
| created_at | DATETIME | 是 | 创建时间 |
| updated_at | DATETIME | 是 | 更新时间 |

---

## 11. 用户表设计

### 11.1 表名：`users`

#### 表说明

用于存储系统用户及权限信息。

#### 字段设计

| 字段名 | 类型 | 是否必填 | 说明 |
|---|---|---:|---|
| id | INT | 是 | 主键，自增 |
| username | VARCHAR(64) | 是 | 用户名 |
| password_hash | VARCHAR(255) | 否 | 密码哈希 |
| role | VARCHAR(20) | 是 | 角色，如 `admin`、`viewer` |
| is_active | BOOLEAN | 是 | 是否启用 |
| external_subject | VARCHAR(255) | 否 | 外部系统用户标识 |
| auth_source | VARCHAR(32) | 是 | 认证来源，如 `local`、`oa` |
| created_at | DATETIME | 是 | 创建时间 |

---

## 12. 不建议入库的字段

以下字段建议由前端或后端实时计算，不建议入库：

| 字段 | 原因 |
|---|---|
| 小计 | 可由当前行所有 `allocation` 求和 |
| 人力占比 | 可由当前行小计 / 当前月总人力计算 |
| 季度汇总 | 可由对应三个月数据汇总 |
| 年度汇总 | 可由 12 个月数据汇总 |
| 前端合并单元格状态 | 属于展示逻辑，不属于业务数据 |
| 表格滚动位置 | 属于前端交互状态 |
| 临时编辑状态 | 属于前端状态 |

---

## 13. 数据读写流程

### 13.1 前端加载月度人力数据

以加载 `2026-01` 为例。

后端需要返回三类数据：

#### 项目行结构

来自：

```text
programs
sub_programs
sub_projects
```

示例：

```json
[
  {
    "id": 1,
    "name": "稳定性",
    "sub_programs": [
      {
        "id": 10,
        "name": "容灾",
        "sub_projects": [
          {
            "id": 101,
            "name": "大数据容灾"
          }
        ]
      }
    ]
  }
]
```

#### 部门列结构

来自：

```text
manpower_department_groups
manpower_columns
```

示例：

```json
[
  {
    "id": 1,
    "name": "平台与架构",
    "columns": [
      {
        "id": 1001,
        "name": "大模型"
      },
      {
        "id": 1002,
        "name": "架构"
      }
    ]
  }
]
```

#### 人力单元格数据

来自：

```text
manpower_cells
```

示例：

```json
[
  {
    "sub_project_id": 101,
    "period": "2026-01",
    "column_id": 1001,
    "allocation": 1.00
  },
  {
    "sub_project_id": 101,
    "period": "2026-01",
    "column_id": 1002,
    "allocation": 0.50
  }
]
```

前端根据：

```text
sub_project_id + column_id
```

即可将数值填回对应单元格。

### 13.2 前端保存月度人力数据

当用户编辑某个单元格时，应保存为：

```text
sub_project_id
period
column_id
allocation
```

推荐使用 upsert 逻辑：

```sql
INSERT INTO manpower_cells (
    sub_project_id,
    period,
    column_id,
    allocation
)
VALUES (...)
ON DUPLICATE KEY UPDATE
    allocation = VALUES(allocation),
    updated_at = CURRENT_TIMESTAMP;
```

---

## 14. 示例映射

前端展示：

| 项目集 | 子项目集 | 子项目 | 平台与架构-大模型 | 平台与架构-架构 | 运维中心-SRE |
|---|---|---|---:|---:|---:|
| 稳定性 | 容灾 | 大数据容灾 | 1.00 | 0.50 | 2.00 |

对应数据库：

### `programs`

| id | year | name |
|---:|---:|---|
| 1 | 2026 | 稳定性 |

### `sub_programs`

| id | program_id | year | name |
|---:|---:|---:|---|
| 10 | 1 | 2026 | 容灾 |

### `sub_projects`

| id | sub_program_id | year | name |
|---:|---:|---:|---|
| 101 | 10 | 2026 | 大数据容灾 |

### `manpower_department_groups`

| id | year | name |
|---:|---:|---|
| 1 | 2026 | 平台与架构 |
| 2 | 2026 | 运维中心 |

### `manpower_columns`

| id | group_id | year | name |
|---:|---:|---:|---|
| 1001 | 1 | 2026 | 大模型 |
| 1002 | 1 | 2026 | 架构 |
| 2001 | 2 | 2026 | SRE |

### `manpower_cells`

| sub_project_id | period | column_id | allocation |
|---:|---|---:|---:|
| 101 | 2026-01 | 1001 | 1.00 |
| 101 | 2026-01 | 1002 | 0.50 |
| 101 | 2026-01 | 2001 | 2.00 |

---

## 15. 推荐建表 SQL 草稿

以下 SQL 供 DBA 和研发评审，具体字段长度、索引命名可根据规范调整。

```sql
CREATE TABLE programs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    year SMALLINT NOT NULL COMMENT '所属年份',
    name VARCHAR(100) NOT NULL COMMENT '项目集名称',
    sort_order INT DEFAULT 0 COMMENT '排序',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_program_year_name (year, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sub_programs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    program_id INT NOT NULL COMMENT '所属项目集',
    year SMALLINT NOT NULL COMMENT '所属年份',
    name VARCHAR(100) NOT NULL COMMENT '子项目集名称',
    sort_order INT DEFAULT 0 COMMENT '排序',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_sub_program_name (program_id, year, name),
    KEY idx_sub_program_year (year),
    CONSTRAINT fk_sub_program_program
        FOREIGN KEY (program_id) REFERENCES programs(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sub_projects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sub_program_id INT NOT NULL COMMENT '所属子项目集',
    year SMALLINT NOT NULL COMMENT '所属年份',
    name VARCHAR(200) NOT NULL COMMENT '子项目名称',
    status VARCHAR(20) DEFAULT 'active' COMMENT '状态',
    sort_order INT DEFAULT 0 COMMENT '排序',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_sub_project_name (sub_program_id, year, name),
    KEY idx_sub_project_year (year),
    CONSTRAINT fk_sub_project_sub_program
        FOREIGN KEY (sub_program_id) REFERENCES sub_programs(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE manpower_department_groups (
    id INT AUTO_INCREMENT PRIMARY KEY,
    year SMALLINT NOT NULL COMMENT '所属年份',
    name VARCHAR(100) NOT NULL COMMENT '一级部门分组名称',
    sort_order INT DEFAULT 0 COMMENT '展示顺序',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_manpower_group_year_name (year, name),
    KEY idx_manpower_group_year (year)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE manpower_columns (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL COMMENT '所属一级部门分组',
    year SMALLINT NOT NULL COMMENT '所属年份',
    name VARCHAR(100) NOT NULL COMMENT '二级部门/角色/职能列名称',
    sort_order INT DEFAULT 0 COMMENT '展示顺序',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_manpower_column_group_name (group_id, name),
    KEY idx_manpower_column_year (year),
    KEY idx_manpower_column_group (group_id),
    CONSTRAINT fk_manpower_column_group
        FOREIGN KEY (group_id) REFERENCES manpower_department_groups(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE manpower_cells (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sub_project_id INT NOT NULL COMMENT '子项目 ID',
    period VARCHAR(7) NOT NULL COMMENT '年月，格式 YYYY-MM',
    column_id INT NOT NULL COMMENT '人力列 ID',
    allocation DECIMAL(6,2) NOT NULL DEFAULT 0.00 COMMENT '人力投入值',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_manpower_cell (sub_project_id, period, column_id),
    KEY idx_manpower_cell_period (period),
    KEY idx_manpower_cell_column (column_id),
    CONSTRAINT fk_manpower_cell_project
        FOREIGN KEY (sub_project_id) REFERENCES sub_projects(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_manpower_cell_column
        FOREIGN KEY (column_id) REFERENCES manpower_columns(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 16. 迁移建议

如果当前数据库中已有 `manpower_allocations` 表，可按以下思路迁移。

### 16.1 从旧表提取一级部门分组

```sql
SELECT DISTINCT
    sp.year,
    ma.department
FROM manpower_allocations ma
JOIN sub_projects sp ON sp.id = ma.sub_project_id;
```

写入：

```text
manpower_department_groups
```

### 16.2 从旧表提取二级部门列

```sql
SELECT DISTINCT
    sp.year,
    ma.department,
    ma.role
FROM manpower_allocations ma
JOIN sub_projects sp ON sp.id = ma.sub_project_id;
```

写入：

```text
manpower_columns
```

### 16.3 迁移旧人力值

将旧数据：

```text
sub_project_id
period
department
role
allocation
```

转换为新数据：

```text
sub_project_id
period
column_id
allocation
```

迁移到：

```text
manpower_cells
```

### 16.4 迁移后处理

建议迁移完成后：

1. 保留旧表一段时间用于回滚；
2. 前后端确认新表读写正常；
3. 数据核对完成后，再考虑废弃旧表；
4. 不建议新功能继续写入旧表。

---

## 17. 设计收益

| 问题 | 解决方式 |
|---|---|
| 前端保存后刷新丢失 | 单元格通过 `sub_project_id + period + column_id` 唯一定位 |
| DBA 修改数据库后前端无法展示 | 前端可读取部门分组和列定义后还原表头 |
| 列顺序混乱 | 使用 `sort_order` 控制展示顺序 |
| 部门名称变更导致历史数据匹配失败 | 单元格绑定 `column_id`，名称变更不影响历史数据 |
| 小计、人力占比不一致 | 不入库存储，统一实时计算 |
| 月度、季度、年度重复存储 | 只存月度，季度/年度按月度聚合 |

---

## 18. 需要评审确认的问题

建议技术评审时重点确认以下问题：

1. 部门列结构是否按年份隔离？
   - 当前建议按 `year` 隔离；
   - 如果组织结构跨年复用，可后续增加复制或模板机制。

2. 人力投入值精度是否使用 `DECIMAL(6,2)`？
   - 当前支持如 `1.00`、`0.50`；
   - 若只允许整数，可改为 `INT`；
   - 若支持半人力，建议保留小数类型。

3. 删除部门列时如何处理历史数据？
   - 建议优先采用逻辑删除或限制删除；
   - 如果物理删除，`manpower_cells` 可能级联删除历史单元格，需谨慎。

4. 项目删除时是否级联删除人力、阶段、风险？
   - 当前建议级联删除；
   - 若需要审计留痕，可改为 `status = archived`，避免物理删除。

5. 是否需要操作日志？
   - 如需审计 DBA 或管理员修改历史，可增加审计表。

---

## 19. 最终推荐表清单

| 表名 | 用途 |
|---|---|
| users | 用户与权限 |
| programs | 项目集 |
| sub_programs | 子项目集 |
| sub_projects | 子项目 |
| phase_assessments | 项目阶段状态 |
| manpower_department_groups | 人力表一级部门表头 |
| manpower_columns | 人力表二级部门列 |
| manpower_cells | 人力单元格数据 |
| project_risks | 项目风险 |

不建议继续作为核心业务表使用：

| 表名 | 原因 |
|---|---|
| manpower_allocations | 缺少复合表头结构，无法完整还原前端矩阵 |
| registry | 如果系统已关系型化，不应继续作为主要业务数据存储 |

---

## 20. 总结

部门项目人力登记不是普通列表，而是一个多维矩阵：

```text
项目维度 × 月份维度 × 部门列维度 = 人力投入值
```

因此推荐数据库设计为：

```text
项目结构表
+ 部门表头定义表
+ 人力单元格事实表
```

即：

```text
programs / sub_programs / sub_projects
+ manpower_department_groups / manpower_columns
+ manpower_cells
```

该设计能够完整支持前端复合表展示、数据库直接维护、月度录入、季度/年度汇总，并能避免保存后刷新丢失和数据库数据无法展示的问题。
