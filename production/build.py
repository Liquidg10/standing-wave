#!/usr/bin/env python3
"""Build The Standing Wave static site from issues/*.md into site/.
Reproduces existing issues faithfully + adds No. 4. Generates index, issue
pages, feed.xml, and OG images. Clean (extensionless) internal links."""
import os, re, glob, html, datetime, sys, json

ROOT = os.path.dirname(os.path.abspath(__file__))
ISSUES_DIR = os.path.join(ROOT, "issues")
SITE = os.path.join(ROOT, "site")
SITE_ISSUES = os.path.join(SITE, "issues")
OG = os.path.join(SITE, "og")
BASE = "https://standingwave.ink"
LEAD_ENDPOINT = "https://gdcfvscjmnfkfwsjpaxn.supabase.co/functions/v1/musenexus-lead"
CONSENT_VERSION = "2026-07-18.1"

for d in (SITE, SITE_ISSUES, OG):
    os.makedirs(d, exist_ok=True)

# ---------- text helpers ----------
_OPENERS = " \t\n([{-—–“‘\"'"

def smarten(s):
    """Smart-quote both double and single quotes with a boundary heuristic:
    a straight quote preceded by whitespace/start-of-string/opening
    punctuation and followed by a letter or digit is an OPENING quote;
    otherwise it's CLOSING. This covers ordinary apostrophes/contractions
    correctly (the character before is always a letter, e.g. don't, it's,
    Wolff's -> always closing) *and* correctly pairs single-quote scare-
    quotes (e.g. 'why' -> ‘why’), which the previous version could not do:
    it forced every straight apostrophe to a closing curl unconditionally
    and only alternated open/close for double quotes, so a single-quoted
    phrase rendered as two closing marks (’why’). Fixed 2026-07-05 (Run
    "Sunday review") after being flagged twice as a live risk (Run No. 16
    DECISIONS.md + known_issues in MEMORY.md) rather than just avoiding the
    pattern in hand-written copy forever."""
    out = []
    n = len(s)
    for i, ch in enumerate(s):
        if ch in ("'", '"'):
            before = s[i - 1] if i > 0 else None
            after = s[i + 1] if i + 1 < n else None
            opening = (before is None or before in _OPENERS) and (after is not None and (after.isalpha() or after.isdigit()))
            if ch == "'" and opening and after is not None and after.isdigit() and s[i + 2:i + 3].isdigit():
                opening = False  # decade elision, e.g. the '90s -> the ’90s, not an opening quote
            if ch == "'":
                out.append("‘" if opening else "’")
            else:
                out.append("“" if opening else "”")
        else:
            out.append(ch)
    return "".join(out)

