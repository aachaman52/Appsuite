import struct
import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List

def get_accessor_data(accessor_idx: int, json_data: Dict[str, Any], bin_data: bytes) -> List[Any]:
    accessor = json_data["accessors"][accessor_idx]
    if "bufferView" not in accessor:
        # Sparsely populated or empty accessor
        return [0] * accessor["count"]
    
    bv_idx = accessor["bufferView"]
    bv = json_data["bufferViews"][bv_idx]
    
    offset = accessor.get("byteOffset", 0) + bv.get("byteOffset", 0)
    component_type = accessor["componentType"]
    count = accessor["count"]
    type_str = accessor["type"]
    
    # Component type mapping
    fmt_chars = {
        5120: "b",  # BYTE
        5121: "B",  # UNSIGNED_BYTE
        5122: "h",  # SHORT
        5123: "H",  # UNSIGNED_SHORT
        5125: "I",  # UNSIGNED_INT
        5126: "f"   # FLOAT
    }
    
    components = {
        "SCALAR": 1,
        "VEC2": 2,
        "VEC3": 3,
        "VEC4": 4,
        "MAT2": 4,
        "MAT3": 9,
        "MAT4": 16
    }[type_str]
    
    char = fmt_chars[component_type]
    char_size = struct.calcsize(char)
    stride = bv.get("byteStride", char_size * components)
    
    data = []
    for i in range(count):
        elem_offset = offset + i * stride
        elem_fmt = f"<{components}{char}"
        val = struct.unpack_from(elem_fmt, bin_data, elem_offset)
        if components == 1:
            data.append(val[0])
        else:
            data.append(list(val))
    return data

