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

    expect(find.text('AO groupe'), findsOneWidget);
    expect(find.text('كل حلول الكهرباء والطاقة، في مكان واحد'), findsOneWidget);
    expect(
      Directionality.of(
        tester.element(find.text('كل حلول الكهرباء والطاقة، في مكان واحد')),
      ),
      TextDirection.rtl,
    );
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
    expect(find.text('كل حلول الكهرباء والطاقة، في مكان واحد'), findsOneWidget);
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
    expect(find.text('نفد المخزون'), findsOneWidget);
    expect(find.byType(DropdownButton<Locale>), findsOneWidget);
  });

  testWidgets('completes a local cart and checkout flow', (tester) async {
    SharedPreferences.setMockInitialValues({'onboarding.complete': true});
    await tester.pumpWidget(const AoGroupeApp());
    await tester.pump(const Duration(milliseconds: 800));
    await tester.pumpAndSettle();

    await tester.tap(find.text('البحث'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).first, 'كابل نحاسي');
    await tester.pumpAndSettle();
    final product = find.text('كابل نحاسي 2.5 مم²').first;
    await tester.ensureVisible(product);
    await tester.tap(product);
    await tester.pumpAndSettle();

    await tester.tap(find.text('أضف إلى السلة'));
    await tester.pumpAndSettle();
    await tester.tap(find.byIcon(Icons.arrow_back));
    await tester.pumpAndSettle();
    await tester.tap(find.text('السلة').last);
    await tester.pumpAndSettle();

    expect(find.text('كابل نحاسي 2.5 مم²'), findsOneWidget);
    final checkoutButton = find.text('إتمام الطلب');
    await tester.ensureVisible(checkoutButton);
    await tester.tap(checkoutButton);
    await tester.pumpAndSettle();
    final nameField = find.byType(TextFormField).at(0);
    final phoneField = find.byType(TextFormField).at(1);
    await tester.ensureVisible(nameField);
    await tester.enterText(nameField, 'مشتري تجريبي');
    await tester.ensureVisible(phoneField);
    await tester.enterText(phoneField, '0550000000');
    await tester.drag(find.byType(ListView).last, const Offset(0, -320));
    await tester.pumpAndSettle();
    final addressField = find.byType(TextFormField).last;
    await tester.ensureVisible(addressField);
    await tester.enterText(addressField, 'شارع الاختبار، الجزائر');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    tester.testTextInput.hide();
    await tester.pumpAndSettle();
    final placeOrderButton = find.text('تأكيد الطلب');
    await tester.ensureVisible(placeOrderButton);
    await tester.pumpAndSettle();
    await tester.tap(placeOrderButton);
    await tester.pumpAndSettle();

    expect(find.text('تم تسجيل طلبك'), findsNWidgets(2));
    expect(
      find.textContaining('وليس طلباً مرسلاً للمتجر'),
      findsOneWidget,
    );
  });
}