def esc_text(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def attr(s):
    s = smarten(s)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def inline(s):
    s = esc_text(s)
    s = smarten(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    return s

def paras(block):
    return [p.strip() for p in re.split(r"\n\s*\n", block.strip()) if p.strip()]

# ---------- parse issues ----------
def parse(path):
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
    meta_block, body = m.group(1), m.group(2)
    meta = {}
    for line in meta_block.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    meta["number"] = int(meta["number"])
    main, _, teaser = body.partition("\n≈\n")
    meta["_dek"] = paras(main)[0]
    meta["_body"] = paras(main)[1:]
    tparas = paras(teaser)
    meta["_teaser_title"] = tparas[0] if tparas else "One loop I'm watching"
    meta["_teaser"] = tparas[1:] if len(tparas) > 1 else []
    return meta

issues = sorted([parse(p) for p in glob.glob(os.path.join(ISSUES_DIR, "no-*.md"))],
                key=lambda x: x["number"])
by_num = {i["number"]: i for i in issues}
TOTAL = len(issues)

# Curated thematic cross-links (the "Related issues" block). Editorial, not sequential —
# the end-nav already does prev/next. Each entry: (target issue number, why it connects).
# Unknown/missing targets are filtered at render time, so this never breaks the build.
RELATED = {
    1:  [(6, "fire and gravity, each balanced into a shape"), (2, "the same logic, in moving water"), (10, "a pattern and not a thing — at the scale of a planet")],
    2:  [(9, "a standing wave you sit inside, on the freeway"), (10, "the same wave, the width of a world"), (1, "where the series began")],
    3:  [(1, "closed to matter, open to energy — like a flame"), (6, "the same throughput, at the scale of a star"), (2, "a shape held up by what pours through it")],
    4:  [(5, "the other loop kept alive only by tending"), (7, "a living rhythm that resets itself"), (3, "a small closed world on a shelf")],
    5:  [(4, "the other tended loop — held in shape by use"), (8, "a pattern with no one conducting it"), (1, "a shape that outlives its own substance")],
    6:  [(1, "the flame's logic, scaled up to a sun"), (10, "another balance of forces, on a planet"), (3, "a world run by what flows through it")],
    7:  [(8, "the firefly math was first written for the heart"), (4, "another loop that keeps itself alive"), (1, "a shape made entirely of replacement")],
    8:  [(7, "the heartbeat its math was built from"), (9, "the dark twin — the same crowd, a jam instead of a beat"), (5, "order with no one in charge")],
    9:  [(2, "the standing wave you can wade into"), (8, "the leaderless meadow it inverts"), (10, "the same trick, run for centuries")],
    10: [(11, "its living opposite — a wave that keeps every one of its dead"), (2, "the standing wave, at human scale"), (9, "the minutes-long version, on the freeway")],
    11: [(1, "a shape that is almost all replacement — so are you"), (3, "the other world that runs on sunlight, sealed on a shelf"), (10, "its opposite: a storm that keeps none of its dead")],
    12: [(11, "the reef's calcium bargain, run inside your own body"), (1, "the same thesis, stated most literally: so do you"), (7, "another self-running system built from arguing cells")],
    13: [(11, "the other symbiosis — sugar for shelter, on a reef instead of a rock"), (4, "another loop kept alive only by re-forming the partnership"), (10, "the deepest 'pattern, not thing' case, at planetary scale instead of a handshake")],
    14: [(13, "the living cousin next door — same patience, but something alive is choosing"), (11, "another mineral shape built by a flow — aragonite instead of calcite"), (5, "the deep past reconstructed from patient, indirect evidence")],
    15: [(9, "the exact same traffic-jam physics, run a trillion times bigger"), (10, "another pattern, not a thing, holding its shape across a whole world"), (1, "the series' first case, echoed at the largest scale it will ever reach")],
    16: [(1, "the series' first case, echoed at the smallest scale it will ever reach"), (12, "the same so-do-you bargain, one level up — a skeleton instead of a membrane"), (3, "another structure defined entirely by what it lets past its own boundary")],
    17: [(10, "its immortal opposite — a storm with no surface to drag against and no fuel to run out"), (6, "the same heat-engine logic, run on a star instead of an ocean"), (9, "the same self-reinforcing loop, once a phantom traffic jam instead of a storm")],
    18: [(7, "the body's other self-oscillator — but this one's clock is chemical, not aerodynamic"), (8, "the same 'nobody's timing this' thesis, run on tissue instead of a hillside"), (17, "the other engine that only runs as long as a continuous flow keeps pushing on it")],
    19: [(10, "its frictionless opposite — a spin with no tax collector, spared this one's whole plot"), (17, "the same 'single point of failure' shape, paid in ocean heat instead of angular momentum"), (1, "the series' founding thesis, restated in pure mechanics: rented, not stored")],
    20: [(19, "the same continuous payment against loss, run in gears instead of angular momentum"), (4, "the other loop that survives only because a person keeps showing up to tend it"), (7, "the other standing wave built to literally keep time, on its own rhythm instead of a gear train")],
    21: [(2, "the same standing shape held up by moving water, minus the spin"), (9, "the same never-the-same-material trick, run on a highway instead of a drain"), (17, "the same combined-vortex shape, scaled up into a storm's own eye")],
    22: [(18, "the aerodynamic cousin — a self-sustaining oscillator built from moving air instead of friction"), (19, "the same real, mapped failure threshold — cross it and the loop doesn't fade, it just stops being itself"), (1, "the founding thesis, run at its fastest: a shape that starts and stops on command")],
    23: [(1, "the same substance — fire — kept alive by an institution instead of a wick"), (5, "the closest cousin in the series: a standing wave held up by speakers who never all overlap"), (4, "the other loop that only survives because someone shows up to tend it on a schedule")],
    24: [(23, "the same duty-roster logic, run in microseconds instead of human lifetimes, by circuitry with no memory of doing it"), (20, "the same continuous small payment against loss, paid in electrons instead of a falling weight"), (14, "its total opposite: a record built once and left permanent, instead of one retold from scratch, forever")],
    25: [(7, "the body's other self-oscillator — electrical instead of molecular"), (18, "the same 'nobody times each cycle' thesis, run on airflow instead of gene expression"), (24, "the same continuous-repair loop, run in cells instead of silicon, at a completely different tempo")],
    26: [(19, "the same angular-momentum bargain, spent down over billions of years instead of minutes"), (21, "the same conserved-spin shape, a hole in water instead of a beam in space"), (8, "the same 'nobody's timing this' thesis — a signal that only looks sent on purpose")],
    27: [(9, "the same trick at a different scale — a pattern stable in aggregate, built from parts that are each only ever passing through"), (1, "the founding thesis, run across acres instead of a wick: a shape that outlives nearly everything that ever made it up"), (12, "the same 'so do you' bargain — a structure being constantly torn down and rebuilt in pieces, never all at once")],
}

# One-line subject summaries for llms.txt (an AI-agent-facing table of contents,
# separate from the human-facing "blurb" paragraph). Hand-maintained like RELATED
# and START_PICKS above — add one line per new issue.
ONE_LINERS = {
    1: "a candle flame: matter flows through continuously, only the shape persists",
    2: "a standing river wave: a pattern needs something to push against to hold its shape",
    3: "a sealed bottle garden, decades old: materially closed, energetically open, like Earth itself",
    4: "a sourdough starter: a standing wave of microbes, kept alive only by feeding",
    5: "a language: no original copy, held in shape only by continuous use",
    6: "a star: hydrostatic equilibrium, a standing truce between gravity and fusion",
    7: "the heartbeat: the sinoatrial node's self-winding electrical rhythm",
    8: "fireflies: spontaneous synchronization with no leader and no signal",
    9: "a phantom traffic jam: a self-sustaining stop-wave that needs no cause",
    10: "Jupiter's Great Red Spot: a centuries-old anticyclone with no surface to slow it down",
    11: "a coral reef: a living veneer over a mountain of its own cemented dead",
    12: "the human skeleton: continuously dissolved and rebuilt by competing cells",
    13: "a lichen: a fungus and an alga (sometimes three partners), re-forming their bargain every generation",
    14: "a stalactite: a stone built entirely from water, none of which is still inside it",
    15: "a spiral galaxy's arms: a density wave that stars drift through and leave, not a fixed population",
    16: "a cell membrane: two molecules thick and structurally permanent-feeling, yet built entirely from motion",
    17: "a hurricane: a heat engine with exactly one fuel source, able to collapse within hours of losing it",
    18: "the vocal folds: a myoelastic-aerodynamic flutter, no nerve timing each cycle, just moving air",
    19: "a spinning top: stability rented continuously from angular momentum, gone the instant the spin runs out",
    20: "a pendulum clock's escapement: a decaying swing paid back one precisely timed tick at a time",
    21: "a bathtub whirlpool: angular momentum made visible, a hole-shaped habit fed by water that's never the same water twice",
    22: "a bowed violin string: a stick-slip cycle repeating hundreds of times a second, first traced by Helmholtz's vibration microscope",
    23: "an eternal flame: not a fire that never goes out, but an unbroken duty roster of people who never let it stay out",
    24: "a DRAM chip: every bit's charge leaks in milliseconds, sensed and rewritten by a controller before anyone would notice",
    25: "the circadian clock: nearly every cell keeps its own day using a gene loop that builds the exact protein that will shut it off",
    26: "a pulsar: a dead star's tilted magnetic beam, swept past Earth once per rotation by nothing but momentum",
    27: "an old-growth forest: canopy patches cycling through collapse and regrowth so the landscape looks stable while few of its trees do",
}

# Short topic/keyword tags per issue — sitewide SEO + AI-agent-facing metadata, distinct
# from the human-facing ONE_LINERS above. Added 2026-07-10 (No. 26): audited head() and
# the issue-page JSON-LD directly and confirmed neither ever emitted a <meta
# name="keywords"> tag nor a schema.org "keywords" property, despite every issue having a
# clear, real subject and scientific domain — a genuine, unaddressed gap in the site's
# existing crawler-legibility streak (RSS -> JSON Feed -> sitemap lastmod -> BreadcrumbList
# -> llms.txt). Deliberately metadata-only (no new visible page chrome, no new CSS, no
# JS) to keep this run's risk low: it helps search engines and AI agents classify each
# issue's actual topic without adding any reader-facing surface to design, style, or
# regression-test. Backfilled for all 26 existing issues in one pass (not just new ones
# going forward), each hand-picked from that issue's real subject matter, 3-5 short
# phrases, most-specific first. Unlisted issue numbers simply emit no keywords tag.
TOPICS = {
    1:  ["candle flame", "combustion", "self-sustaining systems", "matter and energy flow"],
    2:  ["standing wave", "hydraulic jump", "river surfing", "fluid dynamics"],
    3:  ["closed ecosystem", "terrarium", "biosphere", "carbon and water cycles"],
    4:  ["sourdough starter", "wild yeast fermentation", "microbial ecology", "lactobacillus"],
    5:  ["language change", "historical linguistics", "oral tradition", "Proto-Indo-European"],
    6:  ["hydrostatic equilibrium", "stellar physics", "nuclear fusion", "stars"],
    7:  ["sinoatrial node", "cardiac pacemaker cells", "heartbeat", "cardiac electrophysiology"],
    8:  ["firefly synchronization", "coupled oscillators", "Kuramoto model", "emergent behavior"],
    9:  ["phantom traffic jam", "traffic flow physics", "stop-and-go waves", "emergent patterns"],
    10: ["Great Red Spot", "Jupiter", "anticyclone", "planetary atmospheres"],
    11: ["coral reef", "zooxanthellae symbiosis", "calcium carbonate", "coral bleaching"],
    12: ["bone remodeling", "osteoclasts and osteoblasts", "skeletal biology", "human physiology"],
    13: ["lichen symbiosis", "fungus and alga partnership", "lichenometry", "extremophile biology"],
    14: ["stalactite formation", "karst geology", "cave dripstone", "calcite precipitation"],
    15: ["spiral galaxy arms", "density wave theory", "galactic dynamics", "astrophysics"],
    16: ["cell membrane", "lipid bilayer", "fluid mosaic model", "cell biology"],
    17: ["hurricane structure", "tropical cyclone heat engine", "warm core", "atmospheric science"],
    18: ["vocal folds", "phonation physics", "myoelastic-aerodynamic theory", "voice production"],
    19: ["gyroscopic precession", "spinning top physics", "angular momentum", "classical mechanics"],
    20: ["pendulum clock", "anchor escapement", "horology", "mechanical timekeeping"],
    21: ["bathtub vortex", "whirlpool physics", "angular momentum conservation", "fluid dynamics"],
    22: ["bowed string physics", "Helmholtz motion", "stick-slip friction", "violin acoustics"],
    23: ["eternal flame", "Vestal Virgins", "institutional continuity", "ritual maintenance"],
    24: ["DRAM memory refresh", "computer memory", "capacitor charge leakage", "computer architecture"],
    25: ["circadian rhythm", "transcription-translation feedback loop", "molecular clock", "chronobiology"],
    26: ["pulsar", "neutron star", "Jocelyn Bell Burnell", "pulsar timing array", "gravitational waves"],
    27: ["old-growth forest", "canopy gap dynamics", "shifting-mosaic steady state", "forest ecology", "gap-phase regeneration"],
}

# Curated "Further reading" citations per issue — a small, hand-picked bibliography
# (2-3 sources each) drawn from the actual research notes/*.md logged for that issue's
# drafting, not invented after the fact. Added 2026-07-09 (No. 24): the site's stated
# brand promise ("Accuracy is the brand — verify with current sources, cite") had, for
# 23 issues, only ever been kept in local notes/ files invisible to readers — this
# makes a slice of that citation trail public. Entries: (label, url); url may be None
# for a source with no stable public link, rendered as plain (unlinked) text instead.
# Issues 1-3 predated the notes/*.md convention (started at No. 4); that gap was closed
# 2026-07-10 (Run No. 27) by reconstructing notes/no-1/2/3-sources.md HONESTLY — fresh
# web searches re-verifying each essay's actual factual claims, not citations invented
# to match what was already published. No shipped essay text changed; every claim held
# up. Unlisted issue numbers simply render no block (none remain unlisted below No. 27).
SOURCES = {
    1: [("Wikipedia, “The Chemical History of a Candle”", "https://en.wikipedia.org/wiki/The_Chemical_History_of_a_Candle"),
        ("Project Gutenberg, Faraday's “The Chemical History of a Candle” (full text)", "https://www.gutenberg.org/ebooks/14474")],
    2: [("Wikipedia, “Eisbach (Isar)”", "https://en.wikipedia.org/wiki/Eisbach_(Isar)"),
        ("Wikipedia, “Froude number”", "https://en.wikipedia.org/wiki/Froude_number")],
    3: [("Snopes, fact-checking David Latimer's sealed bottle garden", "https://www.snopes.com/fact-check/self-sustaining-bottle-garden-1960/"),
        ("Wikipedia, “Closed ecological system”", "https://en.wikipedia.org/wiki/Closed_ecological_system")],
    4: [("Boudin Bakery, “Our Story” (the 1849 San Francisco mother dough)", "https://boudinbakery.com/our-story/"),
        ("eLife, sourdough starter microbial ecology", "https://elifesciences.org/articles/61644")],
    5: [("Wikipedia, “Proto-Indo-European language”", "https://en.wikipedia.org/wiki/Proto-Indo-European_language"),
        ("Nature, ancient-DNA dating of the Indo-European homeland (2024)", "https://www.nature.com/articles/s41586-024-08531-5")],
    6: [("EUROfusion, “Fusion on the Sun”", "https://euro-fusion.org/fusion/fusion-on-the-sun/"),
        ("Stony Brook Astronomy, the Kelvin–Helmholtz timescale", "https://www.astro.sunysb.edu/fwalter/AST101/k-h.html")],
    7: [("Wikipedia, “Sinoatrial node”", "https://en.wikipedia.org/wiki/Sinoatrial_node"),
        ("PMC, cardiac automaticity and the funny current", "https://pmc.ncbi.nlm.nih.gov/articles/PMC5830425/")],
    8: [("Science Advances, firefly synchronization dynamics", "https://www.science.org/doi/10.1126/sciadv.abg9259"),
        ("Firefly.org, synchronous fireflies at Elkmont", "https://www.firefly.org/synchronous-fireflies.html")],
    9: [("Sugiyama et al., “Traffic jams without bottlenecks,” New Journal of Physics 10 (2008)", None),
        ("Stern et al., “Dissipation of stop-and-go waves via control of autonomous vehicles,” Transportation Research Part C (2018)", None)],
    10: [("NASA Science, Hubble measures Jupiter's shrinking Great Red Spot", "https://science.nasa.gov/missions/hubble/hubble-shows-that-jupiters-great-red-spot-is-smaller-than-ever-seen-before/"),
         ("Yale News, is today's Great Red Spot a different storm? (2024)", "https://news.yale.edu/2024/07/18/new-explanation-jupiters-great-shrinking-spot")],
    11: [("NOAA, the fourth global coral bleaching event", "https://www.noaa.gov/news-release/noaa-confirms-4th-global-coral-bleaching-event"),
         ("Smithsonian Ocean, zooxanthellae and coral bleaching", "https://ocean.si.edu/ocean-life/invertebrates/zooxanthellae-and-coral-bleaching")],
    12: [("Wikipedia, “Bone remodeling”", "https://en.wikipedia.org/wiki/Bone_remodeling"),
         ("PMC, the osteoclast–osteoblast remodeling cycle", "https://pmc.ncbi.nlm.nih.gov/articles/PMC2880220/")],
    13: [("Encyclopaedia Britannica, lichens", "https://www.britannica.com/science/fungus/Lichens"),
         ("ScienceDaily, a hidden third partner in lichen symbiosis (Spribille et al., 2016)", "https://www.sciencedaily.com/releases/2016/07/160721151213.htm")],
    14: [("Wikipedia, “Stalactite”", "https://en.wikipedia.org/wiki/Stalactite"),
         ("Scientific Reports, uranium–thorium dating of cave dripstone", "https://www.nature.com/articles/s41598-017-00474-4")],
    15: [("Wikipedia, “Density wave theory”", "https://en.wikipedia.org/wiki/Density_wave_theory"),
         ("Monthly Notices of the RAS, spiral-arm pattern speed from Gaia data", "https://academic.oup.com/mnras/article/486/4/5726/5484903")],
    16: [("Singer & Nicolson, “The Fluid Mosaic Model,” Science (1972)", "https://www.science.org/doi/10.1126/science.175.4023.720"),
         ("Wikipedia, “Fluid mosaic model”", "https://en.wikipedia.org/wiki/Fluid_mosaic_model")],
    17: [("Kerry Emanuel (MIT), the theoretical limits of hurricane intensity", "https://emanuel.mit.edu/limits-hurricane-intensity/"),
         ("NOAA AOML, hurricane structure research", "https://www.aoml.noaa.gov/hrd/project96/ls_proj2.html")],
    18: [("van den Berg, “Myoelastic-Aerodynamic Theory of Voice Production,” JSHR (1958)", "https://pubs.asha.org/doi/10.1044/jshr.0103.227"),
         ("Voice Science Works, the myoelastic-aerodynamic theory", "https://www.voicescience.org/lexicon/myoelastic-aerodynamic-theory-of-voice-production/")],
    19: [("Wikipedia, “Spinning top”", "https://en.wikipedia.org/wiki/Spinning_top"),
         ("Cross, “The rise and fall of spinning tops,” American Journal of Physics (2013)", "https://pubs.aip.org/aapt/ajp/article/81/4/280/1041965/The-rise-and-fall-of-spinning-tops")],
    20: [("Wikipedia, “Anchor escapement”", "https://en.wikipedia.org/wiki/Anchor_escapement"),
         ("Encyclopaedia Britannica, “Escapement”", "https://www.britannica.com/technology/escapement")],
    21: [("ScienceDirect, the Rankine combined vortex", "https://www.sciencedirect.com/topics/engineering/rankine-vortex"),
         ("Snopes, fact-checking the bathtub-drain Coriolis myth", "https://www.snopes.com/fact-check/coriolis-effect/")],
    22: [("Stanford CCRMA, Helmholtz motion in a bowed string", "https://ccrma.stanford.edu/realsimple/travelingwaves/Helmholtz_Motion.html"),
         ("Wikipedia, “C. V. Raman”", "https://en.wikipedia.org/wiki/C._V._Raman")],
    23: [("Encyclopaedia Britannica, “Vestal Virgins”", "https://www.britannica.com/topic/Vestal-Virgins"),
         ("Wikipedia, “Vestal Virgin”", "https://en.wikipedia.org/wiki/Vestal_Virgin")],
    24: [("Wikipedia, “Memory refresh”", "https://en.wikipedia.org/wiki/Memory_refresh"),
         ("Wikipedia, “Robert H. Dennard”", "https://en.wikipedia.org/wiki/Robert_H._Dennard"),
         ("Revisiting RowHammer: an experimental analysis of modern DRAM devices (arXiv, 2020)", "https://arxiv.org/pdf/2005.13121")],
    25: [("NobelPrize.org, the 2017 Nobel Prize in Physiology or Medicine (press release)", "https://www.nobelprize.org/prizes/medicine/2017/press-release/"),
         ("PMC, the mammalian circadian timing system and the SCN as its pacemaker", "https://pmc.ncbi.nlm.nih.gov/articles/PMC6466121/"),
         ("PNAS, the 50th anniversary of the Konopka and Benzer 1971 paper", "https://www.pnas.org/doi/10.1073/pnas.2110171118")],
    26: [("Britannica, “Jocelyn Bell Burnell”", "https://www.britannica.com/biography/Jocelyn-Bell-Burnell"),
         ("Nature, Davis, Taylor, Weisberg & Backer (1985), high-precision timing of PSR1937+21", "https://www.nature.com/articles/315547a0"),
         ("NANOGrav, “Pulsars as Cosmic Clocks”", "https://nanograv.org/science/topics/pulsars-cosmic-clocks")],
    27: [("The Encyclopedia of Earth, “Shifting mosaic steady-state”", "https://editors.eol.org/eoearth/wiki/Shifting_mosaic_steady-state"),
         ("Ecological Continuity Trust, “Lady Park Wood Handover”", "https://www.ecologicalcontinuitytrust.org/lpw-handover"),
         ("Wikipedia, “Białowieża Forest”", "https://en.wikipedia.org/wiki/Bia%C5%82owie%C5%BCa_Forest")],
}

# Curated entry points for the /start on-ramp page. Newcomers arrive from social / the
# newsletter, where the reverse-chron home page is the worst possible first impression
# (they hit the newest issue cold). This page hands them three good doors instead.
START_PICKS = [
    (1, "Where it starts: a candle flame, and the whole idea in miniature — a shape that survives only by letting its substance burn away."),
    (3, "The one people email about: a sealed bottle garden, undisturbed for decades — a whole living world running on nothing but light."),
    (7, "The one that's about you: your heartbeat, a rhythm the heart makes for itself and would keep making in a dish on a bench."),
]

# ---------- templates ----------
CSS = """:root{--paper:#faf6ef;--ink:#23201b;--muted:#6f685c;--rule:#e2d9c9;--accent:#9a3b26;--measure:34rem}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font-family:Georgia,"Iowan Old Style","Palatino Linotype",Palatino,serif;font-size:1.18rem;line-height:1.66;text-rendering:optimizeLegibility;-webkit-font-smoothing:antialiased}
.wrap{max-width:var(--measure);margin:0 auto;padding:2.4rem 1.3rem 4rem}
.tagline{font-size:.8rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:0 0 1.6rem}
nav.top{font-size:.95rem;margin-bottom:2.6rem;display:flex;gap:1.1rem;flex-wrap:wrap}
a{color:var(--accent);text-decoration:none;border-bottom:1px solid rgba(154,59,38,.28)}
a:hover{border-bottom-color:var(--accent)}
nav.top a{color:var(--muted);border:0}nav.top a:hover{color:var(--ink)}
.issue-meta{font-size:.82rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:.6rem}
h1{font-size:2.35rem;line-height:1.12;letter-spacing:-.01em;margin:.2rem 0 1.3rem;font-weight:600}
h1.site{font-size:2rem;margin:.2rem 0 1.1rem}
h1.site a{border:0;color:var(--ink)}
.dek{font-size:1.32rem;line-height:1.5;color:#3a352d;font-style:italic;margin:0 0 2.1rem;padding-bottom:1.6rem;border-bottom:1px solid var(--rule)}
p{margin:0 0 1.25rem}
.divider{text-align:center;color:var(--accent);font-size:1.7rem;margin:2.8rem 0 2rem;opacity:.8}
.watching{background:#f3ecdf;border:1px solid var(--rule);border-radius:10px;padding:1.4rem 1.5rem;margin:0 0 2.6rem}
.watching h2{font-size:.82rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:0 0 .7rem;font-weight:600}
.watching p{margin:0;font-size:1.1rem}
.endnav{display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap;font-size:.92rem;color:var(--muted);margin:2.4rem 0 1.4rem}
.endnav .count{color:var(--muted)}
.subscribe{border-top:1px solid var(--rule);padding-top:1.6rem;font-size:1.02rem;color:#3a352d}
.subscribe>strong{display:block;color:var(--ink);font-size:1.12rem;margin-bottom:.25rem}
.subscribe-form{margin:1rem 0 .65rem;padding:1rem;border:1px solid var(--rule);border-radius:10px;background:#f3ecdf}
.subscribe-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.65rem}
.subscribe-label{display:block;font-size:.88rem;color:var(--muted);margin:0 0 .35rem}
.subscribe-form input[type=email]{width:100%;min-width:0;padding:.7rem .8rem;border:1px solid var(--rule);border-radius:7px;background:var(--paper);color:var(--ink);font:inherit;font-size:1rem}
.subscribe-form input[type=email]:focus{outline:3px solid rgba(154,59,38,.22);border-color:var(--accent)}
.subscribe-form button{align-self:end;padding:.72rem 1rem;border:0;border-radius:7px;background:var(--accent);color:#fff;font:inherit;font-size:.95rem;font-weight:600;cursor:pointer}
.subscribe-form button:hover{opacity:.88}.subscribe-form button:disabled{cursor:wait;opacity:.65}
.subscribe-consent{display:flex;align-items:flex-start;gap:.55rem;margin:.7rem 0 0;color:var(--muted);font-size:.84rem;line-height:1.45}
.subscribe-consent input{margin-top:.25rem;accent-color:var(--accent)}
.subscribe-status{min-height:1.35rem;margin:.55rem 0 0;font-size:.86rem;color:var(--muted)}
.subscribe-status.error{color:var(--accent)}.subscribe-status.success{color:#42704d}
.subscribe-note{margin:.45rem 0 0;color:var(--muted);font-size:.9rem}
.subscribe-hp{position:absolute!important;left:-10000px!important;width:1px!important;height:1px!important;overflow:hidden!important}
footer{border-top:1px solid var(--rule);margin-top:2.6rem;padding-top:1.4rem;font-size:.85rem;color:var(--muted);line-height:1.6}
.issue-list{list-style:none;padding:0;margin:2rem 0 0}
.issue-list li{margin:0 0 2.1rem;padding:0 0 1.9rem;border-bottom:1px solid var(--rule)}
.issue-list h2{font-size:1.5rem;line-height:1.2;margin:.15rem 0 .5rem;font-weight:600}
.issue-list h2 a{color:var(--ink);border:0}
.issue-list h2 a:hover{color:var(--accent)}
.issue-list .blurb{margin:0;color:#46413a;font-size:1.06rem}
.intro{font-size:1.12rem;color:#3a352d}
.starthere{font-size:1rem;color:var(--muted);margin:.3rem 0 0}
.related{border-top:1px solid var(--rule);margin-top:2.2rem;padding-top:1.3rem}
.related h2{font-size:.82rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:0 0 .9rem;font-weight:600}
.related ul{list-style:none;padding:0;margin:0}
.related li{margin:0 0 .8rem;line-height:1.4}
.related li a{font-size:1.06rem;border:0;color:var(--ink)}
.related li a:hover{color:var(--accent)}
.related .why{display:block;font-size:.92rem;color:var(--muted);border:0}
/* "Further reading" — a small curated bibliography per issue (see SOURCES in build.py).
   Added 2026-07-09 (No. 24). Styled like .related (same quiet, uppercase-label
   convention) but kept OUT of the print stylesheet's hidden-chrome list on purpose —
   unlike nav/subscribe/related, a source list is real editorial/citation content, the
   same reasoning that already keeps the "one loop I'm watching" teaser visible on paper. */
.sources{border-top:1px solid var(--rule);margin-top:1.6rem;padding-top:1.2rem}
.sources h2{font-size:.82rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:0 0 .8rem;font-weight:600}
.sources ul{list-style:none;padding:0;margin:0}
.sources li{margin:0 0 .55rem;line-height:1.4;font-size:.98rem;color:#3a352d}
.sources li a{color:var(--ink)}
.sources li a:hover{color:var(--accent)}
/* Skip-to-content link (keyboard/screen-reader accessibility) — invisible until it
   receives keyboard focus, at which point it's the very first stop in the tab order
   on every page, letting a keyboard or screen-reader reader jump straight past the
   repeated top nav to the actual issue text. Paired with an explicit focus-visible
   outline below, since the browser default outline can be easy to lose against the
   paper background. Added 2026-07-06 (No. 19) — the first accessibility-specific
   growth feature after several rounds of crawler/AI-agent/reader-onboarding work. */
.skip-link{position:absolute;left:-9999px;top:0;background:var(--accent);color:#fff;
  padding:.7rem 1.1rem;z-index:100;border-radius:0 0 8px 0;font-size:.95rem;border:0}
.skip-link:focus{left:0}
a:focus-visible,.skip-link:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
@media (max-width:480px){body{font-size:1.1rem}h1{font-size:1.95rem}.dek{font-size:1.18rem}.subscribe-row{grid-template-columns:1fr}.subscribe-form button{width:100%}}
/* Keyboard-nav discoverability hint — added 2026-07-07 (No. 21), paired with the
   inline keydown-listener script in issue_html(). Quiet by design: same muted
   tone as the byline, not a call-to-action. */
.kbdhint{color:var(--muted);font-size:.85rem;margin:.35rem 0 1.5rem}
/* "Share this issue" control — added 2026-07-08 (No. 22). No-JS-safe default is a
   plain, selectable URL (works via copy-paste with zero JavaScript); progressively
   enhanced into a real button that calls the native Web Share sheet on devices that
   support it, or copies the link to the clipboard with a short text confirmation
   otherwise. First reader-facing feature aimed at lowering the friction of passing a
   single issue on, distinct from the author-run distribution kits. */
.share{border-top:1px solid var(--rule);padding-top:1.4rem;margin:0 0 1.6rem;font-size:1rem;color:var(--muted)}
.share code{font-size:.92rem;word-break:break-all;color:var(--ink)}
.share-btn{font:inherit;font-size:.98rem;background:var(--accent);color:#fff;border:0;border-radius:7px;padding:.55rem 1.05rem;cursor:pointer}
.share-btn:hover{opacity:.88}
.share-btn:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
/* "Read a random issue" — added 2026-07-08 (No. 23), sitewide (issue pages, home,
   /start). The print stylesheet has hidden a #read-random selector since it was
   written (No. 20) but nothing ever used that id — this was the 404 page's own
   "read a random issue" trick (see not_found_html()), rolled out everywhere else
   too, so the archive gets a genuine shuffle-discovery path beyond the reverse-chron
   home page and the three curated /start picks. No-JS-safe default points at
   /start; the inline script (identical pattern to the 404 page's) rewrites it to a
   real random issue, excluding the issue the reader is already on. */
.randlink{font-size:1rem;color:var(--muted);margin:.3rem 0 0}
/* Automatic dark mode, keyed off the reader's OS/browser preference (no toggle,
   no JS, no stored state — see the paired theme-color <meta> tags in head()).
   Re-themes the CSS custom properties in :root, then overrides the handful of
   rules below that predate the variable system and still hardcode a literal
   hex value instead of var(--ink)/var(--muted). Added 2026-07-05 (No. 17). */
@media (prefers-color-scheme:dark){
:root{--paper:#1c1a17;--ink:#e9e2d3;--muted:#a89e8d;--rule:#3a352c;--accent:#e0906f}
.watching{background:#26221d}
.dek,.intro,.subscribe,.sources li{color:#d9d0c0}
.issue-list .blurb{color:#cfc6b4}
.subscribe-form{background:#26221d}.subscribe-status.success{color:#8fcf9c}
}
/* Print stylesheet — added 2026-07-07 (No. 20). Reading an issue on paper (or
   "Print to PDF") had never been considered: without this, a printed page carried
   full site chrome (nav, subscribe box, related-issues links, footer nav — none of
   it useful once ink is on paper), plus dark mode's near-black background if the
   reader's OS was set to dark, which most browsers still try to honor when printing
   and which wastes toner/ink for no reason. This forces light paper + dark ink
   regardless of color-scheme preference, drops every purely-navigational element,
   and leaves only the masthead, title, byline, and the issue's own text — including
   the "one loop I'm watching" teaser, which is real editorial content, not chrome. */
@media print{
  :root{--paper:#fff;--ink:#111;--muted:#444;--rule:#ccc;--accent:#000}
  .skip-link,nav.top,.subscribe,.related,footer,#read-random,.kbdhint,.share{display:none!important}
  body{background:#fff;color:#111}
  a{color:#111;text-decoration:underline}
  .wrap{max-width:100%;padding:0 .25in}
  h1,.dek{page-break-after:avoid}
  .watching{background:#fff;border:1px solid #ccc}
  body::after{content:"The Standing Wave · standingwave.ink";display:block;
    text-align:center;margin-top:2rem;font-size:.75rem;color:#666}
}
"""

def head(title, desc, canonical, og_title, og_desc, og_img, og_type, tw_desc, pub=None, ld=None, prev_url=None, next_url=None, keywords=None):
    t = []
    t.append("<!doctype html>")
    t.append('<html lang="en"><head>')
    t.append('<meta charset="utf-8">')
    t.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    t.append("<title>%s</title>" % attr(title))
    t.append('<link rel="canonical" href="%s">' % canonical)
    # Series pagination hints — help crawlers read the issues as an ordered sequence.
    if prev_url:
        t.append('<link rel="prev" href="%s">' % prev_url)
    if next_url:
        t.append('<link rel="next" href="%s">' % next_url)
    t.append('<meta name="description" content="%s">' % attr(desc))
    # Per-issue topic tags (see TOPICS above) — metadata-only SEO/AI-agent-facing
    # signal, added 2026-07-10 (No. 26). Absent on pages with no TOPICS entry.
    if keywords:
        t.append('<meta name="keywords" content="%s">' % attr(keywords))
    # Allow large image previews + full text snippets in search / social unfurls.
    t.append('<meta name="robots" content="max-image-preview:large, max-snippet:-1, max-video-preview:-1">')
    t.append('<link rel="stylesheet" href="/style.css">')
    # Favicon / tab + bookmark identity (SVG primary, PNG fallbacks) — see favicon.svg / favicon.png / apple-touch-icon.png below.
    t.append('<link rel="icon" type="image/svg+xml" href="/favicon.svg">')
    t.append('<link rel="icon" type="image/png" sizes="48x48" href="/favicon.png">')
    t.append('<link rel="apple-touch-icon" href="/apple-touch-icon.png">')
    # Web app manifest — lets Android/desktop "Add to Home Screen"/"Install" use the
    # brand icon + paper background instead of a generic placeholder (iOS already
    # covered by apple-touch-icon above). theme-color tints the mobile browser chrome
    # to match the paper background, so the tab bar reads as part of the page.
    t.append('<link rel="manifest" href="/site.webmanifest">')
    # Two theme-color tags (one per color-scheme media query) instead of one static
    # value, so the mobile tab bar follows the reader's own light/dark preference —
    # paired with the prefers-color-scheme block in CSS below. Most Safari/Chrome
    # versions in active use already honor the media attribute on this tag.
    t.append('<meta name="theme-color" media="(prefers-color-scheme: light)" content="#faf6ef">')
    t.append('<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#1c1a17">')
    t.append('<link rel="alternate" type="application/rss+xml" title="The Standing Wave" href="%s/feed.xml">' % BASE)
    t.append('<link rel="alternate" type="application/json" title="The Standing Wave (JSON Feed)" href="%s/feed.json">' % BASE)
    t.append('<meta name="author" content="Mark">')
    if pub:
        t.append('<meta property="article:published_time" content="%s">' % pub)
        t.append('<meta name="article:author" content="Mark">')
    t.append('<meta property="og:site_name" content="The Standing Wave">')
    t.append('<meta property="og:type" content="%s">' % og_type)
    t.append('<meta property="og:title" content="%s">' % attr(og_title))
    t.append('<meta property="og:description" content="%s">' % attr(og_desc))
    t.append('<meta property="og:url" content="%s">' % canonical)
    t.append('<meta property="og:image" content="%s">' % og_img)
    t.append('<meta property="og:image:alt" content="%s">' % attr(og_title))
    t.append('<meta property="og:image:width" content="1200">')
    t.append('<meta property="og:image:height" content="630">')
    t.append('<meta property="og:image:type" content="image/png">')
    t.append('<meta property="og:locale" content="en_US">')
    t.append('<meta name="twitter:card" content="summary_large_image">')
    t.append('<meta name="twitter:title" content="%s">' % attr(og_title))
    t.append('<meta name="twitter:description" content="%s">' % attr(tw_desc))
    t.append('<meta name="twitter:image" content="%s">' % og_img)
    t.append('<meta name="twitter:image:alt" content="%s">' % attr(og_title))
    if ld:
        # JSON-LD structured data (schema.org). Raw JSON inside the script tag — no HTML escaping.
        t.append('<script type="application/ld+json">%s</script>' % json.dumps(ld, ensure_ascii=False, separators=(",", ":")))
    t.append("</head><body>")
    return "\n".join(t)

PUBLISHER_LD = {"@type": "Organization", "name": "The Standing Wave", "url": BASE,
                "logo": {"@type": "ImageObject", "url": "%s/og/standingwave.png" % BASE}}

def breadcrumb_ld(name, url):
    # BreadcrumbList structured data (schema.org) — Home > <issue title>. A second,
    # independent JSON-LD block alongside the existing BlogPosting/Blog markup (search
    # engines support multiple <script type="application/ld+json"> tags per page). Lets
    # a search result show "standingwave.ink > A Wave You Speak With" instead of a bare
    # URL, and gives crawlers an explicit, machine-readable site hierarchy. Added
    # 2026-07-06 (No. 18) — the last of the three reader/crawler-facing gaps identified
    # by the Sunday-review build.py audit (dark mode and a custom 404 were the other two;
    # client-side search remains the one deliberately not built, since a full search index
    # is disproportionate machinery for 18 short items — see DECISIONS.md).
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "The Standing Wave", "item": BASE + "/"},
            {"@type": "ListItem", "position": 2, "name": name, "item": url},
        ],
    }

