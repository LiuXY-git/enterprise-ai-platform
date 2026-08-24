from fastapi import APIRouter

from ..models.system import HealthResponse

router = APIRouter(tags=["system"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="检查服务运行状态",
    description=("检查 FastAPI 服务是否正常运行。该接口同时用于 Docker 容器健康检查。"),
    response_description="服务运行正常。",
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
