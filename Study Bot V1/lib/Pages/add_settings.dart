// ignore_for_file: deprecated_member_use

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

class AddSettings extends StatefulWidget {
  final List<String> semesters;
  final List<String> departments;
  final String? selectedSemester;
  final String? selectedDepartment;

  final Future<List<String>> Function(String semester) fetchDepartments;
  final Future<void> Function(String username, String? semester, String? department)
      registerUser;
  final Future<void> Function(String username, String? semester, String? department)
      registerUserGuest;

  final String username;

  const AddSettings({
    super.key,
    required this.semesters,
    required this.departments,
    required this.selectedSemester,
    required this.selectedDepartment,
    required this.fetchDepartments,
    required this.registerUser,
    required this.registerUserGuest,
    required this.username,
  });

  @override
  State<AddSettings> createState() => _AddSettingsState();
}

class _AddSettingsState extends State<AddSettings> {
  String? selectedSemester;
  String? selectedDepartment;
  late List<String> _departments;
  bool isGuest = false;
  String? guestId;


  @override
  void initState() {
    super.initState();
    selectedSemester = widget.selectedSemester;
    selectedDepartment = widget.selectedDepartment;
    _departments = List.from(widget.departments);
    _loadGuestStatus();
  }

  Future<void> _loadGuestStatus() async {
    final prefs = await SharedPreferences.getInstance();
    if (!mounted) return;

    isGuest = prefs.getBool('is_guest') ?? true;
    guestId = prefs.getString('guest_id');

    // Generate a new guest ID if none exists
    if (isGuest && guestId == null) {
      guestId = const Uuid().v4();
      await prefs.setString('guest_id', guestId!);
    }

    if (!mounted) return;
    setState(() {});
  }

  Future<void> _fetchDepartments(String semester) async {
    if (!mounted) return;
    setState(() => selectedDepartment = null);

    try {
      final fetched = await widget.fetchDepartments(semester);
      if (!mounted) return;
      setState(() => _departments = fetched);
    } catch (e) {
      _showError("Failed to fetch departments");
    }
  }

  Future<void> _saveSettings() async {
    final usernameToUse = isGuest ? guestId! : widget.username;

    try {
      if (isGuest) {
        await widget.registerUserGuest(
          usernameToUse,
          selectedSemester,
          selectedDepartment,
        );
      } else {
        await widget.registerUser(
          usernameToUse,
          selectedSemester,
          selectedDepartment,
        );
      }

      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool('add_settings_shown', true);
      await prefs.setBool('is_guest', isGuest);
      await prefs.setString('username', usernameToUse);

      _showSuccess("Settings saved successfully!");

      if (!mounted) return;
      Navigator.pushReplacementNamed(context, "/home");
    } catch (e) {
      _showError("Failed to save settings");
    }
  }

  void _showSuccess(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.green),
    );
  }

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.red),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        iconTheme: const IconThemeData(color: Colors.white),
        title: Text(
          isGuest ? "Welcome Guest" : "Welcome ${widget.username}",
          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
        ),
        centerTitle: true,
        backgroundColor: const Color.fromARGB(255, 2, 85, 152),
      ),
      body: Padding(
        padding: const EdgeInsets.all(30),
        child: SingleChildScrollView(
          child: Column(
            children: [
              const SizedBox(height: 40),
              const Text("Add Your Settings",
                  style: TextStyle(fontSize: 30, fontWeight: FontWeight.bold)),
              const SizedBox(height: 10),
              Text(
                isGuest
                    ? "You are currently using a guest account. Please select your settings."
                    : "We couldn't find your profile in the system. Please add your settings.",
                style: const TextStyle(fontSize: 16),
              ),
              const SizedBox(height: 40),
              const Divider(height: 2, color: Colors.grey),
              const SizedBox(height: 30),
              const CircleAvatar(
                radius: 70,
                backgroundImage: AssetImage('assets/user_avatar.png'),
              ),
              const SizedBox(height: 60),

              /// SEMESTER DROPDOWN
              DropdownButtonFormField<String>(
                dropdownColor: const Color.fromARGB(255, 247, 245, 245),
                // ignore: duplicate_ignore
                // ignore: deprecated_member_use
                value: widget.semesters.contains(selectedSemester)
                    ? selectedSemester
                    : null,
                style: const TextStyle(fontSize: 25, fontWeight: FontWeight.w500, color: Color.fromARGB(255, 39, 38, 38)),
                decoration: InputDecoration(
                  prefixIcon: const Icon(Icons.school, color: Color.fromARGB(255, 2, 85, 152)),
                  labelText: "Select Semester",
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(15)),
                ),
                items: widget.semesters.toSet().map((s) =>
                  DropdownMenuItem(value: s, child: Text(s, style: const TextStyle(fontSize: 18)))
                ).toList(),
                onChanged: (value) {
                  if (value == null) return;
                  setState(() => selectedSemester = value);
                  _fetchDepartments(value);
                },
              ),
              const SizedBox(height: 40),

              /// DEPARTMENT DROPDOWN
              DropdownButtonFormField<String>(
                dropdownColor: const Color.fromARGB(255, 247, 245, 245),
                value: _departments.contains(selectedDepartment)
                    ? selectedDepartment
                    : null,
                style: const TextStyle(fontSize: 25, fontWeight: FontWeight.w500, color: Color.fromARGB(255, 39, 38, 38)),
                decoration: InputDecoration(
                  prefixIcon: const Icon(Icons.school, color: Color.fromARGB(255, 2, 85, 152)),
                  labelText: "Select Department",
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(15)),
                ),
                items: _departments.toSet().map((d) =>
                  DropdownMenuItem(value: d, child: Text(d, style: const TextStyle(fontSize: 18)))
                ).toList(),
                onChanged: (value) => setState(() => selectedDepartment = value),
              ),
              const SizedBox(height: 80),

              /// SAVE BUTTON
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color.fromARGB(255, 2, 85, 152),
                  padding: const EdgeInsets.symmetric(horizontal: 50, vertical: 15),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
                ),
                onPressed: (selectedSemester != null && selectedDepartment != null)
                    ? _saveSettings
                    : null,
                child: const Text("Save Changes",
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
