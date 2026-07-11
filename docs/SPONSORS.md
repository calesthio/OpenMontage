# Sponsors

This document defines how sponsor logos are added to the OpenMontage README.

## Sponsor Asset Convention

- Store sponsor logos in `assets/sponsors/`.
- Use a lowercase kebab-case filename based on the sponsor name, for example `acme-video.svg`.
- Prefer SVG. Use PNG only when the sponsor cannot provide vector artwork.
- Keep logos transparent, tightly cropped, and readable at `44px` height.
- Use the sponsor's official website or product page as the link target.
- Use descriptive alt text: `Acme Video logo`, not just `logo`.

## README Snippet

Add each sponsor as a table row inside the `Sponsors` section near the top of `README.md`:

```html
<tr>
<td width="180" align="center"><a href="https://example.com"><img src="assets/sponsors/example-sponsor.svg" alt="Example Sponsor" width="150"></a></td>
<td><strong>Example Sponsor</strong> helps OpenMontage users do something concrete. Mention the useful product outcome, then close with a short <a href="https://example.com">CTA link</a>.</td>
</tr>
```

For a sponsor with separate light and dark logos, use a `picture` element:

```html
<tr>
<td width="180" align="center">
  <a href="https://example.com">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="assets/sponsors/example-sponsor-dark.svg">
      <img src="assets/sponsors/example-sponsor-light.svg" alt="Example Sponsor" width="150">
    </picture>
  </a>
</td>
<td><strong>Example Sponsor</strong> helps OpenMontage users do something concrete. Mention the useful product outcome, then close with a short <a href="https://example.com">CTA link</a>.</td>
</tr>
```

## Intake Checklist

Before adding a sponsor, collect:

- Sponsor display name
- Sponsor URL
- Logo file, preferably SVG
- Confirmation that OpenMontage has permission to display the logo in the README
- Any required trademark wording, if the sponsor has one

Do not add tracking URLs, affiliate redirects, or claims about endorsement unless they are explicitly approved by the project maintainer.
