import 'package:flutter/material.dart';

import '../l10n/store_strings.dart';
import '../theme/app_colors.dart';

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({required this.onComplete, super.key});

  final Future<void> Function() onComplete;

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  int _step = 0;
  bool _saving = false;

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    final titles = [
      strings.text('onboardingWelcome'),
      strings.text('onboardingCatalog'),
      strings.text('onboardingOrders'),
    ];
    final descriptions = [
      strings.text('onboardingWelcomeBody'),
      strings.text('onboardingCatalogBody'),
      strings.text('onboardingOrdersBody'),
    ];
    final artwork = [
      'assets/products/wall-lamp-modern.png',
      'assets/products/tv-wall-mount.png',
      'assets/products/custom-wall-lamp.png',
    ];
    final motionDuration = MediaQuery.disableAnimationsOf(context)
        ? Duration.zero
        : const Duration(milliseconds: 280);

    return Scaffold(
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final wide = constraints.maxWidth > 650;
            final artHeight = constraints.maxHeight < 700
                ? wide
                    ? 240.0
                    : 200.0
                : wide
                    ? 320.0
                    : 250.0;
            return Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 950),
                child: Padding(
                  padding: const EdgeInsetsDirectional.fromSTEB(22, 14, 22, 22),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Row(
                        children: [
                          _OnboardingBrand(),
                          const Spacer(),
                          TextButton(
                            onPressed: _saving ? null : _complete,
                            child: Text(strings.text('skip')),
                          ),
                        ],
                      ),
                      const Spacer(),
                      AnimatedSwitcher(
                        duration: motionDuration,
                        child: Row(
                          key: ValueKey(_step),
                          children: [
                            Expanded(
                              child: ClipRRect(
                                borderRadius: BorderRadius.circular(28),
                                child: Image.asset(
                                  artwork[_step],
                                  width: double.infinity,
                                  height: artHeight,
                                  fit: BoxFit.cover,
                                  semanticLabel: titles[_step],
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 28),
                      AnimatedSwitcher(
                        duration: motionDuration,
                        child: Column(
                          key: ValueKey('copy-$_step'),
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              titles[_step],
                              style: Theme.of(context)
                                  .textTheme
                                  .headlineMedium
                                  ?.copyWith(fontWeight: FontWeight.w800),
                            ),
                            const SizedBox(height: 10),
                            Text(
                              descriptions[_step],
                              style: Theme.of(context).textTheme.bodyLarge,
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 22),
                      Row(
                        children: List.generate(
                          titles.length,
                          (index) => AnimatedContainer(
                            duration: motionDuration,
                            margin: const EdgeInsetsDirectional.only(end: 7),
                            width: _step == index ? 26 : 8,
                            height: 8,
                            decoration: BoxDecoration(
                              color: _step == index
                                  ? AppColors.primaryBright
                                  : Theme.of(context).dividerColor,
                              borderRadius: BorderRadius.circular(99),
                            ),
                          ),
                        ),
                      ),
                      const Spacer(),
                      Row(
                        children: [
                          Text(
                            '${_step + 1} ${strings.text('stepOf')} ${titles.length}',
                            style: Theme.of(context).textTheme.labelLarge,
                          ),
                          const Spacer(),
                          FilledButton.icon(
                            onPressed: _saving
                                ? null
                                : _step == titles.length - 1
                                    ? _complete
                                    : () => setState(() => _step += 1),
                            icon: Icon(
                              _step == titles.length - 1
                                  ? Icons.arrow_forward_rounded
                                  : Icons.chevron_right_rounded,
                            ),
                            label: Text(
                              strings.text(
                                _step == titles.length - 1
                                    ? 'getStarted'
                                    : 'next',
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }

  Future<void> _complete() async {
    setState(() => _saving = true);
    try {
      await widget.onComplete();
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }
}

class _OnboardingBrand extends StatelessWidget {
  const _OnboardingBrand();

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Image.asset(
          'assets/brand/ao-groupe.png',
          width: 40,
          height: 40,
          semanticLabel: 'AO groupe',
        ),
        const SizedBox(width: 10),
        Text('AO groupe',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w800,
                )),
      ],
    );
  }
}
