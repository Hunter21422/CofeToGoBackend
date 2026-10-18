from enum import StrEnum


class StaffRole(StrEnum):
    BARISTA = "barista"
    MANAGER = "manager"
    OWNER = "owner"


class OrderStatus(StrEnum):
    PENDING_PAYMENT = "pending_payment"  # ждём онлайн-оплату
    NEW = "new"                          # пришёл бариста
    ACCEPTED = "accepted"
    PREPARING = "preparing"
    READY = "ready"
    COMPLETED = "completed"              # выдан → начисляются штампы
    CANCELLED = "cancelled"              # отменил клиент
    REJECTED = "rejected"                # отклонила кофейня
    EXPIRED = "expired"                  # не оплачен вовремя


ACTIVE_ORDER_STATUSES = {
    OrderStatus.NEW,
    OrderStatus.ACCEPTED,
    OrderStatus.PREPARING,
    OrderStatus.READY,
}
FINAL_ORDER_STATUSES = {
    OrderStatus.COMPLETED,
    OrderStatus.CANCELLED,
    OrderStatus.REJECTED,
    OrderStatus.EXPIRED,
}


class OrderType(StrEnum):
    PICKUP = "pickup"
    DINE_IN = "dine_in"


class OrderSource(StrEnum):
    MINIAPP = "miniapp"
    POS = "pos"
    ADMIN = "admin"


class CancelledBy(StrEnum):
    USER = "user"
    STAFF = "staff"
    SYSTEM = "system"


class PaymentMethod(StrEnum):
    CARD_ONLINE = "card_online"
    SBP = "sbp"
    TELEGRAM = "telegram"
    CASH = "cash"
    CARD_ON_PICKUP = "card_on_pickup"


ONLINE_PAYMENT_METHODS = {PaymentMethod.CARD_ONLINE, PaymentMethod.SBP, PaymentMethod.TELEGRAM}


class OrderPaymentStatus(StrEnum):
    UNPAID = "unpaid"
    PENDING = "pending"
    PAID = "paid"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentProvider(StrEnum):
    YOOKASSA = "yookassa"
    TELEGRAM = "telegram"
    CASH = "cash"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    WAITING_FOR_CAPTURE = "waiting_for_capture"
    SUCCEEDED = "succeeded"
    CANCELED = "canceled"


class RefundStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    CANCELED = "canceled"


class LoyaltyTier(StrEnum):
    BASE = "base"
    SILVER = "silver"
    GOLD = "gold"


class LoyaltyTxType(StrEnum):
    STAMP_EARNED = "stamp_earned"      # +штамп за кофе
    GIFT_UNLOCKED = "gift_unlocked"    # 5 штампов → 1 подарок
    GIFT_REDEEMED = "gift_redeemed"    # подарок потрачен
    GIFT_RETURNED = "gift_returned"    # заказ с подарком отменён — вернули
    MANUAL_ADJUST = "manual_adjust"    # ручная корректировка персоналом
    BIRTHDAY = "birthday"
    REFERRAL = "referral"
    EXPIRED = "expired"                # сгорели


class PromoType(StrEnum):
    PERCENT = "percent"
    FIXED = "fixed"
    FREE_PRODUCT = "free_product"


class BannerLinkType(StrEnum):
    NONE = "none"
    PRODUCT = "product"
    CATEGORY = "category"
    URL = "url"


class BroadcastStatus(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    DONE = "done"
    CANCELLED = "cancelled"


class NotificationType(StrEnum):
    ORDER_STATUS = "order_status"
    STAFF_NEW_ORDER = "staff_new_order"
    LOYALTY = "loyalty"
    BIRTHDAY = "birthday"
    BROADCAST = "broadcast"
    SYSTEM = "system"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
