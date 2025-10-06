import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database import get_db, MovieModel
from database.models import CountryModel, GenreModel, ActorModel, LanguageModel
from schemas import MovieListResponseSchema, MovieDetailSchema
from schemas.movies import MovieCreateSchema, MovieUpdateSchema

router = APIRouter()


@router.get("/movies/")
async def get_movies(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=10, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
) -> MovieListResponseSchema:
    total_items = await db.scalar(select(func.count(MovieModel.id)))
    if total_items == 0:
        raise HTTPException(status_code=404, detail="No movies found.")

    total_pages = math.ceil(total_items / per_page)

    if page > total_pages:
        raise HTTPException(status_code=404, detail="No movies found.")

    offset = (page - 1) * per_page
    result = await db.execute(
        select(MovieModel).order_by(MovieModel.id.desc()).offset(offset).limit(per_page)
    )
    movies = result.scalars().all()

    prev_page = (
        f"/theater/movies/?page={page - 1}&per_page={per_page}" if page > 1 else None
    )
    next_page = (
        f"/theater/movies/?page={page + 1}&per_page={per_page}"
        if page < total_pages
        else None
    )

    return MovieListResponseSchema(
        movies=movies,
        prev_page=prev_page,
        next_page=next_page,
        total_pages=total_pages,
        total_items=total_items,
    )


@router.get("/movies/{movie_id}/")
async def get_movie_by_id(
    movie_id: int, db: AsyncSession = Depends(get_db)
) -> MovieDetailSchema:
    result = await db.execute(
        select(MovieModel)
        .options(
            joinedload(MovieModel.country),
            joinedload(MovieModel.genres),
            joinedload(MovieModel.actors),
            joinedload(MovieModel.languages),
        )
        .where(MovieModel.id == movie_id)
    )
    movie = result.unique().scalar_one_or_none()

    if movie is None:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )
    return movie


@router.post("/movies/", status_code=201, response_model=MovieDetailSchema)
async def create_movie(
    movie_data: MovieCreateSchema, db: AsyncSession = Depends(get_db)
):
    existing_movie = await db.scalar(
        select(MovieModel).where(
            MovieModel.name == movie_data.name, MovieModel.date == movie_data.date
        )
    )
    if existing_movie:
        raise HTTPException(
            status_code=409,
            detail=f"A movie with the name '{movie_data.name}' and release date '{movie_data.date}' already exists.",
        )

    country = await db.scalar(
        select(CountryModel).where(CountryModel.code == movie_data.country)
    )
    if not country:
        country = CountryModel(code=movie_data.country, name=None)
        db.add(country)
        await db.flush()

    genres = []
    for genre_name in movie_data.genres:
        genre = await db.scalar(select(GenreModel).where(GenreModel.name == genre_name))
        if not genre:
            genre = GenreModel(name=genre_name)
            db.add(genre)
            await db.flush()
        genres.append(genre)

    actors = []
    for actor_name in movie_data.actors:
        actor = await db.scalar(select(ActorModel).where(ActorModel.name == actor_name))
        if not actor:
            actor = ActorModel(name=actor_name)
            db.add(actor)
            await db.flush()
        actors.append(actor)

    languages = []
    for language_name in movie_data.languages:
        language = await db.scalar(
            select(LanguageModel).where(LanguageModel.name == language_name)
        )
        if not language:
            language = LanguageModel(name=language_name)
            db.add(language)
            await db.flush()
        languages.append(language)

    new_movie = MovieModel(
        name=movie_data.name,
        date=movie_data.date,
        score=movie_data.score,
        overview=movie_data.overview,
        status=movie_data.status,
        budget=movie_data.budget,
        revenue=movie_data.revenue,
        country_id=country.id,
        genres=genres,
        actors=actors,
        languages=languages,
    )

    db.add(new_movie)
    await db.commit()
    await db.refresh(new_movie)

    result = await db.execute(
        select(MovieModel)
        .options(
            joinedload(MovieModel.country),
            joinedload(MovieModel.genres),
            joinedload(MovieModel.actors),
            joinedload(MovieModel.languages),
        )
        .where(MovieModel.id == new_movie.id)
    )
    movie = result.unique().scalar_one()

    return movie


@router.patch("/movies/{movie_id}/", status_code=200)
async def update_movie(
    movie_id: int, movie_data: MovieUpdateSchema, db: AsyncSession = Depends(get_db)
):
    movie = await db.get(MovieModel, movie_id)
    if not movie:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )
    update_data = movie_data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(movie, key, value)
    await db.commit()
    return {"detail": "Movie updated successfully."}


@router.delete("/movies/{movie_id}/", status_code=204)
async def delete_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    movie = await db.get(MovieModel, movie_id)
    if not movie:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )

    await db.delete(movie)
    await db.commit()
    return None
