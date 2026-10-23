import 'package:flutter/material.dart';

import '../l10n/store_strings.dart';
import '../models/catalog.dart';
import '../models/store_controller.dart';
import '../theme/app_colors.dart';

class StoreSectionTitle extends StatelessWidget {
  const StoreSectionTitle({
    required this.title,
    this.actionLabel,
    this.onAction,
    super.key,
  });

  final String title;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(title, style: Theme.of(context).textTheme.titleLarge),
        ),
        if (actionLabel != null)
          TextButton(onPressed: onAction, child: Text(actionLabel!)),
      ],
    );
  }
}

class StoreProductCard extends StatelessWidget {
  const StoreProductCard({
    required this.product,
    required this.controller,
    required this.onTap,
    this.compact = false,
    super.key,
  });

  final CatalogProduct product;
  final StoreController controller;
  final VoidCallback onTap;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    final languageCode = Localizations.localeOf(context).languageCode;
    final isFavorite = controller.favorites.contains(product.id);
    final stock = controller.stockFor(product.id);
    final isUnavailable = stock == 0 && !product.quoteOnly;
    final price = formatLocalizedDzd(product.price, languageCode);

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(20),
      child: Container(
        width: compact ? 196 : null,
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: Theme.of(context).dividerColor),
        ),
        clipBehavior: Clip.antiAlias,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SizedBox(
              height: compact ? 126 : 150,
              child: Stack(
                children: [
                  Positioned.fill(
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          begin: AlignmentDirectional.topStart,
                          end: AlignmentDirectional.bottomEnd,
                          colors: [
                            product.color.withValues(alpha: 0.20),
                            product.color.withValues(alpha: 0.06),
                          ],
                        ),
                      ),
                      child: Icon(
                        product.icon,
                        size: 58,
                        color: product.color,
                      ),
                    ),
                  ),
                  PositionedDirectional(
                    top: 8,
                    end: 8,
                    child: Material(
                      color: Theme.of(context)
                          .colorScheme
                          .surface
                          .withValues(alpha: 0.92),
                      shape: const CircleBorder(),
                      child: IconButton(
                        tooltip: strings.text('favorite'),
                        visualDensity: VisualDensity.compact,
                        onPressed: () => controller.toggleFavorite(product.id),
                        icon: Icon(
                          isFavorite
                              ? Icons.favorite_rounded
                              : Icons.favorite_border_rounded,
                          color: isFavorite
                              ? AppColors.outOfStock
                              : Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ),
                  ),
                  if (product.badge != null)
                    PositionedDirectional(
                      top: 10,
                      start: 10,
                      child: _ProductBadge(label: strings.text(product.badge!)),
                    ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsetsDirectional.fromSTEB(12, 10, 12, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    product.brand,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    product.name(languageCode),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          product.quoteOnly
                              ? strings.text('requestQuote')
                              : price,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context)
                              .textTheme
                              .titleSmall
                              ?.copyWith(
                                color: Theme.of(context).colorScheme.primary,
                                fontWeight: FontWeight.w800,
                              ),
                        ),
                      ),
                      if (!product.quoteOnly)
                        Icon(
                          isUnavailable
                              ? Icons.remove_circle_outline_rounded
                              : Icons.add_circle_rounded,
                          color: isUnavailable
                              ? AppColors.outOfStock
                              : AppColors.primaryBright,
                        ),
                    ],
                  ),
                  const SizedBox(height: 5),
                  Text(
                    product.quoteOnly
                        ? strings.text('requestQuote')
                        : isUnavailable
                            ? strings.text('outOfStock')
                            : stock < 10
                                ? strings.text('lowStock')
                                : strings.text('available'),
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: product.quoteOnly || stock >= 10
                              ? AppColors.available
                              : stock == 0
                                  ? AppColors.outOfStock
                                  : AppColors.lowStock,
                        ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ProductBadge extends StatelessWidget {
  const _ProductBadge({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsetsDirectional.fromSTEB(9, 5, 9, 5),
      decoration: BoxDecoration(
        color: AppColors.accent,
        borderRadius: BorderRadius.circular(99),
      ),
      child: Text(
        label,
        style: const TextStyle(
          color: AppColors.primary,
          fontSize: 11,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}

class CatalogCategoryChip extends StatelessWidget {
  const CatalogCategoryChip({
    required this.category,
    required this.label,
    required this.selected,
    required this.onTap,
    super.key,
  });

  final CatalogCategory category;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return FilterChip(
      selected: selected,
      onSelected: (_) => onTap(),
      avatar: Icon(category.icon, size: 18, color: category.color),
      label: Text(label),
      showCheckmark: false,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(99)),
    );
  }
}

class StoreEmptyState extends StatelessWidget {
  const StoreEmptyState({
    required this.title,
    required this.description,
    this.icon = Icons.shopping_bag_outlined,
    this.actionLabel,
    this.onAction,
    super.key,
  });

  final String title;
  final String description;
  final IconData icon;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 76,
              height: 76,
              decoration: BoxDecoration(
                color: AppColors.primaryBright.withValues(alpha: 0.10),
                borderRadius: BorderRadius.circular(24),
              ),
              child: Icon(
                icon,
                size: 36,
                color: AppColors.primaryBright,
              ),
            ),
            const SizedBox(height: 18),
            Text(title, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            Text(
              description,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
            if (actionLabel != null) ...[
              const SizedBox(height: 18),
              FilledButton(
                onPressed: onAction,
                child: Text(actionLabel!),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class CategoryGrid extends StatelessWidget {
  const CategoryGrid({
    required this.onSelected,
    this.horizontal = false,
    super.key,
  });

  final ValueChanged<String> onSelected;
  final bool horizontal;

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    final names = {
      'cables': strings.text('catCables'),
      'breakers': strings.text('catBreakers'),
      'lighting': strings.text('catLighting'),
      'solar': strings.text('catSolar'),
      'switches': strings.text('catSwitches'),
      'pumps': strings.text('catPumps'),
      'tools': strings.text('catTools'),
      'custom': strings.text('catCustom'),
    };

    final children = catalogCategories
        .map((category) => _CategoryTile(
              category: category,
              label: names[category.id] ?? category.id,
              horizontal: horizontal,
              onTap: () => onSelected(category.id),
            ))
        .toList();

    if (horizontal) {
      return SizedBox(
        height: 105,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          itemCount: children.length,
          separatorBuilder: (_, __) => const SizedBox(width: 10),
          itemBuilder: (context, index) => children[index],
        ),
      );
    }

    return LayoutBuilder(
      builder: (context, constraints) {
        final count = constraints.maxWidth > 800
            ? 4
            : constraints.maxWidth > 500
                ? 3
                : 2;
        return GridView.count(
          crossAxisCount: count,
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
          childAspectRatio: 1.55,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          children: children,
        );
      },
    );
  }
}

class _CategoryTile extends StatelessWidget {
  const _CategoryTile({
    required this.category,
    required this.label,
    required this.horizontal,
    required this.onTap,
  });

  final CatalogCategory category;
  final String label;
  final bool horizontal;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: horizontal ? 88 : null,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(18),
        child: Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: Theme.of(context).dividerColor),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: category.color.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(category.icon, color: category.color),
              ),
              const SizedBox(height: 6),
              Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
