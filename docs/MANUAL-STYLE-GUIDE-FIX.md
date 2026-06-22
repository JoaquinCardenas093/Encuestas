# Manual fix: remove "Distribución general/segmentada" split from active style_guide

## Quick reset (recommended)

Delete your active style_guide.json entirely:

```bash
rm ~/.aurum/training/style_guide.json
```

The renderer falls back to the BUILTIN style guide, which includes a
clean `table_only_full_width` pattern for TABLE_WITH_MINIBARS + breakdown
slides. No manual JSON editing required.

You can re-run training (`/api/training/analyze`) later if you want
AI-generated patterns again.

---

## Manual fix (legacy fallback)

If your current `~/.aurum/training/style_guide.json` was generated before Fase E
of the chart-catalog overhaul, it likely contains a pattern with four elements:

1. A text shape "Distribución general"
2. A left PIE chart
3. A text shape "Distribución segmentada"
4. A right table (`TABLE_WITH_MINIBARS`)

This split is no longer desired — the OLE table now covers all breakdowns and
should occupy the full slide width.

## Steps

1. Open `~/.aurum/training/style_guide.json` in a text editor.
2. Find the pattern with `"id"` containing `demographics` or with elements
   referencing the strings `"Distribución general"` and `"Distribución segmentada"`.
3. Inside that pattern's `implementation.elements` list, remove the three
   non-table elements (the two text shapes and the PIE chart).
4. Keep the remaining `kind="chart"` element with `chart_type="TABLE_WITH_MINIBARS"`.
   Update its `position` to:
   ```json
   {"x_rel": 0.04, "y_rel": 0.18, "w_rel": 0.92, "h_rel": 0.70}
   ```
5. Save the file.

Next pptx generation will use the cleaned-up pattern.

## Future regeneration

If you re-run training corpus analysis (`/api/training/analyze`), the new
system prompt in `llm_client.py` emits a single-element pattern by default,
so this manual edit will not be needed again.
