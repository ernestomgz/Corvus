from __future__ import annotations

import re


_MD_IMAGE = re.compile(r'!\[[^\]]*\]\([^)]+\)')
_HTML_IMAGE = re.compile(r'<img[^>]*src\s*=\s*"[^"]+"[^>]*>', re.IGNORECASE)


def contains_image(markdown: str | None) -> bool:
    if not markdown:
        return False
    return bool(_MD_IMAGE.search(markdown) or _HTML_IMAGE.search(markdown))


def infer_card_type(front_md: str, back_md: str, *, default: str = 'basic') -> str:
    front_image = contains_image(front_md)
    back_image = contains_image(back_md)
    if front_image and not back_image:
        return 'basic_image_front'
    if back_image and not front_image:
        return 'basic_image_back'
    return default
