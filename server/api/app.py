from fastapi import FastAPI

from api.db import lifespan
from api.routers.categories import router as categories_router
from api.routers.posts import router as posts_router
from api.routers.root import router as root_router
from api.routers.tags import router as tags_router
from api.routers.uploads import router as uploads_router

app = FastAPI(lifespan=lifespan)

app.include_router(root_router)
app.include_router(posts_router)
app.include_router(tags_router)
app.include_router(categories_router)
app.include_router(uploads_router)
