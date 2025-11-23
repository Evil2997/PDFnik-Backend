from fastapi import APIRouter

from main_app.infrastructure.rabbit_connector import router as rabbit_router

router = APIRouter()


@router.post("/order")
async def make_order(name: str):
    await rabbit_router.broker.publish(
        message=f"Order {name}",
        queue="orders_http",
    )
    return {"data": "OK"}