TOPNAV = ('<p class="tagline">Field notes on things that run themselves</p>\n'
          '<nav class="top"><a href="/">The Standing Wave</a>'
          '<a href="/">← All issues</a>'
          '<a href="/start">Start here</a>'
          '<a href="/about">About</a></nav>')

# Skip-to-content link — first focusable element on every page (see .skip-link CSS above).
SKIP_LINK = '<a class="skip-link" href="#content">Skip to content</a>'

def random_link_html(exclude_slug=None):
    """'Read a random issue' — sitewide discovery link (see .randlink CSS above).
    Same progressive-enhancement pattern as the share button and keyboard nav: the
    markup works with zero JS (a plain link to /start), and the inline script
    upgrades it in place. exclude_slug keeps an issue page from ever picking itself."""
    pool = [[it["slug"], it["title"]] for it in issues if it["slug"] != exclude_slug]
    data = json.dumps(pool, ensure_ascii=False)
    box = '<p class="randlink" id="read-random"><a href="/start">Read a random issue →</a></p>'
    script = ('<script>(function(){var issues=%s;if(!issues.length)return;'
              'var p=issues[Math.floor(Math.random()*issues.length)];'
              'var box=document.getElementById("read-random");if(!box)return;'
              'var a=box.querySelector("a");if(a){a.href="/issues/"+p[0];'
              'a.textContent="Read a random issue: “"+p[1]+"” →";}'
              '})();</script>') % data
    return box + "\n" + script

