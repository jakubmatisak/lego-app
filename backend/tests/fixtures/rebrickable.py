"""Odpovede Rebrickable odpísané z reálneho API, aby testy nešli po sieti.

Dôležité je, že set nevracia názov témy, len ``theme_id``, a že zberateľské
minifigúrky sú samostatné sety v spoločnej téme, nie jeden set s dvanástimi
figúrkami.
"""

# GET /api/v3/lego/sets/10294-1/
SET_TITANIC = {
    "set_num": "10294-1",
    "name": "Titanic",
    "year": 2021,
    "theme_id": 721,
    "num_parts": 9092,
    "set_img_url": "https://cdn.rebrickable.com/media/sets/10294-1/93446.jpg",
    "set_url": "https://rebrickable.com/sets/10294-1/titanic/",
    "last_modified_dt": "2022-06-08T09:20:42.701201Z",
}

# GET /api/v3/lego/themes/{id}/
THEME_ICONS = {"id": 721, "parent_id": None, "name": "Icons"}
THEME_SERIES_26 = {"id": 762, "parent_id": 535, "name": "Series 26 Minifigures"}
THEME_CMF_PARENT = {"id": 535, "parent_id": None, "name": "Collectible Minifigures"}

# GET /api/v3/lego/sets/71046-1/
SET_CMF_MEMBER = {
    "set_num": "71046-1",
    "name": "Spacewalking Astronaut",
    "year": 2024,
    "theme_id": 762,
    "num_parts": 16,
    "set_img_url": "https://cdn.rebrickable.com/media/sets/71046-1/134700.jpg",
}

_MEMBER_NAMES = [
    "Spacewalking Astronaut",
    "Imposter",
    "Alien Tourist",
    "Retro Space Heroine",
    "M-Tron Powerlifter",
    "Nurse Android",
    "Flying Saucer Costume Fan",
    "Ice Planet Explorer",
    "Robot Butler",
    "Alien Beetlezoid",
    "Orion",
    "Blacktron Mutant",
]


def _member(index: int, name: str) -> dict:
    return {
        "set_num": f"71046-{index}",
        "name": name,
        "year": 2024,
        "theme_id": 762,
        "num_parts": 8,
        "set_img_url": f"https://cdn.rebrickable.com/media/sets/71046-{index}/x.jpg",
    }


def _packaging(set_num: str, name: str) -> dict:
    """Sáčky a kompletné sady majú nula dielikov a medzi členov nepatria."""
    return {
        "set_num": set_num,
        "name": name,
        "year": 2024,
        "theme_id": 762,
        "num_parts": 0,
        "set_img_url": f"https://cdn.rebrickable.com/media/sets/{set_num}/box.jpg",
    }


# GET /api/v3/lego/sets/?theme_id=762&page_size=200
# Poradie je zámerne premiešané ako v skutočnej odpovedi.
SETS_IN_SERIES_26 = {
    "count": 16,
    "next": None,
    "previous": None,
    "results": [
        _packaging("6500703-1", "Series 26 - Sealed Box"),
        _packaging("66764-1", "Series 26 Space 6 Pack"),
        _packaging("71046-0", "Series 26 - Random Box"),
        _member(1, _MEMBER_NAMES[0]),
        _member(10, _MEMBER_NAMES[9]),
        _member(11, _MEMBER_NAMES[10]),
        _member(12, _MEMBER_NAMES[11]),
        _packaging("71046-13", "Series 26 - Complete - All Sets"),
        _member(2, _MEMBER_NAMES[1]),
        _member(3, _MEMBER_NAMES[2]),
        _member(4, _MEMBER_NAMES[3]),
        _member(5, _MEMBER_NAMES[4]),
        _member(6, _MEMBER_NAMES[5]),
        _member(7, _MEMBER_NAMES[6]),
        _member(8, _MEMBER_NAMES[7]),
        _member(9, _MEMBER_NAMES[8]),
    ],
}

# GET /api/v3/lego/sets/{num}/minifigs/
MINIFIGS_IN_CMF_MEMBER = {
    "count": 1,
    "results": [
        {
            "id": 1,
            "set_num": "fig-014961",
            "set_name": "Spacewalking Astronaut",
            "quantity": 1,
            "num_parts": 5,
            "set_img_url": "https://cdn.rebrickable.com/media/sets/fig-014961/x.jpg",
        }
    ],
}

NO_MINIFIGS = {"count": 0, "results": []}
