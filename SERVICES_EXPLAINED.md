# Последние сервисы — построчный разбор

Файлы: `core/security.py`, `services/cart.py`, `services/payment.py`, `services/order.py`, `services/auth.py`, `services/staff.py`.

Порядок, в котором их стоит читать: **security → cart → payment → order → auth → staff**. Каждый следующий использует предыдущие.

---

## 0. `core/security.py` — инструменты безопасности

| Строка | Что делает |
|---|---|
| `_hasher = PasswordHasher()` | объект argon2 — превращает PIN в «хэш», из которого PIN назад не достать |
| `hash_secret(value)` | `"482915"` → `"$argon2id$v=19$..."`. В базе хранится только это |
| `verify_secret(hashed, value)` | сравнивает введённый PIN с хэшем. `try/except` — потому что argon2 при несовпадении кидает ошибку, а нам нужно просто `False` |
| `sha256(value)` | быстрый хэш для refresh-токенов и SMS-кодов (им не нужна медленная защита как PIN) |
| `random_token()` | случайная строка, которую не угадать (`secrets`, не `random`!) |
| `create_access_token(...)` | собирает JWT: `sub` — id юзера, `sid` — id сессии, `role` — роль сотрудника, `pin` — прошёл ли PIN, `exp` — когда протухнет. Подписывает секретом из `.env` |
| `decode_access_token(token)` | проверяет подпись и срок; если кто-то подделал токен — `jwt` кинет ошибку |

---

## 1. `services/cart.py` — подсчёт корзины

### Два вспомогательных класса (`@dataclass`)

```python
@dataclass
class PricedLine: ...
```
`@dataclass` — короткий способ сделать класс «просто с полями», без `__init__` вручную.
- `PricedLine` — одна посчитанная строка корзины: товар, размер, добавки-снимок, цена, количество, ошибка.
- `PricedCart` — вся корзина: точка, строки, ответ для фронта (`out`), какой промокод применился, использован ли подарок.

Зачем: фронту отдаём `out` (красиво), а заказ потом создаётся из `lines` (со всеми id).

### `quote(user_id, data)`

```python
location = await self.locations.with_hours(data.location_id)
if location is None or not location.is_active:
    raise NotFound("Кофейня не найдена")
```
Точка существует и работает.

```python
stop_products, stop_variants, stop_modifiers = await self.stock.stopped_ids(location.id)
```
Три множества id того, что сейчас в стоп-листе.

```python
variants = {v.id: v for v in await self.products.variants_by_ids([i.variant_id for i in data.items])}
```
Одним запросом грузим все размеры из корзины (с товаром и добавками) и делаем словарь `{id: размер}` — чтобы дальше быстро доставать по id.

```python
lines = [self._price_line(i, item, variants.get(item.variant_id), ...) for i, item in enumerate(data.items)]
```
Каждую позицию считаем отдельным методом `_price_line` (разбор ниже). `enumerate` даёт номер позиции — фронт по нему подсветит ошибку у нужной строки.

```python
ok_lines = [l for l in lines if l.error is None]
subtotal = sum(l.unit_price * l.quantity for l in ok_lines)
```
Сумма только по нормальным позициям.

**Подарок:**
```python
account = await self.loyalty.by_user(user_id)
gift_available = bool(account and account.gifts_available > 0)
```
Есть ли у гостя подарок на карте. Только тогда фронт покажет блок «Напиток в подарок».

```python
gift_candidates = [l for l in ok_lines if variants[l.variant_id].product.can_be_gift]
gift_applicable = gift_available and bool(gift_candidates)
```
Подарком может стать только напиток (десерт — нет).

```python
if data.use_gift and gift_applicable:
    best = max(gift_candidates, key=lambda l: variants[l.variant_id].price)
    gift_discount = variants[best.variant_id].price
```
Гость нажал «использовать подарок» → берём **самый дорогой** напиток, скидка = цена его размера. Добавки (овсяное молоко) остаются платными.

```python
    if best.quantity > 1:
        best.quantity -= 1
        ...
        gift_line = PricedLine(**{**best.__dict__, "quantity": 1, ..., "is_gift": True})
        lines.insert(lines.index(best) + 1, gift_line)
    else:
        best.is_gift = True
```
Если латте ×2 — делим на «латте ×1» и «латте ×1 🎁». Иначе просто помечаем строку подарочной.
`{**best.__dict__, "quantity": 1}` = «скопировать все поля строки, но quantity заменить на 1».

