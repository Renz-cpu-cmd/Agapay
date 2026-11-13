# Observed decision-comprehension review

Status: prepared; no participant sessions performed. Use synthetic scenarios in a segregated drill environment. Do not submit a real distress request, publish an operational instruction or deliver an external alert during this review.

Start with a formative sample of residents and duty officers who represent intended users, including people using screen readers and large text. Six residents and three officers are a proposed first round, not a statistical acceptance claim. Record consent using the responsible organization's process. Use participant codes in results; do not store names, phone numbers, exact home locations or audio in this repository.

For each scenario in `scenario-review.csv`, counterbalance light/dark and scenario order. Test narrow web and supported phones, default and 200% text, keyboard and the actual supported screen reader. Record build, OS/device, theme, width, text scale and assistive technology. Start timing when the scenario is visible; stop at the participant's first completed decision. Capture first answer before hints, clarification or training. If interrupted by system behavior, record it rather than silently resetting the time. Use an observer who does not supply the expected answer.

| Task prompt | Expected comprehension |
|---|---|
| What applies to your area, who issued it, and is it still effective? | Correct area and verified issuer; distinguish app/exercise versus Official advisory; recognize update, cancellation and expiry. |
| Explain this online device with an invalid latest sample and a one-hour-old critical depth. | Connectivity does not imply a fresh reading; depth is Last known; current observation unknown; historical critical episode unresolved. |
| The rainfall panel is empty while depth is normal. What do you know about rain? | No valid reading means unknown rainfall, not zero. |
| The experimental curve rises. Is this an observed flood or an official order? | Neither inference is established; identify Experimental projection and its limitations. |
| You tapped Practice SOS and the response was lost. What is its delivery status and next action? | Unknown rather than received; inspect immutable reference/check receipt; do not generate a replacement request or assume dispatch. |
| You have no GPS or Maps. Find usable assistance and shelter information. | Read verified dated list/contact evidence, note availability/route limits, and avoid inventing coordinates or a safe route. |
| Another officer changed this incident while you edited. What should happen next? | Refresh and manually review; no automatic stale overwrite; correctly identify recorded owner versus dispatch. |

Record success as correct only when the user identifies the important source, freshness and next action without help. Record partial, incorrect, abandoned or technically blocked outcomes explicitly. Capture task time in seconds, assistance count, misinterpretation, confidence and an issue reference. Leave unmeasured fields empty; never use zero for missing time.

Predeclare review targets with the responsible operators before recruitment. Suggested formative targets: at least 90% unassisted comprehension on source/freshness/receipt distinctions, no unresolved critical misunderstanding (for example unknown SOS interpreted as received, stale depth interpreted as live, or sensor tier interpreted as an official order), and task-specific time budgets established from a pilot. Report counts and denominators, median/range of completion time and each critical error. Small formative samples cannot establish population-level safety or operational response performance.

Every critical misunderstanding creates an issue, design correction and repeat test. Keep the original result and mark which build was retested. Do not claim screen-reader support from an axe scan: record navigation order, announcement content, control names, focus return, interrupt/reconnect behavior and actual task completion with NVDA/TalkBack/VoiceOver separately.
