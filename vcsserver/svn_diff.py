# -*- coding: utf-8 -*-
#
# Copyright (C) 2004-2009 Edgewall Software
# Copyright (C) 2004-2006 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.org/wiki/TracLicense.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://trac.edgewall.org/log/.
#
# Author: Christopher Lenz <cmlenz@gmx.de>

import difflib


def get_filtered_hunks(fromlines, tolines, context=None,
                       ignore_blank_lines=False, ignore_case=False,
                       ignore_space_changes=False):
    """Retrieve differences in the form of `difflib.SequenceMatcher`
    opcodes, grouped according to the ``context`` and ``ignore_*``
    parameters.

    :param fromlines: list of lines corresponding to the old content
    :param tolines: list of lines corresponding to the new content
    :param ignore_blank_lines: differences about empty lines only are ignored
    :param ignore_case: upper case / lower case only differences are ignored
    :param ignore_space_changes: differences in amount of spaces are ignored
    :param context: the number of "equal" lines kept for representing
                    the context of the change
    :return: generator of grouped `difflib.SequenceMatcher` opcodes

    If none of the ``ignore_*`` parameters is `True`, there's nothing
    to filter out the results will come straight from the
    SequenceMatcher.
    """
    hunks = get_hunks(fromlines, tolines, context)
    if ignore_space_changes or ignore_case or ignore_blank_lines:
        hunks = filter_ignorable_lines(hunks, fromlines, tolines, context,
                                       ignore_blank_lines, ignore_case,
                                       ignore_space_changes)
    return hunks


def get_hunks(fromlines, tolines, context=None):
    """Generator yielding grouped opcodes describing differences .

    See `get_filtered_hunks` for the parameter descriptions.
    """
    matcher = difflib.SequenceMatcher(None, fromlines, tolines)
    if context is None:
        return (hunk for hunk in [matcher.get_opcodes()])
    else:
        return matcher.get_grouped_opcodes(context)


def filter_ignorable_lines(hunks, fromlines, tolines, context,
                           ignore_blank_lines, ignore_case,
                           ignore_space_changes):
    """Detect line changes that should be ignored and emits them as
    tagged as "equal", possibly joined with the preceding and/or
    following "equal" block.

    See `get_filtered_hunks` for the parameter descriptions.
    """
    def is_ignorable(tag, fromlines, tolines):
        if tag == 'delete' and ignore_blank_lines:
            if ''.join(fromlines) == '':
                return True
        elif tag == 'insert' and ignore_blank_lines:
            if ''.join(tolines) == '':
                return True
        elif tag == 'replace' and (ignore_case or ignore_space_changes):
            if len(fromlines) != len(tolines):
                return False
            def f(str):
                if ignore_case:
                    str = str.lower()
                if ignore_space_changes:
                    str = ' '.join(str.split())
                return str
            for i in range(len(fromlines)):
                if f(fromlines[i]) != f(tolines[i]):
                    return False
            return True

    hunks = list(hunks)
    opcodes = []
    ignored_lines = False
    prev = None
    for hunk in hunks:
        for tag, i1, i2, j1, j2 in hunk:
            if tag == 'equal':
                if prev:
                    prev = (tag, prev[1], i2, prev[3], j2)
                else:
                    prev = (tag, i1, i2, j1, j2)
            else:
                if is_ignorable(tag, fromlines[i1:i2], tolines[j1:j2]):
                    ignored_lines = True
                    if prev:
                        prev = 'equal', prev[1], i2, prev[3], j2
                    else:
                        prev = 'equal', i1, i2, j1, j2
                    continue
                if prev:
                    opcodes.append(prev)
                opcodes.append((tag, i1, i2, j1, j2))
                prev = None
    if prev:
        opcodes.append(prev)

    if ignored_lines:
        if context is None:
            yield opcodes
        else:
            # we leave at most n lines with the tag 'equal' before and after
            # every change
            n = context
            nn = n + n

            group = []
            def all_equal():
                all(op[0] == 'equal' for op in group)
            for idx, (tag, i1, i2, j1, j2) in enumerate(opcodes):
                if idx == 0 and tag == 'equal': # Fixup leading unchanged block
                    i1, j1 = max(i1, i2 - n), max(j1, j2 - n)
                elif tag == 'equal' and i2 - i1 > nn:
                    group.append((tag, i1, min(i2, i1 + n), j1,
                                  min(j2, j1 + n)))
                    if not all_equal():
                        yield group
                    group = []
                    i1, j1 = max(i1, i2 - n), max(j1, j2 - n)
                group.append((tag, i1, i2, j1, j2))

            if group and not (len(group) == 1 and group[0][0] == 'equal'):
                if group[-1][0] == 'equal': # Fixup trailing unchanged block
                    tag, i1, i2, j1, j2 = group[-1]
                    group[-1] = tag, i1, min(i2, i1 + n), j1, min(j2, j1 + n)
                if not all_equal():
                    yield group
    else:
        for hunk in hunks:
            yield hunk


NO_NEWLINE_AT_END = '\\ No newline at end of file'


def unified_diff(fromlines, tolines, context=None, ignore_blank_lines=0,
                 ignore_case=0, ignore_space_changes=0, lineterm='\n'):
    """
    Generator producing lines corresponding to a textual diff.

    See `get_filtered_hunks` for the parameter descriptions.
    """
    # TODO: johbo: Check if this can be nicely integrated into the matching
    if ignore_space_changes:
        fromlines = [l.strip() for l in fromlines]
        tolines = [l.strip() for l in tolines]

    for group in get_filtered_hunks(fromlines, tolines, context,
                                    ignore_blank_lines, ignore_case,
                                    ignore_space_changes):
        i1, i2, j1, j2 = group[0][1], group[-1][2], group[0][3], group[-1][4]
        if i1 == 0 and i2 == 0:
            i1, i2 = -1, -1  # support for Add changes
        if j1 == 0 and j2 == 0:
            j1, j2 = -1, -1  # support for Delete changes
        yield '@@ -%s +%s @@%s' % (
            _hunk_range(i1 + 1, i2 - i1),
            _hunk_range(j1 + 1, j2 - j1),
            lineterm)
        for tag, i1, i2, j1, j2 in group:
            if tag == 'equal':
                for line in fromlines[i1:i2]:
                    if not line.endswith(lineterm):
                        yield ' ' + line + lineterm
                        yield NO_NEWLINE_AT_END + lineterm
                    else:
                        yield ' ' + line
            else:
                if tag in ('replace', 'delete'):
                    for line in fromlines[i1:i2]:
                        if not line.endswith(lineterm):
                            yield '-' + line + lineterm
                            yield NO_NEWLINE_AT_END + lineterm
                        else:
                            yield '-' + line
                if tag in ('replace', 'insert'):
                    for line in tolines[j1:j2]:
                        if not line.endswith(lineterm):
                            yield '+' + line + lineterm
                            yield NO_NEWLINE_AT_END + lineterm
                        else:
                            yield '+' + line


def _hunk_range(start, length):
    if length != 1:
        return '%d,%d' % (start, length)
    else:
        return '%d' % (start, )
