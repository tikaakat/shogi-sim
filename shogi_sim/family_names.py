import random
import string

ALPHABET = string.ascii_uppercase  # A-Z


def assign_initial_family_names(count):
    """初期個体数分、A, B, C... の順に割り当てる（26を超えたらAA, AB...）"""
    names = []
    for i in range(count):
        names.append(_index_to_label(i))
    return names


def _index_to_label(i):
    """0->A, 1->B, ..., 25->Z, 26->AA, 27->AB ... （エクセルの列名と同じ方式）"""
    label = ""
    i += 1
    while i > 0:
        i, rem = divmod(i - 1, 26)
        label = ALPHABET[rem] + label
    return label


def random_immigrant_family_name():
    """移民の開祖名：1文字目は大文字、2文字目は小文字（本流と見分けが付くように）"""
    first = random.choice(ALPHABET)
    second = random.choice(ALPHABET).lower()
    return f"{first}{second}"
