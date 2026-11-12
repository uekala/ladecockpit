// The texts are looked up at run time (tr), so widgets holding them cannot be const.
// ignore_for_file: prefer_const_constructors
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:local_auth/local_auth.dart';

import 'l10n.dart';
import 'theme/app_theme.dart';

/// Optional lock: the app asks for fingerprint, face or the phone's own
/// PIN before it shows anything. Off unless the user turns it on.
class AppLock {
  AppLock({
    FlutterSecureStorage storage = const FlutterSecureStorage(),
    Future<bool> Function()? deviceSupported,
    Future<bool> Function(String reason)? authenticate,
  })  : _storage = storage,
        _deviceSupported = deviceSupported ?? _platformSupported,
        _authenticate = authenticate ?? _platformAuthenticate;

  static const _enabledKey = 'app_lock';

  final FlutterSecureStorage _storage;
  final Future<bool> Function() _deviceSupported;
  final Future<bool> Function(String reason) _authenticate;

  static Future<bool> _platformSupported() => LocalAuthentication().isDeviceSupported();

  static Future<bool> _platformAuthenticate(String reason) =>
      LocalAuthentication().authenticate(localizedReason: reason);

  /// True when the phone has a screen lock the app can ask for.
  /// A phone without one never locks the app, so nobody is shut out.
  Future<bool> get supported async {
    try {
      return await _deviceSupported();
    } catch (_) {
      return false;
    }
  }

  Future<bool> get enabled async {
    try {
      return (await _storage.read(key: _enabledKey)) == 'on';
    } catch (_) {
      return false;
    }
  }

  Future<void> setEnabled(bool value) =>
      _storage.write(key: _enabledKey, value: value ? 'on' : 'off');

  /// Asks the phone to confirm its owner. False when cancelled or failed.
  Future<bool> unlock(String reason) async {
    try {
      return await _authenticate(reason);
    } catch (_) {
      return false;
    }
  }
}

/// Covers the whole app while it is locked. Locks at start and after the
/// app was in the background for [relockAfter].
class AppLockGate extends StatefulWidget {
  const AppLockGate({
    super.key,
    required this.child,
    this.lock,
    this.relockAfter = const Duration(minutes: 1),
  });

  final Widget child;

  /// Injectable for tests; the app uses the default.
  final AppLock? lock;
  final Duration relockAfter;

  @override
  State<AppLockGate> createState() => _AppLockGateState();
}

class _AppLockGateState extends State<AppLockGate> with WidgetsBindingObserver {
  late final AppLock _lock = widget.lock ?? AppLock();
  // null until the setting has been read.
  bool? _locked;
  bool _asking = false;
  DateTime? _pausedAt;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _lockIfEnabled();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused) {
      _pausedAt ??= DateTime.now();
    } else if (state == AppLifecycleState.resumed) {
      final pausedAt = _pausedAt;
      _pausedAt = null;
      if (_asking || _locked == true || pausedAt == null) return;
      if (DateTime.now().difference(pausedAt) >= widget.relockAfter) _lockIfEnabled();
    }
  }

  Future<void> _lockIfEnabled() async {
    final lock = await _lock.enabled && await _lock.supported;
    if (!mounted) return;
    setState(() => _locked = lock);
    if (lock) await _ask();
  }

  Future<void> _ask() async {
    if (_asking) return;
    _asking = true;
    final ok = await _lock.unlock(tr('Ladecockpit entsperren'));
    _asking = false;
    if (ok && mounted) setState(() => _locked = false);
  }

  @override
  Widget build(BuildContext context) {
    if (_locked == false) return widget.child;
    return Stack(
      children: [
        widget.child,
        Positioned.fill(
          child: Material(
            color: AppTheme.background,
            child: _locked == null
                ? SizedBox.shrink()
                : Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.lock_outline_rounded, size: 44, color: AppTheme.textSecondary),
                        SizedBox(height: 14),
                        Text(tr('Ladecockpit ist gesperrt'),
                            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                        SizedBox(height: 18),
                        FilledButton.icon(
                          key: ValueKey('app-lock-unlock'),
                          onPressed: _ask,
                          icon: Icon(Icons.fingerprint, size: 20),
                          label: Text(tr('Entsperren')),
                        ),
                      ],
                    ),
                  ),
          ),
        ),
      ],
    );
  }
}
