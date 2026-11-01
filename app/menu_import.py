import argparse
import asyncio
import re

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import SessionLocal
from app.models import (
    Category,
    Modifier,
    ModifierGroup,
    Product,
    ProductModifierGroup,
    ProductVariant,
)

SYRUPS = [
    "Карамель", "Ваниль", "Шоколад", "Фундук", "Макадамия", "Миндаль", "Арахис", "Фисташка",
    "Малина", "Клубника", "Чёрная смородина", "Гуава", "Гренадин", "Банан", "Кокос", "Лаванда",
    "Мята", "Мохито", "Лимон", "Клён", "Имбирный пряник", "Попкорн", "Бейлис", "Ирландский крем",
]
MILKS = ["Безлактозное", "Банановое", "Миндальное", "Овсяное", "Фундучное", "Кокосовое"]
MATCHA = ["Зелёная", "Синяя", "Ходзича", "Манго"]
TEAS = ["Чёрный", "Чабрец", "Бергамот", "Каркаде", "Зелёный", "Жасмин", "Молочный улун"]

S = "syrup"
M = "milk"

AUTUMN = {"pending": True}

MENU = [
    ("Осеннее меню", "🍂", [
        ("Латте «Пряня»", {300: 0, 400: 0}, [S, M], {**AUTUMN, "desc": "Согревающий латте с пряными нотками корицы, имбиря и гвоздики"}),
        ("Латте «Кленовый пекан»", {300: 0, 400: 0}, [S, M], {**AUTUMN, "desc": "Нежный латте с кленовым сиропом и орехом пекан"}),
        ("Чай «Грейпс»", {300: 0, 400: 0}, [], {**AUTUMN, "desc": "Яркий чай с грейпфрутом, лёгкой кислинкой и ароматом цитрусов"}),
        ("Чай «Золотая пора»", {300: 0, 400: 0}, [], {**AUTUMN, "desc": "Душистый чай с яблоком, корицей и мёдом"}),
    ]),
    ("Кофе", "☕", [
        ("Двойной эспрессо", {200: 170}, [S]),
        ("Американо", {200: 180, 300: 210, 400: 240}, [S]),
        ("Флэт-уайт", {200: 240, 300: 280, 400: 320}, [S, M]),
        ("Капучино", {200: 230, 300: 260, 400: 300}, [S, M]),
        ("Латте", {300: 260, 400: 290}, [S, M]),
        ("Раф", {300: 300, 400: 340}, [S, M]),
        ("Моккачино", {300: 290, 400: 330}, [S, M]),
        ("Глясе", {200: 230, 300: 250, 400: 280}, [S]),
    ]),
    ("Авторский кофе", "✨", [
        ("Капучино Сникерс", {300: 310, 400: 370}, [S, M]),
        ("Бамбл апельсиновый", {300: 300, 400: 350}, []),
        ("Арахисовый раф", {300: 350, 400: 400}, [M]),
        ("Кокосовый раф", {300: 350, 400: 400}, [M]),
        ("Медовый раф", {300: 350, 400: 400}, [M]),
        ("Сырный раф", {300: 350, 400: 400}, [M]),
        ("Халва раф", {300: 350, 400: 400}, [M]),
    ]),
    ("Холодный кофе", "🧊", [
        ("Айс латте / капучино", {400: 280, 500: 310}, [S, M]),
        ("Эспрессо тоник", {400: 280, 500: 320}, [S]),
        ("Айс американо", {400: 240}, [S]),
        ("Бамбл-апельсин", {400: 320, 500: 370}, []),
        ("Гранат-грейпфрут", {400: 360, 500: 410}, []),
        ("Аффогато", {250: 210}, [S]),
    ]),
    ("Не кофе", "🍫", [
        ("Горячий шоколад", {200: 250}, [S, M]),
        ("Какао", {200: 160, 300: 180, 400: 220}, [S, M]),
        ("Матча латте", {300: 260, 400: 300}, ["matcha", S, M]),
    ]),
    ("Чай", "🍵", [
        ("Облепиха-апельсин", {300: 230, 400: 290}, []),
        ("Имбирь-лимон", {300: 220, 400: 280}, []),
        ("Ягодный чай", {300: 230, 400: 290}, []),
        ("Чай листовой", {300: 120, 400: 160}, ["tea"]),
        ("Шу пуэр", {300: 180}, []),
    ]),
    ("Лимонады", "🍋", [
        ("Классический лимонад", {400: 240, 500: 270}, []),
        ("Мохито", {400: 280, 500: 320}, []),
        ("Мохито клубника", {400: 300, 500: 340}, []),
        ("Крыжурец", {400: 320, 500: 370}, []),
        ("Айс матча латте", {400: 280, 500: 320}, [S, M]),
    ]),
    ("Милкшейки", "🥤", [
        ("Банановый милкшейк", {400: 320}, [S]),
        ("Клубничный милкшейк", {400: 320}, [S]),
        ("Шоколадный милкшейк", {400: 300}, [S]),
        ("Ягодный милкшейк", {400: 280}, [S]),
        ("Милкшейк Сникерс", {400: 340}, [S]),
    ]),
    ("Смузи", "🍓", [
        ("Ягодный смузи", {400: 320}, []),
        ("Фруктовый смузи", {400: 320}, []),
        ("Зелёный смузи", {400: 340}, []),
    ]),
    ("Свежевыжатые соки", "🍊", [
        ("Апельсиновый сок", {400: 290}, []),
        ("Грейпфрутовый сок", {400: 330}, []),
        ("Яблочный сок", {400: 290}, []),
        ("Морковный сок", {400: 220}, []),
        ("Сельдереевый сок", {400: 330}, []),
        ("Гранатовый сок", {400: 330}, []),
    ]),
    ("Газировка", "🥫", [
        ("Coca-Cola", {330: 0}, [], {"soda": True, "desc": "Банка 0,33 л"}),
        ("Sprite", {330: 0}, [], {"soda": True, "desc": "Банка 0,33 л"}),
        ("Fanta", {330: 0}, [], {"soda": True, "desc": "Банка 0,33 л"}),
    ]),
]

