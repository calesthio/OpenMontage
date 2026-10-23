import 'package:flutter/material.dart';

import '../l10n/app_localizations.dart';
import '../theme/app_colors.dart';
import '../widgets/app_button.dart';
import '../widgets/app_section_header.dart';
import '../widgets/app_status_badge.dart';
import '../widgets/app_surface_card.dart';
import '../widgets/app_text_field.dart';

class DesignSystemShowcase extends StatelessWidget {
  const DesignSystemShowcase({
    required this.locale,
    required this.themeMode,
    required this.onLocaleChanged,
    required this.onThemeModeChanged,
    super.key,
  });

  final Locale locale;
  final ThemeMode themeMode;
  final ValueChanged<Locale> onLocaleChanged;
  final ValueChanged<ThemeMode> onThemeModeChanged;

  @override
  Widget build(BuildContext context) {
    final strings = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const _BrandLockup(),
        actions: [
          Padding(
            padding: const EdgeInsetsDirectional.only(end: 16),
            child: _LanguagePicker(
              locale: locale,
              onChanged: onLocaleChanged,
              label: strings.language,
            ),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsetsDirectional.fromSTEB(20, 16, 20, 40),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1120),
            child: _ShowcaseContent(
              strings: strings,
              themeMode: themeMode,
              onThemeModeChanged: onThemeModeChanged,
            ),
          ),
        ),
      ),
    );
  }
}

class _BrandLockup extends StatelessWidget {
  const _BrandLockup();

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 34,
          height: 34,
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [AppColors.primary, AppColors.primaryBright],
            ),
            borderRadius: BorderRadius.circular(10),
          ),
          child: const Icon(Icons.bolt_rounded, color: AppColors.accent),
        ),
        const SizedBox(width: 10),
        Text(
          'AO groupe',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w800,
              ),
        ),
      ],
    );
  }
}

class _LanguagePicker extends StatelessWidget {
  const _LanguagePicker({
    required this.locale,
    required this.onChanged,
    required this.label,
  });

  final Locale locale;
  final ValueChanged<Locale> onChanged;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: label,
      child: DropdownButton<Locale>(
        value: locale,
        underline: const SizedBox.shrink(),
        borderRadius: BorderRadius.circular(12),
        icon: const Icon(Icons.language_rounded, size: 18),
        selectedItemBuilder: (context) => const [
          _LocaleLabel('العربية'),
          _LocaleLabel('Français'),
          _LocaleLabel('English'),
        ],
        items: const [
          DropdownMenuItem(value: Locale('ar'), child: Text('العربية')),
          DropdownMenuItem(value: Locale('fr'), child: Text('Français')),
          DropdownMenuItem(value: Locale('en'), child: Text('English')),
        ],
        onChanged: (value) {
          if (value != null) onChanged(value);
        },
      ),
    );
  }
}

class _LocaleLabel extends StatelessWidget {
  const _LocaleLabel(this.value);

  final String value;

  @override
  Widget build(BuildContext context) => Align(
        alignment: AlignmentDirectional.centerStart,
        child: Text(value),
      );
}

class _ShowcaseContent extends StatelessWidget {
  const _ShowcaseContent({
    required this.strings,
    required this.themeMode,
    required this.onThemeModeChanged,
  });

  final AppLocalizations strings;
  final ThemeMode themeMode;
  final ValueChanged<ThemeMode> onThemeModeChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _HeroPanel(strings: strings),
        const SizedBox(height: 20),
        _AppearanceCard(
          strings: strings,
          themeMode: themeMode,
          onThemeModeChanged: onThemeModeChanged,
        ),
        const SizedBox(height: 28),
        AppSectionHeader(title: strings.palette),
        const SizedBox(height: 12),
        _PalettePreview(strings: strings),
        const SizedBox(height: 28),
        AppSectionHeader(title: strings.states),
        const SizedBox(height: 12),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: [
            AppStatusBadge(
              label: strings.available,
              status: AppStockStatus.available,
            ),
            AppStatusBadge(
              label: strings.outOfStock,
              status: AppStockStatus.outOfStock,
            ),
            AppStatusBadge(
              label: strings.lowStock,
              status: AppStockStatus.lowStock,
            ),
          ],
        ),
        const SizedBox(height: 28),
        AppSectionHeader(title: strings.components),
        const SizedBox(height: 12),
        _ComponentPreviews(strings: strings),
        const SizedBox(height: 20),
        Text(
          strings.previewNote,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
        ),
      ],
    );
  }
}

class _HeroPanel extends StatelessWidget {
  const _HeroPanel({required this.strings});

