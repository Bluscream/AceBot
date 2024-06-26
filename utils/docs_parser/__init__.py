import os
import json
import shutil
import aiohttp
import logging

from zipfile import ZipFile

from .handlers import *

DOCS_URL = 'https://www.autohotkey.com/docs/'
EXTRACT_TO = 'data'
DOCS_BASE = f'{EXTRACT_TO}/AutoHotkey_L-Docs-master'
DOCS_FOLDER = f'{DOCS_BASE}/docs'
DOWNLOAD_FILE = f'{EXTRACT_TO}/docs.zip'
DOWNLOAD_LINK = 'https://github.com/Lexikos/AutoHotkey_L-Docs/archive/master.zip'

log = logging.getLogger(__name__)


ALIASES = {
	'commands/For.htm': ['For'],
	'commands/IfExpression.htm': ['If'],
	'misc/EscapeChar.htm': ['EscapeChar'],
	'Hotstrings.htm': ['hotstrings'],
}


class DocsAggregator:
	def __init__(self):
		self.force_names = list()
		self.fill_names = list()
		self.entries = list()

	async def __aiter__(self):
		for entry in self.entries:
			yield entry

	def name_check(self, orig_name, force=False):
		name = orig_name.lower()

		if name in self.force_names:
			return False

		if name in self.fill_names:
			if force:
				self.force_names.append(name)
				self.fill_names.remove(name)

				for entry in self.entries:
					for entry_name in entry['names']:
						if entry_name.lower() == name:
							entry['names'].remove(entry_name)
							return True

			else:
				return False

		if force:
			self.force_names.append(name)
		else:
			self.fill_names.append(name)
		return True

	def get_entry_by_page(self, page):
		for entry in self.entries:
			if entry['page'] == page:
				return entry

		return None

	def treat_name(self, name):
		if name.endswith('()'):
			return name[:-2]

		return name

	def add_entry(self, entry):
		if entry.get('desc', None) is None:
			return

		names = list()
		force_names = entry.get('force_names')
		fill_names = entry.get('fill_names')
		entry['main'] = force_names[0] if force_names else fill_names[0]

		for append_page, append_list in ALIASES.items():
			if entry['page'] == append_page:
				for name_to_add in append_list:
					force_names.append(name_to_add)
			else:
				for name_to_add in append_list:
					if name_to_add in force_names:
						force_names.remove(name_to_add)
					if name_to_add in fill_names:
						fill_names.remove(name_to_add)

		for name in force_names:
			name = self.treat_name(name)
			if name not in names and self.name_check(name, force=True):
				names.append(name)

		for name in fill_names:
			name = self.treat_name(name)
			if name not in names and self.name_check(name):
				names.append(name)

		entry['names'] = names

		if entry['page'] is None:
			similar_entry = None
		else:
			similar_entry = self.get_entry_by_page(entry['page'])

		if similar_entry is None:
			self.entries.append(entry)
		else:
			for name in filter(lambda name: name not in similar_entry['names'], entry['names']):
				similar_entry['names'].append(name)


def build_docs():
	aggregator = DocsAggregator()
	BaseParser.DOCS_URL = DOCS_URL
	BaseParser.DOCS_FOLDER = DOCS_FOLDER

	parsers = (
		HeadersParser('commands/Math.htm'),
		HeadersParser('commands/ListView.htm'),
		HeadersParser('commands/TreeView.htm'),
		HeadersParser('commands/Gui.htm', prefix='Gui: '),
		HeadersParser('commands/Menu.htm', prefix='Menu: '),
		GuiControlParser('commands/GuiControls.htm', postfix=' Control'),
		HeadersParser('objects/Functor.htm'),
		MethodListParser('objects/File.htm'),
		MethodListParser('objects/Func.htm'),
		MethodListParser('objects/Object.htm'),
		EnumeratorParser('objects/Enumerator.htm'),
		HeadersParser('KeyList.htm'),
		HeadersParser('Functions.htm'),
		VariablesParser('Functions.htm'),
		HeadersParser('Hotkeys.htm'),
		VariablesParser('Hotkeys.htm'),
		HeadersParser('Variables.htm', ignores=['Loop']),
		VariablesParser('Variables.htm'),
		HeadersParser('Objects.htm'),
		HeadersParser('Program.htm'),
		HeadersParser('FAQ.htm'),
		HeadersParser('Scripts.htm'),
		HeadersParser('Concepts.htm'),
		HeadersParser('HotkeyFeatures.htm'),
		HeadersParser('Language.htm'),
		HeadersParser('Tutorial.htm'),
		HeadersParser('AHKL_DBGPClients.htm'),
		HeadersParser('AHKL_Features.htm'),
		VariablesParser('AHKL_Features.htm'),
	)

	for file in sorted(os.listdir('{}/commands'.format(DOCS_FOLDER))):
		if file.endswith('.htm'):
			for entry in CommandParser('commands/{}'.format(file)).run():
				aggregator.add_entry(entry)

	for parser in parsers:
		for entry in parser.run():
			aggregator.add_entry(entry)

	for file in sorted(os.listdir('{}/misc'.format(DOCS_FOLDER))):
		if file.endswith('.htm'):
			for entry in HeadersParser('misc/{}'.format(file), ignores=['PostExec']).run():
				aggregator.add_entry(entry)

	parsers[0].page = DOCS_URL

	with open(f'{DOCS_FOLDER}/static/source/data_index.js') as f:
		j = json.loads(f.read()[12:-2])
		for line in j:
			name, page, *junk = line
			name = aggregator.treat_name(name)

			if '#' in page:
				page_base, offs = page.split('#')
			else:
				page_base, offs = page, None

			with open(f'{DOCS_FOLDER}/{page_base}') as f:
				bs = BeautifulSoup(f.read(), 'html.parser')

				p = bs.find('p') if offs is None else bs.find(True, id=offs)
				desc = None if p is None else parsers[0].pretty_desc(p)

			fill_names = parsers[0]._string_as_names(name)

			aggregator.add_entry(
				dict(force_names=list(), fill_names=fill_names, page=page, desc=desc)
			)

	return aggregator


async def parse_docs(on_update, fetch=True, loop=None):
	if fetch:
		await on_update('Downloading...')

		# delete old stuff
		try:
			os.remove(DOWNLOAD_FILE)
		except FileNotFoundError:
			pass

		shutil.rmtree(DOCS_BASE, ignore_errors=True)

		# fetch docs package
		async with aiohttp.ClientSession() as session:
			async with session.get(DOWNLOAD_LINK) as resp:
				if resp.status != 200:
					await on_update('download failed.')
					return

				with open(DOWNLOAD_FILE, 'wb') as f:
					f.write(await resp.read())

		# and extract it
		zip_ref = ZipFile(DOWNLOAD_FILE, 'r')
		zip_ref.extractall(EXTRACT_TO)
		zip_ref.close()

	await on_update('Building...')

	aggregator = await loop.run_in_executor(None, build_docs)

	await on_update('List built. Total names: {} Unique entries: {}\n'.format(
		sum(len(entry['names']) for entry in aggregator.entries),
		len(aggregator.entries)
	))

	return aggregator
