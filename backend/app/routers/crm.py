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
    CRMNotificationAttemptRequest,
    CRMNotificationAttemptResponse,
    CRMNotificationResolutionRequest,
    CRMNotificationUpdateRequest,
)
from ..services.crm_service import (
    CRMConflictError,
    CRMNotFoundError,
    begin_notification_attempt,
    create_followup,
    get_customer,
    get_followup,
    get_followup_by_run,
    list_customer_followups,
    resolve_unknown_notification,
    update_notification_result,
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
    "/workflow-runs/{run_id}/followup",
    response_model=CRMFollowupResponse,
    summary="按工作流运行查询 CRM 跟进记录",
    description="供故障恢复和人工核对按 run_id 查询已保存的业务结果。",
    responses={
        404: {"description": "该运行尚未保存跟进记录。"},
        422: {"description": "工作流运行标识不符合约束。"},
    },
)
def read_followup_by_run(run_id: CRMIdentifier) -> CRMFollowupResponse:
    try:
        record = get_followup_by_run(run_id)
    except CRMNotFoundError as exc:
        _raise_http_error(exc)

    return CRMFollowupResponse(**record)


@router.post(
    "/followups/{followup_id}/notification-attempts",
    response_model=CRMNotificationAttemptResponse,
    summary="登记 CRM 跟进通知发送尝试",
    description=(
        "在调用通知接口前原子登记一次发送尝试。"
        "首次发送可以自动开始；明确失败后的重发必须显式标记 manual。"
        "delivery_unknown 在人工核对前禁止重发。"
    ),
    responses={
        404: {"description": "跟进记录不存在。"},
        409: {"description": "当前通知状态不允许发送或重发。"},
        422: {"description": "跟进记录标识或请求字段不符合约束。"},
    },
)
def post_notification_attempt(
    followup_id: CRMIdentifier,
    request: CRMNotificationAttemptRequest,
) -> CRMNotificationAttemptResponse:
    try:
        result = begin_notification_attempt(
            followup_id,
            manual=request.manual,
        )
    except (CRMConflictError, CRMNotFoundError) as exc:
        _raise_http_error(exc)

    return CRMNotificationAttemptResponse(**vars(result))


@router.patch(
    "/followups/{followup_id}/notification",
    response_model=CRMFollowupResponse,
    summary="保存 CRM 跟进通知结果",
    description=(
        "记录上游明确成功、明确失败或结果不确定。"
        "通知结果只允许首次写入或完全相同的幂等重放。"
    ),
    responses={
        404: {"description": "跟进记录不存在。"},
        409: {"description": "尚未登记发送尝试或结果已经记录。"},
        422: {"description": "通知状态、消息 ID 或安全错误码不符合约束。"},
    },
)
def patch_notification(
    followup_id: CRMIdentifier,
    request: CRMNotificationUpdateRequest,
) -> CRMFollowupResponse:
    try:
        record = update_notification_result(
            followup_id,
            notification_status=request.status,
            message_id=request.message_id,
            error_code=request.error_code,
        )
    except (CRMConflictError, CRMNotFoundError) as exc:
        _raise_http_error(exc)

    return CRMFollowupResponse(**record)


@router.patch(
    "/followups/{followup_id}/notification-resolution",
    response_model=CRMFollowupResponse,
    summary="人工核对结果不确定的 CRM 通知",
    description=(
        "仅处理 delivery_unknown。人工确认送达后记为 sent；"
        "确认未送达后记为 failed，之后才可人工决定重发。"
    ),
    responses={
        404: {"description": "跟进记录不存在。"},
        409: {"description": "通知状态不是 delivery_unknown。"},
        422: {"description": "核对结果或消息 ID 不符合约束。"},
    },
)
def patch_notification_resolution(
    followup_id: CRMIdentifier,
    request: CRMNotificationResolutionRequest,
) -> CRMFollowupResponse:
    try:
        record = resolve_unknown_notification(
            followup_id,
            delivered=request.delivered,
            message_id=request.message_id,
        )
    except (CRMConflictError, CRMNotFoundError) as exc:
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