  final AppLocalizations strings;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return Container(
      padding: const EdgeInsets.all(28),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: AlignmentDirectional.topStart,
          end: AlignmentDirectional.bottomEnd,
          colors: [AppColors.primary, AppColors.primaryBright],
        ),
        borderRadius: BorderRadius.circular(24),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsetsDirectional.fromSTEB(10, 6, 10, 6),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(999),
            ),
            child: Text(
              'AO GROUPE  ·  UI KIT',
              style: textTheme.labelSmall?.copyWith(
                color: Colors.white,
                letterSpacing: 1.2,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          const SizedBox(height: 18),
          Text(
            strings.showcase,
            style: textTheme.headlineMedium?.copyWith(color: Colors.white),
          ),
          const SizedBox(height: 8),
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 700),
            child: Text(
              strings.showcaseDescription,
              style: textTheme.bodyLarge?.copyWith(
                color: Colors.white.withValues(alpha: 0.86),
              ),
            ),
          ),
          const SizedBox(height: 20),
          Container(
            width: 44,
            height: 4,
            decoration: BoxDecoration(
              color: AppColors.accent,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
        ],
      ),
    );
  }
}

class _AppearanceCard extends StatelessWidget {
  const _AppearanceCard({
    required this.strings,
    required this.themeMode,
    required this.onThemeModeChanged,
  });

  final AppLocalizations strings;
  final ThemeMode themeMode;
  final ValueChanged<ThemeMode> onThemeModeChanged;

  @override
  Widget build(BuildContext context) {
    return AppSurfaceCard(
      padding: const EdgeInsetsDirectional.fromSTEB(20, 14, 20, 14),
      child: Wrap(
        alignment: WrapAlignment.spaceBetween,
        crossAxisAlignment: WrapCrossAlignment.center,
        runSpacing: 12,
        children: [
          Text(
            strings.appearance,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          SegmentedButton<ThemeMode>(
            showSelectedIcon: false,
            segments: [
              ButtonSegment(
                value: ThemeMode.system,
                label: Text(strings.system),
              ),
              ButtonSegment(
                value: ThemeMode.light,
                label: Text(strings.light),
              ),
              ButtonSegment(
                value: ThemeMode.dark,
                label: Text(strings.dark),
              ),
            ],
            selected: {themeMode},
            onSelectionChanged: (selection) {
              onThemeModeChanged(selection.first);
            },
          ),
        ],
      ),
    );
  }
}

class _PalettePreview extends StatelessWidget {
  const _PalettePreview({required this.strings});

  final AppLocalizations strings;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 12,
      runSpacing: 12,
      children: [
        _ColorSwatch(
          color: AppColors.primary,
          name: strings.primary,
          hex: '#0B1F4B',
        ),
        _ColorSwatch(
          color: AppColors.primaryBright,
          name: strings.gradient,
          hex: '#1D4ED8',
        ),
        _ColorSwatch(
          color: AppColors.accent,
          name: strings.accent,
          hex: '#FFB800',
        ),
        _ColorSwatch(
          color: AppColors.lightBackground,
          name: strings.lightBackground,
          hex: '#F6F8FC',
          outlined: true,
        ),
        _ColorSwatch(
          color: AppColors.darkBackground,
          name: strings.darkBackground,
          hex: '#0A0E1A',
        ),
      ],
    );
  }
}

class _ColorSwatch extends StatelessWidget {
  const _ColorSwatch({
    required this.color,
    required this.name,
    required this.hex,
    this.outlined = false,
  });

  final Color color;
  final String name;
  final String hex;
  final bool outlined;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 154,
      child: AppSurfaceCard(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              height: 56,
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(12),
                border: outlined
                    ? Border.all(color: Theme.of(context).dividerColor)
                    : null,
              ),
            ),
            const SizedBox(height: 10),
            Text(name, style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 2),
            Text(hex, style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}

class _ComponentPreviews extends StatelessWidget {
  const _ComponentPreviews({required this.strings});

  final AppLocalizations strings;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final isWide = constraints.maxWidth >= 760;
        final buttonPanel = AppSurfaceCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              AppSectionHeader(title: strings.buttons),
              const SizedBox(height: 16),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  AppButton(
                    label: strings.primaryAction,
                    icon: Icons.bolt_rounded,
                    onPressed: () {},
                  ),
                  AppButton(
                    label: strings.secondaryAction,
                    variant: AppButtonVariant.secondary,
                    onPressed: () {},
                  ),
                  AppButton(
                    label: strings.outlinedAction,
                    variant: AppButtonVariant.outlined,
                    onPressed: () {},
                  ),
                ],
              ),
              const SizedBox(height: 22),
              AppTextField(
                label: strings.searchLabel,
                hint: strings.searchHint,
                prefixIcon: Icons.search_rounded,
              ),
            ],
          ),
        );

        final productPanel = AppSurfaceCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 52,
                    height: 52,
                    decoration: BoxDecoration(
                      color: AppColors.accent.withValues(alpha: 0.16),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: const Icon(
                      Icons.lightbulb_outline_rounded,
                      color: AppColors.primaryBright,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          strings.productTitle,
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(height: 4),
                        Text(strings.productDescription),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      strings.samplePrice,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                  AppStatusBadge(
                    label: strings.available,
                    status: AppStockStatus.available,
                  ),
                ],
              ),
            ],
          ),
        );

        if (isWide) {
          return Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: buttonPanel),
              const SizedBox(width: 16),
              Expanded(child: productPanel),
            ],
          );
        }
        return Column(
          children: [
            buttonPanel,
            const SizedBox(height: 16),
            productPanel,
          ],
        );
      },
    );
  }
}
