# 19 — Accessibility and inclusive interaction

Use WCAG 2.2 AA as target where applicable; no unsupported compliance claim. Interactive map cannot be sole medium for essential safety information.

## Inputs and controls

- Every origin/destination/departure/weight input has visible label, accessible error, unit and guidance; autocomplete follows combobox/listbox keyboard patterns.
- Native form submission and predictable focus; no clickable divs as substitutes for buttons.
- Route cards are keyboard-selectable controls with state announcement (selected vs recommended are distinct).
- Slider uses accessible `aria-valuetext` with exact forecast timestamp and date/time zone; keyboard controls.
- Checkpoint detail accessible from an ordered list as well as map marker.

## Visual semantics

- Severity colors backed by textual names/icon/line patterns; color is never only indicator.
- Contrast reviewed in light/dark states if both supported; focus rings remain visible even on map.
- Typography reflows at 200% text scale without hiding core safety warnings.
- Reduce/disable nonessential transition on `prefers-reduced-motion`.
- Motion never obscures No Travel warning; loading shimmer can be reduced to static skeleton.

## Screen readers and async

- Use polite live region for stages/loading results; assertive for urgent No Travel or validation failures without repetitive announcements.
- Focus moves sensibly after submit or errors, but not on every polling update.
- Error copy states what failed, what remains usable and next possible action.
- Provide a route comparison summary table/list with ETA, miles, severity and weather coverage independent of map availability.

## QA checks

Manual keyboard walkthrough at desktop/mobile widths, VoiceOver/NVDA smoke tests, axe automation, touch-target review and zoom/reflow. Record real findings and fixes; do not claim certification.
