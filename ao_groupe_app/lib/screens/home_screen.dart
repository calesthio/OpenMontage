import 'package:flutter/material.dart';

import '../l10n/store_strings.dart';
import '../models/catalog.dart';
import '../models/store_controller.dart';
import '../theme/app_colors.dart';
import '../widgets/store_components.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({
    required this.controller,
    required this.onOpenTab,
    required this.onCategorySelected,
    super.key,
  });

  final StoreController controller;
  final ValueChanged<int> onOpenTab;
  final ValueChanged<String> onCategorySelected;

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    final popular =
        catalogProducts.where((product) => product.isPopular).toList();
    final newArrivals =
        catalogProducts.where((product) => product.isNew).toList();

    return LayoutBuilder(
      builder: (context, constraints) {
        final horizontalPadding = constraints.maxWidth > 900 ? 32.0 : 20.0;
        return SingleChildScrollView(
          padding: EdgeInsetsDirectional.fromSTEB(
            horizontalPadding,
            12,
            horizontalPadding,
            36,
          ),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1120),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _SearchEntry(
                    hint: strings.text('searchHint'),
                    onTap: () => onOpenTab(2),
                  ),
                  const SizedBox(height: 18),
                  _WelcomeHero(
                    title: strings.text('welcome'),
                    body: strings.text('welcomeBody'),
                    action: strings.text('shopNow'),
                    onTap: () => onOpenTab(1),
                  ),
                  const SizedBox(height: 14),
                  _DeliveryStrip(label: strings.text('deliveryPromo')),
                  const SizedBox(height: 26),
                  StoreSectionTitle(
                    title: strings.text('moreCategories'),
                    actionLabel: strings.text('showMore'),
                    onAction: () => onOpenTab(1),
                  ),
                  const SizedBox(height: 10),
                  CategoryGrid(
                    horizontal: true,
                    onSelected: onCategorySelected,
                  ),
                  const SizedBox(height: 26),
                  StoreSectionTitle(
                    title: strings.text('bestSellers'),
                    actionLabel: strings.text('allProducts'),
                    onAction: () => onOpenTab(1),
                  ),
                  const SizedBox(height: 10),
                  _ProductRail(
                    products: popular,
                    controller: controller,
                  ),
                  const SizedBox(height: 25),
                  _PromoTiles(
                    solar: strings.text('featuredSolar'),
                    lighting: strings.text('featuredLighting'),
                    onSolarTap: () => onCategorySelected('solar'),
                    onLightingTap: () => onCategorySelected('lighting'),
                  ),
                  const SizedBox(height: 25),
                  StoreSectionTitle(
                    title: strings.text('newArrivals'),
                    actionLabel: strings.text('allProducts'),
                    onAction: () => onOpenTab(1),
                  ),
                  const SizedBox(height: 10),
                  _ProductRail(
                    products: newArrivals,
                    controller: controller,
                  ),
                  const SizedBox(height: 18),
                  Text(
                    strings.text('stockDemo'),
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

class _SearchEntry extends StatelessWidget {
  const _SearchEntry({required this.hint, required this.onTap});

  final String hint;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Theme.of(context).colorScheme.surface,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 15),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: Theme.of(context).dividerColor),
          ),
          child: Row(
            children: [
              const Icon(Icons.search_rounded, color: AppColors.primaryBright),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  hint,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                ),
              ),
              const Icon(Icons.qr_code_scanner_rounded, size: 21),
            ],
          ),
        ),
      ),
    );
  }
}

class _WelcomeHero extends StatelessWidget {
  const _WelcomeHero({
    required this.title,
    required this.body,
    required this.action,
    required this.onTap,
  });

