import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:study_bot_android_app/Pages/api_services.dart';
import 'package:study_bot_android_app/Pages/edit_settings.dart';
import 'package:url_launcher/url_launcher.dart';

class Profile extends StatefulWidget {
  const Profile({super.key});

  @override
  State<Profile> createState() => _ProfileState();
}

class _ProfileState extends State<Profile> {
  String selectedSemester = "Not Selected";
  String selectedDepartment = "Not Selected";
  String username = "Not Selected";
  bool isGuest = false;
  bool isLoading = true;

  late Future<List<String>> Function(String) fetchDepartments;
  late Future<void> Function() fetchSemesters;
  late Future<void> Function (String, String?, String?) registerUser;
  late Future<void> Function(String, String?, String?, {bool isUpgrade})
  updateUser;

  List<String> semesters = [];
  List<String> departments = [];
  final ApiClient _apiClient = ApiClient();

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _initializeProfile();
  }

  Future<void> _initializeProfile() async {
    setState(() => isLoading = true);

    final args =
        ModalRoute.of(context)?.settings.arguments as Map<String, dynamic>? ??
        {};

    // Get data from arguments
    username = args['username'] ?? "User";
    isGuest = args['isGuest'] ?? true;
    fetchDepartments = args['fetchDepartments'];
    fetchSemesters = args['fetchSemesters'];
    updateUser = args['updateUser'];
    registerUser = args['registerUser'];
    semesters = args['semesters'] ?? [];
    departments = args['departments'] ?? [];
    selectedSemester = args['selectedSemester'] ?? "Not Selected";
    selectedDepartment = args['selectedDepartment'] ?? "Not Selected";

    // If we have real data from arguments, use it
    if (selectedSemester != "Not Selected" &&
        selectedDepartment != "Not Selected") {
      setState(() => isLoading = false);
      return;
    }

    // Otherwise, fetch from server
    final prefs = await SharedPreferences.getInstance();
    final currentIsGuest = prefs.getBool('is_guest') ?? true;
    final currentUsername =
        prefs.getString('username') ?? (isGuest ? "Guest" : "User");

    try {
      final response = await _apiClient.userService.fetchSettings(
        currentUsername,
      );

      if (response.success && response.data != null && mounted) {
        setState(() {
          selectedSemester = response.data!['semester'] ?? "Not Selected";
          selectedDepartment = response.data!['department'] ?? "Not Selected";
          isGuest = response.data!['is_guest'] ?? currentIsGuest;
          username = currentUsername;
          isLoading = false;
        });
      } else {
        setState(() => isLoading = false);
      }
    } catch (_) {
      setState(() => isLoading = false);
    }
  }

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.red,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 3),
      ),
    );
  }

  // void _showSuccess(String message) {
  //   if (!mounted) return;
  //   ScaffoldMessenger.of(context).showSnackBar(
  //     SnackBar(
  //       content: Text(message),
  //       backgroundColor: Colors.green,
  //       behavior: SnackBarBehavior.floating,
  //       duration: const Duration(seconds: 3),
  //     ),
  //   );
  // }

  void openWebsite(String urlString) async {
    final Uri url = Uri.parse(urlString);
    try {
      if (!await launchUrl(url, mode: LaunchMode.externalApplication)) {
        _showError("Could not launch $urlString");
      }
    } catch (e) {
      _showError("An error occurred: $e");
    }
  }

  String get semesterNumber =>
      RegExp(r'\d+').firstMatch(selectedSemester)?.group(0) ?? "—";

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
          "Profile",
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
        ),
        centerTitle: true,
        backgroundColor: const Color.fromARGB(255, 2, 85, 152),
      ),
      body: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.all(30.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              CircleAvatar(
                radius: 70,
                backgroundImage: const AssetImage('assets/user_avatar.png'),
              ),
              const SizedBox(height: 40),
              Text(
                isGuest ? "Guest" : username,
                style: const TextStyle(
                  fontSize: 25,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 2,
                ),
              ),
              if (isGuest) ...[
                const SizedBox(height: 10),
                const Text(
                  "Guest Account",
                  style: TextStyle(
                    fontSize: 16,
                    color: Colors.grey,
                    fontStyle: FontStyle.italic,
                  ),
                ),
              ],
              Divider(height: 40, color: Colors.grey[400]),
              const SizedBox(height: 30),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    "Semester:",
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.w500),
                  ),
                  Padding(
                    padding: const EdgeInsets.only(right: 50.0),
                    child: Text(
                      semesterNumber,
                      style: const TextStyle(fontSize: 20),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 30),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    "Department:",
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.w500),
                  ),
                  Text(selectedDepartment, style: const TextStyle(fontSize: 20)),
                ],
              ),
              const SizedBox(height: 30),
              Divider(height: 40, color: Colors.grey[400]),
              const SizedBox(height: 10),
              Column(
                children: [
                  ListTile(
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                    tileColor: Colors.grey[200],
                    hoverColor: Colors.grey[300],
                    leading: const Icon(
                      Icons.edit,
                      color: Color.fromARGB(255, 2, 85, 152),
                      size: 30,
                    ),
                    title: Text(
                      isGuest ? "Upgrade Profile" : "Edit Profile",
                      style: const TextStyle(
                        color: Colors.black,
                        fontSize: 20,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    onTap: () async {
                      final result = await Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (context) => EditSettings(
                            semesters: semesters,
                            departments: departments,
                            selectedSemester: selectedSemester,
                            selectedDepartment: selectedDepartment,
                            fetchDepartments: fetchDepartments,
                            fetchSemesters: fetchSemesters,
                            updateUser: updateUser,
                            registerUser :  registerUser,
                            username: username,
                          ),
                        ),
                      );
        
                      // If profile was updated, refresh
                      if (result != null && mounted) {
                        await _initializeProfile();
                      }
                    },
                  ),
                  const SizedBox(height: 4),
                  ListTile(
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                    tileColor: Colors.grey[200],
                    hoverColor: Colors.grey[300],
                    leading: const Icon(Icons.info, color: Colors.blue, size: 30),
                    title: const Text(
                      "About App",
                      style: TextStyle(
                        color: Colors.black,
                        fontSize: 20,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    onTap: () => openWebsite("https://studybot.viewdns.net"),
                  ),
                  const SizedBox(height: 4),
                  ListTile(
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                    tileColor: Colors.grey[200],
                    hoverColor: Colors.grey[300],
                    leading: const Icon(Icons.link, color: Colors.blue, size: 30),
                    title: const Text(
                      "Website",
                      style: TextStyle(
                        color: Colors.black,
                        fontSize: 20,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    onTap: () => openWebsite("https://studybot.viewdns.net"),
                  ),
                  const SizedBox(height: 4),
                  ListTile(
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                    tileColor: Colors.grey[200],
                    hoverColor: Colors.grey[300],
                    leading: const Icon(
                      Icons.logout,
                      color: Colors.red,
                      size: 30,
                    ),
                    title: const Text(
                      "Logout",
                      style: TextStyle(
                        color: Colors.red,
                        fontSize: 20,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    onTap: () async {
                      final prefs = await SharedPreferences.getInstance();
                      await prefs.clear();
                      if (!context.mounted) return;
                      Navigator.pushNamedAndRemoveUntil(
                        context,
                        '/login',
                        (route) => false,
                      );
                    },
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