TR = dict(zip(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u", "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"],
))


def slug(text: str) -> str:
    s = "".join(TR.get(ch, ch) for ch in text.lower())
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60]


def volume(ml: int) -> str:
    return f"{ml} мл" if ml % 100 else f"0,{ml // 100} л"


async def group(session, name: str, items: list[str], price: int, min_select: int, max_select: int, sort: int, replace: bool) -> ModifierGroup:
    g = (await session.execute(select(ModifierGroup).where(ModifierGroup.name == name).options(selectinload(ModifierGroup.modifiers)))).scalar_one_or_none()
    if g is None:
        g = ModifierGroup(name=name, modifiers=[])
        session.add(g)
    g.min_select, g.max_select, g.sort_order, g.is_active = min_select, max_select, sort, True
    have = {m.name: m for m in g.modifiers}
    for i, item in enumerate(items):
        m = have.pop(item, None)
        if m is None:
            m = Modifier(name=item)
            g.modifiers.append(m)
        m.price_delta, m.sort_order, m.is_active, m.is_default = price * 100, i, True, min_select > 0 and i == 0
    if replace:
        for m in have.values():
            m.is_active = False
            m.is_default = False
    await session.flush()
    return g


async def run(syrup: int, milk: int, soda: int | None, apply: bool, replace: bool) -> None:
    async with SessionLocal() as session:
        groups = {
            S: await group(session, "Сироп", SYRUPS, syrup, 0, 3, 10, replace),
            M: await group(session, "Альтернативное молоко", MILKS, milk, 0, 1, 5, replace),
            "matcha": await group(session, "Вкус матчи", MATCHA, 0, 1, 1, 1, replace),
            "tea": await group(session, "Сорт чая", TEAS, 0, 1, 1, 1, replace),
        }
        created, updated, pending, keep, keep_cats = 0, 0, [], set(), set()
        for ci, (cname, icon, items) in enumerate(MENU):
            cslug = slug(cname)
            keep_cats.add(cslug)
            cat = (await session.execute(select(Category).where(Category.slug == cslug))).scalar_one_or_none()
            if cat is None:
                cat = Category(name=cname, slug=cslug)
                session.add(cat)
            cat.name, cat.icon, cat.sort_order, cat.is_active = cname, icon, ci, True
            await session.flush()
            for pi, (pname, prices, links, *rest) in enumerate(items):
                opts = rest[0] if rest else {}
                pslug = slug(pname)
                keep.add(pslug)
                if opts.get("soda") and soda is not None:
                    prices = {ml: soda for ml in prices}
                hidden_new = bool(opts.get("pending") or (opts.get("soda") and soda is None))
                sizes = sorted(prices)
                product = (await session.execute(
                    select(Product).where(Product.slug == pslug).options(selectinload(Product.variants), selectinload(Product.modifier_links))
                )).scalar_one_or_none()
                if product is not None and hidden_new:
                    continue
                if product is None:
                    product = Product(slug=pslug, tags=[], variants=[], modifier_links=[])
                    session.add(product)
                    created += 1
                else:
                    updated += 1
                if hidden_new:
                    pending.append(pname)
                product.category_id, product.name, product.sort_order, product.is_active = cat.id, pname, pi, not hidden_new
                product.counts_for_loyalty = product.can_be_gift = not opts.get("soda")
                product.tags = [t for t in (product.tags or []) if t not in ("vegan", "soda")] + (["soda"] if opts.get("soda") else [])
                if opts.get("desc") and not product.description:
                    product.description = opts["desc"]
                by_ml = {v.volume_ml: v for v in product.variants}
                for i, ml in enumerate(sizes):
                    v = by_ml.pop(ml, None)
                    if v is None:
                        v = ProductVariant(volume_ml=ml)
                        product.variants.append(v)
                    v.name, v.price, v.old_price, v.sort_order, v.is_active, v.is_default = volume(ml), prices[ml] * 100, None, i, True, i == len(sizes) - 1
                for v in by_ml.values():
                    v.is_active = False
                    v.is_default = False
                want = [groups[k].id for k in links]
                for link in list(product.modifier_links):
                    if link.group_id not in want:
                        product.modifier_links.remove(link)
                have = {link.group_id: link for link in product.modifier_links}
                for i, gid in enumerate(want):
                    if gid in have:
                        have[gid].sort_order = i
                        have[gid].modifier_ids = None
                    else:
                        product.modifier_links.append(ProductModifierGroup(group_id=gid, sort_order=i))
        hidden = 0
        if replace:
            for p in (await session.execute(select(Product).where(Product.is_active.is_(True)))).scalars():
                if p.slug not in keep:
                    p.is_active = False
                    hidden += 1
            for c in (await session.execute(select(Category).where(Category.is_active.is_(True)))).scalars():
                if c.slug not in keep_cats:
                    c.is_active = False
        await session.flush()
        print(f"Новых позиций: {created}, обновлено цен и объёмов: {updated}")
        if replace:
            print(f"Старых позиций скрыто из меню: {hidden}")
        print(f"Сироп +{syrup} ₽, альтернативное молоко +{milk} ₽" + (f", газировка {soda} ₽" if soda is not None else ""))
        if pending:
            print(f"Добавлены скрытыми, без цены: {', '.join(pending)}. Поставьте цену и включите «Показывать в меню» в админке")
        if apply:
            await session.commit()
            print("Готово, меню обновлено")
        else:
            await session.rollback()
            print("Это проверка, в базе ничего не изменилось. Чтобы залить — добавьте --apply")


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m app.menu_import", description="Заливает меню кофейни с фото")
    p.add_argument("--syrup", type=int, required=True, help="цена сиропа, ₽")
    p.add_argument("--milk", type=int, required=True, help="цена альтернативного молока, ₽")
    p.add_argument("--soda", type=int, help="цена банки газировки, ₽ (без неё газировка добавится скрытой)")
    p.add_argument("--apply", action="store_true", help="сохранить в базу")
    p.add_argument("--replace", action="store_true", help="скрыть из меню позиции, которых нет в этом списке")
    a = p.parse_args()
    asyncio.run(run(a.syrup, a.milk, a.soda, a.apply, a.replace))


if __name__ == "__main__":
    main()
