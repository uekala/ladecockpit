import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ladecockpit_mobile/theme/app_theme.dart';

void main() {
  group('AppTheme', () {
    test('uses the approved dark automotive palette', () {
      final theme = AppTheme.dark;

      expect(theme.brightness, Brightness.dark);
      expect(theme.scaffoldBackgroundColor, const Color(0xFF070B10));
      expect(theme.colorScheme.primary, AppTheme.accentTeal);
      expect(theme.colorScheme.secondary, AppTheme.accentGreen);
      expect(theme.cardTheme.color, AppTheme.surface);
    });

    testWidgets('applies the theme to a basic Material app', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.dark,
          home: const Scaffold(
            body: Card(child: Text('Ladecockpit')),
          ),
        ),
      );

      expect(find.text('Ladecockpit'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });
}
