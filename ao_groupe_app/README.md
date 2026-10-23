# AO groupe Flutter storefront prototype

An independent Flutter 3 / Material 3 storefront prototype for electrical,
lighting, and solar products. Arabic is the default locale and uses RTL layout;
French and English are also available. The app includes onboarding, a
categorized catalog, product details, favorites, a cart and demo checkout,
order history, quote-request drafts, planning calculators, and local admin
preview.

## Run

From this directory, with Flutter 3 installed:

```powershell
flutter pub get
flutter run -d chrome
```

The first launch shows onboarding. Later launches open the storefront. Open
**Account > Settings** to change the language, appearance, or revisit the design
system showcase.

## Verify and build for web

```powershell
dart format --output=none --set-exit-if-changed lib test
flutter analyze --fatal-infos
flutter test
flutter build web --release
```

The static web build is written to `build/web/`. Deploy it to a static host
with single-page-app fallback routing enabled. The GitHub Actions workflow runs
formatting, analysis, widget and unit tests, and the release web build when
this app changes.

## Prototype limitations

This is an offline prototype, not a production commerce service. Catalog,
brands, prices, discounts, stock, delivery estimates, and branch labels are
illustrative. Cart, favorites, orders, and inventory adjustments are in-memory
demo state; checkout does not submit an order. CCP and Edahabia payment are
disabled, and there is no authentication, backend, real branch contact data,
or secure administrative access. Do not use the displayed electrical or solar
calculations as installation guidance; a qualified professional must verify
all designs.

Production release requires verified business catalog and branch data,
backend and authentication setup, secure order/inventory APIs, a payment
provider, privacy and security review, and platform release configuration.
This repository currently includes a web target only; native Android/iOS
release setup has not been added.
