# Real Pokémon Card Artwork

Battle Studio resolves artwork only for card IDs visible in the current frame.

Resolution order:

1. Direct image URL in `card_id_list.csv` `link`
2. Pokémon TCG API card ID embedded in `link`
3. Exact `card_name + collection_no` API query

A fuzzy name-only match is never displayed. Ambiguous or missing matches keep the BLACK fallback card instead of showing artwork from a different printing.

Images are not committed to this repository. Browser HTTP cache and `localStorage["black.real-card-art.v1"]` retain resolved URLs. An optional `POKEMON_TCG_API_KEY` is only needed for higher API limits.
