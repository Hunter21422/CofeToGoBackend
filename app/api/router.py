from fastapi import APIRouter

from app.api import webhooks
from app.api.admin import auth as admin_auth
from app.api.admin import banners, broadcasts, categories, customers, locations as admin_locations, loyalty as admin_loyalty, modifier_groups, orders as admin_orders, products, promo_codes, reviews, settings, staff, stats, stock
from app.api.client import auth, cart, favorites, locations, loyalty, me, orders, promo, push

api_router = APIRouter(prefix="/api/v1")
for module in (
    auth, me, locations, cart, promo, orders, loyalty, favorites, push,
    admin_auth, admin_orders, admin_loyalty, categories, products, modifier_groups, stock,
    customers, promo_codes, banners, broadcasts, stats, reviews, staff, admin_locations, settings,
    webhooks,
):
    api_router.include_router(module.router)
