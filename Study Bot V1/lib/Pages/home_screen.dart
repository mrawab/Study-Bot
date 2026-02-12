import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:study_bot_android_app/Pages/api_services.dart';
import 'package:study_bot_android_app/Pages/add_settings.dart';
import 'package:study_bot_android_app/Pages/home_widget.dart';
import 'package:study_bot_android_app/Pages/subjects.dart';
import 'package:uuid/uuid.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late String username;
  String? guestId;
  bool isGuest = false;
  bool userExists = false;
  bool loading = true;

  List<String> semesters = [];
  List<String> departments = [];
  String? selectedSemester;
  String? selectedDepartment;
  String? currentUser;

  int _selectedIndex = 0;

  final ApiClient _apiClient = ApiClient();

  @override
  void initState() {
    super.initState();
    _initializeUser();
  }

  void _showSuccess(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.green,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 3),
      ),
    );
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

  /// INITIALIZE USER: guestId, username, settings
  Future<void> _initializeUser() async {
    final prefs = await SharedPreferences.getInstance();

    isGuest = prefs.getBool('is_guest') ?? true;
    username = prefs.getString('username') ?? "";
    guestId = prefs.getString('guest_id');

    if (isGuest && guestId == null) {
      guestId = const Uuid().v4();
      await prefs.setString('guest_id', guestId!);
    }

    final displayName = isGuest
        ? "Guest"
        : (username.isNotEmpty ? username : "User");

    // Fetch semesters
    try {
      final semResponse = await _apiClient.lectureService.fetchSemesters();
      if (semResponse.success && semResponse.data != null) {
        semesters = semResponse.data!;
      }
    } catch (_) {}

    // Fetch user settings from API
    final usernameForApi = isGuest ? (guestId ?? "Guest") : username;
    try {
      final response = await _apiClient.userService.fetchSettings(
        usernameForApi,
      );
      if (response.success && response.data != null) {
        selectedSemester = response.data!['semester'];
        selectedDepartment = response.data!['department'];
        userExists = true;
        prefs.setBool('add_settings_shown', false);

        if (response.data!.containsKey('is_guest')) {
          isGuest = response.data!['is_guest'] ?? isGuest;
          if (!isGuest && username.isEmpty) {
            username = usernameForApi;
          }
        }

        if (selectedSemester != null) {
          departments = await _fetchDepartments(selectedSemester!);
        }
      } else {
        isGuest = true;
        userExists = false;
      }
    } catch (_) {
      userExists = false;
    }

    if (!mounted) return;

    setState(() {
      loading = false;
      currentUser = displayName;
    });

    // Show AddSettings if guest or no settings exist
    final addSettingsShown = prefs.getBool('add_settings_shown') ?? false;
    if ((!userExists && isGuest) || addSettingsShown) {
      await prefs.setBool('add_settings_shown', true);
      if (!mounted) return;
      _openAddSettings();
    }
  }

  /// OPEN ADD SETTINGS PAGE
  Future<void> _openAddSettings() async {
    if (!mounted) return;
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => AddSettings(
          semesters: semesters,
          departments: departments,
          selectedSemester: selectedSemester,
          selectedDepartment: selectedDepartment,
          fetchDepartments: _fetchDepartments,
          registerUser: _registerUser,
          registerUserGuest: _registerUserGuest,
          username: isGuest ? (guestId ?? "Guest") : username,
        ),
      ),
    );

    if (!mounted) return;
    await _refreshUserData();
  }

  /// REFRESH USER DATA
  Future<void> _refreshUserData() async {
    final prefs = await SharedPreferences.getInstance();
    isGuest = prefs.getBool('is_guest') ?? true;
    username = prefs.getString('username') ?? "";
    setState(() {
      currentUser = isGuest ? "Guest" : username;
    });
  }

  /// FETCH DEPARTMENTS
  Future<List<String>> _fetchDepartments(String semester) async {
    try {
      final response = await _apiClient.lectureService.fetchDepartments(
        semester,
      );
      if (response.success && response.data != null) {
        if (!mounted) return [];
        setState(() {
          departments = response.data!;
          selectedDepartment = null;
        });
        return response.data!;
      } else {
        if (mounted) _showError(response.error ?? "Failed to load departments");
        return [];
      }
    } catch (_) {
      if (mounted) _showError("Network error. Please try again.");
      return [];
    }
  }

  /// REGISTER USER
  Future<void> _registerUser(
    String username,
    String? semester,
    String? department,
  ) async {
    if (semester == null || department == null) return;

    final response = await _apiClient.userService.register(
      name: username,
      semester: semester,
      department: department,
      isGuest: false,
    );

    if (!mounted) return;
    if (response.success && response.data == true) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool('is_guest', false);
      await prefs.setString('username', username);

      setState(() {
        selectedSemester = semester;
        selectedDepartment = department;
        userExists = true;
        isGuest = false;
        this.username = username;
        currentUser = username;
      });

      _showSuccess("Registration successful!");
    } else {
      _showError(response.error ?? "Registration failed");
    }
  }

  /// REGISTER GUEST
  Future<void> _registerUserGuest(
    String username,
    String? semester,
    String? department,
  ) async {
    if (semester == null || department == null) return;

    final response = await _apiClient.userService.register(
      name: username,
      semester: semester,
      department: department,
      isGuest: true,
    );

    if (!mounted) return;
    if (response.success && response.data == true) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool('is_guest', true);
      await prefs.setString('username', username);
      await prefs.setBool('add_settings_shown', true);

      setState(() {
        selectedSemester = semester;
        selectedDepartment = department;
        userExists = true;
        this.username = username;
        currentUser = "Guest";
      });

      _showSuccess("Guest settings saved!");
    } else {
      _showError(response.error ?? "Guest registration failed");
    }
  }

  /// BUILD HOME PAGE
  Widget _buildHomePage() {
    final displayName = currentUser ?? "Guest";

    return Home(displayName: displayName, isGuest: isGuest);
  }

  void _onItemTapped(int index) {
    if (index == 2) {
      // Navigate to Profile page with arguments
      Navigator.pushNamed(
        context,
        '/profile',
        arguments: {
          'username': username,
          'selectedSemester': selectedSemester,
          'selectedDepartment': selectedDepartment,
          'departments': departments,
          'semesters': semesters,
          'fetchDepartments': _fetchDepartments,
          'fetchSemesters': () async => semesters,
          'updateUser': updateUser,
          'registerUser': _registerUser,
          'isGuest': isGuest,
        },
      );
      return;
    }
    setState(() => _selectedIndex = index);
  }

  String _getAppBarTitle() {
    switch (_selectedIndex) {
      case 0:
        return "Home";
      case 1:
        return "Subjects";
      case 2:
        return "Profile";
      default:
        return "Study Bot";
    }
  }

  Future<void> updateUser(
    String username,
    String? semester,
    String? department, {
    bool isUpgrade = false,
    String? oldName,
  }) async {
    if (semester == null || department == null) return;

    final response = await _apiClient.userService.updateUser(
      name: username,
      semester: semester,
      department: department,
      upgrade: isUpgrade,
      oldName: oldName,
    );

    if (!mounted) return;
    if (response.success && response.data == true) {
      if (isUpgrade) {
        final prefs = await SharedPreferences.getInstance();
        await prefs.setBool('is_guest', false);
        await prefs.setString('username', username);

        setState(() {
          isGuest = false;
          this.username = username;
          currentUser = username;
        });
      }

      setState(() {
        selectedSemester = semester;
        selectedDepartment = department;
      });

      _showSuccess("Settings updated successfully!");
    } else {
      _showError(response.error ?? "Update failed");
    }
  }

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        elevation: 1.0,
        leading: IconButton(
          onPressed: () {
            _showError("Ohh silly you $username We Did not Add This Feature Yet");
            _showSuccess("Stay Tuned");
          },
          icon: Icon(Icons.menu),
          color: Colors.black,
        ),
        titleSpacing: 6.0,
        title: Text(
          _getAppBarTitle(),
          style: const TextStyle(
            fontWeight: FontWeight.bold,
            color: Colors.black,
          ),
        ),
        backgroundColor: Colors.white,
        // Color.fromARGB(255, 2, 85, 152)
        centerTitle: true,
      ),
      body: _selectedIndex == 2
          ? const SizedBox() // Profile handled via Navigator
          : IndexedStack(
              index: _selectedIndex,
              children: [_buildHomePage(), Subjects()],
            ),
      bottomNavigationBar: BottomNavigationBar(
        backgroundColor: Colors.white,
        elevation: 1.0,
        currentIndex: _selectedIndex,
        onTap: _onItemTapped,
        type: BottomNavigationBarType.fixed,
        selectedItemColor: Colors.blue,
        unselectedItemColor: Colors.grey,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.home), label: "Home"),
          BottomNavigationBarItem(icon: Icon(Icons.book), label: "Subjects"),
          BottomNavigationBarItem(icon: Icon(Icons.person), label: "Profile"),
        ],
      ),
    );
  }
}
