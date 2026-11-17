# Animations: how it goes together, the pour, how it comes apart

`scripts/moldanim.py` turns the checked mold into one GLB with three clips, and proves that no piece passes through another in any of them. `scripts/animpreview.js` renders the clips to MP4s and contact sheets in the same viewer the site uses.

| Clip | What it shows |
|---|---|
| `build` | Every piece arrives in shop order, then the pour |
| `pour` | The outside opens as a cutaway, the concrete rises in lifts with a pause between them, then the mold closes |
| `demold` | Hardware off, cap and funnel off, outside bands off along their pulls, the pot off the base, then every core piece out on a planned path. The cast stays |

## Run it
```
python3 scripts/moldanim.py MOLD_DIR --cast vessel.stl --spec piece.anim.json \
    --out piece-mold.glb --report piece.anim-report.json
node scripts/animpreview.js piece-mold.glb previews/ --mv model-viewer-4.1.0.min.js --orbit "30deg 66deg auto"
```
- `MOLD_DIR` is the folder (or GLB) moldcheck reads, with the pulls in the part names.
- `--cast` is the cast part. `moldcheck.py --cast-stl` writes it.
- The exit code is 0 only when every clip passes and every core piece found a way out.
- Needs `trimesh manifold3d numpy scipy fast_simplification`. For the previews you also need Node with `playwright`, `ffmpeg`, and a local copy of model-viewer.
- To shrink the file for the web, run `npx @gltf-transform/cli meshopt in.glb out.glb` (model-viewer decodes meshopt). For K this took the file from 17 MB to 2.9 MB.
- Render the previews from the uncompressed GLB. model-viewer fetches its meshopt decoder from a CDN, and headless Chromium may not reach it.

## How the paths are made
- **Pull moves.** Outside pieces, the cap, the funnel, the base and the hardware move straight along the pull in their names (`_pull_137_deg`, `_pull_up`). They travel `dist` mm and then shrink away.
- **Straight out first.** In a `plan` stage, a piece that can slide straight along its pull until it clears everything left does just that.
- **Planned moves.** `move: "plan"` is for core pieces that can't leave along their pull alone.
  1. The piece slides along its pull as far as it stays clear, up to `unlock` mm. That's the real first move: the key pulls in and the side pieces let go.
     - If the named pull doesn't free it, the planner tries the straight move closest to that pull that does, and warns.
     - The name is then wrong, or the piece is locked. Look at it in CAD.
  2. The planner rasterizes everything still in place (the cast and the pieces not yet out) on a coarse grid (`--plan-res`, default 8 mm). It convolves the piece over that grid to get every position where the piece would hit something, then runs a wave search from the start to any position clear of everything.
  3. The path is shortened against the fine check, so the piece moves in a few straight legs and not a staircase.
- **Order.** The order is chosen, not assumed. Pieces are tried in the order `first` gives (for example keys first, then neck, shoulder, belly). The first one that has a way out goes, and the rest are tried again. If no piece can leave, the stage reports `no way out` with the pieces left. That's a real demold problem. Fix the mold, not the animation.
- **Build.** The build clip reuses the demold paths backwards for the core (`move: "reverse"`). The core goes in along the same paths it comes out on. Everything else comes in along its pull from `dist` away.

## How it's checked
- Every part gets a signed distance field on its own grid, at 1.25 mm or coarser for very large parts. Every part also gets surface sample points.
- The whole timeline is sampled so that no piece moves more than 2 mm between samples. At each sample, every moving piece is tested both ways against every piece showing at that moment, and against the cast once it is full.
- **Contact at rest is allowed.** For example, the core skins touch the ledges. The limit for each pair is its depth at rest plus `--tol` (default 1 mm).
- The report lists:
  - for every collision: the clip, the time, the moving piece, what it hit and how deep
  - the demold order
  - every path in mm
- A clip with collisions isn't finished. Change the order, `dist`, `unlock` or `overlap`, or fix the mold. Run it again until all three clips report 0.

## The spec (`<piece>.anim.json`)
```
{"name": "k_mold", "units": "mm", "up": "z", "speed": 340,
 "parts":  {"^HD1": {"role": "hardware", "material": "wood"}, "^K": {"role": "core"}, ...},
 "demold": [{"label": "bridge off", "parts": "^HD1", "move": "pull", "dist": 320},
            {"label": "neck band", "parts": "^D\\d", "move": "pull", "dist": 280}, ...,
            {"label": "core out", "parts": "^K", "move": "plan", "first": ["key", "Neck"],
             "unlock": 48, "speed": 650, "overlap": 0.35}],
 "build":  [{"label": "base plate", "parts": "^BASE$", "move": "pull", "dist": 260},
            {"label": "core", "parts": "^K", "move": "reverse", "speed": 650, "overlap": 0.35}, ...,
            {"label": "pour", "move": "pour"}],
 "pour":   {"explode": "^[A-C]\\d", "dist": 240, "lifts": [0.5, 1.0], "pause": 1.6, "rise_mm_s": 170}}
```
- `move`:
  - `pull`: along the part's pull
  - `vector`: along a direction you give
  - `drop`: in from above (build only)
  - `plan`: planned (demold only)
  - `reverse`: demold paths backwards (build only)
  - `pour`
- `avoid` (on a `plan` stage) lists pieces that are already off in the demold but that the paths must still miss, because they're in place when the core goes in during the build. For K, that's the base and the bench board.
- `stagger` is the delay between pieces in a stage.
- `overlap` lets the next planned piece start before the last one is out. The check still covers it.
- With no spec, the defaults are: hardware, funnel and cap off; bands top down; base; core planned with keys first. Build is the reverse, then the pour.
- **Materials** keep the site's names: `shell` (white), `core` (red), `base`, `wood`, `steel`, `gfrc` (black).

## What the GLB looks like (for the web viewer)
- The root node is named after the piece, at scale 0.001, so millimetres become metres. The GLB is Y up.
- There is one node per part, named by its code (`A1`, `KD2`, `HD1`), with a `_mesh` child. The node sits at the part's centre, so the shrink-away happens in place.
- The cast is cut into horizontal slices (`CAST00`, and so on). Each slice is pivoted at its bottom and scaled in Y to show the fill level.
- Every clip animates every node, so switching clips never leaves a piece where the last clip left it.
- Meshes are decimated copies (`--faces`, 7,000 per part by default). The check always uses the full-resolution STLs.

## Brand
- Previews are on white, using model-viewer's neutral environment, a soft shadow and exposure 1.05, the same as the site.
- Motion is eased in and out, with no bounce.
- No text is burned into the frames. Labels belong on the page, in the brand type.

## Tests
`python3 scripts/tests/run_anim_tests.py` runs moldanim on the cup fixtures. It checks three things:
- The good cup animates with 0 collisions and the core comes out.
- The undercut core has no way out.
- A build that brings the base down through the sides is caught.

## What it found on K (2026-11-17)
On the first run, 12 of the 22 core pieces had no way out. The cause was the window skins added that morning. Each skin had been split between the core pieces along rays in the window plane, so every piece's share was a wedge, about 3 mm deep, that no pull could free. moldcheck can't see this, because it only checks the pieces against the concrete, not against each other.

The fix was to split the skins on the core's own seam planes, carried straight on to the flat wall. `fixes/apply_fixes.py` fits those planes to within 0.03 mm. After that, every core piece comes out, keys first. Lesson: **when you add material to pieces that come apart, split it on their seam planes, never radially, and run moldanim to prove it.**
