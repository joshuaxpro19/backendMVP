from fastapi import APIRouter

from app.api.routes import user, auth, service, product, alert, order, scraping, vecinal

apiRouter = APIRouter(prefix="/api", tags=["API"])

apiRouter.include_router(auth.router)
apiRouter.include_router(user.router)
apiRouter.include_router(service.router)
apiRouter.include_router(product.router)
apiRouter.include_router(alert.router)
apiRouter.include_router(order.router)
apiRouter.include_router(scraping.router)
# Contrato que consume el front de Vecinal Solidaria (ver front/API-CONTRATO.md)
apiRouter.include_router(vecinal.router)


@apiRouter.get("/")
def api_root():
    """
    API root — entry point with HATEOAS navigation links (Fielding constraint).
    """
    return {
        "message": "API Vecinal MVP",
        "_links": {
            "auth_register": {"href": "/api/auth/register", "method": "POST"},
            "auth_login":    {"href": "/api/auth/login", "method": "POST"},
            "auth_me":       {"href": "/api/auth/me", "method": "GET"},
            "users":         {"href": "/api/users", "method": "GET"},
            "services":      {"href": "/api/services", "method": "GET"},
            "products":      {"href": "/api/products", "method": "GET"},
            "alerts":        {"href": "/api/alerts", "method": "GET"},
            "my_orders":     {"href": "/api/orders/my-orders", "method": "GET"},
            "scraped_posts": {"href": "/api/scraping/posts", "method": "GET"},
            "scraping_run":  {"href": "/api/scraping/run", "method": "POST"},
        },
    }
