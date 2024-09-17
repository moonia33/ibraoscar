import graphene
from graphene_django import DjangoObjectType
from oscar.apps.catalogue.models import Product, Category, ProductImage
from oscar.apps.partner.models import StockRecord
from django.db.models import Q


class StockRecordType(DjangoObjectType):
    class Meta:
        model = StockRecord
        fields = ('id', 'partner_sku', 'price', 'num_in_stock', 'product_id')


class ProductImageType(DjangoObjectType):
    class Meta:
        model = ProductImage
        fields = ('id', 'original', 'caption')


class ProductType(DjangoObjectType):
    class Meta:
        model = Product
        fields = ('id', 'title', 'description', 'slug',
                  'upc', 'categories', 'images', 'stockrecord', 'date_created')

    stockrecords = graphene.List(StockRecordType)

    def resolve_stockrecords(self, info):
        return self.stockrecords.all()


class CategoryType(DjangoObjectType):
    class Meta:
        model = Category
        fields = ('id', 'name', 'products')


class ProductFilter(graphene.InputObjectType):
    category = graphene.String(required=False)
    price_min = graphene.Float(required=False)
    price_max = graphene.Float(required=False)
    in_stock = graphene.Boolean(required=False)


class Query(graphene.ObjectType):
    all_products = graphene.List(
        ProductType,
        filter=graphene.Argument(ProductFilter),
        order_by=graphene.String()
    )
    product_by_id = graphene.Field(ProductType, id=graphene.Int())
    product_by_slug = graphene.Field(ProductType, slug=graphene.String())
    all_categories = graphene.List(CategoryType)
    category_by_id = graphene.Field(CategoryType, id=graphene.Int())
    category_by_slug = graphene.Field(CategoryType, slug=graphene.String())

    def resolve_all_products(self, info, filter=None, order_by=None):
        query = Product.objects.all()

        if filter:
            if filter.category:
                query = query.filter(categories__name=filter.category)
            if filter.price_min is not None:
                query = query.filter(stockrecords__price__gte=filter.price_min)
            if filter.price_max is not None:
                query = query.filter(stockrecords__price__lte=filter.price_max)
            if filter.in_stock:
                query = query.filter(stockrecords__num_in_stock__gt=0)

        if order_by == "price":
            query = query.order_by('stockrecords__price')
        elif order_by:
            query = query.order_by(order_by)

        return query

    def resolve_product_by_id(self, info, id):
        return Product.objects.get(pk=id)

    def resolve_product_by_slug(self, info, slug):
        return Product.objects.get(slug=slug)

    def resolve_all_categories(self, info):
        return Category.objects.all()

    def resolve_category_by_id(self, info, id):
        return Category.objects.get(pk=id)

    def resolve_category_by_slug(self, info, slug):
        return Category.objects.get(slug=slug)


schema = graphene.Schema(query=Query)
