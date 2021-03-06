#!/usr/bin/env python3


# removes comments
# combines adjacent override blocks
# adds timeOffset if given
# removes unused styles
# removes unused event columns
#   Layer - if they are all the same, otherwise may renumber them
#   Start - never
#   End - never
#   Style - never
#   Name - always
#   MarginL - if they are all 0
#   MarginR - if they are all 0
#   MarginV - if they are all 0
#   Effect - always
#   Text - never


import re, sys
from collections import OrderedDict


#                       1, 2, 3,    5, 6, 7,    9, 10, 11
SSA_ALIGNMENT_MAP = [0, 1, 2, 3, 0, 7, 8, 9, 0, 4,  5,  6]
class Style:
	def __init__(self, format, line):
		pieces = line.split(',', len(format) - 1)
		for i, piece in enumerate(pieces):
			setattr(self, format[i], piece.strip())

		# set defaults
		for attr in {'PrimaryColour', 'SecondaryColour', 'TertiaryColour', 'OutlineColour', 'BackColour'}:
			if not hasattr(self, attr):
				setattr(self, attr, '')
			else:
				# apparently the colours could be in decimal format rather than hex?
				# this converts it to hex
				val = getattr(self, attr)
				if not val.startswith('&H'):
					num = int(val,10)
					hexnum = hex(num + (2**32 if num < 0 else 0))[2:].upper()
					if len(hexnum) % 2 == 1:
						hexnum = '0' + hexnum
					setattr(self, attr, '&H' + hexnum.ljust(6,'0'))
		for attr in {'Bold', 'Italic', 'Underline', 'StrikeOut', 'Spacing', 'Angle', 'Outline', 'Shadow', 'MarginL', 'MarginR', 'MarginV'}:
			if not hasattr(self, attr):
				setattr(self, attr, '0')
		if not hasattr(self, 'ScaleX'):
			self.ScaleX = '100'
		if not hasattr(self, 'ScaleY'):
			self.ScaleY = '100'
		if not hasattr(self, 'BorderStyle'):
			self.BorderStyle = '1'

		# normalize Bold, Italic, Underline, and StrikeOut
		if int(self.Bold):
			self.Bold = '1'
		if int(self.Italic):
			self.Italic = '1'
		if int(self.Underline):
			self.Underline = '1'
		if int(self.StrikeOut):
			self.StrikeOut = '1'

		# convert SSAv4 to ASSv4+
		if self.TertiaryColour:
			self.OutlineColour = self.TertiaryColour
			if hasattr(self, 'Alignment'):
				val = int(getattr(self, 'Alignment'))
				setattr(self, 'Alignment', str(SSA_ALIGNMENT_MAP[val]))

	def toStr(self, format):
		return 'Style:' + ','.join(getattr(self, x) for x in format)

OVERRIDE_BLOCK_REGEX = re.compile(r'{[^\\]*([^}]*)}')
TRANSITION_TE_REGEX = re.compile(r'(\\t(?!e)[^\\]*(?:\\[^t][^\\()]*(?:\([^)]*\))?)*)(?:\)[^\\]*|(?=\\t))')
WHITESPACE_AND_PARENTHESES_REGEX = re.compile(r'(?:\\(?:(?:((?:fn|r))\s*([^\\]*))|(?:(i?clip)[\s(]*([^\\)]*)[^\\]*)))?[\s()]*')
REDUNDANT_TE_REGEX = re.compile(r'\\te(\\t|$)')
KARAOKE_REGEX_1 = re.compile(r'\\(?:K|k[fo]?)[\d.]+')
KARAOKE_REGEX_2 = re.compile(r'[^\d.]+')
TRAILING_ZERO_REGEX = re.compile(r'\.\d+')
FONT_SCALE_REGEX = re.compile(r'\\fsc(x|y)([^\\]+)(\\[^t][^\\]+)*?\\fsc(?!\1)[xy]\2')
XYBORD_REGEX = re.compile(r'\\(x|y)bord([^\\]+)(\\[^t][^\\]+)*?\\(?!\1)[xy]bord\2')
ADJACENT_OVERRIDE_BLOCK_REGEX = re.compile(r'({[^}]*)}{([^}]*})')
def combineAdjacentOverrideBlocks(text):
	return ADJACENT_OVERRIDE_BLOCK_REGEX.sub(r'\1\2', ADJACENT_OVERRIDE_BLOCK_REGEX.sub(r'\1\2', text))
COMMA_SPLIT_REGEX = re.compile(r'\s*,\s*')
def removeWhitespaceAndParentheses(match):
	frn, frn_arg, iclip, iclip_arg = match.groups('')
	ret = '\\' if frn or iclip else ''
	if frn:
		ret += frn + frn_arg.strip()
	if iclip:
		ret += iclip + ','.join(COMMA_SPLIT_REGEX.split(iclip_arg.strip()))
	return ret
