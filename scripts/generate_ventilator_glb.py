import json
import struct


def make_box(min_corner, max_corner):
    x0, y0, z0 = min_corner
    x1, y1, z1 = max_corner
    positions = [
        x0, y0, z0,
        x1, y0, z0,
        x1, y1, z0,
        x0, y1, z0,
        x0, y0, z1,
        x1, y0, z1,
        x1, y1, z1,
        x0, y1, z1,
    ]
    normals = [
        0, 0, -1,
        0, 0, -1,
        0, 0, -1,
        0, 0, -1,
        0, 0, 1,
        0, 0, 1,
        0, 0, 1,
        0, 0, 1,
    ]
    indices = [
        0, 1, 2, 0, 2, 3,
        4, 7, 6, 4, 6, 5,
        4, 0, 3, 4, 3, 7,
        1, 5, 6, 1, 6, 2,
        3, 2, 6, 3, 6, 7,
        4, 5, 1, 4, 1, 0,
    ]
    return positions, normals, indices


body_pos, body_norm, body_idx = make_box([-0.5, -0.25, -0.2], [0.5, 0.45, 0.2])
screen_pos, screen_norm, screen_idx = make_box([-0.33, 0.45, -0.03], [0.33, 0.68, 0.03])
arm_pos, arm_norm, arm_idx = make_box([-0.08, 0.25, 0.2], [0.08, 0.35, 0.5])

all_positions = [body_pos, screen_pos, arm_pos]
all_normals = [body_norm, screen_norm, arm_norm]
all_indices = [body_idx, screen_idx, arm_idx]

buffer = bytearray()
buffer_views = []
accessors = []
primitives = []

for part_idx, (positions, normals, indices) in enumerate(zip(all_positions, all_normals, all_indices)):
    pos_offset = len(buffer)
    for value in positions:
        buffer.extend(struct.pack('<f', value))

    norm_offset = len(buffer)
    for value in normals:
        buffer.extend(struct.pack('<f', value))

    idx_offset = len(buffer)
    for value in indices:
        buffer.extend(struct.pack('<H', value))

    buffer_views.append({
        'buffer': 0,
        'byteOffset': pos_offset,
        'byteLength': len(positions) * 4,
        'target': 34962,
    })
    buffer_views.append({
        'buffer': 0,
        'byteOffset': norm_offset,
        'byteLength': len(normals) * 4,
        'target': 34962,
    })
    buffer_views.append({
        'buffer': 0,
        'byteOffset': idx_offset,
        'byteLength': len(indices) * 2,
        'target': 34963,
    })

    accessors.append({
        'bufferView': part_idx * 3 + 0,
        'componentType': 5126,
        'count': len(positions) // 3,
        'type': 'VEC3',
        'max': [max(positions[i::3]) for i in range(3)],
        'min': [min(positions[i::3]) for i in range(3)],
    })
    accessors.append({
        'bufferView': part_idx * 3 + 1,
        'componentType': 5126,
        'count': len(normals) // 3,
        'type': 'VEC3',
    })
    accessors.append({
        'bufferView': part_idx * 3 + 2,
        'componentType': 5123,
        'count': len(indices),
        'type': 'SCALAR',
    })

    primitives.append({
        'attributes': {
            'POSITION': part_idx * 3 + 0,
            'NORMAL': part_idx * 3 + 1,
        },
        'indices': part_idx * 3 + 2,
        'material': part_idx,
    })

json_obj = {
    'asset': {'version': '2.0', 'generator': 'GitHub Copilot'},
    'scene': 0,
    'scenes': [{'nodes': [0]}],
    'nodes': [{'mesh': 0, 'rotation': [0.4, 0, 0]}],
    'meshes': [{'primitives': primitives}],
    'materials': [
        {'pbrMetallicRoughness': {'baseColorFactor': [0.14, 0.28, 0.55, 1], 'metallicFactor': 0.1, 'roughnessFactor': 0.35}},
        {'pbrMetallicRoughness': {'baseColorFactor': [0.06, 0.08, 0.1, 1], 'metallicFactor': 0.0, 'roughnessFactor': 0.15}},
        {'pbrMetallicRoughness': {'baseColorFactor': [0.18, 0.58, 0.92, 1], 'metallicFactor': 0.08, 'roughnessFactor': 0.32}},
    ],
    'buffers': [{'byteLength': len(buffer)}],
    'bufferViews': buffer_views,
    'accessors': accessors,
}

json_text = json.dumps(json_obj, separators=(',', ':')).encode('utf-8')
json_padding = (4 - (len(json_text) % 4)) % 4
json_text += b' ' * json_padding

bin_padding = (4 - (len(buffer) % 4)) % 4
buffer += b'\x00' * bin_padding

with open('frontend/dashboard/ventilator.glb', 'wb') as f:
    f.write(struct.pack('<I', 0x46546C67))
    f.write(struct.pack('<I', 2))
    f.write(struct.pack('<I', 12 + 8 + len(json_text) + 8 + len(buffer)))
    f.write(struct.pack('<I', len(json_text)))
    f.write(struct.pack('<I', 0x4E4F534A))
    f.write(json_text)
    f.write(struct.pack('<I', len(buffer)))
    f.write(struct.pack('<I', 0x004E4942))
    f.write(buffer)

print('ventilator.glb written', 12 + 8 + len(json_text) + 8 + len(buffer), 'bytes')
