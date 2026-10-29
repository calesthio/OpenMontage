import 'package:flutter_test/flutter_test.dart';

import 'package:ao_groupe_app/models/algeria_wilaya.dart';
import 'package:ao_groupe_app/models/catalog.dart';
import 'package:ao_groupe_app/models/store_controller.dart';

void main() {
  late StoreController controller;

  setUp(() {
    controller = StoreController();
  });

  tearDown(() {
    controller.dispose();
  });

  test('includes all 58 wilayas with unique codes and localized names', () {
    expect(algerianWilayas, hasLength(58));
    expect(algerianWilayas.map((wilaya) => wilaya.code).toSet(), hasLength(58));
    expect(algerianWilayaByCode('16')?.label('ar'), 'الجزائر العاصمة');
    expect(algerianWilayaByCode('16')?.label('fr'), 'Alger');
    expect(algerianWilayaByCode('00'), isNull);
  });

  test('catalog contains only pictured references awaiting a quote', () {
    expect(catalogProducts, hasLength(14));
    expect(
      catalogProducts.map((product) => product.id).toSet(),
      hasLength(14),
    );
    expect(
      catalogProducts.map((product) => product.categoryId).toSet(),
      {'mounts', 'storage', 'lighting', 'ceiling', 'supports'},
    );
    expect(
      catalogProducts.every(
        (product) =>
            product.quoteOnly &&
            product.imageAsset != null &&
            product.price == 0 &&
            product.wholesalePrice == 0 &&
            product.stock == 0,
      ),
      isTrue,
    );
  });

  test('quote-only reference products cannot enter the cart', () {
    controller.addToCart(catalogProducts.first.id);

    expect(controller.cart, isEmpty);
    expect(controller.cartCount, 0);
  });
}
