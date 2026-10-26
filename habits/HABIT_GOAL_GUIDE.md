# Mossly: Habit & Goal Tracker Module Guide

Guidance for any agent (and any contributor) building the **Sustainable Habit & Goal Tracker** module of Mossly. Read this fully before writing code. When a decision here changes, update this file in the same change.

Status: draft v0.3 (2026-10-21). Owner of this module: **Tania Ju**.

### Changelog

- **v0.3 (2026-10-21):** this guide file must never be staged or committed by the agent (Sections 0 and 15).
- **v0.2 (2026-10-21):** streak milestones are **decided** as 3, 7, 14, and 30 days. The Figma screens (add-habit info alert, milestone modal, "Terkirim ke Dashboard" card, Riwayat log) were updated to match. Milestones beyond 30 days are still open.
- **v0.1 (2026-10-21):** first draft, written from the finished Figma design (15 screens) and the team README. Business rules marked **Proposed** are not yet agreed with the team; they are collected in Section 14.

---

## 0. Notes for the agent (read first)

- **Address the user by name.** The module owner is **Tania**. Greet and answer her by name ("Tania, ...") when sending messages or replying to her prompts. She writes in Indonesian, so reply in Indonesian unless she asks for English.
- **Never mention this guide in code.** Do not write this file's name, or any other agent-instruction file name, in code comments, docstrings, template comments, CSS comments, or test names. Comments explain *why* the code does something, in plain English, as if no guide existed.
- Ask before adding a dependency (Python or JS), a new Django app, a new top-level folder, or a new architectural layer.
- Never invent values, citations, emission factors, or rules that this file marks as open. Unknown means ask.
- **Never stage or commit this guide file.** When Tania asks you to `git add` (or to stage "the updates"), leave this file out, even if it is untracked or shows as modified. The file is currently named `HABIT_GOAL_GUIDE.md`; if it has been renamed, use its current name. Never run a bare `git add .`, `git add -A`, or `git add -u` without excluding it, for example `git add -A -- . ':!HABIT_GOAL_GUIDE.md'`, or stage explicit paths instead. After staging, run `git diff --cached --name-only` and confirm the guide is not listed; if it is, unstage it with `git restore --staged <file>` and tell Tania. Only stage this file if Tania explicitly asks for that file by name.
- Before writing code, inspect the repository (settings, the Login module's user model, the base template, the static folder layout) and report any difference from this file. The repository wins for existing code; this file wins for design intent.
- Run `python manage.py check` and `python manage.py test` before reporting work as done, and state what you ran.

---

## 1. What this module is

Mossly helps users build a sustainable lifestyle through carbon tracking, habits, personal achievements, and a community. The name comes from "moss": it grows slowly but consistently, so small steps count.

This module, **Sustainable Habit & Goal Tracker**, has two complementary parts:

- **Habit:** recurring daily habits (bring a tumbler, take public transport, sort waste). The user checks in each day and builds a streak.
- **Goal:** a specific target with a deadline (for example "naik transportasi umum 20 kali dalam sebulan"), with a checklist and a progress bar.

Whenever a **goal is completed** or a **habit reaches a streak milestone**, this module sends an event to the **Personal Sustainability Dashboard** so it can be aggregated and evaluated as part of the user's overall achievements.

Tech stack: **Django, HTML, CSS** (deployed on PWS UI). Source of truth for visuals: the Figma file (Section 4).

### Out of scope for this module

- Authentication, registration, onboarding forms (Login & Onboarding module).
- Computing carbon emissions or storing trips (Carbon Footprint Tracker module).
- Deciding badges or achievements, and posting to the community (Personal Sustainability Dashboard module owns the badge logic and triggers Community posts).
- Forum threads, replies, likes (Sustainability Community module).
- Push, email, or WhatsApp reminders (the form has a reminder field in the design; see Section 14).

---

## 2. How this module connects to the others

| Module | Owner | Relationship to this module |
| --- | --- | --- |
| Login & Onboarding | Sheva | Provides the authenticated user (`request.user`), display name, and avatar initial. This module never creates its own profile or auth. Onboarding collects initial sustainability targets and frequently used vehicles; whether those prefill habit or goal suggestions is open (Section 14). |
| Carbon Footprint Tracker | Callysta | Some goals relate to trips or emissions ("Kurangi emisi perjalanan 10 kg", "Naik transportasi umum 20 kali"). In the MVP, progress for these goals is entered **manually** by the user. Auto-linking goal progress to recorded trips is open (Section 14). |
| Personal Sustainability Dashboard | Fildza | **Receives events from this module** (goal completed, habit streak milestone). Owns badge and achievement logic. Links like "Lihat di Dashboard" point to it. This module shows only habit and goal history; it does not duplicate the Dashboard's aggregated recap. |
| Sustainability Community | Isybal | Does not talk to this module directly. Achievement auto-posts are triggered by the Dashboard after it receives our events. |

Rules for crossing module boundaries:

- Depend on the Login module only through `settings.AUTH_USER_MODEL` / `get_user_model()`. Do not import its internals.
- Talk to the Dashboard only through the event mechanism in Section 7. Do not write to the Dashboard's tables or import its models.
- Never trigger Community posts from this module.
- Agree the route names (`url` names) for the Dashboard and Login pages with their owners before linking to them; use `{% url %}` names, never hardcoded paths.

---

## 3. Features (MVP)

| Feature | Notes |
| --- | --- |
| Habit list (today) | Habits grouped by time of day (Pagi, Siang, Malam; "Kapan saja" is a fourth option in the form). One tap checks in. Shows streak per habit. |
| Week strip | Seven day chips for the current week with a status per day (Section 6). |
| Add / edit / delete habit | Form fields in Section 8. Deleting asks for confirmation. |
| Streak and milestones | Streak per habit; reaching a milestone shows a celebration and sends an event. |
| Goal list | Active goals sorted by nearest deadline, plus "Selesai baru-baru ini". |
| Add / edit / delete goal | Name, category, target, start and deadline, optional checklist. |
| Log progress (Catat progres) | Adds N to a goal's progress with an optional note. |
| Goal and habit detail | Detail pages with checklist, progress log, calendar, statistics, settings. |
| History (Riwayat) | Calendar heatmap (month, 3 months, year), activity log, monthly summary, most consistent habits. |
| Empty states | For Habit, Goal, and Riwayat, with suggestions to start. |
| Events to Dashboard | On goal completion and on habit milestones (Section 7). |

---

## 4. Design source (Figma)

- File: `https://www.figma.com/design/xMVSWGoAmsCNbc0IrEX4gX/PBP-LETSGOOO` (file key `xMVSWGoAmsCNbc0IrEX4gX`).
- Pages: **Design System** (Lucide icon library), **Component** (components, foundations, landing page versions), **Landing Page** (current landing page v3 and the `navbar` component), **Habit & Goal Tracker** (this module's screens).
- **Use the Figma MCP if it is available**: read tokens, text styles, and frame structure from the file instead of guessing. If it is not available, use the screenshots and the tables in this file.
- Node IDs can change when a frame is rebuilt. Find frames by **name**; the IDs below are only a starting point.

### Screens (page "Habit & Goal Tracker", desktop 1440 wide)

| Frame name | Node ID | What it is |
| --- | --- | --- |
| 01 v2 Habit & Goal / Tab Habit | `704:481` | Habit tab: focus panel, week strip, grouped habit list, sidebar |
| 02 v2 Habit & Goal / Tab Goal | `708:762` | Goal tab: focus panel, active goals, completed goals |
| 03 v2 Habit & Goal / Tab Riwayat | `709:1058` | History: month heatmap, activity log, summary cards |
| 04 Tambah Habit (modal) | `711:1260` | Add habit form |
| 05 Buat Goal (modal) | `711:1507` | Create goal form |
| 06 Catat Progres (modal) | `713:1936` | Log goal progress |
| 07 Milestone Tercapai (modal) | `713:2051` | Streak milestone celebration |
| 08 Hapus Habit (konfirmasi) | `713:2237` | Delete confirmation |
| 09 Detail Goal | `714:2862` | Goal detail |
| 10 Detail Habit | `714:3159` | Habit detail |
| 11 Empty State: Habit / Goal / Riwayat | `715:3167` / `715:3525` / `715:3882` | Empty states |
| 12 Riwayat: 3 Bulan / Setahun | `716:3979` / `716:4489` | History periods |

### Components and libraries

| Item | Node ID |
| --- | --- |
| Components board of this module | `697:3` |
| Habit Row / Day Chip / Milestone Row / Card Goal / Checklist Item | `702:509` / `697:33` / `697:57` / `698:9` / `697:15` |
| Heatmap Cell / History Item / Choice Chip / Icon Option | `708:5289` / `708:5290` / `711:1248` / `711:1259` |
| Nature decoration library ("Dekorasi Alam") | `706:648` |
| Design system components / foundations | `208:2` / `210:9` |
| Lucide icon library | `201:17` |
| Landing page `navbar` component | `694:5344` |

### Assets the owner must provide (checklist)

Mark each when done; the agent should not start the dependent work without it.

- [ ] **Logo** as SVG: the wooden "M" mark, with and without the "mossly" wordmark (from the `navbar` component).
- [ ] **Reference screenshots** of every screen above, PNG @2x, named after the frame (used to compare the built page with the design).
- [ ] **Nature decoration SVGs** (leaf, branch, flower, hill, grass, sprout) from the "Dekorasi Alam" frame. If not exported, the agent may redraw them as inline SVG using CSS variables for color.
- [ ] **Fonts:** see Section 5 (one font is unresolved).
- [ ] Answers to the open decisions in Section 14.

Icons come from Lucide. Do not export them from Figma: use `lucide-static` SVGs or inline SVG. Icons used: `cup-soda`, `train-front`, `recycle`, `shopping-bag`, `droplet`, `lightbulb`, `leaf`, `utensils`, `sun`, `cloud-sun`, `moon`, `flame`, `trophy`, `calendar`, `calendar-check`, `goal`, `target`, `list-checks`, `sparkles`, `footprints`, `circle-alert`, `arrow-left`, `minus`, `plus`, `check`, `x`, `trash-2`, `award`, `handshake`, `glass-water`.

---

## 5. Design tokens

Figma variables are the source of truth. Mirror them in `static/css/tokens.css` as CSS custom properties named after the Figma variable (`color/bg/canvas` becomes `--color-bg-canvas`). **Use only these tokens in CSS.** No raw hex, no one-off pixel values, no ad hoc font sizes. If a value is missing, ask; do not add it silently.

### Primitive colors

| Family | Steps |
| --- | --- |
| moss | 50 `#F1F4EC`, 100 `#E2E9D8`, 200 `#C6D3B2`, 300 `#99AD7A`, 400 `#7A9160`, 500 `#546B41`, 600 `#45583A`, 700 `#374630`, 800 `#2F3A25`, 900 `#1E2618` |
| sand | 50 `#FFF8EC`, 100 `#F6EEDC`, 200 `#EBDFC6`, 300 `#DCCCAC`, 400 `#C8B48C` |
| clay | 100 `#F3E4D1`, 300 `#D39C5E`, 500 `#B07634`, 600 `#8A6343`, 700 `#7E521F`, 800 `#5B4030`, 900 `#3B2A20` |
| pink | 50 `#FDF1F4`, 100 `#FBE3EA`, 200 `#F7CBD8`, 300 `#F2B3C6`, 400 `#E89AB1`, 500 `#D97F9C` |
| neutral | 0 `#FFFFFF`, 400 `#8C937F`, 600 `#5E6852` |
| red | 50 `#FBEAE8`, 500 `#B3261E` |

### Semantic colors (alias to a primitive)

| Token | Alias | Token | Alias |
| --- | --- | --- | --- |
| `color/bg/canvas` | sand/50 | `color/text/primary` | moss/800 |
| `color/bg/surface` | neutral/0 | `color/text/secondary` | neutral/600 |
| `color/bg/subtle` | sand/100 | `color/text/tertiary` | neutral/400 |
| `color/bg/sand` | sand/300 | `color/text/brand` | moss/500 |
| `color/bg/muted` | moss/50 | `color/text/accent` | clay/500 |
| `color/bg/brand` | moss/500 | `color/text/on-brand` | sand/50 |
| `color/bg/brand-hover` | moss/600 | `color/text/danger` | red/500 |
| `color/bg/brand-soft` | moss/100 | `color/text/disabled` | neutral/400 |
| `color/bg/inverse` | moss/800 | `color/border/default` | sand/300 |
| `color/bg/inverse-deep` | moss/900 | `color/border/subtle` | sand/200 |
| `color/bg/accent` | clay/500 | `color/border/strong` | moss/300 |
| `color/bg/accent-soft` | clay/100 | `color/border/focus` | moss/500 |
| `color/bg/sage` | moss/300 | `color/border/danger` | red/500 |
| `color/bg/danger-soft` | red/50 | `color/icon/brand` | moss/500 |
| `color/bg/danger` | red/500 | `color/icon/accent` | clay/500 |
| `color/bg/disabled` | sand/200 | | |

The module screens also use a few primitives directly (moss 100 to 400, clay 100 and 300, pink 100 to 300) for habit icon tints, heatmap levels, and decoration. Expose primitives as variables too.

### Typography

| Style | Font | Weight | Size / line height |
| --- | --- | --- | --- |
| Display/XL, Display/L | Red Hat Display | Bold | 80 / 100%, 64 / 104% |
| Heading/H1, H2, H3 | Red Hat Display | Bold | 48 / 110%, 36 / 115%, 24 / 125% |
| Heading/H4 | Red Hat Display | SemiBold | 20 / 130% |
| Body/L, M, S | Plus Jakarta Sans | Regular | 18 / 160%, 16 / 160%, 14 / 155% |
| Label/L, M, S | Plus Jakarta Sans | SemiBold | 16, 14, 12 / 120% |
| Overline | Plus Jakarta Sans | Bold | 12 / 120% (uppercase section label) |
| Stat/L | Red Hat Display | Bold | 40 / 110% |

Letter spacing and exact uppercase styling: read from Figma. Self-host fonts as `.woff2` or load from Google Fonts, whichever the team already does.

**Unresolved font conflict:** the design system says the logo font is Shippori Antique B1, but the landing page `navbar` component uses Fraunces SemiBold. The logo ships as an SVG asset, so this only matters if "mossly" is typed as live text. Ask before choosing.

### Spacing, radius, elevation

- Spacing (`space/n`, px): 1=4, 2=8, 3=12, 4=16, 5=20, 6=24, 8=32, 10=40, 12=48, 16=64, 20=80, 24=96, 30=120.
- Radius: sm 8, md 12, lg 16, xl 24, 2xl 32, full 999. Cards use xl or 2xl; chips, buttons, and avatars use full; inputs use md.
- Shadows: `Shadow/SM`, `Shadow/MD`, `Shadow/LG` (values: read from Figma). SM for cards, MD for dropdowns, LG for modals.

### Layout

- Designed at 1440 px wide. Page side margin **88 px** (matches the landing page navbar); content max width 1264 px. The 88 px margin is not in the spacing scale; define it once as a layout variable.
- Two-column grids use a 24 px gap (`space/6`); sections are 40 px apart (`space/10`).
- Mobile and tablet layouts are **not designed yet**. Build desktop first with fluid widths; do not invent mobile designs. Ask before adding breakpoints beyond simple stacking.

---

## 6. Visual rules and behavior of each state

- **Tone: motivating, never guilt-inducing.** A missed day is neutral (sand), not red. No shaming copy. Red (`danger`) is for destructive actions and form errors only.
- **One focus per screen.** Each tab opens with one green focus panel (today's progress, nearest goal, or monthly consistency). Keep the rest quiet.
- **Never color alone.** Every status has text or an icon too (check icon, "5/6", the legend).
- **Decorations** (leaf, branch, flower, hill, grass, sprout): flat vector, soft colors, always behind content (`z-index` below), never over text, `aria-hidden="true"`. Hills sit at the bottom edge of the focus panel. Keep them sparing.
- Cards are white, rounded, with `Shadow/SM`; inputs are white with a `border/default` border; the page background is `color/bg/canvas`.

### Day status (week strip and calendar)

| Status | Meaning | Look |
| --- | --- | --- |
| Done | All habits scheduled that day were checked in | Filled `bg/brand` with a check |
| Partial | Some, not all (shows "n/m") | `bg/accent-soft` fill, clay border, text "n/m" |
| Missed | Scheduled habits, none checked in | `bg/subtle`, dash |
| Today | Current day | Outlined ring (`border/focus`) |
| Upcoming | Future day | Empty outline |

### Heatmap levels (history)

Five levels plus Upcoming and Today. L0 = no check-in, L4 = all habits done. **Proposed** buckets (confirm): L0 = 0%, L1 = 1 to 39%, L2 = 40 to 69%, L3 = 70 to 99%, L4 = 100%. Colors: `bg/subtle`, moss/200, moss/300, moss/400, `bg/brand`. Generate cells from data; they are not images.

### Habit row

White row with `Shadow/SM` when not yet checked in; `bg/muted` fill when done. Left: icon in a tinted circle. Middle: name and streak line ("{n} hari berturut-turut", flame icon in accent). Right: a round check button (outlined when todo, filled when done). A brand-new habit with no streak shows "Baru dimulai · streak pertamamu mulai hari ini" with a grey flame.

---

## 7. Events to the Personal Sustainability Dashboard

Every goal completion and every habit milestone must create **one event** the Dashboard can read. The mechanism and exact payload are **not agreed yet** (Section 14). **Proposed:** an append-only `SustainabilityEvent` record (or an agreed Django signal / service function) with:

| Field | Notes |
| --- | --- |
| `user` | FK to the user, `on_delete=CASCADE` |
| `event_type` | `goal_completed` or `habit_milestone` |
| `source_type`, `source_id` | Which habit or goal; `source_id` may be nulled if the source is deleted |
| `title_snapshot` | Name of the habit or goal at that time, so history survives deletion |
| `payload` | Small JSON: for a milestone `{"streak_days": 7}`; for a goal `{"target": 20, "unit": "kali", "category": "transportasi"}` |
| `occurred_at` | Timezone-aware UTC |

Rules (**Proposed**, confirm with Fildza):

- **Idempotent:** a given habit reaches a given milestone once; a given goal completes once. Re-checking, undoing, or editing must not send duplicates.
- Events survive deletion of the habit or goal (the design promises "pencapaian yang sudah terkirim tetap tersimpan"). Use `SET_NULL` on the source, never cascade.
- Events are written in the **same database transaction** as the check-in or progress change that caused them.
- This module only **writes** events. The Dashboard decides what they mean.

---

## 8. Data model (Proposed, not verified)

> Not yet agreed with the team. Before writing models, inspect the repo, then confirm this section with Tania and report differences.

All models belong to a user (`settings.AUTH_USER_MODEL`). Every query is scoped to `request.user`; accessing another user's object returns 404.

**Habit**: `name` (max 80), `icon` (key from the icon list), `tint` (key from the tint list), `time_of_day` (`pagi`, `siang`, `malam`, `kapan_saja`), `frequency_type` (`daily`, `weekdays`, `times_per_week`), `weekdays` (set of Mon to Sun, for `weekdays`), `times_per_week` (1 to 7), `reminder_time` (nullable, stored only, see Section 14), `start_date`, `created_at`.

**HabitCheckIn**: `habit`, `date` (local date, Asia/Jakarta), `checked_at`. Unique on `(habit, date)`.

**Goal**: `title` (max 120), `category` (Transportasi, Emisi, Plastik, Sampah, Komunitas), `target_value` (positive number), `unit` (`kali`, `hari`, `kg CO2e`), `start_date`, `deadline`, `status` (`active`, `completed`, `expired`), `completed_at` (nullable), `created_at`.

**GoalChecklistItem**: `goal`, `label`, `is_done`, `done_at`, `position`.

**GoalProgressLog**: `goal`, `amount` (positive), `note` (optional), `logged_at`. Goal progress = sum of `amount`.

**SustainabilityEvent**: Section 7.

Rules:

- Habit and goal deletion is a **hard delete** of the habit or goal and its check-ins or logs (the delete dialog says so); events stay (Section 7).
- Validate on the server, always: lengths, `deadline >= start_date`, `target_value > 0`, `times_per_week` 1 to 7, `weekdays` required for `weekdays`.
- Use `TIME_ZONE = "Asia/Jakarta"` and `USE_TZ = True`. A "day" is the local calendar day, rolling over at 00:00 WIB. Store datetimes in UTC; compute the local date with Django's timezone utilities, not naive `datetime.now()`.
- Do not store derived numbers (streak, consistency, day status, goal percentage). Compute them when reading, in one place each (Section 9).

---

## 9. Business rules (Proposed, confirm in Section 14)

Put each rule in **one pure function** (`habits/services.py` or similar) with unit tests. Views and templates never recompute them.

- **Streak** (daily habits): consecutive local days, counting back from today, with a check-in. If today is not checked in yet, count back from yesterday (the streak is not broken until today ends). A missed day resets it to 0. The "streak terpanjang" is the maximum run ever.
- **Milestones (decided):** a habit reaches a milestone at a streak of **3, 7, 14, and 30 days**. Keep the list in one constant (for example `STREAK_MILESTONES = (3, 7, 14, 30)`) and use it everywhere: milestone detection, the "Milestone berikutnya" card, the habit detail ladder (Reached, Next, Locked), and the copy that lists the milestones. A streak that jumps past a milestone in one step (for example after editing past check-ins) sends an event for each milestone crossed, once each. Milestones beyond 30 days are not defined yet; after 30 there is no "next milestone" (show a neutral "Semua milestone tercapai").
- **Non-daily habits** (`weekdays`, `times_per_week`): the design offers them but the streak meaning is undefined. **Proposed for the MVP:** streak counts consecutive *scheduled* days for `weekdays`; for `times_per_week`, streak counts consecutive weeks that met the target. Confirm, or restrict the MVP to daily.
- **Day status:** from the habits scheduled that day: all checked = Done, some = Partial (n/m), none = Missed; future = Upcoming. Habits created later do not count for earlier days.
- **Consistency %** (history hero): check-ins done ÷ check-ins expected in the period, as an integer percent. Compare with the previous period for the "naik x%" text; hide the comparison when there is no previous data.
- **Goal progress %:** `min(100, progress / target_value * 100)`. A goal is **completed** when progress reaches the target. The checklist is a helper: it does **not** gate completion (confirm).
- **Deadline:** a goal still below target after its deadline becomes `expired` (computed on read; no background job needed for the MVP). Expired goals stay visible in history.
- **Undo a check-in** on the same day is allowed. Undoing never retracts an event that was already sent (Section 7).
- **Goals nearing deadline** ("hampir mencapai deadline"): **Proposed:** deadline within 7 days and progress under 100%.

---

## 10. Django structure and conventions (Proposed)

Inspect the repo first and follow its existing layout. If it has none yet, propose:

```
habits/                      # Django app for this module
  models.py
  forms.py                   # server-side validation (ModelForm)
  services.py                # streak, day status, consistency, goal progress, event writing
  views.py                   # thin class- or function-based views
  urls.py                    # app_name = "habits"
  templates/habits/
    habit_list.html          # Tab Habit
    goal_list.html           # Tab Goal
    history.html             # Tab Riwayat
    habit_detail.html, goal_detail.html
    empty/                   # empty states
    forms/                   # add / edit habit, add / edit goal, log progress
    partials/                # one file per component (Section 11)
  tests/
static/css/
  tokens.css                 # variables from Section 5
  components.css             # shared components
  habits.css                 # this module's screens
static/img/habits/           # decoration SVGs
```

- Views stay thin: parse request, call a service, render. Business rules live in `services.py`.
- Use `login_required` on every view; filter querysets by `request.user`; POST for every state change (check-in, undo, create, delete) with CSRF.
- Prefer server-rendered pages and normal form posts. Small interactions (opening a modal, toggling a check) may use a native `<dialog>` and a few lines of vanilla JavaScript with a working non-JS fallback page. Ask before adding htmx, Alpine, a bundler, or any JS library.
- Template partials receive plain values (strings, numbers, booleans), not model instances, where practical.
- CSS: no inline styles except a data-driven width (`style="--value: 75"`) for progress bars. Name classes consistently (for example `.btn`, `.btn--primary`, `.btn--lg`); follow the repo's convention if one exists.
- Heatmaps and the year grid are rendered as HTML/CSS (a grid of small elements) from data, not images or a charting library.
- Secrets (including any Geoapify key) stay in environment variables. Never commit `.env`.
- Suggested URLs (agree with the team; use English paths and named routes): `/habits/`, `/habits/goals/`, `/habits/history/`, `/habits/new/`, `/habits/<id>/`, `/habits/goals/new/`, `/habits/goals/<id>/`, `/habits/goals/<id>/progress/`.

---

## 11. Components to build (from Figma)

Build shared components once as template partials plus CSS, from the design system, then reuse. Variants listed here are the Figma variant names.

**Design system:**

| Component | Variants and properties |
| --- | --- |
| Button | Style: Primary, Secondary, Ghost, Inverse, Accent. Size: L, M. Shape: Pill, Rounded. Label, optional leading and trailing icon |
| Icon Button | Shape: Circle, Square. Style: Primary, Secondary, Accent, Soft, Inverse. Size: L 48, M 40 |
| Input | State: Default, Focus, Error. Label, value, helper text |
| Tag | Tips, Achievement, General, Outline |
| Avatar | Size S 32, M 40, L 56; initial from the user's name |
| Progress | Value 25, 50, 75, 100 in Figma; in code use any 0 to 100 via `--value` |
| Achievement Badge | Title |
| Navbar | Landing page `navbar` component, reused on every page |
| Alert | Info, Success, Warning, Error; dismissible optional |
| Dropdown | Trigger (Closed, Open) + Menu Item (Default, Hover, Selected, Disabled) |
| Tabs | Underline (Habit, Goal, Riwayat) and Pill (period filters) |
| Accordion | Collapsed, Expanded |

**Module components:** Habit Row (Todo, Done), Day Chip (Done, Partial, Missed, Today, Upcoming), Milestone Row (Reached, Next, Locked), Card Goal, Checklist Item (Todo, Done), Heatmap Cell (L0 to L4, Upcoming, Today), History Item, Choice Chip (Off, On), Icon Option (Off, On), and the nature decoration set.

**Notes:**

- **Navbar:** logged-in state shows the user's avatar initial and name (from the Login module) instead of the "Masuk" and "Daftar" buttons. Links: Dashboard, Carbon Tracker, Habit & Goal (active, `text/brand`), Komunitas. Link targets come from the other modules' named routes.
- **Delete button:** the design system has no danger button style. The "Ya, hapus" button uses `color/bg/danger` and `color/text/on-brand`, built by hand. Ask the team before turning it into an official variant.
- Components keep their Figma names where possible so a designer can map code to design.

---

## 12. Copy (user-facing text)

- **UI text in Bahasa Indonesia; everything developer-facing in English** (code, comments, commit messages, variable names, test names, this file). Never mix.
- Write copy inline in the template that renders it; no i18n setup unless the team adds one.
- Use "kamu" (informal), as in the designs. Warm and encouraging; no pressure.
- Greeting follows local time of day: Pagi, Siang, Sore, Malam ("SELAMAT SORE, {NAMA}").

| Where | Text |
| --- | --- |
| Tabs | Habit · Goal · Riwayat |
| Habit hero | `{n} dari {m} kebiasaan hijau sudah kamu selesaikan hari ini` · `Tinggal {k} lagi untuk hari yang sempurna.` · Tambah habit |
| Day legend | Semua habit selesai · Sebagian selesai · Tidak ada yang dicentang |
| Habit groups | Pagi · Siang · Malam · `{n} dari {m} selesai` |
| Habit meta | `{n} hari berturut-turut` · new habit: `Baru dimulai · streak pertamamu mulai hari ini` |
| Milestone side card | MILESTONE BERIKUTNYA · `Setiap milestone otomatis dikirim ke Personal Dashboard.` · Terkirim ke Dashboard · Lihat di Dashboard |
| Goal hero | `GOAL BULAN {BULAN}` · `{n} goal sedang berjalan, {k} hampir mencapai deadline` · Buat goal |
| Goal list | Goal aktif · Diurutkan dari deadline terdekat · Selesai baru-baru ini · Otomatis dikirim ke Personal Dashboard · Lihat detail · Catat progres · Lihat ringkasan |
| Goal placeholder | Buat goal baru · `Tentukan target, deadline, dan checklist. Progresnya dipantau otomatis.` |
| Add habit | Tambah habit baru · `Mulai dari yang kecil. Kamu bisa mengubahnya kapan saja.` · Nama habit · Ikon & warna · Waktu check-in (Pagi, Siang, Malam, Kapan saja) · Seberapa sering? (Setiap hari, Hari tertentu, X kali/minggu) · Pengingat · Batal · Simpan habit |
| Add habit info | `Streak dimulai dari check-in pertamamu` · `Begitu mencapai 3, 7, 14, atau 30 hari, milestone otomatis dikirim ke Personal Dashboard.` (build the list from `STREAK_MILESTONES`) |
| Create goal | Buat goal baru · `Tentukan target yang jelas dan beri batas waktu.` · Nama goal · Kategori · Target · Mulai · Deadline · Checklist (opsional) · Tambah item · Buat goal |
| Create goal info | `Goal selesai dikirim otomatis` · `Saat semua target tercapai, pencapaian ini masuk ke Personal Dashboard dan menambah rekap bulananmu.` |
| Log progress | Catat progres · Tambah berapa kali? · `Setelah disimpan: {x} / {y} kali ({p}%)` · Catatan (opsional) · Simpan progres |
| Milestone modal | MILESTONE TERCAPAI · `{n} hari berturut-turut!` · Terkirim ke Personal Dashboard · Lihat di Dashboard · Lanjutkan |
| Delete habit | Hapus habit ini? · `"{nama}" beserta riwayat check-in-nya akan dihapus. Pencapaian yang sudah terkirim ke Personal Dashboard tetap tersimpan.` · Batal · Ya, hapus |
| Empty: Habit | MULAI DARI NOL · `Belum ada kebiasaan. Mulai dari satu langkah kecil.` · Tambah habit pertama · Saran untuk memulai |
| Empty: Goal | BELUM ADA GOAL · `Tentukan satu target dengan deadline.` · Buat goal pertama · Contoh goal |
| Empty: Riwayat | RIWAYAT MASIH KOSONG · `Riwayatmu akan tumbuh di sini.` · `Belum ada aktivitas. Check-in pertamamu akan tercatat di sini lengkap dengan waktunya.` |
| History | `RIWAYAT · {BULAN} {TAHUN}` · `{n}% konsistensi bulan ini, naik {x}% dari {bulan lalu}` · Kalender {bulan} · Log aktivitas · Ringkasan {bulan} · Paling konsisten · Bulan ini / 3 bulan / Tahun |

Add new strings to this table when you add them. Never write copy that shames the user or labels a person ("malas", "gagal"); describe the data ("Terlewat", "Belum check-in").

---

## 13. Testing

- Python tests with Django's `TestCase`; no dependency on external services.
- Test each business rule in Section 9 at its edges: streak across a missed day, streak when today is not yet checked, day rollover at 00:00 WIB (use a fixed clock), longest streak, consistency with no data, goal exactly at target, deadline day itself, expired goals.
- Test event idempotency: re-checking, undoing, and re-saving never creates a second event for the same habit milestone or goal completion; deleting a habit keeps its events.
- Test access control: another user's habit or goal returns 404; anonymous requests redirect to login; every state-changing view requires POST and CSRF.
- Test form validation on the server (not only the browser).
- Check loading-free states by hand: empty, one item, many items, long names (names wrap, never overflow the card).
- Compare each built page to its reference screenshot at 1440 px.

---

## 14. Open decisions (ask Tania; do not guess)

1. **Event contract:** table versus signal versus service function, and the exact payload (Section 7). Agree with Fildza.
2. **Milestones beyond 30 days:** the list is 3, 7, 14, 30 (decided). Should 60 or 100 days exist later? Until decided, there is no milestone after 30.
3. **Non-daily habits:** support `weekdays` and `times_per_week` in the MVP, and what streak means for them.
4. **Goal completion:** does the checklist gate completion, or is progress reaching the target enough?
5. **Carbon Tracker link:** may emission and transport goals read progress from recorded trips (Callysta), or is it manual only?
6. **Onboarding link:** should onboarding answers (vehicles, initial targets) prefill suggested habits and goals?
7. **Reminders:** the form has a "Pengingat" field. Store only, hide it, or skip until there is a delivery channel?
8. **Heatmap buckets:** confirm the proposed percentage ranges (Section 6).
9. **Logo font:** Shippori Antique B1 or Fraunces (Section 5).
10. **Modals:** native `<dialog>` with JavaScript, or separate pages per form?
11. **JavaScript:** vanilla only, or is htmx / another helper allowed?
12. **URLs and route names:** English paths as suggested, and the route names for Dashboard, Login, Carbon Tracker, and Community pages.
13. **Mobile layouts:** not designed. Build desktop only for now?
14. **Data retention:** deleting a habit or goal is a hard delete in this draft. Confirm.

---

## 15. Working agreements

- Ask before adding a dependency, a new Django app, a new top-level folder, or a new architectural layer.
- Never invent emission factors, badge rules, or any value this file marks as open.
- Keep module boundaries (Section 2): no writes to other modules' tables, no Community posts from here.
- Business rules live in one tested function each; templates only display results.
- UI text in Bahasa Indonesia; all developer-facing text in English.
- Do not mention this guide, or any agent-instruction file, in code comments (Section 0).
- Do not stage or commit this guide file when asked to `git add` or commit updates (Section 0). Verify with `git diff --cached --name-only` before every commit.
- Run `python manage.py check` and `python manage.py test` before reporting work as done, and state what you ran.
- Commit messages: English, imperative mood, one logical change per commit.