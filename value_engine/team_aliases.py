# value_engine/team_aliases.py

import logging
import re
import json
from pathlib import Path

logger = logging.getLogger("aliases")

# =====================================================
# DATA (AUTO-LEARNING)
# =====================================================

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

LEARNED_FILE = DATA_DIR / "learned_aliases.json"

if LEARNED_FILE.exists():
    try:
        LEARNED_ALIASES = json.loads(
            LEARNED_FILE.read_text(encoding="utf-8")
        )
    except Exception:
        LEARNED_ALIASES = {}
else:
    LEARNED_ALIASES = {}

# =====================================================
# ❌ NON-MALE FOOTBALL MARKERS (STRICT)
# =====================================================

EXCLUDED_PATTERNS = [
    r"\bwomen\b",
    r"\bfemale\b",
    r"\bgirls\b",
    r"\bfeminino\b",
    r"\bfemenino\b",
    r"\byouth\b",
    r"\breserves\b",
    r"\bu1[789]\b",
    r"\bu2[01]\b",
]

EXCLUDED_RE = re.compile("|".join(EXCLUDED_PATTERNS), re.IGNORECASE)

# =====================================================
# EXPLICIT ALIASES
# =====================================================

TEAM_ALIASES = {
    # 🇬🇧 England
    "manchester united": ["man utd", "man united"],
    "manchester city": ["man city"],
    "tottenham hotspur": ["tottenham", "spurs"],
    "wolverhampton wanderers": ["wolves"],
    "west ham united": ["west ham"],
    "newcastle united": ["newcastle"],
    "nottingham forest": ["nottingham"],

    # 🇪🇸 Spain
    "real madrid": ["real madrid cf"],
    "atletico madrid": ["atlético madrid", "ath madrid"],
    "athletic bilbao": ["athletic club"],
    "real sociedad": ["sociedad"],
    "real betis": ["betis"],

    # 🇮🇹 Italy
    "internazionale": ["inter", "inter milan"],
    "ac milan": ["milan"],
    "juventus": ["juve"],
    "as roma": ["roma"],
    "ss lazio": ["lazio"],
    "napoli": ["ssc napoli"],

    # 🇩🇪 Germany
    "bayern munich": ["bayern münchen"],
    "borussia dortmund": ["dortmund", "bvb"],
    "rb leipzig": ["leipzig"],
    "bayer leverkusen": ["leverkusen"],

    # 🇫🇷 France
    "paris saint germain": ["psg", "paris sg", "paris saint-germain"],
    "olympique lyonnais": ["lyon"],
    "olympique marseille": ["marseille"],
    "as monaco": ["monaco"],

    # 🇵🇹 Portugal
    "benfica": ["sl benfica"],
    "porto": ["fc porto"],
    "sporting cp": ["sporting", "sporting lisbon"],

    # 🇺🇸 MLS
    "los angeles fc": ["lafc"],
    "la galaxy": ["los angeles galaxy"],
    "inter miami": ["inter miami cf"],
    "new york city": ["nycfc"],
    "new york red bulls": ["ny red bulls"],

    # 🇧🇷 Brazil
    "flamengo": ["cr flamengo"],
    "palmeiras": ["se palmeiras"],
    "sao paulo": ["são paulo"],
    "corinthians": ["sc corinthians"],

    # 🇦🇷 Argentina
    "river plate": ["club atletico river plate"],
    "boca juniors": ["boca"],

    # 🇯🇵 Japan
    "urawa reds": ["urawa red diamonds"],
    "kawasaki frontale": ["kawasaki"],

    # 🇰🇷 Korea
    "jeonbuk motors": ["jeonbuk hyundai"],
    "ulsan hyundai": ["ulsan"],

    # 🇦🇺 Australia
    "melbourne victory": ["melbourne v"],
    "melbourne city": ["melb city"],
    "sydney fc": ["sydney"],

    # 🌍 National teams
    "united states": ["usa", "u s a"],
    "south korea": ["korea republic"],
    "czech republic": ["czechia"],
    "england": ["england national team"],
}

# =====================================================
# NORMALIZATION
# =====================================================

def normalize_team(name: str) -> str:
    if not name:
        return ""

    n = name.lower()
    n = re.sub(EXCLUDED_RE, "", n)
    n = re.sub(
        r"\b(fc|cf|sc|afc|club|fk|cd|ud)\b",
        "",
        n,
    )
    n = re.sub(r"[^\w\s]", "", n)
    n = re.sub(r"\s+", " ", n)
    return n.strip()

# =====================================================
# AUTO-LEARNING
# =====================================================

def _save_learned():
    LEARNED_FILE.write_text(
        json.dumps(
            LEARNED_ALIASES,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

def learn_alias(raw: str, canonical: str):
    raw_n = normalize_team(raw)
    if not raw_n or raw_n == canonical:
        return

    if raw_n in LEARNED_ALIASES:
        return

    LEARNED_ALIASES[raw_n] = canonical
    logger.info(f"🧠 Alias learned: '{raw_n}' → '{canonical}'")
    _save_learned()

# =====================================================
# RESOLUTION
# =====================================================

# кешируем нормализованные алиасы
NORMALIZED_ALIAS_MAP = {
    canonical: {normalize_team(a) for a in aliases}
    for canonical, aliases in TEAM_ALIASES.items()
}

def resolve_team_name(name: str) -> str | None:
    """
    Возвращает каноническое имя команды
    или None, если это не мужской футбол
    """

    n = normalize_team(name)

    if not n:
        return None

    # автообученные
    if n in LEARNED_ALIASES:
        return LEARNED_ALIASES[n]

    # явные
    for canonical, alias_set in NORMALIZED_ALIAS_MAP.items():
        if n == canonical:
            return canonical
        if n in alias_set:
            learn_alias(n, canonical)
            return canonical

    # fallback — считаем валидной мужской командой
    return n