def subscribe_html():
    """Consent-forward email capture, shared across every reader-facing page."""
    endpoint = json.dumps(LEAD_ENDPOINT)
    version = json.dumps(CONSENT_VERSION)
    return '''<section id="subscribe" class="subscribe">
<strong>Get each issue.</strong>
<span>One short email when a new issue is live — no noise.</span>
<form class="subscribe-form" id="standingwave-subscribe" novalidate>
  <div class="subscribe-hp" aria-hidden="true"><label for="standingwave-website">Website</label><input id="standingwave-website" name="website" type="text" tabindex="-1" autocomplete="off"></div>
  <label class="subscribe-label" for="standingwave-email">Email address</label>
  <div class="subscribe-row"><input id="standingwave-email" name="email" type="email" maxlength="254" autocomplete="email" inputmode="email" placeholder="you@example.com" required><button type="submit">Subscribe</button></div>
  <label class="subscribe-consent"><input name="consent" type="checkbox" required><span>Email me new issues of The Standing Wave. I can unsubscribe at any time.</span></label>
  <p class="subscribe-status" role="status" aria-live="polite"></p>
</form>
<p class="subscribe-note">Prefer feeds? Follow by <a href="/feed.xml">RSS</a> or <a href="/feed.json">JSON Feed</a>.</p>
</section>
<script>(function(){var form=document.getElementById("standingwave-subscribe");if(!form)return;var status=form.querySelector(".subscribe-status"),button=form.querySelector("button[type=submit]");function say(kind,message){status.className="subscribe-status"+(kind?" "+kind:"");status.setAttribute("role",kind==="error"?"alert":"status");status.textContent=message;}form.addEventListener("submit",async function(event){event.preventDefault();if(!form.reportValidity())return;var email=form.elements.email.value.trim(),website=form.elements.website.value;button.disabled=true;button.textContent="Subscribing…";say("","");try{var response=await fetch(%s,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email:email,intent:"newsletter",site:"standingwave",interest:"updates",consent:true,consent_version:%s,page:window.location.pathname,website:website})});if(!response.ok)throw new Error("subscribe failed");form.reset();say("success","You’re on the list. The next issue will find you.");}catch(error){say("error","That did not land. Please try again in a moment.");}finally{button.disabled=false;button.textContent="Subscribe";}});})();</script>''' % (endpoint, version)

