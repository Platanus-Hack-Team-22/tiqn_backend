# from typing import AsyncGenerator
#
# from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
# from sqlmodel.ext.asyncio.session import AsyncSession
#
# from .config import settings
# from .constants import Environment
#
# DATABASE_URL = settings.DATABASE_URL
#
#
# engine = create_async_engine(
#     str(DATABASE_URL),
#     echo=(True if settings.ENVIRONMENT == Environment.DEVELOPMENT else False),
#     future=True,
# )
#
#
# async def get_session() -> AsyncGenerator[AsyncSession, None]:
#     async_session = async_sessionmaker(
#         engine, class_=AsyncSession, expire_on_commit=False
#     )
#     async with async_session() as session:
#         yield session
