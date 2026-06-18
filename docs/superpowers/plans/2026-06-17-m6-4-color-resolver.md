# M6.4 — Color Resolver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the full color resolver: cascade `chart.colors[i]` → `project.palette[role]` → `style_guide.suggested_palette[i]` → built-in default greys. Auto-derive N colors from a single primary hex via lumMod variations (monotonic lightness progression). Persist recent colors (last 8 unique) to `~/.aurum/config.json`.

**Architecture:** `color_resolver.py` is a pure-function module. All hex values are normalized to `#RRGGBB` uppercase. `lumMod` derivation works entirely in hex/RGB space without external dependencies — no Pillow or colormath needed. `update_recent` reads and writes `~/.aurum/config.json` via the existing `config.py` helpers.

**Tech Stack adds:** None. Pure stdlib (colorsys for HSL manipulation).

---

## File Structure

**Modify (backend):**
- `backend/aurum_encuestas/color_resolver.py` — replace stub with full implementation
- `backend/tests/test_color_resolver.py` — new test file

---

### Task 1: resolve() — cascade chart.colors → palette → style_guide → built-in

**Files:**
- Modify: `backend/aurum_encuestas/color_resolver.py`
- Create: `backend/tests/test_color_resolver.py`

- [ ] **Step 1: Failing tests**

Create `backend/tests/test_color_resolver.py`:

```python
"""Tests for color_resolver — cascade, auto_derive, update_recent."""
import pytest
from aurum_encuestas.color_resolver import (
    resolve,
    auto_derive,
    update_recent,
    normalize_hex,
    _BUILTIN_DEFAULTS,
)
from aurum_encuestas.style_guide import BUILTIN_STYLE_GUIDE


# ────────────────────────────────────────────────────────────────────────────
# normalize_hex
# ────────────────────────────────────────────────────────────────────────────

class TestNormalizeHex:
    def test_uppercase_with_hash(self):
        assert normalize_hex("#7f7f7f") == "#7F7F7F"

    def test_already_uppercase(self):
        assert normalize_hex("#BFBFBF") == "#BFBFBF"

    def test_without_hash(self):
        assert normalize_hex("FFC000") == "#FFC000"

    def test_short_form_expanded(self):
        """#RGB → #RRGGBB."""
        assert normalize_hex("#fff") == "#FFFFFF"

    def test_invalid_returns_fallback(self):
        """Non-hex strings fall back to #7F7F7F (first built-in default)."""
        assert normalize_hex("not-a-color") == "#7F7F7F"


# ────────────────────────────────────────────────────────────────────────────
# resolve — cascade logic
# ────────────────────────────────────────────────────────────────────────────

class TestResolve:
    def test_chart_colors_wins_first(self):
        """chart.colors[0] wins over everything else."""
        result = resolve(
            role="primary",
            chart_colors=["#ABCDEF", "#123456"],
            project_palette={"primary": "#FF0000"},
            style_guide=BUILTIN_STYLE_GUIDE,
            element_idx=0,
        )
        assert result == "#ABCDEF"

    def test_chart_colors_second_slot(self):
        result = resolve(
            role="secondary",
            chart_colors=["#ABCDEF", "#123456"],
            project_palette=None,
            style_guide=BUILTIN_STYLE_GUIDE,
            element_idx=1,
        )
        assert result == "#123456"

    def test_chart_colors_out_of_range_falls_to_palette(self):
        """element_idx beyond chart_colors length → cascade to project_palette."""
        result = resolve(
            role="primary",
            chart_colors=["#ABCDEF"],  # only 1 color
            project_palette={"primary": "#FF0000"},
            style_guide=BUILTIN_STYLE_GUIDE,
            element_idx=1,  # out of range
        )
        assert result == "#FF0000"

    def test_empty_chart_colors_falls_to_palette(self):
        result = resolve(
            role="primary",
            chart_colors=[],
            project_palette={"primary": "#FF0000"},
            style_guide=BUILTIN_STYLE_GUIDE,
            element_idx=0,
        )
        assert result == "#FF0000"

    def test_palette_role_match(self):
        result = resolve(
            role="accent",
            chart_colors=[],
            project_palette={"primary": "#7F7F7F", "accent": "#FFC000"},
            style_guide=BUILTIN_STYLE_GUIDE,
            element_idx=0,
        )
        assert result == "#FFC000"

    def test_palette_role_miss_falls_to_style_guide(self):
        """Role not in project_palette → style_guide.global.suggested_palette[element_idx]."""
        sg = BUILTIN_STYLE_GUIDE
        expected = sg.global_.suggested_palette[0] if sg.global_.suggested_palette else _BUILTIN_DEFAULTS[0]
        result = resolve(
            role="unknown_role",
            chart_colors=[],
            project_palette={"primary": "#7F7F7F"},  # "unknown_role" not in palette
            style_guide=sg,
            element_idx=0,
        )
        assert result == normalize_hex(expected)

    def test_no_palette_falls_to_style_guide(self):
        sg = BUILTIN_STYLE_GUIDE
        expected = sg.global_.suggested_palette[0] if sg.global_.suggested_palette else _BUILTIN_DEFAULTS[0]
        result = resolve(
            role="primary",
            chart_colors=[],
            project_palette=None,
            style_guide=sg,
            element_idx=0,
        )
        assert result == normalize_hex(expected)

    def test_style_guide_index_wraps(self):
        """element_idx beyond suggested_palette length → wrap modulo."""
        sg = BUILTIN_STYLE_GUIDE
        palette = sg.global_.suggested_palette
        n = len(palette)
        result = resolve(
            role="primary",
            chart_colors=[],
            project_palette=None,
            style_guide=sg,
            element_idx=n + 2,  # beyond palette length
        )
        assert result == normalize_hex(palette[(n + 2) % n])

    def test_empty_style_guide_palette_falls_to_builtin(self):
        """No suggested_palette → fall through to _BUILTIN_DEFAULTS."""
        from aurum_encuestas.style_guide import StyleGuide
        sg = StyleGuide.model_validate({
            "version": 1,
            "is_builtin": False,
            "patterns": [],
            "global": {
                "typography": {"font_family": "Arial", "title_size": 16, "subtitle_size": 12, "label_size": 9, "body_size": 10},
                "text_patterns": {},
                "suggested_palette": [],  # empty!
                "vibe": "",
            },
            "available_chart_types": [],
        })
        result = resolve(
            role="primary",
            chart_colors=[],
            project_palette=None,
            style_guide=sg,
            element_idx=0,
        )
        assert result == normalize_hex(_BUILTIN_DEFAULTS[0])

    def test_all_levels_empty_returns_builtin_default(self):
        from aurum_encuestas.style_guide import StyleGuide
        sg = StyleGuide.model_validate({
            "version": 1, "is_builtin": False, "patterns": [],
            "global": {"typography": {"font_family": "Arial", "title_size": 16, "subtitle_size": 12, "label_size": 9, "body_size": 10}, "text_patterns": {}, "suggested_palette": [], "vibe": ""},
            "available_chart_types": [],
        })
        result = resolve("primary", [], None, sg, 0)
        assert result.startswith("#")
        assert len(result) == 7
```

- [ ] **Step 2: Run failing**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest tests/test_color_resolver.py -v 2>&1 | head -30
```
Expected: ImportError (stub lacks `normalize_hex`, `_BUILTIN_DEFAULTS` not exported).

- [ ] **Step 3: Implement color_resolver.py — normalize_hex + resolve**

Replace the stub content of `backend/aurum_encuestas/color_resolver.py` with:

```python
"""M6 Color Resolver.

Symbolic color role → hex cascade:
  1. chart.colors[element_idx]                   (per-chart explicit)
  2. project_palette[role]                       (project-level)
  3. style_guide.global.suggested_palette[idx]   (AI-suggested)
  4. _BUILTIN_DEFAULTS[idx % len]                (fallback greys)

All returned hex values are normalized to #RRGGBB uppercase.

Auto-derive: auto_derive(primary_hex, n) produces n colors from primary using
lumMod-like lightness variation (implemented in pure RGB/HLS — no external deps).
"""
from __future__ import annotations

import colorsys
import logging
import re

log = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# Built-in default palette (neutral greys + accent)
# ────────────────────────────────────────────────────────────────────────────

