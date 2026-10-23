import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../l10n/store_strings.dart';
import '../models/algeria_wilaya.dart';
import '../models/catalog.dart';
import '../models/store_controller.dart';
import '../theme/app_colors.dart';
import '../widgets/app_surface_card.dart';
import '../widgets/store_components.dart';
import 'catalog_screen.dart';
import 'cart_screens.dart';
import 'design_system_showcase.dart';
import 'home_screen.dart';

class AccountScreen extends StatelessWidget {
  const AccountScreen({
    required this.controller,
    required this.locale,
    required this.themeMode,
    required this.onLocaleChanged,
    required this.onThemeModeChanged,
    super.key,
  });

  final StoreController controller;
  final Locale locale;
  final ThemeMode themeMode;
  final ValueChanged<Locale> onLocaleChanged;
  final ValueChanged<ThemeMode> onThemeModeChanged;

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    return ListView(
      padding: const EdgeInsetsDirectional.fromSTEB(18, 12, 18, 30),
      children: [
        Container(
          padding: const EdgeInsets.all(22),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [AppColors.primary, AppColors.primaryBright],
            ),
            borderRadius: BorderRadius.circular(24),
          ),
          child: Row(
            children: [
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(18),
                ),
                child: const Icon(Icons.bolt_rounded,
                    color: AppColors.accent, size: 32),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      strings.text('accountTitle'),
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                            color: Colors.white,
                          ),
                    ),
                    const SizedBox(height: 5),
                    Text(
                      strings.text('accountBody'),
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: Colors.white.withValues(alpha: 0.82),
                          ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 14),
        _AccountLink(
          icon: Icons.receipt_long_outlined,
          title: strings.text('orders'),
          trailing: '${controller.orders.length}',
          onTap: () => _open(context, OrdersScreen(controller: controller)),
        ),
        _AccountLink(
          icon: Icons.favorite_border_rounded,
          title: strings.text('favorites'),
          trailing: '${controller.favorites.length}',
          onTap: () => _open(
            context,
            FavoritesScreen(controller: controller),
          ),
        ),
        _AccountLink(
          icon: Icons.business_outlined,
          title: strings.text('branches'),
          onTap: () => _open(context, const BranchesScreen()),
        ),
        _AccountLink(
          icon: Icons.calculate_outlined,
          title: strings.text('tools'),
          onTap: () => _open(context, const SmartToolsScreen()),
        ),
        _AccountLink(
          icon: Icons.settings_outlined,
          title: strings.text('settings'),
          onTap: () => _open(
            context,
            SettingsScreen(
              locale: locale,
              themeMode: themeMode,
              onLocaleChanged: onLocaleChanged,
              onThemeModeChanged: onThemeModeChanged,
            ),
          ),
        ),
        const SizedBox(height: 8),
        _AccountLink(
          icon: Icons.storefront_outlined,
          title: strings.text('wholesaleAccount'),
          onTap: () => _showSignInNotice(context, strings),
        ),
        const SizedBox(height: 22),
        OutlinedButton.icon(
          onPressed: () => _open(
            context,
            AdminDashboardScreen(controller: controller),
          ),
          icon: const Icon(Icons.admin_panel_settings_outlined),
          label: Text(strings.text('adminDemo')),
        ),
        const SizedBox(height: 10),
        Text(
          strings.text('adminNotice'),
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ],
    );
  }

  static void _open(BuildContext context, Widget page) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => page),
    );
  }

  static void _showSignInNotice(
    BuildContext context,
    StoreStrings strings,
  ) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(strings.text('signInRequired'))),
    );
  }
}

class _AccountLink extends StatelessWidget {
  const _AccountLink({
    required this.icon,
    required this.title,
    this.trailing,
    this.onTap,
  });

