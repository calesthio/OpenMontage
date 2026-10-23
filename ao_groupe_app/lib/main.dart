import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'l10n/app_localizations.dart';
import 'l10n/store_strings.dart';
import 'screens/onboarding_screen.dart';
import 'screens/store_shell.dart';
import 'theme/app_theme.dart';

void main() {
  runApp(const AoGroupeApp());
}

class AoGroupeApp extends StatefulWidget {
  const AoGroupeApp({super.key});

  @override
  State<AoGroupeApp> createState() => _AoGroupeAppState();
}

class _AoGroupeAppState extends State<AoGroupeApp> {
  Locale _locale = const Locale('ar');
  ThemeMode _themeMode = ThemeMode.system;
  bool? _showOnboarding;
  Object? _startupError;

  Future<void> _setLocale(Locale locale) async {
    if (!AppLocalizations.supportedLocales
        .any((supported) => supported.languageCode == locale.languageCode)) {
      throw ArgumentError.value(locale, 'locale', 'Unsupported locale.');
    }
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString('app.locale', locale.languageCode);
    if (!mounted) return;
    setState(() => _locale = locale);
  }

  Future<void> _setThemeMode(ThemeMode themeMode) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString('app.themeMode', themeMode.name);
    if (!mounted) return;
    setState(() => _themeMode = themeMode);
  }

  @override
  void initState() {
    super.initState();
    _loadStartupState();
  }

  Future<void> _loadStartupState() async {
    try {
      await Future<void>.delayed(const Duration(milliseconds: 750));
      final preferences = await SharedPreferences.getInstance();
      final localeCode = preferences.getString('app.locale') ?? 'ar';
      final locale = AppLocalizations.supportedLocales.firstWhere(
        (supported) => supported.languageCode == localeCode,
        orElse: () => const Locale('ar'),
      );
      final themeMode = switch (preferences.getString('app.themeMode')) {
        'light' => ThemeMode.light,
        'dark' => ThemeMode.dark,
        _ => ThemeMode.system,
      };
      if (!mounted) return;
      setState(() {
        _locale = locale;
        _themeMode = themeMode;
        _showOnboarding =
            !(preferences.getBool('onboarding.complete') ?? false);
        _startupError = null;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _startupError = error);
    }
  }

  Future<void> _completeOnboarding() async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setBool('onboarding.complete', true);
    if (!mounted) return;
    setState(() => _showOnboarding = false);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AO groupe',
      debugShowCheckedModeBanner: false,
      locale: _locale,
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      themeMode: _themeMode,
      home: AnimatedSwitcher(
        duration: const Duration(milliseconds: 350),
        child: _startupError != null
            ? _StartupError(
                key: const ValueKey('startup-error'),
                error: _startupError!,
                onRetry: _loadStartupState,
              )
            : _showOnboarding == null
                ? const _SplashScreen(key: ValueKey('splash'))
                : _showOnboarding!
                    ? OnboardingScreen(
                        key: const ValueKey('onboarding'),
                        onComplete: _completeOnboarding,
                      )
                    : StoreShell(
                        key: const ValueKey('store'),
                        locale: _locale,
                        themeMode: _themeMode,
                        onLocaleChanged: _setLocale,
                        onThemeModeChanged: _setThemeMode,
                      ),
      ),
    );
  }
}

class _SplashScreen extends StatelessWidget {
  const _SplashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 88,
              height: 88,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF0B1F4B), Color(0xFF1D4ED8)],
                ),
                borderRadius: BorderRadius.circular(28),
                boxShadow: [
                  BoxShadow(
                    color: const Color(0xFF1D4ED8).withValues(alpha: 0.22),
                    blurRadius: 32,
                    offset: const Offset(0, 12),
                  ),
                ],
              ),
              child: const Icon(
                Icons.bolt_rounded,
                color: Color(0xFFFFB800),
                size: 52,
              ),
            ),
            const SizedBox(height: 18),
            Text(
              'AO groupe',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
            ),
            const SizedBox(height: 6),
            Text(
              StoreStrings.of(context).text('stockDemo'),
              style: TextStyle(
                color: dark ? Colors.white60 : Colors.black54,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StartupError extends StatelessWidget {
  const _StartupError({
    required this.error,
    required this.onRetry,
    super.key,
  });

  final Object error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline_rounded, size: 48),
              const SizedBox(height: 12),
              Text(
                'AO groupe could not start: $error',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: onRetry,
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
