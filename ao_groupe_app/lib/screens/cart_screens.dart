import 'package:flutter/material.dart';

import '../l10n/store_strings.dart';
import '../models/algeria_wilaya.dart';
import '../models/store_controller.dart';
import '../theme/app_colors.dart';
import '../widgets/store_components.dart';

class CartScreen extends StatefulWidget {
  const CartScreen({
    required this.controller,
    required this.onBrowse,
    super.key,
  });

  final StoreController controller;
  final VoidCallback onBrowse;

  @override
  State<CartScreen> createState() => _CartScreenState();
}

class _CartScreenState extends State<CartScreen> {
  final _couponController = TextEditingController();
  bool _couponApplied = false;

  @override
  void dispose() {
    _couponController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    final languageCode = Localizations.localeOf(context).languageCode;
    return AnimatedBuilder(
      animation: widget.controller,
      builder: (context, _) {
        final items = widget.controller.cart.entries.toList();
        if (items.isEmpty) {
          return StoreEmptyState(
            title: strings.text('emptyCart'),
            description: strings.text('emptyCartBody'),
            actionLabel: strings.text('continueShopping'),
            onAction: widget.onBrowse,
          );
        }

        return LayoutBuilder(
          builder: (context, constraints) {
            final wide = constraints.maxWidth > 850;
            final content = _CartSummary(
              controller: widget.controller,
              strings: strings,
              languageCode: languageCode,
              couponController: _couponController,
              couponApplied: _couponApplied,
              onApplyCoupon: () {
                final valid =
                    _couponController.text.trim().toUpperCase() == 'AO5';
                setState(() => _couponApplied = valid);
                if (!valid) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text(strings.text('couponInvalid'))),
                  );
                }
              },
            );
            return SingleChildScrollView(
              padding: const EdgeInsetsDirectional.fromSTEB(18, 10, 18, 26),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 1120),
                  child: wide
                      ? Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(
                              flex: 3,
                              child: _CartItems(
                                items: items,
                                controller: widget.controller,
                                languageCode: languageCode,
                                strings: strings,
                              ),
                            ),
                            const SizedBox(width: 18),
                            Expanded(child: content),
                          ],
                        )
                      : Column(
                          children: [
                            _CartItems(
                              items: items,
                              controller: widget.controller,
                              languageCode: languageCode,
                              strings: strings,
                            ),
                            const SizedBox(height: 16),
                            content,
                          ],
                        ),
                ),
              ),
            );
          },
        );
      },
    );
  }
}

class _CartItems extends StatelessWidget {
  const _CartItems({
    required this.items,
    required this.controller,
    required this.languageCode,
    required this.strings,
  });

