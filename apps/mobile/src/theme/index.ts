/**
 * Champagne + charcoal palette: gender-neutral, premium-fashion feel.
 *
 * Light, neutral surfaces let the user's photography (cutouts, try-ons, outfit
 * composites) carry the colour. The single warm metallic accent — champagne /
 * burnished copper — is what the eye lands on for actionable elements (CTAs,
 * focus rings, selected chips).
 *
 * Kid mode keeps a bright override so the same screens feel playful in the
 * family ecosystem without forking the layout.
 */

export const palette = {
  // Surfaces
  background: "#FBF7F2", // warm cream — feels like a fashion magazine page
  surface: "#FFFFFF", // cards on top of the cream background
  surfaceAlt: "#EDE7DD", // dividers, image placeholders, ghost-button borders

  // Type
  text: "#1A1A1A", // near-black, the only thing the brand uses for body copy
  textMuted: "#6B6B6B", // metadata, hints, secondary labels

  // Single accent — champagne / burnished copper. Used for primary CTAs,
  // promo dots, selected chips, focus rings. Resist the urge to use this
  // anywhere decorative — keep it scarce so the eye trusts it.
  accent: "#B8915F",
  accentDark: "#8E6E47",

  // Text/spinner color when rendered *on top of* the accent (or kid accent).
  // Near-black gives ~6:1 contrast on champagne, ~7:1 on orange — both well
  // above WCAG AA. Use this anywhere you'd previously have used `background`
  // as the text color on a CTA.
  onAccent: "#1A1A1A",

  // Semantic
  success: "#3D7C5A",
  danger: "#B23A48",

  // Kid mode override — bright, friendly, still warm-toned so it doesn't
  // clash with the parent palette when a guardian switches profiles.
  kidPrimary: "#FF8A4C", // bright orange
  kidAccent: "#FFC857", // sunshine yellow
};

export const radii = { sm: 8, md: 14, lg: 22, pill: 999 };

export const spacing = (n: number) => n * 4;

export type ThemeMode = "adult" | "kid";
