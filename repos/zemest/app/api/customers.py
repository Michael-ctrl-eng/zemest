import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_tenant
from app.models.customer import Customer
from app.models.order import Order
from app.models.conversation import Conversation
from app.schemas.customer import CustomerResponse, CustomerListResponse, CustomerUpdate

router = APIRouter(prefix="/api/tenants/{tenant_id}/customers", tags=["Customers"])


def _customer_response(c: Customer, orders_count: int = 0, conversations_count: int = 0, total_spent: float = 0) -> CustomerResponse:
    return CustomerResponse(
        id=str(c.id),
        name=c.name,
        phone=c.phone,
        governorate=c.governorate,
        city=c.city,
        area=c.area,
        address_detail=c.address_detail,
        created_at=c.created_at,
        orders_count=orders_count,
        conversations_count=conversations_count,
        total_spent=total_spent,
    )


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: str | None = None,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    base = select(Customer).where(Customer.tenant_id == tenant.id)
    count_base = select(func.count(Customer.id)).where(Customer.tenant_id == tenant.id)

    if search:
        pattern = f"%{search}%"
        filt = or_(Customer.name.ilike(pattern), Customer.phone.ilike(pattern))
        base = base.where(filt)
        count_base = count_base.where(filt)

    total = await db.scalar(count_base) or 0

    result = await db.execute(
        base.order_by(Customer.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    customers = result.scalars().all()

    # Get counts for each customer
    responses = []
    for c in customers:
        o_count = await db.scalar(
            select(func.count(Order.id)).where(Order.customer_id == c.id)
        ) or 0
        c_count = await db.scalar(
            select(func.count(Conversation.id)).where(Conversation.customer_id == c.id)
        ) or 0
        spent = await db.scalar(
            select(func.coalesce(func.sum(Order.total), 0)).where(
                Order.customer_id == c.id,
                Order.status.in_(["confirmed", "shipped", "delivered"]),
            )
        ) or 0
        responses.append(_customer_response(c, o_count, c_count, float(spent)))

    return CustomerListResponse(
        customers=responses, total=total, page=page, page_size=page_size
    )


@router.get("/{customer_id}")
async def get_customer_detail(
    customer_id: uuid.UUID,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Customer).where(
            Customer.id == customer_id, Customer.tenant_id == tenant.id
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Get orders
    orders_result = await db.execute(
        select(Order).where(Order.customer_id == customer.id)
        .order_by(Order.created_at.desc()).limit(20)
    )
    orders = orders_result.scalars().all()

    # Get conversations
    convs_result = await db.execute(
        select(Conversation).where(Conversation.customer_id == customer.id)
        .order_by(Conversation.last_message_at.desc()).limit(10)
    )
    convs = convs_result.scalars().all()

    spent = await db.scalar(
        select(func.coalesce(func.sum(Order.total), 0)).where(
            Order.customer_id == customer.id,
            Order.status.in_(["confirmed", "shipped", "delivered"]),
        )
    ) or 0

    return {
        "id": str(customer.id),
        "name": customer.name,
        "phone": customer.phone,
        "governorate": customer.governorate,
        "city": customer.city,
        "area": customer.area,
        "address_detail": customer.address_detail,
        "created_at": str(customer.created_at),
        "total_spent": float(spent),
        "orders": [
            {
                "id": str(o.id),
                "order_number": o.order_number,
                "total": float(o.total),
                "status": o.status,
                "created_at": str(o.created_at),
            }
            for o in orders
        ],
        "conversations": [
            {
                "id": str(cv.id),
                "status": cv.status,
                "last_message_at": str(cv.last_message_at),
            }
            for cv in convs
        ],
    }


@router.patch("/{customer_id}")
async def update_customer(
    customer_id: uuid.UUID,
    req: CustomerUpdate,
    tenant=Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Customer).where(
            Customer.id == customer_id, Customer.tenant_id == tenant.id
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    for key, value in req.model_dump(exclude_none=True).items():
        setattr(customer, key, value)
    await db.flush()

    return {"status": "updated", "id": str(customer.id)}
