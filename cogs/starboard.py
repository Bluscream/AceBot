import discord, asyncio
from discord.ext import commands

from datetime import datetime, timedelta
from sqlalchemy import or_, and_

from .base import TogglableCogMixin
from utils.checks import is_manager
from utils.database import db, StarGuild, StarMessage, Starrers

MEDALS = ['🥇', '🥈', '🥉', '🏅', '🏅']

STAR_EMOJI = '⭐'
MINIMUM_STARS = 4  # people (excluding starrer) must've starred within
PURGE_TIME = timedelta(days=7)  # days, to avoid message being removed.
PURGE_INTERVAL = 60 * 60  # check once an hour
COOLDOWN_PERIOD = timedelta(minutes=10)


class StarError(Exception):
	pass


class Starboard(TogglableCogMixin):
	'''Classic starboard.'''

	def __init__(self, bot):
		super().__init__(bot)
		self.bot.loop.create_task(self.purge_stars())

	async def __local_check(self, ctx):
		return await self._is_used(ctx)

	async def purge_stars(self):
		while True:
			await asyncio.sleep(PURGE_INTERVAL)

			try:
				query = '''
					SELECT id, channel_id, star_message_id
					FROM starmessage
					WHERE (SELECT COUNT(id) from starrers where starrers.star_id=starmessage.id) < $1
					AND starred_at < $2
				'''

				# gets all stars older than a week with less than 4 stars
				star_list = await db.all(query, MINIMUM_STARS, datetime.now() - PURGE_TIME)

				for star in star_list:
					# delete discord starmessage, starrers and starmessage
					await Starrers.delete.where(Starrers.star_id == star[0]).gino.status()
					await StarMessage.delete.where(StarMessage.id == star[0]).gino.status()

					# delete starred message in star channel
					channel = self.bot.get_channel(star[1])
					if channel is None:
						continue

					sg = await StarGuild.query.where(StarGuild.guild_id == channel.guild.id).gino.first()
					if sg is None:
						continue

					star_channel = self.bot.get_channel(sg.channel_id)
					if star_channel is None:
						continue
					try:
						star_message = await star_channel.get_message(star[2])
					except discord.NotFound:
						continue

					try:
						await star_message.delete()
					except discord.ClientException:
						continue

			except (SyntaxError, ValueError, AttributeError) as exc:
				raise exc
			except Exception:
				pass

	async def reaction_checks(self, pl):
		if str(pl.emoji) != STAR_EMOJI or pl.user_id == self.bot.user.id:
			return None

		if not await self.bot.uses_module(pl.guild_id, 'starboard'):
			return None

		channel = self.bot.get_channel(pl.channel_id)
		if channel is None:
			return None

		try:
			message = await channel.get_message(pl.message_id)
		except discord.NotFound:
			return None

		if (datetime.now() - message.created_at).days > 6:
			return None

		return message

	async def on_raw_reaction_add(self, pl):
		message = await self.reaction_checks(pl)
		if message is not None:
			await self._star(message, pl.user_id)

	async def on_raw_reaction_remove(self, pl):
		message = await self.reaction_checks(pl)
		if message is not None:
			await self._unstar(message, pl.user_id)

	async def get_star_channel(self, message):
		# get guild starboard channel
		sg = await StarGuild.query.where(StarGuild.guild_id == message.guild.id).gino.first()
		if sg is None:
			return None

		if message.channel.id == sg.channel_id:
			star_channel = message.channel
		else:
			star_channel = self.bot.get_channel(sg.channel_id)

		return star_channel

	async def get_messages(self, sm, star_channel, message):
		'''Gets both the original and the star message.'''

		if message.id == sm.message_id:
			try:
				star_message = await star_channel.get_message(sm.star_message_id)
			except discord.NotFound:
				raise StarError
		else:
			star_message = message
			channel = self.bot.get_channel(sm.channel_id)
			if channel is None:
				raise StarError
			try:
				message = await channel.get_message(sm.message_id)
			except discord.NotFound:
				raise StarError

		return message, star_message

	async def post_star(self, channel, message):
		content, embed = self.get_emoji_message(message, 1)
		return await channel.send(content=content, embed=embed)

	async def update_star(self, message, star_message, stars):
		content, embed = self.get_emoji_message(message, stars + 1)
		await star_message.edit(content=content, embed=embed)

	async def remove_star(self, sm, star_message=None):
		await sm.delete()

		if star_message is not None:
			await star_message.delete()

	async def _star(self, message, starrer_id):
		star_channel = await self.get_star_channel(message)
		if star_channel is None:
			return

		# find out if it's adding a new star to an existingly starred message, or an original star
		sm = await StarMessage.query.where(
			and_(
				StarMessage.guild_id == message.guild.id,
				or_(
					StarMessage.message_id == message.id,
					StarMessage.star_message_id == message.id
				)
			)
		).gino.first()

		if sm is None:
			# new star. post it and store it

			# unless it's a bot message
			if message.author.bot:
				await message.channel.send(f'Sorry <@{starrer_id}> - no starring of bot messages!')
				return

			if message.author.id == starrer_id:
				await message.channel.send(
					f'Sorry <@{starrer_id}> - you can\'t star your own message!',
					delete_after=20
				)
				return

			# or if the user has starred something the last (timedelta COOLDOWN) time ago
			test = await StarMessage.query.where(
				and_(
					StarMessage.guild_id == message.guild.id,
					and_(
						StarMessage.starrer_id == starrer_id,
						StarMessage.starred_at > (datetime.now() - COOLDOWN_PERIOD)
					)
				)
			).gino.scalar()

			if test is not None:
				await message.channel.send(
					f'<@{starrer_id}> - please wait a bit before starring another message.',
					delete_after=20
				)
				return

			star_message = await self.post_star(star_channel, message)

			await StarMessage.create(
				author_id=message.author.id,
				guild_id=message.guild.id,
				message_id=message.id,
				channel_id=message.channel.id,
				star_message_id=star_message.id,
				starrer_id=starrer_id,
				starred_at=datetime.now(),
			)

			await star_message.add_reaction('\N{WHITE MEDIUM STAR}')
		else:
			# original starrer can't re-star
			if starrer_id == sm.starrer_id:
				return

			exists = await Starrers.query.where(
				and_(
					Starrers.star_id == sm.id,
					Starrers.user_id == starrer_id
				)
			).gino.scalar()

			if exists:
				return

			try:
				message, star_message = await self.get_messages(sm, star_channel, message)
			except StarError:
				return

			await Starrers.create(
				user_id=starrer_id,
				star_id=sm.id
			)

			stars = await db.scalar('SELECT COUNT(id) FROM starrers WHERE star_id=$1', sm.id)

			await self.update_star(message, star_message, stars)

	async def _unstar(self, message, starrer_id):
		sm = await StarMessage.query.where(
			and_(
				StarMessage.guild_id == message.guild.id,
				or_(
					StarMessage.message_id == message.id,
					StarMessage.star_message_id == message.id
				)
			)
		).gino.first()

		if sm is None:
			return

		star_channel = await self.get_star_channel(message)
		if star_channel is None:
			return

		# for later, surprise tool
		orig_message_id = message.id

		try:
			message, star_message = await self.get_messages(sm, star_channel, message)
		except StarError:
			return

		if starrer_id == sm.starrer_id:
			if orig_message_id == sm.message_id:
				# starrer un-starred the original message, delete everything
				await Starrers.delete.where(Starrers.star_id == sm.id).gino.status()
				await sm.delete()
				await star_message.delete()
		else:
			# remove *a* star

			await Starrers.delete.where(
				and_(
					Starrers.star_id == sm.id,
					Starrers.user_id == starrer_id
				)
			).gino.status()

			stars = await db.scalar('SELECT COUNT(id) FROM starrers WHERE star_id=$1', sm.id)

			await self.update_star(message, star_message, stars)

	@commands.command(hidden=True)
	async def star(self, ctx, message_id: int):
		'''Star a message.'''

		raise commands.CommandError('Sorry! Not yet implemented.')

	@commands.command(hidden=True)
	async def unstar(self, ctx, message_id: int):
		'''Unstar a message you previously starred.'''

		raise commands.CommandError('Sorry! Not yet implemented.')

	@commands.group(hidden=True, aliases=['sb'])
	@is_manager()
	async def starboard(self, ctx):
		pass


	@starboard.command()
	async def top(self, ctx):
		'''Lists the most starred authors.'''

		# I think this can be done more cleanly, though my SQL skills are lacking
		# if you have improvements, join here and yell at me :D - https://discord.gg/X7abzRe
		query = '''
			SELECT COALESCE(sm.count + st.count, sm.count), sm.author_id
			FROM
				(SELECT COUNT(id), (SELECT author_id FROM starmessage WHERE starmessage.id=star_id)
				FROM starrers GROUP BY author_id) AS st
			RIGHT JOIN
				(SELECT COUNT(id), author_id FROM starmessage WHERE guild_id=$1 GROUP BY author_id) AS sm
			ON sm.author_id=st.author_id ORDER BY coalesce DESC LIMIT $2;
		'''

		res = await db.all(query, ctx.guild.id, 5)

		e = discord.Embed()
		e.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)

		for idx, (stars, user_id) in enumerate(res):
			e.add_field(
				name=' '.join((MEDALS[idx], ctx.guild.get_member(user_id).display_name)),
				value='\u200b ' * 7 + f'{stars} stars',
				inline=False
			)

		await ctx.send(embed=e)

	@starboard.command()
	async def info(self, ctx, message_id: int):
		'''Info about a starred message.'''

		sm = await StarMessage.query.where(
			and_(
				StarMessage.guild_id == ctx.guild.id,
				or_(
					StarMessage.message_id == message_id,
					StarMessage.star_message_id == message_id
				)
			)
		).gino.first()

		if sm is None:
			raise commands.CommandError('Could not find that starred message.')

		star_ret = await db.all('SELECT COUNT(id) FROM starrers WHERE star_id=$1', sm.id)

		author = ctx.guild.get_member(sm.author_id)
		starrer = ctx.guild.get_member(sm.starrer_id)
		channel = self.bot.get_channel(sm.channel_id)
		stars = star_ret[0][0] + 1

		e = discord.Embed(description='ID: ' + str(sm.message_id))
		e.set_author(name=author.display_name, icon_url=author.avatar_url)

		e.add_field(name='Stars', value=self.star_emoji(stars) + ' ' + str(stars))
		e.add_field(name='Starred in', value='[deleted channel]' if channel is None else channel.mention)
		e.add_field(name='Author', value='[deleted user]' if author is None else author.mention)
		e.add_field(name='Starrer', value='[deleted user]' if starrer is None else starrer.mention)

		e.timestamp = sm.starred_at

		await ctx.send(embed=e)

	@starboard.command()
	@is_manager()
	async def channel(self, ctx, channel: discord.TextChannel = None):
		'''Set the starboard channel.'''

		async def announce():
			await ctx.send(f'Starboard channel set to {channel.mention}')

		sg = await StarGuild.query.where(StarGuild.guild_id == ctx.guild.id).gino.first()

		if channel is None:
			if sg is None:
				await ctx.send('No starboard set.')
			else:
				channel = self.bot.get_channel(sg.channel_id)
				if channel is None:
					await ctx.send('Starboard channel is set, but I didn\'t manage to find the channel.')
				else:
					await announce()
			return
		else:
			if sg is None:
				await StarGuild.create(
					guild_id=ctx.guild.id,
					channel_id=channel.id
				)
			else:
				await sg.update(channel_id=channel.id).apply()

		await announce()

	@starboard.command()
	@is_manager()
	async def delete(self, ctx, message_id: int):
		'''Delete a starred message.'''

		sm = await StarMessage.query.where(
			and_(
				StarMessage.guild_id == ctx.guild.id,
				or_(
					StarMessage.message_id == message_id,
					StarMessage.star_message_id == message_id
				)
			)
		).gino.first()

		if sm is None:
			raise commands.CommandError('Sorry, couldn\'t find that star.')

		star_message_id = sm.star_message_id

		await db.all('DELETE FROM starrers WHERE star_id=$1', sm.id)
		await sm.delete()

		star_channel = await self.get_star_channel(ctx.message)
		if star_channel is None:
			raise commands.CommandError(
				'Database entries deleted but starred message was not, as the starboard channel was not found.'
			)

		try:
			message = await star_channel.get_message(star_message_id)
		except discord.NotFound:
			raise commands.CommandError(
				'Database entries deleted but starred message was not, as the starred message was not found.'
			)

		await message.delete()

		await ctx.send('Star removed successfully.')

	def star_emoji(self, stars):
		'''
		Stolen from Rapptz, thanks!
		https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/stars.py#L141-L149
		'''
		if 5 > stars >= 0:
			return '\N{WHITE MEDIUM STAR}'
		elif 10 > stars >= 5:
			return '\N{GLOWING STAR}'
		elif 25 > stars >= 10:
			return '\N{DIZZY SYMBOL}'
		else:
			return '\N{SPARKLES}'

	def star_gradient_colour(self, stars):
		'''
		Stolen from Rapptz, thanks!
		https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/stars.py#L151-L166
		'''

		p = stars / 13
		if p > 1.0:
			p = 1.0

		red = 255
		green = int((194 * p) + (253 * (1 - p)))
		blue = int((12 * p) + (247 * (1 - p)))
		return (red << 16) + (green << 8) + blue

	def get_emoji_message(self, message, stars):
		'''
		Stolen from Rapptz, thanks!
		https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/stars.py#L168-L193
		'''

		content = f'{self.star_emoji(stars)} **{stars}**'  # \tID: {message.id}

		embed = discord.Embed(description=message.content)
		if message.embeds:
			data = message.embeds[0]
			if data.type == 'image':
				embed.set_image(url=data.url)

		if message.attachments:
			file = message.attachments[0]
			if file.url.lower().endswith(('png', 'jpeg', 'jpg', 'gif', 'webp')):
				embed.set_image(url=file.url)
			else:
				embed.add_field(name='Attachment', value=f'[{file.filename}]({file.url})', inline=False)

		embed.set_author(
			name=message.author.display_name,
			icon_url=message.author.avatar_url_as(format='png'),
			url=f'https://discordapp.com/channels/{message.guild.id}/{message.channel.id}/{message.id}'
		)

		embed.timestamp = message.created_at
		embed.colour = self.star_gradient_colour(stars)
		return content, embed


def setup(bot):
	bot.add_cog(Starboard(bot))
