import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

class EditSettings extends StatefulWidget {
  final List<String> semesters;
  final List<String> departments;
  final String? selectedSemester;
  final String? selectedDepartment;
  final Future<List<String>> Function(String) fetchDepartments;
  final Future<void> Function() fetchSemesters;
  final Future<void> Function(String, String?, String?, {bool isUpgrade})
  updateUser;
  final Future<void> Function(String, String?, String?) registerUser;
  final String username;

  const EditSettings({
    super.key,
    required this.semesters,
    required this.departments,
    required this.selectedSemester,
    required this.selectedDepartment,
    required this.fetchDepartments,
    required this.fetchSemesters,
    required this.updateUser,
    required this.username,
    required this.registerUser,
  });

  @override
  State<EditSettings> createState() => _EditSettingsState();
}

class _EditSettingsState extends State<EditSettings> {
  String? selectedSemester;
  String? selectedDepartment;
  bool isLoading = true;
  bool isGuest = false;
  String? guestId;
  final TextEditingController guestUsernameController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _initializeData();
  }

  Future<void> _initializeData() async {
    final prefs = await SharedPreferences.getInstance();
    isGuest = prefs.getBool('is_guest') ?? false;
    guestId = prefs.getString('guest_id');

    if (isGuest && guestId == null) {
      guestId = const Uuid().v4();
      await prefs.setString('guest_id', guestId!);
    }

    selectedSemester = widget.selectedSemester;
    selectedDepartment = widget.selectedDepartment;

    if (widget.semesters.isEmpty) {
      await widget.fetchSemesters();
    }

    if (selectedSemester != null) {
      final fetchedDepartments = await widget.fetchDepartments(
        selectedSemester!,
      );
      if (!mounted) return;
      setState(() {
        widget.departments.clear();
        widget.departments.addAll(fetchedDepartments);
        if (!widget.departments.contains(selectedDepartment)) {
          selectedDepartment = null;
        }
      });
    }

    if (!mounted) return;
    setState(() => isLoading = false);
  }

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.red),
    );
  }

  Future<void> _onSemesterChanged(String semester) async {
    setState(() {
      selectedDepartment = null;
      isLoading = true;
    });

    try {
      final fetchedDepartments = await widget.fetchDepartments(semester);
      if (!mounted) return;
      setState(() {
        widget.departments.clear();
        widget.departments.addAll(fetchedDepartments);
        selectedSemester = semester;
        isLoading = false;
      });
    } catch (e) {
      setState(() => isLoading = false);
      _showError("Failed to fetch departments");
    }
  }

  Future<void> _updateUser() async {
    String finalUsername = isGuest ? guestId! : widget.username;

    if (isGuest) {
      final inputName = guestUsernameController.text.trim();
      if (inputName.isEmpty) {
        _showError("Please enter a username to upgrade your account");
        return;
      }
      finalUsername = inputName;

      try {
        await widget.registerUser(
          finalUsername,
          selectedSemester,
          selectedDepartment,
        );

        final prefs = await SharedPreferences.getInstance();
        if (isGuest) {
          await prefs.setBool('is_guest', false);
          await prefs.setString('username', finalUsername);
          isGuest = false;
        }

        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text("Settings updated successfully!"),
            backgroundColor: Colors.green,
          ),
        );
        Navigator.pop(context, {
          'semester': selectedSemester,
          'department': selectedDepartment,
          'username': finalUsername,
        });
      } catch (e) {
        _showError("Failed to update settings");
      }
    }
    ////
    else {
      try {
        await widget.updateUser(
          finalUsername,
          selectedSemester,
          selectedDepartment,
          isUpgrade: isGuest,
        );

        final prefs = await SharedPreferences.getInstance();
        if (isGuest) {
          await prefs.setBool('is_guest', false);
          await prefs.setString('username', finalUsername);
          isGuest = false;
        }

        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text("Settings updated successfully!"),
            backgroundColor: Colors.green,
          ),
        );
        Navigator.pop(context, {
          'semester': selectedSemester,
          'department': selectedDepartment,
          'username': finalUsername,
        });
      } catch (e) {
        _showError("Failed to update settings");
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        iconTheme: const IconThemeData(color: Colors.white),
        title: const Text(
          "Edit Profile",
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
        ),
        centerTitle: true,
        backgroundColor: const Color.fromARGB(255, 2, 85, 152),
      ),
      body: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.only(top: 60.0, left: 30, right: 30),
          child: SingleChildScrollView(
            child: Column(
              children: [
                const Text(
                  "Update Settings",
                  style: TextStyle(
                    fontSize: 30,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 0.5,
                  ),
                ),
                const SizedBox(height: 40),

                if (isGuest)
                  TextFormField(
                    controller: guestUsernameController,
                    decoration: InputDecoration(
                      labelText: "Enter Username to Upgrade",
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(15),
                      ),
                      prefixIcon: const Icon(
                        Icons.person,
                        color: Color.fromARGB(255, 2, 85, 152),
                      ),
                    ),
                  ),
                if (isGuest) const SizedBox(height: 40),

                DropdownButtonFormField<String>(
                  style: const TextStyle(
                    fontSize: 25,
                    fontWeight: FontWeight.w500,
                    color: Color.fromARGB(255, 39, 38, 38),
                  ),
                  dropdownColor: const Color.fromARGB(255, 205, 207, 208),
                  decoration: InputDecoration(
                    contentPadding: const EdgeInsets.all(15),
                    prefixIcon: const Icon(
                      Icons.school,
                      color: Color.fromARGB(255, 2, 85, 152),
                    ),
                    label: const Text("Select Semester"),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(15),
                    ),
                  ),
                  // ignore: deprecated_member_use
                  value: widget.semesters.contains(selectedSemester)
                      ? selectedSemester
                      : null,
                  items: widget.semesters
                      .map((s) => DropdownMenuItem(value: s, child: Text(s)))
                      .toList(),
                  onChanged: (value) => _onSemesterChanged(value!),
                ),
                const SizedBox(height: 40),

                DropdownButtonFormField<String>(
                  style: const TextStyle(
                    fontSize: 25,
                    fontWeight: FontWeight.w500,
                    color: Color.fromARGB(255, 39, 38, 38),
                  ),
                  dropdownColor: const Color.fromARGB(255, 205, 207, 208),
                  decoration: InputDecoration(
                    contentPadding: const EdgeInsets.all(15),
                    prefixIcon: const Icon(
                      Icons.school,
                      color: Color.fromARGB(255, 2, 85, 152),
                    ),
                    label: const Text("Select Department"),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(15),
                    ),
                  ),
                  // ignore: deprecated_member_use
                  value: widget.departments.contains(selectedDepartment)
                      ? selectedDepartment
                      : null,
                  items: widget.departments
                      .map((d) => DropdownMenuItem(value: d, child: Text(d)))
                      .toList(),
                  onChanged: (value) =>
                      setState(() => selectedDepartment = value),
                ),
                const SizedBox(height: 80),

                ElevatedButton(
                  onPressed:
                      (selectedSemester != null && selectedDepartment != null)
                      ? _updateUser
                      : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color.fromARGB(255, 2, 85, 152),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 50,
                      vertical: 15,
                    ),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(15),
                    ),
                  ),
                  child: const Text(
                    "Save Changes",
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
