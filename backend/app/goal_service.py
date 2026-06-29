"""目标进展自动推导服务。"""

from __future__ import annotations

from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models_relational import Goal, GoalLink, Task


def _period_for_date(d: date) -> str:
    """将日期转为 YYYY-MM 格式。"""
    return f"{d.year:04d}-{d.month:02d}"


def _quarter_for_date(d: date) -> str:
    """将日期转为 YYYY-Q1/Q2/Q3/Q4 格式。"""
    q = (d.month - 1) // 3 + 1
    return f"{d.year:04d}-Q{q}"


def _collect_linked_items(db: Session, goal: Goal) -> tuple[list[Task], list[Task]]:
    """获取一个目标关联的所有里程碑任务和普通任务。"""
    milestone_tasks: list[Task] = []
    normal_tasks: list[Task] = []
    for link in goal.links:
        t = db.get(Task, link.target_id)
        if t and t.sub_project_id == goal.sub_project_id:
            if t.is_milestone:
                milestone_tasks.append(t)
            else:
                normal_tasks.append(t)
    return milestone_tasks, normal_tasks


def derive_goal_progress(
    db: Session,
    goal: Goal,
    *,
    year: int,
) -> list[dict]:
    """
    为一个目标推导年度内各季度和各月的进展。

    返回格式:
    [
        {
            "period": "2026-Q2",
            "related_items": ["完成架构设计"],
            "progress_pct": 100.0,
            "status": "completed"
        },
        ...
    ]
    """
    milestone_tasks, normal_tasks = _collect_linked_items(db, goal)

    if not milestone_tasks and not normal_tasks:
        # 无关联 → 无推导数据，返回空列表
        return []

    # 按季度聚合
    quarter_items: dict[str, list[dict]] = {}
    month_items: dict[str, list[dict]] = {}

    for m in milestone_tasks:
        q = _quarter_for_date(m.end_date)
        mo = _period_for_date(m.end_date)
        item = {
            "name": m.name,
            "type": "milestone",
            "status": m.status,
            "date": m.end_date,
        }
        quarter_items.setdefault(q, []).append(item)
        month_items.setdefault(mo, []).append(item)

    for t in normal_tasks:
        # 任务按 start_date 所在的时间窗口聚合
        q = _quarter_for_date(t.start_date)
        mo = _period_for_date(t.start_date)
        item = {
            "name": t.name,
            "type": "task",
            "progress": t.progress,  # 0-100
            "start_date": t.start_date,
            "end_date": t.end_date,
        }
        quarter_items.setdefault(q, []).append(item)
        month_items.setdefault(mo, []).append(item)

    results: list[dict] = []

    # 计算每个时间窗口的聚合状态
    for period, items in sorted(quarter_items.items()):
        results.append(_aggregate_period(period, items))
    for period, items in sorted(month_items.items()):
        results.append(_aggregate_period(period, items))

    return results


def _aggregate_period(period: str, items: list[dict]) -> dict:
    """聚合一个时间窗口内的里程碑/任务状态。

    里程碑和任务统一计算进度：
    - 里程碑: completed=100%, in-progress=50%, not-started=0%
    - 任务: 直接使用 progress 字段
    - 混合时取所有项的平均进度
    """
    related_names = [i["name"] for i in items]

    # 统一计算进度
    progress_values: list[float] = []
    for item in items:
        if item["type"] == "milestone":
            # 里程碑状态转进度
            status = item.get("status", "not-started")
            if status == "completed":
                progress_values.append(100.0)
            elif status == "in-progress":
                progress_values.append(50.0)
            else:  # not-started or other
                progress_values.append(0.0)
        elif item["type"] == "task":
            # 任务直接使用 progress 字段
            progress_values.append(float(item.get("progress", 0)))

    if progress_values:
        progress_pct = round(sum(progress_values) / len(progress_values), 1)
    else:
        progress_pct = None

    # 判断状态
    if progress_pct is not None and progress_pct >= 100:
        status = "completed"
    elif progress_pct is not None and progress_pct > 0:
        status = "in_progress"
    else:
        status = "not_started"

    return {
        "period": period,
        "related_items": related_names,
        "progress_pct": progress_pct,
        "status": status,
    }