def sources_html(n):
    """'Further reading' — a small, curated public bibliography per issue, drawn from
    SOURCES above. Renders nothing if the issue has no entry (issues 1-3, and any
    future issue not yet logged) — a graceful default, same pattern as RELATED.get(n, [])."""
    srcs = SOURCES.get(n, [])
    if not srcs:
        return ""
    items = []
    for label, url in srcs:
        if url:
            items.append('<li><a href="%s">%s</a></li>' % (attr(url), inline(label)))
        else:
            items.append('<li>%s</li>' % inline(label))
    return '<nav class="sources"><h2>Further reading</h2><ul>%s</ul></nav>' % "".join(items)

WPM = 225  # reading-speed assumption for the "~N min read" estimate

def word_count(it):
    return len(it["_dek"].split()) + sum(len(p.split()) for p in it["_body"])

def read_minutes(it):
    import math
    return max(1, math.ceil(word_count(it) / WPM))

def issue_html(it):
    n = it["number"]; slug = it["slug"]
    canonical = "%s/issues/%s" % (BASE, slug)
    og_img = "%s/og/%s.png" % (BASE, slug)
    _prev = by_num.get(n - 1); _next = by_num.get(n + 1)
    prev_url = ("%s/issues/%s" % (BASE, _prev["slug"])) if _prev else None
    next_url = ("%s/issues/%s" % (BASE, _next["slug"])) if _next else None
    wc = word_count(it); mins = read_minutes(it)
    topics = TOPICS.get(n, [])
    kw = ", ".join(topics)
    ld = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": it["title"],
        "description": it["meta_description"],
        "datePublished": it["iso"],
        "dateModified": it["iso"],
        "url": canonical,
        "mainEntityOfPage": canonical,
        "image": og_img,
        "inLanguage": "en-US",
        "author": {"@type": "Person", "name": "Mark"},
        "publisher": PUBLISHER_LD,
        "isPartOf": {"@type": "Blog", "name": "The Standing Wave", "url": BASE + "/"},
        "articleSection": "Self-sustaining systems",
        "wordCount": wc,
        "timeRequired": "PT%dM" % mins,
    }
    if kw:
        ld["keywords"] = kw
    h = head(it["title"] + " — The Standing Wave", it["meta_description"], canonical,
             it["title"], it["og_description"], og_img, "article",
             it.get("twitter_description", it["og_description"]), pub=it["iso"], ld=ld,
             prev_url=prev_url, next_url=next_url, keywords=kw)
    bc = '<script type="application/ld+json">%s</script>' % json.dumps(
        breadcrumb_ld(it["title"], canonical), ensure_ascii=False, separators=(",", ":"))
    p = [h, SKIP_LINK, bc, '<article class="wrap" id="content">', TOPNAV]
    p.append('<p class="issue-meta">Issue No. %d · %s · ~%d min read</p>' % (n, it["date"], mins))
    p.append("<h1>%s</h1>" % inline(it["title"]))
    p.append('<p class="dek">%s</p>' % inline(it["_dek"]))
    for para in it["_body"]:
        p.append("<p>%s</p>" % inline(para))
    p.append('<div class="divider">≈</div>')
    p.append('<section class="watching"><h2>%s</h2>' % inline(it["_teaser_title"]))
    for para in it["_teaser"]:
        p.append("<p>%s</p>" % inline(para))
    p.append("</section>")
    prev = by_num.get(n - 1); nxt = by_num.get(n + 1)
    left = ('<a href="/issues/%s">← No. %d · %s</a>' % (prev["slug"], prev["number"], esc_text(prev["title"]))) if prev else "<span></span>"
    right = ('<a href="/issues/%s">No. %d · %s →</a>' % (nxt["slug"], nxt["number"], esc_text(nxt["title"]))) if nxt else "<span></span>"
    p.append('<div class="endnav">%s<span class="count">No. %d of %d</span>%s</div>' % (left, n, TOTAL, right))
    # Keyboard navigation (← / →) between issues — added 2026-07-07 (No. 21). Small,
    # stateless, inline script (no localStorage, matching the dark-mode precedent's
    # constraint) that reuses the prev/next URLs already computed above for rel=prev/
    # next. Ignores the keypress if a modifier key is held or focus is in an editable
    # field (neither exists on this page today, but the guard costs nothing and keeps
    # the handler safe if that ever changes). A visible hint makes the shortcut
    # discoverable instead of a silent Easter egg; the hint is dropped from print
    # output as pure navigational chrome, same treatment as the top nav.
    p.append('<p class="kbdhint">Tip: the ← and → arrow keys move between issues.</p>')
    p.append('<script>(function(){var P=%s,N=%s;document.addEventListener("keydown",function(e){'
              'if(e.defaultPrevented||e.altKey||e.ctrlKey||e.metaKey||e.shiftKey)return;'
              'var t=e.target,g=t&&t.tagName;if(g==="INPUT"||g==="TEXTAREA"||(t&&t.isContentEditable))return;'
              'if(e.key==="ArrowLeft"&&P){location.href=P}else if(e.key==="ArrowRight"&&N){location.href=N}'
              '});})();</script>' % (json.dumps(prev_url), json.dumps(next_url)))
    # "Share this issue" — added 2026-07-08 (No. 22). The default markup (no JS
    # required) is the plain, selectable canonical URL, a real fallback that already
    # works via copy-paste. The script replaces it with a button that calls the
    # native Web Share sheet where supported, or copies the link to the clipboard
    # with a short text confirmation otherwise — same progressive-enhancement
    # pattern as the 404 page's random-issue link.
    p.append('<p class="share" id="share-box">Share this issue: <code>%s</code></p>' % esc_text(canonical))
    p.append('<script>(function(){var url=%s,title=%s;var box=document.getElementById("share-box");'
              'if(!box)return;var btn=document.createElement("button");btn.type="button";'
              'btn.className="share-btn";btn.textContent="Share this issue";'
              'btn.addEventListener("click",function(){'
              'if(navigator.share){navigator.share({title:title,url:url}).catch(function(){});}'
              'else if(navigator.clipboard&&navigator.clipboard.writeText){'
              'navigator.clipboard.writeText(url).then(function(){'
              'btn.textContent="Link copied!";setTimeout(function(){btn.textContent="Share this issue";},2000);'
              '}).catch(function(){});}'
              '});box.textContent="";box.appendChild(btn);'
              '})();</script>' % (json.dumps(canonical), json.dumps(it["title"] + " — The Standing Wave")))
    p.append(subscribe_html())
    if n != 1:
        p.append('<p class="starthere">New to The Standing Wave? <a href="/start">Start here →</a></p>')
    # Related issues — curated thematic cross-links (internal-linking growth feature).
    rel = [(by_num[t], why) for (t, why) in RELATED.get(n, []) if t in by_num and t != n]
    if rel:
        p.append('<nav class="related"><h2>Related issues</h2><ul>')
        for rit, why in rel:
            p.append('<li><a href="/issues/%s">No. %d · %s</a><span class="why">%s</span></li>'
                     % (rit["slug"], rit["number"], inline(rit["title"]), inline(why)))
        p.append("</ul></nav>")
    p.append(sources_html(n))
    p.append(random_link_html(exclude_slug=slug))
    p.append('<footer>The Standing Wave · <a href="/">standingwave.ink</a><br>'
             'Issue No. %d · written %s</footer>' % (n, it["date"]))
    p.append("</article></body></html>")
    return "\n".join(p)

