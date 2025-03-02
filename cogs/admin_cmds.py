"""Commands for bot admins only."""
from __future__ import annotations

import logging
import os
from logging import Logger
from typing import TYPE_CHECKING, Optional

from discord import app_commands, Interaction, Object, Permissions, Embed, Colour, TextChannel, Forbidden
from discord.ext.commands import Cog
from dotenv import load_dotenv
from sqlalchemy import delete

from consts import COG_NAME_ADMIN_CMDS, LOGGER_NAME_MAIN, LOGGER_NAME_ADMIN_COG, LOGGER_NAME_MANAGER_COG, \
    LOGGER_NAME_USER_COG, LOGGERS_LIST
from model import UsedWordsModel, MemberModel, BlacklistModel, WhitelistModel, ServerConfigModel

if TYPE_CHECKING:
    from main import WordChainBot

load_dotenv()
ADMIN_GUILD_ID = int(os.environ['ADMIN_GUILD_ID'])

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(LOGGER_NAME_ADMIN_COG)


class AdminCommandsCog(Cog, name=COG_NAME_ADMIN_CMDS):

    def __init__(self, bot: WordChainBot) -> None:
        self.bot: WordChainBot = bot
        self.bot.tree.add_command(AdminCommandsCog.PurgeCmdGroup(self))
        self.bot.tree.add_command(AdminCommandsCog.LoggingControlCmdGroup(self))

    # -----------------------------------------------------------------------------------------------------------------

    def cog_load(self) -> None:
        logger.info(f'Cog {self.qualified_name} loaded.')

    # -----------------------------------------------------------------------------------------------------------------

    def cog_unload(self) -> None:
        logger.info('Removing commands...')

        for command in self.bot.tree.get_commands():  # Loop through all commands in the bot
            if command in self.__cog_commands__:  # And remove the ones that are in the specified cog
                self.bot.tree.remove_command(command.name)

        logger.info(f'Cog {self.qualified_name} unloaded.')

    # -----------------------------------------------------------------------------------------------------------------

    @app_commands.command(name='announce', description='Announce something to all servers')
    @app_commands.default_permissions(administrator=True)
    @app_commands.guilds(ADMIN_GUILD_ID)
    @app_commands.describe(msg='The message to announce')
    async def announce(self, interaction: Interaction, msg: str):

        await interaction.response.defer()

        emb: Embed = Embed(title='Announcement from devs', description=msg, colour=Colour.yellow())
        emb.description += f'''
\n*For support and updates, join our Discord server:\nhttps://discord.gg/yhbzVGBNw3*
'''
        count_sent: int = 0
        count_failed: int = 0
        for guild in self.bot.guilds:
            config = self.bot.server_configs[guild.id]

            channel: Optional[TextChannel] = self.bot.get_channel(config.channel_id)
            if channel:
                try:
                    await channel.send(embed=emb)
                    count_sent += 1
                except Forbidden as _:
                    logger.error(f'Failed to send announcement to {guild.name} (ID: {guild.id}) due to missing perms.')
                    count_failed += 1

        emb2: Embed = Embed(title='Announcement status', colour=Colour.yellow(), description='Command completed.')
        emb2.add_field(name='Success', value=f'{count_sent} servers', inline=True)
        emb2.add_field(name='Failed', value=f'{count_failed} servers', inline=True)
        await interaction.followup.send(embed=emb2)

    # ============================================================================================================

    class LoggingControlCmdGroup(app_commands.Group):
        """A group of commands to allow the devs to control logging dynamically without restarting the bot."""

        def __init__(self, cog: AdminCommandsCog):
            super().__init__(name='logging', description='Admin commands for setting the log level',
                             guild_ids=[ADMIN_GUILD_ID], guild_only=True,
                             default_permissions=Permissions(administrator=True))
            self.cog: AdminCommandsCog = cog

        # -----------------------------------------------------------------------------------------------------------

        @app_commands.command(name='set_level', description='Set the log level for a specific/all logger(s)')
        @app_commands.describe(level='The logging level to be set',
                               logger_name='The logger for which the level has to be set')
        @app_commands.choices(level=[
            app_commands.Choice(name='Debug', value=logging.DEBUG),
            app_commands.Choice(name='Info', value=logging.INFO),
            app_commands.Choice(name='Warning', value=logging.WARNING),
            app_commands.Choice(name='Error', value=logging.ERROR),
            app_commands.Choice(name='Critical', value=logging.CRITICAL)
        ])
        @app_commands.choices(logger_name=[
            app_commands.Choice(name='Main', value=LOGGER_NAME_MAIN),
            app_commands.Choice(name='Admin Commands', value=LOGGER_NAME_ADMIN_COG),
            app_commands.Choice(name='Manager Commands', value=LOGGER_NAME_MANAGER_COG),
            app_commands.Choice(name='User Commands', value=LOGGER_NAME_USER_COG),
            app_commands.Choice(name='All', value='all')
        ])
        async def set_log_level(self, interaction: Interaction, logger_name: str, level: int):

            await interaction.response.defer()
            emb: Embed = Embed(title='Log level', colour=Colour.yellow(), description='')

            match logger_name:
                case 'all':
                    for logger_name1 in LOGGERS_LIST:

                        # Retrieve the existing logger; do NOT create a new logger
                        queried_logger: Optional[Logger] = logging.root.manager.loggerDict.get(logger_name1, None)

                        if not queried_logger:
                            emb.description += f'❌ Logger `{logger_name1}` not found.\n'
                            continue

                        queried_logger.setLevel(level)
                        emb.description += (f'✅ Level of logger '
                                            f'`{logger_name1}` set to `{logging.getLevelName(level)}`.\n')
                case _:
                    # Retrieve the existing logger; do NOT create a new logger
                    queried_logger: Optional[logging.Logger] = logging.root.manager.loggerDict.get(logger_name, None)

                    if queried_logger:
                        queried_logger.setLevel(level)
                        emb.description += (f'✅ Level of logger '
                                            f'`{logger_name}` set to `{logging.getLevelName(level)}`.')
                    else:
                        emb.description += f'❌ Logger `{logger_name}` not found.'

            await interaction.followup.send(embed=emb)

        # -----------------------------------------------------------------------------------------------------------

        @app_commands.command(name='turn_off_all', description='Turn off logging completely')
        async def turn_off_all(self, interaction: Interaction):

            await interaction.response.defer()
            emb: Embed = Embed(title='Logging status', colour=Colour.green(), description='')

            for logger_name in LOGGERS_LIST:

                # Retrieve the existing logger; do NOT create a new logger
                queried_logger: Optional[logging.Logger] = logging.root.manager.loggerDict.get(logger_name, None)
                if queried_logger:
                    queried_logger.disabled = True
                    emb.description += f'✅ Disabled logger `{queried_logger.name}`.\n'
                else:
                    emb.description += f'❌ Logger `{logger_name}` not found.\n'

            await interaction.followup.send(embed=emb)

        # -----------------------------------------------------------------------------------------------------------

        @app_commands.command(name='turn_on_all', description='Turn on logging')
        @app_commands.describe(reset_individual_loggers='Whether to reset the log levels of individual loggers')
        async def turn_on_all(self, interaction: Interaction, reset_individual_loggers: bool = True):

            await interaction.response.defer()

            logging.disable(logging.NOTSET)

            emb: Embed = Embed(title='Logging status', colour=Colour.dark_orange(), description='')

            for logger_name in LOGGERS_LIST:

                # Retrieve the existing logger; do NOT create a new logger
                queried_logger: Optional[logging.Logger] = logging.root.manager.loggerDict.get(logger_name, None)
                if queried_logger:
                    queried_logger.disabled = False

                    if reset_individual_loggers:
                        queried_logger.setLevel(logging.INFO)
                        emb.description += f'✅ Enabled logger `{queried_logger.name}` and set level to `INFO`.\n'
                    else:
                        emb.description += f'✅ Enabled logger `{queried_logger.name}`.\n'
                else:
                    emb.description += f'❌ Logger `{logger_name}` not found.\n'

            await interaction.followup.send(embed=emb)

        # -----------------------------------------------------------------------------------------------------------

        @app_commands.command(name='turn_off_specific_logger', description='Turn off a specific logger')
        @app_commands.describe(logger_name='The logger for which the level has to be set')
        @app_commands.choices(logger_name=[
            app_commands.Choice(name='Main', value=LOGGER_NAME_MAIN),
            app_commands.Choice(name='Admin Commands', value=LOGGER_NAME_ADMIN_COG),
            app_commands.Choice(name='Manager Commands', value=LOGGER_NAME_MANAGER_COG),
            app_commands.Choice(name='User Commands', value=LOGGER_NAME_USER_COG)
        ])
        async def turn_off_specific_logger(self, interaction: Interaction, logger_name: str):

            await interaction.response.defer()
            emb: Embed = Embed(title='Specific logger status', description='')

            queried_logger: Optional[logging.Logger] = logging.root.manager.loggerDict.get(logger_name, None)
            if queried_logger:
                queried_logger.disabled = True
                emb.description += f'✅ Disabled logger `{queried_logger.name}`.'
                emb.colour = Colour.green()
            else:
                emb.description += f'❌ Logger `{logger_name}` not found.'
                emb.colour = Colour.red()

            await interaction.followup.send(embed=emb)

        # -----------------------------------------------------------------------------------------------------------

        @app_commands.command(name='turn_on_specific_logger',
                              description='Turns on a specific logger and sets it to INFO by default')
        @app_commands.describe(logger_name='The logger for which the level has to be set',
                               reset_level='Whether the level should be explicitly reset to INFO')
        @app_commands.choices(logger_name=[
            app_commands.Choice(name='Main', value=LOGGER_NAME_MAIN),
            app_commands.Choice(name='Admin Commands', value=LOGGER_NAME_ADMIN_COG),
            app_commands.Choice(name='Manager Commands', value=LOGGER_NAME_MANAGER_COG),
            app_commands.Choice(name='User Commands', value=LOGGER_NAME_USER_COG)
        ])
        async def turn_on_specific_logger(self, interaction: Interaction, logger_name: str, reset_level: bool = False):

            await interaction.response.defer()
            emb: Embed = Embed(title='Specific logger status', description='')

            queried_logger: Optional[logging.Logger] = logging.root.manager.loggerDict.get(logger_name, None)
            if not queried_logger:
                emb.description += f'❌ Logger `{logger_name}` not found.'
                emb.colour = Colour.red()
            else:
                queried_logger.disabled = False
                if reset_level:
                    queried_logger.setLevel(logging.INFO)
                    emb.description += (f'✅ Enabled logger `{queried_logger.name}` & '
                                        f'set to level `{logging.getLevelName(queried_logger.level)}`.')
                else:
                    emb.description += f'✅ Enabled logger `{queried_logger.name}`.'
                emb.colour = Colour.green()

            await interaction.followup.send(embed=emb)

        # -----------------------------------------------------------------------------------------------------------

        @app_commands.command(name='test_logger',
                              description='Tests a specific logger')
        @app_commands.describe(logger_name='The logger for which the level has to be set',
                               level='The logging level to be set (default: INFO)',
                               message='The message to be logged')
        @app_commands.choices(logger_name=[
            app_commands.Choice(name='Main', value=LOGGER_NAME_MAIN),
            app_commands.Choice(name='Admin Commands', value=LOGGER_NAME_ADMIN_COG),
            app_commands.Choice(name='Manager Commands', value=LOGGER_NAME_MANAGER_COG),
            app_commands.Choice(name='User Commands', value=LOGGER_NAME_USER_COG)
        ])
        @app_commands.choices(level=[
            app_commands.Choice(name='Debug', value=logging.DEBUG),
            app_commands.Choice(name='Info', value=logging.INFO),
            app_commands.Choice(name='Warning', value=logging.WARNING),
            app_commands.Choice(name='Error', value=logging.ERROR),
            app_commands.Choice(name='Critical', value=logging.CRITICAL)
        ])
        async def test_loggers(self, interaction: Interaction, logger_name: str, message: str,
                               level: int = logging.INFO):

            await interaction.response.defer()
            emb: Embed = Embed(title='Logging Test', description='')

            queried_logger: Optional[logging.Logger] = logging.root.manager.loggerDict.get(logger_name, None)
            if not queried_logger:
                emb.description += f'❌ Logger `{logger_name}` not found.'
                emb.colour = Colour.red()
            else:
                if queried_logger.disabled:
                    emb.description += f'❌ Logger `{queried_logger.name}` is disabled.'
                    emb.colour = Colour.red()
                else:
                    queried_logger.log(level=level, msg=message)
                    emb.description += (f'✅ Sent message via `{queried_logger.name}` '
                                        f'& at level `{logging.getLevelName(level)}`.')
                    emb.colour = Colour.green()

            await interaction.followup.send(embed=emb)

        # -----------------------------------------------------------------------------------------------------------

        @app_commands.command(name='status',
                              description='Status of a specific/all logger(s)')
        @app_commands.describe(logger_name='The logger for which you want to view the status')
        @app_commands.choices(logger_name=[
            app_commands.Choice(name='Main', value=LOGGER_NAME_MAIN),
            app_commands.Choice(name='Admin Commands', value=LOGGER_NAME_ADMIN_COG),
            app_commands.Choice(name='Manager Commands', value=LOGGER_NAME_MANAGER_COG),
            app_commands.Choice(name='User Commands', value=LOGGER_NAME_USER_COG),
            app_commands.Choice(name='All', value='all')
        ])
        async def logger_status(self, interaction: Interaction, logger_name: str = 'all'):

            await interaction.response.defer()
            emb: Embed = Embed(title='Logger Info', description='', colour=Colour.from_rgb(255, 255, 255))

            match logger_name:
                case 'all':
                    for logger_name1 in LOGGERS_LIST:

                        logger1: Optional[logging.Logger] = logging.root.manager.loggerDict.get(logger_name1, None)
                        emb.description += f'`{logger_name1}`\n'

                        if logger1:
                            emb.description += f'''> Status: {'Disabled' if logger1.disabled else 'Enabled'}
> Level: {logging.getLevelName(logger.level)}\n\n'''
                        else:
                            emb.description += f'❌ Logger not found.\n\n'

                case _:
                    logger1: Optional[logging.Logger] = logging.root.manager.loggerDict.get(logger_name, None)
                    emb.description += f'`{logger_name}`\n'

                    if logger1:
                        emb.description += f'''> Status: {'Disabled' if logger1.disabled else 'Enabled'}
> Level: {logging.getLevelName(logger.level)}\n\n'''
                    else:
                        emb.description += f'❌ Logger not found.\n\n'

            emb.colour = Colour.green()
            await interaction.followup.send(embed=emb)

    # ============================================================================================================

    class PurgeCmdGroup(app_commands.Group):

        def __init__(self, cog: AdminCommandsCog):
            super().__init__(name='purge_data', description='Admin commands for cleaning up the DB',
                             guild_ids=[ADMIN_GUILD_ID], guild_only=True,
                             default_permissions=Permissions(administrator=True))
            self.cog: AdminCommandsCog = cog

        # -----------------------------------------------------------------------------------------------------------

        @app_commands.command(name='server', description='Removes all config data for given guild id.')
        @app_commands.describe(guild_id='ID of the guild to be removed from the DB')
        async def clean_server(self, interaction: Interaction, guild_id: str):

            await interaction.response.defer()

            # cannot use int directly in type annotation, because it would allow just 32-bit integers,
            # but most IDs are 64-bit
            try:
                guild_id_as_number = int(guild_id)
            except ValueError:
                await interaction.followup.send('This is not a valid ID!')
                return

            async with self.cog.bot.db_connection() as connection:
                total_rows_changed = 0

                # delete used words
                stmt = delete(UsedWordsModel).where(UsedWordsModel.server_id == guild_id_as_number)
                result = await connection.execute(stmt)
                total_rows_changed += result.rowcount

                # delete members
                stmt = delete(MemberModel).where(MemberModel.server_id == guild_id_as_number)
                result = await connection.execute(stmt)
                total_rows_changed += result.rowcount

                # delete blacklist
                stmt = delete(BlacklistModel).where(BlacklistModel.server_id == guild_id_as_number)
                result = await connection.execute(stmt)
                total_rows_changed += result.rowcount

                # delete whitelist
                stmt = delete(WhitelistModel).where(WhitelistModel.server_id == guild_id_as_number)
                result = await connection.execute(stmt)
                total_rows_changed += result.rowcount

                # delete config
                if guild_id_as_number in self.cog.bot.server_configs:
                    # just reset the data instead to make sure that every current guild has an existing config
                    config = self.cog.bot.server_configs[guild_id_as_number]
                    config.channel_id = None
                    config.current_count = 0
                    config.current_word = None
                    config.high_score = 0
                    config.used_high_score_emoji = False
                    config.reliable_role_id = None
                    config.failed_role_id = None
                    config.last_member_id = None
                    config.failed_member_id = None
                    config.correct_inputs_by_failed_member = 0

                    total_rows_changed += await config.sync_to_db_with_connection(connection)
                else:
                    stmt = delete(ServerConfigModel).where(ServerConfigModel.server_id == guild_id_as_number)
                    result = await connection.execute(stmt)
                    total_rows_changed += result.rowcount

                await connection.commit()

                if total_rows_changed > 0:
                    await interaction.followup.send(f'Removed data for server {guild_id_as_number}')
                else:
                    await interaction.followup.send(f'No data to remove for server {guild_id_as_number}')

        # ---------------------------------------------------------------------------------------------------------------

        @app_commands.command(name='user', description='Removes all saved data for given user id.')
        @app_commands.describe(user_id='ID of the user to be removed from the DB')
        async def clean_user(self, interaction: Interaction, user_id: str):

            await interaction.response.defer()

            # cannot use int directly in type annotation, because it would allow just 32-bit integers,
            # but most IDs are 64-bit
            try:
                user_id_as_number = int(user_id)
            except ValueError:
                await interaction.followup.send('This is not a valid ID!')
                return

            async with self.cog.bot.db_connection() as connection:
                stmt = delete(MemberModel).where(MemberModel.member_id == user_id_as_number)
                result = await connection.execute(stmt)
                await connection.commit()
                rows_deleted: int = result.rowcount
                if rows_deleted > 0:
                    await interaction.followup.send(f'Removed data for user {user_id_as_number} in {rows_deleted} servers')
                else:
                    await interaction.followup.send(f'No data to remove for user {user_id_as_number}')

# ====================================================================================================================


async def setup(bot: WordChainBot):
    await bot.add_cog(AdminCommandsCog(bot), guild=Object(id=ADMIN_GUILD_ID))
