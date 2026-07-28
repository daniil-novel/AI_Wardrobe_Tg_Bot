# Claude Code Opus: post-deploy UX review

Date: 2026-07-29  
Mode: read-only (`--permission-mode plan`, `--tools Read`, no session persistence)  
Evidence: final 390×844 production screenshots `01`–`21` and `tmp/e2e/production-e2e.json`

## Verdict

**GO (conditional).** No P0 blockers were found. The reviewer considered the application suitable for the current
deployment and product demo, but not yet for a broad paid launch without resolving the P1 visual-content findings.

Evidence explicitly accepted by the reviewer:

- `scrollWidth == clientWidth == 390` on all 21 recorded steps;
- zero console errors, failed requests and automated E2E issues;
- the fixed bottom navigation appearing in the middle of full-page screenshots is a capture artifact, not proof of
  an inaccessible element;
- payment-disabled wording, preliminary-price labels, explicit avatar consent and no-beautification language support
  commercial trust.

## Findings returned by Opus

### P1

1. Some pre-existing wardrobe cards use a category placeholder while carrying the provenance badge `Ваше фото`.
   The reviewer also found that saved outfit cards had no visual collage. This weakens trust in a visual wardrobe.
2. Repeated generic titles such as `Образ из вашего гардероба` make saved looks hard to distinguish. The synthetic
   account also contains intentional repeated uploads, which should remain clearly marked for review.
3. On Today, the `Завтра` and `Лучший вариант` sections can repeat the same one-item recommendation; the selected
   `Много метро` context chip near quick scenarios can look detached from its purpose.

### P2

- `VIRTUAL TRY-ON` was the only English eyebrow inside an otherwise Russian flow.
- The Free-plan checked item `Ограниченный AI-анализ` can read like a benefit rather than a stated limit.
- The synthetic E2E body-description text is visibly test data and must not be mistaken for production copy.
- The initial Designer state has more vertical whitespace than the other screens.
- A try-on of a thin bracelet is hard to distinguish visually from the base avatar.
- Long garment names must retain the intended two-line clamp.

## Per-tab assessment

| Tab | Assessment |
| --- | --- |
| Today | Clear hierarchy, with repetitive copy as the main weakness |
| Wardrobe | Understandable two-column catalog; legacy placeholders need honest treatment |
| Add | Strongest flow: clear drop zone, selection editor and privacy explanation |
| Designer | Scenario-first interaction and CTA are clear; initial whitespace can be tightened |
| Favorites | Structure is clear, but outfit imagery was missing |
| Studio | One-column plans and trust language work; localization needed one final pass |

## Codex adjudication

The review correctly identified the missing saved-outfit collage and the English try-on eyebrow. Both were fixed
after this review. Real product photos were present for all six items created by the final run; the placeholder
finding applies to older records whose derived product image is absent, not to the current upload pipeline. The
try-on comparison used a thin bracelet, so low visual difference is expected and is not evidence that garments were
ignored. The full production run did authenticate with signed synthetic Telegram `initData`; the reviewer's final
“auth not confirmed” caveat conflicts with the supplied E2E trace and is not adopted.
