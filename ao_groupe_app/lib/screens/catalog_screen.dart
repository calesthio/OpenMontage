import 'package:flutter/material.dart';

import '../l10n/store_strings.dart';
import '../models/catalog.dart';
import '../models/store_controller.dart';
import '../widgets/store_components.dart';
import 'home_screen.dart';

class CatalogScreen extends StatefulWidget {
  const CatalogScreen({
    required this.controller,
    this.initialCategoryId,
    this.favoritesOnly = false,
    this.showCategories = false,
    super.key,
  });

  final StoreController controller;
  final String? initialCategoryId;
  final bool favoritesOnly;
  final bool showCategories;

  @override
  State<CatalogScreen> createState() => _CatalogScreenState();
}

class _CatalogScreenState extends State<CatalogScreen> {
  late String? _selectedCategory = widget.initialCategoryId;
  String _query = '';
  bool _ascendingPrice = false;

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final normalizedQuery = _query.trim().toLowerCase();
    final products = catalogProducts.where((product) {
      if (widget.favoritesOnly &&
          !widget.controller.favorites.contains(product.id)) {
        return false;
      }
      if (_selectedCategory != null &&
          product.categoryId != _selectedCategory) {
        return false;
      }
      if (normalizedQuery.isEmpty) return true;
      final categoryName =
          strings.text('cat${_categoryTitleSuffix(product.categoryId)}');
      return product.name(locale).toLowerCase().contains(normalizedQuery) ||
          product.brand.toLowerCase().contains(normalizedQuery) ||
          categoryName.toLowerCase().contains(normalizedQuery);
    }).toList()
      ..sort((a, b) {
        if (_ascendingPrice) return a.price.compareTo(b.price);
        final popular = (b.isPopular ? 1 : 0).compareTo(a.isPopular ? 1 : 0);
        if (popular != 0) return popular;
        final newArrival = (b.isNew ? 1 : 0).compareTo(a.isNew ? 1 : 0);
        return newArrival != 0 ? newArrival : a.price.compareTo(b.price);
      });

    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth > 850;
        final horizontalPadding = wide ? 30.0 : 18.0;
        return SingleChildScrollView(
          padding: EdgeInsetsDirectional.fromSTEB(
            horizontalPadding,
            12,
            horizontalPadding,
            30,
          ),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1120),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (widget.showCategories) ...[
                    Text(
                      strings.text('browseCategories'),
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 14),
                    CategoryGrid(
                      onSelected: (categoryId) {
                        setState(() => _selectedCategory = categoryId);
                      },
                    ),
                    const SizedBox(height: 20),
                  ],
                  TextField(
                    onChanged: (value) => setState(() => _query = value),
                    decoration: InputDecoration(
                      hintText: strings.text('searchHint'),
                      prefixIcon: const Icon(Icons.search_rounded),
                      suffixIcon: _query.isEmpty
                          ? null
                          : IconButton(
                              tooltip: strings.text('cancel'),
                              onPressed: () => setState(() => _query = ''),
                              icon: const Icon(Icons.close_rounded),
                            ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  SizedBox(
                    height: 42,
                    child: ListView(
                      scrollDirection: Axis.horizontal,
                      children: [
                        _CategoryFilterChip(
                          label: strings.text('all'),
                          selected: _selectedCategory == null,
                          onTap: () => setState(() => _selectedCategory = null),
                        ),
                        ...catalogCategories.map((category) {
                          final suffix = _categoryTitleSuffix(category.id);
                          return _CategoryFilterChip(
                            label: strings.text('cat$suffix'),
                            selected: _selectedCategory == category.id,
                            onTap: () => setState(
                              () => _selectedCategory = category.id,
                            ),
                          );
                        }),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          '${strings.text('allProducts')} · ${products.length}',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                      ),
                      TextButton.icon(
                        onPressed: () => setState(
                          () => _ascendingPrice = !_ascendingPrice,
                        ),
                        icon: const Icon(Icons.swap_vert_rounded),
                        label: Text(strings.text(
                          _ascendingPrice ? 'sortByPrice' : 'sortRecommended',
                        )),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  if (products.isEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 40),
                      child: StoreEmptyState(
                        title: strings.text('noResults'),
                        description: strings.text('noProducts'),
                        icon: Icons.search_off_rounded,
                      ),
                    )
                  else
                    GridView.builder(
                      itemCount: products.length,
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                        crossAxisCount: wide
                            ? 4
                            : constraints.maxWidth > 500
                                ? 3
                                : 2,
                        crossAxisSpacing: 12,
                        mainAxisSpacing: 12,
                        mainAxisExtent: 300,
                      ),
                      itemBuilder: (context, index) {
                        final product = products[index];
                        return StoreProductCard(
                          product: product,
                          controller: widget.controller,
                          onTap: () => openProduct(
                            context,
                            widget.controller,
                            product,
                          ),
                        );
                      },
                    ),
                  const SizedBox(height: 20),
                  Text(
                    strings.text('stockDemo'),
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  String _categoryTitleSuffix(String id) => switch (id) {
        'cables' => 'Cables',
        'breakers' => 'Breakers',
        'lighting' => 'Lighting',
        'solar' => 'Solar',
        'switches' => 'Switches',
        'pumps' => 'Pumps',
        'tools' => 'Tools',
        'custom' => 'Custom',
        _ => 'Cables',
      };
}

class _CategoryFilterChip extends StatelessWidget {
  const _CategoryFilterChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsetsDirectional.only(end: 8),
      child: ChoiceChip(
        label: Text(label),
        selected: selected,
        onSelected: (_) => onTap(),
        showCheckmark: false,
      ),
    );
  }
}