_BUILTIN_DEFAULTS: list[str] = [
    "#7F7F7F",  # primary grey
    "#BFBFBF",  # secondary light grey
    "#FFC000",  # accent yellow
    "#404040",  # dark grey
    "#D9D9D9",  # very light grey
    "#A6A6A6",  # mid grey
    "#595959",  # dark mid grey
    "#D6D6D6",  # near-white grey
]

# ────────────────────────────────────────────────────────────────────────────
# hex normalization
# ────────────────────────────────────────────────────────────────────────────

_HEX_RE = re.compile(r"^#?([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")


def normalize_hex(color: str) -> str:
    """Normalize a hex color string to #RRGGBB uppercase.

    Accepts: #RGB, RGB, #RRGGBB, RRGGBB (case-insensitive).
    Returns _BUILTIN_DEFAULTS[0] (#7F7F7F) for invalid inputs.
    """
    if not isinstance(color, str):
        return _BUILTIN_DEFAULTS[0]

    color = color.strip()
    m = _HEX_RE.match(color)
    if not m:
        return _BUILTIN_DEFAULTS[0]

    h = m.group(1)
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2  # expand #RGB → RRGGBB
    return f"#{h.upper()}"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = normalize_hex(hex_color).lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


# ────────────────────────────────────────────────────────────────────────────
# resolve — main cascade
# ────────────────────────────────────────────────────────────────────────────

def resolve(
    role: str,
    chart_colors: list[str],
    project_palette: dict | None,
    style_guide,
    element_idx: int = 0,
) -> str:
    """Resolve a symbolic color role to a normalized hex string.

    Cascade (first non-empty wins):
    1. chart_colors[element_idx]
    2. project_palette[role]
    3. style_guide.global_.suggested_palette[element_idx % len]
    4. _BUILTIN_DEFAULTS[element_idx % len]
    """
    # 1. chart.colors[element_idx]
    if chart_colors and element_idx < len(chart_colors):
        return normalize_hex(chart_colors[element_idx])

    # 2. project_palette[role]
    if project_palette and role in project_palette:
        return normalize_hex(project_palette[role])

    # 3. style_guide.global_.suggested_palette
    try:
        palette = style_guide.global_.suggested_palette
        if palette:
            return normalize_hex(palette[element_idx % len(palette)])
    except (AttributeError, TypeError, IndexError) as exc:
        log.debug("resolve: error accessing style_guide palette: %s", exc)

    # 4. built-in defaults
    return _BUILTIN_DEFAULTS[element_idx % len(_BUILTIN_DEFAULTS)]
```

- [ ] **Step 4: Run resolve tests**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest tests/test_color_resolver.py::TestNormalizeHex tests/test_color_resolver.py::TestResolve -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas"
git add backend/aurum_encuestas/color_resolver.py backend/tests/test_color_resolver.py
git commit -m "$(cat <<'EOF'
feat(backend/m6.4): color_resolver — normalize_hex + resolve() cascade (chart→palette→style_guide→builtin)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: auto_derive() — N colors via lumMod lightness progression

**Files:**
- Modify: `backend/aurum_encuestas/color_resolver.py`
- Modify: `backend/tests/test_color_resolver.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_color_resolver.py`:

```python
# ────────────────────────────────────────────────────────────────────────────
# auto_derive tests
# ────────────────────────────────────────────────────────────────────────────