  final String title;
  final String body;
  final String action;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final isWide = MediaQuery.sizeOf(context).width >= 650;
    return Container(
      padding: EdgeInsets.all(isWide ? 30 : 22),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: AlignmentDirectional.topStart,
          end: AlignmentDirectional.bottomEnd,
          colors: [AppColors.primary, AppColors.primaryBright],
        ),
        borderRadius: BorderRadius.circular(26),
      ),
      child: Row(
        children: [
          Expanded(
            flex: 4,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsetsDirectional.fromSTEB(10, 6, 10, 6),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.14),
                    borderRadius: BorderRadius.circular(99),
                  ),
                  child: Text(
                    'AO GROUPE  ·  DZ',
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: Colors.white,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 1,
                        ),
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  title,
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w800,
                        height: 1.2,
                      ),
                ),
                const SizedBox(height: 8),
                Text(
                  body,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Colors.white.withValues(alpha: 0.85),
                        height: 1.5,
                      ),
                ),
                const SizedBox(height: 18),
                FilledButton.icon(
                  onPressed: onTap,
                  style: FilledButton.styleFrom(
                    backgroundColor: AppColors.accent,
                    foregroundColor: AppColors.primary,
                  ),
                  icon: const Icon(Icons.arrow_forward_rounded),
                  label: Text(action),
                ),
              ],
            ),
          ),
          if (isWide) ...[
            const SizedBox(width: 20),
            Expanded(
              flex: 2,
              child: Container(
                height: 170,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.10),
                  borderRadius: BorderRadius.circular(22),
                ),
                child: const Icon(
                  Icons.bolt_rounded,
                  size: 112,
                  color: AppColors.accent,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _DeliveryStrip extends StatelessWidget {
  const _DeliveryStrip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: AppColors.accent.withValues(alpha: 0.16),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          const Icon(Icons.local_shipping_outlined, color: AppColors.primary),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              label,
              style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: AppColors.primary,
                  ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ProductRail extends StatelessWidget {
  const _ProductRail({
    required this.products,
    required this.controller,
  });

  final List<CatalogProduct> products;
  final StoreController controller;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 292,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: products.length,
        separatorBuilder: (_, __) => const SizedBox(width: 12),
        itemBuilder: (context, index) {
          final product = products[index];
          return StoreProductCard(
            product: product,
            controller: controller,
            compact: true,
            onTap: () => openProduct(context, controller, product),
          );
        },
      ),
    );
  }
}

class _PromoTiles extends StatelessWidget {
  const _PromoTiles({
    required this.solar,
    required this.lighting,
    required this.onSolarTap,
    required this.onLightingTap,
  });

  final String solar;
  final String lighting;
  final VoidCallback onSolarTap;
  final VoidCallback onLightingTap;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth > 620;
        final children = [
          _PromoTile(
            title: solar,
            icon: Icons.solar_power_rounded,
            colors: const [Color(0xFF166534), Color(0xFF22C55E)],
            onTap: onSolarTap,
          ),
          _PromoTile(
            title: lighting,
            icon: Icons.lightbulb_outline_rounded,
            colors: const [Color(0xFF92400E), Color(0xFFF59E0B)],
            onTap: onLightingTap,
          ),
        ];
        if (wide) {
          return Row(
            children: [
              Expanded(child: children[0]),
              const SizedBox(width: 12),
              Expanded(child: children[1]),
            ],
          );
        }
        return Column(
          children: [
            children[0],
            const SizedBox(height: 12),
            children[1],
          ],
        );
      },
    );
  }
}

class _PromoTile extends StatelessWidget {
  const _PromoTile({
    required this.title,
    required this.icon,
    required this.colors,
    required this.onTap,
  });

  final String title;
  final IconData icon;
  final List<Color> colors;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: colors.first,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Container(
          height: 118,
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: AlignmentDirectional.topStart,
              end: AlignmentDirectional.bottomEnd,
              colors: colors,
            ),
            borderRadius: BorderRadius.circular(20),
          ),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ),
              Icon(icon, size: 46, color: Colors.white.withValues(alpha: 0.88)),
            ],
          ),
        ),
      ),
    );
  }
}

void openProduct(
  BuildContext context,
  StoreController controller,
  CatalogProduct product,
) {
  Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => ProductDetailsScreen(
        controller: controller,
        product: product,
      ),
    ),
  );
}

class ProductDetailsScreen extends StatefulWidget {
  const ProductDetailsScreen({
    required this.controller,
    required this.product,
    super.key,
  });

  final StoreController controller;
  final CatalogProduct product;

  @override
  State<ProductDetailsScreen> createState() => _ProductDetailsScreenState();
}

class _ProductDetailsScreenState extends State<ProductDetailsScreen> {
  int _quantity = 1;

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    final languageCode = Localizations.localeOf(context).languageCode;
    final product = widget.product;
    final specs = localizedSpecification(product.specification, languageCode);
    final stock = widget.controller.stockFor(product.id);
    final isAvailable = stock > 0 || product.quoteOnly;

