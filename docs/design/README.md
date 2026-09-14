# Investigation workspace wireframe

[`investigation-wireframe.svg`](./investigation-wireframe.svg) is a rendered,
content-first wireframe for the first Incident Lens workspace. It shows the
wide reading order and the compact state vocabulary without claiming that a
live run or metric exists.

| Product requirement | Wireframe location | Phase 0 decision |
| --- | --- | --- |
| Context bar with origin, execution, service, window, run | Header strip | Origin and execution remain separate labels; no health badge |
| Findings as the visual anchor | Left reading column | Assessment uses “unusual ranking,” never root-cause probability |
| Evidence on demand | Right evidence drawer | Wide panel; overlay/sheet at 768/390 |
| Expandable execution timeline | Lower timeline row | Collapsed after a run; actual tool outputs arrive later |
| Review actions | Bottom action rail | Accept/correct/challenge/withhold/export remain bounded actions |
| Required empty/loading/running/partial/success/unresolved/error/cached/upload/save states | State strip | Every state is text-labelled; color is supplementary |

Target review widths are **1440**, **1280**, **768**, and **390** CSS pixels.
The 768 and 390 layouts deliberately stack or sheet the evidence and timeline;
the exact drawer focus-trap behavior is unresolved until the interactive slice
exists. No screenshot is presented as browser evidence in Phase 0.

The visual baseline uses a warm light canvas, dark readable typography, slate
blue action accents, semantic amber/error colors with text labels, and
monospace only for telemetry. Tokens are in [`tokens.css`](./tokens.css).