def index_html():
    canonical = BASE + "/"
    site_desc = "A publication about self-sustaining systems — the loops, cycles, and standing patterns that hold their shape while everything inside them flows through."
    ld = {
        "@context": "https://schema.org",
        "@type": "Blog",
        "name": "The Standing Wave",
        "alternateName": "Field notes on things that run themselves",
        "description": site_desc,
        "url": BASE + "/",
        "inLanguage": "en-US",
        "author": {"@type": "Person", "name": "Mark"},
        "publisher": PUBLISHER_LD,
        "blogPost": [
            {"@type": "BlogPosting", "headline": it["title"],
             "url": "%s/issues/%s" % (BASE, it["slug"]), "datePublished": it["iso"]}
            for it in reversed(issues)
        ],
    }
    h = head("The Standing Wave — field notes on things that run themselves",
             site_desc,
             canonical, "The Standing Wave", "Field notes on things that run themselves.",
             "%s/og/standingwave.png" % BASE, "website", "Field notes on things that run themselves.", ld=ld)
    p = [h, SKIP_LINK, '<main class="wrap" id="content">', TOPNAV]
    p.append('<h1 class="site"><a href="/">The Standing Wave</a></h1>')
    p.append('<p class="intro">A small publication about self-sustaining systems. Some things last because they’re solid. Others last because they found a loop that pays for its own upkeep — a flame, a sourdough starter, a language, a sealed jar on a shelf. This is a publication about those: the patterns that hold their shape while everything inside them flows through and leaves. One issue, one system, explained as clearly and as beautifully as I can manage.</p>')
    p.append('<p class="starthere">New here? <a href="/start">Start here →</a></p>')
    p.append('<ul class="issue-list">')
    for it in reversed(issues):
        p.append("<li>")
        p.append('<p class="issue-meta">No. %d · %s</p>' % (it["number"], it["date"]))
        p.append('<h2><a href="/issues/%s">%s</a></h2>' % (it["slug"], inline(it["title"])))
        p.append('<p class="blurb">%s</p>' % inline(it["blurb"]))
        p.append("</li>")
    p.append("</ul>")
    p.append(subscribe_html())
    p.append(random_link_html())
    p.append('<footer>The Standing Wave · written at <a href="/">standingwave.ink</a> · '
             '<a href="https://musenexus.studio/ecosystem">Muse Nexus ecosystem</a><br>'
             'A pattern that shows up when there’s something to burn.</footer>')
    p.append("</main></body></html>")
    return "\n".join(p)

