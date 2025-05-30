from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel
from sqlalchemy import Boolean, Float, Integer, String, update
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

if TYPE_CHECKING:
    from main import WordChainBot  # Thanks to https://stackoverflow.com/a/39757388/8387076


class Base(DeclarativeBase):
    pass


class ServerConfigModel(Base):
    __tablename__ = 'server_config'
    server_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[Optional[int]] = mapped_column(Integer)
    current_count: Mapped[int] = mapped_column(Integer)
    current_word: Mapped[Optional[str]] = mapped_column(String)
    high_score: Mapped[int] = mapped_column(Integer)
    used_high_score_emoji: Mapped[bool] = mapped_column(Boolean)
    reliable_role_id: Mapped[Optional[int]] = mapped_column(Integer)
    failed_role_id: Mapped[Optional[int]] = mapped_column(Integer)
    last_member_id: Mapped[Optional[int]] = mapped_column(Integer)
    failed_member_id: Mapped[Optional[int]] = mapped_column(Integer)
    correct_inputs_by_failed_member: Mapped[int] = mapped_column(Integer)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)


class WordCacheModel(Base):
    __tablename__ = 'word_cache'
    word: Mapped[str] = mapped_column(String, primary_key=True)


class UsedWordsModel(Base):
    __tablename__ = 'used_words'
    server_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word: Mapped[str] = mapped_column(String, primary_key=True)


class MemberModel(Base):
    __tablename__ = 'member'
    server_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    score: Mapped[int] = mapped_column(Integer)
    correct: Mapped[int] = mapped_column(Integer)
    wrong: Mapped[int] = mapped_column(Integer)
    karma: Mapped[float] = mapped_column(Float)


class BlacklistModel(Base):
    __tablename__ = 'blacklist'
    server_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word: Mapped[str] = mapped_column(String, primary_key=True)


class WhitelistModel(Base):
    __tablename__ = 'whitelist'
    server_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word: Mapped[str] = mapped_column(String, primary_key=True)


class BannedMemberModel(Base):
    __tablename__ = 'banned_member'
    member_id: Mapped[int] = mapped_column(Integer, primary_key=True)


class ServerConfig(BaseModel):
    server_id: int
    channel_id: Optional[int] = None
    current_count: int = 0
    current_word: Optional[str] = None
    high_score: int = 0
    used_high_score_emoji: bool = False
    reliable_role_id: Optional[int] = None
    failed_role_id: Optional[int] = None
    last_member_id: Optional[int] = None
    failed_member_id: Optional[int] = None
    correct_inputs_by_failed_member: int = 0
    is_banned: bool = False

    def fail_chain(self, member_id: int) -> None:
        """
        Resets the stats because a mistake was made.
        """
        self.current_count = 0
        self.failed_member_id = member_id
        self.correct_inputs_by_failed_member = 0
        self.used_high_score_emoji = False

    def update_current(self, member_id: int, current_word: str) -> None:
        """
        Increment the current count.
        """
        # increment current count
        self.current_count += 1
        self.current_word = current_word

        # update current member id
        self.last_member_id = member_id

        # check the high score
        self.high_score = max(self.high_score, self.current_count)

    def reaction_emoji(self) -> str:
        """
        Get the reaction emoji based on the current count.
        """
        special_emojis = {
            100: "💯",
            69: "😏",
            666: "👹",
        }
        if self.current_count == self.high_score:
            if not self.used_high_score_emoji:
                emoji = "🎉"
                self.used_high_score_emoji = True
            else:
                emoji = special_emojis.get(self.current_count, '☑️')
        else:
            emoji = special_emojis.get(self.current_count, '✅')
        return emoji

    def __update_statement(self):
        stmt = update(ServerConfigModel).values(
            channel_id=self.channel_id,
            current_count=self.current_count,
            current_word=self.current_word,
            high_score=self.high_score,
            used_high_score_emoji=self.used_high_score_emoji,
            reliable_role_id=self.reliable_role_id,
            failed_role_id=self.failed_role_id,
            last_member_id=self.last_member_id,
            failed_member_id=self.failed_member_id,
            correct_inputs_by_failed_member=self.correct_inputs_by_failed_member,
            is_banned=self.is_banned
        ).where(ServerConfigModel.server_id == self.server_id)
        return stmt

    async def sync_to_db(self, bot: WordChainBot):
        """
        Synchronizes itself with the DB.
        """
        async with bot.db_connection(locked=True) as connection:
            stmt = self.__update_statement()
            await connection.execute(stmt)
            await connection.commit()

    async def sync_to_db_with_connection(self, connection: AsyncConnection) -> int:
        """
        Synchronizes itself with the DB using an existing connection without committing.
        """
        stmt = self.__update_statement()
        result = await connection.execute(stmt)
        return result.rowcount  # noqa: custom property with memoization which IDEs won't recognize as a property

    class Config:
        from_attributes = True


class Member(BaseModel):
    server_id: int
    member_id: int
    score: int
    correct: int
    wrong: int
    karma: float

    class Config:
        from_attributes = True
