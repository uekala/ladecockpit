import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ladecockpit_mobile/app_lock.dart';
import 'package:ladecockpit_mobile/theme/app_theme.dart';

Widget _app(AppLock lock) => MaterialApp(
      theme: AppTheme.dark,
      builder: (context, child) => AppLockGate(lock: lock, child: child!),
      home: const Scaffold(body: Center(child: Text('Zahlen'))),
    );

Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 4; i++) {
    await tester.pump(const Duration(milliseconds: 100));
  }
}

void main() {
  testWidgets('stays open when the lock is off', (tester) async {
    FlutterSecureStorage.setMockInitialValues({});
    var asked = 0;
    await tester.pumpWidget(_app(AppLock(
      deviceSupported: () async => true,
      authenticate: (_) async {
        asked++;
        return true;
      },
    )));
    await _settle(tester);
    expect(find.text('Ladecockpit ist gesperrt'), findsNothing);
    expect(find.text('Zahlen').hitTestable(), findsOneWidget);
    expect(asked, 0);
  });

  testWidgets('a phone without a screen lock never locks the app', (tester) async {
    FlutterSecureStorage.setMockInitialValues({'app_lock': 'on'});
    await tester.pumpWidget(_app(AppLock(
      deviceSupported: () async => false,
      authenticate: (_) async => false,
    )));
    await _settle(tester);
    expect(find.text('Ladecockpit ist gesperrt'), findsNothing);
    expect(find.text('Zahlen').hitTestable(), findsOneWidget);
  });

  testWidgets('covers the app until the phone confirms its owner', (tester) async {
    FlutterSecureStorage.setMockInitialValues({'app_lock': 'on'});
    var answer = false;
    var asked = 0;
    await tester.pumpWidget(_app(AppLock(
      deviceSupported: () async => true,
      authenticate: (_) async {
        asked++;
        return answer;
      },
    )));
    await _settle(tester);
    expect(asked, 1);
    expect(find.text('Ladecockpit ist gesperrt'), findsOneWidget);
    expect(find.text('Zahlen').hitTestable(), findsNothing);

    answer = true;
    await tester.tap(find.byKey(const ValueKey('app-lock-unlock')));
    await _settle(tester);
    expect(asked, 2);
    expect(find.text('Ladecockpit ist gesperrt'), findsNothing);
    expect(find.text('Zahlen').hitTestable(), findsOneWidget);
  });

  testWidgets('locks again after a while in the background', (tester) async {
    FlutterSecureStorage.setMockInitialValues({'app_lock': 'on'});
    var answer = true;
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.dark,
      builder: (context, child) => AppLockGate(
        lock: AppLock(deviceSupported: () async => true, authenticate: (_) async => answer),
        relockAfter: Duration.zero,
        child: child!,
      ),
      home: const Scaffold(body: Center(child: Text('Zahlen'))),
    ));
    await _settle(tester);
    expect(find.text('Zahlen').hitTestable(), findsOneWidget);

    answer = false;
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await _settle(tester);
    expect(find.text('Ladecockpit ist gesperrt'), findsOneWidget);
    expect(find.text('Zahlen').hitTestable(), findsNothing);
  });

  test('a failing phone check counts as not confirmed', () async {
    FlutterSecureStorage.setMockInitialValues({});
    final lock = AppLock(
      deviceSupported: () async => throw Exception('no plugin'),
      authenticate: (_) async => throw Exception('cancelled'),
    );
    expect(await lock.supported, isFalse);
    expect(await lock.unlock('x'), isFalse);
    expect(await lock.enabled, isFalse);
    await lock.setEnabled(true);
    expect(await lock.enabled, isTrue);
  });
}