**Промокод:**
```python
try:
    promo, promo_discount = await self.promo.validate(...)
except ServiceError as e:
    promo_error = e.detail
```
Зовём наш `PromoService.validate`. Если код плохой — **не падаем**, а запоминаем текст ошибки: корзина посчитается без промокода, а под полем ввода фронт напишет причину.

```python
else:
    if promo.type == PromoType.FREE_PRODUCT:
        ... lines.append(PricedLine(..., line_total=0, is_gift=True))
        subtotal += variant.price
    else:
        promo_discount = min(promo_discount, subtotal - gift_discount)
```
`else` у `try` выполняется, если ошибки не было.
- «Товар в подарок» → добавляем бесплатную строку (круассан за 0 ₽).
- Скидка не может быть больше остатка суммы.

```python
discount_total = gift_discount + promo_discount
total = max(subtotal - discount_total, 0)
discount_total = subtotal - total
```
Итог. Последняя строка нужна, чтобы в базе всегда выполнялось `total = subtotal − discount_total` (это правило стоит в таблице).

**Предупреждения:** заказ «ко времени» раньше минимума, точка не принимает заказы, гость заблокирован. Любое предупреждение → `can_checkout = False`, кнопка «Оплатить» на фронте станет серой.

```python
stamps = sum(l.quantity for l in lines if ... l.counts_for_loyalty and not l.is_gift)
```
Сколько штампов гость получит — напитки, кроме подарочного.

### `_price_line` — одна позиция

```python
def broken(name, error): return PricedLine(..., error=error)
```
Функция внутри функции: короткий способ вернуть «сломанную» строку с текстом ошибки.

Проверки по порядку:
1. размер существует и принадлежит этому товару (защита от подмены id);
2. товар и размер активны;
3. не в стоп-листе.

```python
allowed = {}
for link in product.modifier_links:
    for m in group.modifiers:
        if m.is_active and (link.modifier_ids is None or m.id in link.modifier_ids):
            allowed[m.id] = (group, m)
```
Собираем, **какие добавки разрешены именно у этого товара** (те, что владелец отметил галочками).

```python
for modifier_id in dict.fromkeys(item.modifier_ids):
```
`dict.fromkeys` убирает повторы, сохраняя порядок (если фронт прислал одну добавку дважды).
Каждая выбранная добавка: разрешена? не закончилась? Считаем, сколько выбрано в каждой группе.

```python
if count < group.min_select:  → «Выберите: молоко»
if count > group.max_select:  → «Сироп: можно выбрать не больше 2»
```
Правила групп.

```python
unit = variant.price + sum(m["price_delta"] for m in picked)
```
Цена за штуку = размер + добавки. **Цены всегда считает сервер** — что прислал фронт, не важно.

---

## 2. `services/payment.py` — ЮKassa

### `PaymentGateway(Protocol)`
«Протокол» = описание: у платёжки должны быть методы `create_payment`, `get_payment`, `create_refund`. Настоящая ЮKassa и фейк для тестов оба подходят под него — поэтому сервис можно проверить без реальных денег.

### `YooKassaGateway`
| Метод | Что делает |
|---|---|
| `_request` | общий HTTP-запрос через `httpx` с логином `shop_id:secret_key`. Заголовок `Idempotence-Key` — если запрос повторится из-за сети, ЮKassa не создаст второй платёж |
| `create_payment` | сумма в рублях строкой (`"260.00"`), `capture: True` — списать сразу, `return_url` — куда вернуть гостя после оплаты, `metadata.order_id` — чтобы потом понять, какой это заказ |
| `get_payment` | узнать текущий статус платежа |
| `create_refund` | вернуть деньги |

`rub(26000)` → `"260.00"`: у нас копейки, ЮKassa хочет рубли.

### `PaymentService`

**`create_for_order(order)`** — создать платёж, сохранить строку `Payment` и вернуть ссылку на оплату. Ключ идемпотентности `order-{id}` — один заказ = один платёж.

**`handle_webhook(external_id)`** — ЮKassa сообщила «что-то с платежом»:
```python
data = await self.gateway.get_payment(external_id)
```
**Не верим телу вебхука** — его может прислать кто угодно. Сами спрашиваем ЮKassa, какой статус на самом деле.
- `succeeded` → платёж оплачен, заказ из «ждёт оплаты» переходит в «новый» и появляется у бариста.
- `canceled` → гость не оплатил.
Проверки `payment.status != ...` — защита от повторного вебхука (ЮKassa может прислать одно событие дважды).

**`refund(order, amount, reason)`** — вернуть деньги: находим успешный платёж, проверяем, что не возвращаем больше оплаченного, просим ЮKassa, записываем `Refund`, обновляем статус заказа (полный / частичный возврат).

