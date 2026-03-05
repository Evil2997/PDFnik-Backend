from faststream.rabbit import RabbitBroker
from faststream.rabbit.fastapi import RabbitRouter

from main_app.core.constants import RABBITMQ_URL
from main_app.rabbitmq.pdf_orders import register_pdf_consumers
from main_app.rabbitmq.txt_orders import register_txt_consumers

broker = RabbitBroker(RABBITMQ_URL)
router = RabbitRouter(RABBITMQ_URL)


def setup_rabbit_subscribers() -> None:
    """Явно регистрируем всех Rabbit-подписчиков."""
    register_pdf_consumers(router)
    register_txt_consumers(router)