  final IconData icon;
  final String title;
  final String? trailing;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: Icon(icon, color: AppColors.primaryBright),
        title: Text(title),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (trailing != null)
              Text(
                trailing!,
                style: Theme.of(context).textTheme.labelLarge,
              ),
            const SizedBox(width: 6),
            const Icon(Icons.chevron_right_rounded),
          ],
        ),
        onTap: onTap,
      ),
    );
  }
}

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({
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
    final strings = StoreStrings.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(strings.text('settingsTitle'))),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text(strings.text('language'),
              style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 10),
          DropdownButtonFormField<Locale>(
            initialValue: locale,
            decoration: InputDecoration(labelText: strings.text('language')),
            items: const [
              DropdownMenuItem(value: Locale('ar'), child: Text('العربية')),
              DropdownMenuItem(value: Locale('fr'), child: Text('Français')),
              DropdownMenuItem(value: Locale('en'), child: Text('English')),
            ],
            onChanged: (value) {
              if (value != null) onLocaleChanged(value);
            },
          ),
          const SizedBox(height: 24),
          Text(strings.text('appearance'),
              style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 10),
          SegmentedButton<ThemeMode>(
            showSelectedIcon: false,
            segments: [
              ButtonSegment(
                value: ThemeMode.system,
                label: Text(strings.text('system')),
              ),
              ButtonSegment(
                value: ThemeMode.light,
                label: Text(strings.text('light')),
              ),
              ButtonSegment(
                value: ThemeMode.dark,
                label: Text(strings.text('dark')),
              ),
            ],
            selected: {themeMode},
            onSelectionChanged: (selection) =>
                onThemeModeChanged(selection.first),
          ),
          const SizedBox(height: 26),
          OutlinedButton.icon(
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => DesignSystemShowcase(
                  locale: locale,
                  themeMode: themeMode,
                  onLocaleChanged: onLocaleChanged,
                  onThemeModeChanged: onThemeModeChanged,
                ),
              ),
            ),
            icon: const Icon(Icons.palette_outlined),
            label: Text(strings.text('preview')),
          ),
          const SizedBox(height: 24),
          AppSurfaceCard(
            child: Row(
              children: [
                const Icon(Icons.info_outline_rounded),
                const SizedBox(width: 12),
                Expanded(child: Text(strings.text('orderHistoryDisclaimer'))),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class FavoritesScreen extends StatelessWidget {
  const FavoritesScreen({required this.controller, super.key});

  final StoreController controller;

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(strings.text('favorites'))),
      body: AnimatedBuilder(
        animation: controller,
        builder: (context, _) => CatalogScreen(
          key: ValueKey(controller.favorites.join(',')),
          controller: controller,
          favoritesOnly: true,
        ),
      ),
    );
  }
}

class OrdersScreen extends StatelessWidget {
  const OrdersScreen({required this.controller, super.key});

  final StoreController controller;

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    final languageCode = Localizations.localeOf(context).languageCode;
    return Scaffold(
      appBar: AppBar(title: Text(strings.text('orders'))),
      body: AnimatedBuilder(
        animation: controller,
        builder: (context, _) {
          if (controller.orders.isEmpty) {
            return StoreEmptyState(
              title: strings.text('noOrders'),
              description: strings.text('orderHistoryDisclaimer'),
              icon: Icons.receipt_long_outlined,
            );
          }
          return ListView.separated(
            padding: const EdgeInsets.all(18),
            itemCount: controller.orders.length,
            separatorBuilder: (_, __) => const SizedBox(height: 10),
            itemBuilder: (context, index) {
              final order = controller.orders[index];
              return Card(
                child: ListTile(
                  leading: const CircleAvatar(
                    child: Icon(Icons.inventory_2_outlined),
                  ),
                  title: Text(order.number),
                  subtitle: Text(
                    '${order.items.length} ${strings.text('items')} · ${algerianWilayaByCode(order.wilaya)?.label(languageCode) ?? order.wilaya}',
                  ),
                  trailing: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(formatLocalizedDzd(order.total, languageCode)),
                      IconButton(
                        tooltip: strings.text('reorder'),
                        onPressed: () {
                          for (final item in order.items.entries) {
                            controller.addToCart(item.key, item.value);
                          }
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(strings.text('updatedLocally')),
                            ),
                          );
                        },
                        icon: const Icon(Icons.replay_rounded),
                      ),
                    ],
                  ),
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => OrderTrackingScreen(
                        controller: controller,
                        order: order,
                      ),
                    ),
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}

class BranchesScreen extends StatelessWidget {
  const BranchesScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    final branchInfo = [
      ('branchAlgiers', 'branchAddressAlgiers'),
      ('branchOran', 'branchAddressOran'),
      ('branchSetif', 'branchAddressSetif'),
    ];
    return Scaffold(
      appBar: AppBar(title: Text(strings.text('branches'))),
      body: ListView(
        padding: const EdgeInsets.all(18),
        children: [
          Container(
            height: 176,
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [AppColors.primary, AppColors.primaryBright],
              ),
              borderRadius: BorderRadius.circular(22),
            ),
            child: const Icon(
              Icons.map_outlined,
              color: Colors.white,
              size: 62,
            ),
          ),
          const SizedBox(height: 10),
          Text(strings.text('branchMapHint')),
          const SizedBox(height: 14),
          ...branchInfo.map((entry) => Card(
                margin: const EdgeInsets.only(bottom: 10),
                child: ListTile(
                  leading: const Icon(
                    Icons.location_on_outlined,
                    color: AppColors.primaryBright,
                  ),
                  title: Text(strings.text(entry.$1)),
                  subtitle: Text(
                    '${strings.text(entry.$2)}\n${strings.text('branchHours')}',
                  ),
                  isThreeLine: true,
                  trailing: IconButton(
                    tooltip: strings.text('call'),
                    onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text(strings.text('callUnavailable'))),
                    ),
                    icon: const Icon(Icons.call_outlined),
                  ),
                ),
              )),
        ],
      ),
    );
  }
}

