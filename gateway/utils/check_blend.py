from fastapi import UploadFile


def is_blend_file(filename: str) -> bool:
    return filename.lower().endswith(".blend")


# def is_valid_blend(file: UploadFile) -> bool:
#     file.file.seek(0)
#     header = file.file.read(7)  # Read first 7 bytes
#     file.file.seek(0)  # Reset pointer


#     print("Header (repr):", str(header))

#     return header == b'BLENDER'


def is_valid_blend(file: UploadFile) -> bool:
    file.file.seek(0)
    header = file.file.read(7)
    file.file.seek(0)

    # Case 1: normal .blend
    if header.startswith(b"BLENDER"):
        return True

    # Case 2: gzip compressed .blend
    if header[:2] == b"\x1f\x8b":
        return True

    return False
