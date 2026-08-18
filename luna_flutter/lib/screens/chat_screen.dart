import "package:flutter/material.dart";

import "../api.dart";

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key, required this.api, required this.onLogout});
  final LunaApi api;
  final VoidCallback onLogout;

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final input = TextEditingController();
  String dialogue = "…";
  List<String> chips = [];
  String exp = "Lv.1";
  String error = "";
  bool busy = false;

  static const spriteBase = "https://luna-fsq.onrender.com/static/live2d/luna-expressions";

  @override
  void initState() {
    super.initState();
    _start();
  }

  Future<void> _start() async {
    setState(() => busy = true);
    try {
      final data = await widget.api.chatStart();
      await _apply(data);
    } catch (e) {
      setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> _apply(Map<String, dynamic> data) async {
    dialogue = (data["dialogue"] ?? "").toString();
    chips = ((data["suggested_replies"] as List?) ?? []).map((e) => e.toString()).toList();
    try {
      final st = await widget.api.state();
      exp = "Lv.${st["current_level"] ?? 1} · EXP ${st["total_exp"] ?? 0}";
    } catch (_) {}
    setState(() {});
  }

  Future<void> _send(String text) async {
    final msg = text.trim();
    if (msg.isEmpty || busy) return;
    input.clear();
    setState(() {
      busy = true;
      error = "";
    });
    try {
      final data = await widget.api.chat(msg);
      await _apply(data);
    } catch (e) {
      setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("LUNA"),
        actions: [
          Center(child: Padding(padding: const EdgeInsets.only(right: 8), child: Text(exp, style: const TextStyle(fontSize: 12)))),
          IconButton(onPressed: widget.onLogout, icon: const Icon(Icons.logout)),
        ],
      ),
      body: Column(
        children: [
          Image.network(
            "$spriteBase/luna-neutral.png",
            height: 180,
            errorBuilder: (_, __, ___) => const SizedBox(height: 120, child: Center(child: Text("LUNA"))),
          ),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text(dialogue, style: const TextStyle(height: 1.6)),
            ),
          ),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: chips
                .map((c) => ActionChip(label: Text(c), onPressed: busy ? null : () => _send(c)))
                .toList(),
          ),
          if (error.isNotEmpty)
            Padding(
              padding: const EdgeInsets.all(8),
              child: Text(error, style: const TextStyle(color: Color(0xFFD96B6B))),
            ),
          const Spacer(),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 16),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: input,
                    enabled: !busy,
                    decoration: const InputDecoration(hintText: "自分の言葉で答える…"),
                    onSubmitted: _send,
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton(onPressed: busy ? null : () => _send(input.text), child: const Text("送信")),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