class SmartToolsScreen extends StatelessWidget {
  const SmartToolsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: Text(strings.text('tools')),
          bottom: TabBar(
            isScrollable: true,
            tabs: [
              Tab(text: strings.text('cableCalculator')),
              Tab(text: strings.text('solarCalculator')),
              Tab(text: strings.text('quoteTitle')),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            const CableCalculator(),
            const SolarCalculator(),
            const GeneralQuoteEntry(),
          ],
        ),
      ),
    );
  }
}

class CableCalculator extends StatefulWidget {
  const CableCalculator({super.key});

  @override
  State<CableCalculator> createState() => _CableCalculatorState();
}

class _CableCalculatorState extends State<CableCalculator> {
  final _power = TextEditingController(text: '2000');
  final _length = TextEditingController(text: '20');
  final _voltage = TextEditingController(text: '230');
  double? _current;
  double? _section;

  @override
  void dispose() {
    _power.dispose();
    _length.dispose();
    _voltage.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        _CalculatorIntro(
          icon: Icons.cable_rounded,
          title: strings.text('cableCalculator'),
          warning: strings.text('contactElectrician'),
        ),
        const SizedBox(height: 16),
        _NumericField(controller: _power, label: strings.text('loadWatts')),
        _NumericField(controller: _length, label: strings.text('cableLength')),
        _NumericField(controller: _voltage, label: strings.text('voltage')),
        const SizedBox(height: 14),
        FilledButton(
          onPressed: _calculate,
          child: Text(strings.text('calculate')),
        ),
        if (_current != null) ...[
          const SizedBox(height: 16),
          _CalculatorResult(
            title: strings.text('calculatorResult'),
            lines: [
              '${strings.text('estimatedCurrent')}: ${_current!.toStringAsFixed(1)} A',
              '${strings.text('suggestedCable')}: ${_section! > 0 ? '${_section!.toStringAsFixed(1)} mm²' : '>185 mm²'}',
            ],
          ),
        ],
      ],
    );
  }

  void _calculate() {
    final power = double.tryParse(_power.text);
    final length = double.tryParse(_length.text);
    final voltage = double.tryParse(_voltage.text);
    if (power == null ||
        length == null ||
        voltage == null ||
        !power.isFinite ||
        !length.isFinite ||
        !voltage.isFinite ||
        power <= 0 ||
        length <= 0 ||
        voltage <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(StoreStrings.of(context).text('requiredField'))),
      );
      return;
    }
    final current = power / voltage;
    final minimumSection = (2 * length * current * 0.0175) / (voltage * 0.03);
    const standardSizes = [
      1.5,
      2.5,
      4.0,
      6.0,
      10.0,
      16.0,
      25.0,
      35.0,
      50.0,
      70.0,
      95.0,
      120.0,
      150.0,
      185.0,
    ];
    setState(() {
      _current = current;
      _section = minimumSection <= standardSizes.last
          ? standardSizes.firstWhere(
              (section) => section >= minimumSection,
              orElse: () => -1,
            )
          : -1;
    });
  }
}

class SolarCalculator extends StatefulWidget {
  const SolarCalculator({super.key});

  @override
  State<SolarCalculator> createState() => _SolarCalculatorState();
}

class _SolarCalculatorState extends State<SolarCalculator> {
  final _load = TextEditingController(text: '1200');
  final _hours = TextEditingController(text: '5');
  final _sunHours = TextEditingController(text: '5');
  int? _panelCount;
  int? _batteryCapacity;

