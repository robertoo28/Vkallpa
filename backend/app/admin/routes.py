from fastapi import APIRouter, Depends, Response, status

from ..auth.dependencies import (
    get_current_user,
    get_data_repository,
    require_module_access,
)
from ..auth.schemas import (
    CompanyItem,
    CompanyListResponse,
    CreateCompanyRequest,
    CreateUserRequest,
    UpdateCompanyRequest,
    UpdateUserRequest,
    UserItem,
    UserListResponse,
)
from ..auth.service import (
    CurrentUserContext,
    create_company,
    create_user,
    delete_user,
    list_companies,
    list_users,
    update_company,
    update_user,
)
from ..services.data_repository import DataRepository


router = APIRouter(prefix="/admin", tags=["admin"])
tenants_router = APIRouter(prefix="/tenants", tags=["tenants"])


@tenants_router.get(
    "",
    response_model=CompanyListResponse,
    dependencies=[Depends(require_module_access("admin-companies"))],
)
def get_tenants(
    current_user: CurrentUserContext = Depends(get_current_user),
) -> CompanyListResponse:
    return CompanyListResponse(
        items=[
            CompanyItem.model_validate(item)
            for item in list_companies(current_user)
        ]
    )


@tenants_router.post(
    "",
    response_model=CompanyItem,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_module_access("admin-companies"))],
)
def post_tenant(
    payload: CreateCompanyRequest,
    current_user: CurrentUserContext = Depends(get_current_user),
    repo: DataRepository = Depends(get_data_repository),
) -> CompanyItem:
    return CompanyItem.model_validate(create_company(current_user, payload, repo))


@tenants_router.put(
    "/{tenant_id}",
    response_model=CompanyItem,
    dependencies=[Depends(require_module_access("admin-companies"))],
)
def put_tenant(
    tenant_id: str,
    payload: UpdateCompanyRequest,
    current_user: CurrentUserContext = Depends(get_current_user),
    repo: DataRepository = Depends(get_data_repository),
) -> CompanyItem:
    return CompanyItem.model_validate(
        update_company(current_user, tenant_id, payload, repo)
    )


@router.get(
    "/companies",
    response_model=CompanyListResponse,
    dependencies=[Depends(require_module_access("admin-companies"))],
)
def get_companies(
    current_user: CurrentUserContext = Depends(get_current_user),
) -> CompanyListResponse:
    return CompanyListResponse(
        items=[
            CompanyItem.model_validate(item)
            for item in list_companies(current_user)
        ]
    )


@router.post(
    "/companies",
    response_model=CompanyItem,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_module_access("admin-companies"))],
)
def post_company(
    payload: CreateCompanyRequest,
    current_user: CurrentUserContext = Depends(get_current_user),
    repo: DataRepository = Depends(get_data_repository),
) -> CompanyItem:
    return CompanyItem.model_validate(create_company(current_user, payload, repo))


@router.patch(
    "/companies/{company_id}",
    response_model=CompanyItem,
    dependencies=[Depends(require_module_access("admin-companies"))],
)
def patch_company(
    company_id: str,
    payload: UpdateCompanyRequest,
    current_user: CurrentUserContext = Depends(get_current_user),
    repo: DataRepository = Depends(get_data_repository),
) -> CompanyItem:
    return CompanyItem.model_validate(
        update_company(current_user, company_id, payload, repo)
    )


@router.get(
    "/users",
    response_model=UserListResponse,
    dependencies=[Depends(require_module_access("admin-users"))],
)
def get_users(
    current_user: CurrentUserContext = Depends(get_current_user),
) -> UserListResponse:
    return UserListResponse(
        items=[UserItem.model_validate(item) for item in list_users(current_user)]
    )


@router.post(
    "/users",
    response_model=UserItem,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_module_access("admin-users"))],
)
def post_user(
    payload: CreateUserRequest,
    current_user: CurrentUserContext = Depends(get_current_user),
    repo: DataRepository = Depends(get_data_repository),
) -> UserItem:
    return UserItem.model_validate(create_user(current_user, payload, repo))


@router.patch(
    "/users/{user_id}",
    response_model=UserItem,
    dependencies=[Depends(require_module_access("admin-users"))],
)
def patch_user(
    user_id: str,
    payload: UpdateUserRequest,
    current_user: CurrentUserContext = Depends(get_current_user),
    repo: DataRepository = Depends(get_data_repository),
) -> UserItem:
    return UserItem.model_validate(update_user(current_user, user_id, payload, repo))


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_module_access("admin-users"))],
)
def remove_user(
    user_id: str,
    current_user: CurrentUserContext = Depends(get_current_user),
) -> Response:
    delete_user(current_user, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
