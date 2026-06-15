from fastapi import FastAPI

from app.routers import artists, albums, tracks, genres, search, playlists, auth, scanner, discover, compilations, import_music, credits, users
from app.routers import map as map_router

app = FastAPI(title="Calliope", version="2.0.0")

app.include_router(artists.router)
app.include_router(albums.router)
app.include_router(tracks.router)
app.include_router(genres.router)
app.include_router(search.router)
app.include_router(playlists.router)
app.include_router(auth.router)
app.include_router(scanner.router)
app.include_router(discover.router)
app.include_router(compilations.router)
app.include_router(import_music.router)
app.include_router(credits.router)
app.include_router(users.router)
app.include_router(map_router.router)


@app.get("/health")
def health():
    return {"status": "ok"}