    return Scaffold(
      appBar: AppBar(
        title: Text(strings.text('productDetails')),
        actions: [
          IconButton(
            tooltip: strings.text('favorite'),
            onPressed: () {
              widget.controller.toggleFavorite(product.id);
              setState(() {});
            },
            icon: Icon(
              widget.controller.favorites.contains(product.id)
                  ? Icons.favorite_rounded
                  : Icons.favorite_border_rounded,
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final wide = constraints.maxWidth > 760;
            final details = _ProductInformation(
              product: product,
              specs: specs,
              strings: strings,
              languageCode: languageCode,
              quantity: _quantity,
              stock: stock,
              onQuantityChanged: (quantity) =>
                  setState(() => _quantity = quantity),
            );
            return SingleChildScrollView(
              padding: const EdgeInsetsDirectional.fromSTEB(20, 8, 20, 100),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 1050),
                  child: wide
                      ? Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(child: _ProductArtwork(product: product)),
                            const SizedBox(width: 28),
                            Expanded(child: details),
                          ],
                        )
                      : Column(
                          children: [
                            _ProductArtwork(product: product),
                            const SizedBox(height: 22),
                            details,
                          ],
                        ),
                ),
              ),
            );
          },
        ),
      ),
      bottomNavigationBar: SafeArea(
        minimum: const EdgeInsets.all(14),
        child: FilledButton.icon(
          onPressed: isAvailable
              ? () {
                  if (product.quoteOnly) {
                    Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => QuoteRequestScreen(product: product),
                      ),
                    );
                    return;
                  }
                  widget.controller.addToCart(product.id, _quantity);
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text(strings.text('updatedLocally'))),
                  );
                }
              : null,
          icon: Icon(
            product.quoteOnly
                ? Icons.request_quote_outlined
                : Icons.add_shopping_cart_rounded,
          ),
          label: Text(
              strings.text(product.quoteOnly ? 'requestQuote' : 'addToCart')),
        ),
      ),
    );
  }
}

class _ProductArtwork extends StatelessWidget {
  const _ProductArtwork({required this.product});

  final CatalogProduct product;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      height: MediaQuery.sizeOf(context).width > 760 ? 410 : 270,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: AlignmentDirectional.topStart,
          end: AlignmentDirectional.bottomEnd,
          colors: [
            product.color.withValues(alpha: 0.24),
            product.color.withValues(alpha: 0.06),
          ],
        ),
        borderRadius: BorderRadius.circular(28),
      ),
      child: Icon(product.icon, size: 124, color: product.color),
    );
  }
}

class _ProductInformation extends StatelessWidget {
  const _ProductInformation({
    required this.product,
    required this.specs,
    required this.strings,
    required this.languageCode,
    required this.quantity,
    required this.stock,
    required this.onQuantityChanged,
  });

