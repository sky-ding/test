from fastapi import APIRouter, Response, status

router = APIRouter(prefix="/manpower", tags=["manpower"])


def _gone() -> Response:
    return Response(
        status_code=status.HTTP_410_GONE,
        media_type="application/json",
        content=(
            '{"detail":"Removed: use GET/PUT /api/v1/manpower-allocations '
            'with year, period, and sub_project_id."}'
        ),
    )


@router.get("")
def get_manpower_deprecated():
    return _gone()


@router.put("")
def put_manpower_deprecated():
    return _gone()
