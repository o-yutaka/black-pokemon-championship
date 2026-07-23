# BLACK Battle Studio Site

Responsive, dependency-free public website for BLACK Battle Studio.

## Local preview

```bash
python3 -m http.server 8080 --directory site
```

Open `http://localhost:8080`.

## Deployment

The included GitHub Pages workflow publishes the `site/` directory. In repository settings, set **Pages → Source → GitHub Actions** once, then merge this branch or run the workflow manually.

## Boundaries

- Static HTML/CSS/Canvas JavaScript only
- No dependency added to the competition runtime
- No changes to `submission/`, `deck.csv`, policy code, or official engine files
- Repository and Draft PR #14 links are embedded
- Responsive down to narrow iPhone widths