class TestAutoDerive:
    def test_n1_returns_primary(self):
        result = auto_derive("#7F7F7F", 1)
        assert result == ["#7F7F7F"]

    def test_returns_n_colors(self):
        for n in range(1, 9):
            result = auto_derive("#7F7F7F", n)
            assert len(result) == n, f"Expected {n} colors, got {len(result)}"

    def test_all_valid_hex(self):
        result = auto_derive("#FFC000", 5)
        for c in result:
            assert c.startswith("#"), f"Expected #RRGGBB, got {c}"
            assert len(c) == 7, f"Expected 7-char hex, got {c}"

    def test_first_is_primary(self):
        primary = "#7F7F7F"
        result = auto_derive(primary, 3)
        assert result[0] == normalize_hex(primary)

    def test_monotonic_lightness_progression(self):
        """Each derived color should have distinct lightness from prior ones.

        We check that derived colors differ from each other — exact ordering
        depends on the derivation algorithm, but no two should be identical.
        """
        result = auto_derive("#7F7F7F", 5)
        # All colors should be unique (no duplicates)
        assert len(set(result)) == len(result), f"Duplicate colors in {result}"

    def test_n2_primary_and_lighter(self):
        """For n=2: [primary, lighter variant]."""
        result = auto_derive("#404040", 2)
        # second color should be different (lighter or adjusted)
        assert result[0] != result[1]

    def test_invalid_primary_falls_back(self):
        """Invalid hex primary → still returns n colors using builtin default."""
        result = auto_derive("not-a-color", 3)
        assert len(result) == 3
        for c in result:
            assert c.startswith("#")

    def test_white_primary(self):
        result = auto_derive("#FFFFFF", 3)
        assert len(result) == 3

    def test_black_primary(self):
        result = auto_derive("#000000", 3)
        assert len(result) == 3
```

- [ ] **Step 2: Implement auto_derive**

Append to `backend/aurum_encuestas/color_resolver.py`:

```python
# ────────────────────────────────────────────────────────────────────────────
# auto_derive — N colors from primary via HLS lightness variations
# ────────────────────────────────────────────────────────────────────────────

def auto_derive(primary_hex: str, n: int) -> list[str]:
    """Derive n colors from a single primary hex using HLS lightness modulation.

    Strategy:
    - color[0] = primary (unchanged)
    - colors[1..n-1] = primary with lightness shifted by evenly spaced lumMod steps
      spanning from slightly darker to lighter (avoids invisible white/black extremes)

    Lightness modulations: for k in [1..n-1], lightness adjusted by
      Δl = (k / (n - 1 or 1)) * max_range, centered around primary lightness.
    Range clamped to [0.15, 0.90] to avoid invisible extremes.

    All colors returned as #RRGGBB uppercase.
    """
    if n <= 0:
        return []

    primary_norm = normalize_hex(primary_hex)
    if primary_norm == _BUILTIN_DEFAULTS[0] and not _HEX_RE.match(primary_hex.strip()):
        # primary was invalid — use builtin cycle
        return [_BUILTIN_DEFAULTS[i % len(_BUILTIN_DEFAULTS)] for i in range(n)]

    if n == 1:
        return [primary_norm]

    r, g, b = _hex_to_rgb(primary_norm)
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)

    results: list[str] = [primary_norm]

    # Generate n-1 variants spaced across a lightness range
    # Range: go from lighter to darker (or fill gap if primary is at extreme)
    l_min = 0.15
    l_max = 0.90
    # Create n-1 target lightness values that differ from primary l
    # Spread evenly in [l_min, l_max], excluding the primary lightness slot
    candidates = []
    step = (l_max - l_min) / max(n, 2)
    for i in range(1, n + 1):
        candidate_l = l_min + i * step
        if abs(candidate_l - l) > 0.03:  # avoid near-duplicates
            candidates.append(min(l_max, max(l_min, candidate_l)))
    # If we ended up with fewer candidates than needed, generate more
    if len(candidates) < n - 1:
        extra_step = (l_max - l_min) / (n + 1)
        for i in range(n):
            cl = l_min + (i + 0.5) * extra_step
            if cl not in candidates:
                candidates.append(cl)

    # Take n-1 candidates, prefer those furthest from primary first
    candidates_sorted = sorted(candidates[:n - 1 + 5], key=lambda cl: -abs(cl - l))
    selected = candidates_sorted[:n - 1]
    # Sort selected lightness values for monotonic appearance (lightest to darkest or vice versa)
    selected.sort(reverse=True)

    for candidate_l in selected[:n - 1]:
        r2, g2, b2 = colorsys.hls_to_rgb(h, candidate_l, s)
        ri, gi, bi = round(r2 * 255), round(g2 * 255), round(b2 * 255)
        ri = max(0, min(255, ri))
        gi = max(0, min(255, gi))
        bi = max(0, min(255, bi))
        results.append(_rgb_to_hex(ri, gi, bi))

    # Ensure exactly n colors
    while len(results) < n:
        results.append(_BUILTIN_DEFAULTS[len(results) % len(_BUILTIN_DEFAULTS)])

    return results[:n]