---

## 3. `services/order.py` — заказы

### Таблица переходов
```python
NEXT_STATUS = {
    NEW: {ACCEPTED},
    ACCEPTED: {PREPARING, READY},
    PREPARING: {READY},
    READY: {COMPLETED},
}
```
Куда можно перевести заказ из каждого статуса. Бариста не может «Выдан» → «Принят» или «Новый» → «Выдан».
`USER_CAN_CANCEL` — гость отменяет сам, только пока заказ не взяли в работу.

### `create(user_id, data, idempotency_key)`

```python
if idempotency_key:
    existing = await self.orders.by_idempotency_key(...)
    if existing is not None: return existing
```
Гость нажал «Оплатить» дважды (или пропал интернет и фронт повторил запрос) → вернём **тот же** заказ, второй не создастся.

```python
if user.is_blocked: raise Forbidden(...)
priced = await self.cart.quote(user_id, data)
```
Пересчитываем корзину **на сервере** — фронт мог прислать старые цены.

```python
if data.payment_method not in priced.location.payment_methods: ...
if data.promo_code and priced.out.promo_error: ...
if not priced.out.can_checkout: ...
```
Способ оплаты доступен в этой точке, промокод рабочий, корзина без ошибок.

```python
online = data.payment_method in ONLINE_PAYMENT_METHODS
today = datetime.now(ZoneInfo(priced.location.timezone)).date()
number = await self.orders.next_number(priced.location.id, today)
status = PENDING_PAYMENT if online else NEW
```
- «Сегодня» — по часам **точки**, не сервера (сервер может быть в UTC).
- Номер `#001` за день с блокировкой (два заказа одновременно не получат одинаковый номер).
- Онлайн-оплата → заказ ждёт денег и бариста его ещё **не видит**. Наличные → сразу новый.

```python
order = Order(..., items=[OrderItem(...) for l in priced.lines], status_history=[...])
await self.orders.add(order)
```
Создаём заказ сразу с позициями и первой строкой истории. В позициях — **снимок**: название, цена и добавки на момент заказа. Если потом поменяют меню — старый заказ не изменится.

```python
if priced.gift_used: await self.loyalty.redeem_gift(...)
if priced.promo: await self.promo.redeem(...)
```
Списываем подарок с карты, отмечаем использование промокода.

```python
if online and order.total > 0:
    url = await self.payments().create_for_order(order)
elif online:
    order.payment_status = PAID ...
```
Нужна оплата → ссылка ЮKassa. Если всё покрыл подарок (итог 0 ₽) — платить нечего, заказ сразу уходит бариста.

```python
order_id = order.id
self.session.expire(order)
return await self.orders.full(order_id), url
```
Перечитываем заказ со всеми связями для ответа (помнишь: сначала сохранить id, потом `expire`).

### `change_status(order_id, to, staff_id, staff_user_id)`
```python
order = await self.orders.full(order_id, for_update=True)
```
С блокировкой — два бариста не переведут заказ одновременно.
```python
if to not in NEXT_STATUS.get(order.status, set()): raise Conflict(...)
```
Проверка по таблице переходов.
- `ACCEPTED` → кто принял и когда.
- `READY` → когда готов.
- `COMPLETED` → когда выдан; наличные теперь считаются оплаченными; **штампы**:
```python
if not order.loyalty_processed:
    stamps = order.loyalty_items_count
    await self.loyalty.add_stamps(order.user_id, stamps, ...)
    order.loyalty_processed = True
```
Флаг `loyalty_processed` — штампы за один заказ ставятся ровно один раз.

### `cancel_by_user` / `reject` и общий `_undo`
Отмена гостем (только пока не приняли) и отказ от кофейни (с причиной). Обе зовут `_undo`, который откатывает всё, что сделал `create`:
1. вернуть подарок на карту;
2. вернуть использование промокода;
3. если было оплачено онлайн — вернуть деньги.

### `expire_unpaid()`
Фоновая задача раз в минуту: заказы, не оплаченные за N минут (`orders.payment_timeout_min`, по умолчанию 15) → «просрочен», подарок и промокод возвращаются.

### `queue(location_id)`
Активные заказы точки, разложенные по колонкам: новые / приняты / готовятся / ждут выдачи.

---

## 4. `services/auth.py` — вход

### SMS-отправители
`SmsRuSender` — настоящая отправка через sms.ru. `LogSender` — пишет код в лог (для разработки). `default_sender()` выбирает сам: есть ключ в `.env` → настоящий.

