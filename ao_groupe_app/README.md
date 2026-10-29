# AO groupe Flutter storefront prototype

An independent Flutter 3 / Material 3 storefront prototype for the products in
the AO groupe reference images. Arabic is the default locale and uses RTL layout;
French and English are also available. The app includes onboarding, a
categorized catalog with an automatically transitioning, pauseable product
showcase, product details, favorites, quote-request drafts, and the supplied
brand mark. The catalog contains only the 14 pictured references; they remain
quote-only until real product, pricing, and inventory data are verified.

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

This is an offline prototype, not a production commerce service. Pictured
products are references only; prices and stock are intentionally not shown.
Quote requests remain local drafts and are not submitted to the store. Delivery
and branch details must be confirmed before launch. The app has no
authentication, backend, payment processing, or secure administrative access.

Production release requires verified business catalog and branch data,
backend and authentication setup, secure order/inventory APIs, a payment
provider, privacy and security review, and platform release configuration.
This repository currently includes a web target only; native Android/iOS
release setup has not been added.