  @override
  void dispose() {
    _load.dispose();
    _hours.dispose();
    _sunHours.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        _CalculatorIntro(
          icon: Icons.solar_power_rounded,
          title: strings.text('solarCalculator'),
          warning: strings.text('contactElectrician'),
        ),
        const SizedBox(height: 16),
        _NumericField(controller: _load, label: strings.text('loadWatts')),
        _NumericField(controller: _hours, label: strings.text('systemHours')),
        _NumericField(
          controller: _sunHours,
          label: strings.text('solarIrradiance'),
        ),
        const SizedBox(height: 14),
        FilledButton(
          onPressed: _calculate,
          child: Text(strings.text('calculate')),
        ),
        if (_panelCount != null) ...[
          const SizedBox(height: 16),
          _CalculatorResult(
            title: strings.text('calculatorResult'),
            lines: [
              '${strings.text('estimatedPanels')}: $_panelCount × 550 W',
              '${strings.text('projectList')}: $_batteryCapacity Ah at 48 V',
            ],
          ),
        ],
      ],
    );
  }

  void _calculate() {
    final load = double.tryParse(_load.text);
    final hours = double.tryParse(_hours.text);
    final sunHours = double.tryParse(_sunHours.text);
    if (load == null ||
        hours == null ||
        sunHours == null ||
        !load.isFinite ||
        !hours.isFinite ||
        !sunHours.isFinite ||
        load <= 0 ||
        hours <= 0 ||
        sunHours <= 0 ||
        hours > 24 ||
        sunHours > 24) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(StoreStrings.of(context).text('requiredField'))),
      );
      return;
    }
    const efficiency = 0.75;
    final dailyEnergy = load * hours;
    final panelCount = (dailyEnergy / (550 * sunHours * efficiency)).ceil();
    final batteryAh = (dailyEnergy / (48 * 0.8)).ceil();
    setState(() {
      _panelCount = math.max(1, panelCount).toInt();
      _batteryCapacity = math.max(1, batteryAh).toInt();
    });
  }
}

class _CalculatorIntro extends StatelessWidget {
  const _CalculatorIntro({
    required this.icon,
    required this.title,
    required this.warning,
  });

  final IconData icon;
  final String title;
  final String warning;

  @override
  Widget build(BuildContext context) {
    return AppSurfaceCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 32, color: AppColors.primaryBright),
          const SizedBox(height: 8),
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 6),
          Text(warning, style: Theme.of(context).textTheme.bodySmall),
        ],
      ),
    );
  }
}

class _NumericField extends StatelessWidget {
  const _NumericField({required this.controller, required this.label});

  final TextEditingController controller;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextField(
        controller: controller,
        keyboardType: const TextInputType.numberWithOptions(decimal: true),
        decoration: InputDecoration(labelText: label),
      ),
    );
  }
}

class _CalculatorResult extends StatelessWidget {
  const _CalculatorResult({
    required this.title,
    required this.lines,
  });

  final String title;
  final List<String> lines;

  @override
  Widget build(BuildContext context) {
    return AppSurfaceCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          ...lines.map(
            (line) => Padding(
              padding: const EdgeInsets.only(top: 5),
              child: Text(line),
            ),
          ),
        ],
      ),
    );
  }
}

class GeneralQuoteEntry extends StatelessWidget {
  const GeneralQuoteEntry({super.key});

  @override
  Widget build(BuildContext context) {
    return const _GeneralQuoteLauncher();
  }
}

class _GeneralQuoteLauncher extends StatelessWidget {
  const _GeneralQuoteLauncher();

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(strings.text('quoteBody')),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => const GeneralQuoteFormScreen(),
                ),
              ),
              icon: const Icon(Icons.request_quote_outlined),
              label: Text(strings.text('createQuote')),
            ),
          ],
        ),
      ),
    );
  }
}

class GeneralQuoteFormScreen extends StatelessWidget {
  const GeneralQuoteFormScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const QuoteRequestScreen();
  }
}

class AdminDashboardScreen extends StatelessWidget {
  const AdminDashboardScreen({required this.controller, super.key});