def simplifyOverridesCallback(match):
	overrides = match[1]

	if not overrides:
		return '{}'

	# Close transitions with \te instead of parentheses.
	overrides = TRANSITION_TE_REGEX.sub(r'\1\\te', overrides);

	# Remove all extraneous whitespace and parentheses.
	# Whitespace must be kept inside:
	# \fn names, \r style names, and \clip and \iclip path code.
	# Parentheses will be allowed in \fn names and \r style names.
	overrides = WHITESPACE_AND_PARENTHESES_REGEX.sub(removeWhitespaceAndParentheses, overrides)

	# Remove redundant \te overrides.
	overrides = REDUNDANT_TE_REGEX.sub(r'\1', overrides)

	# Fix multiple karaoke effects in one override by converting
	# all but the last one into a single \kt override.
	k_overrides = KARAOKE_REGEX_1.findall(overrides)
	if len(k_overrides) > 1:
		kt_sum = sum(float(KARAOKE_REGEX_2.sub('',match)) for match in k_overrides[0:-1])
		pieces = KARAOKE_REGEX_1.split(overrides)
		pieces[-2] += (f'\\kt{kt_sum}' if kt_sum else '') + k_overrides[-1]
		overrides = ''.join(pieces)

	# Remove trailing 0's.
	overrides = TRAILING_ZERO_REGEX.sub(lambda m: m[0].rstrip('0').rstrip('.'), overrides)

	# Combine font scale overrides with the same value into the custom \fsc override.
	overrides = FONT_SCALE_REGEX.sub(r'\\fsc\2\3', overrides)

	# Combine \xbord and \ybord overrides with the same value into the \bord override.
	overrides = XYBORD_REGEX.sub(r'\\bord\2\3', overrides)

	return '{' + overrides + '}'
class Event:
	def __init__(self, format, line):
		# get attributes from line
		pieces = line.split(',', len(format) - 1)
		for i, piece in enumerate(pieces):
			setattr(self, format[i], piece.strip())

		# check for any content
		if not self.Text:
			return

		# fix times
		if '-' in self.End:
			self.End = ''
			return
		if '-' in self.Start:
			self.Start = '0:00:00.00'

		# set defaults
		if not hasattr(self, 'Layer'):
			self.Layer = None
		if not hasattr(self, 'MarginL'):
			self.MarginL = '0'
		if not hasattr(self, 'MarginR'):
			self.MarginR = '0'
		if not hasattr(self, 'MarginV'):
			self.MarginV = '0'

	def simplifyOverrides(self):
		if not self.Text:
			return

		# Remove whitespace at the start and end.
		text = self.Text.strip()

		# Combine adjacent override blocks.
		text = combineAdjacentOverrideBlocks(text)

		# Simplify Overrides
		self.Text = OVERRIDE_BLOCK_REGEX.sub(simplifyOverridesCallback, text)

	def toStr(self, format):
		return 'Dialogue:' + ','.join(getattr(self, x) for x in format)


def getStyleFormat(events, styles):
	temp = ('Name', 'Fontname', 'Fontsize', 'PrimaryColour', 'SecondaryColour', 'OutlineColour', 'BackColour', 'Bold', 'Italic', 'Underline', 'StrikeOut', 'ScaleX', 'ScaleY', 'Spacing', 'Angle', 'BorderStyle', 'Outline', 'Shadow', 'Alignment', 'Justify', 'MarginL', 'MarginR', 'MarginV', 'Encoding', 'Blur')
	attrs = OrderedDict((attr,False) for attr in temp)
	usedStyles = set()

	# check events for used styles
	STYLE_OVERRIDE_REGEX = re.compile(r'\\r([^\\]+)')
	for event in events:
		usedStyles.add(event.Style)
		for style in STYLE_OVERRIDE_REGEX.findall(event.Text):
			style = style.strip()
			usedStyles.add(style)
			if style[0] == '(' and style[-1] == ')':
				style = style[1:-1].strip()
				usedStyles.add(style)

	# mark the styles that are used
	for style in styles:
		if style.Name in usedStyles:
			style.isUsed = True

			# Bold, Italic, Underline, StrikeOut, BorderStyle
			attrs['Bold'] |= style.Bold == '1'
			attrs['Italic'] |= style.Italic == '1'
			attrs['Underline'] |= style.Underline == '1'
			attrs['StrikeOut'] |= style.StrikeOut == '1'
			attrs['BorderStyle'] |= style.BorderStyle != '1'

			# ScaleX, ScaleY
			attrs['ScaleX'] |= float(style.ScaleX) != 100.0
			attrs['ScaleY'] |= float(style.ScaleY) != 100.0

			# Spacing, Angle, Outline, Shadow
			attrs['Spacing'] |= float(style.Spacing) != 0
			attrs['Angle'] |= float(style.Angle) != 0
			attrs['Outline'] |= float(style.Outline) != 0
			attrs['Shadow'] |= float(style.Shadow) != 0

			# Justify
			if hasattr(style, 'Justify'):
				attrs['Justify'] |= int(style.Justify) != 0

			# MarginL, MarginR, MarginV
			attrs['MarginL'] |= float(style.MarginL) != 0
			attrs['MarginR'] |= float(style.MarginR) != 0
			attrs['MarginV'] |= float(style.MarginV) != 0

			# Blur
			if hasattr(style, 'Blur'):
				attrs['Blur'] |= float(style.Blur) != 0
		else:
			style.isUsed = False

	# this is never kept
	attrs['Encoding'] = False

	# these are always kept
	for attr in ('Name', 'Fontname', 'Fontsize', 'PrimaryColour', 'SecondaryColour', 'OutlineColour', 'BackColour', 'Alignment'):
		attrs[attr] = True

	return [attr for attr in attrs if attrs[attr]]

