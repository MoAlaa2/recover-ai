# ReCover — judge-style test of the live deploy (2 Nov 2026)

Target: https://moalaa2--recover-ai-web.us-east.modal.run (Basic Auth), commit `4cbcb8a` at test time.
Method: three independent testers drove the site cold as first-time judges (desktop 1440x900 in Chromium and WebKit; iPhone 15 Pro WebKit in EN/AR/FR/HI; API abuse with 164 requests), plus a designer-page run and header checks. Every number below was measured, every quote is verbatim. Fixes shipped afterwards are in the last section (commit `1bec7c8`).

## Verdict

Technically the strongest thing in the room: a real tool-using agent, grounded recommendations that refuse invented codes, SAM isolation plus an image edit plus a Spark check that retries, five live languages, an honest quote with a sourced CO₂ figure and a working WhatsApp and PDF handoff. The renders of the sofa and the armchair are the best moment of the product and judges will notice.

What a judge would hold against it, in order: the wait (41 to 52 s per render, 60 s before the first word on a HEIC photo), the consultant padding with questions and sometimes ignoring the stated budget, and a handful of unfinished states that make it feel one week short.

| Dimension | Desktop | Phone | API | Combined |
|---|---|---|---|---|
| First impression | 7 | 6 | – | 7 |
| Speed | 6 | 4 | – | 5 |
| AI quality (recommendations) | 5 | 5 | 8 (honesty under pressure) | 5 |
| Swap realism | 8 | 7 | – | 8 |
| Honesty | 6 | 5 | 8 | 6 |
| Polish | 6 | 4 | 5 (robustness) | 5 |
| Security hygiene | – | – | 7 | 7 |

## Measured timings

| Step | Desktop Chromium | Phone WebKit |
|---|---|---|
| Landing load | 2.4 s (TTFB 1.0 s) | 3.8 s |
| Consult page load | 1.6 s | 7.6 to 9.3 s |
| Sample photo to first consultant comment | 11.8 s | 11.1 s |
| Real iPhone HEIC to first comment | – | 60.2 s (client timeout, silent retry) |
| Chat turn | 2.5 to 4.5 s | 3.0 to 6.2 s |
| Photo to 3 cards | 2 to 5 rounds | 21 s (JPG), 81 s (HEIC) |
| Single render | 41 to 50 s | 44 to 52 s |
| Apply to all / second piece | 46 s | 44 to 64 s |
| Photo to quote in practice | about 5 min | – |
| Designer: plan to pieces / render / PDF | 8.9 s / 46.8 s / 1.5 s | – |

Static assets carry no Cache-Control header and each round trip is 0.8 to 1.5 s, so every page load refetches 160 KB of JavaScript and 235 KB hero images.

## Findings by severity

### Blockers (fixed where marked)
1. **Blank before/after in the phone result modal.** The fresh result image can 404 on its first GET (volume sync lag) and the modal images had no reload-on-error, so the core moment showed a 2 px line. Seen on EN and AR runs. **Fixed:** modal and chat-thumb images now reload up to three times.
2. **Second piece did not build on the first on desktop.** After a sofa swap, a curtains Try rendered on the untouched photo, and the share image and PDF then contradicted the bill. Cause: every chat turn echoes the server's assignments over the client's, and a single swap was recorded only client-side. **Fixed:** single-swap picks are recorded server-side; verified live on desktop and phone (summary lists both pieces, canvas shows the combined render).
3. **Upload HTTP 500, intermittent.** About 2 of 9 first requests failed (HEIC and JPG), shown as "check your connection". Four direct HEIC uploads afterwards all succeeded in 3 s. Not reproduced, not fixed; the copy no longer blames the user's connection. The Modal log stream did not retain the traceback.
4. **`/api/swap` returned 500** for any bad image path and once for an unknown target after a full 43 s model run; an unknown target was otherwise silently swapped as a sofa. **Fixed:** the endpoint validates like the stream endpoints and rejects unknown targets with 400.

