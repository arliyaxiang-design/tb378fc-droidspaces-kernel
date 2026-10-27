"""Read-only kernel ABI helpers, using only the Python standard library."""
import struct


def elf_sections(data):
    assert data[:6] == b'\x7fELF\x02\x01', 'Expected ELF64 little endian'
    offset = struct.unpack_from('<Q', data, 40)[0]
    entry_size, count, string_index = struct.unpack_from('<HHH', data, 58)
    headers = [struct.unpack_from('<IIQQQQIIQQ', data, offset + i * entry_size) for i in range(count)]
    header = headers[string_index]
    names = data[header[4]:header[4] + header[5]]
    return {names[h[0]:].split(b'\0', 1)[0].decode(): data[h[4]:h[4] + h[5]]
            for h in headers if h[1] != 8}


def parse_btf(data):
    assert data[:2] == b'\x9f\xeb', 'Expected little-endian BTF'
    header, type_offset, type_length, string_offset, string_length = struct.unpack_from('<IIIII', data, 4)
    strings = data[header + string_offset:header + string_offset + string_length]
    def text(offset):
        return strings[offset:strings.find(b'\0', offset)].decode(errors='replace')
    position = header + type_offset
    end = position + type_length
    types = []
    while position < end:
        name, info, size = struct.unpack_from('<III', data, position)
        position += 12
        kind, count, flag = (info >> 24) & 31, info & 65535, info >> 31
        extra = {1: 4, 2: 0, 3: 12, 4: 12*count, 5: 12*count, 6: 8*count,
                 7: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0, 13: 8*count, 14: 4,
                 15: 12*count, 16: 0, 17: 4, 18: 0, 19: 12*count}[kind]
        members = []
        if kind in (4, 5):
            for i in range(count):
                mn, mt, mo = struct.unpack_from('<III', data, position + 12*i)
                members.append({'name': text(mn), 'type': mt,
                                'bits': mo & 0xffffff if flag else mo,
                                'width': mo >> 24 if flag else 0})
        types.append({'name': text(name), 'kind': kind, 'size': size, 'members': members})
        position += extra
    assert position == end
    return types


STRUCTURES = ('task_struct', 'module', 'cred', 'file', 'inode', 'mm_struct')


def layouts(data):
    types = parse_btf(data)
    def flatten(item, base=0):
        result = {}
        for member in item['members']:
            if member['name']:
                result[member['name']] = {'bits': base + member['bits'], 'width': member['width']}
            else:
                child = types[member['type'] - 1]
                if child['kind'] in (4, 5):
                    result.update(flatten(child, base + member['bits']))
        return result
    result = {}
    for name in STRUCTURES:
        item = next(t for t in types if t['name'] == name and t['kind'] == 4 and t['size'])
        result[name] = {'size': item['size'], 'members': flatten(item)}
    return result


def module_versions(data):
    section = elf_sections(data).get('__versions', b'')
    assert len(section) % 64 == 0, 'Unexpected __versions layout'
    return {section[i+8:i+64].split(b'\0', 1)[0].decode():
            struct.unpack_from('<Q', section, i)[0] for i in range(0, len(section), 64)}


def exported_symbols(path):
    return {parts[1]: int(parts[0], 16) for line in path.read_text().splitlines()
            if len(parts := line.split()) >= 2}