def getEventFormat(events):
	layers = {}
	MarginL = MarginR = MarginV = False

	# check attributes
	layers = {int(event.Layer):0 for event in events if event.Layer != None}
	for event in events:
		MarginL = MarginL or bool(float(event.MarginL))
		MarginR = MarginR or bool(float(event.MarginR))
		MarginV = MarginV or bool(float(event.MarginV))

	# renumber layers
	if len(layers) > 1:
		for i, layer in enumerate(sorted(layers)):
			layers[layer] = i
		for event in events:
			if event.Layer != None:
				event.Layer = str(layers[int(event.Layer)])

	return [x for x in ['Layer' if len(layers) > 1 else '', 'Start', 'End', 'Style', 'MarginL' if MarginL else '', 'MarginR' if MarginR else '', 'MarginV' if MarginV else '', 'Text'] if x]


def convert(lines, offset=0):
	blockNames = {'info', 'styles', 'events', 'fonts', 'aegisub'}
	currentBlock = 'info'
	infoTypes = {'WrapStyle': None, 'PlayResX': None, 'PlayResY': None, 'ScaledBorderAndShadow': None, 'TimeOffset': offset}
	styleFormat = []
	styles = []
	eventFormat = []
	events = []
	fontLines = []

	for line in lines:
		line = line.strip()

		# skip empty lines
		if not line: continue

		# skip comments if not in a font block
		if currentBlock != 'fonts' and line.startswith((';','!:','//')):
			continue


		# line starts a new block
		if line.startswith('[') and (currentBlock != 'fonts' or (currentBlock == 'fonts' and any(c.islower() for c in line))):
			line = line.lower()
			for blockName in blockNames:
				if blockName in line:
					currentBlock = blockName
					break
			else:
				currentBlock = line
				print(currentBlock)
		else:
			if currentBlock == 'info':
				type, value = line.split(':', 1)
				if type in infoTypes:
					if type == 'TimeOffset':
						infoTypes['TimeOffset'] = float(value)
					elif type == 'ScaledBorderAndShadow':
						value = value.strip().lower()
						try:
							if int(value) == 0:
								infoTypes['ScaledBorderAndShadow'] = 0
						except ValueError:
							if value == 'no':
								infoTypes['ScaledBorderAndShadow'] = 0
					else: infoTypes[type] = str(int(value))
			elif currentBlock == 'styles':
				if line.startswith('Format'):
					styleFormat = [piece.strip() for piece in line[7:].split(',')]
				elif line.startswith('Style'):
					styles.append(Style(styleFormat, line[6:]))
			elif currentBlock == 'events':
				if line.startswith('Format'):
					eventFormat = [piece.strip() for piece in line[7:].split(',')]
				elif line.startswith('Dialogue'):
					events.append(Event(eventFormat, line[9:]))
				elif line.startswith(('Comment','comment')):
					pass
				else:
					print(line)
			elif currentBlock == 'fonts':
				fontLines.append(line)
			elif currentBlock == 'aegisub':
				pass
			else:
				print(line)


	# remove events that have no content or occur too early
	events = [event for event in events if event.Text and event.End]

	# simplify event overrides
	for event in events:
		event.simplifyOverrides()


	out = []

	# add info block
	out.append('[Script Info]')
	if infoTypes['WrapStyle'] != None: out.append('WrapStyle:' + infoTypes['WrapStyle'])
	if infoTypes['PlayResX'] != None: out.append('PlayResX:' + infoTypes['PlayResX'])
	if infoTypes['PlayResY'] != None: out.append('PlayResY:' + infoTypes['PlayResY'])
	if infoTypes['ScaledBorderAndShadow'] == 0: out.append('ScaledBorderAndShadow:0')
	if infoTypes['TimeOffset']: out.append('TimeOffset:' + str(infoTypes['TimeOffset']))

	# add style block
	out.append('[V4+ Styles]')
	styleFormat = getStyleFormat(events, styles)
	out.append('Format:' + ','.join(styleFormat))
	out.extend(style.toStr(styleFormat) for style in styles if style.isUsed)

	# add events block
	out.append('[Events]')
	eventFormat = getEventFormat(events)
	out.append('Format:' + ','.join(eventFormat))
	out.extend(event.toStr(eventFormat) for event in events)

	# add fonts block
	if fontLines:
		out.append('[Fonts]')
		out.extend(fontLines)

	return out

if __name__ == '__main__':
	if len(sys.argv) > 1:
		with open(sys.argv[1], encoding='utf8') as file, open(1, 'w', encoding='utf8', closefd=False) as stdout:
			for line in convert([line.strip() for line in file if line], int(sys.argv[2]) if len(sys.argv) > 2 else 0):
				print(line, file=stdout)