def start_html():
    canonical = BASE + "/start"
    desc = "New to The Standing Wave? Start here — what the series is about, and three issues to read first."
    h = head("Start here — The Standing Wave", desc, canonical,
             "Start here — The Standing Wave",
             "What the series is about, and three issues to read first.",
             "%s/og/standingwave.png" % BASE, "website",
             "What the series is about, and three issues to read first.")
    bc = '<script type="application/ld+json">%s</script>' % json.dumps(
        breadcrumb_ld("Start here", canonical), ensure_ascii=False, separators=(",", ":"))
    p = [h, SKIP_LINK, bc, '<main class="wrap" id="content">', TOPNAV]
    p.append("<h1>Start here</h1>")
    p.append('<p class="dek">The Standing Wave is a publication about self-sustaining systems — the loops, cycles, and standing patterns that hold their shape while everything inside them flows through and leaves. One issue, one system, explained as clearly and as beautifully as I can manage.</p>')
    p.append('<p class="intro">The newest issue sits on the <a href="/">home page</a>, but the latest one isn’t the best way in — whichever of these three pulls you is. Read one; the rest of the series rhymes with it.</p>')
    p.append('<ul class="issue-list">')
    for num, why in START_PICKS:
        it = by_num.get(num)
        if not it:
            continue
        p.append("<li>")
        p.append('<p class="issue-meta">No. %d · %s</p>' % (it["number"], it["date"]))
        p.append('<h2><a href="/issues/%s">%s</a></h2>' % (it["slug"], inline(it["title"])))
        p.append('<p class="blurb">%s</p>' % inline(why))
        p.append("</li>")
    p.append("</ul>")
    p.append('<p class="starthere">Or just begin at the beginning — <a href="/issues/%s">Issue No. 1 →</a> — and read forward. Every issue ends by naming the next.</p>' % issues[0]["slug"])
    p.append(subscribe_html())
    p.append(random_link_html())
    p.append('<footer>The Standing Wave · <a href="/">standingwave.ink</a><br>'
             'A pattern that shows up when there’s something to burn.</footer>')
    p.append("</main></body></html>")
    return "\n".join(p)

def about_html():
    # Added 2026-07-09 (No. 25) — a colophon/"why trust this" page. Distinct from
    # /start (a content on-ramp picking three issues to read first): this page is
    # about editorial standards and process, not which issue to read. Deliberately
    # keeps the existing byline convention (Mark) unchanged rather than making a new
    # authorship-disclosure decision unilaterally — that's a bigger brand call than a
    # nightly content run should make on its own. Everything stated here is already
    # true of the shipped site (the ~600-900-word standard, the "Further reading"
    # bibliography shipped in No. 24, no ads/tracking/paywall — verified via grep of
    # build.py before writing this page) rather than new promises.
    canonical = BASE + "/about"
    desc = "What The Standing Wave is, and how each issue gets researched, checked, and published."
    h = head("About — The Standing Wave", desc, canonical,
             "About — The Standing Wave",
             "What this is, and how it gets made.",
             "%s/og/standingwave.png" % BASE, "website",
             "What this is, and how it gets made.")
    bc = '<script type="application/ld+json">%s</script>' % json.dumps(
        breadcrumb_ld("About", canonical), ensure_ascii=False, separators=(",", ":"))
    p = [h, SKIP_LINK, bc, '<main class="wrap" id="content">', TOPNAV]
    p.append("<h1>About</h1>")
    p.append('<p class="dek">What this is, and how it gets made.</p>')
    p.append('<p class="intro">The Standing Wave is a publication about self-sustaining systems — the loops, cycles, and standing patterns that hold their shape while everything inside them flows through and leaves. One issue, one system: a flame, a heartbeat, a stalactite, a DRAM chip\'s memory. Usually 600 to 900 words, written to be readable in one sitting and to still hold up years later.</p>')
    p.append("<p>Every issue is researched before it's written, not after. Facts get checked against current, credible sources — peer-reviewed papers where they exist, primary sources and major institutions where they don't — and where the evidence is genuinely unsettled (a physics dispute, a contested historical detail, a figure that varies by an order of magnitude depending on who measured it), the piece says so plainly instead of picking the tidier-sounding number. Most issues carry a short “Further reading” list at the bottom linking a few of the actual sources used to write them, drawn from the real research notes kept for each piece rather than added for show.</p>")
    p.append("<p>New issues run three to four times a week, evergreen rather than tied to the news. There's no paywall, no ads, and nothing on this site tracks you. Read it here, receive each issue by email, or follow by RSS or JSON Feed and get the same words with nothing added.</p>")
    p.append("<p>Byline: Mark.</p>")
    p.append('<p class="starthere">New here? <a href="/start">Start here →</a></p>')
    p.append(subscribe_html())
    p.append(random_link_html())
    p.append('<footer>The Standing Wave · <a href="/">standingwave.ink</a><br>'
             'A pattern that shows up when there’s something to burn.</footer>')
    p.append("</main></body></html>")
    return "\n".join(p)

def not_found_html():
    # Custom 404 — Cloudflare Pages automatically serves a top-level site/404.html
    # for any unmatched route (walking up the directory tree for the closest match;
    # confirmed against Cloudflare's own Pages docs). On-brand paper styling, noindex
    # (an error page shouldn't rank), links back to the two real on-ramps (home,
    # /start), and a client-side "read a random issue" pick — a small bit of delight
    # for what would otherwise be a dead end, and a discovery path distinct from the
    # reverse-chron home page or the curated /start picks.
    rand_data = json.dumps([[it["slug"], it["title"]] for it in issues], ensure_ascii=False)
    script = ("<script>(function(){var issues=%s;"
              "var p=issues[Math.floor(Math.random()*issues.length)];"
              "var a=document.getElementById('rand-issue');"
              "if(a&&p){a.href='/issues/'+p[0];"
              "a.textContent='Read a random issue: “'+p[1]+'” →';}"
              "})();</script>") % rand_data
    t = ["<!doctype html>", '<html lang="en"><head>',
         '<meta charset="utf-8">',
         '<meta name="viewport" content="width=device-width, initial-scale=1">',
         "<title>Page not found — The Standing Wave</title>",
         '<meta name="robots" content="noindex">',
         '<link rel="stylesheet" href="/style.css">',
         '<link rel="icon" type="image/svg+xml" href="/favicon.svg">',
         '<link rel="icon" type="image/png" sizes="48x48" href="/favicon.png">',
         '<link rel="apple-touch-icon" href="/apple-touch-icon.png">',
         '<link rel="manifest" href="/site.webmanifest">',
         '<meta name="theme-color" media="(prefers-color-scheme: light)" content="#faf6ef">',
         '<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#1c1a17">',
         "</head><body>"]
    t.append(SKIP_LINK)
    t.append('<main class="wrap" id="content">')
    t.append(TOPNAV)
    t.append("<h1>This one didn’t hold its shape.</h1>")
    t.append('<p class="dek">Every standing wave in this publication needs something '
             'pushing on it, continuously, or it collapses back into whatever it was '
             'made of. Whatever used to be at this address didn’t have that going '
             'for it. It’s gone — not moved, not renamed, just gone.</p>')
    t.append('<p class="intro">Here’s what’s still standing:</p>')
    t.append('<p><a href="/">The home page →</a></p>')
    t.append('<p><a href="/start">Start here →</a> — three issues to read first</p>')
    t.append('<p><a id="rand-issue" href="/">Read a random issue →</a></p>')
    t.append(script)
    t.append('<footer>The Standing Wave · <a href="/">standingwave.ink</a><br>'
              'A pattern that shows up when there’s something to burn.</footer>')
    t.append("</main></body></html>")
    return "\n".join(t)

def rfc822(iso):
    dt = datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")

def feed_xml():
    items = []
    for it in reversed(issues):
        link = "%s/issues/%s" % (BASE, it["slug"])
        desc = smarten(it["blurb"])
        items.append("""    <item>
      <title>%s</title>
      <link>%s</link>
      <guid isPermaLink="true">%s</guid>
      <pubDate>%s</pubDate>
      <description>%s</description>
    </item>""" % (html.escape("No. %d · %s" % (it["number"], it["title"])), link, link,
                  rfc822(it["iso"]), html.escape(desc)))
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>The Standing Wave</title>
    <link>%s/</link>
    <atom:link href="%s/feed.xml" rel="self" type="application/rss+xml"/>
    <description>Field notes on things that run themselves.</description>
    <language>en-us</language>
    <lastBuildDate>%s</lastBuildDate>
%s
  </channel>
