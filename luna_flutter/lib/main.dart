import "package:flutter/material.dart";

import "api.dart";
import "screens/chat_screen.dart";
import "screens/login_screen.dart";

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const LunaApp());
}

class LunaApp extends StatefulWidget {
  const LunaApp({super.key});

  @override
  State<LunaApp> createState() => _LunaAppState();
}

class _LunaAppState extends State<LunaApp> {
  final api = LunaApi();
  bool ready = false;
  bool loggedIn = false;

  @override
  void initState() {
    super.initState();
    _boot();
  }

  Future<void> _boot() async {
    await api.loadToken();
    var ok = api.token != null && api.token!.isNotEmpty;
    if (ok) {
      try {
        await api.me();
      } catch (_) {
        await api.clearToken();
        ok = false;
      }
    }
    setState(() {
      loggedIn = ok;
      ready = true;
    });
  }

  @override
  Widget build(BuildContext context) {
    const bg = Color(0xFF0C1416);
    const amber = Color(0xFFE8B86D);
    const teal = Color(0xFF2EC4B6);
    if (!ready) {
      return const MaterialApp(
        home: Scaffold(backgroundColor: bg, body: Center(child: CircularProgressIndicator())),
      );
    }
    return MaterialApp(
      title: "LUNA",
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: bg,
        colorScheme: const ColorScheme.dark(
          primary: teal,
          secondary: amber,
          surface: Color(0xFF162126),
        ),
        fontFamily: "Roboto",
      ),
      home: loggedIn
          ? ChatScreen(
              api: api,
              onLogout: () async {
                await api.clearToken();
                setState(() => loggedIn = false);
              },
            )
          : LoginScreen(
              api: api,
              onLoggedIn: () => setState(() => loggedIn = true),
            ),
    );
  }
}
