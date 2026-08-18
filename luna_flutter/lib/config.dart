class AppConfig {
  /// Production API. For local: http://127.0.0.1:8006
  /// Android emulator: http://10.0.2.2:8006
  static const String baseUrl = String.fromEnvironment(
    "LUNA_API",
    defaultValue: "https://luna-fsq.onrender.com",
  );
}