  final CatalogProduct product;
  final Map<String, String> specs;
  final StoreStrings strings;
  final String languageCode;
  final int quantity;
  final int stock;
  final ValueChanged<int> onQuantityChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(product.brand, style: Theme.of(context).textTheme.labelLarge),
        const SizedBox(height: 6),
        Text(
          product.name(languageCode),
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.w800,
              ),
        ),
        const SizedBox(height: 10),
        Text(
          product.quoteOnly
              ? strings.text('quoteOnly')
              : '${formatLocalizedDzd(product.priceForQuantity(quantity), languageCode)} / ${specs['pack']}',
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
                color: Theme.of(context).colorScheme.primary,
              ),
        ),
        if (quantity < 5 && !product.quoteOnly) ...[
          const SizedBox(height: 6),
          Text(
            '${strings.text('wholesale')}: ${formatLocalizedDzd(product.wholesalePrice, languageCode)} / ${specs['pack']}',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
        ],
        const SizedBox(height: 22),
        Text(strings.text('specifications'),
            style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 9),
        ...specs.entries.map((entry) => _SpecificationRow(
              label: _specificationLabel(entry.key, languageCode),
              value: entry.value,
            )),
        const SizedBox(height: 20),
        if (!product.quoteOnly) ...[
          Text(strings.text('quantity'),
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Row(
            children: [
              IconButton.filledTonal(
                tooltip: '-1',
                onPressed:
                    quantity > 1 ? () => onQuantityChanged(quantity - 1) : null,
                icon: const Icon(Icons.remove_rounded),
              ),
              SizedBox(
                width: 52,
                child: Text(
                  '$quantity',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              IconButton.filledTonal(
                tooltip: '+1',
                onPressed: quantity < stock
                    ? () => onQuantityChanged(quantity + 1)
                    : null,
                icon: const Icon(Icons.add_rounded),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  stock == 0
                      ? strings.text('outOfStock')
                      : stock < 10
                          ? strings.text('lowStock')
                          : strings.text('available'),
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        color: stock >= 10
                            ? AppColors.available
                            : stock == 0
                                ? AppColors.outOfStock
                                : AppColors.lowStock,
                      ),
                ),
              ),
            ],
          ),
        ] else ...[
          const SizedBox(height: 18),
          Text(
            strings.text('quoteOnly'),
            style: Theme.of(context).textTheme.labelLarge?.copyWith(
                  color: AppColors.primaryBright,
                ),
          ),
        ],
      ],
    );
  }

  String _specificationLabel(String key, String locale) {
    const labels = {
      'material': {
        'ar': 'العلامة / المادة',
        'fr': 'Marque / matière',
        'en': 'Brand / material'
      },
      'section': {'ar': 'المواصفة', 'fr': 'Caractéristique', 'en': 'Rating'},
      'voltage': {'ar': 'تفاصيل', 'fr': 'Détails', 'en': 'Details'},
      'pack': {'ar': 'الوحدة', 'fr': 'Unité', 'en': 'Unit'},
    };
    return labels[key]?[locale] ?? labels[key]?['ar'] ?? key;
  }
}

class _SpecificationRow extends StatelessWidget {
  const _SpecificationRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 11),
      decoration: BoxDecoration(
        border:
            Border(bottom: BorderSide(color: Theme.of(context).dividerColor)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              textAlign: TextAlign.end,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
            ),
          ),
        ],
      ),
    );
  }
}

class QuoteRequestScreen extends StatefulWidget {
  const QuoteRequestScreen({this.product, super.key});

  final CatalogProduct? product;

  @override
  State<QuoteRequestScreen> createState() => _QuoteRequestScreenState();
}

class _QuoteRequestScreenState extends State<QuoteRequestScreen> {
  final _formKey = GlobalKey<FormState>();
  final _projectController = TextEditingController();
  final _detailsController = TextEditingController();
  bool _created = false;

  @override
  void dispose() {
    _projectController.dispose();
    _detailsController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(strings.text('quoteTitle'))),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text(strings.text('quoteBody')),
          if (widget.product != null) ...[
            const SizedBox(height: 16),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(widget.product!.icon, color: widget.product!.color),
              title: Text(
                widget.product!.name(
                  Localizations.localeOf(context).languageCode,
                ),
              ),
            ),
          ],
          const SizedBox(height: 18),
          Form(
            key: _formKey,
            child: Column(
              children: [
                TextFormField(
                  controller: _projectController,
                  decoration: InputDecoration(
                    labelText: strings.text('projectName'),
                  ),
                  validator: (value) => (value == null || value.trim().isEmpty)
                      ? strings.text('requiredField')
                      : null,
                ),
                const SizedBox(height: 14),
                TextFormField(
                  controller: _detailsController,
                  minLines: 4,
                  maxLines: 7,
                  decoration: InputDecoration(
                    labelText: strings.text('projectDetails'),
                    alignLabelWithHint: true,
                  ),
                  validator: (value) => (value == null || value.trim().isEmpty)
                      ? strings.text('requiredField')
                      : null,
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: () {
              if (!_formKey.currentState!.validate()) return;
              setState(() => _created = true);
            },
            icon: const Icon(Icons.description_outlined),
            label: Text(strings.text('createQuote')),
          ),
          if (_created) ...[
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(strings.text('quoteReady'),
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    Text(_projectController.text.trim()),
                    Text(_detailsController.text.trim()),
                    if (widget.product != null)
                      Text(
                        widget.product!.name(
                          Localizations.localeOf(context).languageCode,
                        ),
                      ),
                    const SizedBox(height: 8),
                    Text(strings.text('shareUnavailable')),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
