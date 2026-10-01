"""Diely a alternatívne stavby z Rebrickable v tvare reálnych odpovedí.

Zoznam dielov je stránkovaný (``next`` je celá adresa ďalšej stránky),
náhradné diely majú ``is_spare: true`` a ten istý diel v tej istej farbe
môže prísť ako náhradný aj ako bežný. Obrázok dielu niekedy chýba (null).
"""

SET_NUM = "40597-1"

_BRICK_RED = {
    "id": 4,
    "name": "Red",
    "rgb": "C91A09",
    "is_trans": False,
    "external_ids": {"BrickLink": {"ext_ids": [5], "ext_descrs": [["Red"]]}},
}
_WHITE = {
    "id": 15,
    "name": "White",
    "rgb": "FFFFFF",
    "is_trans": False,
    "external_ids": {"BrickLink": {"ext_ids": [1], "ext_descrs": [["White"]]}},
}
_TRANS_CLEAR = {
    "id": 47,
    "name": "Trans-Clear",
    "rgb": "FCFCFC",
    "is_trans": True,
    "external_ids": {},
}


def _part(part_num: str, name: str, image: str | None) -> dict:
    return {
        "part_num": part_num,
        "name": name,
        "part_cat_id": 11,
        "part_url": f"https://rebrickable.com/parts/{part_num}/",
        "part_img_url": image,
        "external_ids": {"BrickLink": [part_num], "LEGO": [part_num]},
        "print_of": None,
    }


# GET /api/v3/lego/sets/40597-1/parts/?page_size=1000
PARTS_PAGE_1 = {
    "count": 4,
    "next": "https://rebrickable.com/api/v3/lego/sets/40597-1/parts/?page=2&page_size=1000",
    "previous": None,
    "results": [
        {
            "id": 7461238,
            "inv_part_id": 7461238,
            "part": _part(
                "3001",
                "Brick 2 x 4",
                "https://cdn.rebrickable.com/media/parts/elements/300121.jpg",
            ),
            "color": _BRICK_RED,
            "set_num": SET_NUM,
            "quantity": 4,
            "is_spare": False,
            "element_id": "300121",
            "num_sets": 3245,
        },
        {
            "id": 7461239,
            "inv_part_id": 7461239,
            "part": _part(
                "3024",
                "Plate 1 x 1",
                "https://cdn.rebrickable.com/media/parts/elements/302401.jpg",
            ),
            "color": _WHITE,
            "set_num": SET_NUM,
            "quantity": 6,
            "is_spare": False,
            "element_id": "302401",
            "num_sets": 5120,
        },
    ],
}

# GET https://rebrickable.com/api/v3/lego/sets/40597-1/parts/?page=2&page_size=1000
PARTS_PAGE_2 = {
    "count": 4,
    "next": None,
    "previous": "https://rebrickable.com/api/v3/lego/sets/40597-1/parts/?page_size=1000",
    "results": [
        {
            "id": 7461240,
            "inv_part_id": 7461240,
            "part": _part("3024", "Plate 1 x 1", None),
            "color": _WHITE,
            "set_num": SET_NUM,
            "quantity": 1,
            "is_spare": True,
            "element_id": None,
            "num_sets": 5120,
        },
        {
            "id": 7461241,
            "inv_part_id": 7461241,
            "part": _part(
                "98138",
                "Tile Round 1 x 1",
                "https://cdn.rebrickable.com/media/parts/elements/6146226.jpg",
            ),
            "color": _TRANS_CLEAR,
            "set_num": SET_NUM,
            "quantity": 2,
            "is_spare": False,
            "element_id": "6146226",
            "num_sets": 980,
        },
    ],
}

# GET /api/v3/lego/sets/40597-1/alternates/
ALTERNATES = {
    "count": 2,
    "next": None,
    "previous": None,
    "results": [
        {
            "set_num": "MOC-21134",
            "name": "Mini Fire Station",
            "year": 2021,
            "theme_id": 158,
            "num_parts": 118,
            "moc_img_url": "https://cdn.rebrickable.com/media/mocs/moc-21134.jpg",
            "moc_url": "https://rebrickable.com/mocs/MOC-21134/brickdesigner/mini-fire-station/",
            "designer_name": "brickdesigner",
            "designer_url": "https://rebrickable.com/users/brickdesigner/mocs/",
        },
        {
            "set_num": "MOC-30411",
            "name": "Red Truck",
            "year": 2022,
            "theme_id": 158,
            "num_parts": 96,
            "moc_img_url": None,
            "moc_url": "https://rebrickable.com/mocs/MOC-30411/inny/red-truck/",
            "designer_name": "inny",
            "designer_url": "https://rebrickable.com/users/inny/mocs/",
        },
    ],
}

#: Set bez alternatívnych stavieb: Rebrickable vráti prázdny zoznam, nie 404.
NO_ALTERNATES = {"count": 0, "next": None, "previous": None, "results": []}
