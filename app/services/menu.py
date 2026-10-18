from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Product, ProductVariant
from app.repositories import CategoryRepository, FavoriteRepository, LocationRepository, ProductRepository, StockRepository
from app.schemas.menu import CategoryCreate, CategoryRead, CategoryUpdate, ModifierGroupRead, ModifierRead, ProductAdminFilter, ProductCreate, ProductRead, ProductShort, ProductUpdate, VariantRead

from .errors import Conflict, NotFound


class MenuService:
    def __init__(self, session: AsyncSession):
        self.categories = CategoryRepository(session)
        self.products = ProductRepository(session)
        self.locations = LocationRepository(session)
        self.stock = StockRepository(session)
        self.favorites = FavoriteRepository(session)
    async def get_product(self,product_id:int)->Product:
        product=await self.products.full(product_id)
        if product is None:
            raise NotFound("Продукт не найден")
        return product
    async def list_categories(self)->list[Category]:
        return await self.categories.list_all()
    async def get_category(self,category_id:int)->Category:
        category=await self.categories.get(category_id)
        if category is None:
            raise NotFound("Категория не найдена")
        return category
    async def create_category(self, data: CategoryCreate) -> Category:
        existing = await self.categories.by_slug(data.slug)
        if existing is not None:
            raise Conflict("Категория с таким адресом уже есть")
        category = await self.categories.create(**data.model_dump())
        return category
    async def delete_category(self, category_id: int) -> None:
        category = await self.get_category(category_id)
        has_products = await self.products.exists(Product.category_id == category_id)
        if has_products:
            raise Conflict("Сначала уберите товары из категории")
        await self.categories.delete(category)
    async def update_category(self, category_id: int, data: CategoryUpdate) -> Category:
        category = await self.get_category(category_id)
        if data.slug is not None and data.slug != category.slug:
            existing = await self.categories.by_slug(data.slug)
            if existing is not None:
                raise Conflict("Категория с таким адресом уже есть")
        await self.categories.update(category, **data.model_dump(exclude_unset=True))
        return category
    async def reorder_categories(self,ids:list[int]):
        await self.categories.reorder(ids)
    async def delete_product(self,product_id:int)->None:
        product=await self.get_product(product_id)
        await self.products.delete(product)
    async def reorder_product(self,ids:list[int])->None:
        await self.products.reorder(ids)
    async def admin_products(self,f:ProductAdminFilter)->tuple[list[Product],int]:
        return await self.products.admin_page(f)
    async def create_product(self,data:ProductCreate)->Product:
        await self.get_category(data.category_id)
        if await self.products.slug_taken(data.slug):
            raise Conflict("Товар с таким адресом уже есть")
        variants=[ProductVariant(**v.model_dump(exclude={"id","sort_order"}),sort_order=i) for i,v in enumerate(data.variants)]
        product=Product(category_id=data.category_id,name=data.name,slug=data.slug,description=data.description,composition=data.composition,image_url=data.image_url,tags=data.tags,counts_for_loyalty=data.counts_for_loyalty,can_be_gift=data.counts_for_loyalty,sort_order=data.sort_order,variants=variants,modifier_links=[])
        await self.products.add(product)
        await self.products.set_modifiers(product,data.modifier_ids)
        product_id=product.id
        self.products.session.expire(product)
        return await self.get_product(product_id)
    async def update_product(self,product_id:int,data:ProductUpdate)->Product:
        product=await self.get_product(product_id)
        fields=data.model_dump(exclude_unset=True,exclude={"variants","modifier_ids"})
        if "category_id" in fields:
            await self.get_category(fields["category_id"])
        if "slug" in fields and fields["slug"]!=product.slug:
            if await self.products.slug_taken(fields["slug"],exclude_id=product_id):
                raise Conflict("Товар с таким адресом уже есть")
        if "counts_for_loyalty" in fields:
            fields["can_be_gift"]=fields["counts_for_loyalty"]
        await self.products.update(product,**fields)
        if data.variants is not None:
            current={v.id:v for v in product.variants}
            new_variants=[]
            for i,v in enumerate(data.variants):
                values=v.model_dump(exclude={"id","sort_order"})
                variant=current.get(v.id) if v.id else None
                if variant is None:
                    variant=ProductVariant(**values)
                else:
                    for key,value in values.items():
                        setattr(variant,key,value)
                variant.sort_order=i
                new_variants.append(variant)
            product.variants[:]=new_variants
        if data.modifier_ids is not None:
            await self.products.set_modifiers(product,data.modifier_ids)
        await self.products.session.flush()
        self.products.session.expire(product)
        return await self.get_product(product_id)
    def category_open(self,category:Category,now:time)->bool:
        start,end=category.available_from,category.available_to
        if start is None or end is None:
            return True
        if start<=end:
            return start<=now<end
        return now>=start or now<end
    async def local_now(self,location_id:int)->time:
        location=await self.locations.get(location_id)
        if location is None or not location.is_active:
            raise NotFound("Кофейня не найдена")
        return datetime.now(ZoneInfo(location.timezone)).time()
    async def menu_for_location(self,location_id:int)->list[CategoryRead]:
        now=await self.local_now(location_id)
        stop_products,stop_variants,_=await self.stock.stopped_ids(location_id)
        result=[]
        for category in await self.categories.menu_tree():
            open_now=self.category_open(category,now)
            items=[]
            for p in category.products:
                variants=[v for v in p.variants if v.is_active]
                if not p.is_active or not variants:
                    continue
                available=open_now and p.id not in stop_products and any(v.id not in stop_variants for v in variants)
                items.append(ProductShort(id=p.id,name=p.name,slug=p.slug,description=p.description,image_url=p.image_url,min_price=min(v.price for v in variants),tags=list(p.tags),is_available=available))
            if items:
                result.append(CategoryRead(id=category.id,name=category.name,slug=category.slug,icon=category.icon,image_url=category.image_url,products=items))
        return result
    async def product_for_guest(self,location_id:int,product_id:int,user_id:int|None=None)->ProductRead:
        now=await self.local_now(location_id)
        product=await self.get_product(product_id)
        variants=[v for v in product.variants if v.is_active]
        if not product.is_active or not variants:
            raise NotFound("Продукт не найден")
        stop_products,stop_variants,stop_modifiers=await self.stock.stopped_ids(location_id)
        groups=[]
        for link in product.modifier_links:
            g=link.group
            if not g.is_active:
                continue
            mods=[m for m in g.modifiers if m.is_active and (link.modifier_ids is None or m.id in link.modifier_ids)]
            if not mods:
                continue
            modifiers=[ModifierRead(id=m.id,name=m.name,price_delta=m.price_delta,is_default=m.is_default,is_available=m.id not in stop_modifiers) for m in mods]
            groups.append(ModifierGroupRead(id=g.id,name=g.name,min_select=g.min_select,max_select=min(g.max_select,len(mods)),modifiers=modifiers))
        is_favorite=user_id is not None and product.id in await self.favorites.product_ids(user_id)
        available=self.category_open(product.category,now) and product.id not in stop_products and any(v.id not in stop_variants for v in variants)
        variants_out=[VariantRead(id=v.id,name=v.name,volume_ml=v.volume_ml,price=v.price,old_price=v.old_price,is_default=v.is_default,is_available=v.id not in stop_variants,calories=v.calories,proteins=v.proteins,fats=v.fats,carbs=v.carbs) for v in variants]
        return ProductRead(id=product.id,name=product.name,slug=product.slug,description=product.description,image_url=product.image_url,min_price=min(v.price for v in variants),tags=list(product.tags),is_available=available,composition=product.composition,counts_for_loyalty=product.counts_for_loyalty,can_be_gift=product.can_be_gift,variants=variants_out,modifier_groups=groups,is_favorite=is_favorite)