### `issue_tokens(user, pin)`
```python
refresh = random_token()
row = await self.tokens.create(user_id=..., token_hash=sha256(refresh), expires_at=...)
```
Создаём **сессию** в базе. Сам refresh-токен не храним — только его хэш (украдут базу — токены не узнают).
```python
staff = await self.staff.by_user_id(user.id)
role = staff.role.value if staff and staff.is_active else None
access, ttl = create_access_token(user.id, row.id, role=role, pin=...)
return TokenPair(access_token=access, refresh_token=f"{row.id}.{refresh}", ...)
```
Access-токен короткий (15 мин), refresh — `id_сессии.секрет` на 30 дней.

### `_new_user` / `_upsert_telegram` / `_ensure_owner`
- новый гость получает уникальный реферальный код и сразу карту лояльности;
- вход через Telegram: нашли по `tg_id` — обновили имя/фото; не нашли — создали;
- если `tg_id` указан в `OWNER_TG_IDS` в `.env` — автоматически становится владельцем (так появляется самый первый админ).

### `login_telegram(init_data)`
```python
if self.settings.dev_mode and init_data.startswith("dev="): ...
```
Только для локальной разработки (`DEV_MODE=true`) — вход без Telegram.
Иначе — `verify_init_data` проверяет подпись Telegram. Подделать нельзя: нужен токен бота.

### `login_widget(data)` — кнопка «Войти через Telegram» на сайте, та же логика, другая проверка подписи.

### `sms_send(phone, ip)`
Защиты от «спама SMS за наш счёт»:
1. `sms:wait:{phone}` — повтор не раньше чем через 60 с;
2. `sms:day:{phone}` — не больше 10 кодов на номер в сутки;
3. `sms:ip:{ip}` — не больше 20 запросов с одного IP в час.

`redis.incr` — атомарно +1 и вернуть новое значение; `expire` — ключ сам удалится через N секунд.
Код храним как `sha256(phone:code)` + счётчик попыток, живёт 5 минут.

### `sms_verify(phone, code)`
1. код ещё жив?
2. `hincrby attempts` — больше 5 попыток → код сгорает (перебор 10 000 вариантов не пройдёт);
3. `secrets.compare_digest` — сравнение, по времени которого нельзя угадать код;
4. нашли гостя по телефону — входим, нет — создаём.

### `refresh(refresh_token)`
Проверяем сессию (существует, не отозвана, не истекла, секрет совпал); если владелец нажал «Выйти везде» после её создания — отказ. Старую сессию **отзываем**, выдаём новую пару (ротация: украденный refresh сработает максимум один раз). PIN после refresh **не сохраняется** — панель спросит снова.

### `check_session(payload)`
Вызывается на каждом запросе: сессия из токена не отозвана, гость не заблокирован.

### `magic_create` / `magic_login`
Вход в админку с компьютера: бот на `/admin` создаёт одноразовую ссылку на 2 минуты (`getdel` — прочитал и сразу удалил).

---

## 5. `services/staff.py` — команда и PIN

### `me(user_id)`
Сотрудник + список точек, которые ему видны (владельцу — все, бариста — только своя).

### `pin_setup` — первый вход: придумать PIN. Если уже задан → 409. Хэшируем, выдаём токен с `pin=True`.

### `pin_verify`
```python
if staff.pin_locked(now): return PinVerifyOut(ok=False, locked_until=...)
if verify_secret(staff.pin_hash, pin): ... ok
attempts = await self.staff.pin_failed(staff.id)
if attempts >= 5: lock_pin(now + 15 мин)
return PinVerifyOut(ok=False, attempts_left=5 - attempts)
```
Заблокирован → сразу отказ. Верный → токен с `pin=True`. Неверный → +1 к ошибкам (атомарно), на 5-й — блок на 15 минут, фронт покажет таймер.

### `lock` — кнопка «Заблокировать» / автоблок: новый access с `pin=False`.

### `add_staff(owner, data)`
Человек должен **хотя бы раз открыть бота** (иначе мы не знаем его как юзера). Нельзя добавить дважды.

### `update_staff`
- нельзя убрать **последнего владельца** (иначе админка останется без хозяина);
- нельзя отключить самого себя;
- отключили сотрудника → сразу выкидываем из всех сессий.

### `reset_pin` / `revoke_sessions`
Владелец сбрасывает PIN баристе (тот придумает новый при входе) и/или «Выйти везде»: ставим `tokens_valid_after = сейчас` и отзываем все refresh-сессии.