</rss>
""" % (BASE, BASE, rfc822(issues[-1]["iso"]), "\n".join(items))

def json_feed():
    # JSON Feed 1.1 (jsonfeed.org) — a second, modern subscribe surface alongside RSS.
    items = []
    for it in reversed(issues):
        link = "%s/issues/%s" % (BASE, it["slug"])
        items.append({
            "id": link,
            "url": link,
            "title": "No. %d · %s" % (it["number"], it["title"]),
            "summary": it["blurb"],
            "content_text": it["blurb"],
            "date_published": it["iso"],
            "image": "%s/og/%s.png" % (BASE, it["slug"]),
            "authors": [{"name": "Mark"}],
        })
    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "The Standing Wave",
        "home_page_url": BASE + "/",
        "feed_url": BASE + "/feed.json",
        "description": "Field notes on things that run themselves.",
        "language": "en-US",
        "authors": [{"name": "Mark"}],
        "items": items,
    }
    return json.dumps(feed, ensure_ascii=False, indent=2)

def llms_txt():
    # llms.txt (llmstxt.org convention) — a concise, agent-facing map of the site,
    # the same idea as robots.txt/sitemap.xml but written for LLMs reading it into
    # a context window rather than for a search-index crawler. On-brand for a
    # publication written and operated by an agent: the whole point of the growth
    # streak so far (JSON-LD, JSON Feed, sitemap lastmod, rel=prev/next) has been
    # legibility to machines as well as people, and this is the next natural rung.
    lines = ["# The Standing Wave", ""]
    lines.append("> A publication about self-sustaining systems — the loops, cycles, and "
                  "standing patterns that hold their shape while everything inside them "
                  "flows through and leaves. One issue, one system: a flame, a heartbeat, "
                  "a coral reef, a spiral galaxy's arms. ~600-900 words per issue, written "
                  "by Mark, sources verified and cited, no paywall.")
    lines.append("")
    lines.append("## Start here")
    lines.append("")
    lines.append("- [Start here](%s/start): the premise, plus three issues to read first." % BASE)
    lines.append("- [About](%s/about): editorial standards and how issues get researched and sourced." % BASE)
    lines.append("- [All issues](%s/): the full archive, newest first." % BASE)
    lines.append("")
    lines.append("## Issues (oldest to newest)")
    lines.append("")
    for it in issues:
        one_line = ONE_LINERS.get(it["number"], it["blurb"])
        lines.append("- [No. %d · %s](%s/issues/%s): %s"
                      % (it["number"], it["title"], BASE, it["slug"], one_line))
    lines.append("")
    lines.append("## Feeds")
    lines.append("")
    lines.append("- [RSS](%s/feed.xml)" % BASE)
    lines.append("- [JSON Feed](%s/feed.json)" % BASE)
    return "\n".join(lines) + "\n"

# ---------- write text outputs ----------
open(os.path.join(SITE, "style.css"), "w", encoding="utf-8").write(CSS)
open(os.path.join(SITE, "index.html"), "w", encoding="utf-8").write(index_html())
open(os.path.join(SITE, "start.html"), "w", encoding="utf-8").write(start_html())
open(os.path.join(SITE, "about.html"), "w", encoding="utf-8").write(about_html())
open(os.path.join(SITE, "404.html"), "w", encoding="utf-8").write(not_found_html())
for it in issues:
    open(os.path.join(SITE_ISSUES, it["slug"] + ".html"), "w", encoding="utf-8").write(issue_html(it))
open(os.path.join(SITE, "feed.xml"), "w", encoding="utf-8").write(feed_xml())
open(os.path.join(SITE, "feed.json"), "w", encoding="utf-8").write(json_feed())
open(os.path.join(SITE, "llms.txt"), "w", encoding="utf-8").write(llms_txt())
open(os.path.join(SITE, "robots.txt"), "w", encoding="utf-8").write(
    "User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n" % BASE)
# Favicon (SVG) — the brand mark (paper square, accent border, the "≈" divider glyph),
# scalable and dependency-free so it always ships even if PIL/fonts are unavailable.
FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="14" fill="#faf6ef"/>
<rect x="3" y="3" width="58" height="58" rx="11" fill="none" stroke="#9a3b26" stroke-width="3"/>
<text x="32" y="44" font-family="Georgia, 'Iowan Old Style', serif" font-size="34" font-weight="700" fill="#9a3b26" text-anchor="middle">≈</text>
</svg>"""
open(os.path.join(SITE, "favicon.svg"), "w", encoding="utf-8").write(FAVICON_SVG)
# Web app manifest (Android/desktop "install"/"add to home screen"). Static JSON,
# zero new dependencies; icons generated below alongside the favicon PNGs.
MANIFEST = {
    "name": "The Standing Wave",
    "short_name": "Standing Wave",
    "description": "Field notes on things that run themselves.",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "background_color": "#faf6ef",
    "theme_color": "#faf6ef",
    "icons": [
        {"src": "/favicon.png", "sizes": "48x48", "type": "image/png"},
        {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
    ],
}
open(os.path.join(SITE, "site.webmanifest"), "w", encoding="utf-8").write(
    json.dumps(MANIFEST, ensure_ascii=False, indent=2))
# sitemap (with <lastmod> from each issue's iso date; homepage = newest issue)
newest = max(it["iso"][:10] for it in issues)
entries = [("%s/" % BASE, newest), ("%s/start" % BASE, newest), ("%s/about" % BASE, newest)] + [("%s/issues/%s" % (BASE, it["slug"]), it["iso"][:10]) for it in issues]
sm = ['<?xml version="1.0" encoding="UTF-8"?>',
      '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for loc, lastmod in entries:
    sm.append("  <url><loc>%s</loc><lastmod>%s</lastmod></url>" % (loc, lastmod))
sm.append("</urlset>")
open(os.path.join(SITE, "sitemap.xml"), "w", encoding="utf-8").write("\n".join(sm))

print("text outputs written:", TOTAL, "issues + index + start + feed(xml+json) + sitemap + robots")

if os.environ.get("STANDING_WAVE_TEXT_ONLY") == "1":
    print("binary art preserved (STANDING_WAVE_TEXT_ONLY=1)")
    print("DONE -> site/")
    sys.exit(0)

# ---------- OG images ----------
def find_font(names):
    roots = ["/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.fonts")]
    for r in roots:
        for dp, _, fs in os.walk(r):
            for f in fs:
                if f in names:
                    return os.path.join(dp, f)
    return None

try:
    from PIL import Image, ImageDraw, ImageFont
    PAPER=(250,246,239); INK=(35,32,27); ACCENT=(154,59,38); MUTED=(111,104,92)
    serif = find_font(["DejaVuSerif.ttf","DejaVuSerif-Bold.ttf"]) or find_font(["LiberationSerif-Regular.ttf"])
    serif_bold = find_font(["DejaVuSerif-Bold.ttf"]) or serif
    sans = find_font(["DejaVuSans.ttf"]) or serif
    def F(path,size):
        try: return ImageFont.truetype(path,size) if path else ImageFont.load_default()
        except Exception: return ImageFont.load_default()
    def wrap(draw,text,font,maxw):
        words=text.split(); lines=[]; cur=""
        for w in words:
            t=(cur+" "+w).strip()
            if draw.textlength(t,font=font)<=maxw: cur=t
            else:
                if cur: lines.append(cur)
                cur=w
        if cur: lines.append(cur)
        return lines
    def card(path,kicker,title,foot):
        W,H=1200,630
        img=Image.new("RGB",(W,H),PAPER); d=ImageDraw.Draw(img)
        d.rectangle([28,28,W-28,H-28],outline=ACCENT,width=3)
        fk=F(sans,30); ft=F(serif_bold or serif,76); ff=F(sans,28)
        d.text((70,78),kicker.upper(),font=fk,fill=ACCENT)
        lines=wrap(d,title,ft,W-160)
        # vertical center block
        lh=92; total=lh*len(lines); y=(H-total)//2-10
        for ln in lines:
            d.text((70,y),ln,font=ft,fill=INK); y+=lh
        d.text((70,H-86),foot,font=ff,fill=MUTED)
        img.save(path,"PNG")
    for it in issues:
        card(os.path.join(OG, it["slug"]+".png"),
             "The Standing Wave · No. %d" % it["number"],
             it["title"], "standingwave.ink")
    card(os.path.join(OG,"standingwave.png"),"The Standing Wave",
         "Field notes on things that run themselves","standingwave.ink")
    print("OG images written:", TOTAL+1, "(font:", os.path.basename(serif or "default"),")")

    # Favicon PNG fallbacks (browsers/iOS "add to home screen" that don't take SVG icons).
    def icon(path, size, radius):
        img = Image.new("RGB", (size, size), PAPER)
        d = ImageDraw.Draw(img)
        b = max(2, size // 20)
        d.rounded_rectangle([b, b, size - b, size - b], radius=radius, outline=ACCENT, width=max(2, size // 22))
        glyph_font = F(serif_bold or serif, int(size * 0.5))
        tb = d.textbbox((0, 0), "≈", font=glyph_font)
        gw, gh = tb[2] - tb[0], tb[3] - tb[1]
        d.text(((size - gw) / 2 - tb[0], (size - gh) / 2 - tb[1]), "≈", font=glyph_font, fill=ACCENT)
        img.save(path, "PNG")
    icon(os.path.join(SITE, "favicon.png"), 48, 10)
    icon(os.path.join(SITE, "apple-touch-icon.png"), 180, 38)
    icon(os.path.join(SITE, "icon-192.png"), 192, 40)
    icon(os.path.join(SITE, "icon-512.png"), 512, 108)
    print("Favicon/manifest PNGs written: favicon.png (48x48), apple-touch-icon.png (180x180), icon-192.png, icon-512.png")
except Exception as e:
    print("OG image generation skipped:", repr(e))

print("DONE -> site/")
