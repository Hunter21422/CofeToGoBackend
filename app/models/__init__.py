"""Все модели импортируются здесь — Alembic видит их через Base.metadata."""

from .audit import AuditLog
from .base import Base
from .location import Location, LocationHours, LocationSpecialDay
from .loyalty import LoyaltyAccount, LoyaltyTransaction
from .marketing import Banner, Broadcast
from .menu import Category, Product, ProductVariant
from .modifier import Modifier, ModifierGroup, ProductModifierGroup
from .notification import NotificationLog
from .order import Order, OrderItem, OrderStatusHistory
from .payment import Payment, Refund
from .profile import Favorite, Review
from .promo import PromoCode, PromoRedemption
from .setting import Setting
from .staff import Staff
from .stock import StockItem
from .user import RefreshToken, User

__all__ = [
    "AuditLog",
    "Banner",
    "Base",
    "Broadcast",
    "Category",
    "Favorite",
    "Location",
    "LocationHours",
    "LocationSpecialDay",
    "LoyaltyAccount",
    "LoyaltyTransaction",
    "Modifier",
    "ModifierGroup",
    "NotificationLog",
    "Order",
    "OrderItem",
    "OrderStatusHistory",
    "Payment",
    "ProductModifierGroup",
    "Product",
    "ProductVariant",
    "PromoCode",
    "PromoRedemption",
    "RefreshToken",
    "Refund",
    "Review",
    "Setting",
    "Staff",
    "StockItem",
    "User",
]
