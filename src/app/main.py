import functools

import starlette_admin
import starlette_auth
import starlette_core
import starlette_file
import uvicorn
from starlette.applications import Starlette
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from app import admin, db, endpoints, handlers, settings

# config
starlette_admin.config.logout_url = "/auth/logout"
starlette_core.config.email_default_from_address = settings.EMAIL_DEFAULT_FROM_ADDRESS
starlette_core.config.email_default_from_name = settings.EMAIL_DEFAULT_FROM_NAME
starlette_core.config.email_host = settings.EMAIL_HOST
starlette_core.config.email_port = settings.EMAIL_PORT
starlette_core.config.email_username = settings.EMAIL_USERNAME
starlette_core.config.email_password = settings.EMAIL_PASSWORD

# file storage
if settings.AWS_ACCESS_KEY_ID:
    starlette_file.StoreManager.register(
        "s3",
        functools.partial(
            starlette_file.S3Store,
            settings.AWS_BUCKET,
            settings.AWS_ACCESS_KEY_ID,
            str(settings.AWS_SECRET_ACCESS_KEY),
            settings.AWS_REGION,
            acl="private",
        ),
        default=True,
    )

# base app
app = Starlette(debug=settings.DEBUG)

# routes
app.add_route("/", endpoints.Home, methods=["GET"], name="home")

# sub apps
app.mount(path="/admin", app=admin.adminsite, name=admin.adminsite.name)
app.mount(path="/auth", app=starlette_auth.app, name="auth")

# static app
app.mount(
    path="/static",
    app=StaticFiles(directory="static", packages=["starlette_admin"]),
    name="static",
)

# middleware
app.add_middleware(AuthenticationMiddleware, backend=starlette_auth.ModelAuthBackend())
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
app.add_middleware(CORSMiddleware, allow_origins=settings.ALLOWED_HOSTS)
app.add_middleware(starlette_core.middleware.DatabaseMiddleware)

# exception handlers
app.add_exception_handler(404, handlers.not_found)
app.add_exception_handler(500, handlers.server_error)

# sentry
if settings.SENTRY_DSN:
    try:
        from sentry_asgi import SentryMiddleware
        import sentry_sdk

        sentry_sdk.init(str(settings.SENTRY_DSN))
        app = SentryMiddleware(app)
    except ImportError:
        pass

# load the app
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, debug=settings.DEBUG)