def compute_goal_overall_status(goal: Goal, derived: list[dict], year: int | None = None) -> str:
    """
    计算目标的达成状态。

    目标达成状态只看 current_value 与 target_value 的比较，
    不看里程碑/任务的完成进度（那是工作进度，不是目标达成状态）。

    返回: 'on_track' | 'at_risk' | 'behind' | 'not_started'
    """
    # boolean 类型：只要填了值就视为达标（如"是"或"否"）
    if goal.direction == "boolean":
        return "on_track" if goal.current_value else "not_started"

    # 没有手填当前值 → 无法判断是否达成
    if not goal.current_value:
        return "not_started"

    # 有手填值 → 与目标值做数值比较
    try:
        cv = float(goal.current_value.replace("%", ""))
        tv = float((goal.mid_term_target or goal.initial_target).replace("%", ""))

        if goal.direction == "higher_better":
            # 越大越好
            if cv >= tv:
                return "on_track"
            elif tv != 0 and cv / tv >= 0.8:
                return "at_risk"
            else:
                return "behind"
        elif goal.direction == "lower_better":
            # 越小越好
            if cv <= tv:
                return "on_track"
            elif tv != 0 and cv / tv <= 1.2:
                return "at_risk"
            else:
                return "behind"
        else:
            return "on_track"
    except (ValueError, ZeroDivisionError):
        # 无法解析为数字（如文本"完成"），只要有值就视为在跟踪中
        return "on_track"


def build_phase_monthly_data(
    db: Session,
    sub_project_id: int,
    year: int,
    month: int,
) -> dict:
    """构建单个子项目的月度自动填充数据。

    返回自动填充的阶段交付目标文本和目标达成状态。
    前端只在 phase_assessments 对应字段为 NULL 时使用这些数据。
    """
    # 1. 获取本月相关的任务
    tasks = list(db.scalars(
        select(Task)
        .where(Task.sub_project_id == sub_project_id)
    ).all())

    # 2. 筛选本月相关的项，生成自动填充文本
    month_start = date(year, month, 1)
    month_end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    lines = []
    for t in tasks:
        if t.is_milestone:
            if t.end_date.year == year and t.end_date.month == month:
                lines.append(f"📌 {t.name}（{t.end_date.isoformat()}）")
        else:
            if t.start_date < month_end and t.end_date >= month_start:
                lines.append(f"📋 {t.name}（进度 {t.progress}%）")

    auto_goal_text = "\n".join(lines) if lines else ""

    # 3. 计算目标达成状态
    goals = list(db.scalars(
        select(Goal)
        .where(Goal.sub_project_id == sub_project_id)
        .options(selectinload(Goal.links))
        .order_by(Goal.sort_order, Goal.id)
    ).all())

    if not goals:
        auto_status = "not_started"
    else:
        statuses = [compute_goal_overall_status(g, [], year=year) for g in goals]
        priority = {"behind": 0, "at_risk": 1, "not_started": 2, "on_track": 3}
        auto_status = min(statuses, key=lambda s: priority.get(s, 2))

    emoji_map = {
        "on_track": "🟢",
        "at_risk": "🟡",
        "behind": "🔴",
        "not_started": "⏳",
    }

    return {
        "sub_project_id": sub_project_id,
        "auto_goal_text": auto_goal_text,
        "auto_status": auto_status,
        "auto_status_emoji": emoji_map.get(auto_status, "⏳"),
    }


def build_goal_summary(
    db: Session,
    sub_project_id: int,
    year: int,
) -> list[dict]:
    """
    为项目阶段状态页构建目标摘要(只读)。

    返回格式供前端渲染用。
    """
    from app.models_relational import Goal as GoalModel, SubProject
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    # 预加载 links 避免 N+1
    goals = list(
        db.scalars(
            select(GoalModel)
            .where(GoalModel.sub_project_id == sub_project_id)
            .options(selectinload(GoalModel.links))
            .order_by(GoalModel.sort_order, GoalModel.id)
        ).all()
    )

    # 获取子项目名称
    sp = db.get(SubProject, sub_project_id)
    sp_name = sp.name if sp else ""

    summaries: list[dict] = []
    for goal in goals:
        # 优先取期中调整值
        target = goal.mid_term_target or goal.initial_target

        # 获取推导进度（统一计算一次，避免重复查询）
        derived = derive_goal_progress(db, goal, year=year) if goal.links else []

        # 获取当前值：优先取用户手填值，无手填值才用推导进度
        if goal.current_value:
            current_value = goal.current_value
        elif derived:
            now = date.today()
            current_month = f"{now.year:04d}-{now.month:02d}"
            current = next((d for d in derived if d["period"] == current_month), None)
            if current and current["progress_pct"] is not None:
                current_value = f"{current['progress_pct']}%"
            else:
                current_value = "-"
        else:
            current_value = "-"

        # 统一用 compute_goal_overall_status 计算状态
        status = compute_goal_overall_status(goal, derived, year=year)

        emoji_map = {
            "completed": "✅",
            "on_track": "🟢",
            "at_risk": "🟡",
            "behind": "🔴",
            "not_started": "⏳",
        }

        summaries.append({
            "sub_project_id": sub_project_id,
            "sub_project_name": sp_name,
            "name": goal.name,
            "metric_unit": goal.metric_unit,
            "target_value": target,
            "current_value": current_value,
            "status": status,
            "status_emoji": emoji_map.get(status, "⏳"),
        })

    return summaries
