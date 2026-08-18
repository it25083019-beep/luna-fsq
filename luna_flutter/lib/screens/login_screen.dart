import "package:flutter/material.dart";

import "../api.dart";

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, required this.api, required this.onLoggedIn});
  final LunaApi api;
  final VoidCallback onLoggedIn;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final email = TextEditingController();
  final password = TextEditingController();
  bool register = false;
  bool busy = false;
  String error = "";

  Future<void> _submit() async {
    setState(() {
      busy = true;
      error = "";
    });
    try {
      final data = register
          ? await widget.api.register(email.text.trim(), password.text)
          : await widget.api.login(email.text.trim(), password.text);
      await widget.api.saveToken(data["access_token"] as String);
      widget.onLoggedIn();
    } catch (e) {
      setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            const Text("LUNA", style: TextStyle(color: Color(0xFFE8B86D), fontSize: 32, fontWeight: FontWeight.w600)),
            const SizedBox(height: 4),
            const Text("管理者・ユーザー共通ログイン", style: TextStyle(color: Color(0xFF8AA3A0))),
            const SizedBox(height: 28),
            TextField(
              controller: email,
              keyboardType: TextInputType.emailAddress,
              decoration: const InputDecoration(labelText: "メール"),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: password,
              obscureText: true,
              decoration: const InputDecoration(labelText: "パスワード"),
            ),
            const SizedBox(height: 20),
            FilledButton(
              onPressed: busy ? null : _submit,
              child: Text(register ? "登録して開始" : "ログイン"),
            ),
            TextButton(
              onPressed: busy ? null : () => setState(() => register = !register),
              child: Text(register ? "ログインはこちら" : "新規登録はこちら"),
            ),
            if (error.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(error, style: const TextStyle(color: Color(0xFFD96B6B))),
              ),
          ],
        ),
      ),
    );
  }
}
