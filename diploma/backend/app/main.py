from collections import Counter
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from .db import Base, SessionLocal, engine
from .models import AuditLog, ModerationCheck, Project, utc_now
from .rule_engine import evaluate_payload
from .schemas import (
    AnalyticsOut,
    CheckDetail,
    CheckOut,
    ModerationRequest,
    ModerationResult,
    ProjectCreate,
    ProjectOut,
    ProjectUpdateRules,
    ReviewRequest,
    RuleSet,
)

ROLE_ADMIN = "admin"
ROLE_MODERATOR = "moderator"
ROLE_INTEGRATOR = "integrator"
VALID_ROLES = {ROLE_ADMIN, ROLE_MODERATOR, ROLE_INTEGRATOR}

DEFAULT_BANNED_CATEGORIES = ["оружие", "наркотики"]
DEFAULT_BANNED_KEYWORDS = ["поддельный сертификат", "без документов", "обход закона"]
DEFAULT_RISKY_KEYWORDS = ["лечит все болезни", "гарантированный доход", "100% результат"]
DEFAULT_REQUIRED_FIELDS = ["brand", "price", "country_of_origin"]
DEFAULT_CERT_REQUIRED_CATEGORIES = ["детские товары", "косметика", "электроника"]

app = FastAPI(title="Moderation SaaS Prototype", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_role(x_role: Annotated[str | None, Header(alias="X-Role")] = None) -> str:
    role = (x_role or ROLE_INTEGRATOR).strip().lower()
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Unknown role '{role}'")
    return role


def require_roles(*allowed_roles: str):
    def checker(role: str = Depends(get_role)) -> str:
        if role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return role

    return checker


def to_rules(project: Project) -> RuleSet:
    return RuleSet(
        risk_threshold=project.risk_threshold,
        banned_categories=project.banned_categories,
        banned_keywords=project.banned_keywords,
        risky_keywords=project.risky_keywords,
        required_fields=project.required_fields,
        certificate_required_categories=project.certificate_required_categories,
    )


def to_project_out(project: Project) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        name=project.name,
        description=project.description,
        api_key=project.api_key,
        is_active=project.is_active,
        rules=to_rules(project),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def write_audit(
    db: Session,
    action: str,
    actor_role: str,
    project_id: str | None = None,
    check_id: str | None = None,
    payload: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            project_id=project_id,
            check_id=check_id,
            action=action,
            actor_role=actor_role,
            payload=payload or {},
        )
    )


def create_default_project_if_missing() -> None:
    with SessionLocal() as db:
        exists = db.query(Project).filter(Project.api_key == "demo-api-key-123").first()
        if exists:
            return

        db.add(
            Project(
                name="Demo Marketplace",
                description="Демонстрационный проект для прототипа модерации",
                api_key="demo-api-key-123",
                risk_threshold=55,
                banned_categories=DEFAULT_BANNED_CATEGORIES,
                banned_keywords=DEFAULT_BANNED_KEYWORDS,
                risky_keywords=DEFAULT_RISKY_KEYWORDS,
                required_fields=DEFAULT_REQUIRED_FIELDS,
                certificate_required_categories=DEFAULT_CERT_REQUIRED_CATEGORIES,
            )
        )
        db.commit()


def resolve_project_for_submission(
    db: Session,
    payload: ModerationRequest,
    api_key: str | None,
) -> Project:
    if api_key:
        project = db.query(Project).filter(Project.api_key == api_key, Project.is_active.is_(True)).first()
        if not project:
            raise HTTPException(status_code=401, detail="Invalid X-API-Key")
        return project

    if not payload.project_id:
        raise HTTPException(status_code=400, detail="project_id is required when X-API-Key is not provided")

    project = db.query(Project).filter(Project.id == payload.project_id, Project.is_active.is_(True)).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def resolve_version(
    db: Session,
    project_id: str,
    external_content_id: str | None,
    parent_check_id: str | None,
) -> tuple[int, str | None, str | None]:
    parent_id = parent_check_id
    external_id = external_content_id

    if parent_check_id:
        parent = db.query(ModerationCheck).filter(ModerationCheck.id == parent_check_id).first()
        if not parent or parent.project_id != project_id:
            raise HTTPException(status_code=400, detail="Invalid parent_check_id")
        parent_id = parent.id
        external_id = external_id or parent.external_content_id
        return parent.version + 1, parent_id, external_id

    if external_content_id:
        max_version = (
            db.query(func.max(ModerationCheck.version))
            .filter(
                ModerationCheck.project_id == project_id,
                ModerationCheck.external_content_id == external_content_id,
            )
            .scalar()
        )
        return (max_version or 0) + 1, None, external_content_id

    return 1, None, external_id


