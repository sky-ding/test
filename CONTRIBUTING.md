# 协作说明（Git 与 PR）

本仓库由**多人同时维护**时，请统一采用下面的流程，避免在 `main` 上互相覆盖、难以回滚或集成线不可部署。

## 核心原则

1. **`main` 分支永远可部署**：不在 `main` 上做未经验证的长时间开发。
2. **禁止直接向 `main` push**：日常只 push 到自己的**功能/修复分支**，变更经 **Pull Request / Merge Request** 合入 `main`。
3. **合并前 Code Review**：PR 中可见 diff，指定 reviewer，通过后再合并。

> 仅靠自觉不够：请在托管平台（GitHub / GitLab / Gitee 等）为 `main` 打开**分支保护**，从机制上禁止直推（见下文「仓库管理员」）。

## 分支命名（建议）

| 前缀 | 用途 | 示例 |
|------|------|------|
| `feature/` | 新功能 | `feature/phase-export` |
| `fix/` | 缺陷修复 | `fix/manpower-save-month` |
| `chore/` | 工具、文档、无行为变更的维护 | `chore/readme-env` |

命名简短、使用英文小写与连字符即可；团队可约定是否带 issue 编号。

## 日常开发流程（每人）

1. 更新本地 `main`：
   ```bash
   git fetch origin
   git checkout main
   git pull origin main
   ```
2. 从 `main` 新建分支：
   ```bash
   git checkout -b fix/your-topic
   ```
3. 开发与提交（在**当前分支**上）：
   ```bash
   git add -p   # 或 git add <路径>
   git commit -m "fix: 简短说明（可选 Conventional Commits）"
   ```
4. 推送到远程**同名分支**（不要 push `main`）：
   ```bash
   git push -u origin fix/your-topic
   ```
5. 在网页上创建 **PR / MR**：base 选 `main`，填写标题与说明（改了什么、如何验证），指定 reviewer。
6. Review 通过并合并后，本地同步并可选删除分支：
   ```bash
   git checkout main
   git pull origin main
   git branch -d fix/your-topic
   ```

### 冲突处理

若 PR 提示与 `main` 冲突：在本地把最新 `main` 合并进你的分支（或 rebase，团队统一一种方式），解决冲突后再 push 到同一远程分支，PR 会自动更新。

**禁止**对共享分支使用 `git push --force` 覆盖他人历史；对 `main` 的 force push 应在平台上**永久关闭**。

## PR / MR 描述建议

- **标题**：一句话说明变更（可与 commit 首行一致）。
- **正文**：动机、主要改动、如何手动验证（若涉及接口/前端联调可写步骤）。
- 若团队使用 issue 跟踪，可写 `Closes #123` 等（视平台语法而定）。

## 仓库管理员：在托管平台启用「分支保护」

以下操作在**网页仓库设置**中完成，无法通过本仓库内文件自动生效；**至少应由一位管理员配置一次**。

### GitHub

1. 打开仓库 **Settings** → **Branches**（或 **Rules** → **Rulesets**，视组织是否已迁移到 rulesets）。
2. 为分支名模式 **`main`** 添加保护规则（Add branch protection rule / ruleset）。
3. 建议勾选：
   - **Require a pull request before merging**（合并前必须经过 PR）。
   - **Require approvals**（至少 1 人 Approve，小团队可酌情）。
   - **Do not allow bypassing the above settings**（含管理员也遵守，可选但利于纪律）。
   - **Block force pushes**。
4. 保存。

官方文档：[About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)

### GitLab

1. 打开项目 **Settings** → **Repository** → **Protected branches**。
2. 将 **`main`** 设为 **Allowed to merge** / **Allowed to push** 仅赋予 Maintainer（或仅允许通过 MR 合并，按版本界面勾选「No one」对 push、仅 Maintainer 对 merge 等）。
3. 禁止对受保护分支 force push（在保护规则或实例策略中确认）。

官方文档：[Protected branches](https://docs.gitlab.com/ee/user/project/protected_branches.html)

### Gitee

1. 进入仓库 **管理** → **保护分支设置**（或类似入口）。
2. 将 **`main`** 设为保护分支：**禁止直接推送**，仅允许通过 **Pull Request** 合并。
3. 关闭或不使用对 `main` 的强制推送。

官方帮助可在 Gitee 帮助中心搜索「保护分支」。

### 可选增强

- 合并前要求 **CI 通过**（GitHub Actions / GitLab CI 等）。
- 合并方式统一为 **Squash merge** 或 **Merge commit**（团队二选一，在仓库设置中限定）。

## 与「每次直接 push 到 main」对比

| 不推荐 | 推荐 |
|--------|------|
| 在 `main` 上改完 `git push origin main` | 在 `feature/…` 或 `fix/…` 上改完 `git push origin <分支名>`，再开 PR 合入 `main` |
| 无 review、无集成门禁 | PR + Review（+ CI 可选） |

若你过去习惯直推 `main`，从下一次提交起切换到功能分支即可；启用分支保护后，直推会被平台拒绝，避免误操作。
