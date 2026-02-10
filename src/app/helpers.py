import zipfile


def enum_candidates(zip_file: zipfile.ZipFile, filter_fn):
    return ((f, zip_file.open(f), zip_file) for f in zip_file.filelist if filter_fn(f.filename))


def enum_package(zip_file: zipfile.ZipFile):
    yield zip_file
    for f in zip_file.filelist:
        if f.filename.lower().endswith(".apk"):
            yield zipfile.ZipFile(zip_file.open(f))


def compare_version(new_version: str, current_version: str) -> bool:
    new_parts = list(map(int, new_version.split(".")))
    cur_parts = list(map(int, current_version.split(".")))
    max_len = max(len(new_parts), len(cur_parts))
    new_parts.extend([0] * (max_len - len(new_parts)))
    cur_parts.extend([0] * (max_len - len(cur_parts)))
    for n, c in zip(new_parts, cur_parts):
        if n > c:
            return True
        elif n < c:
            return False
    return True