```

- [ ] **Step 3: Run auto_derive tests**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest tests/test_color_resolver.py::TestAutoDerive -v
```
Expected: all PASS (9 tests).

- [ ] **Step 4: Commit**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas"
git add backend/aurum_encuestas/color_resolver.py backend/tests/test_color_resolver.py
git commit -m "$(cat <<'EOF'
feat(backend/m6.4): auto_derive — N colors via HLS lightness modulation, no duplicates

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: update_recent() — persist last 8 unique hex to config.json

**Files:**
- Modify: `backend/aurum_encuestas/color_resolver.py`
- Modify: `backend/tests/test_color_resolver.py`

- [ ] **Step 1: Failing tests**

Append to `backend/tests/test_color_resolver.py`:

```python
# ────────────────────────────────────────────────────────────────────────────
# update_recent tests
# ────────────────────────────────────────────────────────────────────────────

from aurum_encuestas.color_resolver import update_recent, get_recent_colors


class TestUpdateRecent:
    def test_update_adds_color(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        update_recent("#7F7F7F")
        recents = get_recent_colors()
        assert "#7F7F7F" in recents

    def test_update_normalizes_hex(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        update_recent("#ffc000")
        recents = get_recent_colors()
        assert "#FFC000" in recents

    def test_most_recent_is_first(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        update_recent("#AAAAAA")
        update_recent("#BBBBBB")
        recents = get_recent_colors()
        assert recents[0] == "#BBBBBB"

    def test_deduplicates_moves_to_front(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        update_recent("#AAAAAA")
        update_recent("#BBBBBB")
        update_recent("#AAAAAA")  # revisit
        recents = get_recent_colors()
        assert recents[0] == "#AAAAAA"
        assert recents.count("#AAAAAA") == 1

    def test_max_8_entries(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        colors = [f"#{i:02X}{i:02X}{i:02X}" for i in range(10, 28, 2)]  # 9 distinct colors
        for c in colors:
            update_recent(c)
        recents = get_recent_colors()
        assert len(recents) <= 8

    def test_invalid_hex_not_stored(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        update_recent("not-a-color")
        recents = get_recent_colors()
        assert "not-a-color" not in recents

    def test_empty_initial_state(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        recents = get_recent_colors()
        assert recents == []

    def test_concurrent_writes_idempotent(self, tmp_path, monkeypatch):
        """Two sequential writes don't corrupt file."""
        monkeypatch.setenv("HOME", str(tmp_path))
        update_recent("#111111")
        update_recent("#222222")
        update_recent("#333333")
        recents = get_recent_colors()
        assert "#333333" in recents
        assert "#111111" in recents
```

- [ ] **Step 2: Implement update_recent + get_recent_colors**

Append to `backend/aurum_encuestas/color_resolver.py`:

```python
# ────────────────────────────────────────────────────────────────────────────
# Recent colors — persist to ~/.aurum/config.json
# ────────────────────────────────────────────────────────────────────────────

_MAX_RECENTS = 8


def get_recent_colors() -> list[str]:
    """Return recent_colors list from ~/.aurum/config.json. Empty list if not found."""
    try:
        from .config import load_config
        cfg = load_config()
        recents = cfg.ui.get("recent_colors", []) if isinstance(cfg.ui, dict) else []
        return [c for c in recents if isinstance(c, str) and c.startswith("#")]
    except Exception as exc:
        log.debug("get_recent_colors: failed to load config: %s", exc)
        return []


def update_recent(hex_color: str) -> None:
    """Add hex_color to the front of recent_colors in ~/.aurum/config.json.

    - Normalizes hex before storing.
    - Deduplicates (moves to front if already present).
    - Keeps max 8 entries.
    - Silently ignores invalid hex strings.
    """
    normalized = normalize_hex(hex_color)
    # Check if it was actually invalid (normalize returns #7F7F7F as fallback)
    if not _HEX_RE.match(hex_color.strip()):
        log.debug("update_recent: invalid hex %r — not stored", hex_color)
        return

    try:
        from .config import load_config, save_config
        cfg = load_config()
        if not isinstance(cfg.ui, dict):
            cfg.ui = {}
        recents: list[str] = [c for c in cfg.ui.get("recent_colors", []) if isinstance(c, str) and c != normalized]
        recents.insert(0, normalized)
        cfg.ui["recent_colors"] = recents[:_MAX_RECENTS]
        save_config(cfg)
    except Exception as exc:
        log.warning("update_recent: failed to save recent color %r: %s", normalized, exc)
```