  final StoreController controller;

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    final languageCode = Localizations.localeOf(context).languageCode;
    return Scaffold(
      appBar: AppBar(title: Text(strings.text('adminDemo'))),
      body: AnimatedBuilder(
        animation: controller,
        builder: (context, _) {
          final revenue = controller.orders.fold<int>(
            0,
            (sum, order) => sum + order.total,
          );
          return ListView(
            padding: const EdgeInsets.all(18),
            children: [
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppColors.lowStock.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.warning_amber_rounded,
                        color: AppColors.lowStock),
                    const SizedBox(width: 10),
                    Expanded(child: Text(strings.text('adminNotice'))),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              LayoutBuilder(
                builder: (context, constraints) => GridView.count(
                  crossAxisCount: constraints.maxWidth > 650 ? 3 : 2,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  childAspectRatio: 1.55,
                  children: [
                    _AdminMetric(
                      title: strings.text('salesSummary'),
                      value: formatLocalizedDzd(revenue, languageCode),
                      icon: Icons.trending_up_rounded,
                    ),
                    _AdminMetric(
                      title: strings.text('manageOrders'),
                      value: '${controller.orders.length}',
                      icon: Icons.receipt_long_outlined,
                    ),
                    _AdminMetric(
                      title: strings.text('manageProducts'),
                      value:
                          '${catalogProducts.length} ${strings.text('catalogCount')}',
                      icon: Icons.inventory_2_outlined,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 22),
              StoreSectionTitle(title: strings.text('manageProducts')),
              const SizedBox(height: 8),
              ...catalogProducts.map((product) => _InventoryTile(
                    product: product,
                    controller: controller,
                    languageCode: languageCode,
                  )),
              const SizedBox(height: 22),
              StoreSectionTitle(title: strings.text('manageOrders')),
              if (controller.orders.isEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(strings.text('noOrders')),
                )
              else
                ...controller.orders.map(
                  (order) => ListTile(
                    leading: const Icon(Icons.receipt_outlined),
                    title: Text(order.number),
                    subtitle: Text('${order.wilaya} · ${order.paymentMethod}'),
                    trailing:
                        Text(formatLocalizedDzd(order.total, languageCode)),
                  ),
                ),
              const SizedBox(height: 16),
              Card(
                child: ListTile(
                  leading: const Icon(Icons.people_outline_rounded),
                  title: Text(strings.text('wholesaleApply')),
                  subtitle: Text(strings.text('signInRequired')),
                ),
              ),
              Card(
                child: ListTile(
                  leading: const Icon(Icons.sell_outlined),
                  title: Text(strings.text('coupon')),
                  subtitle: Text('AO5 · 5% · local demo'),
                ),
              ),
              Card(
                child: ListTile(
                  leading: const Icon(Icons.admin_panel_settings_outlined),
                  title: Text(strings.text('settings')),
                  subtitle: Text(strings.text('signInRequired')),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _AdminMetric extends StatelessWidget {
  const _AdminMetric({
    required this.title,
    required this.value,
    required this.icon,
  });

  final String title;
  final String value;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: AppColors.primaryBright),
            const SizedBox(height: 10),
            Text(
              value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            Text(
              title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}

class _InventoryTile extends StatelessWidget {
  const _InventoryTile({
    required this.product,
    required this.controller,
    required this.languageCode,
  });

  final CatalogProduct product;
  final StoreController controller;
  final String languageCode;

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    final stock = controller.stockFor(product.id);
    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      child: ListTile(
        leading: Icon(product.icon, color: product.color),
        title: Text(
          product.name(languageCode),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Text('${strings.text('stockCount')}: $stock'),
        trailing: product.quoteOnly
            ? Text(strings.text('quoteOnly'))
            : IconButton(
                tooltip: strings.text('edit'),
                onPressed: () => _editStock(context, stock, strings),
                icon: const Icon(Icons.edit_outlined),
              ),
      ),
    );
  }

  Future<void> _editStock(
    BuildContext context,
    int stock,
    StoreStrings strings,
  ) async {
    final controller = TextEditingController(text: '$stock');
    final formKey = GlobalKey<FormState>();
    final value = await showDialog<int>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(strings.text('stockCount')),
        content: Form(
          key: formKey,
          child: TextFormField(
            controller: controller,
            autofocus: true,
            keyboardType: TextInputType.number,
            decoration: InputDecoration(labelText: strings.text('stockCount')),
            validator: (input) {
              final amount = int.tryParse(input ?? '');
              return amount == null || amount < 0
                  ? strings.text('requiredField')
                  : null;
            },
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(strings.text('cancel')),
          ),
          FilledButton(
            onPressed: () {
              if (!formKey.currentState!.validate()) return;
              Navigator.pop(context, int.parse(controller.text));
            },
            child: Text(strings.text('confirm')),
          ),
        ],
      ),
    );
    controller.dispose();
    if (value != null) {
      this.controller.setInventory(product.id, value);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(strings.text('updatedLocally'))),
      );
    }
  }
}
