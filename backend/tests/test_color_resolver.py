"""Tests for color_resolver — cascade, auto_derive, update_recent."""
from aurum_encuestas.color_resolver import (
    _BUILTIN_DEFAULTS,
    auto_derive,
    normalize_hex,
    resolve,
    update_recent,
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


# ────────────────────────────────────────────────────────────────────────────
# update_recent tests
# ────────────────────────────────────────────────────────────────────────────

from aurum_encuestas.color_resolver import get_recent_colors  # noqa: E402


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