### Major
- Consultant quality: says "I found some lovely options" then asks another question; answered "Under $20" with $37 to $41 picks and no disclosure in the text (the receipt line was missing on desktop cards, **fixed**); recommended a dimout and a thermal fabric for "sheer"; re-recommended instead of quoting when asked for the quote; recommended upholstery and offered "Try on my photo" on a kitchen photo with a fridge and nothing to recover.
- Pattern scale: honeycomb and stripe fabrics render 5 to 10 times too large (quilt-scale hexagons, deck-chair stripes) while the self-score reads 8 or 9 out of 10. One curtains render scored 3/10, honestly.
- Failure state of the swap modal had no Close button and kept spinning. **Fixed.**
- English "Just show me" chip inside Arabic chips. **Fixed.**
- Language switch mid-conversation wipes the chat, photo and results without warning.
- RTL swap modal: step bullets overlap the text and the clock reads "s 2".
- Room viewer on the phone: analysis pills drawn over the photo, outline labels overlapping, 4th tile clipped.
- Browse panel for curtains listed upholstery velvets (the filter keyed on a field that means home/hotel/kids). **Fixed.**
- No upload size cap: a 57 MB body was accepted. **Fixed at 25 MB.**
- Designer: detected boxes sit visibly offset from the drawn pieces; render 47 s against the page's "about 30 seconds"; Spark itself notes the render moved the sofa and added a window (layout match 7/10).
- Occasional 500 on the targets endpoint and a 408 on the chat stream, both recovered by the UI.

### Minor
- 60 s HEIC turn with a silent retry; "about a minute" copy holds for JPG only.
- Money formatting inconsistent ("$1090.5" on the card, "$1,090.50" in chat).
- PDF has no text layer; two thirds of the page empty.
- Every fresh session logs a 404 on the session-state call.
- Untranslated aria-labels and page title in non-English modes; English trace lines in Arabic.
- Several tap targets under 40 px on the phone (Close, Download, chips).
- Designer plan endpoint 500s on text bytes named .jpg; proposal endpoint 500s on a NaN total or a non-numeric CO₂ (not reachable from the UI).
- No HSTS, CSP or X-Content-Type-Options headers; docs and openapi exposed behind the lock.

### Nits
Typo "تغّيره"; bidi price "م/٣٧$"; persona gender varies by language; "a armchair"; name wrapping "Honeycom / b"; 19 m for a 3-seater unexplained; hero images with empty alt.

## What held up under attack
- Scope guard held on off-topic prompts; the system prompt did not leak; two bogus fabric codes were denied and nothing was invented.
- Every path traversal attempt on uploads, samples, share tokens and session ids was rejected; share tokens are HMAC-signed and tamper-proof; noindex on every response; WhatsApp webhook gated.
- Three concurrent renders all succeeded within 64 s.
- Session restore after refresh kept messages, cards, previews and the canvas.
- Landing: zero broken links or images; hero slider works with mouse, keys and taps.

## Fixes shipped after the test (commit `1bec7c8`, live)
Image reload-on-error in the modal and chat thumbs; Close button and stopped spinner on a failed check; single-swap picks recorded server-side so the next piece builds on them; receipt line on desktop cards; localized Just-show-me chip; `/api/swap` validation and 400 on unknown targets; 25 MB upload cap; piece-based Browse filter; honest upload-failure copy. Full suite 437 green.

## Left as is, by decision
Consultant question count and budget adherence (prompt work, risky before judging); pattern scale (model behaviour); language switch wiping state; RTL modal layout; phone viewer overlaps; designer box offset; the intermittent upload 500 (not reproduced).

## Recommendation for the judging hour
Warm the sample room once within the hour. Keep the judges on the sample path. Open the video on the slider moment. If a judge uploads a HEIC, say "about a minute" before they do.
