# The Standing Wave

The current production source for [standingwave.ink](https://standingwave.ink)
lives in [`production/`](production/):

- `production/issues/` contains the 27 published issue sources.
- `production/build.py` renders the complete static site.
- `production/site/` is the full Cloudflare Pages direct-upload artifact.

Deploy the complete artifact with:

```sh
bash deploy-production.sh
```

Cloudflare credentials must be supplied through `CLOUDFLARE_API_TOKEN` and
`CLOUDFLARE_ACCOUNT_ID`; they do not belong in this repository.

Before publishing, `production/check_release.py` verifies the homepage social
metadata and the byte identity and dimensions of the established Open Graph
art. Do not run the generator merely to refresh metadata: its image renderer can
produce different PNG bytes on another machine. When editorial work requires a
rebuild, inspect any `production/site/og/` diff and commit artwork changes only
when they are intentional.

For text or interface-only changes, preserve the committed art while rebuilding
all HTML and feeds:

```sh
STANDING_WAVE_TEXT_ONLY=1 python3 production/build.py
python3 production/check_release.py
```

The static files at the repository root are the original two-issue Vercel
snapshot retained for history. They are not the source or deploy artifact for
the current publication.
