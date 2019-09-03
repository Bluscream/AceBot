import re
from bs4 import BeautifulSoup, NavigableString

PREPEND = dict(
	br='\n',  # linebreak
)

WRAP = dict(
	b='**',  # bold
	em='*',  # emphasis
	i='*',  # italics
)

MULTIWRAP = dict(
	li=(' - ', '\n'),  # list item
)

SPACING = dict(
	p=2,
	div=2,
	ul=2
)

CODEBOX_NAMES = ('code', 'pre')


class CreditsEmpty(Exception):
	pass


class Result:
	def __init__(self, credits):
		self.credits = credits
		self.content = ''

	def __str__(self):
		return self.content

	def consume(self, amount: int):
		if amount > self.credits:
			raise CreditsEmpty()

		self.credits -= amount

	def feed(self, amount: int):
		self.credits += amount

	def can_afford(self, *strings):
		return sum(len(part) for part in strings) <= self.credits

	def ensure_spacing(self, spacing=2):
		while self.content.endswith('\n' * (spacing + 1)):
			self.content = self.content[:-1]
			self.feed(1)

		while not self.content.endswith('\n' * spacing):
			self.content += '\n'
			self.consume(1)

	def add(self, string):
		self.content += string

	def add_and_consume(self, string, trunc=False):
		to_consume = len(string)
		do_raise = False

		if trunc is True and to_consume > self.credits:
			to_consume = self.credits
			string = string[:to_consume]
			do_raise = True

		self.consume(to_consume)
		self.add(string)

		if do_raise:
			raise CreditsEmpty()


class HTML2Markdown:
	def __init__(self, escaper=None, big_box=False, lang=None, max_len=2000, base_url=None):
		self.result = None
		self.escaper = escaper
		self.max_len = max_len
		self.base_url = base_url
		self.big_box = big_box
		self.lang = lang

		self.cutoff = '...'

	def convert(self, html, temp_url=None):
		self.result = Result(max(self.max_len, 8) - len(self.cutoff) - 1)

		if temp_url is not None:
			old_url = self.base_url
			self.base_url = temp_url
		else:
			old_url = None

		try:
			self.traverse(BeautifulSoup(html, 'html.parser'))
		except CreditsEmpty:
			if str(self.result).endswith(' '):
				self.result.add(self.cutoff)
			else:
				self.result.add(' ' + self.cutoff)

		if old_url is not None:
			self.base_url = old_url

		ret = str(self.result)
		return ret.strip('\n')

	def traverse(self, tag):
		for node in tag.contents:
			if isinstance(node, NavigableString):
				self.navigable_string(node)
			else:
				if node.name in CODEBOX_NAMES:
					self.codebox(node)
					continue
				elif node.name == 'a':
					self.link(node)
					continue

				back_required = False

				if node.name in PREPEND:
					front, back = PREPEND[node.name], ''

				elif node.name in WRAP:
					wrap_str = WRAP[node.name]
					front, back = wrap_str, wrap_str
					back_required = True

				elif node.name in MULTIWRAP:
					front, back = MULTIWRAP[node.name]

				elif node.name in SPACING:
					self.result.ensure_spacing(SPACING[node.name])
					front, back = '', ''
				else:
					front, back = '', ''

				if not self.result.can_afford(front, back, ' '):
					raise CreditsEmpty()

				self.result.add_and_consume(front)

				# prematurely consume the back characters if it *must* be added later
				if back_required:
					self.result.consume(len(back))

				try:
					self.traverse(node)
				except CreditsEmpty as exc:
					if back_required:
						self.result.add(back)
					raise exc

				if back_required:
					self.result.add(back)
				elif node.name in SPACING:
					self.result.ensure_spacing(SPACING[node.name])
				else:
					self.result.add_and_consume(back)

	def navigable_string(self, node):
		node = str(node)
		if node == '\n':
			return
		self.result.add_and_consume(self.escaper(node) if callable(self.escaper) else node, True)

	def _get_content(self, tag):
		contents = ''
		for node in filter(lambda node: isinstance(node, NavigableString), tag.contents):
			contents += str(node)

		return contents

	def codebox(self, tag):
		front, back = self._codebox_wraps()

		# specific fix for autohotkey rss
		for br in tag.find_all('br'):
			br.replace_with('\n')

		contents = self._get_content(tag)

		self.result.add_and_consume(front + contents + back)

	def _codebox_wraps(self):
		return '```{}\n'.format(self.lang or '') if self.big_box else '`', '\n```\n' if self.big_box else '`'

	def link(self, tag):
		credits = self.result.credits

		link = self._format_link(tag['href'])
		contents = self._get_content(tag)

		full = '[{}]({})'.format(contents, link)

		if link is None:
			self.result.add_and_consume(contents, True)
		elif credits >= len(full):
			self.result.add_and_consume(full)
		elif credits >= len(link) + 5:
			self.result.add_and_consume('[{}]({})'.format(contents[:credits - len(link) - 4], link))
		else:
			self.result.add_and_consume(contents, True)

	def _format_link(self, href):
		if re.match(r'^.+:\/\/', href):
			return href

		if self.base_url is None:
			return None

		if href.startswith('#'):
			return self.base_url + href
		else:
			return '/'.join(self.base_url.split('/')[:-1]) + '/' + href
