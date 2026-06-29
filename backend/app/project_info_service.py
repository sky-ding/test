"""项目信息聚合读写的业务逻辑（事务内同步子表）。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.manpower_saturation import PERSON_MONTHLY_CAPACITY, person_totals_by_name, saturation_level
from app.models_relational import (
    Goal,
    GoalLink,
    ManpowerCell,
    ManpowerColumn,
    ProjectRisk,
    SubProgram,
    SubProject,
    Task,
    TeamMember,
    TeamMemberAllocation,
)
from app.relational_api import assert_period_matches_year, parse_year
from app.routers.manpower_allocations import build_manpower_matrix_response
from app.schemas_relational import (
    GoalDerivedProgress,
    GoalLinkOut,
    GoalOut,
    ProjectInfoBreadcrumb,
    ProjectInfoGetResponse,
    ProjectInfoManpowerOut,
    ProjectInfoPutBody,
    ProjectRiskDetailOut,
    SubProjectDetailOut,
    TaskOut,
    TeamMemberOut,
)
from app.goal_service import derive_goal_progress, compute_goal_overall_status


def default_period_for_year(year: int) -> str:
    now = datetime.now()
    if year == now.year:
        return f"{year:04d}-{now.month:02d}"
    if year < now.year:
        return f"{year:04d}-12"
    return f"{year:04d}-01"


def _load_sub_project(db: Session, sub_project_id: int, year: int) -> SubProject:
    sp = db.scalar(
        select(SubProject)
        .where(SubProject.id == sub_project_id, SubProject.year == year)
        .options(
            joinedload(SubProject.sub_program).joinedload(SubProgram.program),
        )
    )
    if sp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sub_project not found")
    return sp


def _breadcrumb(sp: SubProject) -> ProjectInfoBreadcrumb:
    spg = sp.sub_program
    prog = spg.program
    return ProjectInfoBreadcrumb(
        program_id=prog.id,
        program_name=prog.name,
        sub_program_id=spg.id,
        sub_program_name=spg.name,
        sub_project_id=sp.id,
        sub_project_name=sp.name,
    )


def _team_members_out(
    db: Session, sub_project_id: int, *, year: int, period: str
) -> list[TeamMemberOut]:
    rows = list(
        db.scalars(
            select(TeamMember)
            .where(TeamMember.sub_project_id == sub_project_id)
            .order_by(TeamMember.sort_order, TeamMember.id)
        ).all()
    )
    col_names: dict[int, str] = {}
    alloc_by_member: dict[int, Decimal] = {}
    if rows:
        col_ids = {r.team_column_id for r in rows}
        cols = db.scalars(select(ManpowerColumn).where(ManpowerColumn.id.in_(col_ids))).all()
        col_names = {c.id: c.name for c in cols}
        member_ids = [r.id for r in rows]
        allocs = db.scalars(
            select(TeamMemberAllocation).where(
                TeamMemberAllocation.team_member_id.in_(member_ids),
                TeamMemberAllocation.period == period,
            )
        ).all()
        alloc_by_member = {a.team_member_id: a.allocation for a in allocs}

    person_totals = person_totals_by_name(db, year=year, period=period)

    result: list[TeamMemberOut] = []
    for r in rows:
        monthly = alloc_by_member.get(r.id, Decimal("0.00"))
        person_total = person_totals.get(r.name.strip(), Decimal("0.00"))
        rate = (person_total / PERSON_MONTHLY_CAPACITY).quantize(Decimal("0.0001"))
        result.append(
            TeamMemberOut(
                id=r.id,
                name=r.name,
                team_column_id=r.team_column_id,
                team_column_name=col_names.get(r.team_column_id, ""),
                role=r.role,
                participation=r.participation,
                remark=r.remark,
                sort_order=r.sort_order,
                monthly_allocation=monthly,
                person_total_allocation=person_total,
                person_saturation_rate=rate,
                person_saturation_level=saturation_level(rate),
            )
        )
    return result


def _project_monthly_total(members: list[TeamMemberOut]) -> Decimal:
    total = sum((m.monthly_allocation for m in members), Decimal("0"))
    return total.quantize(Decimal("0.01"))


def build_project_info_response(
    db: Session,
    *,
    sub_project_id: int,
    year: int,
    period: str,
) -> ProjectInfoGetResponse:
    y = parse_year(year)
    p = assert_period_matches_year(period, y)
    sp = _load_sub_project(db, sub_project_id, y)

    all_tasks = list(
        db.scalars(
            select(Task)
            .where(Task.sub_project_id == sub_project_id)
            .options(selectinload(Task.children))
            .order_by(Task.sort_order, Task.id)
        ).all()
    )
    # 所有顶层任务统一按 parent_id 组织，里程碑只是一个标签，不做互斥筛选
    top_tasks = [t for t in all_tasks if t.parent_id is None]
    risks = list(
        db.scalars(
            select(ProjectRisk)
            .where(ProjectRisk.sub_project_id == sub_project_id)
            .order_by(ProjectRisk.id)
        ).all()
    )

    matrix = build_manpower_matrix_response(db, y, p)
    cells = [c for c in matrix.cells if c.sub_project_id == sub_project_id]
    team_members = _team_members_out(db, sub_project_id, year=y, period=p)

    # ========== 目标跟踪 ==========
    goals = list(
        db.scalars(
            select(Goal)
            .where(Goal.sub_project_id == sub_project_id)
            .order_by(Goal.sort_order, Goal.id)
        ).all()
    )

    # 查询所有 goal_links 用于构建反向索引
    all_links: list[GoalLink] = []
    if goals:
        goal_ids = [g.id for g in goals]
        all_links = list(
            db.scalars(
                select(GoalLink).where(GoalLink.goal_id.in_(goal_ids))
            ).all()
        )

    # 构建反向索引: (target_type, target_id) -> [goal_id, ...]
    reverse_links: dict[tuple[str, int], list[int]] = {}
    for lnk in all_links:
        key = (lnk.target_type, lnk.target_id)
        reverse_links.setdefault(key, []).append(lnk.goal_id)

    # 为每个 goal 构建 links 列表
    goal_links_map: dict[int, list[GoalLink]] = {}
    for lnk in all_links:
        goal_links_map.setdefault(lnk.goal_id, []).append(lnk)

    goals_out: list[GoalOut] = []
    for g in goals:
        derived = derive_goal_progress(db, g, year=y)
        overall = compute_goal_overall_status(g, derived, year=y)
        goals_out.append(GoalOut(
            id=g.id,
            name=g.name,
            metric_unit=g.metric_unit,
            initial_target=g.initial_target,
            mid_term_target=g.mid_term_target,
            current_value=g.current_value,
            direction=g.direction,
            sort_order=g.sort_order,
            links=[GoalLinkOut.model_validate(lnk) for lnk in goal_links_map.get(g.id, [])],
            derived_progress=[GoalDerivedProgress(**d) for d in derived],
            overall_status=overall,
        ))

    # 给任务填充 goal_ids（所有任务/里程碑统一用 task 类型）
    def _build_task_out(t: Task) -> TaskOut:
        tk_out = TaskOut.model_validate(t)
        tk_out.goal_ids = reverse_links.get(("task", t.id), [])
        # 构建子任务
        tk_out.children = [_build_task_out(c) for c in t.children]
        return tk_out

    # 构建任务树（所有任务，含 is_milestone=True 的任务，含 children）
    tasks_out: list[TaskOut] = [_build_task_out(t) for t in top_tasks]

    # 从任务树中提取里程碑（平铺，所有层级中 is_milestone=True 的任务）
    def _extract_milestones(task_list: list[TaskOut]) -> list[TaskOut]:
        result: list[TaskOut] = []
        for t in task_list:
            if t.is_milestone:
                result.append(t)
            if t.children:
                result.extend(_extract_milestones(t.children))
        return result

    milestones_out: list[TaskOut] = _extract_milestones(tasks_out)

    return ProjectInfoGetResponse(
        year=y,
        period=p,
        sub_project=SubProjectDetailOut.model_validate(sp),
        milestones=milestones_out,
        tasks=tasks_out,
        team_members=team_members,
        risks=[ProjectRiskDetailOut.model_validate(r) for r in risks],
        manpower=ProjectInfoManpowerOut(
            period=p,
            dept_groups=matrix.dept_groups,
            cells=cells,
        ),
        breadcrumb=_breadcrumb(sp),
        project_monthly_total=_project_monthly_total(team_members),
        goals=goals_out,
    )


def _assert_owned_ids(db: Session, model, sub_project_id: int, ids: list[int], label: str) -> None:
    if not ids:
        return
    found = set(
        db.scalars(
            select(model.id).where(model.id.in_(ids), model.sub_project_id == sub_project_id)
        ).all()
    )
    missing = set(ids) - found
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} id(s) not found for sub_project: {sorted(missing)}",
        )


def _validate_column_year(db: Session, column_id: int, year: int) -> ManpowerColumn:
    col = db.get(ManpowerColumn, column_id)
    if col is None or int(col.year) != year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid column_id {column_id} for year {year}",
        )
    return col


def _apply_risk_status(row: ProjectRisk, status_value: str) -> None:
    row.status = status_value
    if row.status == "Close":
        if row.closed_at is None:
            row.closed_at = datetime.now(timezone.utc)
    else:
        row.closed_at = None


def _upsert_member_allocation(
    db: Session, *, team_member_id: int, period: str, allocation: Decimal
) -> None:
    alloc = allocation.quantize(Decimal("0.01"))
    row = db.scalar(
        select(TeamMemberAllocation).where(
            TeamMemberAllocation.team_member_id == team_member_id,
            TeamMemberAllocation.period == period,
        )
    )
    if row is None:
        db.add(
            TeamMemberAllocation(
                team_member_id=team_member_id,
                period=period,
                allocation=alloc,
            )
        )
    else:
        row.allocation = alloc


def _rollup_manpower_cells(
    db: Session,
    *,
    sub_project_id: int,
    period: str,
    members: list[tuple[TeamMember, Decimal]],
) -> None:
    by_column: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    for member, alloc in members:
        by_column[member.team_column_id] += alloc

    existing = list(
        db.scalars(
            select(ManpowerCell).where(
                ManpowerCell.sub_project_id == sub_project_id,
                ManpowerCell.period == period,
            )
        ).all()
    )
    touched_columns = set(by_column.keys()) | {c.column_id for c in existing}

    for column_id in touched_columns:
        alloc = by_column.get(column_id, Decimal("0")).quantize(Decimal("0.01"))
        row = db.scalar(
            select(ManpowerCell).where(
                ManpowerCell.sub_project_id == sub_project_id,
                ManpowerCell.period == period,
                ManpowerCell.column_id == column_id,
            )
        )
        if row is None:
            if alloc == Decimal("0.00"):
                continue
            db.add(
                ManpowerCell(
                    sub_project_id=sub_project_id,
                    period=period,
                    column_id=column_id,
                    allocation=alloc,
                )
            )
        else:
            row.allocation = alloc


def save_project_info(
    db: Session,
    *,
    sub_project_id: int,
    year: int,
    body: ProjectInfoPutBody,
) -> ProjectInfoGetResponse:
    y = parse_year(year)
    sp = _load_sub_project(db, sub_project_id, y)
    p = assert_period_matches_year(body.manpower.period, y)

    name = body.sub_project.name.strip()
    clash = db.scalar(
        select(SubProject.id).where(
            SubProject.sub_program_id == sp.sub_program_id,
            SubProject.year == y,
            SubProject.name == name,
            SubProject.id != sub_project_id,
        )
    )
    if clash:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="sub_project name exists")

    sp.name = name
    sp.status = body.sub_project.status
    sp.description = (body.sub_project.description or "").strip() or None
    sp.key_goal = (body.sub_project.key_goal or "").strip() or None
    sp.automation_rate_goal = (body.sub_project.automation_rate_goal or "").strip() or None
    sp.planned_start_date = body.sub_project.planned_start_date
    sp.planned_end_date = body.sub_project.planned_end_date
    sp.actual_start_date = body.sub_project.actual_start_date
    sp.actual_end_date = body.sub_project.actual_end_date

    # ========== 清理被删任务的 goal_links ==========
    from sqlalchemy import delete as sa_delete
    for tid in body.deleted_task_ids:
        db.execute(sa_delete(GoalLink).where(
            GoalLink.target_type == "task",
            GoalLink.target_id == tid,
        ))

    _assert_owned_ids(db, Task, sub_project_id, body.deleted_task_ids, "task")
    for tid in body.deleted_task_ids:
        db.delete(db.get(Task, tid))

    # 两轮处理 tasks：先处理顶层任务（parent_id 为空），再处理子任务，避免外键约束违反
    MAX_TASK_DEPTH = 5

    def _check_depth(item) -> int:
        """检查任务嵌套深度，返回当前深度。超过限制抛出异常。"""
        depth = 0
        cur_pid = item.parent_id
        visited = set()
        while cur_pid is not None:
            if cur_pid in visited:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="circular parent_id reference detected")
            visited.add(cur_pid)
            parent_task = db.get(Task, cur_pid)
            if parent_task is None:
                break
            cur_pid = parent_task.parent_id
            depth += 1
            if depth >= MAX_TASK_DEPTH:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"task nesting depth exceeds maximum ({MAX_TASK_DEPTH})")
        return depth

    def _upsert_and_sync(item) -> None:
        # 校验循环引用和嵌套深度
        if item.parent_id is not None:
            _check_depth(item)
            # 新建任务要额外检查：不能让新建任务成为自己的 parent
            if item.id is not None and item.parent_id == item.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="task cannot be its own parent")
            # 新建任务 id 为 None，但需检查 parent_id 是否指向不存在的任务
            parent_task = db.get(Task, item.parent_id)
            if parent_task is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"parent task {item.parent_id} not found")

        if item.id is None:
            task = Task(
                sub_project_id=sub_project_id,
                name=item.name.strip(),
                status=item.status,
                assignee=(item.assignee or "").strip() or None,
                start_date=item.start_date,
                end_date=item.end_date,
                progress=item.progress,
                is_milestone=item.is_milestone,
                parent_id=item.parent_id,
                sort_order=item.sort_order,
            )
            db.add(task)
            db.flush()
        else:
            task = db.get(Task, item.id)
            if task is None or task.sub_project_id != sub_project_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid task id")
            task.name = item.name.strip()
            task.status = item.status
            task.assignee = (item.assignee or "").strip() or None
            task.start_date = item.start_date
            task.end_date = item.end_date
            task.progress = item.progress
            task.is_milestone = item.is_milestone
            task.parent_id = item.parent_id
            task.sort_order = item.sort_order

        # 同步该任务的 goal 关联
        db.execute(sa_delete(GoalLink).where(
            GoalLink.target_type == "task",
            GoalLink.target_id == task.id,
        ))
        for gid in item.goal_ids:
            goal = db.get(Goal, gid)
            if goal is None or goal.sub_project_id != sub_project_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"invalid goal id {gid}")
            db.add(GoalLink(
                goal_id=gid,
                target_type="task",
                target_id=task.id,
            ))

    # 第一轮：处理 parent_id 为空的顶层任务
    for item in body.tasks:
        if item.parent_id is None:
            _upsert_and_sync(item)
    # 第二轮：处理有 parent_id 的子任务
    for item in body.tasks:
        if item.parent_id is not None:
            _upsert_and_sync(item)

    _assert_owned_ids(db, TeamMember, sub_project_id, body.deleted_team_member_ids, "team_member")
    for tid in body.deleted_team_member_ids:
        db.delete(db.get(TeamMember, tid))

    saved_members: list[tuple[TeamMember, Decimal]] = []
    for item in body.team_members:
        _validate_column_year(db, item.team_column_id, y)
        alloc = item.monthly_allocation.quantize(Decimal("0.01"))
        if item.id is None:
            row = TeamMember(
                sub_project_id=sub_project_id,
                name=item.name.strip(),
                team_column_id=item.team_column_id,
                role=item.role.strip(),
                participation=item.participation,
                remark=(item.remark or "").strip() or None,
                sort_order=item.sort_order,
            )
            db.add(row)
            db.flush()
        else:
            row = db.get(TeamMember, item.id)
            if row is None or row.sub_project_id != sub_project_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid team_member id")
            row.name = item.name.strip()
            row.team_column_id = item.team_column_id
            row.role = item.role.strip()
            row.participation = item.participation
            row.remark = (item.remark or "").strip() or None
            row.sort_order = item.sort_order
        _upsert_member_allocation(db, team_member_id=row.id, period=p, allocation=alloc)
        saved_members.append((row, alloc))

    _rollup_manpower_cells(db, sub_project_id=sub_project_id, period=p, members=saved_members)

    _assert_owned_ids(db, ProjectRisk, sub_project_id, body.deleted_risk_ids, "risk")
    for rid in body.deleted_risk_ids:
        db.delete(db.get(ProjectRisk, rid))

    for item in body.risks:
        if item.id is None:
            row = ProjectRisk(
                sub_project_id=sub_project_id,
                risk_category=item.risk_category.strip(),
                risk_source=item.risk_source.strip(),
                description=item.description.strip(),
                solution=(item.solution or "").strip() or None,
                level=item.level.strip(),
                assignee=item.assignee.strip(),
                resolution_date=item.resolution_date,
                status=item.status,
            )
            _apply_risk_status(row, item.status)
            db.add(row)
        else:
            row = db.get(ProjectRisk, item.id)
            if row is None or row.sub_project_id != sub_project_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid risk id")
            row.risk_category = item.risk_category.strip()
            row.risk_source = item.risk_source.strip()
            row.description = item.description.strip()
            row.solution = (item.solution or "").strip() or None
            row.level = item.level.strip()
            row.assignee = item.assignee.strip()
            row.resolution_date = item.resolution_date
            _apply_risk_status(row, item.status)

    # ========== Upsert 目标 ==========
    _assert_owned_ids(db, Goal, sub_project_id, body.deleted_goal_ids, "goal")
    for gid in body.deleted_goal_ids:
        db.delete(db.get(Goal, gid))

    for item in body.goals:
        if item.id is None:
            goal = Goal(
                sub_project_id=sub_project_id,
                name=item.name.strip(),
                metric_unit=(item.metric_unit or "").strip() or None,
                initial_target=item.initial_target.strip(),
                mid_term_target=(item.mid_term_target or "").strip() or None,
                current_value=(item.current_value or "").strip() or None,
                direction=item.direction,
                sort_order=item.sort_order,
            )
            db.add(goal)
            db.flush()  # 获取 id
        else:
            goal = db.get(Goal, item.id)
            if goal is None or goal.sub_project_id != sub_project_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid goal id")
            goal.name = item.name.strip()
            goal.metric_unit = (item.metric_unit or "").strip() or None
            goal.initial_target = item.initial_target.strip()
            goal.mid_term_target = (item.mid_term_target or "").strip() or None
            goal.current_value = (item.current_value or "").strip() or None
            goal.direction = item.direction
            goal.sort_order = item.sort_order

    db.flush()
    return build_project_info_response(db, sub_project_id=sub_project_id, year=y, period=p)
