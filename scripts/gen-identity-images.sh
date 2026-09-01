#!/bin/bash
# Generate Zemest identity images — two-tone halftone/bitmap, indigo twilight + cream.
# Usage: bash /home/z/my-project/scripts/gen-identity-images.sh
set -u
OUT=/home/z/my-project/identity-raw
mkdir -p "$OUT"

STYLE="two-tone halftone bitmap illustration, dark indigo night palette, cream and warm ivory halftone dot grain, premium risograph screen-print texture, bold clean high-contrast shapes, minimal composition, crescent moon motif, no text, no letters, no words"

z-ai image -p "friendly AI shop agent character, a glowing abstract assistant silhouette with headset standing behind a small shop counter with sneaker and perfume bottle on it, $STYLE" -o "$OUT/hero-agent.png" -s 1152x864
z-ai image -p "hand holding a smartphone with rounded chat bubbles floating upward out of the screen, $STYLE" -o "$OUT/usecase-whatsapp.png" -s 1152x864
z-ai image -p "smartphone floating in center with a big heart and a folded paper plane message flying away in a curved trail, $STYLE" -o "$OUT/usecase-instagram.png" -s 1152x864
z-ai image -p "open laptop with a large chat window on screen and three speech bubbles rising above the keyboard, $STYLE" -o "$OUT/usecase-messenger.png" -s 1152x864
z-ai image -p "warehouse shelves stacked with boxes and one sneaker on a pedestal, a glowing magnifying glass hovering and scanning the shelf, $STYLE" -o "$OUT/usecase-inventory.png" -s 1152x864
z-ai image -p "elegant sitting rabbit silhouette with long ears, surrounded by flowing calligraphic swirls and small stars, $STYLE" -o "$OUT/usecase-rabbit.png" -s 1152x864
z-ai image -p "wide panoramic soft cloud bank drifting over gentle hills at dusk, warm sepia brown and caramel palette, cream halftone dots on deep espresso brown background, premium risograph screen-print, bold high-contrast shapes, no text" -o "$OUT/footer-cloud.png" -s 1440x720

ls -la "$OUT"
