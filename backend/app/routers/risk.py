from fastapi import APIRouter, Response, status

router = APIRouter(prefix="/risk", tags=["risk"])


def _gone() -> Response:
    return Response(
        status_code=status.HTTP_410_GONE,
        media_type="application/json",
        content=(
            '{"detail":"Removed: use GET/POST/PATCH/DELETE /api/v1/project-risks '
            'with year or sub_project_id."}'
        ),
    )


@router.get("")
def get_risk_deprecated():
    return _gone()


@router.put("")
def put_risk_deprecated():
    return _gone()
