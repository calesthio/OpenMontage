import 'package:flutter/foundation.dart';

import 'catalog.dart';

class DemoOrder {
  const DemoOrder({
    required this.number,
    required this.items,
    required this.total,
    required this.wilaya,
    required this.paymentMethod,
    required this.customerName,
    required this.phone,
    required this.address,
    required this.createdAt,
  });

  final String number;
  final Map<String, int> items;
  final int total;
  final String wilaya;
  final String paymentMethod;
  final String customerName;
  final String phone;
  final String address;
  final DateTime createdAt;
}

class StoreController extends ChangeNotifier {
  final Map<String, int> _cart = {};
  final Set<String> _favorites = {};
  final List<DemoOrder> _orders = [];
  final Map<String, int> _stockAdjustments = {};

  Map<String, int> get cart => Map.unmodifiable(_cart);
  Set<String> get favorites => Set.unmodifiable(_favorites);
  List<DemoOrder> get orders => List.unmodifiable(_orders);
  int stockFor(String productId) =>
      _stockAdjustments[productId] ?? productById(productId).stock;
  int get cartCount => _cart.values.fold(0, (sum, count) => sum + count);

  int get subtotal => _cart.entries.fold(0, (sum, entry) {
        final product = productById(entry.key);
        return sum + product.priceForQuantity(entry.value) * entry.value;
      });

  int deliveryFee(String wilayaCode) {
    if (_cart.isEmpty || subtotal >= 15000) return 0;
    return wilayaCode == '16' ? 500 : 800;
  }

  int totalFor(String wilaya, {bool couponApplied = false}) {
    final discount = couponApplied ? (subtotal * 5 ~/ 100) : 0;
    return subtotal - discount + deliveryFee(wilaya);
  }

  void addToCart(String productId, [int quantity = 1]) {
    final product = productById(productId);
    final stock = stockFor(productId);
    if (product.quoteOnly || stock == 0) return;
    _cart[productId] =
        ((_cart[productId] ?? 0) + quantity).clamp(1, stock).toInt();
    notifyListeners();
  }

  void setQuantity(String productId, int quantity) {
    if (quantity <= 0) {
      _cart.remove(productId);
    } else {
      final stock = stockFor(productId);
      if (stock == 0) {
        _cart.remove(productId);
      } else {
        _cart[productId] = quantity.clamp(1, stock).toInt();
      }
    }
    notifyListeners();
  }

  void setInventory(String productId, int quantity) {
    if (quantity < 0) {
      throw ArgumentError.value(quantity, 'quantity', 'Must not be negative.');
    }
    _stockAdjustments[productId] = quantity;
    if (quantity == 0) {
      _cart.remove(productId);
    } else if (_cart.containsKey(productId) && _cart[productId]! > quantity) {
      _cart[productId] = quantity;
    }
    notifyListeners();
  }

  void removeFromCart(String productId) {
    _cart.remove(productId);
    notifyListeners();
  }

  void toggleFavorite(String productId) {
    if (!_favorites.add(productId)) _favorites.remove(productId);
    notifyListeners();
  }

  DemoOrder placeOrder({
    required String wilaya,
    required String paymentMethod,
    required String customerName,
    required String phone,
    required String address,
    bool couponApplied = false,
  }) {
    if (_cart.isEmpty) {
      throw StateError('Cannot place an order with an empty cart.');
    }
    final order = DemoOrder(
      number:
          'AO-${DateTime.now().millisecondsSinceEpoch.toString().substring(7)}',
      items: Map.unmodifiable(_cart),
      total: totalFor(wilaya, couponApplied: couponApplied),
      wilaya: wilaya,
      paymentMethod: paymentMethod,
      customerName: customerName,
      phone: phone,
      address: address,
      createdAt: DateTime.now(),
    );
    _orders.insert(0, order);
    _cart.clear();
    notifyListeners();
    return order;
  }
}

CatalogProduct productById(String id) =>
    catalogProducts.firstWhere((product) => product.id == id);