  final List<MapEntry<String, int>> items;
  final StoreController controller;
  final String languageCode;
  final StoreStrings strings;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: items.map((entry) {
        final product = productById(entry.key);
        final quantity = entry.value;
        return Dismissible(
          key: ValueKey(product.id),
          direction: DismissDirection.endToStart,
          onDismissed: (_) => controller.removeFromCart(product.id),
          background: Container(
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsetsDirectional.only(end: 18),
            alignment: AlignmentDirectional.centerEnd,
            decoration: BoxDecoration(
              color: AppColors.outOfStock,
              borderRadius: BorderRadius.circular(20),
            ),
            child: IconButton(
              onPressed: null,
              tooltip: strings.text('remove'),
              icon: const Icon(Icons.delete_outline, color: Colors.white),
            ),
          ),
          child: Container(
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surface,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: Theme.of(context).dividerColor),
            ),
            child: Row(
              children: [
                Container(
                  width: 64,
                  height: 64,
                  decoration: BoxDecoration(
                    color: product.color.withValues(alpha: 0.14),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Icon(product.icon, color: product.color, size: 30),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        product.name(languageCode),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                      const SizedBox(height: 5),
                      Text(
                        formatLocalizedDzd(
                            product.priceForQuantity(quantity) * quantity,
                            languageCode),
                        style: Theme.of(context).textTheme.labelLarge?.copyWith(
                              color: Theme.of(context).colorScheme.primary,
                            ),
                      ),
                      const SizedBox(height: 8),
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          _QuantityButton(
                            icon: Icons.remove_rounded,
                            onPressed: () => controller.setQuantity(
                              product.id,
                              quantity - 1,
                            ),
                          ),
                          SizedBox(
                            width: 34,
                            child: Text(
                              '$quantity',
                              textAlign: TextAlign.center,
                              style: Theme.of(context).textTheme.labelLarge,
                            ),
                          ),
                          _QuantityButton(
                            icon: Icons.add_rounded,
                            onPressed:
                                quantity < controller.stockFor(product.id)
                                    ? () => controller.setQuantity(
                                          product.id,
                                          quantity + 1,
                                        )
                                    : null,
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                IconButton(
                  tooltip: strings.text('remove'),
                  onPressed: () => controller.removeFromCart(product.id),
                  icon: const Icon(Icons.delete_outline_rounded),
                ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }
}

class _QuantityButton extends StatelessWidget {
  const _QuantityButton({required this.icon, required this.onPressed});

  final IconData icon;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 30,
      height: 30,
      child: IconButton.filledTonal(
        padding: EdgeInsets.zero,
        visualDensity: VisualDensity.compact,
        onPressed: onPressed,
        icon: Icon(icon, size: 17),
      ),
    );
  }
}

class _CartSummary extends StatefulWidget {
  const _CartSummary({
    required this.controller,
    required this.strings,
    required this.languageCode,
    required this.couponController,
    required this.couponApplied,
    required this.onApplyCoupon,
  });

  final StoreController controller;
  final StoreStrings strings;
  final String languageCode;
  final TextEditingController couponController;
  final bool couponApplied;
  final VoidCallback onApplyCoupon;

  @override
  State<_CartSummary> createState() => _CartSummaryState();
}

class _CartSummaryState extends State<_CartSummary> {
  String _wilaya = '16';

  @override
  Widget build(BuildContext context) {
    final strings = widget.strings;
    final controller = widget.controller;
    final languageCode = widget.languageCode;
    final delivery = controller.deliveryFee(_wilaya);
    final discount = widget.couponApplied ? controller.subtotal * 5 ~/ 100 : 0;

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        border: Border.all(color: Theme.of(context).dividerColor),
        borderRadius: BorderRadius.circular(22),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(strings.text('cart'),
              style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 14),
          TextField(
            controller: widget.couponController,
            textCapitalization: TextCapitalization.characters,
            decoration: InputDecoration(
              labelText: strings.text('coupon'),
              hintText: 'AO5',
              suffixIcon: TextButton(
                onPressed: widget.onApplyCoupon,
                child: Text(strings.text('apply')),
              ),
            ),
          ),
          if (widget.couponApplied)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                strings.text('couponApplied'),
                style: const TextStyle(color: AppColors.available),
              ),
            ),
          const SizedBox(height: 16),
          DropdownButtonFormField<String>(
            initialValue: _wilaya,
            decoration: InputDecoration(labelText: strings.text('wilaya')),
            items: algerianWilayas
                .map((wilaya) => DropdownMenuItem(
                      value: wilaya.code,
                      child: Text(wilaya.label(languageCode)),
                    ))
                .toList(),
            onChanged: (value) {
              if (value != null) setState(() => _wilaya = value);
            },
          ),
          const SizedBox(height: 18),
          _SummaryRow(
            label: strings.text('subtotal'),
            value: formatLocalizedDzd(controller.subtotal, languageCode),
          ),
          const SizedBox(height: 8),
          _SummaryRow(
            label: strings.text('shipping'),
            value: delivery == 0
                ? strings.text('free')
                : formatLocalizedDzd(delivery, languageCode),
          ),
          if (discount > 0) ...[
            const SizedBox(height: 8),
            _SummaryRow(
              label: strings.text('discount'),
              value: '-${formatLocalizedDzd(discount, languageCode)}',
              highlight: true,
            ),
          ],
          const Divider(height: 28),
          _SummaryRow(
            label: strings.text('total'),
            value: formatLocalizedDzd(
              controller.totalFor(_wilaya, couponApplied: widget.couponApplied),
              languageCode,
            ),
            bold: true,
          ),
          const SizedBox(height: 8),
          Text(
            strings.text('freeDeliveryAt'),
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 18),
          FilledButton.icon(
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => CheckoutScreen(
                  controller: controller,
                  initialWilaya: _wilaya,
                  couponApplied: widget.couponApplied,
                ),
              ),
            ),
            icon: const Icon(Icons.arrow_forward_rounded),
            label: Text(strings.text('checkout')),
          ),
          const SizedBox(height: 8),
          Text(
            strings.text('deliveryEstimate'),
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _SummaryRow extends StatelessWidget {
  const _SummaryRow({
    required this.label,
    required this.value,
    this.bold = false,
    this.highlight = false,
  });

  final String label;
  final String value;
  final bool bold;
  final bool highlight;

  @override
  Widget build(BuildContext context) {
    final textStyle = Theme.of(context).textTheme.bodyMedium?.copyWith(
          fontWeight: bold ? FontWeight.w800 : FontWeight.w500,
          color: highlight ? AppColors.available : null,
        );
    return Row(
      children: [
        Expanded(child: Text(label, style: textStyle)),
        Text(value, style: textStyle),
      ],
    );
  }
}

class CheckoutScreen extends StatefulWidget {
  const CheckoutScreen({
    required this.controller,
    required this.initialWilaya,
    required this.couponApplied,
    super.key,
  });

  final StoreController controller;
  final String initialWilaya;
  final bool couponApplied;

  @override
  State<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends State<CheckoutScreen> {
  final _formKey = GlobalKey<FormState>();
  final _addressController = TextEditingController();
  late String _wilaya = widget.initialWilaya;
  String _payment = 'cash';
  final _nameController = TextEditingController();
  final _phoneController = TextEditingController();

  @override
  void dispose() {
    _addressController.dispose();
    _nameController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    final languageCode = Localizations.localeOf(context).languageCode;
    return Scaffold(
      appBar: AppBar(title: Text(strings.text('checkout'))),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsetsDirectional.fromSTEB(20, 8, 20, 30),
          children: [
            _CheckoutStepHeader(strings: strings),
            const SizedBox(height: 18),
            Text(strings.text('address'),
                style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _wilaya,
              decoration: InputDecoration(
                labelText: strings.text('selectWilaya'),
              ),
              items: algerianWilayas
                  .map((wilaya) => DropdownMenuItem(
                        value: wilaya.code,
                        child: Text(
                            '${wilaya.code} · ${wilaya.label(languageCode)}'),
                      ))
                  .toList(),
              onChanged: (value) {
                if (value != null) setState(() => _wilaya = value);
              },
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _nameController,
              textCapitalization: TextCapitalization.words,
              decoration: InputDecoration(
                labelText: strings.text('customerName'),
              ),
              validator: (value) => (value == null || value.trim().length < 2)
                  ? strings.text('requiredField')
                  : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _phoneController,
              keyboardType: TextInputType.phone,
              decoration: InputDecoration(
                labelText: strings.text('phone'),
                prefixIcon: const Icon(Icons.phone_outlined),
              ),
              validator: (value) {
                final phone = (value ?? '').replaceAll(RegExp(r'[\s-]'), '');
                return RegExp(r'^(0[567]\d{8}|\+213[567]\d{8})$')
                        .hasMatch(phone)
                    ? null
                    : strings.text('invalidPhone');
              },
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _addressController,
              minLines: 2,
              maxLines: 3,
              decoration: InputDecoration(
                labelText: strings.text('address'),
                hintText: strings.text('addressHint'),
                alignLabelWithHint: true,
              ),
              validator: (value) => (value == null || value.trim().length < 6)
                  ? strings.text('requiredField')
                  : null,
            ),
            const SizedBox(height: 22),
            Text(strings.text('payment'),
                style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            RadioGroup<String>(
              groupValue: _payment,
              onChanged: (value) {
                if (value != null) setState(() => _payment = value);
              },
              child: Column(
                children: [
                  _PaymentOption(
                    value: 'cash',
                    title: strings.text('cash'),
                    icon: Icons.payments_outlined,
                    enabled: true,
                  ),
                  _PaymentOption(
                    value: 'ccp',
                    title: strings.text('ccp'),
                    icon: Icons.account_balance_outlined,
                    enabled: false,
                  ),
                  _PaymentOption(
                    value: 'edahabia',
                    title: strings.text('edahabia'),
                    icon: Icons.credit_card_rounded,
                    enabled: false,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 8),
            Text(strings.text('signInRequired'),
                style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 18),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    _SummaryRow(
                      label: strings.text('subtotal'),
                      value: formatLocalizedDzd(
                        widget.controller.subtotal,
                        languageCode,
                      ),
                    ),
                    const SizedBox(height: 10),
                    _SummaryRow(
                      label: strings.text('shipping'),
                      value: formatLocalizedDzd(
                        widget.controller.deliveryFee(_wilaya),
                        languageCode,
                      ),
                    ),
                    if (widget.couponApplied) ...[
                      const SizedBox(height: 10),
                      _SummaryRow(
                        label: strings.text('discount'),
                        value:
                            '-${formatLocalizedDzd(widget.controller.subtotal * 5 ~/ 100, languageCode)}',
                        highlight: true,
                      ),
                    ],
                    const Divider(height: 24),
                    _SummaryRow(
                      label: strings.text('total'),
                      value: formatLocalizedDzd(
                        widget.controller.totalFor(
                          _wilaya,
                          couponApplied: widget.couponApplied,
                        ),
                        languageCode,
                      ),
                      bold: true,
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 18),
            FilledButton.icon(
              onPressed: () {
                if (!_formKey.currentState!.validate()) return;
                final order = widget.controller.placeOrder(
                  wilaya: _wilaya,
                  paymentMethod: _payment,
                  customerName: _nameController.text.trim(),
                  phone: _phoneController.text.trim(),
                  address: _addressController.text.trim(),
                  couponApplied: widget.couponApplied,
                );
                Navigator.of(context).pushReplacement(
                  MaterialPageRoute<void>(
                    builder: (_) => OrderConfirmationScreen(
                      controller: widget.controller,
                      order: order,
                    ),
                  ),
                );
              },
              icon: const Icon(Icons.lock_outline_rounded),
              label: Text(strings.text('placeOrder')),
            ),
            const SizedBox(height: 10),
            Text(
              strings.text('orderPlacedBody'),
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}

class _CheckoutStepHeader extends StatelessWidget {
  const _CheckoutStepHeader({required this.strings});

  final StoreStrings strings;

  @override
  Widget build(BuildContext context) {
    final labels = [
      strings.text('address'),
      strings.text('shipping'),
      strings.text('payment'),
      strings.text('confirm'),
    ];
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: List.generate(labels.length, (index) {
        return Chip(
          avatar: CircleAvatar(
            radius: 11,
            backgroundColor: index == 0
                ? AppColors.primaryBright
                : AppColors.primaryBright.withValues(alpha: 0.10),
            foregroundColor:
                index == 0 ? Colors.white : AppColors.primaryBright,
            child: Text('${index + 1}', style: const TextStyle(fontSize: 11)),
          ),
          label: Text(labels[index]),
          backgroundColor: index == 0
              ? AppColors.primaryBright.withValues(alpha: 0.10)
              : null,
          side: BorderSide.none,
        );
      }),
    );
  }
}

class _PaymentOption extends StatelessWidget {
  const _PaymentOption({
    required this.value,
    required this.title,
    required this.icon,
    required this.enabled,
  });

  final String value;
  final String title;
  final IconData icon;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: enabled ? 1 : 0.55,
      child: RadioListTile<String>(
        value: value,
        enabled: enabled,
        title: Text(title),
        secondary: Icon(icon),
        contentPadding: EdgeInsets.zero,
        dense: true,
      ),
    );
  }
}

class OrderConfirmationScreen extends StatelessWidget {
  const OrderConfirmationScreen({
    required this.controller,
    required this.order,
    super.key,
  });

  final StoreController controller;
  final DemoOrder order;

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    final languageCode = Localizations.localeOf(context).languageCode;
    return Scaffold(
      appBar: AppBar(title: Text(strings.text('orderPlaced'))),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: Column(
              children: [
                Container(
                  width: 94,
                  height: 94,
                  decoration: BoxDecoration(
                    color: AppColors.available.withValues(alpha: 0.12),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(
                    Icons.check_rounded,
                    size: 52,
                    color: AppColors.available,
                  ),
                ),
                const SizedBox(height: 20),
                Text(
                  strings.text('orderPlaced'),
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
                const SizedBox(height: 8),
                Text(
                  strings.text('orderPlacedBody'),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 20),
                Card(
                  child: ListTile(
                    title: Text(strings.text('orderNumber')),
                    subtitle: Text(order.number),
                    trailing: Text(
                      formatLocalizedDzd(order.total, languageCode),
                      style: Theme.of(context).textTheme.titleSmall,
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                FilledButton.icon(
                  onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => OrderTrackingScreen(
                        controller: controller,
                        order: order,
                      ),
                    ),
                  ),
                  icon: const Icon(Icons.local_shipping_outlined),
                  label: Text(strings.text('trackOrder')),
                ),
                const SizedBox(height: 10),
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: Text(strings.text('continueShopping')),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class OrderTrackingScreen extends StatelessWidget {
  const OrderTrackingScreen({
    required this.controller,
    required this.order,
    super.key,
  });

  final StoreController controller;
  final DemoOrder order;

  @override
  Widget build(BuildContext context) {
    final strings = StoreStrings.of(context);
    final languageCode = Localizations.localeOf(context).languageCode;
    final statuses = [
      strings.text('statusReceived'),
      strings.text('statusConfirmed'),
      strings.text('statusPreparing'),
      strings.text('statusShipped'),
      strings.text('statusDelivered'),
    ];
    return Scaffold(
      appBar: AppBar(title: Text(strings.text('trackOrder'))),
      body: ListView(
        padding: const EdgeInsets.all(22),
        children: [
          Card(
            child: ListTile(
              leading: const Icon(Icons.receipt_long_outlined),
              title: Text('${strings.text('orderNumber')} ${order.number}'),
              subtitle: Text(
                '${formatLocalizedDzd(order.total, languageCode)} · ${strings.text('orderStatus')}',
              ),
            ),
          ),
          const SizedBox(height: 20),
          ...List.generate(statuses.length, (index) {
            final complete = index < 2;
            return _TimelineStep(
              title: statuses[index],
              complete: complete,
              last: index == statuses.length - 1,
            );
          }),
          const SizedBox(height: 12),
          Text(
            strings.text('orderHistoryDisclaimer'),
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _TimelineStep extends StatelessWidget {
  const _TimelineStep({
    required this.title,
    required this.complete,
    required this.last,
  });

  final String title;
  final bool complete;
  final bool last;

  @override
  Widget build(BuildContext context) {
    final color = complete
        ? AppColors.available
        : Theme.of(context).colorScheme.outlineVariant;
    return SizedBox(
      height: 66,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 30,
            child: Column(
              children: [
                Icon(
                  complete ? Icons.check_circle : Icons.circle_outlined,
                  color: color,
                  size: 22,
                ),
                if (!last)
                  Expanded(
                    child: Container(
                        width: 2, color: color.withValues(alpha: 0.4)),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Text(
              title,
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    color: complete
                        ? Theme.of(context).colorScheme.onSurface
                        : Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
          ),
        ],
      ),
    );
  }
}
