# BLACK Battle Studio Site

Dependency-free public website for BLACK Battle Studio.

## Local preview

```bash
python3 -m http.server 8080 --directory site
```

Open `http://localhost:8080`.

## Card Library

The public site can load multiple files at once and merge rows by card ID.

Supported inputs:

- CSV / TSV
- JSON array
- JSON object containing `cards`, `data`, `rows`, `items`, or `records`
- Object maps keyed by card ID

Typical files can be selected together:

- `EN_Card_Data.csv`
- `card_id_list.csv`
- `deck.csv`

Recognized aliases include:

- ID: `id`, `card_id`, `card_number`, `number`, `index`
- Name: `name`, `card_name`, `english_name`, `japanese_name`
- Category: `category`, `card_type`, `supertype`, `type`
- HP: `hp`, `hit_points`, `health`
- Quantity: `quantity`, `qty`, `count`, `copies`

Files are parsed only in browser memory and are not uploaded. The merged normalized view can be exported as JSON.

## Deployment

The included GitHub Pages workflow publishes `site/`. Set **Repository Settings → Pages → Source → GitHub Actions** once.

## Boundaries

- Static HTML/CSS/Canvas JavaScript only
- Zero competition-runtime dependencies
- No changes to `submission/`, root `deck.csv`, policy code, or official engine files
- Responsive down to narrow iPhone widths