def build_moderation_check(
    payload: ModerationRequest,
    project: Project,
    status_value: str,
    action_value: str,
    risk_score: int,
    signals: list[dict],
    version: int,
    parent_id: str | None,
    external_id: str | None,
) -> ModerationCheck:
    return ModerationCheck(
        project_id=project.id,
        content_type=payload.content_type,
        external_content_id=external_id,
        parent_check_id=parent_id,
        version=version,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        attributes=payload.attributes,
        image_urls=payload.image_urls,
        status=status_value,
        decision_source="automatic",
        risk_score=risk_score,
        recommended_action=action_value,
        triggered_rules=signals,
    )


def process_async_check(check_id: str, payload_data: dict) -> None:
    with SessionLocal() as db:
        check = db.query(ModerationCheck).filter(ModerationCheck.id == check_id).first()
        if not check:
            return
        project = db.query(Project).filter(Project.id == check.project_id).first()
        if not project:
            return

        payload = ModerationRequest(**payload_data)
        result = evaluate_payload(project, payload)
        check.status = result.status
        check.recommended_action = result.recommended_action
        check.risk_score = result.risk_score
        check.triggered_rules = [signal.model_dump() for signal in result.signals]
        check.updated_at = utc_now()

        write_audit(
            db=db,
            action="moderation_check_processed_async",
            actor_role="system",
            project_id=check.project_id,
            check_id=check.id,
            payload={"status": check.status, "risk_score": check.risk_score},
        )
        db.commit()


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    create_default_project_if_missing()


@app.get("/health")
def healthcheck() -> dict:
    return {"status": "ok"}


@app.post(
    "/api/v1/projects",
    response_model=ProjectOut,
    dependencies=[Depends(require_roles(ROLE_ADMIN))],
)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectOut:
    project = Project(
        name=payload.name,
        description=payload.description,
        api_key=f"key-{payload.name.lower().replace(' ', '-')}-{abs(hash(payload.name)) % 100000}",
        risk_threshold=payload.rules.risk_threshold,
        banned_categories=payload.rules.banned_categories,
        banned_keywords=payload.rules.banned_keywords,
        risky_keywords=payload.rules.risky_keywords,
        required_fields=payload.rules.required_fields,
        certificate_required_categories=payload.rules.certificate_required_categories,
    )
    db.add(project)
    db.flush()
    write_audit(db, action="project_created", actor_role=ROLE_ADMIN, project_id=project.id, payload=payload.model_dump())
    db.commit()
    db.refresh(project)
    return to_project_out(project)


@app.get(
    "/api/v1/projects",
    response_model=list[ProjectOut],
    dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_MODERATOR, ROLE_INTEGRATOR))],
)
def list_projects(db: Session = Depends(get_db)) -> list[ProjectOut]:
    projects = db.query(Project).order_by(desc(Project.created_at)).all()
    return [to_project_out(project) for project in projects]


@app.patch(
    "/api/v1/projects/{project_id}/rules",
    response_model=ProjectOut,
    dependencies=[Depends(require_roles(ROLE_ADMIN))],
)
def update_project_rules(project_id: str, payload: ProjectUpdateRules, db: Session = Depends(get_db)) -> ProjectOut:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.risk_threshold = payload.rules.risk_threshold
    project.banned_categories = payload.rules.banned_categories
    project.banned_keywords = payload.rules.banned_keywords
    project.risky_keywords = payload.rules.risky_keywords
    project.required_fields = payload.rules.required_fields
    project.certificate_required_categories = payload.rules.certificate_required_categories
    project.updated_at = utc_now()

    write_audit(
        db,
        action="project_rules_updated",
        actor_role=ROLE_ADMIN,
        project_id=project.id,
        payload=payload.model_dump(),
    )
    db.commit()
    db.refresh(project)
    return to_project_out(project)


