# Authentication Pages Design

## Goal

Replace the basic login and registration screens with a polished, responsive
authentication experience that balances a practical decision workspace with
the product's AI-forward visual identity.

## Scope

- Keep the existing login, registration, redirect, validation and API flows.
- Use a shared authentication shell for both routes.
- Add clear field focus, validation, busy, error and password-visibility
  states.
- Make the layout efficient on mobile and visually rich on desktop.

## Layout

Desktop uses a two-column composition. A restrained brand panel introduces
YanJie as a personal decision coach through an abstract decision-path visual
and a small set of outcome-oriented signals. The authentication form occupies
the focused right column.

On narrow screens the brand panel becomes a compact header and the form fills
the available width. The primary action remains visible without a decorative
or overlapping layout.

## Interaction

The form preserves the existing username/email and password fields for login,
and username, optional email and password fields for registration. Password
visibility is controlled with an accessible icon button. Registration shows
local password guidance and a strength indicator; server responses remain the
source of truth. Submit buttons retain the store's busy and error behavior.

## Visual Language

The pages retain the existing dark abyss, cyan and blue palette, but use a
lighter, more structured surface than the current single glass card. The
decision-path visual uses code-native HTML and CSS rather than a new external
asset. Motion is minimal and respects the existing reduced-motion rule.

## Verification

- `npm run build` completes successfully.
- Existing routes remain `/login` and `/register`.
- Login maintains the `redirect` query behavior.
- Registration maintains automatic navigation to `/` after success.
- Controls remain usable at desktop and mobile widths.
