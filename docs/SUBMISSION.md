# ReCover — submission text (English)

Paste-ready blocks for the hackathon form. Fill the two bracketed
items before submitting: the demo credentials and the video link.

## Project name

ReCover

## Tagline

Change the look, not the furniture. An AI upholstery consultant that
shows your own sofa in a new fabric before you buy a metre.

## Short description (about 100 words)

Most sofas are thrown out for their fabric, not their frame. ReCover
is an AI upholstery consultant: photograph your sofa, describe your
home in plain language (kids, a cat, afternoon sun, a budget), and get
three fabrics that fit, each justified with real catalog numbers. Then
see the result on your own furniture: SAM 3.1 isolates the piece, Muse
Image reupholsters only that region, and Muse Spark checks the result
and retries when it is not convincing. Finish with metres, a price
estimate, the CO₂ avoided, and a one-tap WhatsApp handoff to an
upholsterer or a PDF proposal.

## The problem

- 12.1 million tons of furniture were discarded in the US in a single
  year (US EPA, 2018); about 80% went to landfill.
- 10 million+ tonnes are discarded each year in the EU (EEB, 2017).
- Reupholstering a 3-seat sofa avoids about 52 kg of CO₂e (sourced
  from EPD NEPD-1805-759, manufacturing stages A1–A3).

People replace instead of reupholstering for two reasons: they do not
know which fabric survives their home, and they cannot picture the
result. ReCover removes both.

## What it does

1. Room analysis: upload a photo (or pick a sample room). Spark
   reports room type, style, light level, the pieces it sees and a
   wall-colour palette.
2. A real multi-turn consultant, not a questionnaire. It learns the
   piece, the room, who uses it and the budget one question at a time,
   in the customer's language, by text or voice.
3. Grounded recommendations: exactly three fabrics per turn, every
   code validated against the catalog search for that turn, with
   receipts showing what matched and what was relaxed, in numbers.
4. Part-accurate swap: SAM 3.1 segments the sofa, armchair, cushions
   or curtains; Muse Image recolours only that region; the result is
   composited back so the rest of the room is pixel-identical; Spark
   scores colour, pattern, scale and isolation and the swap retries
   once below 7/10. Hidden slivers behind throws and tables get a
   second aimed pass. Before/after slider and a match badge.
5. Apply to all: assign a fabric per piece and render every piece in
   parallel from the original photo.
6. Quote and handoff: a yardage table, a USD estimate labelled
   preliminary, the CO₂ avoided, a WhatsApp message with a signed
   14-day preview link, and a PDF proposal.
7. For designers: a floor plan with numbered pieces, a top-down
   render and a client-ready PDF.

Five live languages (English, Arabic with RTL, Hindi, French,
Spanish), phone and desktop.

## Meta models used

| Model | Role |
|---|---|
| muse-spark-1.3 | Consultant agent with tools, room vision, target listing, swap verification, catalog tagging |
| muse-image-1.0 | Fabric edit inside the swap, catalog swatches, sample rooms |
| sam-3.1 | Piece segmentation for the swap and the tappable outlines |
| muse-voice-transcribe-1.0 | Hold-to-talk voice input |

## How it is built

FastAPI backend, vanilla JavaScript front end with no build step,
server-sent events for chat and swap progress, deployed on Modal.
Everything in the repository was written during the hackathon.
426 automated tests, including real WebKit browser runs for the phone
and desktop journeys, plus a live end-to-end proof script against the
deployed app.

## Try it

Live app: https://moalaa2--recover-ai-web.us-east.modal.run
Demo lock: [username / password, or state that the lock is removed]
Fastest path: open /consult?sample=living, tap Try on a fabric, then
Apply to all.

Repository: https://github.com/MoAlaa2/recover-ai

Video: [link]

## Honest limits

- A swap takes 30 to 60 seconds per piece; Apply to all runs pieces
  in parallel and finishes in about a minute.
- Items the photo does not contain (a roller blind when curtains are
  requested) are reported as not visible instead of being faked.
- Prices are catalog estimates in USD and are labelled preliminary;
  the upholsterer confirms them.