@app.post(
    "/api/v1/moderation/checks",
    response_model=ModerationResult,
    status_code=status.HTTP_201_CREATED,
)
def submit_check(
    payload: ModerationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    role: str = Depends(get_role),
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> ModerationResult:
    project = resolve_project_for_submission(db, payload, x_api_key)
    version, parent_id, external_id = resolve_version(
        db, project.id, payload.external_content_id, payload.parent_check_id
    )

    if payload.mode == "async":
        check = build_moderation_check(
            payload=payload,
            project=project,
            status_value="pending",
            action_value="wait_for_result",
            risk_score=0,
            signals=[],
            version=version,
            parent_id=parent_id,
            external_id=external_id,
        )
        db.add(check)
        db.flush()
        write_audit(
            db,
            action="moderation_check_submitted_async",
            actor_role=role,
            project_id=project.id,
            check_id=check.id,
            payload={"mode": payload.mode},
        )
        db.commit()
        db.refresh(check)
        background_tasks.add_task(process_async_check, check.id, payload.model_dump())
        return ModerationResult(
            check_id=check.id,
            project_id=project.id,
            status=check.status,
            recommended_action=check.recommended_action,
            risk_score=check.risk_score,
            signals=[],
            version=check.version,
            parent_check_id=check.parent_check_id,
            created_at=check.created_at,
        )

    result = evaluate_payload(project, payload)
    check = build_moderation_check(
        payload=payload,
        project=project,
        status_value=result.status,
        action_value=result.recommended_action,
        risk_score=result.risk_score,
        signals=[signal.model_dump() for signal in result.signals],
        version=version,
        parent_id=parent_id,
        external_id=external_id,
    )
    db.add(check)
    db.flush()
    write_audit(
        db,
        action="moderation_check_submitted_sync",
        actor_role=role,
        project_id=project.id,
        check_id=check.id,
        payload={"mode": payload.mode, "status": check.status},
    )
    db.commit()
    db.refresh(check)

    return ModerationResult(
        check_id=check.id,
        project_id=project.id,
        status=check.status,
        recommended_action=check.recommended_action,
        risk_score=check.risk_score,
        signals=result.signals,
        version=check.version,
        parent_check_id=check.parent_check_id,
        created_at=check.created_at,
    )


@app.get(
    "/api/v1/moderation/checks",
    response_model=list[CheckOut],
    dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_MODERATOR, ROLE_INTEGRATOR))],
)
def list_checks(
    project_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    content_type: str | None = Query(default=None),
    risk_min: int | None = Query(default=None, ge=0, le=100),
    risk_max: int | None = Query(default=None, ge=0, le=100),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[ModerationCheck]:
    query = db.query(ModerationCheck).order_by(desc(ModerationCheck.created_at))
    if project_id:
        query = query.filter(ModerationCheck.project_id == project_id)
    if status_filter:
        query = query.filter(ModerationCheck.status == status_filter)
    if content_type:
        query = query.filter(ModerationCheck.content_type == content_type)
    if risk_min is not None:
        query = query.filter(ModerationCheck.risk_score >= risk_min)
    if risk_max is not None:
        query = query.filter(ModerationCheck.risk_score <= risk_max)
    return query.limit(limit).all()


@app.get(
    "/api/v1/moderation/checks/{check_id}",
    response_model=CheckDetail,
    dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_MODERATOR, ROLE_INTEGRATOR))],
)
def get_check(check_id: str, db: Session = Depends(get_db)) -> CheckDetail:
    check = db.query(ModerationCheck).filter(ModerationCheck.id == check_id).first()
    if not check:
        raise HTTPException(status_code=404, detail="Check not found")

    if check.external_content_id:
        related = (
            db.query(ModerationCheck)
            .filter(
                ModerationCheck.project_id == check.project_id,
                ModerationCheck.external_content_id == check.external_content_id,
                ModerationCheck.id != check.id,
            )
            .order_by(desc(ModerationCheck.version))
            .all()
        )
    else:
        related = (
            db.query(ModerationCheck)
            .filter(
                ModerationCheck.project_id == check.project_id,
                ModerationCheck.parent_check_id == check.id,
            )
            .order_by(desc(ModerationCheck.version))
            .all()
        )

    return CheckDetail(
        **CheckOut.model_validate(check).model_dump(),
        related_versions=[CheckOut.model_validate(item) for item in related],
    )


@app.post(
    "/api/v1/moderation/checks/{check_id}/review",
    response_model=CheckOut,
    dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_MODERATOR))],
)
def review_check(
    check_id: str,
    payload: ReviewRequest,
    db: Session = Depends(get_db),
    role: str = Depends(get_role),
) -> ModerationCheck:
    check = db.query(ModerationCheck).filter(ModerationCheck.id == check_id).first()
    if not check:
        raise HTTPException(status_code=404, detail="Check not found")
    if check.status == "pending":
        raise HTTPException(status_code=409, detail="Async check is still processing")

    status_map = {
        "approve": "approved",
        "reject": "rejected",
        "escalate": "escalated",
    }
    check.status = status_map[payload.action]
    check.recommended_action = payload.action
    check.decision_source = "manual"
    check.reviewed_by_role = role
    check.review_comment = payload.comment
    check.reviewed_at = utc_now()
    check.updated_at = utc_now()

    write_audit(
        db=db,
        action="manual_review_decision",
        actor_role=role,
        project_id=check.project_id,
        check_id=check.id,
        payload=payload.model_dump(),
    )
    db.commit()
    db.refresh(check)
    return check


@app.get(
    "/api/v1/analytics",
    response_model=AnalyticsOut,
    dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_MODERATOR, ROLE_INTEGRATOR))],
)
def get_analytics(project_id: str = Query(...), db: Session = Depends(get_db)) -> AnalyticsOut:
    checks = db.query(ModerationCheck).filter(ModerationCheck.project_id == project_id).all()
    status_counter = Counter(item.status for item in checks)

    signal_counter: Counter[str] = Counter()
    for item in checks:
        for signal in item.triggered_rules or []:
            code = signal.get("code", "UNKNOWN")
            signal_counter[code] += 1

    return AnalyticsOut(
        total_checks=len(checks),
        by_status=dict(status_counter),
        top_risk_signals=[
            {"code": code, "count": count} for code, count in signal_counter.most_common(5)
        ],
    )