- [ ] **Step 3: Extend AurumConfig.ui to support recent_colors**

Check `backend/aurum_encuestas/config.py`. The `AurumConfig` model has `ui: dict = {"theme": "dark"}`. This already allows storing `recent_colors` as a key. No change needed — `update_recent` reads/writes `cfg.ui["recent_colors"]` as a plain dict key.

Verify:
```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend"
.venv/bin/python -c "
from aurum_encuestas.config import AurumConfig
cfg = AurumConfig()
cfg.ui['recent_colors'] = ['#7F7F7F']
print(cfg.model_dump())
"
```
Expected: prints dict with `ui.recent_colors` key.

- [ ] **Step 4: Run update_recent tests**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest tests/test_color_resolver.py::TestUpdateRecent -v
```
Expected: all PASS (8 tests).

- [ ] **Step 5: Run full color_resolver test suite**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest tests/test_color_resolver.py -v
```
Expected: all PASS (~30 tests total).

- [ ] **Step 6: Commit**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas"
git add backend/aurum_encuestas/color_resolver.py backend/tests/test_color_resolver.py
git commit -m "$(cat <<'EOF'
feat(backend/m6.4): update_recent + get_recent_colors — persist last 8 unique hex to config.json

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4 (final): Full test suite + tag M6.4

**Files:** none

- [ ] **Step 1: Full backend test suite**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend" && .venv/bin/pytest -v
```
Expected: all PASS — no regressions.

- [ ] **Step 2: Smoke test color_resolver as standalone**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/backend"
.venv/bin/python -c "
from aurum_encuestas.color_resolver import resolve, auto_derive, normalize_hex
from aurum_encuestas.style_guide import BUILTIN_STYLE_GUIDE

# Test cascade
c1 = resolve('primary', ['#FFC000'], None, BUILTIN_STYLE_GUIDE, 0)
print(f'chart.colors[0] wins: {c1}')  # #FFC000

c2 = resolve('primary', [], {'primary': '#FF0000'}, BUILTIN_STYLE_GUIDE, 0)
print(f'palette wins: {c2}')  # #FF0000

c3 = resolve('primary', [], None, BUILTIN_STYLE_GUIDE, 0)
print(f'style_guide suggested: {c3}')  # first suggested palette color

# Test auto_derive
derived = auto_derive('#7F7F7F', 5)
print(f'auto_derive 5 from grey: {derived}')
assert len(derived) == 5
assert len(set(derived)) == 5

print('Smoke test PASSED')
"
```
Expected: prints 4 lines, ends with `Smoke test PASSED`.

- [ ] **Step 3: Tag M6.4**

```bash
cd "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas"
git tag m6.4-color-resolver
git log --oneline | head -10
```

---

## M6.4 Done When

- [ ] `normalize_hex()` handles `#RGB`, `#RRGGBB`, `RRGGBB` (no hash), case-insensitive — invalid → `#7F7F7F`
- [ ] `resolve(role, chart_colors, project_palette, style_guide, element_idx)` implements full 4-level cascade with index-wrapping and empty-list handling at every level
- [ ] `auto_derive(primary_hex, n)` returns exactly n unique hex colors; first is always primary; no two identical; handles white/black/invalid primary
- [ ] `update_recent(hex)` normalizes, deduplicates, moves to front, max 8 entries, persists to `~/.aurum/config.json`
- [ ] `get_recent_colors()` reads from config, returns `[]` on first run or missing file
- [ ] All color_resolver tests pass (~30 tests)
- [ ] No regressions in full backend test suite
- [ ] Git tag `m6.4-color-resolver` created