def convert_glb_to_obj(glb_path: Path, out_obj_path: Path) -> Dict[str, Any]:
    """Convert binary GLB file to OBJ + MTL + PNG. Extracts textures and maps them correctly."""
    with open(glb_path, "rb") as f:
        header = f.read(12)
        if len(header) < 12 or header[:4] != b"glTF":
            raise ValueError("Not a valid glTF/GLB file")
        
        # Read chunks
        json_data = None
        bin_data = None
        while True:
            chunk_header = f.read(8)
            if len(chunk_header) < 8:
                break
            chunk_length = int.from_bytes(chunk_header[:4], "little")
            chunk_type = chunk_header[4:]
            chunk_data = f.read(chunk_length)
            if chunk_type == b"JSON":
                json_data = json.loads(chunk_data.decode("utf-8"))
            elif chunk_type in (b"BIN\x00", b"BIN"):
                bin_data = chunk_data

    if not json_data:
        raise ValueError("GLB JSON chunk not found")
    if not bin_data:
        bin_data = b""

    obj_lines = []
    mtl_lines = []
    
    # 1. Extract Images / Textures
    images = json_data.get("images", [])
    texture_files = []
    for img_idx, img in enumerate(images):
        img_name = img.get("name", f"texture_{img_idx}")
        # Sanitize name
        img_name = re.sub(r'[^\w\-_\.]', '_', img_name)
        
        # Determine format extension
        mime = img.get("mimeType", "")
        ext = ".png"
        if "jpeg" in mime or "jpg" in mime:
            ext = ".jpg"
            
        if not img_name.endswith(ext):
            img_name += ext
            
        if "bufferView" in img:
            bv_idx = img["bufferView"]
            bv = json_data["bufferViews"][bv_idx]
            offset = bv.get("byteOffset", 0)
            length = bv["byteLength"]
            img_data = bin_data[offset:offset+length]
            
            img_path = out_obj_path.parent / img_name
            img_path.write_bytes(img_data)
            texture_files.append(img_name)
        elif "uri" in img:
            # If it's a relative path uri, copy it if it exists
            uri = img["uri"]
            src_img = glb_path.parent / uri
            if src_img.exists():
                shutil.copy(src_img, out_obj_path.parent / Path(uri).name)
                texture_files.append(Path(uri).name)
            else:
                texture_files.append(Path(uri).name)
        else:
            texture_files.append(img_name)

    # 2. Write Materials to MTL
    materials = json_data.get("materials", [])
    mtl_name = out_obj_path.stem + ".mtl"
    obj_lines.append(f"mtllib {mtl_name}\n")
    
    mat_to_tex = {}
    for mat_idx, mat in enumerate(materials):
        mat_name = mat.get("name", f"Material_{mat_idx}")
        mat_name = re.sub(r'\s+', '_', mat_name)
        mtl_lines.append(f"newmtl {mat_name}")
        
        # Colors
        pbr = mat.get("pbrMetallicRoughness", {})
        base_color = pbr.get("baseColorFactor", [1.0, 1.0, 1.0, 1.0])
        mtl_lines.append(f"Kd {base_color[0]} {base_color[1]} {base_color[2]}")
        
        # Texture
        if "baseColorTexture" in pbr:
            tex_idx = pbr["baseColorTexture"]["index"]
            textures_list = json_data.get("textures", [])
            if tex_idx < len(textures_list):
                img_idx = textures_list[tex_idx].get("source")
                if img_idx is not None and img_idx < len(texture_files):
                    tex_file = texture_files[img_idx]
                    mtl_lines.append(f"map_Kd {tex_file}")
                    mat_to_tex[mat_name] = tex_file
        mtl_lines.append("")

    # 3. Process Meshes & primitives
    v_offset = 1
    vt_offset = 1
    vn_offset = 1
    
    meshes = json_data.get("meshes", [])
    for mesh_idx, mesh in enumerate(meshes):
        mesh_name = mesh.get("name", f"Mesh_{mesh_idx}")
        mesh_name = re.sub(r'\s+', '_', mesh_name)
        obj_lines.append(f"o {mesh_name}\n")
        
        for prim in mesh.get("primitives", []):
            if "material" in prim:
                mat_idx = prim["material"]
                mat_name = materials[mat_idx].get("name", f"Material_{mat_idx}")
                mat_name = re.sub(r'\s+', '_', mat_name)
                obj_lines.append(f"usemtl {mat_name}\n")
                
            attrs = prim["attributes"]
            positions = get_accessor_data(attrs["POSITION"], json_data, bin_data)
            for v in positions:
                obj_lines.append(f"v {v[0]} {v[1]} {v[2]}\n")
                
            has_uvs = "TEXCOORD_0" in attrs
            if has_uvs:
                uvs = get_accessor_data(attrs["TEXCOORD_0"], json_data, bin_data)
                for uv in uvs:
                    # Invert Y coordinate for OBJ texture coordinates format
                    obj_lines.append(f"vt {uv[0]} {1.0 - uv[1]}\n")
                    
            has_normals = "NORMAL" in attrs
            if has_normals:
                normals = get_accessor_data(attrs["NORMAL"], json_data, bin_data)
                for n in normals:
                    obj_lines.append(f"vn {n[0]} {n[1]} {n[2]}\n")
                    
            if "indices" in prim:
                indices = get_accessor_data(prim["indices"], json_data, bin_data)
            else:
                indices = list(range(len(positions)))
                
            # Face writing
            for i in range(0, len(indices), 3):
                idx = indices[i:i+3]
                if len(idx) < 3:
                    continue
                face_parts = []
                for j in range(3):
                    v_idx = v_offset + idx[j]
                    vt_idx = vt_offset + idx[j] if has_uvs else ""
                    vn_idx = vn_offset + idx[j] if has_normals else ""
                    
                    if vt_idx != "" and vn_idx != "":
                        face_parts.append(f"{v_idx}/{vt_idx}/{vn_idx}")
                    elif vt_idx != "":
                        face_parts.append(f"{v_idx}/{vt_idx}")
                    elif vn_idx != "":
                        face_parts.append(f"{v_idx}//{vn_idx}")
                    else:
                        face_parts.append(f"{v_idx}")
                obj_lines.append(f"f {' '.join(face_parts)}\n")
                
            v_offset += len(positions)
            if has_uvs:
                vt_offset += len(uvs)
            if has_normals:
                vn_offset += len(normals)

    # Write files
    out_obj_path.write_text("".join(obj_lines), encoding="utf-8")
    (out_obj_path.parent / mtl_name).write_text("\n".join(mtl_lines), encoding="utf-8")
    
    return {
        "textures": texture_files,
        "materials": [m.get("name", f"Material_{i}") for i, m in enumerate(materials)],
        "material_to_texture": mat_to_tex
    }
