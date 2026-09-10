from typing import Annotated, Never

from fastapi import APIRouter, HTTPException, Path, status

from ..models.crm import (
    IDENTIFIER_PATTERN,
    CRMCustomerResponse,
    CRMCustomerUpsertRequest,
    CRMFollowupCreateRequest,
    CRMFollowupCreateResponse,
    CRMFollowupListResponse,
    CRMFollowupResponse,
)
from ..services.crm_service import (
    CRMConflictError,
    CRMNotFoundError,
    create_followup,
    get_customer,
    get_followup,
    list_customer_followups,
    upsert_customer,
)

router = APIRouter(prefix="/crm", tags=["crm"])

CRMIdentifier = Annotated[
    str,
    Path(
        min_length=1,
        max_length=128,
        pattern=IDENTIFIER_PATTERN,
    ),
]


def _raise_http_error(exc: RuntimeError) -> Never:
    if isinstance(exc, CRMNotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    else:
        status_code = status.HTTP_409_CONFLICT

    raise HTTPException(
        status_code=status_code,
        detail=str(exc),
    ) from exc


@router.put(
    "/customers/{customer_id}",
    response_model=CRMCustomerResponse,
    summary="新增或更新 CRM 客户",
    description=(
        "按稳定 customer_id 新增或更新模拟 CRM 客户资料。"
        "路径与请求体中的 customer_id 必须一致。"
    ),
    responses={
        409: {"description": "路径与请求体中的客户标识不一致。"},
        422: {"description": "客户字段或路径参数不符合约束。"},
    },
)
def put_customer(
    customer_id: CRMIdentifier,
    request: CRMCustomerUpsertRequest,
) -> CRMCustomerResponse:
    if customer_id != request.customer_id:
        _raise_http_error(CRMConflictError("路径与请求体中的 customer_id 不一致"))

    return CRMCustomerResponse(**upsert_customer(request))


@router.get(
    "/customers/{customer_id}",
    response_model=CRMCustomerResponse,
    summary="查询 CRM 客户",
    description="按稳定 customer_id 查询一个模拟 CRM 客户。",
    responses={
        404: {"description": "客户不存在。"},
        422: {"description": "客户标识不符合约束。"},
    },
)
def read_customer(customer_id: CRMIdentifier) -> CRMCustomerResponse:
    try:
        record = get_customer(customer_id)
    except CRMNotFoundError as exc:
        _raise_http_error(exc)

    return CRMCustomerResponse(**record)


@router.post(
    "/followups",
    response_model=CRMFollowupCreateResponse,
    summary="创建 CRM 跟进记录",
    description=(
        "在一个事务中新增或更新客户并创建跟进记录。"
        "相同 run_id 再次请求时返回原记录，created 为 false，"
        "不会覆盖客户或创建第二条跟进记录。"
    ),
    responses={
        404: {"description": "对应的工作流运行不存在。"},
        409: {"description": "运行状态、业务事件或客户关联冲突。"},
        422: {"description": "客户、分析、复核或通知字段不符合约束。"},
    },
)
def post_followup(
    request: CRMFollowupCreateRequest,
) -> CRMFollowupCreateResponse:
    try:
        result = create_followup(request)
    except (CRMConflictError, CRMNotFoundError) as exc:
        _raise_http_error(exc)

    return CRMFollowupCreateResponse(
        created=result.created,
        **result.record,
    )


@router.get(
    "/followups/{followup_id}",
    response_model=CRMFollowupResponse,
    summary="查询 CRM 跟进记录",
    description="按平台生成的 followup_id 查询一条完整跟进记录。",
    responses={
        404: {"description": "跟进记录不存在。"},
        422: {"description": "跟进记录标识不符合约束。"},
    },
)
def read_followup(followup_id: CRMIdentifier) -> CRMFollowupResponse:
    try:
        record = get_followup(followup_id)
    except CRMNotFoundError as exc:
        _raise_http_error(exc)

    return CRMFollowupResponse(**record)


@router.get(
    "/customers/{customer_id}/followups",
    response_model=CRMFollowupListResponse,
    summary="查询客户跟进记录",
    description="按 customer_id 返回该客户的全部跟进记录。",
    responses={
        404: {"description": "客户不存在。"},
        422: {"description": "客户标识不符合约束。"},
    },
)
def list_followups(customer_id: CRMIdentifier) -> CRMFollowupListResponse:
    try:
        records = list_customer_followups(customer_id)
    except CRMNotFoundError as exc:
        _raise_http_error(exc)

    return CRMFollowupListResponse(
        customer_id=customer_id,
        count=len(records),
        followups=[CRMFollowupResponse(**record) for record in records],
    )
