import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

enum AppStockStatus { available, outOfStock, lowStock }

class AppStatusBadge extends StatelessWidget {
  const AppStatusBadge({
    required this.label,
    required this.status,
    super.key,
  });

  final String label;
  final AppStockStatus status;

  @override
  Widget build(BuildContext context) {
    final color = switch (status) {
      AppStockStatus.available => AppColors.available,
      AppStockStatus.outOfStock => AppColors.outOfStock,
      AppStockStatus.lowStock => AppColors.lowStock,
    };

    return Container(
      padding: const EdgeInsetsDirectional.fromSTEB(10, 6, 10, 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 7,
            height: 7,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 7),
          Text(
            label,
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: color,
                  fontWeight: FontWeight.w600,
                ),
          ),
        ],
      ),
    );
  }
}
