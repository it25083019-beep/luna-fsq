import "dart:convert";

import "package:flutter_secure_storage/flutter_secure_storage.dart";
import "package:http/http.dart" as http;

import "config.dart";

class LunaApi {
  LunaApi({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;
  final _storage = const FlutterSecureStorage();
  static const _tokenKey = "luna_token";

  String? token;

  Future<void> loadToken() async {
    token = await _storage.read(key: _tokenKey);
  }

  Future<void> saveToken(String value) async {
    token = value;
    await _storage.write(key: _tokenKey, value: value);
  }

  Future<void> clearToken() async {
    token = null;
    await _storage.delete(key: _tokenKey);
  }

  Map<String, String> _headers({bool auth = true}) {
    final h = {"Content-Type": "application/json"};
    if (auth && token != null && token!.isNotEmpty) {
      h["Authorization"] = "Bearer $token";
    }
    return h;
  }

  Future<Map<String, dynamic>> _json(
    String method,
    String path, {
    Object? body,
    bool auth = true,
  }) async {
    final uri = Uri.parse("${AppConfig.baseUrl}$path");
    late http.Response res;
    if (method == "GET") {
      res = await _client.get(uri, headers: _headers(auth: auth));
    } else {
      res = await _client.post(
        uri,
        headers: _headers(auth: auth),
        body: body == null ? null : jsonEncode(body),
      );
    }
    Map<String, dynamic>? data;
    try {
      data = jsonDecode(res.body) as Map<String, dynamic>;
    } catch (_) {}
    if (res.statusCode < 200 || res.statusCode >= 300) {
      final detail = data?["detail"];
      if (detail is Map && detail["message"] != null) {
        throw LunaApiException(detail["message"].toString(), res.statusCode);
      }
      if (detail is String) throw LunaApiException(detail, res.statusCode);
      throw LunaApiException("Request failed (${res.statusCode})", res.statusCode);
    }
    return data ?? {};
  }

  Future<Map<String, dynamic>> login(String email, String password) {
    return _json("POST", "/auth/login", body: {"email": email, "password": password}, auth: false);
  }

  Future<Map<String, dynamic>> register(String email, String password) {
    return _json("POST", "/auth/register", body: {"email": email, "password": password}, auth: false);
  }

  Future<Map<String, dynamic>> me() => _json("GET", "/auth/me");

  Future<Map<String, dynamic>> chatStart() {
    return _json("POST", "/chat/start", body: {"message": ""});
  }

  Future<Map<String, dynamic>> chat(String message) {
    return _json("POST", "/chat", body: {"message": message});
  }

  Future<Map<String, dynamic>> state() => _json("GET", "/state/me");

  Future<Map<String, dynamic>> morningCheckin(String goal) {
    return _json("POST", "/checkin/morning", body: {"goal": goal});
  }

  Future<Map<String, dynamic>> eveningCheckin() {
    return _json("POST", "/checkin/evening", body: {});
  }
}

class LunaApiException implements Exception {
  LunaApiException(this.message, this.statusCode);
  final String message;
  final int statusCode;
  @override
  String toString() => message;
}
