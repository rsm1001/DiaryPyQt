#!/usr/bin/env python3
"""
Simple PO to MO compiler
"""
import struct
import sys
import os

def unescape(s):
    """Unescape PO file string"""
    return s.replace('\\"', '"').replace('\\\\', '\\').replace('\\n', '\n')

def escape(s):
    """Escape string for MO file"""
    return s.replace('\\', '\\\\').replace('\x04', '\\x04').replace('\x00', '\\x00')

def compile_po_to_mo(po_path, mo_path):
    """Compile PO file to MO file"""
    msgs = {}

    with open(po_path, 'r', encoding='utf-8') as f:
        content = f.read()

    msgctxt = None
    msgid = None
    msgstr = None
    in_msgid = False
    in_msgstr = False

    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('#'):
            continue
        if line.startswith('msgctxt '):
            msgctxt = unescape(line[8:].strip('"'))
            msgid = None
            msgstr = None
        elif line.startswith('msgid '):
            if msgid is not None and msgstr is not None:
                key = (msgctxt or '', msgid)
                if msgid is not None:
                    msgs[key] = msgstr
            msgid = unescape(line[6:].strip('"'))
            msgstr = None
            in_msgid = True
            in_msgstr = False
        elif line.startswith('msgstr '):
            msgstr = unescape(line[7:].strip('"'))
            in_msgid = False
            in_msgstr = True
        elif line.startswith('"') and line.endswith('"'):
            part = unescape(line[1:-1])
            if in_msgid:
                msgid += part
            elif in_msgstr:
                msgstr += part

    # Add last entry
    if msgid is not None and msgstr is not None:
        key = (msgctxt or '', msgid)
        msgs[key] = msgstr

    # Build MO file
    keys = list(msgs.keys())
    nstrings = len(keys)

    magic = 0x950412de
    version = 0
    # MO header is 7 uint32s = 28 bytes; orig table starts immediately after.
    orig_tab_offset = 28
    trans_tab_offset = orig_tab_offset + nstrings * 8
    hash_tab_offset = trans_tab_offset + nstrings * 8
    hash_tab_size = 0

    # Sort by msgid
    keys.sort(key=lambda x: x[1])

    # Prepare string data
    orig_strings = []
    for ctx, mid in keys:
        if ctx:
            combined = ctx + '\x04' + mid
        else:
            combined = mid
        orig_strings.append((combined, msgs[(ctx, mid)]))

    # Calculate data offsets
    data_offset = hash_tab_offset + hash_tab_size * 4

    ids = []
    strs = []
    for orig, trans in orig_strings:
        orig_bytes = orig.encode('utf-8')
        trans_bytes = trans.encode('utf-8')
        ids.append((len(orig_bytes), data_offset))
        data_offset += len(orig_bytes) + 1
        strs.append((len(trans_bytes), data_offset))
        data_offset += len(trans_bytes) + 1

    # Write MO file
    with open(mo_path, 'wb') as f:
        f.write(struct.pack('I', magic))
        f.write(struct.pack('I', version))
        f.write(struct.pack('I', nstrings))
        f.write(struct.pack('I', orig_tab_offset))
        f.write(struct.pack('I', trans_tab_offset))
        f.write(struct.pack('I', hash_tab_size))
        f.write(struct.pack('I', hash_tab_offset))

        for length, offset in ids:
            f.write(struct.pack('II', length, offset))

        for length, offset in strs:
            f.write(struct.pack('II', length, offset))

        for i in range(hash_tab_size):
            f.write(struct.pack('I', 0))

        for orig, trans in orig_strings:
            f.write(orig.encode('utf-8'))
            f.write(b'\x00')
            f.write(trans.encode('utf-8'))
            f.write(b'\x00')

    print(f'Compiled {po_path} -> {mo_path}')

if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.abspath(__file__))

    compile_po_to_mo(
        os.path.join(base_dir, 'zh_CN/LC_MESSAGES/messages.po'),
        os.path.join(base_dir, 'zh_CN/LC_MESSAGES/messages.mo')
    )

    compile_po_to_mo(
        os.path.join(base_dir, 'en_US/LC_MESSAGES/messages.po'),
        os.path.join(base_dir, 'en_US/LC_MESSAGES/messages.mo')
    )

    print('Done!')
