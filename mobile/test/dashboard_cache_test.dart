import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:ladecockpit_mobile/dashboard_cache.dart';

void main() {
  late Directory dir;
  late DashboardCache cache;

  setUp(() async {
    dir = await Directory.systemTemp.createTemp('ladecockpit-cache-test');
    cache = DashboardCache(directory: () async => dir);
  });

  tearDown(() async {
    if (await dir.exists()) await dir.delete(recursive: true);
  });

  test('returns what was written, with its time', () async {
    final at = DateTime.utc(2026, 11, 12, 18, 30);
    await cache.write({'mode': 'live', 'month': {'cost': 65.1}}, at);
    final cached = await cache.read();
    expect(cached, isNotNull);
    expect(cached!.fetchedAt.toUtc(), at);
    expect((cached.data['month'] as Map)['cost'], 65.1);
    expect(await File('${dir.path}/dashboard.json.tmp').exists(), isFalse);
  });

  test('is empty before the first write and after clear', () async {
    expect(await cache.read(), isNull);
    await cache.write({'mode': 'live'}, DateTime.now());
    await cache.clear();
    expect(await cache.read(), isNull);
    await cache.clear();
  });

  test('ignores a broken file', () async {
    await File('${dir.path}/dashboard.json').writeAsString('{"fetched_at": "nonsense", "data": []');
    expect(await cache.read(), isNull);
    await File('${dir.path}/dashboard.json').writeAsString('{"fetched_at": "2026-11-12T18:30:00Z", "data": []}');
    expect(await cache.read(), isNull);
  });

  test('never throws when the folder is not available', () async {
    final broken = DashboardCache(directory: () async => throw const FileSystemException('no storage'));
    await broken.write({'mode': 'live'}, DateTime.now());
    expect(await broken.read(), isNull);
    await broken.clear();
  });
}
