import uvicorn
from fastapi import FastAPI

from main_app.infrastructure.rabbit_connector import router, setup_rabbit_subscribers
from main_app.api.routes.orders import router as orders_router


app = FastAPI()

setup_rabbit_subscribers()
app.include_router(orders_router)
app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
