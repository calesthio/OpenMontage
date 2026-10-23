import 'package:flutter_test/flutter_test.dart';

import 'package:ao_groupe_app/models/algeria_wilaya.dart';
import 'package:ao_groupe_app/models/store_controller.dart';

void main() {
  late StoreController controller;

  setUp(() {
    controller = StoreController();
  });

  tearDown(() {
    controller.dispose();
  });

  test('uses wholesale pricing from five units and calculates delivery', () {
    controller.addToCart('cable-25', 5);

    expect(controller.cartCount, 5);
    expect(controller.subtotal, 775);
    expect(controller.deliveryFee('16'), 500);
    expect(controller.totalFor('16', couponApplied: true), 1237);
  });

  test('respects live inventory when adding and updating cart quantities', () {
    controller.setInventory('cable-25', 3);
    controller.addToCart('cable-25', 8);

    expect(controller.cart['cable-25'], 3);
    controller.setInventory('cable-25', 1);
    expect(controller.cart['cable-25'], 1);
    controller.setInventory('cable-25', 0);
    expect(controller.cart, isEmpty);
    controller.addToCart('cable-25');
    expect(controller.cart, isEmpty);
  });

  test('rejects negative inventory', () {
    expect(
      () => controller.setInventory('cable-25', -1),
      throwsArgumentError,
    );
  });

  test('records an immutable order and clears the cart', () {
    controller.addToCart('cable-25', 2);
    final order = controller.placeOrder(
      wilaya: '16',
      paymentMethod: 'cash',
      customerName: 'Test Customer',
      phone: '0550000000',
      address: 'Test address',
    );

    expect(order.items, {'cable-25': 2});
    expect(order.total, 860);
    expect(controller.cart, isEmpty);
    expect(controller.orders, [order]);
    expect(() => order.items['cable-25'] = 5, throwsUnsupportedError);
  });

  test('includes all 58 wilayas with unique codes and localized names', () {
    expect(algerianWilayas, hasLength(58));
    expect(algerianWilayas.map((wilaya) => wilaya.code).toSet(), hasLength(58));
    expect(algerianWilayaByCode('16')?.label('ar'), 'الجزائر العاصمة');
    expect(algerianWilayaByCode('16')?.label('fr'), 'Alger');
    expect(algerianWilayaByCode('00'), isNull);
  });
}
