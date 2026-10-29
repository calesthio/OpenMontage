import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:ao_groupe_app/main.dart';

void main() {
  testWidgets('shows onboarding and opens the Arabic RTL storefront', (
    tester,
  ) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const AoGroupeApp());
    await tester.pump(const Duration(milliseconds: 800));
    await tester.pumpAndSettle();

    expect(find.text('أهلاً بك في AO groupe'), findsOneWidget);
    await tester.tap(find.text('تخطي'));
    await tester.pumpAndSettle();

    expect(find.text('AO groupe'), findsAtLeastNWidgets(1));
    expect(find.text('تفاصيل تضيء مساحتك'), findsOneWidget);
    expect(
      Directionality.of(
        tester.element(find.text('تفاصيل تضيء مساحتك')),
      ),
      TextDirection.rtl,
    );
    expect(
      find.byKey(const ValueKey('assets/products/tv-wall-mount.png')),
      findsOneWidget,
    );
    await tester.tap(find.byTooltip('إيقاف عرض الصور'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('الصورة التالية'));
    await tester.pumpAndSettle();
    final selectedProductSlide =
        find.byKey(const ValueKey('assets/products/laundry-organizer.png'));
    expect(selectedProductSlide, findsOneWidget);
    await tester.pump(const Duration(seconds: 6));
    expect(selectedProductSlide, findsOneWidget);
    expect(find.byTooltip('تشغيل عرض الصور'), findsOneWidget);

    final preferences = await SharedPreferences.getInstance();
    expect(preferences.getBool('onboarding.complete'), isTrue);
  });

  testWidgets('opens persisted onboarding directly to the storefront', (
    tester,
  ) async {
    SharedPreferences.setMockInitialValues({'onboarding.complete': true});
    await tester.pumpWidget(const AoGroupeApp());
    await tester.pump(const Duration(milliseconds: 800));
    await tester.pumpAndSettle();

    expect(find.text('أهلاً بك في AO groupe'), findsNothing);
    expect(find.text('تفاصيل تضيء مساحتك'), findsOneWidget);
    expect(
      find.byType(NavigationBar),
      findsOneWidget,
    );
  });

  testWidgets('keeps the design system preview available in settings', (
    tester,
  ) async {
    SharedPreferences.setMockInitialValues({'onboarding.complete': true});
    await tester.pumpWidget(const AoGroupeApp());
    await tester.pump(const Duration(milliseconds: 800));
    await tester.pumpAndSettle();

    await tester.tap(find.text('حسابي'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('الإعدادات'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('معاينة نظام التصميم'));
    await tester.pumpAndSettle();

    expect(find.text('معاينة نظام التصميم'), findsOneWidget);
    expect(find.text('حامل تلفاز جداري'), findsOneWidget);
    expect(find.text('السعر عند الطلب'), findsOneWidget);
    expect(find.text('450 دج / قطعة'), findsNothing);
    expect(find.text('نفد المخزون'), findsOneWidget);
    expect(find.byType(DropdownButton<Locale>), findsOneWidget);
  });

  testWidgets('shows only supplied products and offers quote requests', (
    tester,
  ) async {
    SharedPreferences.setMockInitialValues({'onboarding.complete': true});
    await tester.pumpWidget(const AoGroupeApp());
    await tester.pump(const Duration(milliseconds: 800));
    await tester.pumpAndSettle();

    await tester.tap(find.text('البحث'));
    await tester.pumpAndSettle();
    final searchField = find.byType(TextField).first;
    await tester.enterText(searchField, 'كابل نحاسي');
    await tester.pumpAndSettle();
    expect(find.text('لا توجد منتجات مطابقة'), findsOneWidget);

    await tester.enterText(searchField, 'حامل تلفاز');
    await tester.pumpAndSettle();
    final product = find.text('حامل تلفاز جداري').first;
    expect(product, findsOneWidget);
    await tester.tap(product);
    await tester.pumpAndSettle();

    final quoteButton = find.widgetWithText(FilledButton, 'اطلب عرض سعر');
    expect(quoteButton, findsOneWidget);
    await tester.tap(quoteButton);
    await tester.pumpAndSettle();
    expect(find.text('طلب عرض سعر'), findsOneWidget);
  });
}
