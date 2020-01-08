import starlette_admin as admin
import starlette_auth as auth
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette_core.middleware import DatabaseMiddleware

from app import db
from app import endpoints
from app import settings
from app.admin import adminsite
from app.globals import templates
from app.handlers import not_found, server_error
from app.middleware import SessionMiddleware
from app.sessions import CookieBackend, DatabaseBackend


admin.config.templates = templates
auth.config.templates = templates

static = StaticFiles(directory="static", packages=["starlette_admin"])

# session_backend = CookieBackend(secret_key=settings.SECRET_KEY, max_age=15)
session_backend = DatabaseBackend(secret_key=settings.SECRET_KEY, max_age=60)

app_middleware = [
    Middleware(DatabaseMiddleware),
    Middleware(CORSMiddleware, allow_origins=settings.ALLOWED_HOSTS),
    Middleware(SessionMiddleware, backend=session_backend, max_age=60),
    Middleware(AuthenticationMiddleware, backend=auth.ModelAuthBackend()),
]

app_routes = [
    Route("/", endpoints.Home, methods=["GET"], name="home"),
    Mount("/admin", app=adminsite, name=adminsite.name),
    Mount("/auth", app=auth.app, name="auth"),
    Mount("/static", app=static, name="static"),
]

app = Starlette(
    debug=settings.DEBUG, middleware=app_middleware, routes=app_routes
)  # type: ignore

app.add_exception_handler(404, not_found)
app.add_exception_handler(500, server_error)

if settings.SENTRY_DSN:
    try:
        from sentry_asgi import SentryMiddleware
        import sentry_sdk

        sentry_sdk.init(str(settings.SENTRY_DSN))
        app = SentryMiddleware(app)
    except ImportError:
        pass
