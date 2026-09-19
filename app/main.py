from datetime import datetime
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import AfterSaleTicket, Order, Shipment


app = FastAPI(
    title="AI Ecommerce Customer Service API",
    version="0.1.0",
)


@app.get("/health/live", tags=["health"])
def health_live():
    return {
        "status": "ok"
    }


@app.get("/health/ready", tags=["health"])
def health_ready():
    return {
        "status": "ready",
        "environment": settings.app_env,
    }

@app.get("/api/v1/orders/{order_no}", tags=["orders"])
def get_order(order_no: str):
    # MVP identity comes only from server configuration, never request parameters.
    with SessionLocal() as session:
        result = session.execute(
            select(Order, Shipment)
            .outerjoin(Shipment, Shipment.order_id == Order.id)
            .where(
                Order.order_no == order_no,
                Order.user_id == settings.demo_user_id,
            )
        ).one_or_none()
        if result is None:
            raise HTTPException(status_code=404, detail="未找到可访问的订单")
        order, shipment = result
        return {
            "order_no": order.order_no,
            "product_name": order.product_name,
            "quantity": order.quantity,
            "total_amount": format(order.total_amount, ".2f"),
            "order_status": order.status,
            "receiver_name": order.receiver_name,
            "logistics": {
                "carrier": shipment.carrier,
                "tracking_no": shipment.tracking_no,
                "status": shipment.status,
            } if shipment is not None else None,
        }


class AfterSaleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_no: str = Field(min_length=1, max_length=50, pattern=r"\S")
    request_type: Literal["return", "refund", "exchange", "reship", "other"]
    issue_type: Literal["damaged", "missing", "wrong_item", "quality", "no_issue", "other"]
    reason: str = Field(min_length=1, max_length=1000, pattern=r"\S")


class AfterSaleResponse(BaseModel):
    ticket_id: int
    order_no: str
    request_type: str
    issue_type: str
    reason: str
    status: str
    created_at: datetime


@app.post(
    "/api/v1/after-sales",
    status_code=201,
    response_model=AfterSaleResponse,
    tags=["after-sales"],
)
def create_after_sale(payload: AfterSaleCreate):
    # MVP identity comes only from server configuration, never request parameters.
    user_id = settings.demo_user_id
    with SessionLocal() as session:
        order = session.scalar(
            select(Order).where(
                Order.order_no == payload.order_no,
                Order.user_id == user_id,
            )
        )
        if order is None:
            raise HTTPException(status_code=404, detail="未找到可访问的订单")

        ticket = AfterSaleTicket(
            order_id=order.id,
            user_id=user_id,
            request_type=payload.request_type,
            issue_type=payload.issue_type,
            reason=payload.reason,
        )
        session.add(ticket)
        session.commit()
        session.refresh(ticket)
        return AfterSaleResponse(
            ticket_id=ticket.id,
            order_no=order.order_no,
            request_type=ticket.request_type,
            issue_type=ticket.issue_type,
            reason=ticket.reason,
            status=ticket.status,
            created_at=ticket.created_at,
        )


if __name__ == "__main__":
    uvicorn.run("app.main:app",
                host="0.0.0.0",
                port=8000,
                reload=True
                )
