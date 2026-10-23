import 'package:flutter/material.dart';

import '../l10n/store_strings.dart';
import '../models/store_controller.dart';
import '../theme/app_colors.dart';
import 'account_screens.dart';
import 'cart_screens.dart';
import 'catalog_screen.dart';
import 'home_screen.dart';

class StoreShell extends StatefulWidget {
  const StoreShell({
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
  State<StoreShell> createState() => _StoreShellState();
}

class _StoreShellState extends State<StoreShell> {
  final StoreController _controller = StoreController();
  int _selectedIndex = 0;
  String? _categoryId;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _selectCategory(String categoryId) {
    setState(() {
      _categoryId = categoryId;
      _selectedIndex = 1;
    });
  }

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    final labels = [
      strings.text('home'),
      strings.text('categories'),
      strings.text('search'),
      strings.text('cart'),
      strings.text('account'),
    ];

    final pages = [
      HomeScreen(
        controller: _controller,
        onOpenTab: (index) => setState(() => _selectedIndex = index),
        onCategorySelected: _selectCategory,
      ),
      CatalogScreen(
        key: ValueKey('categories-$_categoryId'),
        controller: _controller,
        initialCategoryId: _categoryId,
        showCategories: true,
      ),
      CatalogScreen(
        key: const ValueKey('search'),
        controller: _controller,
      ),
      CartScreen(
        controller: _controller,
        onBrowse: () => setState(() => _selectedIndex = 1),
      ),
      AccountScreen(
        controller: _controller,
        locale: widget.locale,
        themeMode: widget.themeMode,
        onLocaleChanged: widget.onLocaleChanged,
        onThemeModeChanged: widget.onThemeModeChanged,
      ),
    ];

    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) => Scaffold(
        appBar: _StoreAppBar(
          onGoHome: () => setState(() => _selectedIndex = 0),
          onOpenCart: () => setState(() => _selectedIndex = 3),
          cartCount: _controller.cartCount,
        ),
        body: IndexedStack(
          index: _selectedIndex,
          children: pages,
        ),
        bottomNavigationBar: SafeArea(
          top: false,
          child: Container(
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surface,
              border: Border(
                top: BorderSide(color: Theme.of(context).dividerColor),
              ),
            ),
            child: NavigationBar(
              selectedIndex: _selectedIndex,
              onDestinationSelected: (index) {
                setState(() => _selectedIndex = index);
              },
              destinations: [
                NavigationDestination(
                  icon: const Icon(Icons.home_outlined),
                  selectedIcon: const Icon(Icons.home_rounded),
                  label: labels[0],
                ),
                NavigationDestination(
                  icon: const Icon(Icons.grid_view_outlined),
                  selectedIcon: const Icon(Icons.grid_view_rounded),
                  label: labels[1],
                ),
                NavigationDestination(
                  icon: const Icon(Icons.search_rounded),
                  selectedIcon: const Icon(Icons.manage_search_rounded),
                  label: labels[2],
                ),
                NavigationDestination(
                  icon: Badge(
                    isLabelVisible: _controller.cartCount > 0,
                    label: Text('${_controller.cartCount}'),
                    child: const Icon(Icons.shopping_bag_outlined),
                  ),
                  selectedIcon: Badge(
                    isLabelVisible: _controller.cartCount > 0,
                    label: Text('${_controller.cartCount}'),
                    child: const Icon(Icons.shopping_bag_rounded),
                  ),
                  label: labels[3],
                ),
                NavigationDestination(
                  icon: const Icon(Icons.person_outline_rounded),
                  selectedIcon: const Icon(Icons.person_rounded),
                  label: labels[4],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _StoreAppBar extends StatelessWidget implements PreferredSizeWidget {
  const _StoreAppBar({
    required this.onGoHome,
    required this.onOpenCart,
    required this.cartCount,
  });

  final VoidCallback onGoHome;
  final VoidCallback onOpenCart;
  final int cartCount;

  @override
  Widget build(BuildContext context) {
    return AppBar(
      titleSpacing: 18,
      title: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onGoHome,
        child: const Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            _BrandMark(),
            SizedBox(width: 9),
            Text(
              'AO groupe',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
            ),
          ],
        ),
      ),
      actions: [
        IconButton(
          tooltip: StoreStrings.of(context).text('cart'),
          onPressed: onOpenCart,
          icon: Badge(
            isLabelVisible: cartCount > 0,
            label: Text('$cartCount'),
            child: const Icon(Icons.shopping_bag_outlined),
          ),
        ),
        const SizedBox(width: 8),
      ],
    );
  }

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);
}

class _BrandMark extends StatelessWidget {
  const _BrandMark();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 34,
      height: 34,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [AppColors.primary, AppColors.primaryBright],
        ),
        borderRadius: BorderRadius.circular(11),
      ),
      child: const Icon(Icons.bolt_rounded, color: AppColors.accent, size: 22),
    );
  }
}
